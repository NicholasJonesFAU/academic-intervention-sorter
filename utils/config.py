"""
config.py — Centralized configuration for the Intervention Sorter application.
All magic values, column names, styling settings, and constants live here.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple
from pathlib import Path

APP_VERSION = "2.0.0"
APP_NAME = "Academic Intervention Sorter"

# ---------------------------------------------------------------------------
# Directory paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"

# ---------------------------------------------------------------------------
# Progress report column mapping
# Maps internal field names → actual column headers in YOUR file.
# If your file uses different headers, update the VALUES (right side) only.
# ---------------------------------------------------------------------------
PROGRESS_REPORT_COLUMN_MAP = {
    "student_name":  "Student Name",
    "student_id":    "Student ID",
    "course_number": "Course Number",
    "course":        "Course Name",
    "at_risk":       "Marked At-Risk",
    "letter_grade":  "Progress Report Grade",
    "absences":      "Progress Report Number of Absences",
    "alert_reasons": "Alert Reasons",
    "comments":      "Progress Report Comment",
}

# Required columns (derived from map)
PROGRESS_REPORT_REQUIRED_COLUMNS = [
    PROGRESS_REPORT_COLUMN_MAP["student_name"],
    PROGRESS_REPORT_COLUMN_MAP["student_id"],
    PROGRESS_REPORT_COLUMN_MAP["course"],
    PROGRESS_REPORT_COLUMN_MAP["at_risk"],
]

PROGRESS_REPORT_OPTIONAL_COLUMNS = [
    PROGRESS_REPORT_COLUMN_MAP["letter_grade"],
    PROGRESS_REPORT_COLUMN_MAP["absences"],
    PROGRESS_REPORT_COLUMN_MAP["alert_reasons"],
    PROGRESS_REPORT_COLUMN_MAP["comments"],
]

# ---------------------------------------------------------------------------
# Contact report column mapping
# Maps internal field names → actual column headers in YOUR file.
# Update the VALUES (right side) to match your contact report headers.
# ---------------------------------------------------------------------------
CONTACT_REPORT_COLUMN_MAP = {
    "student_id":      "ZNUMBER",
    "phone_cellular":  "CELLULAR_PHONE",
    "phone_local":     "LOCAL_PHONE",
    "phone_permanent": "PERMANENT_PHONE",
    "email":           "FAU_EMAIL_ADDRESS",
}


# Phone fallback order — first non-blank value wins
PHONE_FALLBACK_COLUMNS = [
    CONTACT_REPORT_COLUMN_MAP["phone_cellular"],
    CONTACT_REPORT_COLUMN_MAP["phone_local"],
    CONTACT_REPORT_COLUMN_MAP["phone_permanent"],
]

# Required columns (derived from map)
CONTACT_REPORT_REQUIRED_COLUMNS = [
    CONTACT_REPORT_COLUMN_MAP["student_id"],
]

CONTACT_REPORT_OPTIONAL_COLUMNS = [
    CONTACT_REPORT_COLUMN_MAP["phone_cellular"],
    CONTACT_REPORT_COLUMN_MAP["phone_local"],
    CONTACT_REPORT_COLUMN_MAP["phone_permanent"],
    CONTACT_REPORT_COLUMN_MAP["email"],
]

# ---------------------------------------------------------------------------
# At-risk normalization — values treated as TRUE
# ---------------------------------------------------------------------------
AT_RISK_TRUE_VALUES = {
    "true", "yes", "y", "1",
}

# ---------------------------------------------------------------------------
# Output column schema — ALL tabs use this exact order
# ---------------------------------------------------------------------------
OUTPUT_COLUMNS = [
    "Student Name",
    "Student ID",
    "Phone Number",
    "Email",
    "Risk Course Count",
    "Total Absences",
    "Course Numbers",
    "Courses",
    "Grades",
    "Alert Reasons",
    "Comments",
    "Matched Group",
    "Match Source",
    "Processing Notes",
]

# ---------------------------------------------------------------------------
# Aggregation delimiter
# ---------------------------------------------------------------------------
MULTILINE_DELIMITER = "\n"

# ---------------------------------------------------------------------------
# Unmatched bucket tab names & thresholds
# ---------------------------------------------------------------------------
UNMATCHED_LOW_TAB = "Risk_1_2"
UNMATCHED_HIGH_TAB = "Risk_3_Plus"
UNMATCHED_HIGH_THRESHOLD = 3   # >= this value goes to Risk_3_Plus

# ---------------------------------------------------------------------------
# Special tab names
# ---------------------------------------------------------------------------
SUMMARY_TAB = "Summary"
QA_LOG_TAB = "QA_Log"
MANIFEST_TAB = "Processing_Manifest"

# ---------------------------------------------------------------------------
# Control file delimiter
# ---------------------------------------------------------------------------
CONTROL_FILE_DELIMITER = "|"

# ---------------------------------------------------------------------------
# Sorting specification
# ---------------------------------------------------------------------------
SORT_COLUMNS = ["Risk Course Count", "Total Absences", "Student Name"]
SORT_ASCENDING = [False, False, True]

# ---------------------------------------------------------------------------
# Excel tab name constraints
# ---------------------------------------------------------------------------
EXCEL_TAB_MAX_LEN = 31
EXCEL_TAB_INVALID_CHARS = r'[\[\]:*?/\\]'

# ---------------------------------------------------------------------------
# Supported progress report file formats
# ---------------------------------------------------------------------------
PROGRESS_REPORT_EXTENSIONS = {".xlsx", ".xls", ".csv"}

# ---------------------------------------------------------------------------
# Workbook styling
# ---------------------------------------------------------------------------
@dataclass
class StyleConfig:
    # FAU brand colors for Excel output
    header_fill_color: str = "003366"    # FAU Navy
    header_font_color: str = "FFFFFF"
    header_font_size: int = 11
    header_font_name: str = "Calibri"

    alt_row_fill_color: str = "E8EEF4"   # Light FAU blue-gray
    default_fill_color: str = "FFFFFF"

    body_font_name: str = "Calibri"
    body_font_size: int = 10

    summary_accent_color: str = "004488"  # FAU navy lighter
    qa_header_color: str = "9B2226"       # Dark red
    manifest_header_color: str = "1A6B3C" # Dark green

    min_col_width: int = 10
    max_col_width: int = 120
    row_height: int = 55
    freeze_row: int = 1

STYLE = StyleConfig()

# ---------------------------------------------------------------------------
# Column width overrides
# ---------------------------------------------------------------------------
COLUMN_WIDTH_OVERRIDES: Dict[str, int] = {
    "Student Name": 28,
    "Student ID": 14,
    "Phone Number": 16,
    "Email": 30,
    "Risk Course Count": 10,
    "Total Absences": 10,
    "Course Numbers": 16,
    "Courses": 48,
    "Grades": 8,
    "Alert Reasons": 35,
    "Comments": 120,
    "Matched Group": 20,
    "Match Source": 28,
    "Processing Notes": 35,
}

# ---------------------------------------------------------------------------
# QA Log columns
# ---------------------------------------------------------------------------
QA_LOG_COLUMNS = [
    "Category",
    "Student ID",
    "Detail",
    "Source File",
    "Timestamp",
]

# ---------------------------------------------------------------------------
# Summary row labels
# ---------------------------------------------------------------------------
SUMMARY_LABELS = {
    "total_input_rows": "Total Input Rows (Progress Report)",
    "total_at_risk_rows": "Total At-Risk Rows",
    "total_distinct_students": "Distinct At-Risk Students",
    "duplicate_course_rows_removed": "Duplicate Course Rows Removed",
    "total_assigned": "Total Students Assigned to Groups",
    "total_unmatched": "Total Unmatched Students",
    "total_risk_1_2": "Students in Risk_1_2",
    "total_risk_3_plus": "Students in Risk_3_Plus",
    "contact_matches": "Students with Contact Info",
    "contact_misses": "Students Missing Contact Info",
    "processing_timestamp": "Processing Timestamp",
    "execution_duration": "Execution Duration (seconds)",
    "progress_report_file": "Progress Report File",
    "contact_report_file": "Contact Report File",
    "control_file": "Control File",
    "output_file": "Output File",
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FILENAME_PATTERN = "intervention_sorter_{timestamp}.log"
LOG_DATE_FORMAT = "%m-%d-%Y_%I-%M%p"
LOG_LEVEL = "INFO"

# ---------------------------------------------------------------------------
# Output filename pattern
# ---------------------------------------------------------------------------
OUTPUT_FILENAME_PATTERN = "ProgressReport_{timestamp}.xlsx"

# ---------------------------------------------------------------------------
# Supported encodings for TXT control file
# ---------------------------------------------------------------------------
CONTROL_FILE_ENCODINGS = ["utf-8-sig", "utf-8", "latin-1", "cp1252"]

# ---------------------------------------------------------------------------
# Previously assigned students tracking
# ---------------------------------------------------------------------------
ASSIGNED_STUDENTS_FILENAME = "assigned_students.txt"
ASSIGNED_STUDENTS_PATH = OUTPUT_DIR / ASSIGNED_STUDENTS_FILENAME

# ---------------------------------------------------------------------------
# Midterm grade report column mapping
# ---------------------------------------------------------------------------
MIDTERM_COLUMN_MAP = {
    "student_id":     "Z#",
    "last_name":      "LASTNAME",
    "first_name":     "FIRSTNAME",
    "email":          "FAU_EMAIL",
    "college":        "COLLEGE",
    "major":          "MAJOR",
    "classification": "CLASSIFICATION",
    "course_prefix":  "COURSE_PREFIX",
    "course_number":  "COURSE_NUMBER",
    "course_name":    "COURSE",
    "section":        "COURSE_SECTION_NO",
    "credit_hrs":     "CREDIT_HR",
    "midterm_grade":  "MIDTERMGRADE",
}

MIDTERM_REQUIRED_COLUMNS = [
    MIDTERM_COLUMN_MAP["student_id"],
    MIDTERM_COLUMN_MAP["last_name"],
    MIDTERM_COLUMN_MAP["first_name"],
    MIDTERM_COLUMN_MAP["course_prefix"],
    MIDTERM_COLUMN_MAP["course_number"],
    MIDTERM_COLUMN_MAP["midterm_grade"],
]

# Grades that trigger outreach — C- and below only
MIDTERM_AT_RISK_GRADES = {
    "c-", "d+", "d", "d-", "f",
}

# Output columns for midterm tabs
MIDTERM_OUTPUT_COLUMNS = [
    "Student Name",
    "Student ID",
    "Phone Number",
    "Email",
    "College",
    "Major",
    "Classification",
    "Risk Course Count",
    "Course Numbers",
    "Courses",
    "Grades",
    "Matched Group",
    "Match Source",
    "Processing Notes",
]

# Output filename pattern for midterm
MIDTERM_OUTPUT_FILENAME_PATTERN = "ProgressReport_Midterm_{timestamp}.xlsx"

# ---------------------------------------------------------------------------
# Trend / Campaign Cycle Report
# ---------------------------------------------------------------------------
TREND_OUTPUT_FILENAME_PATTERN = "CampaignTrend_{timestamp}.xlsx"

# Student trajectory labels
TRAJECTORY_LABELS = {
    "persistent":       "Persistent (All 3)",
    "recovered_early":  "Recovered Early (PR1 only)",
    "recovered_late":   "Recovered Late (PR1+Mid only)",
    "relapsed":         "Relapsed (PR1+PR2, not Mid)",
    "new_midterm":      "New at Midterm",
    "new_pr2":          "New at PR2",
    "midterm_only":     "Midterm Only",
    "pr2_only":         "PR2 Only",
    "pr1_pr2":          "PR1 and PR2 (not Mid)",
}

TRAJECTORY_COLORS = {
    "persistent":       "#C62828",   # Dark red
    "recovered_early":  "#2E7D32",   # Dark green
    "recovered_late":   "#388E3C",   # Medium green
    "relapsed":         "#F57F17",   # Amber
    "new_midterm":      "#1565C0",   # Blue
    "new_pr2":          "#6A1B9A",   # Purple
    "midterm_only":     "#00838F",   # Teal
    "pr2_only":         "#4527A0",   # Deep purple
    "pr1_pr2":          "#E65100",   # Orange
}

# ---------------------------------------------------------------------------
# Campaign Manager
# ---------------------------------------------------------------------------
CAMPAIGNS_FILENAME = "campaigns.json"
CAMPAIGNS_PATH = BASE_DIR / CAMPAIGNS_FILENAME

CHECKPOINT_TYPES = ["Progress Report 1", "Midterm", "Progress Report 2"]

# ---------------------------------------------------------------------------
# Semester Manager
# ---------------------------------------------------------------------------
SEMESTERS_FILENAME = "semesters.json"
SEMESTERS_PATH = BASE_DIR / SEMESTERS_FILENAME

SEMESTER_CHECKPOINTS = ["Progress Report 1", "Midterm", "Progress Report 2"]

CHECKPOINT_STATUS_NOT_STARTED = "Not Started"
CHECKPOINT_STATUS_IN_PROGRESS = "In Progress"
CHECKPOINT_STATUS_COMPLETE    = "Complete"

SEMESTER_STATUS_ACTIVE   = "Active"
SEMESTER_STATUS_COMPLETE = "Complete"

def get_semester_output_dir(season_name: str = "") -> "Path":
    """Return output/Season_Name/ if season set, else output/."""
    if season_name:
        safe = season_name.strip().replace(" ", "_").replace("/", "-")
        return OUTPUT_DIR / safe
    return OUTPUT_DIR
