"""
campaign_manager.py — Manages campaign history for the Intervention Sorter.

Stores campaign metadata in campaigns.json:
  - Campaign name (user-defined, e.g. "Fall 2026")
  - Season (groups campaigns together, e.g. "Fall 2026")
  - Checkpoint type (Progress Report 1 / Midterm / Progress Report 2)
  - Run timestamp
  - Students processed / assigned / unmatched counts
  - Output file path
  - assigned_students.txt snapshot count at time of run

Provides:
  - Student repeat tracking (how many campaigns has a student appeared in)
  - Season-level rollup for the Trend tab
  - Reset functionality (clear assigned_students.txt for a new season)
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

from utils.config import CAMPAIGNS_PATH, ASSIGNED_STUDENTS_PATH, OUTPUT_DIR

logger = logging.getLogger("intervention_sorter")


@dataclass
class CampaignRun:
    """A single processing run within a campaign season."""
    run_id:          str
    season:          str
    checkpoint_type: str        # "Progress Report 1" / "Midterm" / "Progress Report 2"
    timestamp:       str
    students_processed: int     = 0
    students_assigned:  int     = 0
    students_unmatched: int     = 0
    output_file:        str     = ""
    assigned_total:     int     = 0   # size of assigned_students.txt after this run
    notes:              str     = ""


class CampaignManager:
    """Loads, saves, and queries campaign history."""

    def __init__(self) -> None:
        self._runs: List[CampaignRun] = []
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_run(
        self,
        season:           str,
        checkpoint_type:  str,
        students_processed: int,
        students_assigned:  int,
        students_unmatched: int,
        output_file:      str = "",
        notes:            str = "",
    ) -> CampaignRun:
        """Record a completed processing run and save to disk."""
        assigned_total = self._count_assigned()
        run = CampaignRun(
            run_id=datetime.now().strftime("%Y%m%d%H%M%S"),
            season=season.strip(),
            checkpoint_type=checkpoint_type,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            students_processed=students_processed,
            students_assigned=students_assigned,
            students_unmatched=students_unmatched,
            output_file=output_file,
            assigned_total=assigned_total,
            notes=notes,
        )
        self._runs.append(run)
        self._save()
        logger.info(
            "CampaignManager: Recorded run — Season: '%s' | Checkpoint: '%s' | "
            "Processed: %d | Assigned: %d",
            season, checkpoint_type, students_processed, students_assigned,
        )
        return run

    def all_runs(self) -> List[CampaignRun]:
        return list(self._runs)

    def runs_for_season(self, season: str) -> List[CampaignRun]:
        return [r for r in self._runs if r.season == season]

    def seasons(self) -> List[str]:
        """Return unique season names in chronological order."""
        seen = []
        for r in self._runs:
            if r.season not in seen:
                seen.append(r.season)
        return seen

    def student_appearance_counts(self) -> Dict[str, int]:
        """
        Count how many campaigns each student has appeared in.
        Reads assigned_students.txt — students appear once per run they were assigned.
        Returns {student_id: count}.

        Note: assigned_students.txt is cumulative so we can't get per-run counts
        from it alone. We use the run records to track season boundaries instead.
        """
        # For now return count from assigned_students.txt as a lower bound
        if not ASSIGNED_STUDENTS_PATH.exists():
            return {}
        try:
            lines = ASSIGNED_STUDENTS_PATH.read_text(encoding="utf-8").splitlines()
            counts: Dict[str, int] = {}
            for line in lines:
                sid = line.strip().upper()
                if sid:
                    counts[sid] = counts.get(sid, 0) + 1
            return counts
        except Exception:
            return {}

    def repeat_students(self, min_appearances: int = 2) -> Dict[str, int]:
        """Return students who appear >= min_appearances times."""
        counts = self.student_appearance_counts()
        return {sid: n for sid, n in counts.items() if n >= min_appearances}

    def reset_season(self, season: str) -> int:
        """
        Clear assigned_students.txt to start a fresh season.
        Marks all runs for the old season as archived.
        Returns the number of student IDs cleared.
        """
        cleared = 0
        if ASSIGNED_STUDENTS_PATH.exists():
            try:
                lines = ASSIGNED_STUDENTS_PATH.read_text(encoding="utf-8").splitlines()
                cleared = len([l for l in lines if l.strip()])
                ASSIGNED_STUDENTS_PATH.unlink()
                logger.info(
                    "CampaignManager: Cleared %d IDs from assigned_students.txt "
                    "for season reset '%s'", cleared, season
                )
            except Exception as exc:
                logger.error("CampaignManager: Could not clear assigned_students.txt: %s", exc)
        return cleared

    def delete_run(self, run_id: str) -> bool:
        before = len(self._runs)
        self._runs = [r for r in self._runs if r.run_id != run_id]
        if len(self._runs) < before:
            self._save()
            return True
        return False

    def assigned_count(self) -> int:
        """Current number of IDs in assigned_students.txt."""
        return self._count_assigned()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not CAMPAIGNS_PATH.exists():
            self._runs = []
            return
        try:
            data = json.loads(CAMPAIGNS_PATH.read_text(encoding="utf-8"))
            self._runs = [CampaignRun(**r) for r in data.get("runs", [])]
            logger.info("CampaignManager: Loaded %d runs from campaigns.json", len(self._runs))
        except Exception as exc:
            logger.warning("CampaignManager: Could not load campaigns.json: %s", exc)
            self._runs = []

    def _save(self) -> None:
        CAMPAIGNS_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {"runs": [asdict(r) for r in self._runs]}
        try:
            CAMPAIGNS_PATH.write_text(
                json.dumps(data, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            logger.error("CampaignManager: Could not save campaigns.json: %s", exc)

    def _count_assigned(self) -> int:
        if not ASSIGNED_STUDENTS_PATH.exists():
            return 0
        try:
            lines = ASSIGNED_STUDENTS_PATH.read_text(encoding="utf-8").splitlines()
            return len([l for l in lines if l.strip()])
        except Exception:
            return 0
