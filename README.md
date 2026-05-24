# Academic Intervention Sorter

A desktop workflow tool for academic advisors that takes raw at-risk student exports from Navigate/EAB, matches every student to their intervention group (Athletes, Probation, Honors, etc.) in priority order, enriches the records with contact information, and delivers a ready-to-use Excel workbook — no manual filtering, no copy-pasting, no pivot tables.

Built specifically for the **FAU Academic Advising** team and modeled on the real operational workflow of running progress-report campaigns across a full semester cycle.

---

## The Problem It Solves

At a large research university, a progress-report campaign might flag 2,000+ at-risk students at once. The advising team needs to divide that list among advisors by student population (athletes handled differently than honors students, probation students differently than general population), make sure no student is contacted twice in the same campaign, and get phone/email into the same row so advisors can make calls immediately.

Doing this by hand in Excel takes 30–60 minutes per checkpoint and introduces errors every time. This tool does it in under a minute with a full audit trail.

---

## Key Features

### Core Pipeline (Progress Report Sorter tab)
- Loads Navigate/EAB progress report exports in `.xlsx` or `.csv`
- Filters to at-risk students only — supports `TRUE / Yes / Y / 1` flag variants
- Aggregates multiple at-risk courses into one row per student
- Assigns each student to their first matching group via a **priority-ordered control file** — first match wins, exactly like routing rules
- Unmatched students fall to `Risk_1_2` (1–2 at-risk courses) or `Risk_3_Plus` (3+) automatically
- Merges phone and email from a separate contact report — phone fallback chain: cellular → local → permanent
- **Exclude-previous checkbox**: reads/writes a persisted `assigned_students.txt` so students contacted in PR1 are not in the PR2 list unless re-flagged
- **Group Selection dialog**: choose which groups to produce per run without editing any files
- **Pre-Run Check**: validates file formats, column presence, and group-file coverage before committing to a full run

### Midterm Sorter tab
- Same group-matching pipeline applied to Canvas midterm grade exports
- At-risk threshold: C− or below (D+, D, D−, F) — W and WM excluded by design
- Course number built from prefix + number columns (MAC + 1105 → MAC1105)

### Faculty Report Status tab
- Analyzes which professors have submitted progress reports
- Completion % by college, department, and individual professor
- Output workbook includes donut chart (overall), bar charts by college and department, and a `Faculty_Download` tab with full contact info for follow-up

### Campaign Trend tab
- Select PR1, Midterm, and PR2 output workbooks to analyze population movement across the semester
- Student trajectory categories: Persistent, Recovered Early, Recovered Late, Recovered, Relapsed, New Late, and more
- Flow analysis: how many carried forward, recovered, or newly appeared at each transition
- By-group breakdown across all three checkpoints
- **Master Season Report**: combined end-of-semester workbook with full student list and season summary

### Campaigns tab (Semester Manager)
- Create and name a semester — all runs are organized under it automatically
- Checkpoint cards (PR1 / Midterm / PR2) show run count, student totals, and status at a glance
- **Mark Complete** and **Reset** per checkpoint (reset clears assigned list so all students are eligible again)
- File paths (contact report, control file, group folder) are saved on first run and pre-fill all subsequent runs
- Complete Semester generates the Master Season Report and moves the semester to history
- Full audit history of all past semesters preserved

### Settings tab
- Column name mapping for all four input file types — no Python editing required
- Changes saved to `settings.json`, take effect on the next run
- Reset to Defaults button restores all mappings

---

## Output Workbook Structure

Every output workbook (Progress Report Sorter, Midterm Sorter) contains:

| Tab | Contents |
|---|---|
| **Summary** | Processing metrics, run timestamp, group counts, contact coverage rate |
| **[Group name]** | One tab per group from the control file (Athletes, Probation, …) |
| **Risk\_1\_2** | Unmatched students with 1–2 at-risk courses |
| **Risk\_3\_Plus** | Unmatched students with 3+ at-risk courses |
| **Missing\_Contacts** | Students where no phone or email was found |
| **QA\_Log** | All data quality events — column mismatches, duplicate IDs, skipped rows |
| **Processing\_Manifest** | Full run metadata: input file names, timestamps, row counts, settings snapshot |

---

## Setup

```bash
pip install -r requirements.txt
python main.py
```

**Requirements:** Python 3.10+, Windows (tkinter GUI). Tested on Windows 10/11.

### Run headless (no GUI, for testing)
```bash
python test_pipeline.py
```

### Generate synthetic test data
```bash
python generate_test_data.py
```

---

## Input Files

| File | Format | Required Columns |
|---|---|---|
| Progress Report | `.xlsx` / `.csv` | `Student Name`, `Student ID`, `Course Name`, `Marked At-Risk` |
| Contact Report | `.xlsx` | `ZNUMBER` (student ID), phone/email columns |
| Group Control File | `.txt` | `TabName\|filename.xlsx` one per line |
| Group Files Folder | folder | `.xlsx` files listed in the control file |

Column names are configurable in the Settings tab — no code changes needed.

---

## Control File Format

```
Athletes|athletes.xlsx
Probation|probation.xlsx
Honors|honors.xlsx
International|international.xlsx
```

- **Order matters** — first match wins
- Lines starting with `#` are comments; blank lines are ignored

---

## Student ID Normalization

All student IDs are normalized before any matching:

- Converted to string and stripped of whitespace
- Uppercased
- `.0` Excel decimal artifacts removed (common when IDs are read from numeric columns)

`" z12345678 "` → `"Z12345678"` | `"Z12345678.0"` → `"Z12345678"`

---

## At-Risk Flag Values Recognized

`TRUE` / `True` / `true` / `YES` / `Yes` / `Y` / `1`

---

## Architecture

The codebase follows a strict separation between the GUI layer and all business logic. The GUI never processes data — it collects file paths, shows progress, and renders results. Every processor is independently testable.

```
main.py                              ← tkinter GUI — no business logic
gui/
    theme.py                         ← Color constants and button style presets
processors/
    pipeline_controller.py           ← Orchestrator: sequences all pipeline steps
    grade_processor.py               ← Load / filter / deduplicate progress report
    contact_processor.py             ← Load and merge contact report
    aggregator.py                    ← Collapse courses → one row per student
    group_matcher.py                 ← First-match-wins group assignment
    exporter.py                      ← Build output workbook with charts
    midterm_pipeline_controller.py   ← Midterm-specific orchestrator
    midterm_processor.py             ← Load and filter Canvas grade export
    midterm_aggregator.py            ← Course aggregation for midterm
    trend_analyzer.py                ← Cross-checkpoint population analysis
    trend_exporter.py                ← Trend report workbook builder
    report_status_processor.py       ← Faculty submission analysis
    report_status_exporter.py        ← Faculty report workbook with charts
    season_report.py                 ← End-of-semester master report generator
    semester_manager.py              ← Semester lifecycle and run history (JSON)
    campaign_manager.py              ← Assigned-student persistence
    prerun_checker.py                ← Pre-flight data quality validation
    summary_enhancer.py              ← Summary tab chart and metric generation
    department_mapper.py             ← Course prefix → college/department mapping
utils/
    config.py                        ← All configurable values (one place)
    normalization.py                 ← ID, flag, and string normalization
    validation.py                    ← File and column validation
    logging_utils.py                 ← Logger setup and QALog event collector
    excel_utils.py                   ← openpyxl formatting helpers
    settings_manager.py              ← Runtime settings with JSON persistence
output/                              ← Generated workbooks (organized by semester)
logs/                                ← Timestamped run logs
```

### Design decisions worth noting

**GUI/logic decoupling.** `main.py` calls `PipelineController.run(inputs)` and receives a `PipelineResult`. All file I/O, pandas transformations, and Excel generation happen in the processors layer. The GUI thread never blocks — all processing runs in a daemon thread with `self.after()` callbacks for UI updates.

**First-match-wins group routing.** The control file defines a priority queue. A student in the Athletes file who is also on probation appears only in Athletes — exactly matching how advisors' caseloads are structured. The order is owned by operations staff, not developers.

**QA\_Log tab.** Every data quality event (missing column, malformed ID, skipped row) is written to a structured log that lands in the output workbook itself. This means the institution has a reproducible audit trail attached to each intervention file, not a separate log file that might get lost.

**Settings as runtime config.** Column names vary across Navigate export versions and institutional customizations. Rather than requiring a code change, `settings.json` lets an administrator update column mappings through the Settings tab UI without touching Python.

---

## Tech Stack

| Layer | Technology |
|---|---|
| GUI | Python `tkinter` + `ttk` — no external UI dependencies, runs anywhere Python runs |
| Data processing | `pandas` — normalization, deduplication, merge, group assignment |
| Excel output | `openpyxl` — styled workbooks with charts, conditional formatting, freeze panes |
| Charts | `matplotlib` — embedded into openpyxl worksheets as images |
| Persistence | JSON files — semester state, run history, settings |
| Logging | Python `logging` module + custom QALog collector |

---

## Background

This tool was built to solve a real operational pain point in a higher education advising office. The workflow it automates — loading Navigate exports, matching students to advisor caseloads, merging contact data, producing intervention lists — is a task that advisors at large universities run multiple times per semester, under time pressure, at the start of intervention windows when speed matters most.

The design prioritizes **reliability over cleverness**: deterministic group assignment, explicit audit logs, pre-run validation, and settings that non-developers can manage. The goal is that an advising coordinator with no programming background can configure and run this tool confidently.

---

*Python 3.10+ · pandas · openpyxl · matplotlib · tkinter*
