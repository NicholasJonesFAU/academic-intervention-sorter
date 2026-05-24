"""
settings_manager.py — Loads and saves user-editable column mappings.

Settings are stored in settings.json next to the app.
Falls back to config.py defaults if settings.json doesn't exist.

Usage:
    from utils.settings_manager import get_settings
    settings = get_settings()
    col = settings.progress_report_map["student_name"]
"""

import json
import logging
from pathlib import Path
from typing import Dict
from dataclasses import dataclass, field, asdict

from utils.config import (
    PROGRESS_REPORT_COLUMN_MAP as _DEFAULT_PROGRESS,
    CONTACT_REPORT_COLUMN_MAP   as _DEFAULT_CONTACT,
    MIDTERM_COLUMN_MAP          as _DEFAULT_MIDTERM,
    BASE_DIR,
)

# Default faculty report column names
_DEFAULT_FACULTY = {
    "first_name":   "Professor Requested First Name",
    "last_name":    "Professor Requested Last Name",
    "email":        "Professor Requested Email",
    "course_number": "Course Number",
    "section_name": "Section Name",
    "responded":    "Responded",
}

logger = logging.getLogger("intervention_sorter")

SETTINGS_PATH = BASE_DIR / "settings.json"


@dataclass
class AppSettings:
    """All user-editable column mappings."""

    progress_report_map: Dict[str, str] = field(default_factory=lambda: dict(_DEFAULT_PROGRESS))
    contact_report_map:  Dict[str, str] = field(default_factory=lambda: dict(_DEFAULT_CONTACT))
    midterm_map:         Dict[str, str] = field(default_factory=lambda: dict(_DEFAULT_MIDTERM))
    faculty_map:         Dict[str, str] = field(default_factory=lambda: dict(_DEFAULT_FACULTY))

    def save(self) -> None:
        """Write current settings to settings.json."""
        data = {
            "progress_report_map": self.progress_report_map,
            "contact_report_map":  self.contact_report_map,
        }
        try:
            SETTINGS_PATH.write_text(
                json.dumps(data, indent=2), encoding="utf-8"
            )
            logger.info("SettingsManager: Saved settings to '%s'", SETTINGS_PATH)
        except Exception as exc:
            logger.error("SettingsManager: Could not save settings: %s", exc)
            raise

    def reset_to_defaults(self) -> None:
        """Reset all mappings to config.py defaults."""
        self.progress_report_map = dict(_DEFAULT_PROGRESS)
        self.contact_report_map  = dict(_DEFAULT_CONTACT)
        self.midterm_map         = dict(_DEFAULT_MIDTERM)
        self.faculty_map         = dict(_DEFAULT_FACULTY)

    # Convenience properties so processors can use the same names as before
    @property
    def progress_required_columns(self):
        m = self.progress_report_map
        return [m["student_name"], m["student_id"], m["course"], m["at_risk"]]

    @property
    def contact_required_columns(self):
        return [self.contact_report_map["student_id"]]

    @property
    def midterm_required_columns(self):
        m = self.midterm_map
        return [m["student_id"], m["last_name"], m["first_name"],
                m["course_prefix"], m["course_number"], m["midterm_grade"]]

    @property
    def faculty_required_columns(self):
        m = self.faculty_map
        return [m["first_name"], m["last_name"], m["course_number"], m["responded"]]

    @property
    def phone_fallback_columns(self):
        m = self.contact_report_map
        return [m["phone_cellular"], m["phone_local"], m["phone_permanent"]]


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_settings: AppSettings = None


def get_settings() -> AppSettings:
    """Return the loaded AppSettings singleton, loading from disk if needed."""
    global _settings
    if _settings is None:
        _settings = _load()
    return _settings


def reload_settings() -> AppSettings:
    """Force reload from disk (call after saving)."""
    global _settings
    _settings = _load()
    return _settings


def _load() -> AppSettings:
    if not SETTINGS_PATH.exists():
        logger.info("SettingsManager: No settings.json found — using config.py defaults.")
        return AppSettings()

    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        settings = AppSettings()

        # Merge saved values over defaults so new keys added to config still appear
        if "progress_report_map" in data:
            settings.progress_report_map.update(data["progress_report_map"])
        if "contact_report_map" in data:
            settings.contact_report_map.update(data["contact_report_map"])
        if "midterm_map" in data:
            settings.midterm_map.update(data["midterm_map"])
        if "faculty_map" in data:
            settings.faculty_map.update(data["faculty_map"])

        logger.info("SettingsManager: Loaded settings from '%s'", SETTINGS_PATH)
        return settings

    except Exception as exc:
        logger.warning(
            "SettingsManager: Could not load settings.json (%s) — using defaults.", exc
        )
        return AppSettings()
