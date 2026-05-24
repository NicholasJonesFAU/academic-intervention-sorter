# Academic Intervention Sorter Demo Pack

This folder contains fully synthetic sample files for demonstrating the Academic Intervention Sorter without using student data.

## Files Included

- `sample_data/progress_report_sample.csv`
- `sample_data/contact_report_sample.xlsx`
- `sample_data/group_control.txt`
- `sample_data/group_files/01_Academic_Coaching.xlsx`
- `sample_data/group_files/02_Tutoring_Referral.xlsx`
- `sample_data/group_files/03_Advisor_Outreach.xlsx`
- `sample_data/expected_output/expected_behavior.txt`

## How to Run the Demo

1. Start the app:

   ```bash
   python main.py
   ```

2. On the **Progress Report Sorter** tab, select:

   | App Field | Demo File |
   |---|---|
   | Progress Report | `sample_data/progress_report_sample.csv` |
   | Contact Report | `sample_data/contact_report_sample.xlsx` |
   | Group Control File | `sample_data/group_control.txt` |
   | Group Files Folder | `sample_data/group_files/` |
   | Output Folder | any local folder, such as `outputs/` |

3. Click **Pre-Run Check** first.

4. If the check passes, click **Run Full Processing**.

5. Review the generated Excel workbook in your selected output folder.

## What This Demonstrates

This demo shows that the application can:

- read a progress report
- filter to at-risk students
- enrich student records with contact data
- apply prioritized group matching
- prevent duplicate assignment across intervention groups
- generate an organized Excel workbook

## Privacy Note

All data in this demo pack is fictional. Do not commit real student data, reports, outputs, or logs to GitHub.
