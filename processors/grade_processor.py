"""
grade_processor.py — Loads the progress report (xlsx or csv) and filters at-risk students.
Uses PROGRESS_REPORT_COLUMN_MAP from config to handle any column naming convention.
"""

import logging
from pathlib import Path
from typing import Tuple

import pandas as pd

from utils.config import PROGRESS_REPORT_EXTENSIONS
from utils.settings_manager import get_settings
from utils.normalization import (
    normalize_student_id_series,
    normalize_at_risk_series,
    normalize_string_series,
    normalize_absences,
)
from utils.validation import validate_required_columns
from utils.logging_utils import QALog

logger = logging.getLogger("intervention_sorter")


class GradeProcessor:
    def __init__(self, qa_log: QALog) -> None:
        self.qa_log = qa_log
        self._total_input_rows: int = 0
        self._total_at_risk_rows: int = 0
        self._duplicate_course_rows_removed: int = 0

    def load(self, file_path: Path) -> Tuple[pd.DataFrame, dict]:
        logger.info("GradeProcessor: Loading progress report from '%s'", file_path.name)

        suffix = file_path.suffix.lower()
        if suffix not in PROGRESS_REPORT_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type '{suffix}'. "
                f"Supported formats: {', '.join(PROGRESS_REPORT_EXTENSIONS)}"
            )

        df_raw = self._read_file(file_path)
        self._total_input_rows = len(df_raw)
        logger.info("GradeProcessor: %d total rows loaded", self._total_input_rows)

        # Validate required columns using mapped names
        validation = validate_required_columns(
            df_raw, get_settings().progress_required_columns, f"Progress Report ({file_path.name})"
        )
        if not validation.is_valid:
            raise ValueError("\n".join(validation.errors))

        df = self._normalize_columns(df_raw, file_path.name)
        df_at_risk = self._filter_at_risk(df)
        self._total_at_risk_rows = len(df_at_risk)
        logger.info("GradeProcessor: %d at-risk rows after filtering", self._total_at_risk_rows)

        if df_at_risk.empty:
            logger.warning("GradeProcessor: No at-risk students found.")

        df_clean = self._remove_duplicate_course_rows(df_at_risk, file_path.name)

        metrics = {
            "total_input_rows": self._total_input_rows,
            "total_at_risk_rows": self._total_at_risk_rows,
            "duplicate_course_rows_removed": self._duplicate_course_rows_removed,
        }
        logger.info(
            "GradeProcessor: Complete. %d clean at-risk rows. %d duplicates removed.",
            len(df_clean), self._duplicate_course_rows_removed,
        )
        return df_clean, metrics

    def _read_file(self, file_path: Path) -> pd.DataFrame:
        suffix = file_path.suffix.lower()
        try:
            if suffix == ".csv":
                # Try common encodings for CSVs exported from institutional systems
                for encoding in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
                    try:
                        df = pd.read_csv(
                            file_path, dtype=str, keep_default_na=False, encoding=encoding
                        )
                        logger.info("GradeProcessor: CSV loaded with encoding '%s'", encoding)
                        return df
                    except UnicodeDecodeError:
                        continue
                raise RuntimeError(f"Could not decode CSV file '{file_path.name}'")
            else:
                return pd.read_excel(
                    file_path, dtype=str, keep_default_na=False, engine="openpyxl"
                )
        except Exception as exc:
            self.qa_log.log("FILE_LOAD_ERROR",
                detail=f"Could not load progress report: {exc}",
                source_file=file_path.name)
            raise RuntimeError(f"Cannot open progress report '{file_path.name}': {exc}") from exc

    def _normalize_columns(self, df: pd.DataFrame, source: str) -> pd.DataFrame:
        """Rename file columns to internal names using PROGRESS_REPORT_COLUMN_MAP."""
        result = df.copy()
        col = get_settings().progress_report_map

        # Rename to internal standard names
        result["Student Name"] = normalize_string_series(result[col["student_name"]])
        result["Student ID"]   = normalize_student_id_series(result[col["student_id"]])
        result["Course"]       = normalize_string_series(result[col["course"]])

        # Course number (e.g. MAC1105) — optional, blank if not present
        course_num_col = col.get("course_number", "")
        result["Course Number"] = (
            normalize_string_series(result[course_num_col])
            if course_num_col and course_num_col in result.columns else ""
        )
        result["__at_risk_bool"] = normalize_at_risk_series(result[col["at_risk"]])

        # Optional columns — use mapped name if present, else blank
        grade_col = col["letter_grade"]
        result["Current Grade"] = (
            normalize_string_series(result[grade_col])
            if grade_col in result.columns else ""
        )

        abs_col = col["absences"]
        result["Absences"] = (
            result[abs_col].apply(normalize_absences)
            if abs_col in result.columns else 0.0
        )

        ar_col = col["alert_reasons"]
        result["Alert Reasons"] = (
            normalize_string_series(result[ar_col])
            if ar_col in result.columns else ""
        )

        comment_col = col["comments"]
        result["Comments"] = (
            normalize_string_series(result[comment_col])
            if comment_col in result.columns else ""
        )

        # Flag blank Student IDs
        blank_mask = result["Student ID"] == ""
        if blank_mask.any():
            count = blank_mask.sum()
            logger.warning("GradeProcessor: %d rows have blank Student ID", count)
            for _, row in result[blank_mask].iterrows():
                self.qa_log.log("BLANK_STUDENT_ID",
                    detail=f"Blank Student ID. Course: {row.get('Course', '')}",
                    source_file=source)

        return result

    def _filter_at_risk(self, df: pd.DataFrame) -> pd.DataFrame:
        return df[df["__at_risk_bool"]].copy()

    def _remove_duplicate_course_rows(self, df: pd.DataFrame, source: str) -> pd.DataFrame:
        dup_mask = df.duplicated(subset=["Student ID", "Course"], keep="first")
        dup_count = dup_mask.sum()
        if dup_count > 0:
            logger.info("GradeProcessor: Removing %d duplicate (Student ID + Course) rows", dup_count)
            for _, row in df[dup_mask].iterrows():
                self.qa_log.log("DUPLICATE_COURSE_ROW", student_id=row["Student ID"],
                    detail=f"Duplicate course row removed: {row.get('Course', '')}",
                    source_file=source)
        self._duplicate_course_rows_removed = dup_count
        return df[~dup_mask].copy()
