# Academic Intervention Sorter Demo Pack

`sample_data/` holds fully synthetic files for demonstrating the Academic
Intervention Sorter without touching real student data.

## Files Included

- `sample_data/progress_report_sample.csv`
- `sample_data/contact_report_sample.xlsx`
- `sample_data/registration_report_sample.xlsx`
- `sample_data/first_gen_sample.csv`
- `sample_data/group_control.txt`
- `sample_data/group_files/01_SAS.xlsx`
- `sample_data/group_files/02_Athletes.xlsx`
- `sample_data/group_files/03_Academic_Coaching.xlsx`
- `sample_data/group_files/04_Tutoring_Referral.xlsx`

Regenerate them at any time, for example after changing a column mapping in
`utils/config.py`:

```bash
python generate_sample_data.py
```

## How to Run the Demo

1. Start the app:

   ```bash
   python main.py
   ```

2. On the **Progress Report Sorter** tab, click **Load Demo Files**. That fills
   every picker for you. To do it by hand instead:

   | App Field | Demo File |
   |---|---|
   | Progress Report | `sample_data/progress_report_sample.csv` |
   | Contact Report | `sample_data/contact_report_sample.xlsx` |
   | Registration Report | `sample_data/registration_report_sample.xlsx` |
   | First-Gen List | `sample_data/first_gen_sample.csv` |
   | Group Control File | `sample_data/group_control.txt` |
   | Group Files Folder | `sample_data/group_files/` |

3. Click **Pre-Run Check** first.

4. If the check passes, click **Run Full Processing**.

5. Two workbooks appear in the semester folder under `output/`: one for the
   participating offices and one for Student Accessibility Services.

You can also run the whole pipeline headless, with no GUI:

```bash
python test_pipeline.py
```

## What This Demonstrates

- reading a progress report and filtering to at-risk students
- enriching records with contact and course-registration data
- prioritized group matching, where the first matching group wins
- campus 76 students staying on those lists when they match, otherwise
  splitting to Campus76_45_Under / Campus76_Over_45 by earned credits
- preventing duplicate assignment across intervention groups
- splitting SAS students into their own workbook
- generating outreach workbooks with tracking columns and dropdowns

The demo data deliberately includes a few students in two group files at once,
and a few with no contact record, so first-match-wins and the
`Missing_Contacts` tab are both visible in the output.

## Privacy Note

All data in this demo pack is fictional. Do not commit real student data,
reports, outputs, or logs to GitHub.
