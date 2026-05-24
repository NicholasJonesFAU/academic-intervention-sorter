"""
semester_manager.py — Manages semester lifecycle for the Intervention Sorter.

A Semester contains:
  - Name (e.g. "Fall 2026")
  - Status (Active / Complete)
  - Saved file paths (contact report, control file, group folder)
  - Three CheckpointRun records (PR1, Midterm, PR2)
  - Master report path (set when semester is completed)
  - Created/completed timestamps

Stored in semesters.json at the project root.
"""

import json
import logging
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from utils.config import (
    SEMESTERS_PATH,
    ASSIGNED_STUDENTS_PATH,
    OUTPUT_DIR,
    SEMESTER_CHECKPOINTS,
    CHECKPOINT_STATUS_NOT_STARTED,
    CHECKPOINT_STATUS_IN_PROGRESS,
    CHECKPOINT_STATUS_COMPLETE,
    SEMESTER_STATUS_ACTIVE,
    SEMESTER_STATUS_COMPLETE,
    LOG_DATE_FORMAT,
)

logger = logging.getLogger("intervention_sorter")


@dataclass
class CheckpointRun:
    """One checkpoint within a semester (PR1, Midterm, or PR2)."""
    name:               str
    status:             str   = CHECKPOINT_STATUS_NOT_STARTED
    run_count:          int   = 0
    students_processed: int   = 0
    students_assigned:  int   = 0
    students_unmatched: int   = 0
    output_file:        str   = ""
    last_run:           str   = ""
    selected_groups:    list  = None  # None = all groups; list = selected subset

    def __post_init__(self):
        if self.selected_groups is None:
            self.selected_groups = []


@dataclass
class Semester:
    """A full semester campaign record."""
    semester_id:    str
    name:           str
    status:         str   = SEMESTER_STATUS_ACTIVE
    created:        str   = ""
    completed:      str   = ""
    master_report:  str   = ""

    # Saved file paths — set on first run, reused for rest of semester
    contact_report: str   = ""
    control_file:   str   = ""
    group_folder:   str   = ""

    # Checkpoint records — keyed by checkpoint name
    checkpoints:    Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.checkpoints:
            self.checkpoints = {
                name: asdict(CheckpointRun(name=name))
                for name in SEMESTER_CHECKPOINTS
            }
        if not self.created:
            self.created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def get_checkpoint(self, name: str) -> CheckpointRun:
        data = self.checkpoints.get(name, {})
        return CheckpointRun(**data) if data else CheckpointRun(name=name)

    def set_checkpoint(self, cp: CheckpointRun) -> None:
        self.checkpoints[cp.name] = asdict(cp)

    def is_complete(self) -> bool:
        return self.status == SEMESTER_STATUS_COMPLETE

    def all_checkpoints_complete(self) -> bool:
        return all(
            self.get_checkpoint(name).status == CHECKPOINT_STATUS_COMPLETE
            for name in SEMESTER_CHECKPOINTS
        )

    def output_files(self) -> Dict[str, str]:
        """Return {checkpoint_name: output_file} for completed checkpoints."""
        return {
            name: self.get_checkpoint(name).output_file
            for name in SEMESTER_CHECKPOINTS
            if self.get_checkpoint(name).output_file
        }


class SemesterManager:
    """Loads, saves, and manages semester records."""

    def __init__(self) -> None:
        self._semesters: List[Semester] = []
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def has_active_semester(self) -> bool:
        return any(s.status == SEMESTER_STATUS_ACTIVE for s in self._semesters)

    def active_semester(self) -> Optional[Semester]:
        for s in self._semesters:
            if s.status == SEMESTER_STATUS_ACTIVE:
                return s
        return None

    def create_semester(self, name: str) -> Semester:
        """Create a new active semester. Errors if one already exists."""
        if self.has_active_semester():
            raise ValueError(
                f"An active semester already exists: "
                f"'{self.active_semester().name}'. Complete it before starting a new one."
            )
        sem = Semester(
            semester_id=datetime.now().strftime("%Y%m%d%H%M%S"),
            name=name.strip(),
        )
        self._semesters.append(sem)
        self._save()
        logger.info("SemesterManager: Created semester '%s'", name)
        return sem

    def save_file_paths(
        self,
        contact_report: str = "",
        control_file:   str = "",
        group_folder:   str = "",
    ) -> None:
        """Save file paths to the active semester (called on first run)."""
        sem = self.active_semester()
        if not sem:
            return
        if contact_report and not sem.contact_report:
            sem.contact_report = contact_report
        if control_file and not sem.control_file:
            sem.control_file = control_file
        if group_folder and not sem.group_folder:
            sem.group_folder = group_folder
        self._save()

    def save_group_selection(
        self,
        checkpoint_name: str,
        selected_groups: list,
    ) -> None:
        """Save the group selection for a checkpoint."""
        sem = self.active_semester()
        if not sem:
            return
        cp = sem.get_checkpoint(checkpoint_name)
        cp.selected_groups = list(selected_groups)
        sem.set_checkpoint(cp)
        self._save()

    def get_group_selection(self, checkpoint_name: str) -> list:
        """Get saved group selection for a checkpoint (empty list = all groups)."""
        sem = self.active_semester()
        if not sem:
            return []
        cp = sem.get_checkpoint(checkpoint_name)
        return list(cp.selected_groups) if cp.selected_groups else []

    def record_run(
        self,
        checkpoint_name:    str,
        students_processed: int,
        students_assigned:  int,
        students_unmatched: int,
        output_file:        str = "",
    ) -> None:
        """Record a completed run for the active semester's checkpoint."""
        sem = self.active_semester()
        if not sem:
            return

        cp = sem.get_checkpoint(checkpoint_name)
        cp.run_count          += 1
        cp.students_processed  = students_processed
        cp.students_assigned   = students_assigned
        cp.students_unmatched  = students_unmatched
        cp.output_file         = output_file
        cp.last_run            = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cp.status              = CHECKPOINT_STATUS_IN_PROGRESS
        sem.set_checkpoint(cp)
        self._save()

        logger.info(
            "SemesterManager: Recorded run — '%s' / '%s' | "
            "Processed: %d | Assigned: %d",
            sem.name, checkpoint_name, students_processed, students_assigned,
        )

    def mark_checkpoint_complete(self, checkpoint_name: str) -> None:
        sem = self.active_semester()
        if not sem:
            return
        cp = sem.get_checkpoint(checkpoint_name)
        cp.status = CHECKPOINT_STATUS_COMPLETE
        sem.set_checkpoint(cp)
        self._save()
        logger.info("SemesterManager: Checkpoint '%s' marked complete", checkpoint_name)

    def reset_checkpoint(self, checkpoint_name: str) -> int:
        """
        Reset a checkpoint back to Not Started.
        Clears assigned_students.txt.
        Returns number of IDs cleared.
        """
        sem = self.active_semester()
        if not sem:
            return 0

        cp = sem.get_checkpoint(checkpoint_name)
        cp.status             = CHECKPOINT_STATUS_NOT_STARTED
        cp.run_count          = 0
        cp.students_processed = 0
        cp.students_assigned  = 0
        cp.students_unmatched = 0
        cp.output_file        = ""
        cp.last_run           = ""
        sem.set_checkpoint(cp)
        self._save()

        cleared = self._clear_assigned_students()
        logger.info(
            "SemesterManager: Reset checkpoint '%s', cleared %d IDs",
            checkpoint_name, cleared,
        )
        return cleared

    def complete_semester(self, master_report_path: str = "") -> Semester:
        """
        Mark the active semester as complete.
        Clears assigned_students.txt (keeps master report reference).
        """
        sem = self.active_semester()
        if not sem:
            raise ValueError("No active semester to complete.")

        sem.status         = SEMESTER_STATUS_COMPLETE
        sem.completed      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sem.master_report  = master_report_path
        self._save()

        self._clear_assigned_students()
        logger.info("SemesterManager: Semester '%s' completed.", sem.name)
        return sem

    def reset_semester(self) -> int:
        """
        Reset the active semester entirely — marks it abandoned,
        clears assigned_students.txt. History is preserved.
        Returns IDs cleared.
        """
        sem = self.active_semester()
        if not sem:
            return 0
        sem.status    = "Abandoned"
        sem.completed = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._save()
        cleared = self._clear_assigned_students()
        logger.info("SemesterManager: Semester '%s' abandoned.", sem.name)
        return cleared

    def history(self) -> List[Semester]:
        """Return all non-active semesters in reverse chronological order."""
        return [s for s in reversed(self._semesters)
                if s.status != SEMESTER_STATUS_ACTIVE]

    def all_semesters(self) -> List[Semester]:
        return list(reversed(self._semesters))

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not SEMESTERS_PATH.exists():
            self._semesters = []
            return
        try:
            data = json.loads(SEMESTERS_PATH.read_text(encoding="utf-8"))
            self._semesters = [Semester(**s) for s in data.get("semesters", [])]
            logger.info(
                "SemesterManager: Loaded %d semesters.", len(self._semesters)
            )
        except Exception as exc:
            logger.warning("SemesterManager: Could not load semesters.json: %s", exc)
            self._semesters = []

    def _save(self) -> None:
        SEMESTERS_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {"semesters": [asdict(s) for s in self._semesters]}
        try:
            SEMESTERS_PATH.write_text(
                json.dumps(data, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            logger.error("SemesterManager: Could not save semesters.json: %s", exc)

    def _clear_assigned_students(self) -> int:
        if not ASSIGNED_STUDENTS_PATH.exists():
            return 0
        try:
            lines = ASSIGNED_STUDENTS_PATH.read_text(encoding="utf-8").splitlines()
            count = len([l for l in lines if l.strip()])
            ASSIGNED_STUDENTS_PATH.unlink()
            return count
        except Exception as exc:
            logger.error("SemesterManager: Could not clear assigned_students.txt: %s", exc)
            return 0
