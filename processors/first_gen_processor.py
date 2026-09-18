"""
first_gen_processor.py — Optional first-generation ID list.

Matching students get First Generation = "Yes" on the outreach report.
This does not create a group tab or change assignment.
"""

import logging
from pathlib import Path
from typing import Set

from processors.group_matcher import GroupMatcher
from utils.logging_utils import QALog

logger = logging.getLogger("intervention_sorter")

FIRST_GEN_COLUMN = "First Generation"
FIRST_GEN_YES = "Yes"


class FirstGenProcessor:
    def __init__(self, qa_log: QALog) -> None:
        self.qa_log = qa_log
        self._ids: Set[str] = set()
        self._source_name: str = ""

    def load(self, file_path: Path) -> None:
        logger.info(
            "FirstGenProcessor: Loading first-generation list from '%s'",
            file_path.name,
        )
        matcher = GroupMatcher(self.qa_log)
        self._ids = matcher._load_id_file(file_path)
        self._source_name = file_path.name
        logger.info(
            "FirstGenProcessor: %d IDs loaded from '%s'",
            len(self._ids),
            file_path.name,
        )

    def merge(self, students_df):
        ids = students_df["Student ID"].astype(str)
        students_df[FIRST_GEN_COLUMN] = ids.map(
            lambda sid: FIRST_GEN_YES if sid in self._ids else ""
        )
        flagged = int((students_df[FIRST_GEN_COLUMN] == FIRST_GEN_YES).sum())
        if self._source_name:
            logger.info(
                "FirstGenProcessor: %d of %d students flagged as first-generation.",
                flagged,
                len(students_df),
            )
        else:
            students_df[FIRST_GEN_COLUMN] = ""
            logger.info(
                "FirstGenProcessor: No first-generation list provided — column left blank."
            )
        return students_df

    @property
    def id_count(self) -> int:
        return len(self._ids)

    @property
    def student_ids(self) -> Set[str]:
        return set(self._ids)

    @property
    def flagged_ready(self) -> bool:
        return bool(self._source_name)
