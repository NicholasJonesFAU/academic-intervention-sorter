"""Action handlers for the Midterm Sorter tab.

These functions are intentionally thin and operate on the main Tk app instance.
They were extracted from main.py to keep the application entry point smaller
without changing behavior.
"""

import threading
import traceback
from pathlib import Path
from tkinter import messagebox

from processors.midterm_pipeline_controller import MidtermPipelineController, MidtermPipelineInputs
from processors.semester_manager import SemesterManager


def run_midterm_sort(app):
    """Validate inputs, build MidtermPipelineInputs, and start the midterm pipeline."""
    if app._midterm_processing:
        return
    if not app._ensure_season_set():
        return

    semester_groups = SemesterManager().get_groups()
    using_semester_groups = bool(semester_groups)

    errors = []
    always_required = {
        "Midterm Grade File": app._midterm_file_picker.path,
        "Contact Report": app._midterm_contact_picker.path,
        "Output Folder": app._midterm_output_picker.path,
    }
    for label, val in always_required.items():
        if not val:
            errors.append(f"  {label} is required.")

    if not using_semester_groups:
        if not app._midterm_control_picker.path:
            errors.append("  Group Control File is required (no semester groups configured).")
        if not app._midterm_group_dir_picker.path:
            errors.append("  Group Files Folder is required (no semester groups configured).")

    if errors:
        messagebox.showerror(
            "Missing Inputs",
            "Please provide all required files:\n\n" + "\n".join(errors),
        )
        return

    season = app._campaign_season_var.get().strip() if hasattr(app, "_campaign_season_var") else ""
    control_file = Path(app._midterm_control_picker.path) if app._midterm_control_picker.path else Path(".")
    group_dir = Path(app._midterm_group_dir_picker.path) if app._midterm_group_dir_picker.path else Path(".")

    inputs = MidtermPipelineInputs(
        midterm_file=Path(always_required["Midterm Grade File"]),
        contact_report=Path(always_required["Contact Report"]),
        control_file=control_file,
        group_dir=group_dir,
        output_dir=Path(always_required["Output Folder"]),
        exclude_previous=app._midterm_exclude_var.get(),
        season=season,
        checkpoint_type="Midterm",
        semester_groups=semester_groups if using_semester_groups else None,
    )

    proceed, skip_groups = app._show_group_selection_dialog(
        app._midterm_control_picker.path,
        app._midterm_group_dir_picker.path,
        "Midterm",
    )
    if not proceed:
        return
    inputs.skip_groups = skip_groups

    app._midterm_processing = True
    app._midterm_run_btn.config(state="disabled")
    app._midterm_progress_bar.start(12)
    app._midterm_log_write("=" * 55, "info")
    app._midterm_log_write("STARTING MIDTERM SORT", "step")
    app._midterm_log_write("=" * 55, "info")

    def _worker():
        try:
            controller = MidtermPipelineController(
                progress_callback=lambda msg: app.after(0, app._midterm_log_write, msg, "step")
            )
            result = controller.run(inputs)
            app.after(0, app._on_midterm_complete, result)
        except Exception:
            app.after(0, app._on_midterm_error, traceback.format_exc())

    threading.Thread(target=_worker, daemon=True).start()


def handle_midterm_complete(app, result):
    """Handle successful or failed midterm pipeline completion."""
    app._midterm_processing = False
    app._trend_processing = False
    app._semester_mgr = SemesterManager()
    app._midterm_run_btn.config(state="normal")
    app._midterm_progress_bar.stop()

    if result.success:
        app._midterm_log_write("\n✅ " + result.message, "success")
        app._midterm_log_write("📁 Output: " + str(result.output_path), "success")
        if hasattr(app, "_refresh_campaign_tab"):
            app._refresh_campaign_tab()
        messagebox.showinfo(
            "Midterm Sort Complete",
            "✅ Midterm sort completed!\n\n" + result.message + "\n\nOutput:\n" + str(result.output_path),
        )
    else:
        app._midterm_log_write("\n❌ " + result.message, "error")
        for e in result.errors[:3]:
            app._midterm_log_write("  " + e[:300], "error")
        messagebox.showerror(
            "Midterm Sort Failed",
            "❌ Processing failed:\n\n" + result.message + ("\n\n" + result.errors[0][:400] if result.errors else ""),
        )


def handle_midterm_error(app, error_text: str):
    """Handle an unexpected exception from the midterm pipeline worker."""
    app._midterm_processing = False
    app._trend_processing = False
    app._semester_mgr = SemesterManager()
    app._midterm_run_btn.config(state="normal")
    app._midterm_progress_bar.stop()
    app._midterm_log_write("\n❌ Unexpected error:\n" + error_text[:400], "error")
    messagebox.showerror("Unexpected Error", error_text[:600])
