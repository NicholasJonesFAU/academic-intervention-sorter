"""
generate_test_data.py — Generates sample input files for testing the pipeline.

Creates:
  - test_data/progress_report.xlsx
  - test_data/contact_report.xlsx
  - test_data/groups/athletes.xlsx
  - test_data/groups/probation.xlsx
  - test_data/groups/honors.xlsx
  - test_data/groups/international.xlsx
  - test_data/groups/control.txt
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import random

SEED = 42
random.seed(SEED)

TEST_DIR = Path(__file__).parent / "test_data"
GROUP_DIR = TEST_DIR / "groups"
TEST_DIR.mkdir(exist_ok=True)
GROUP_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Student IDs
# ---------------------------------------------------------------------------
NUM_STUDENTS = 80
student_ids = [f"Z{10000000 + i:08d}" for i in range(1, NUM_STUDENTS + 1)]

FIRST_NAMES = ["Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Jamie",
               "Avery", "Cameron", "Blake", "Drew", "Quinn", "Reese", "Skylar",
               "Peyton", "Kendall", "Hayden", "Logan", "Dakota", "Emery",
               "Maria", "Carlos", "Wei", "Priya", "Dimitri", "Fatima", "Kwame"]

LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia",
              "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez",
              "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore",
              "Jackson", "Martin", "Lee", "Perez", "Thompson", "White"]

student_names = {
    sid: f"{random.choice(LAST_NAMES)}, {random.choice(FIRST_NAMES)}"
    for sid in student_ids
}

COURSES = [
    "MAC1105", "ENC1101", "CHM2045", "BSC1010", "PSY2012",
    "STA2023", "COP2210", "PHI2010", "ART1300", "MUS1010",
    "SLS1501", "SOC2000", "ECO2013", "HIS1010", "GEA2000",
]

GRADES = ["D", "F", "C-", "D+", "F", "D-", "W", "C"]

ALERT_REASONS = [
    "Missing assignments",
    "Multiple absences",
    "Low exam scores",
    "Has not attended recently",
    "Failing multiple assessments",
    "No contact from student",
]

COMMENTS = [
    "Student has not responded to outreach.",
    "Spoke with student — aware of situation.",
    "Referred to tutoring center.",
    "Student reports family emergency.",
    "",
    "",
]


def make_at_risk_value(idx: int) -> str:
    """Vary At-Risk values to test normalization."""
    options = ["TRUE", "True", "true", "YES", "Yes", "Y", "1"]
    return options[idx % len(options)]


# ---------------------------------------------------------------------------
# Progress Report
# ---------------------------------------------------------------------------
rows = []
for sid in student_ids:
    n_courses = random.choices([1, 2, 3, 4], weights=[30, 35, 25, 10])[0]
    courses = random.sample(COURSES, n_courses)
    for i, course in enumerate(courses):
        rows.append({
            "Student Name": student_names[sid],
            "Student id": sid if random.random() > 0.05 else f"{sid}.0",
            "Full Course Name": course,
            "Is at Risk": make_at_risk_value(len(rows)),
            "Alert Reasons": random.choice(ALERT_REASONS),
            "Letter Grade": random.choice(GRADES),
            "Number of Absences": random.randint(0, 12),
            "Comment": random.choice(COMMENTS),
        })

# Add some non-at-risk rows
for i in range(20):
    sid = random.choice(student_ids[:20])
    rows.append({
        "Student Name": student_names[sid],
        "Student id": sid,
        "Full Course Name": random.choice(COURSES),
        "Is at Risk": "FALSE",
        "Alert Reasons": "",
        "Letter Grade": "B",
        "Number of Absences": 1,
        "Comment": "",
    })

# Add duplicate course row
rows.append({
    "Student Name": student_names[student_ids[0]],
    "Student id": student_ids[0],
    "Full Course Name": "MAC1105",
    "Is at Risk": "TRUE",
    "Alert Reasons": "Duplicate row test",
    "Letter Grade": "D",
    "Number of Absences": 3,
    "Comment": "",
})

progress_df = pd.DataFrame(rows)
progress_path = TEST_DIR / "progress_report.xlsx"
progress_df.to_excel(progress_path, index=False)
print(f"✓ Progress report: {len(progress_df)} rows → {progress_path}")


# ---------------------------------------------------------------------------
# Contact Report
# ---------------------------------------------------------------------------
contact_rows = []
for sid in student_ids:
    has_contact = random.random() > 0.1   # 10% missing
    contact_rows.append({
        "Student ID": sid,
        "Phone Number": f"(954) {random.randint(200,999)}-{random.randint(1000,9999)}" if has_contact else "",
        "Email": f"{sid.lower()}@student.fau.edu" if has_contact else "",
    })

contact_df = pd.DataFrame(contact_rows)
contact_path = TEST_DIR / "contact_report.xlsx"
contact_df.to_excel(contact_path, index=False)
print(f"✓ Contact report: {len(contact_df)} rows → {contact_path}")


# ---------------------------------------------------------------------------
# Group files
# ---------------------------------------------------------------------------
shuffled = student_ids[:]
random.shuffle(shuffled)

athletes     = shuffled[:12]
probation    = shuffled[10:22]   # Overlap: 2 students in both (first-match wins)
honors       = shuffled[20:30]
international = shuffled[28:38]

def write_group_file(path: Path, ids: list):
    pd.DataFrame({"Student ID": ids}).to_excel(path, index=False)
    print(f"✓ Group file: {len(ids)} IDs → {path}")

write_group_file(GROUP_DIR / "athletes.xlsx", athletes)
write_group_file(GROUP_DIR / "probation.xlsx", probation)
write_group_file(GROUP_DIR / "honors.xlsx", honors)
write_group_file(GROUP_DIR / "international.xlsx", international)


# ---------------------------------------------------------------------------
# Control file
# ---------------------------------------------------------------------------
control_content = (
    "Athletes|athletes.xlsx\n"
    "Probation|probation.xlsx\n"
    "Honors|honors.xlsx\n"
    "International|international.xlsx\n"
)
control_path = TEST_DIR / "control.txt"
control_path.write_text(control_content, encoding="utf-8")
print(f"✓ Control file → {control_path}")

print("\nAll test data generated successfully.")
print(f"Test data directory: {TEST_DIR}")
