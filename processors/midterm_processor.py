"""
midterm_processor.py — Loads the Canvas midterm grade export and filters at-risk students.

At-risk definition: MIDTERMGRADE is C- or lower (C-, D+, D, D-, F).
W, WM, and similar withdrawal codes are excluded per spec.

Produces a clean DataFrame ready for aggregation and group matching.
"""

import logging
from pathlib import Path
from typing import Tuple

import pandas as pd

from utils.config import MIDTERM_AT_RISK_GRADES, PROGRESS_REPORT_EXTENSIONS
from utils.settings_manager import get_settings
from utils.normalization import normalize_student_id_series, normalize_string_series
from utils.validation import validate_required_columns
from utils.logging_utils import QALog

logger = logging.getLogger("intervention_sorter")


class MidtermProcessor:
    """
    Loads and pre-processes the Canvas midterm grade export.
    """

    def __init__(self, qa_log: QALog) -> None:
        self.qa_log = qa_log
        self._total_input_rows: int = 0
        self._total_at_risk_rows: int = 0
        self._duplicate_rows_removed: int = 0

    def load(self, file_path: Path) -> Tuple[pd.DataFrame, dict]:
        """
        Load and process the midterm grade file.

        Returns:
            (at_risk_df, metrics_dict)
        """
        logger.info("MidtermProcessor: Loading '%s'", file_path.name)

        suffix = file_path.suffix.lower()
        if suffix not in PROGRESS_REPORT_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type '{suffix}'. "
                f"Supported: {', '.join(PROGRESS_REPORT_EXTENSIONS)}"
            )

        df_raw = self._read_file(file_path)
        self._total_input_rows = len(df_raw)
        logger.info("MidtermProcessor: %d rows loaded", self._total_input_rows)

        # Strip column headers
        df_raw.columns = [str(c).strip() for c in df_raw.columns]

        # Validate required columns
        validation = validate_required_columns(
            df_raw, get_settings().midterm_required_columns, f"Midterm File ({file_path.name})"
        )
        if not validation.is_valid:
            raise ValueError("\n".join(validation.errors))

        df = self._normalize_columns(df_raw, file_path.name)
        df_at_risk = self._filter_at_risk(df)
        self._total_at_risk_rows = len(df_at_risk)
        logger.info("MidtermProcessor: %d at-risk rows", self._total_at_risk_rows)

        if df_at_risk.empty:
            logger.warning("MidtermProcessor: No at-risk students found.")

        df_clean = self._remove_duplicates(df_at_risk, file_path.name)

        metrics = {
            "total_input_rows":          self._total_input_rows,
            "total_at_risk_rows":        self._total_at_risk_rows,
            "duplicate_rows_removed":    self._duplicate_rows_removed,
        }
        logger.info(
            "MidtermProcessor: Complete. %d clean rows, %d duplicates removed.",
            len(df_clean), self._duplicate_rows_removed,
        )
        return df_clean, metrics

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _read_file(self, file_path: Path) -> pd.DataFrame:
        suffix = file_path.suffix.lower()
        try:
            if suffix == ".csv":
                for encoding in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
                    try:
                        df = pd.read_csv(
                            file_path, dtype=str, keep_default_na=False, encoding=encoding
                        )
                        logger.info("MidtermProcessor: CSV loaded with encoding '%s'", encoding)
                        return df
                    except UnicodeDecodeError:
                        continue
                raise RuntimeError(f"Could not decode CSV '{file_path.name}'")
            else:
                return pd.read_excel(
                    file_path, dtype=str, keep_default_na=False, engine="openpyxl"
                )
        except Exception as exc:
            self.qa_log.log("FILE_LOAD_ERROR",
                detail=f"Could not load midterm file: {exc}",
                source_file=file_path.name)
            raise RuntimeError(
                f"Cannot open midterm file '{file_path.name}': {exc}"
            ) from exc

    def _normalize_columns(self, df: pd.DataFrame, source: str) -> pd.DataFrame:
        col = get_settings().midterm_map
        result = df.copy()

        result["Student ID"]   = normalize_student_id_series(result[col["student_id"]])
        result["Last Name"]    = normalize_string_series(result[col["last_name"]])
        result["First Name"]   = normalize_string_series(result[col["first_name"]])
        result["Student Name"] = result["Last Name"] + ", " + result["First Name"]

        # Email from midterm file (FAU_EMAIL) — used if contact report has no match
        result["Midterm Email"] = (
            normalize_string_series(result[col["email"]])
            if col["email"] in result.columns else ""
        )

        # Course fields
        result["Course Prefix"] = normalize_string_series(result[col["course_prefix"]])
        result["Course Num"]    = normalize_string_series(result[col["course_number"]])
        result["Course Number"] = result["Course Prefix"] + result["Course Num"]
        result["Course"]        = (
            normalize_string_series(result[col["course_name"]])
            if col["course_name"] in result.columns else result["Course Number"]
        )
        result["Section"]       = (
            normalize_string_series(result[col["section"]])
            if col["section"] in result.columns else ""
        )

        # Student info
        result["College"]        = (
            normalize_string_series(result[col["college"]])
            if col["college"] in result.columns else ""
        )
        result["Major"]          = (
            normalize_string_series(result[col["major"]])
            if col["major"] in result.columns else ""
        )
        result["Classification"] = (
            normalize_string_series(result[col["classification"]])
            if col["classification"] in result.columns else ""
        )

        # Midterm grade — normalized to uppercase stripped string
        result["Midterm Grade"] = normalize_string_series(result[col["midterm_grade"]])

        # Flag blank Student IDs
        blank_mask = result["Student ID"] == ""
        if blank_mask.any():
            logger.warning("MidtermProcessor: %d rows with blank Student ID", blank_mask.sum())
            for _, row in result[blank_mask].iterrows():
                self.qa_log.log("BLANK_STUDENT_ID",
                    detail=f"Blank Student ID. Course: {row.get('Course Number', '')}",
                    source_file=source)

        return result

    def _filter_at_risk(self, df: pd.DataFrame) -> pd.DataFrame:
        """Keep only rows where Midterm Grade is C- or lower."""
        mask = df["Midterm Grade"].str.strip().str.lower().isin(MIDTERM_AT_RISK_GRADES)
        return df[mask].copy()

    def _remove_duplicates(self, df: pd.DataFrame, source: str) -> pd.DataFrame:
        """Remove duplicate (Student ID + Course Number) rows."""
        dup_mask = df.duplicated(subset=["Student ID", "Course Number"], keep="first")
        dup_count = dup_mask.sum()
        if dup_count > 0:
            logger.info("MidtermProcessor: Removing %d duplicate rows", dup_count)
            for _, row in df[dup_mask].iterrows():
                self.qa_log.log("DUPLICATE_COURSE_ROW",
                    student_id=row["Student ID"],
                    detail=f"Duplicate removed: {row.get('Course Number', '')}",
                    source_file=source)
        self._duplicate_rows_removed = dup_count
        return df[~dup_mask].copy()
