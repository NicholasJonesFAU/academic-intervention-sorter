"""
normalization.py — Data normalization utilities.

All ID normalization, at-risk flag normalization, and string cleaning
must flow through here to ensure consistent behavior across the pipeline.
"""

import re
import pandas as pd
from typing import Any, Optional
from utils.config import AT_RISK_TRUE_VALUES, EXCEL_TAB_INVALID_CHARS, EXCEL_TAB_MAX_LEN


def normalize_student_id(value: Any) -> str:
    """
    Normalize a Student ID to a canonical uppercase string.

    Rules:
        - Convert to string
        - Strip all surrounding whitespace
        - Remove hidden whitespace / embedded newlines
        - Uppercase
        - Remove trailing Excel decimal artifacts like ".0"

    Examples:
        " z12345678 "   → "Z12345678"
        "Z12345678.0"   → "Z12345678"
        "z12345678\\n"  → "Z12345678"
    """
    if pd.isna(value):
        return ""
    raw = str(value).strip()
    # Remove embedded whitespace characters (tabs, newlines, zero-width spaces)
    raw = re.sub(r"[\s\u00a0\u200b\ufeff]+", "", raw)
    # Remove trailing .0 from Excel numeric coercion
    raw = re.sub(r"\.0+$", "", raw)
    return raw.upper()


def normalize_student_id_series(series: pd.Series) -> pd.Series:
    """Vectorized normalization of a Student ID column."""
    return series.astype(str).str.strip().str.replace(
        r"[\s\u00a0\u200b\ufeff]+", "", regex=True
    ).str.replace(r"\.0+$", "", regex=True).str.upper()


def normalize_at_risk_flag(value: Any) -> bool:
    """
    Normalize an At-Risk flag to a Python bool.

    Treats TRUE / Yes / Y / 1 (case-insensitive, whitespace-trimmed) as True.
    Everything else — including NaN, blank, None — is False.
    """
    if pd.isna(value):
        return False
    normalized = str(value).strip().lower()
    return normalized in AT_RISK_TRUE_VALUES


def normalize_at_risk_series(series: pd.Series) -> pd.Series:
    """Vectorized at-risk normalization returning a boolean Series."""
    cleaned = series.astype(str).str.strip().str.lower()
    return cleaned.isin(AT_RISK_TRUE_VALUES)


def normalize_string(value: Any) -> str:
    """Clean a generic string value — strip whitespace, handle NaN."""
    if pd.isna(value):
        return ""
    return str(value).strip()


def normalize_string_series(series: pd.Series) -> pd.Series:
    """Vectorized string normalization."""
    return series.fillna("").astype(str).str.strip()


def normalize_absences(value: Any) -> float:
    """
    Parse an absences value to a numeric float.
    Returns 0.0 if the value cannot be parsed.
    """
    if pd.isna(value):
        return 0.0
    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        return 0.0


def safe_excel_tab_name(name: str, existing_names: Optional[list] = None) -> str:
    """
    Sanitize a string to be a valid Excel worksheet tab name.

    Rules:
        - Remove invalid characters: []:*?/\\
        - Truncate to 31 characters
        - Ensure uniqueness against existing_names (append _2, _3, etc.)
        - Never return empty string — fall back to "Sheet"
    """
    cleaned = re.sub(EXCEL_TAB_INVALID_CHARS, "", name).strip()
    if not cleaned:
        cleaned = "Sheet"
    cleaned = cleaned[:EXCEL_TAB_MAX_LEN]

    if existing_names is None:
        return cleaned

    candidate = cleaned
    counter = 2
    while candidate in existing_names:
        suffix = f"_{counter}"
        candidate = cleaned[: EXCEL_TAB_MAX_LEN - len(suffix)] + suffix
        counter += 1

    return candidate


def deduplicate_multiline_values(joined: str, delimiter: str = "\n") -> str:
    """
    Given a delimiter-joined string, remove duplicate entries while
    preserving order and readability.
    """
    if not joined:
        return ""
    seen = set()
    result = []
    for part in joined.split(delimiter):
        stripped = part.strip()
        if stripped and stripped not in seen:
            seen.add(stripped)
            result.append(stripped)
    return delimiter.join(result)
