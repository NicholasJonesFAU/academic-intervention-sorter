"""
group_matcher.py — Group matching with strict FIRST MATCH WINS logic.

Responsibilities:
  1. Load and parse the control TXT file (group processing order)
  2. Load each group ID file
  3. Assign students to groups in order — first match wins
  4. Split unmatched students into Risk_1_2 and Risk_3_Plus buckets
  5. Produce a complete set of per-group DataFrames with audit columns
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from utils.config import (
    CONTROL_FILE_DELIMITER,
    CONTROL_FILE_ENCODINGS,
    UNMATCHED_LOW_TAB,
    UNMATCHED_HIGH_TAB,
    UNMATCHED_HIGH_THRESHOLD,
    SORT_COLUMNS,
    SORT_ASCENDING,
)
from utils.normalization import normalize_student_id_series, safe_excel_tab_name
from utils.validation import validate_control_file_line, validate_student_id
from utils.logging_utils import QALog

logger = logging.getLogger("intervention_sorter")


@dataclass
class GroupDefinition:
    """Represents one entry from the control TXT file."""
    tab_name: str
    filename: str
    student_ids: set = field(default_factory=set)
    safe_tab_name: str = ""


class GroupMatcher:
    """
    Orchestrates group-matching using strict first-match-wins logic.
    """

    def __init__(self, qa_log: QALog) -> None:
        self.qa_log = qa_log
        self._groups: List[GroupDefinition] = []
        self._group_dir: Optional[Path] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_control_file(
        self,
        control_path: Path,
        group_dir: Path,
        skip_groups: set = None,
    ) -> None:
        """
        Parse the control TXT file and load all group ID files.

        Args:
            control_path: Path to the TXT file (TabName|filename.xlsx per line)
            group_dir:    Directory where group Excel files are located
            skip_groups:  Set of tab names to skip entirely (students fall to buckets)
        """
        self._group_dir = group_dir
        self._skip_groups = set(skip_groups) if skip_groups else set()
        logger.info("GroupMatcher: Loading control file '%s'", control_path.name)
        if self._skip_groups:
            logger.info("GroupMatcher: Skipping groups: %s", self._skip_groups)

        lines = self._read_control_file(control_path)
        raw_groups = self._parse_control_lines(lines, control_path.name)

        # Filter out skipped groups before loading files
        if self._skip_groups:
            raw_groups = [
                (tab, fname) for tab, fname in raw_groups
                if tab not in self._skip_groups
            ]

        self._groups = self._load_group_files(raw_groups, group_dir)

        logger.info(
            "GroupMatcher: %d groups loaded from control file.", len(self._groups)
        )

        # Detect cross-group duplicates
        self._audit_cross_group_duplicates()

    def match(self, students_df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """
        Assign each student to exactly one group or unmatched bucket.

        Returns:
            dict mapping safe_tab_name → DataFrame of students
        """
        logger.info(
            "GroupMatcher: Matching %d students across %d groups.",
            len(students_df),
            len(self._groups),
        )

        remaining = students_df.copy()
        result: Dict[str, pd.DataFrame] = {}
        used_tab_names: List[str] = []

        for group in self._groups:
            if remaining.empty:
                logger.info(
                    "GroupMatcher: All students assigned. Skipping remaining groups."
                )
                result[group.safe_tab_name] = pd.DataFrame(
                    columns=students_df.columns.tolist()
                    + ["Matched Group", "Match Source", "Processing Notes"]
                )
                used_tab_names.append(group.safe_tab_name)
                continue

            match_mask = remaining["Student ID"].isin(group.student_ids)
            matched = remaining[match_mask].copy()
            remaining = remaining[~match_mask].copy()

            matched["Matched Group"] = group.tab_name
            matched["Match Source"] = group.filename
            matched["Processing Notes"] = ""

            matched = self._sort_students(matched)

            result[group.safe_tab_name] = matched
            used_tab_names.append(group.safe_tab_name)

            logger.info(
                "GroupMatcher: Group '%s' — %d matched, %d remaining.",
                group.tab_name,
                len(matched),
                len(remaining),
            )

        # Split unmatched into buckets
        low_df, high_df = self._split_unmatched(remaining)
        result[UNMATCHED_LOW_TAB] = low_df
        result[UNMATCHED_HIGH_TAB] = high_df

        logger.info(
            "GroupMatcher: Unmatched — Risk_1_2: %d | Risk_3_Plus: %d",
            len(low_df),
            len(high_df),
        )

        return result

    def read_group_names(self, control_path: Path) -> List[tuple]:
        """
        Read group names from control file without loading xlsx files.
        Returns list of (tab_name, filename) tuples.
        Used to populate the group selection dialog.
        """
        try:
            lines = self._read_control_file(control_path)
            return self._parse_control_lines(lines, control_path.name)
        except Exception as exc:
            logger.warning("GroupMatcher: Could not read group names: %s", exc)
            return []


    def load_from_semester_groups(
        self,
        groups: list,
        skip_groups: set = None,
    ) -> None:
        """
        Load groups from semester-configured definitions (full file paths).

        This is the alternative to load_control_file() — used when the
        active semester has groups configured rather than a control TXT file.

        Args:
            groups:      List of {'name': str, 'file_path': str} dicts in
                         priority order.
            skip_groups: Set of group names to skip (students fall to buckets).
        """
        self._skip_groups = set(skip_groups) if skip_groups else set()
        logger.info(
            "GroupMatcher: Loading %d groups from semester configuration.", len(groups)
        )
        if self._skip_groups:
            logger.info("GroupMatcher: Skipping groups: %s", self._skip_groups)

        # Build (tab_name, full_path) pairs, honouring skip list
        raw = [
            (g["name"], g["file_path"])
            for g in groups
            if g["name"] not in self._skip_groups
        ]

        self._groups = self._load_group_files_by_path(raw)
        self._audit_cross_group_duplicates()

        logger.info(
            "GroupMatcher: %d groups loaded from semester configuration.",
            len(self._groups),
        )

    def _load_group_files_by_path(
        self,
        raw_groups: list,  # [(tab_name, full_file_path), ...]
    ) -> "List[GroupDefinition]":
        """
        Load group files given full paths (not filename + directory).
        Mirrors _load_group_files but accepts absolute/relative Path strings.
        """
        groups = []
        used_tab_names: List[str] = []

        for tab_name, file_path_str in raw_groups:
            file_path = Path(file_path_str) if file_path_str else None
            safe_name = safe_excel_tab_name(tab_name, used_tab_names)
            used_tab_names.append(safe_name)

            group_def = GroupDefinition(
                tab_name=tab_name,
                filename=file_path.name if file_path else "",
                safe_tab_name=safe_name,
            )

            if not file_path or not file_path.exists():
                logger.warning(
                    "GroupMatcher: Group file not found: '%s'. Group will be empty.",
                    file_path,
                )
                self.qa_log.log(
                    "FILE_LOAD_ERROR",
                    detail=f"Group file not found: {file_path}",
                    source_file=str(file_path) if file_path else tab_name,
                )
                groups.append(group_def)
                continue

            ids = self._load_id_file(file_path)
            group_def.student_ids = ids

            if not ids:
                logger.warning(
                    "GroupMatcher: Group file '%s' yielded no valid IDs.",
                    file_path.name,
                )
                self.qa_log.log(
                    "EMPTY_GROUP_FILE",
                    detail=f"No valid Student IDs in group file: {file_path.name}",
                    source_file=file_path.name,
                )

            groups.append(group_def)
            logger.info(
                "GroupMatcher: Loaded group '%s' — %d IDs from '%s'",
                tab_name, len(ids), file_path.name,
            )

        return groups

    @property
    def group_definitions(self) -> List[GroupDefinition]:
        return list(self._groups)

    # ------------------------------------------------------------------
    # Control file loading
    # ------------------------------------------------------------------

    def _read_control_file(self, path: Path) -> List[str]:
        """Read control file content, trying multiple encodings."""
        for encoding in CONTROL_FILE_ENCODINGS:
            try:
                with open(path, "r", encoding=encoding) as f:
                    content = f.read()
                # Normalize line endings
                return content.splitlines()
            except (UnicodeDecodeError, UnicodeError):
                continue
            except Exception as exc:
                raise RuntimeError(
                    f"Cannot read control file '{path.name}': {exc}"
                ) from exc
        raise RuntimeError(
            f"Cannot decode control file '{path.name}'. Tried encodings: {CONTROL_FILE_ENCODINGS}"
        )

    def _parse_control_lines(
        self, lines: List[str], source: str
    ) -> List[Tuple[str, str]]:
        """Parse lines into (tab_name, filename) tuples."""
        results = []
        for i, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            is_valid, error = validate_control_file_line(
                stripped, i, CONTROL_FILE_DELIMITER
            )
            if not is_valid:
                logger.warning("GroupMatcher: Control file parse issue — %s", error)
                self.qa_log.log(
                    "MALFORMED_ROW",
                    detail=error,
                    source_file=source,
                )
                continue
            parts = stripped.split(CONTROL_FILE_DELIMITER)
            results.append((parts[0].strip(), parts[1].strip()))
        return results

    # ------------------------------------------------------------------
    # Group file loading
    # ------------------------------------------------------------------

    def _load_group_files(
        self,
        raw_groups: List[Tuple[str, str]],
        group_dir: Path,
    ) -> List[GroupDefinition]:
        """Load each group file and build GroupDefinition objects."""
        groups: List[GroupDefinition] = []
        used_tab_names: List[str] = []

        for tab_name, filename in raw_groups:
            file_path = group_dir / filename
            safe_name = safe_excel_tab_name(tab_name, used_tab_names)
            used_tab_names.append(safe_name)

            group_def = GroupDefinition(
                tab_name=tab_name,
                filename=filename,
                safe_tab_name=safe_name,
            )

            if not file_path.exists():
                logger.warning(
                    "GroupMatcher: Group file not found: '%s'. Group will be empty.",
                    file_path,
                )
                self.qa_log.log(
                    "FILE_LOAD_ERROR",
                    detail=f"Group file not found: {filename}",
                    source_file=filename,
                )
                groups.append(group_def)
                continue

            ids = self._load_id_file(file_path)
            group_def.student_ids = ids

            if not ids:
                logger.warning(
                    "GroupMatcher: Group file '%s' yielded no valid IDs.", filename
                )
                self.qa_log.log(
                    "EMPTY_GROUP_FILE",
                    detail=f"No valid Student IDs found in group file: {filename}",
                    source_file=filename,
                )

            groups.append(group_def)
            logger.info(
                "GroupMatcher: Loaded group '%s' — %d IDs from '%s'",
                tab_name,
                len(ids),
                filename,
            )

        return groups

    def _load_id_file(self, file_path: Path) -> set:
        """
        Load a group ID file robustly.

        Handles:
          - Files with or without headers
          - Files with multiple columns (uses first column only)
          - Blank rows
          - Duplicate IDs
          - Malformed rows
        """
        try:
            df = pd.read_excel(
                file_path,
                dtype=str,
                keep_default_na=False,
                engine="openpyxl",
                header=None,     # Always read without header assumption
            )
        except Exception as exc:
            logger.error(
                "GroupMatcher: Cannot read group file '%s': %s", file_path.name, exc
            )
            self.qa_log.log(
                "FILE_LOAD_ERROR",
                detail=f"Cannot read group file: {exc}",
                source_file=file_path.name,
            )
            return set()

        if df.empty:
            return set()

        # Use only the first column
        raw_ids = df.iloc[:, 0].astype(str).tolist()

        valid_ids: set = set()
        for raw in raw_ids:
            from utils.normalization import normalize_student_id
            normalized = normalize_student_id(raw)

            # Skip header-like values
            if normalized.lower() in {"student id", "studentid", "id", "z number",
                                       "znumber", "student_id", "nan", ""}:
                continue

            is_valid, reason = validate_student_id(normalized)
            if not is_valid:
                self.qa_log.log(
                    "INVALID_STUDENT_ID",
                    student_id=raw,
                    detail=f"Skipped invalid ID: {reason}",
                    source_file=file_path.name,
                )
                continue

            if normalized in valid_ids:
                self.qa_log.log(
                    "DUPLICATE_GROUP_ID",
                    student_id=normalized,
                    detail=f"Duplicate ID in group file (ignored)",
                    source_file=file_path.name,
                )
            valid_ids.add(normalized)

        return valid_ids

    # ------------------------------------------------------------------
    # Cross-group auditing
    # ------------------------------------------------------------------

    def _audit_cross_group_duplicates(self) -> None:
        """Identify Student IDs that appear in multiple group files."""
        id_to_groups: Dict[str, List[str]] = {}
        for group in self._groups:
            for sid in group.student_ids:
                id_to_groups.setdefault(sid, []).append(group.tab_name)

        for sid, group_names in id_to_groups.items():
            if len(group_names) > 1:
                self.qa_log.log(
                    "MULTI_GROUP_STUDENT",
                    student_id=sid,
                    detail=f"ID found in multiple group files: {', '.join(group_names)}. "
                           f"Will be assigned to first matching group only.",
                    source_file="multiple",
                )
                logger.warning(
                    "GroupMatcher: Student ID '%s' found in groups: %s. "
                    "First-match wins.",
                    sid,
                    group_names,
                )

    # ------------------------------------------------------------------
    # Unmatched splitting
    # ------------------------------------------------------------------

    def _split_unmatched(
        self, remaining: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Split unmatched students into Risk_1_2 and Risk_3_Plus."""
        if remaining.empty:
            empty = pd.DataFrame(
                columns=list(remaining.columns) + ["Matched Group", "Match Source", "Processing Notes"]
            )
            return empty.copy(), empty.copy()

        remaining = remaining.copy()
        remaining["Matched Group"] = "Unmatched"
        remaining["Match Source"] = ""
        remaining["Processing Notes"] = "No group file match"

        low_mask = remaining["Risk Course Count"] < UNMATCHED_HIGH_THRESHOLD
        low_df = self._sort_students(remaining[low_mask].copy())
        high_df = self._sort_students(remaining[~low_mask].copy())

        low_df["Matched Group"] = UNMATCHED_LOW_TAB
        high_df["Matched Group"] = UNMATCHED_HIGH_TAB

        return low_df, high_df

    # ------------------------------------------------------------------
    # Sorting
    # ------------------------------------------------------------------

    @staticmethod
    def _sort_students(df: pd.DataFrame) -> pd.DataFrame:
        """Sort students per spec: Risk Course Count desc, Absences desc, Name asc."""
        sort_cols = [c for c in SORT_COLUMNS if c in df.columns]
        ascending = [
            SORT_ASCENDING[SORT_COLUMNS.index(c)]
            for c in sort_cols
        ]
        if not sort_cols:
            return df
        return df.sort_values(sort_cols, ascending=ascending).reset_index(drop=True)
