"""
logging_utils.py — Logging setup and QA log management.

Provides:
  - Application-level Python logger (file + console)
  - QALog: in-memory collection of QA events flushed to the output workbook
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from utils.config import (
    LOGS_DIR,
    LOG_FILENAME_PATTERN,
    LOG_DATE_FORMAT,
    LOG_LEVEL,
    QA_LOG_COLUMNS,
)


def setup_logger(name: str = "intervention_sorter") -> logging.Logger:
    """
    Configure and return the application logger.

    Writes to:
      - Rotating timestamped log file in logs/
      - Console (stdout)

    Privacy note: Avoid logging PII (phone, email, comments, full records).
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime(LOG_DATE_FORMAT)
    log_filename = LOG_FILENAME_PATTERN.format(timestamp=timestamp)
    log_path = LOGS_DIR / log_filename

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    if logger.handlers:
        return logger  # Already configured (avoid duplicate handlers)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    logger.info("Logger initialized. Log file: %s", log_path)
    return logger


# ---------------------------------------------------------------------------
# QA Log — in-memory event collector
# ---------------------------------------------------------------------------

class QALog:
    """
    Collects QA events during processing for export to the QA_Log worksheet.

    Categories:
        DUPLICATE_COURSE_ROW
        DUPLICATE_GROUP_ID
        MULTI_GROUP_STUDENT
        MISSING_CONTACT
        INVALID_STUDENT_ID
        BLANK_STUDENT_ID
        SKIPPED_ROW
        MALFORMED_ROW
        MISSING_COLUMN
        EMPTY_GROUP_FILE
        FILE_LOAD_ERROR
        NORMALIZATION_WARNING
        INFO
    """

    def __init__(self) -> None:
        self._entries: List[Dict[str, Any]] = []

    def log(
        self,
        category: str,
        student_id: str = "",
        detail: str = "",
        source_file: str = "",
    ) -> None:
        self._entries.append({
            "Category": category,
            "Student ID": student_id,
            "Detail": detail,
            "Source File": source_file,
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    def entries(self) -> List[Dict[str, Any]]:
        return list(self._entries)

    def count_by_category(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for entry in self._entries:
            cat = entry["Category"]
            counts[cat] = counts.get(cat, 0) + 1
        return counts

    def total(self) -> int:
        return len(self._entries)

    def clear(self) -> None:
        self._entries.clear()
