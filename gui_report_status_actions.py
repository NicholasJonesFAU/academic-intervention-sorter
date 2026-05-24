"""Action handlers for the Faculty Report Status tab.

These functions are intentionally thin and app-oriented. They keep Tkinter event
handling out of main.py while preserving the existing behavior of the original
InterventionSorterApp methods.
"""

import threading
import traceback
from datetime import datetime
from pathlib import Path
from tkinter import messagebox

from processors.department_mapper import DepartmentMapper
from processors.report_status_exporter import ReportStatusExporter
from processors.report_status_processor import ReportStatusProcessor
from utils.config import LOG_DATE_FORMAT


def run_report_status(app) -> None:
    """Validate inputs and generate the faculty report status workbook."""
    if app._report_processing:
        return

    status_path = app._status_picker.path
    mapping_path = app._mapping_picker.path
    output_dir = app._report_output_picker.path

    errors = []
    if not status_path:
        errors.append("• Report Status File is required.")
    if not mapping_path:
        errors.append("• Dept/College Mapping File is required.")
    if not output_dir:
        errors.append("• Output Folder is required.")

    if errors:
        messagebox.showerror("Missing Inputs", "\n".join(errors))
        return

    app._report_processing = True
    app._report_run_btn.config(state="disabled")
    app._report_progress_bar.start(12)
    app._report_log("=" * 55, "info")
    app._report_log("GENERATING FACULTY REPORT STATUS", "step")
    app._report_log("=" * 55, "info")

    def _worker() -> None:
        try:
            timestamp = datetime.now().strftime(LOG_DATE_FORMAT)
            out_path = Path(output_dir) / f"FacultyCompletion_{timestamp}.xlsx"

            app._report_log("Loading department mapping...", "step")
            mapper = DepartmentMapper()
            mapper.load(Path(mapping_path))

            app._report_log("Loading report status file...", "step")
            processor = ReportStatusProcessor()
            processor.load(Path(status_path), mapper)

            overall = processor.overall_stats()
            app._report_log(
                f"Sections loaded: {overall['total_sections']:,}  |  "
                f"Submitted: {overall['submitted']:,}  |  "
                f"Overall: {overall['completion_pct']}%",
                "info",
            )

            app._report_log("Building workbook with charts...", "step")
            exporter = ReportStatusExporter()
            exporter.export(processor, out_path, Path(status_path).name)

            app.after(0, app._on_report_complete, True, str(out_path), overall)
        except Exception:
            app.after(0, app._on_report_complete, False, traceback.format_exc(), {})

    threading.Thread(target=_worker, daemon=True).start()


def handle_report_status_complete(app, success: bool, message: str, overall: dict) -> None:
    """Handle the result of faculty report status generation."""
    app._report_processing = False
    app._report_run_btn.config(state="normal")
    app._report_progress_bar.stop()

    if success:
        summary = (
            "✅ Faculty completion report generated!\n\n"
            "Overall completion: {}%\n"
            "Submitted: {:,} / {:,} sections\n\n"
            "Output:\n{}"
        ).format(
            overall.get("completion_pct", 0),
            overall.get("submitted", 0),
            overall.get("total_sections", 0),
            message,
        )
        app._report_log(
            "\n✅ Done! Overall: {}%".format(overall.get("completion_pct", 0)),
            "success",
        )
        app._report_log("📁 Output: " + message, "success")
        messagebox.showinfo("Report Complete", summary)
        return

    app._report_log("\n❌ Failed: " + message[:200], "error")
    messagebox.showerror("Report Failed", "❌ Report failed:\n\n" + message[:400])
