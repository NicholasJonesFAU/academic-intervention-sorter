"""
validation.py — Input validation utilities for the Intervention Sorter.

All file and column validation flows through here.
Returns structured ValidationResult objects rather than raising immediately,
so the pipeline controller can accumulate all errors before reporting.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple
import pandas as pd


@dataclass
class ValidationResult:
    """Encapsulates the outcome of a validation check."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def merge(self, other: "ValidationResult") -> None:
        """Merge another ValidationResult into this one."""
        if not other.is_valid:
            self.is_valid = False
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)

    def add_error(self, msg: str) -> None:
        self.is_valid = False
        self.errors.append(msg)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def __bool__(self) -> bool:
        return self.is_valid


def validate_file_exists(path: Path, label: str) -> ValidationResult:
    """Check that a file exists and is a file (not directory)."""
    result = ValidationResult(is_valid=True)
    if not path.exists():
        result.add_error(f"{label} not found: {path}")
    elif not path.is_file():
        result.add_error(f"{label} is not a file: {path}")
    return result


def validate_file_readable(path: Path, label: str) -> ValidationResult:
    """Check that a file can be opened for reading."""
    result = ValidationResult(is_valid=True)
    try:
        with open(path, "rb") as f:
            f.read(16)
    except (PermissionError, OSError) as exc:
        result.add_error(f"{label} cannot be read: {exc}")
    return result


def validate_output_path(path: Path) -> ValidationResult:
    """Check that the output directory exists and is writable."""
    result = ValidationResult(is_valid=True)
    directory = path.parent if path.suffix else path
    if not directory.exists():
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            result.add_error(f"Cannot create output directory '{directory}': {exc}")
            return result
    # Test write access
    test_file = directory / ".write_test"
    try:
        test_file.touch()
        test_file.unlink()
    except (PermissionError, OSError) as exc:
        result.add_error(f"Output directory is not writable '{directory}': {exc}")
    return result


def validate_required_columns(
    df: pd.DataFrame,
    required: List[str],
    source_label: str,
) -> ValidationResult:
    """Verify that all required column names are present in a DataFrame."""
    result = ValidationResult(is_valid=True)
    missing = [col for col in required if col not in df.columns]
    if missing:
        result.add_error(
            f"{source_label} is missing required columns: {missing}. "
            f"Found columns: {list(df.columns)}"
        )
    return result


def validate_control_file_line(line: str, line_number: int, delimiter: str) -> Tuple[bool, str]:
    """
    Validate a single line from the control TXT file.

    Returns (is_valid, error_message).
    Valid format: "Tab Name|filename.xlsx"
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return True, ""     # blank or comment line — skip silently

    parts = stripped.split(delimiter)
    if len(parts) != 2:
        return False, (
            f"Line {line_number}: Expected 'TabName{delimiter}filename.xlsx', "
            f"got: '{stripped}'"
        )
    tab_name, filename = parts[0].strip(), parts[1].strip()
    if not tab_name:
        return False, f"Line {line_number}: Tab name is blank."
    if not filename:
        return False, f"Line {line_number}: Filename is blank."
    return True, ""


def validate_student_id(sid: str) -> Tuple[bool, str]:
    """
    Light validation of a normalized Student ID.
    Returns (is_valid, reason).
    A valid ID must be non-empty after normalization.
    """
    if not sid:
        return False, "Empty Student ID after normalization"
    if len(sid) < 2:
        return False, f"Suspiciously short Student ID: '{sid}'"
    return True, ""
