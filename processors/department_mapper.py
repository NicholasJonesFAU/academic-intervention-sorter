"""
department_mapper.py — Loads the course prefix → department/college mapping.

Mapping file columns:
    COURSE  — course prefix (e.g. MAC, ENC, CHM)
    DEPT    — department code
    CO      — college code
"""

import logging
from pathlib import Path
from typing import Optional
import pandas as pd

logger = logging.getLogger("intervention_sorter")

# Expand college codes to readable names
COLLEGE_NAMES = {
    "BA": "Business",
    "ED": "Education",
    "AL": "Arts & Letters",
    "SC": "Science",
    "EN": "Engineering",
    "MS": "Medicine",
    "NR": "Nursing",
    "AR": "Architecture",
    "SO": "Social Work",
    "HO": "Honors",
    "GR": "Graduate",
    "OT": "Other",
}


class DepartmentMapper:
    """Maps course prefixes to department and college."""

    def __init__(self) -> None:
        self._map: pd.DataFrame = pd.DataFrame()

    def load(self, file_path: Path) -> None:
        try:
            df = pd.read_excel(file_path, dtype=str, keep_default_na=False)
        except Exception as exc:
            raise RuntimeError(f"Cannot open mapping file '{file_path.name}': {exc}") from exc

        required = ["DEPT", "CO", "COURSE"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Mapping file missing columns: {missing}")

        df = df[required].copy()
        df["COURSE"] = df["COURSE"].str.strip().str.upper()
        df["DEPT"]   = df["DEPT"].str.strip().str.upper()
        df["CO"]     = df["CO"].str.strip().str.upper()
        df["COLLEGE_NAME"] = df["CO"].map(COLLEGE_NAMES).fillna(df["CO"])

        df_clean = df.drop_duplicates(subset=["COURSE"])
        self._dept_dict    = dict(zip(df_clean["COURSE"], df_clean["DEPT"]))
        self._college_dict = dict(zip(df_clean["COURSE"], df_clean["COLLEGE_NAME"]))
        self._code_dict    = dict(zip(df_clean["COURSE"], df_clean["CO"]))
        self._map = df_clean  # kept for compatibility
        logger.info("DepartmentMapper: %d course prefixes loaded.", len(self._dept_dict))

    def get_dept(self, course_number: str) -> str:
        prefix = self._extract_prefix(course_number)
        return self._dept_dict.get(prefix, "Unknown")

    def get_college(self, course_number: str) -> str:
        prefix = self._extract_prefix(course_number)
        return self._college_dict.get(prefix, "Unknown")

    def get_college_code(self, course_number: str) -> str:
        prefix = self._extract_prefix(course_number)
        return self._code_dict.get(prefix, "Unknown")

    def enrich_dataframe(self, df: pd.DataFrame, course_col: str = "Course Number") -> pd.DataFrame:
        """
        Add Department and College columns to a DataFrame based on course number.
        """
        df = df.copy()
        prefixes = df[course_col].astype(str).apply(self._extract_prefix)
        df["Department"]   = prefixes.map(lambda p: self._dept_dict.get(p, "Unknown"))
        df["College"]      = prefixes.map(lambda p: self._college_dict.get(p, "Unknown"))
        df["College Code"] = prefixes.map(lambda p: self._code_dict.get(p, "Unknown"))
        return df

    @staticmethod
    def _extract_prefix(course_number: str) -> str:
        """Extract alphabetic prefix from a course number like 'MAC1105' → 'MAC'."""
        import re
        match = re.match(r"([A-Za-z]+)", str(course_number).strip())
        return match.group(1).upper() if match else ""
