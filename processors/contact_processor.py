"""
contact_processor.py — Loads the contact report and merges contact info onto student records.

Phone number uses a waterfall fallback:
    cellular_phone → local_phone → permanent_phone → blank

Contact coverage counts a student as covered when EITHER phone or email is present.
"""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from utils.settings_manager import get_settings
from utils.normalization import normalize_student_id_series, normalize_string_series
from utils.validation import validate_required_columns
from utils.logging_utils import QALog

logger = logging.getLogger("intervention_sorter")


class ContactProcessor:
    def __init__(self, qa_log: QALog) -> None:
        self.qa_log = qa_log
        self._contact_df: Optional[pd.DataFrame] = None
        self._contact_matches: int = 0
        self._contact_misses: int = 0

    def load(self, file_path: Path) -> None:
        logger.info("ContactProcessor: Loading contact report from '%s'", file_path.name)

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
                detail=f"Could not load contact report: {exc}",
                source_file=file_path.name,
            )
            raise RuntimeError(
                f"Cannot open contact report '{file_path.name}': {exc}"
            ) from exc

        # Strip headers early so settings match even if the file has accidental spaces.
        df_raw.columns = [str(c).strip() for c in df_raw.columns]

        validation = validate_required_columns(
            df_raw,
            get_settings().contact_required_columns,
            f"Contact Report ({file_path.name})",
        )
        if not validation.is_valid:
            raise ValueError("\n".join(validation.errors))

        col = get_settings().contact_report_map
        df = df_raw.copy()

        # Normalize Student ID.
        df["Student ID"] = normalize_student_id_series(df[col["student_id"]])

        # Phone waterfall — cellular → local → permanent → blank.
        df["Phone Number"] = self._resolve_phone(df)

        found = [
            c for c in get_settings().phone_fallback_columns
            if c in df_raw.columns
        ]
        missing = [
            c for c in get_settings().phone_fallback_columns
            if c not in df_raw.columns
        ]

        if found:
            logger.info("ContactProcessor: Phone columns found: %s", found)
        if missing:
            logger.warning(
                "ContactProcessor: Phone columns not found and will be skipped: %s",
                missing,
            )

        # Email and optional student attributes — blank if the source column is missing.
        self._load_optional_string(df, col.get("email", ""), "Email")
        self._load_optional_string(df, col.get("campus", ""), "Campus")
        self._load_optional_string(df, col.get("earned_credits", ""), "Total Earned Credits")
        self._load_optional_string(df, col.get("ftic", ""), "FTIC Cohort")
        self._load_optional_string(df, col.get("major", ""), "Major")

        df = df[[
            "Student ID",
            "Phone Number",
            "Email",
            "Campus",
            "Total Earned Credits",
            "FTIC Cohort",
            "Major",
        ]].drop_duplicates(
            subset=["Student ID"],
            keep="first",
        )

        self._contact_df = df
        logger.info(
            "ContactProcessor: %d unique contacts loaded.",
            len(self._contact_df),
        )

    def _resolve_phone(self, df: pd.DataFrame) -> pd.Series:
        """
        Return a Series with the best available phone number per row.
        Waterfall: cellular_phone → local_phone → permanent_phone → blank.
        """
        result = pd.Series("", index=df.index)

        for col_name in get_settings().phone_fallback_columns:
            if col_name not in df.columns:
                continue

            normalized = normalize_string_series(df[col_name])
            still_blank = result == ""
            result = result.where(~still_blank, normalized.where(still_blank, result))

        return result

    def _load_optional_string(self, df: pd.DataFrame, source_col: str, dest_col: str) -> None:
        """Normalize a source column as a string, or fill dest_col with blank if missing."""
        if source_col and source_col in df.columns:
            df[dest_col] = normalize_string_series(df[source_col])
        else:
            df[dest_col] = ""
            if source_col:
                logger.warning(
                    "ContactProcessor: Column '%s' not found — %s will be blank.",
                    source_col,
                    dest_col,
                )

    def merge(self, students_df: pd.DataFrame) -> pd.DataFrame:
        contact_columns = [
            "Phone Number",
            "Email",
            "Campus",
            "Total Earned Credits",
            "FTIC Cohort",
            "Major",
        ]
        if self._contact_df is None:
            logger.warning("ContactProcessor: No contact data loaded. Skipping merge.")
            for col_name in contact_columns:
                if col_name not in students_df.columns:
                    students_df[col_name] = ""
            self._contact_matches = 0
            self._contact_misses = len(students_df)
            return students_df

        result = students_df.merge(
            self._contact_df,
            on="Student ID",
            how="left",
            suffixes=("", "_contact"),
        )

        # Contact values win when present (Major comes from the Active Students
        # extract). A column the caller already filled is kept only if contact
        # left it blank.
        for col_name in contact_columns:
            incoming = f"{col_name}_contact"
            if incoming in result.columns:
                existing = result[col_name].fillna("").astype(str).str.strip()
                incoming_vals = result[incoming].fillna("").astype(str).str.strip()
                result[col_name] = incoming_vals.where(incoming_vals != "", existing)
                result = result.drop(columns=[incoming])
            elif col_name in result.columns:
                result[col_name] = result[col_name].fillna("")
            else:
                result[col_name] = ""

        # IMPORTANT:
        # A contact match means the student has either a usable phone number OR email.
        # The previous logic counted email only, which made phone-only sample data show 0%.
        has_contact_mask = (result["Phone Number"] != "") | (result["Email"] != "")

        self._contact_matches = int(has_contact_mask.sum())
        self._contact_misses = int((~has_contact_mask).sum())

        for _, row in result[~has_contact_mask].iterrows():
            self.qa_log.log(
                "MISSING_CONTACT",
                student_id=row.get("Student ID", ""),
                detail="No phone or email found across all contact columns",
                source_file="contact_report",
            )

        if self._contact_misses > 0:
            logger.warning(
                "ContactProcessor: %d students have no contact info.",
                self._contact_misses,
            )

        logger.info(
            "ContactProcessor: Merge complete. Contacts found: %d | Missing: %d",
            self._contact_matches,
            self._contact_misses,
        )

        return result

    @property
    def contact_match_count(self) -> int:
        return self._contact_matches

    @property
    def contact_miss_count(self) -> int:
        return self._contact_misses
