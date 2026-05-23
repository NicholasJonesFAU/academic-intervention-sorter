\# Architecture



\## Overview



Academic Intervention Sorter is a desktop Python application for processing academic progress report exports, sorting at-risk students into prioritized intervention groups, and producing advisor-friendly Excel workbooks.



\## Main Layers



\### GUI Layer

`main.py`



Handles:

\- file selection

\- user input

\- progress display

\- error dialogs

\- launching processing workflows



The GUI delegates processing to backend pipeline classes.



\### Pipeline Layer

`processors/pipeline\_controller.py`



Handles:

\- validation

\- sequencing

\- metrics

\- error propagation

\- processing orchestration



\### Processing Layer

`processors/`



Handles:

\- progress report loading

\- at-risk filtering

\- student/course aggregation

\- contact merging

\- group matching

\- faculty report status processing

\- Excel export



\### Utility Layer

`utils/`



Handles:

\- configuration

\- normalization

\- validation helpers

\- logging

\- Excel formatting

\- user-editable settings



\## Design Goals



\- Keep GUI logic separate from business logic

\- Centralize configuration

\- Normalize student IDs before matching

\- Preserve auditability through QA logs

\- Avoid silent failures

\- Produce polished Excel output

\- Support future expansion

