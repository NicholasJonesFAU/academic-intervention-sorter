"""
prerun_checker.py — Pre-run data quality validation.

Runs in ~5 seconds before a full pipeline run and surfaces issues like:
  - Column name mismatches
  - Missing contact matches
  - Group file IDs not in progress report
  - Encoding issues
  - Empty group files
  - At-risk count anomalies

Returns a list of CheckResult objects — warnings don't block the run,
errors do.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
import pandas as pd

from utils.config import MIDTERM_AT_RISK_GRADES
from utils.settings_manager import get_settings
from utils.normalization import normalize_student_id_series

logger = logging.getLogger("intervention_sorter")


@dataclass
class CheckResult:
    level:   str    # "error" | "warning" | "info"
    message: str


class PreRunChecker:
    """
    Runs lightweight validation checks before a full pipeline run.
    Fast — no aggregation, no matching, no output writing.
    """

    def check_progress_report(self, file_path: Path) -> List[CheckResult]:
        results = []
        col = get_settings().progress_report_map

        try:
            df = self._load_file(file_path)
        except Exception as exc:
            return [CheckResult("error", f"Cannot open progress report: {exc}")]

        df.columns = [str(c).strip() for c in df.columns]

        # Required columns
        required = [col["student_name"], col["student_id"], col["course"], col["at_risk"]]
        missing = [c for c in required if c not in df.columns]
        if missing:
            results.append(CheckResult("error",
                f"Missing required columns: {missing}\nFound: {list(df.columns[:8])}..."))
            return results

        results.append(CheckResult("info",
            f"Progress report loaded: {len(df):,} rows"))

        # At-risk count
        at_risk_col = col["at_risk"]
        at_risk_vals = {"true","yes","y","1"}
        at_risk_count = df[at_risk_col].astype(str).str.strip().str.lower().isin(at_risk_vals).sum()
        pct = at_risk_count / len(df) * 100 if len(df) else 0
        results.append(CheckResult("info",
            f"At-risk rows: {at_risk_count:,} ({pct:.1f}% of total)"))

        if at_risk_count == 0:
            results.append(CheckResult("error",
                f"No at-risk rows found. Check that '{at_risk_col}' contains TRUE/YES/Y/1 values."))
        elif pct > 80:
            results.append(CheckResult("warning",
                f"{pct:.0f}% of rows are marked at-risk — unusually high. "
                f"Verify the '{at_risk_col}' column is correct."))

        # Blank Student IDs
        ids = normalize_student_id_series(df[col["student_id"]])
        blank_ids = (ids == "").sum()
        if blank_ids > 0:
            results.append(CheckResult("warning",
                f"{blank_ids:,} rows have blank Student IDs and will be skipped."))

        return results

    def check_midterm_file(self, file_path: Path) -> List[CheckResult]:
        results = []
        from utils.config import MIDTERM_COLUMN_MAP, MIDTERM_REQUIRED_COLUMNS

        try:
            df = self._load_file(file_path)
        except Exception as exc:
            return [CheckResult("error", f"Cannot open midterm file: {exc}")]

        df.columns = [str(c).strip() for c in df.columns]

        missing = [c for c in MIDTERM_REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            results.append(CheckResult("error",
                f"Missing required columns: {missing}"))
            return results

        results.append(CheckResult("info", f"Midterm file loaded: {len(df):,} rows"))

        grade_col = MIDTERM_COLUMN_MAP["midterm_grade"]
        at_risk_count = df[grade_col].astype(str).str.strip().str.lower().isin(
            MIDTERM_AT_RISK_GRADES).sum()
        pct = at_risk_count / len(df) * 100 if len(df) else 0
        results.append(CheckResult("info",
            f"At-risk grades (C- or below): {at_risk_count:,} ({pct:.1f}%)"))

        if at_risk_count == 0:
            results.append(CheckResult("error",
                f"No at-risk grades found. Check '{grade_col}' contains C-, D+, D, D-, F values."))

        return results

    def check_contact_report(self, file_path: Path,
                              progress_ids: Optional[set] = None) -> List[CheckResult]:
        results = []
        col = get_settings().contact_report_map

        try:
            df = pd.read_excel(file_path, dtype=str, keep_default_na=False,
                               engine="openpyxl")
        except Exception as exc:
            return [CheckResult("error", f"Cannot open contact report: {exc}")]

        df.columns = [str(c).strip() for c in df.columns]
        id_col = col["student_id"]
        if id_col not in df.columns:
            results.append(CheckResult("error",
                f"Student ID column '{id_col}' not found in contact report. "
                f"Found: {list(df.columns[:6])}..."))
            return results

        contact_ids = set(normalize_student_id_series(df[id_col]).replace("", pd.NA).dropna())
        results.append(CheckResult("info",
            f"Contact report loaded: {len(contact_ids):,} unique student IDs"))

        if progress_ids:
            missing = progress_ids - contact_ids
            pct_missing = len(missing) / len(progress_ids) * 100 if progress_ids else 0
            if missing:
                results.append(CheckResult(
                    "warning" if pct_missing < 20 else "error",
                    f"{len(missing):,} at-risk students ({pct_missing:.1f}%) have no contact info."
                ))
            else:
                results.append(CheckResult("info",
                    "All at-risk students have a contact record. ✓"))

        # Check email and phone columns
        for label, key in [("Email", "email"), ("Cellular", "phone_cellular")]:
            c = col.get(key, "")
            if c and c not in df.columns:
                results.append(CheckResult("warning",
                    f"{label} column '{c}' not found — will be blank in output."))

        return results

    def check_group_files(self, control_path: Path,
                          group_dir: Path,
                          progress_ids: Optional[set] = None) -> List[CheckResult]:
        results = []
        from utils.config import CONTROL_FILE_DELIMITER, CONTROL_FILE_ENCODINGS

        # Read control file
        content = None
        for enc in CONTROL_FILE_ENCODINGS:
            try:
                content = control_path.read_text(encoding=enc)
                break
            except Exception:
                continue
        if content is None:
            return [CheckResult("error", "Cannot read control file.")]

        lines = [l.strip() for l in content.splitlines()
                 if l.strip() and not l.strip().startswith("#")]

        if not lines:
            return [CheckResult("error", "Control file is empty.")]

        results.append(CheckResult("info", f"Control file: {len(lines)} groups defined"))

        total_group_ids = set()
        for line in lines:
            parts = line.split(CONTROL_FILE_DELIMITER)
            if len(parts) != 2:
                results.append(CheckResult("warning", f"Malformed control file line: '{line}'"))
                continue
            tab_name, filename = parts[0].strip(), parts[1].strip()
            file_path = group_dir / filename

            if not file_path.exists():
                results.append(CheckResult("warning",
                    f"Group file not found: '{filename}' (group '{tab_name}' will be empty)"))
                continue

            try:
                df = pd.read_excel(file_path, dtype=str, keep_default_na=False,
                                   engine="openpyxl", header=None)
                ids = set(normalize_student_id_series(df.iloc[:, 0])
                          .replace("", pd.NA).dropna())
                # Remove header-like values
                ids = {i for i in ids if i.lower() not in
                       {"student id","studentid","id","z number","znumber","nan"}}
                total_group_ids |= ids

                if not ids:
                    results.append(CheckResult("warning",
                        f"Group '{tab_name}': file loaded but no valid IDs found."))
                else:
                    if progress_ids:
                        overlap = ids & progress_ids
                        results.append(CheckResult("info",
                            f"Group '{tab_name}': {len(ids):,} IDs loaded, "
                            f"{len(overlap):,} match at-risk students"))
                    else:
                        results.append(CheckResult("info",
                            f"Group '{tab_name}': {len(ids):,} IDs loaded"))
            except Exception as exc:
                results.append(CheckResult("warning",
                    f"Group '{tab_name}': could not read '{filename}': {exc}"))

        return results

    def _load_file(self, path: Path) -> pd.DataFrame:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            for enc in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
                try:
                    return pd.read_csv(path, dtype=str, keep_default_na=False,
                                       encoding=enc)
                except UnicodeDecodeError:
                    continue
            raise RuntimeError(f"Could not decode CSV: {path.name}")
        return pd.read_excel(path, dtype=str, keep_default_na=False,
                             engine="openpyxl")
