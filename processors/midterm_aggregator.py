"""
midterm_aggregator.py — Collapses per-course midterm rows into ONE row per student.

Output columns:
    Student Name, Student ID, College, Major, Classification,
    Risk Course Count, Course Numbers, Courses, Grades
"""

import logging
import pandas as pd
from utils.config import MULTILINE_DELIMITER
from utils.normalization import deduplicate_multiline_values

logger = logging.getLogger("intervention_sorter")


class MidtermAggregator:

    def aggregate(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("MidtermAggregator: Aggregating %d rows.", len(df))

        if df.empty:
            logger.warning("MidtermAggregator: Empty input.")
            return self._empty_output()

        for col in ["Student ID", "Student Name", "Course Number", "Course",
                    "Midterm Grade", "College", "Major", "Classification"]:
            if col not in df.columns:
                df[col] = ""

        result = df.groupby("Student ID", sort=False).apply(
            self._aggregate_student, include_groups=False
        ).reset_index()

        logger.info("MidtermAggregator: %d distinct students.", len(result))
        return result

    def _aggregate_student(self, group: pd.DataFrame) -> pd.Series:
        delim = MULTILINE_DELIMITER

        # Student name — first non-blank
        names = group["Student Name"].replace("", pd.NA).dropna()
        student_name = names.iloc[0] if not names.empty else ""

        # Parallel lists per course row
        course_numbers = [str(r).strip() for r in group["Course Number"]]
        course_names   = [str(r).strip() for r in group["Course"]]
        grades         = [str(r).strip() for r in group["Midterm Grade"]]

        risk_course_count = len(set(cn for cn in course_numbers if cn))

        # Student info — first non-blank value
        def first_val(col):
            vals = group[col].replace("", pd.NA).dropna()
            return vals.iloc[0] if not vals.empty else ""

        return pd.Series({
            "Student Name":     student_name,
            "College":          first_val("College"),
            "Major":            first_val("Major"),
            "Classification":   first_val("Classification"),
            "Risk Course Count": risk_course_count,
            "Course Numbers":   delim.join(course_numbers),
            "Courses":          delim.join(course_names),
            "Grades":           delim.join(grades),
        })

    @staticmethod
    def _empty_output() -> pd.DataFrame:
        return pd.DataFrame(columns=[
            "Student ID", "Student Name", "College", "Major", "Classification",
            "Risk Course Count", "Course Numbers", "Courses", "Grades",
        ])
