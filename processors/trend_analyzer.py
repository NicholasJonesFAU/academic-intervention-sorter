"""
trend_analyzer.py — Analyzes student at-risk trajectories across a full semester cycle.

Reads three output workbooks (PR1 → Midterm → PR2) and produces aggregate
trend statistics showing how the at-risk population moved through checkpoints.

Workbook format assumption: each group tab and unmatched bucket tab contains
a 'Student ID' column. The analyzer reads all non-meta tabs to build the
at-risk population at each checkpoint.
"""

import logging
from pathlib import Path
from typing import Dict, Optional, Set, Tuple
import pandas as pd

from utils.config import TRAJECTORY_LABELS, SUMMARY_TAB, QA_LOG_TAB, MANIFEST_TAB

logger = logging.getLogger("intervention_sorter")

# Tabs to skip when reading student IDs from output workbooks
SKIP_TABS = {SUMMARY_TAB, QA_LOG_TAB, MANIFEST_TAB, "Processing_Manifest", "QA_Log"}


class TrendAnalyzer:
    """
    Loads three output workbooks and computes student trajectory statistics.
    """

    def __init__(self) -> None:
        self._pr1_ids:  Set[str] = set()
        self._mid_ids:  Set[str] = set()
        self._pr2_ids:  Set[str] = set()
        self._pr1_groups:  Dict[str, Set[str]] = {}
        self._mid_groups:  Dict[str, Set[str]] = {}
        self._pr2_groups:  Dict[str, Set[str]] = {}

    def load(
        self,
        pr1_path:  Optional[Path],
        mid_path:  Optional[Path],
        pr2_path:  Optional[Path],
    ) -> None:
        """Load student IDs from each workbook. Any path can be None to skip."""
        if pr1_path:
            self._pr1_ids, self._pr1_groups = self._read_workbook(pr1_path, "PR1")
            logger.info("TrendAnalyzer: PR1 — %d students", len(self._pr1_ids))
        if mid_path:
            self._mid_ids, self._mid_groups = self._read_workbook(mid_path, "Midterm")
            logger.info("TrendAnalyzer: Midterm — %d students", len(self._mid_ids))
        if pr2_path:
            self._pr2_ids, self._pr2_groups = self._read_workbook(pr2_path, "PR2")
            logger.info("TrendAnalyzer: PR2 — %d students", len(self._pr2_ids))

    def overall_stats(self) -> Dict:
        """High-level counts for the three checkpoints."""
        all_ids = self._pr1_ids | self._mid_ids | self._pr2_ids
        return {
            "total_unique_students": len(all_ids),
            "pr1_count":  len(self._pr1_ids),
            "mid_count":  len(self._mid_ids),
            "pr2_count":  len(self._pr2_ids),
            "pr1_to_mid_recovered":  len(self._pr1_ids - self._mid_ids - self._pr2_ids),
            "pr1_to_mid_persistent": len(self._pr1_ids & self._mid_ids),
            "mid_to_pr2_recovered":  len(self._mid_ids - self._pr2_ids),
            "new_at_midterm":        len(self._mid_ids - self._pr1_ids),
            "new_at_pr2":            len(self._pr2_ids - self._pr1_ids - self._mid_ids),
        }

    def trajectory_breakdown(self) -> pd.DataFrame:
        """
        Classify every unique student into a trajectory across all 3 checkpoints.
        Returns a DataFrame with columns: Trajectory, Count, Pct
        """
        all_ids = self._pr1_ids | self._mid_ids | self._pr2_ids
        trajectories: Dict[str, int] = {k: 0 for k in TRAJECTORY_LABELS}

        for sid in all_ids:
            in_pr1 = sid in self._pr1_ids
            in_mid = sid in self._mid_ids
            in_pr2 = sid in self._pr2_ids

            if   in_pr1 and in_mid and in_pr2:         trajectories["persistent"]      += 1
            elif in_pr1 and not in_mid and not in_pr2: trajectories["recovered_early"] += 1
            elif in_pr1 and in_mid and not in_pr2:     trajectories["recovered_late"]  += 1
            elif in_pr1 and not in_mid and in_pr2:     trajectories["relapsed"]        += 1
            elif not in_pr1 and in_mid and in_pr2:     trajectories["new_midterm"]     += 1
            elif not in_pr1 and not in_mid and in_pr2: trajectories["new_pr2"]         += 1
            elif not in_pr1 and in_mid and not in_pr2: trajectories["midterm_only"]    += 1

        total = len(all_ids) or 1
        rows = []
        for key, label in TRAJECTORY_LABELS.items():
            count = trajectories.get(key, 0)
            rows.append({
                "Trajectory": label,
                "Count": count,
                "Pct": f"{count / total * 100:.1f}%",
            })

        return pd.DataFrame(rows)

    def group_breakdown(self) -> pd.DataFrame:
        """
        For each group that appears across checkpoints, show how many
        students were at-risk at each checkpoint.
        """
        all_groups = (
            set(self._pr1_groups) |
            set(self._mid_groups) |
            set(self._pr2_groups)
        ) - SKIP_TABS

        rows = []
        for group in sorted(all_groups):
            pr1_n  = len(self._pr1_groups.get(group, set()))
            mid_n  = len(self._mid_groups.get(group, set()))
            pr2_n  = len(self._pr2_groups.get(group, set()))
            pr1_s  = self._pr1_groups.get(group, set())
            mid_s  = self._mid_groups.get(group, set())
            pr2_s  = self._pr2_groups.get(group, set())
            recovered = len(pr1_s - mid_s - pr2_s)
            persistent = len(pr1_s & mid_s & pr2_s)
            rows.append({
                "Group":         group,
                "PR1 Count":     pr1_n,
                "Midterm Count": mid_n,
                "PR2 Count":     pr2_n,
                "Recovered by Mid": recovered,
                "Persistent (All 3)": persistent,
            })

        return pd.DataFrame(rows) if rows else pd.DataFrame(
            columns=["Group", "PR1 Count", "Midterm Count", "PR2 Count",
                     "Recovered by Mid", "Persistent (All 3)"]
        )

    def checkpoint_flow(self) -> pd.DataFrame:
        """
        Show student movement between consecutive checkpoints.
        """
        rows = [
            {
                "Transition": "PR1 → Midterm",
                "Carried Forward": len(self._pr1_ids & self._mid_ids),
                "Recovered":       len(self._pr1_ids - self._mid_ids),
                "New":             len(self._mid_ids - self._pr1_ids),
                "End Count":       len(self._mid_ids),
            },
            {
                "Transition": "Midterm → PR2",
                "Carried Forward": len(self._mid_ids & self._pr2_ids),
                "Recovered":       len(self._mid_ids - self._pr2_ids),
                "New":             len(self._pr2_ids - self._mid_ids),
                "End Count":       len(self._pr2_ids),
            },
        ]
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _read_workbook(
        self, path: Path, label: str
    ) -> Tuple[Set[str], Dict[str, Set[str]]]:
        """
        Read all student IDs from a generated output workbook.
        Returns (all_ids_set, {tab_name: ids_set}).
        """
        try:
            xl = pd.ExcelFile(path, engine="openpyxl")
        except Exception as exc:
            raise RuntimeError(f"Cannot open {label} workbook '{path.name}': {exc}") from exc

        all_ids: Set[str] = set()
        group_ids: Dict[str, Set[str]] = {}

        for sheet_name in xl.sheet_names:
            if sheet_name in SKIP_TABS:
                continue
            try:
                df = xl.parse(sheet_name, dtype=str)
                df.columns = [str(c).strip() for c in df.columns]
                if "Student ID" not in df.columns:
                    continue
                ids = set(
                    df["Student ID"].dropna()
                    .astype(str).str.strip().str.upper()
                    .replace("", pd.NA).dropna()
                )
                all_ids |= ids
                group_ids[sheet_name] = ids
            except Exception as exc:
                logger.warning("TrendAnalyzer: Could not read tab '%s': %s", sheet_name, exc)

        logger.info("TrendAnalyzer: %s workbook — %d IDs across %d tabs",
                    label, len(all_ids), len(group_ids))
        return all_ids, group_ids
