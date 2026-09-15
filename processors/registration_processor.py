"""
registration_processor.py — Loads the course-registration extract and merges
per-student fields onto student records.

Registered Credits = sum of CREDIT_HR for rows whose REGISTRATION_STATUS is in
REGISTRATION_STATUS_ACTIVE_VALUES.

College, Major, Classification, Dual Enrollment, and FAU High come from the
first row per student.
"""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from utils.config import (
    AT_RISK_TRUE_VALUES,
    REGISTRATION_REPORT_COLUMN_MAP,
    REGISTRATION_REPORT_REQUIRED_COLUMNS,
    REGISTRATION_STATUS_ACTIVE_VALUES,
)
from utils.normalization import normalize_student_id_series, normalize_string_series
from utils.validation import validate_required_columns
from utils.logging_utils import QALog

logger = logging.getLogger("intervention_sorter")

REGISTRATION_COLUMNS = [
    "Registered Credits",
    "College",
    "Major",
    "Classification",
    "Dual Enrollment",
    "FAU High",
]


class RegistrationProcessor:
    def __init__(self, qa_log: QALog) -> None:
        self.qa_log = qa_log
        self._registration_df: Optional[pd.DataFrame] = None

    def load(self, file_path: Path) -> None:
        logger.info(
            "RegistrationProcessor: Loading registration extract from '%s'",
            file_path.name,
        )

        try:
            df_raw = pd.read_excel(
                file_path,
                dtype=str,
                keep_default_na=False,
                engine="openpyxl",
            )
        except Exception as exc:
            self.qa_log.log(
                "FILE_LOAD_ERROR",
                detail=f"Could not load registration extract: {exc}",
                source_file=file_path.name,
            )
            raise RuntimeError(
                f"Cannot open registration extract '{file_path.name}': {exc}"
            ) from exc

        df_raw.columns = [str(c).strip() for c in df_raw.columns]

        validation = validate_required_columns(
            df_raw,
            REGISTRATION_REPORT_REQUIRED_COLUMNS,
            f"Registration Report ({file_path.name})",
        )
        if not validation.is_valid:
            raise ValueError("\n".join(validation.errors))

        col = REGISTRATION_REPORT_COLUMN_MAP
        df = df_raw.copy()

        df["Student ID"] = normalize_student_id_series(df[col["student_id"]])

        credit_col = col["credit_hr"]
        if credit_col in df.columns:
            credit_hrs = pd.to_numeric(df[credit_col], errors="coerce").fillna(0)
        else:
            credit_hrs = pd.Series(0, index=df.index, dtype=float)
            logger.warning(
                "RegistrationProcessor: Column '%s' not found — Registered Credits will be 0.",
                credit_col,
            )

        status_col = col["registration_status"]
        if status_col in df.columns:
            is_active = normalize_string_series(df[status_col]).isin(
                REGISTRATION_STATUS_ACTIVE_VALUES
            )
        else:
            is_active = pd.Series(False, index=df.index)
            logger.warning(
                "RegistrationProcessor: Column '%s' not found — no rows will count toward Registered Credits.",
                status_col,
            )

        df["_active_credits"] = credit_hrs.where(is_active, 0)

        self._load_optional_string(df, col["college"], "College")
        self._load_optional_string(df, col["major"], "Major")
        self._load_optional_string(df, col["classification"], "Classification")
        self._load_optional_bool(df, col["dual_enrollment"], "Dual Enrollment")
        self._load_optional_bool(df, col["fau_high"], "FAU High")

        grouped = df.groupby("Student ID", sort=False)
        summary = grouped.agg(
            **{
                "Registered Credits": ("_active_credits", "sum"),
                "College": ("College", "first"),
                "Major": ("Major", "first"),
                "Classification": ("Classification", "first"),
                "Dual Enrollment": ("Dual Enrollment", "first"),
                "FAU High": ("FAU High", "first"),
            }
        ).reset_index()

        self._registration_df = summary
        logger.info(
            "RegistrationProcessor: %d unique students loaded.",
            len(self._registration_df),
        )

    def _load_optional_string(self, df: pd.DataFrame, source_col: str, dest_col: str) -> None:
        if source_col in df.columns:
            df[dest_col] = normalize_string_series(df[source_col])
        else:
            df[dest_col] = ""
            logger.warning(
                "RegistrationProcessor: Column '%s' not found — %s will be blank.",
                source_col,
                dest_col,
            )

    def _load_optional_bool(self, df: pd.DataFrame, source_col: str, dest_col: str) -> None:
        if source_col in df.columns:
            df[dest_col] = (
                normalize_string_series(df[source_col]).str.lower().isin(AT_RISK_TRUE_VALUES)
            )
        else:
            df[dest_col] = False
            logger.warning(
                "RegistrationProcessor: Column '%s' not found — %s will be False.",
                source_col,
                dest_col,
            )

    def merge(self, students_df: pd.DataFrame) -> pd.DataFrame:
        if self._registration_df is None:
            logger.warning(
                "RegistrationProcessor: No registration data loaded. Skipping merge."
            )
            for col_name in REGISTRATION_COLUMNS:
                students_df[col_name] = ""
            return students_df

        result = students_df.merge(
            self._registration_df,
            on="Student ID",
            how="left",
            suffixes=("", "_registration"),
        )

        for col_name in REGISTRATION_COLUMNS:
            result[col_name] = result[col_name].fillna("")

        logger.info(
            "RegistrationProcessor: Merge complete. %d students, %d with registration rows.",
            len(result),
            int((result["Registered Credits"] != "").sum()),
        )

        return result
