"""
midterm_pipeline_controller.py — Orchestrates the midterm grade processing pipeline.

Steps:
  1. Validate inputs
  2. Load + filter midterm file (C- and below only)
  3. Aggregate to one row per student
  4. Merge contact info
  5. Group matching (same first-match-wins logic)
  6. Export output workbook
"""

import logging
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Any

import pandas as pd

from processors.midterm_processor import MidtermProcessor
from processors.midterm_aggregator import MidtermAggregator
from processors.contact_processor import ContactProcessor
from processors.group_matcher import GroupMatcher
from processors.exporter import Exporter
from utils.config import (
    MIDTERM_OUTPUT_COLUMNS,
    MIDTERM_OUTPUT_FILENAME_PATTERN,
    LOG_DATE_FORMAT,
    UNMATCHED_LOW_TAB,
    UNMATCHED_HIGH_TAB,
    ASSIGNED_STUDENTS_PATH,
)
from utils.validation import (
    validate_file_exists,
    validate_file_readable,
    validate_output_path,
    ValidationResult,
)
from utils.logging_utils import QALog, setup_logger
from processors.campaign_manager import CampaignManager
from processors.semester_manager import SemesterManager

logger = logging.getLogger("intervention_sorter")


@dataclass
class MidtermPipelineInputs:
    midterm_file:   Path
    contact_report: Path
    control_file:   Path
    group_dir:      Path
    output_dir:     Path
    exclude_previous: bool = False
    skip_groups: set = None  # Group tab names to skip (students fall to buckets)
    season: str = ""
    checkpoint_type: str = "Midterm"


@dataclass
class MidtermPipelineResult:
    success: bool
    message: str = ""
    errors:  List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    output_path: Optional[Path] = None


class MidtermPipelineController:

    def __init__(self, progress_callback: Optional[Callable[[str], None]] = None) -> None:
        self.progress_callback = progress_callback or (lambda msg: None)
        self._qa_log = QALog()
        self._start_time: Optional[datetime] = None
        self._metrics: Dict[str, Any] = {}

    def run(self, inputs: MidtermPipelineInputs) -> MidtermPipelineResult:
        self._start_time = datetime.now()
        self._qa_log.clear()
        self._metrics = {}

        logger.info("=" * 60)
        logger.info("Midterm Pipeline starting: %s", self._start_time.strftime("%Y-%m-%d %H:%M:%S"))
        logger.info("=" * 60)

        try:
            # Step 1 — Validate
            self._update("Validating input files...")
            validation = self._validate_inputs(inputs)
            if not validation.is_valid:
                return MidtermPipelineResult(
                    success=False,
                    message="Input validation failed.",
                    errors=validation.errors,
                )

            # Step 2 — Load midterm file
            self._update("Loading midterm grade file...")
            processor = MidtermProcessor(self._qa_log)
            at_risk_df, metrics = processor.load(inputs.midterm_file)
            self._metrics.update(metrics)

            if at_risk_df.empty:
                return MidtermPipelineResult(
                    success=False,
                    message="No at-risk students found. Check that MIDTERMGRADE contains "
                            "grades of C- or lower (C-, D+, D, D-, F).",
                    errors=["No at-risk rows after filtering."],
                )

            # Step 3 — Aggregate
            self._update("Aggregating student records...")
            aggregator = MidtermAggregator()
            students_df = aggregator.aggregate(at_risk_df)
            self._metrics["total_distinct_students"] = len(students_df)
            logger.info("Midterm Pipeline: %d distinct at-risk students.", len(students_df))

            # Step 4 — Exclude previously assigned (if enabled)
            excluded_count = 0
            if inputs.exclude_previous:
                self._update("Checking for previously assigned students...")
                students_df, excluded_count = self._exclude_previous(students_df)
                self._metrics["excluded_previously_assigned"] = excluded_count
                if students_df.empty:
                    return MidtermPipelineResult(
                        success=False,
                        message="All at-risk students have already been assigned. "
                                "Delete assigned_students.txt to start a new campaign.",
                        errors=["No new students after exclusion."],
                    )

            # Step 5 — Merge contact info
            self._update("Merging contact information...")
            contact_proc = ContactProcessor(self._qa_log)
            contact_proc.load(inputs.contact_report)
            students_df = contact_proc.merge(students_df)
            self._metrics["contact_matches"] = contact_proc.contact_match_count
            self._metrics["contact_misses"]  = contact_proc.contact_miss_count

            # Step 6 — Group matching
            self._update("Matching students to groups...")
            matcher = GroupMatcher(self._qa_log)
            matcher.load_control_file(inputs.control_file, inputs.group_dir,
                                              skip_groups=inputs.skip_groups)
            group_data = matcher.match(students_df)
            group_order = [g.safe_tab_name for g in matcher.group_definitions]

            total_assigned = sum(
                len(group_data.get(tab, pd.DataFrame())) for tab in group_order
            )
            total_unmatched = (
                len(group_data.get(UNMATCHED_LOW_TAB, pd.DataFrame())) +
                len(group_data.get(UNMATCHED_HIGH_TAB, pd.DataFrame()))
            )
            self._metrics["total_assigned"]   = total_assigned
            self._metrics["total_unmatched"]  = total_unmatched
            self._metrics["total_risk_1_2"]   = len(group_data.get(UNMATCHED_LOW_TAB, pd.DataFrame()))
            self._metrics["total_risk_3_plus"] = len(group_data.get(UNMATCHED_HIGH_TAB, pd.DataFrame()))

            # Step 7 — Export
            self._update("Writing output workbook...")
            output_path = self._resolve_output_path(inputs.output_dir)
            duration = (datetime.now() - self._start_time).total_seconds()
            self._metrics.update({
                "processing_timestamp": self._start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "execution_duration":   duration,
                "output_filename":      output_path.name,
            })

            source_files = {
                "Midterm Grade File":    inputs.midterm_file.name,
                "Contact Report":        inputs.contact_report.name,
                "Control File":         inputs.control_file.name,
                "Group Files Directory": str(inputs.group_dir),
            }

            # Use the existing Exporter but pass MIDTERM_OUTPUT_COLUMNS
            exporter = MidtermExporter()
            exporter.export(
                group_data=group_data,
                group_order=group_order,
                qa_log=self._qa_log,
                metrics=self._metrics,
                output_path=output_path,
                source_files=source_files,
            )

            # Append to assigned students
            self._append_assigned_students(group_data, group_order)

            # Record campaign run
            if inputs.season:
                cm = CampaignManager()
                cm.record_run(
                    season=inputs.season,
                    checkpoint_type=inputs.checkpoint_type,
                    students_processed=len(students_df),
                    students_assigned=total_assigned,
                    students_unmatched=total_unmatched,
                    output_file=str(output_path),
                )

            # Record semester run
            sm = SemesterManager()
            if sm.has_active_semester():
                sm.save_file_paths(
                    contact_report=str(inputs.contact_report),
                    control_file=str(inputs.control_file),
                    group_folder=str(inputs.group_dir),
                )
                sm.record_run(
                    checkpoint_name=inputs.checkpoint_type,
                    students_processed=len(students_df),
                    students_assigned=total_assigned,
                    students_unmatched=total_unmatched,
                    output_file=str(output_path),
                )

            summary_lines = [
                f"Processing complete in {duration:.2f}s",
                f"Input rows: {self._metrics.get('total_input_rows', 0):,}",
                f"At-risk students: {len(students_df):,}",
                f"Previously assigned (excluded): {excluded_count:,}",
                f"Assigned to groups: {total_assigned:,}",
                f"Unmatched: {total_unmatched:,}",
                f"QA events: {self._qa_log.total()}",
            ]
            self._update("\n".join(summary_lines))

            return MidtermPipelineResult(
                success=True,
                message="\n".join(summary_lines),
                metrics=self._metrics,
                output_path=output_path,
            )

        except Exception as exc:
            error_detail = traceback.format_exc()
            logger.error("Midterm Pipeline: UNHANDLED EXCEPTION\n%s", error_detail)
            return MidtermPipelineResult(
                success=False,
                message=f"Processing failed: {exc}",
                errors=[str(exc), error_detail],
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_inputs(self, inputs: MidtermPipelineInputs) -> ValidationResult:
        result = ValidationResult(is_valid=True)
        for label, path in [
            ("Midterm File",    inputs.midterm_file),
            ("Contact Report",  inputs.contact_report),
            ("Control File",    inputs.control_file),
        ]:
            result.merge(validate_file_exists(path, label))
            result.merge(validate_file_readable(path, label))
        if not inputs.group_dir.exists():
            result.add_error(f"Group files directory not found: {inputs.group_dir}")
        result.merge(validate_output_path(inputs.output_dir))
        return result

    def _resolve_output_path(self, output_dir: Path) -> Path:
        timestamp = datetime.now().strftime(LOG_DATE_FORMAT)
        filename = MIDTERM_OUTPUT_FILENAME_PATTERN.format(timestamp=timestamp)
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir / filename

    def _exclude_previous(self, students_df: pd.DataFrame):
        if not ASSIGNED_STUDENTS_PATH.exists():
            return students_df, 0
        try:
            lines = ASSIGNED_STUDENTS_PATH.read_text(encoding="utf-8").splitlines()
            previously = {l.strip().upper() for l in lines if l.strip()}
        except Exception as exc:
            logger.warning("Midterm Pipeline: Could not read assigned_students.txt: %s", exc)
            return students_df, 0
        mask = students_df["Student ID"].isin(previously)
        excluded = int(mask.sum())
        return students_df[~mask].copy().reset_index(drop=True), excluded

    def _append_assigned_students(self, group_data: dict, group_order: list) -> None:
        all_tabs = list(group_order) + [UNMATCHED_LOW_TAB, UNMATCHED_HIGH_TAB]
        new_ids = []
        for tab in all_tabs:
            df = group_data.get(tab)
            if df is not None and not df.empty and "Student ID" in df.columns:
                new_ids.extend(df["Student ID"].tolist())
        if not new_ids:
            return
        ASSIGNED_STUDENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        existing = set()
        if ASSIGNED_STUDENTS_PATH.exists():
            try:
                existing = {l.strip().upper() for l in
                            ASSIGNED_STUDENTS_PATH.read_text(encoding="utf-8").splitlines()
                            if l.strip()}
            except Exception:
                pass
        truly_new = [sid for sid in new_ids if sid.upper() not in existing]
        if truly_new:
            with open(ASSIGNED_STUDENTS_PATH, "a", encoding="utf-8") as f:
                for sid in truly_new:
                    f.write(sid + "\n")
            logger.info("Midterm Pipeline: Appended %d IDs to assigned_students.txt", len(truly_new))

    def _update(self, message: str) -> None:
        logger.info("Midterm Pipeline: %s", message)
        self.progress_callback(message)


# ---------------------------------------------------------------------------
# Midterm-specific exporter (uses MIDTERM_OUTPUT_COLUMNS)
# ---------------------------------------------------------------------------

from processors.exporter import Exporter
from utils.config import MIDTERM_OUTPUT_COLUMNS
from utils.logging_utils import QALog


class MidtermExporter(Exporter):
    """Extends the base Exporter to use MIDTERM_OUTPUT_COLUMNS."""

    def export(self, group_data, group_order, qa_log, metrics, output_path, source_files):
        # Temporarily swap output columns
        import utils.config as cfg
        original = cfg.OUTPUT_COLUMNS
        cfg.OUTPUT_COLUMNS = MIDTERM_OUTPUT_COLUMNS
        try:
            super().export(group_data, group_order, qa_log, metrics, output_path, source_files)
        finally:
            cfg.OUTPUT_COLUMNS = original
