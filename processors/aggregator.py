"""
aggregator.py — Collapses multiple at-risk course rows into ONE row per student.

Three separate columns for course data — no text wrapping so rows stay aligned:
  Course Numbers  |  Courses  |  Grades
  MAC1105             Calculus    D
  ENC1101             Writing     F
"""

import logging
import pandas as pd
from utils.config import MULTILINE_DELIMITER
from utils.normalization import deduplicate_multiline_values

logger = logging.getLogger("intervention_sorter")


class Aggregator:

    def aggregate(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("Aggregator: Starting aggregation of %d rows.", len(df))

        if df.empty:
            logger.warning("Aggregator: Input DataFrame is empty.")
            return self._empty_output()

        for col in ["Student ID", "Student Name", "Course", "Course Number",
                    "Current Grade", "Absences", "Alert Reasons", "Comments"]:
            if col not in df.columns:
                df[col] = ""

        result = df.groupby("Student ID", sort=False).apply(
            self._aggregate_student, include_groups=False
        ).reset_index()

        logger.info("Aggregator: Complete. %d distinct students.", len(result))
        return result

    def _aggregate_student(self, group: pd.DataFrame) -> pd.Series:
        delim = MULTILINE_DELIMITER

        # Student name — first non-blank
        names = group["Student Name"].replace("", pd.NA).dropna()
        student_name = names.iloc[0] if not names.empty else ""

        # Three parallel newline-delimited lists — one entry per course row
        course_numbers = []
        course_names   = []
        grades         = []

        for _, row in group.iterrows():
            course_numbers.append(str(row.get("Course Number", "")).strip())
            course_names.append(str(row.get("Course", "")).strip())
            grades.append(str(row.get("Current Grade", "")).strip())

        risk_course_count = len(set(
            (cn or nm) for cn, nm in zip(course_numbers, course_names) if cn or nm
        ))

        total_absences = group["Absences"].fillna(0.0).sum()

        alert_reasons = deduplicate_multiline_values(
            delim.join(str(v) for v in group["Alert Reasons"].fillna("") if str(v).strip()), delim
        )
        comments_raw = deduplicate_multiline_values(
            delim.join(str(v) for v in group["Comments"].fillna("") if str(v).strip()), delim
        )
        # Truncate each comment line to 120 characters
        comments = delim.join(
            (line[:120] + "..." if len(line) > 120 else line)
            for line in comments_raw.split(delim)
        )

        return pd.Series({
            "Student Name":     student_name,
            "Risk Course Count": risk_course_count,
            "Total Absences":   total_absences,
            "Course Numbers":   delim.join(course_numbers),
            "Courses":          delim.join(course_names),
            "Grades":           delim.join(grades),
            "Alert Reasons":    alert_reasons,
            "Comments":         comments,
        })

    @staticmethod
    def _empty_output() -> pd.DataFrame:
        return pd.DataFrame(columns=[
            "Student ID", "Student Name", "Risk Course Count", "Total Absences",
            "Course Numbers", "Courses", "Grades", "Alert Reasons", "Comments",
        ])
