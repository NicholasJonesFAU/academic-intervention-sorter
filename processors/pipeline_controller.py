"""
pipeline_controller.py — Central orchestrator for the Intervention Sorter pipeline.

Responsibilities:
  - Sequence all processing steps
  - Propagate errors cleanly
  - Track processing metrics
  - Manage application state
  - Coordinate logging
  - Support validation-only mode

This is the single entry point for all business logic.
The GUI calls run() or validate_only() and receives a PipelineResult.
"""

import logging
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Any

import pandas as pd

from processors.grade_processor import GradeProcessor
from processors.contact_processor import ContactProcessor
from processors.aggregator import Aggregator
from processors.group_matcher import GroupMatcher
from processors.exporter import Exporter
from utils.config import (
    OUTPUT_COLUMNS,
    OUTPUT_FILENAME_PATTERN,
    LOG_DATE_FORMAT,
    UNMATCHED_LOW_TAB,
    UNMATCHED_HIGH_TAB,
)
from utils.validation import (
    validate_file_exists,
    validate_file_readable,
    validate_output_path,
    ValidationResult,
)
from utils.logging_utils import QALog, setup_logger
from processors.campaign_manager import CampaignManager

logger = logging.getLogger("intervention_sorter")


@dataclass
class PipelineInputs:
    """All file paths required to run the pipeline."""
    progress_report: Path
    contact_report: Path
    control_file: Path
    group_dir: Path
    output_dir: Path
    exclude_previous: bool = False
    season: str = ""
    checkpoint_type: str = "Progress Report"

@dataclass
class PipelineResult:
    """Encapsulates the outcome of a pipeline run."""
    success: bool
    message: str = ""
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    output_path: Optional[Path] = None
    validation_only: bool = False


class PipelineController:
    """
    Orchestrates the full processing pipeline.
    """

    def __init__(self, progress_callback: Optional[Callable[[str], None]] = None) -> None:
        """
        Args:
            progress_callback: Optional callable(message) for GUI status updates.
        """
        self.progress_callback = progress_callback or (lambda msg: None)
        self._qa_log = QALog()
        self._start_time: Optional[datetime] = None
        self._metrics: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, inputs: PipelineInputs) -> PipelineResult:
        """
        Execute the full processing pipeline.

        Returns a PipelineResult — never raises to the caller.
        """
        self._start_time = datetime.now()
        self._qa_log.clear()
        self._metrics = {}

        logger.info("=" * 60)
        logger.info("Pipeline starting: %s", self._start_time.strftime("%Y-%m-%d %H:%M:%S"))
        logger.info("=" * 60)

        try:
            # Step 1 — Validate inputs
            self._update("Validating input files...")
            validation = self._validate_inputs(inputs)
            if not validation.is_valid:
                return PipelineResult(
                    success=False,
                    message="Input validation failed.",
                    errors=validation.errors,
                    warnings=validation.warnings,
                )

            # Step 2 — Load & filter progress report
            self._update("Loading progress report...")
            grade_proc = GradeProcessor(self._qa_log)
            at_risk_df, grade_metrics = grade_proc.load(inputs.progress_report)
            self._metrics.update(grade_metrics)

            if at_risk_df.empty:
                return PipelineResult(
                    success=False,
                    message="No at-risk students found in the progress report. "
                            "Please check that the 'At-Risk' column contains TRUE values.",
                    errors=["No at-risk rows after filtering."],
                )

            # Step 3 — Aggregate to one row per student
            self._update("Aggregating student records...")
            aggregator = Aggregator()
            students_df = aggregator.aggregate(at_risk_df)
            self._metrics["total_distinct_students"] = len(students_df)
            logger.info("Pipeline: %d distinct at-risk students.", len(students_df))

            # Step 4 — Exclude previously assigned students (if enabled)
            excluded_count = 0
            if inputs.exclude_previous:
                self._update("Checking for previously assigned students...")
                students_df, excluded_count = self._exclude_previous(students_df)
                self._metrics["excluded_previously_assigned"] = excluded_count
                if students_df.empty:
                    return PipelineResult(
                        success=False,
                        message="All at-risk students have already been assigned in a previous run. "
                                "Delete assigned_students.txt in the output folder to start a new campaign.",
                        errors=["No new students remaining after exclusion."],
                    )

            # Step 5 — Merge contact info
            self._update("Merging contact information...")
            contact_proc = ContactProcessor(self._qa_log)
            contact_proc.load(inputs.contact_report)
            students_df = contact_proc.merge(students_df)
            self._metrics["contact_matches"] = contact_proc.contact_match_count
            self._metrics["contact_misses"] = contact_proc.contact_miss_count

            # Step 5 — Group matching
            self._update("Matching students to groups...")
            matcher = GroupMatcher(self._qa_log)
            matcher.load_control_file(inputs.control_file, inputs.group_dir)
            group_data = matcher.match(students_df)

            # Collect ordered group tab names (excluding unmatched buckets)
            group_order = [
                g.safe_tab_name for g in matcher.group_definitions
            ]

            # Calculate assignment metrics
            total_assigned = sum(
                len(group_data.get(tab, pd.DataFrame()))
                for tab in group_order
            )
            total_unmatched = (
                len(group_data.get(UNMATCHED_LOW_TAB, pd.DataFrame()))
                + len(group_data.get(UNMATCHED_HIGH_TAB, pd.DataFrame()))
            )
            self._metrics["total_assigned"] = total_assigned
            self._metrics["total_unmatched"] = total_unmatched
            self._metrics["total_risk_1_2"] = len(group_data.get(UNMATCHED_LOW_TAB, pd.DataFrame()))
            self._metrics["total_risk_3_plus"] = len(group_data.get(UNMATCHED_HIGH_TAB, pd.DataFrame()))

            logger.info(
                "Pipeline: Assigned: %d | Unmatched: %d",
                total_assigned,
                total_unmatched,
            )

            # Verify no student is lost
            total_out = total_assigned + total_unmatched
            if total_out != len(students_df):
                logger.error(
                    "Pipeline: INTEGRITY CHECK FAILED — In: %d, Out: %d",
                    len(students_df),
                    total_out,
                )
                self._qa_log.log(
                    "INFO",
                    detail=f"Integrity check: input={len(students_df)}, output={total_out}. "
                           f"Discrepancy detected.",
                    source_file="pipeline",
                )

            # Step 6 — Export
            self._update("Writing output workbook...")
            output_path = self._resolve_output_path(inputs.output_dir)
            end_time = datetime.now()
            duration = (end_time - self._start_time).total_seconds()

            self._metrics["processing_timestamp"] = self._start_time.strftime("%Y-%m-%d %H:%M:%S")
            self._metrics["execution_duration"] = duration
            self._metrics["output_filename"] = output_path.name

            source_files = {
                "Progress Report": inputs.progress_report.name,
                "Contact Report": inputs.contact_report.name,
                "Control File": inputs.control_file.name,
                "Group Files Directory": str(inputs.group_dir),
            }

            exporter = Exporter()
            exporter.export(
                group_data=group_data,
                group_order=group_order,
                qa_log=self._qa_log,
                metrics=self._metrics,
                output_path=output_path,
                source_files=source_files,
            )

            # Append all assigned students to tracking file
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

            # Summary
            excluded_count = self._metrics.get("excluded_previously_assigned", 0)
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

            return PipelineResult(
                success=True,
                message="\n".join(summary_lines),
                metrics=self._metrics,
                output_path=output_path,
            )

        except Exception as exc:
            error_detail = traceback.format_exc()
            logger.error("Pipeline: UNHANDLED EXCEPTION\n%s", error_detail)
            return PipelineResult(
                success=False,
                message=f"Processing failed: {exc}",
                errors=[str(exc), error_detail],
            )

    def validate_only(self, inputs: PipelineInputs) -> PipelineResult:
        """
        Run validation-only mode — check files and preview counts
        WITHOUT writing any output.
        """
        self._start_time = datetime.now()
        self._qa_log.clear()

        logger.info("Pipeline: Validation-only mode starting.")
        self._update("Running validation checks...")

        try:
            validation = self._validate_inputs(inputs)
            issues = []

            if not validation.is_valid:
                issues.extend(validation.errors)

            # Try loading progress report to count at-risk students
            preview_info = []
            try:
                grade_proc = GradeProcessor(self._qa_log)
                at_risk_df, grade_metrics = grade_proc.load(inputs.progress_report)
                preview_info.append(f"Total input rows: {grade_metrics.get('total_input_rows', 0):,}")
                preview_info.append(f"At-risk rows: {grade_metrics.get('total_at_risk_rows', 0):,}")
                preview_info.append(f"Duplicate course rows: {grade_metrics.get('duplicate_course_rows_removed', 0):,}")

                aggregator = Aggregator()
                students_df = aggregator.aggregate(at_risk_df)
                preview_info.append(f"Distinct at-risk students: {len(students_df):,}")
            except Exception as exc:
                issues.append(f"Progress report validation error: {exc}")

            # Try loading group matcher
            try:
                matcher = GroupMatcher(self._qa_log)
                matcher.load_control_file(inputs.control_file, inputs.group_dir)
                for g in matcher.group_definitions:
                    preview_info.append(f"Group '{g.tab_name}': {len(g.student_ids):,} IDs loaded")
            except Exception as exc:
                issues.append(f"Group file validation error: {exc}")

            preview_info.append(f"QA events detected: {self._qa_log.total()}")
            preview_info.extend([f"  WARNING: {w}" for w in validation.warnings])

            if issues:
                return PipelineResult(
                    success=False,
                    message="Validation failed — see errors below.",
                    errors=issues,
                    warnings=preview_info,
                    validation_only=True,
                )

            return PipelineResult(
                success=True,
                message="Validation passed.\n" + "\n".join(preview_info),
                warnings=preview_info,
                validation_only=True,
            )

        except Exception as exc:
            return PipelineResult(
                success=False,
                message=f"Validation error: {exc}",
                errors=[traceback.format_exc()],
                validation_only=True,
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_inputs(self, inputs: PipelineInputs) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        for label, path in [
            ("Progress Report", inputs.progress_report),
            ("Contact Report", inputs.contact_report),
            ("Control File", inputs.control_file),
        ]:
            result.merge(validate_file_exists(path, label))
            result.merge(validate_file_readable(path, label))

        if not inputs.group_dir.exists():
            result.add_error(
                f"Group files directory not found: {inputs.group_dir}"
            )

        result.merge(validate_output_path(inputs.output_dir))

        return result

    def _exclude_previous(self, students_df: pd.DataFrame):
        """
        Load assigned_students.txt and remove matching Student IDs.
        Returns (filtered_df, excluded_count).
        """
        from utils.config import ASSIGNED_STUDENTS_PATH
        if not ASSIGNED_STUDENTS_PATH.exists():
            logger.info("Pipeline: No assigned_students.txt found — no exclusions applied.")
            return students_df, 0
        try:
            lines = ASSIGNED_STUDENTS_PATH.read_text(encoding="utf-8").splitlines()
            previously_assigned = {line.strip().upper() for line in lines if line.strip()}
            logger.info("Pipeline: Loaded %d previously assigned IDs.", len(previously_assigned))
        except Exception as exc:
            logger.warning("Pipeline: Could not read assigned_students.txt: %s", exc)
            return students_df, 0

        mask = students_df["Student ID"].isin(previously_assigned)
        excluded_count = int(mask.sum())
        filtered_df = students_df[~mask].copy().reset_index(drop=True)
        logger.info("Pipeline: Excluded %d | %d remaining.", excluded_count, len(filtered_df))
        return filtered_df, excluded_count

    def _append_assigned_students(self, group_data: dict, group_order: list) -> None:
        """
        Append ALL assigned student IDs to assigned_students.txt —
        includes group-matched AND unmatched bucket students.
        """
        from utils.config import ASSIGNED_STUDENTS_PATH, UNMATCHED_LOW_TAB, UNMATCHED_HIGH_TAB

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
                existing = {
                    line.strip().upper()
                    for line in ASSIGNED_STUDENTS_PATH.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                }
            except Exception:
                pass

        truly_new = [sid for sid in new_ids if sid.upper() not in existing]
        if truly_new:
            with open(ASSIGNED_STUDENTS_PATH, "a", encoding="utf-8") as f:
                for sid in truly_new:
                    f.write(sid + "\n")
            logger.info(
                "Pipeline: Appended %d new IDs to assigned_students.txt (total: %d)",
                len(truly_new), len(existing) + len(truly_new),
            )

    def _resolve_output_path(self, output_dir: Path) -> Path:
        timestamp = datetime.now().strftime(LOG_DATE_FORMAT)
        filename = OUTPUT_FILENAME_PATTERN.format(timestamp=timestamp)
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir / filename

    def _update(self, message: str) -> None:
        logger.info("Pipeline: %s", message)
        self.progress_callback(message)
