"""
report_status_processor.py — Analyzes faculty progress report submission status.
"""

import logging
from pathlib import Path
from typing import Dict
import pandas as pd

from processors.department_mapper import DepartmentMapper
from utils.settings_manager import get_settings

logger = logging.getLogger("intervention_sorter")

# Required columns now come from settings_manager

RESPONDED_TRUE = {"yes", "true", "1", "y"}


class ReportStatusProcessor:

    def __init__(self) -> None:
        self._sections: pd.DataFrame = pd.DataFrame()

    def load(self, file_path: Path, mapper: DepartmentMapper) -> None:
        logger.info("ReportStatusProcessor: Loading '%s'", file_path.name)

        try:
            suffix = file_path.suffix.lower()
            if suffix == ".csv":
                df = None
                for encoding in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
                    try:
                        df = pd.read_csv(file_path, dtype=str, keep_default_na=False, encoding=encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                if df is None:
                    raise RuntimeError(f"Could not decode CSV '{file_path.name}'")
            else:
                df = pd.read_excel(file_path, dtype=str, keep_default_na=False, engine="openpyxl")
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Cannot open status file '{file_path.name}': {exc}") from exc

        # Strip ALL column headers of extra whitespace immediately
        df.columns = [str(c).strip() for c in df.columns]

        # Validate required columns
        missing = [c for c in get_settings().faculty_required_columns if c not in df.columns]
        if missing:
            raise ValueError(
                f"Status file missing required columns: {missing}\n"
                f"Found: {list(df.columns)}"
            )

        df = df.copy()

        # Normalize core columns
        fac = get_settings().faculty_map
        df["Professor Requested First Name"] = df[fac["first_name"]].str.strip()
        df["Professor Requested Last Name"]  = df[fac["last_name"]].str.strip()
        df["Course Number"] = df[get_settings().faculty_map["course_number"]].str.strip().str.upper()
        df["Section Name"]  = df["Section Name"].str.strip() if "Section Name" in df.columns else ""

        # Email — find it by stripped name regardless of spacing in header
        email_col = next((c for c in df.columns if c.strip() == "Professor Requested Email"), None)
        if email_col:
            df["Professor Requested Email"] = df[email_col].str.strip().str.lower()
        else:
            df["Professor Requested Email"] = ""
            logger.warning("ReportStatusProcessor: No email column found — email will be blank.")

        # Responded flag
        df["Submitted"] = df[get_settings().faculty_map["responded"]].str.strip().str.lower().isin(RESPONDED_TRUE)

        # Full name
        df["Faculty Name"] = (
            df["Professor Requested First Name"] + " " +
            df["Professor Requested Last Name"]
        ).str.strip()

        # Deduplicate: one row per professor + course + section
        subset = ["Professor Requested Email", "Course Number"]
        if "Section Name" in df.columns:
            subset.append("Section Name")
        df = df.drop_duplicates(subset=subset, keep="first")

        # Enrich with dept/college
        df = mapper.enrich_dataframe(df, course_col="Course Number")

        self._sections = df
        logger.info("ReportStatusProcessor: %d section assignments loaded.", len(df))

    def overall_stats(self) -> Dict:
        total = len(self._sections)
        submitted = int(self._sections["Submitted"].sum())
        return {
            "total_sections": total,
            "submitted": submitted,
            "not_submitted": total - submitted,
            "completion_pct": round(submitted / total * 100, 1) if total else 0.0,
        }

    def by_college(self) -> pd.DataFrame:
        return self._completion_by(["College"])

    def by_department(self) -> pd.DataFrame:
        return self._completion_by(["College", "Department"])

    def by_professor(self) -> pd.DataFrame:
        grp = self._sections.groupby(
            ["Professor Requested Email", "Faculty Name",
             "Professor Requested First Name", "Professor Requested Last Name",
             "College", "Department"],
            as_index=False,
        ).agg(
            Total_Sections=("Submitted", "count"),
            Submitted=("Submitted", "sum"),
        )
        grp["Not Submitted"] = grp["Total_Sections"] - grp["Submitted"]
        grp["Completion %"]  = (grp["Submitted"] / grp["Total_Sections"] * 100).round(1)
        grp = grp.rename(columns={
            "Professor Requested Email":      "Email",
            "Professor Requested First Name": "First Name",
            "Professor Requested Last Name":  "Last Name",
            "Total_Sections":                 "Total Sections",
        })
        return grp.sort_values(["College", "Department", "Last Name", "First Name"]).reset_index(drop=True)

    def faculty_download(self) -> pd.DataFrame:
        df = self._sections[[
            "Professor Requested First Name",
            "Professor Requested Last Name",
            "Professor Requested Email",
            "College",
            "Department",
        ]].drop_duplicates(subset=["Professor Requested Email"]).copy()
        df = df.rename(columns={
            "Professor Requested First Name": "First Name",
            "Professor Requested Last Name":  "Last Name",
            "Professor Requested Email":      "Email",
        })
        return df.sort_values(["College", "Department", "Last Name", "First Name"]).reset_index(drop=True)

    def _completion_by(self, group_cols: list) -> pd.DataFrame:
        grp = self._sections.groupby(group_cols, as_index=False).agg(
            Total_Sections=("Submitted", "count"),
            Submitted=("Submitted", "sum"),
        )
        grp["Not Submitted"] = grp["Total_Sections"] - grp["Submitted"]
        grp["Completion %"]  = (grp["Submitted"] / grp["Total_Sections"] * 100).round(1)
        grp = grp.rename(columns={"Total_Sections": "Total Sections"})
        return grp.sort_values(group_cols).reset_index(drop=True)

    @property
    def sections(self) -> pd.DataFrame:
        return self._sections.copy()
