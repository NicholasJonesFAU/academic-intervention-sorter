"""
generate_sample_data.py — Regenerates the synthetic demo files in sample_data/.

Run this after changing any column mapping in utils/config.py:

    python generate_sample_data.py

Every header is read from the config maps, so the demo files cannot drift out
of sync with what the processors expect. All records are fictional.

Creates:
  - sample_data/progress_report_sample.csv
  - sample_data/contact_report_sample.xlsx
  - sample_data/registration_report_sample.xlsx
  - sample_data/group_control.txt
  - sample_data/group_files/*.xlsx
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from utils.config import (
    CONTACT_REPORT_COLUMN_MAP,
    CONTROL_FILE_DELIMITER,
    PROGRESS_REPORT_COLUMN_MAP,
    REGISTRATION_REPORT_COLUMN_MAP,
    REGISTRATION_STATUS_ACTIVE_VALUES,
)

random.seed(20260915)  # Stable output, so regenerating produces no noisy diff

SAMPLE_DIR = Path(__file__).parent / "sample_data"
GROUP_DIR = SAMPLE_DIR / "group_files"

NUM_STUDENTS = 60

FIRST_NAMES = [
    "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Jamie", "Avery",
    "Cameron", "Blake", "Drew", "Quinn", "Reese", "Skylar", "Peyton", "Hayden",
    "Maria", "Carlos", "Wei", "Priya", "Dimitri", "Fatima", "Kwame", "Nadia",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Wilson",
    "Anderson", "Thomas", "Moore", "Jackson", "Lee", "Perez", "Nguyen",
]

COURSES = [
    ("MAC1105", "College Algebra"),
    ("ENC1101", "College Writing I"),
    ("CHM2045", "General Chemistry I"),
    ("BSC1010", "Biological Principles"),
    ("PSY2012", "General Psychology"),
    ("STA2023", "Introductory Statistics"),
    ("COP2210", "Programming I"),
    ("SLS1501", "Student Success Strategies"),
    ("ECO2013", "Macroeconomics"),
    ("HIS1010", "Western Civilization"),
]

GRADES = ["D", "F", "D+", "D-", "C-", "F", "W"]

ALERT_REASONS = [
    "In Danger of Failing",
    "Excessive Absences",
    "Missing Assignments",
    "Low Exam Scores",
    "No Show",
    "In Danger of Failing; Excessive Absences",
]

COMMENTS = [
    "Student has not responded to outreach.",
    "Spoke with student, aware of situation.",
    "Referred to tutoring center.",
    "",
    "",
]

CAMPUSES = ["Boca Raton", "Davie", "Jupiter", "76"]

COLLEGES = [
    ("Arts and Letters", "English"),
    ("Science", "Biological Sciences"),
    ("Business", "Accounting"),
    ("Engineering", "Computer Science"),
    ("Undergraduate Studies", "Exploratory"),
]

CLASSIFICATIONS = ["Freshman", "Sophomore", "Junior", "Senior"]

# Demo intervention groups, in priority order. First match wins, so a student
# in two lists lands in whichever appears first here.
DEMO_GROUPS = [
    ("Student Accessibility Services", "01_SAS.xlsx"),
    ("Athletes", "02_Athletes.xlsx"),
    ("Academic Coaching", "03_Academic_Coaching.xlsx"),
    ("Tutoring Referral", "04_Tutoring_Referral.xlsx"),
]

# Varied spellings of "true", to exercise at-risk normalization
AT_RISK_TRUE_SPELLINGS = ["TRUE", "True", "true", "Yes", "Y", "1"]


def main() -> None:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    GROUP_DIR.mkdir(parents=True, exist_ok=True)

    student_ids = [f"Z{10000000 + i:08d}" for i in range(1, NUM_STUDENTS + 1)]
    names = {
        sid: f"{random.choice(LAST_NAMES)}, {random.choice(FIRST_NAMES)}"
        for sid in student_ids
    }

    # Every 9th student has no contact row, so Missing_Contacts is populated
    no_contact = set(student_ids[::9])

    p = PROGRESS_REPORT_COLUMN_MAP
    rows = []
    for idx, sid in enumerate(student_ids):
        for course_number, course_name in random.sample(COURSES, random.randint(1, 3)):
            rows.append({
                p["student_name"]:  names[sid],
                p["student_id"]:    sid,
                p["course_number"]: course_number,
                p["course"]:        course_name,
                p["at_risk"]:       AT_RISK_TRUE_SPELLINGS[idx % len(AT_RISK_TRUE_SPELLINGS)],
                p["letter_grade"]:  random.choice(GRADES),
                p["absences"]:      random.randint(0, 12),
                p["alert_reasons"]: random.choice(ALERT_REASONS),
                p["comments"]:      random.choice(COMMENTS),
            })

    # Not-at-risk rows, which the pipeline should filter out
    for sid in random.sample(student_ids, 12):
        course_number, course_name = random.choice(COURSES)
        rows.append({
            p["student_name"]:  names[sid],
            p["student_id"]:    sid,
            p["course_number"]: course_number,
            p["course"]:        course_name,
            p["at_risk"]:       "FALSE",
            p["letter_grade"]:  "B",
            p["absences"]:      1,
            p["alert_reasons"]: "",
            p["comments"]:      "",
        })

    progress_path = SAMPLE_DIR / "progress_report_sample.csv"
    pd.DataFrame(rows).to_csv(progress_path, index=False)
    print(f"  progress report: {len(rows)} rows -> {progress_path.name}")

    c = CONTACT_REPORT_COLUMN_MAP
    contact_rows = []
    for sid in student_ids:
        if sid in no_contact:
            continue
        area = random.choice(["561", "954", "772"])
        contact_rows.append({
            c["student_id"]:      sid,
            c["phone_cellular"]:  f"({area}) {random.randint(200, 999)}-{random.randint(1000, 9999)}",
            c["phone_local"]:     "",
            c["phone_permanent"]: "",
            c["email"]:           f"{sid.lower()}@example.edu",
            c["campus"]:          random.choice(CAMPUSES),
            c["earned_credits"]:  random.randint(0, 90),
            # A cohort term means FTIC; blank means not FTIC
            c["ftic"]:            random.choice(["202608", "202508", "", ""]),
            # Deterministic so adding this column does not reshuffle other RNG fields
            c["major"]:           COLLEGES[student_ids.index(sid) % len(COLLEGES)][1],
        })

    contact_path = SAMPLE_DIR / "contact_report_sample.xlsx"
    pd.DataFrame(contact_rows).to_excel(contact_path, index=False)
    print(f"  contact report: {len(contact_rows)} rows -> {contact_path.name}")

    r = REGISTRATION_REPORT_COLUMN_MAP
    statuses = sorted(REGISTRATION_STATUS_ACTIVE_VALUES) + ["Dropped", "Withdrawn"]
    registration_rows = []
    for sid in student_ids:
        college, major = random.choice(COLLEGES)
        classification = random.choice(CLASSIFICATIONS)
        for _ in range(random.randint(2, 5)):
            registration_rows.append({
                r["student_id"]:          sid,
                r["college"]:             college,
                r["major"]:               major,
                r["classification"]:      classification,
                r["credit_hr"]:           random.choice([1, 3, 3, 3, 4]),
                r["registration_status"]: random.choice(statuses),
                r["dual_enrollment"]:     "N",
                r["fau_high"]:            "N",
                r["ftic_early_admit"]:    "N",
            })

    registration_path = SAMPLE_DIR / "registration_report_sample.xlsx"
    pd.DataFrame(registration_rows).to_excel(registration_path, index=False)
    print(f"  registration report: {len(registration_rows)} rows -> {registration_path.name}")

    # Group files. Slices overlap by two students so first-match-wins is visible.
    shuffled = student_ids[:]
    random.shuffle(shuffled)
    slices = [
        shuffled[0:10],
        shuffled[8:18],
        shuffled[18:27],
        shuffled[26:34],
    ]
    for (tab_name, filename), ids in zip(DEMO_GROUPS, slices):
        path = GROUP_DIR / filename
        pd.DataFrame({"Student ID": ids}).to_excel(path, index=False)
        print(f"  group '{tab_name}': {len(ids)} IDs -> {filename}")

    control_path = SAMPLE_DIR / "group_control.txt"
    control_path.write_text(
        "".join(
            f"{tab}{CONTROL_FILE_DELIMITER}{filename}\n"
            for tab, filename in DEMO_GROUPS
        ),
        encoding="utf-8",
    )
    print(f"  control file -> {control_path.name}")

    print(f"\nDemo data written to {SAMPLE_DIR}")


if __name__ == "__main__":
    main()
