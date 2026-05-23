# Academic Intervention Sorter

Production-quality academic advising intervention workflow tool.

## Setup

```bash
# Install dependencies
pip install -r requirements.txt
```

## Running the GUI

```bash
python main.py
```

## Running headless (no GUI)

```bash
python test_pipeline.py
```

## Generate sample test data

```bash
python generate_test_data.py
```

---

## Input Files Required

| File | Format | Description |
|------|--------|-------------|
| Progress Report | `.xlsx` | Student at-risk data (requires `Student`, `Student ID`, `Course`, `At-Risk` columns) |
| Contact Report | `.xlsx` | Phone/email data (requires `Student ID` column) |
| Group Control File | `.txt` | Processing order: `TabName\|filename.xlsx` per line |
| Group Files Folder | folder | Directory containing group `.xlsx` files listed in control file |

---

## Control File Format

```
Athletes|athletes.xlsx
Probation|probation.xlsx
Honors|honors.xlsx
International|international.xlsx
```

- ORDER MATTERS — first match wins
- Lines starting with `#` are comments
- Blank lines are ignored

---

## Output Workbook Tabs

| Tab | Contents |
|-----|----------|
| Summary | Processing metrics and counts |
| Athletes, Probation, … | One tab per group (from control file) |
| Risk_1_2 | Unmatched students with 1–2 at-risk courses |
| Risk_3_Plus | Unmatched students with 3+ at-risk courses |
| QA_Log | All data quality events for institutional auditing |
| Processing_Manifest | Full run metadata for reproducibility |

---

## Student ID Normalization

All IDs are normalized before any matching:
- Converted to string, stripped of whitespace
- Uppercased
- `.0` Excel decimal artifacts removed

`" z12345678 "` → `"Z12345678"` | `"Z12345678.0"` → `"Z12345678"`

---

## At-Risk Flag Values Recognized as TRUE

`TRUE` / `True` / `true` / `YES` / `Yes` / `Y` / `1`

---

## Architecture

```
main.py                        ← tkinter GUI (no business logic)
processors/
    pipeline_controller.py     ← Orchestrator: sequences all steps
    grade_processor.py         ← Load/filter/deduplicate progress report
    contact_processor.py       ← Load/merge contact report
    aggregator.py              ← Collapse courses → one row per student
    group_matcher.py           ← First-match-wins group assignment
    exporter.py                ← Build polished output workbook
utils/
    config.py                  ← All configurable values (one place)
    normalization.py           ← ID + flag + string normalization
    validation.py              ← File + column validation
    logging_utils.py           ← Logger + QALog event collector
    excel_utils.py             ← openpyxl formatting helpers
output/                        ← Generated workbooks land here
logs/                          ← Timestamped log files
```
