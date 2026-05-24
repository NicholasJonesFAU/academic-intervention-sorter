"""Action handlers for the Progress Report Sorter tab."""

import threading
import traceback
from pathlib import Path
from tkinter import messagebox

from processors.pipeline_controller import PipelineController, PipelineInputs
from processors.prerun_checker import PreRunChecker
from processors.semester_manager import SemesterManager


def on_run_progress(app):
    if app._processing:
        return
    if not app._ensure_season_set():
        return
    inputs = app._collect_inputs()
    if inputs is None:
        return

    if app._control_picker.path and app._group_dir_picker.path:
        checkpoint = (
            app._checkpoint_type_var.get()
            if hasattr(app, "_checkpoint_type_var")
            else "Progress Report 1"
        )
        proceed, skip_groups = app._show_group_selection_dialog(
            app._control_picker.path,
            app._group_dir_picker.path,
            checkpoint,
        )
        if not proceed:
            return
        inputs.skip_groups = skip_groups

    app._start_processing(inputs, validate_only=False)


def on_validate_progress(app):
    if app._processing:
        return
    inputs = app._collect_inputs()
    if inputs is None:
        return
    app._start_processing(inputs, validate_only=True)


def on_prerun_check_progress(app):
    """Run pre-flight data quality checks without a full pipeline run."""
    paths = {
        "Progress Report": app._progress_picker.path,
        "Contact Report": app._contact_picker.path,
        "Group Control": app._control_picker.path,
        "Group Folder": app._group_dir_picker.path,
    }
    missing = [k for k, v in paths.items() if not v]
    if missing:
        messagebox.showerror(
            "Missing Files",
            "Please select files first:\n" + "\n".join(f"  • {m}" for m in missing),
        )
        return

    app._log("=" * 55, "info")
    app._log("PRE-RUN DATA QUALITY CHECK", "step")
    app._log("=" * 55, "info")

    def _worker():
        checker = PreRunChecker()
        all_results = []
        progress_ids = None

        app.after(0, app._log, "Checking progress report...", "step")
        pr_results = checker.check_progress_report(Path(paths["Progress Report"]))
        all_results.extend(pr_results)

        try:
            from utils.settings_manager import get_settings
            from utils.normalization import normalize_student_id_series, normalize_at_risk_series
            import pandas as pd

            col = get_settings().progress_report_map
            if paths["Progress Report"].endswith(".csv"):
                df = pd.read_csv(paths["Progress Report"], dtype=str, keep_default_na=False)
            else:
                df = pd.read_excel(
                    paths["Progress Report"],
                    dtype=str,
                    keep_default_na=False,
                    engine="openpyxl",
                )
            df.columns = [str(c).strip() for c in df.columns]
            if col["at_risk"] in df.columns and col["student_id"] in df.columns:
                at_risk_mask = normalize_at_risk_series(df[col["at_risk"]])
                progress_ids = set(
                    normalize_student_id_series(df[at_risk_mask][col["student_id"]])
                    .replace("", pd.NA)
                    .dropna()
                )
        except Exception:
            pass

        app.after(0, app._log, "Checking contact report...", "step")
        cr_results = checker.check_contact_report(Path(paths["Contact Report"]), progress_ids)
        all_results.extend(cr_results)

        app.after(0, app._log, "Checking group files...", "step")
        gf_results = checker.check_group_files(
            Path(paths["Group Control"]),
            Path(paths["Group Folder"]),
            progress_ids,
        )
        all_results.extend(gf_results)

        app.after(0, app._show_precheck_results, all_results)

    threading.Thread(target=_worker, daemon=True).start()


def show_precheck_results(app, results):
    """Display pre-run check results in the log and a summary popup."""
    errors = [r for r in results if r.level == "error"]
    warnings = [r for r in results if r.level == "warning"]
    infos = [r for r in results if r.level == "info"]

    for r in infos:
        app._log(f"  ℹ️  {r.message}", "info")
    for r in warnings:
        app._log(f"  ⚠️  {r.message}", "warning")
    for r in errors:
        app._log(f"  ❌  {r.message}", "error")

    if errors:
        app._log("\n❌ Pre-run check found errors — fix before running.", "error")
        messagebox.showerror(
            "Pre-Run Check Failed",
            f"Found {len(errors)} error(s) and {len(warnings)} warning(s).\n\n"
            + "\n".join(f"❌ {r.message[:120]}" for r in errors[:5]),
        )
    elif warnings:
        app._log(f"\n⚠️  Pre-run check passed with {len(warnings)} warning(s).", "warning")
        messagebox.showwarning(
            "Pre-Run Check — Warnings",
            f"No errors found but {len(warnings)} warning(s):\n\n"
            + "\n".join(f"⚠️ {r.message[:120]}" for r in warnings[:5])
            + "\n\nYou can still run — check warnings in the log.",
        )
    else:
        app._log("\n✅ Pre-run check passed — all files look good!", "success")
        messagebox.showinfo(
            "Pre-Run Check Passed",
            "✅ All files validated successfully!\n\nReady to run.",
        )


def on_clear_progress(app):
    app._log_box.config(state="normal")
    app._log_box.delete("1.0", "end")
    app._log_box.config(state="disabled")
    app._progress_var.set(0)
    app._progress_bar.stop()


def collect_progress_inputs(app):
    """Gather and validate Progress Report Sorter inputs."""
    semester_groups = SemesterManager().get_groups()
    using_semester_groups = bool(semester_groups)

    errors = []
    always_required = {
        "Progress Report": app._progress_picker.path,
        "Contact Report": app._contact_picker.path,
        "Output Folder": app._output_picker.path,
    }
    for label, val in always_required.items():
        if not val:
            errors.append(f"• {label} is required.")

    if not using_semester_groups:
        if not app._control_picker.path:
            errors.append("• Group Control File is required (no semester groups configured).")
        if not app._group_dir_picker.path:
            errors.append("• Group Files Folder is required (no semester groups configured).")

    if errors:
        messagebox.showerror(
            "Missing Inputs",
            "Please provide all required files:\n\n" + "\n".join(errors),
        )
        return None

    season = app._campaign_season_var.get().strip() if hasattr(app, "_campaign_season_var") else ""
    checkpoint = app._checkpoint_type_var.get() if hasattr(app, "_checkpoint_type_var") else "Progress Report"

    control_file = Path(app._control_picker.path) if app._control_picker.path else Path(".")
    group_dir = Path(app._group_dir_picker.path) if app._group_dir_picker.path else Path(".")

    return PipelineInputs(
        progress_report=Path(always_required["Progress Report"]),
        contact_report=Path(always_required["Contact Report"]),
        control_file=control_file,
        group_dir=group_dir,
        output_dir=Path(always_required["Output Folder"]),
        exclude_previous=app._exclude_var.get(),
        season=season,
        checkpoint_type=checkpoint,
        semester_groups=semester_groups if using_semester_groups else None,
    )


def start_progress_processing(app, inputs, validate_only: bool):
    """Run the progress report pipeline in a background thread."""
    app._processing = True
    app._set_buttons_state("disabled")
    app._progress_bar.start(12)
    app._log("=" * 60, "info")
    app._log("VALIDATION CHECK" if validate_only else "STARTING FULL PROCESSING", "step")
    app._log("=" * 60, "info")

    def _worker():
        try:
            controller = PipelineController(
                progress_callback=lambda msg: app.after(0, app._log, msg, "step")
            )
            result = controller.validate_only(inputs) if validate_only else controller.run(inputs)
            app.after(0, app._on_complete, result)
        except Exception:
            app.after(0, app._on_error, traceback.format_exc())

    threading.Thread(target=_worker, daemon=True).start()


def on_progress_complete(app, result):
    app._processing = False
    app._set_buttons_state("normal")
    app._progress_bar.stop()
    app._progress_var.set(100 if result.success else 0)

    if result.success:
        app._log("\n✅ " + result.message, "success")
        if not result.validation_only and result.output_path:
            app._log(f"\n📁 Output: {result.output_path}", "success")
            if messagebox.askyesno(
                "Processing Complete",
                f"Processing completed successfully!\n\n"
                f"Output file:\n{result.output_path}\n\n"
                f"{result.message}\n\n"
                f"Open the output file now?",
            ):
                import subprocess
                import sys

                try:
                    if sys.platform == "win32":
                        subprocess.Popen(["explorer", str(result.output_path)])
                    elif sys.platform == "darwin":
                        subprocess.Popen(["open", str(result.output_path)])
                    else:
                        subprocess.Popen(["xdg-open", str(result.output_path)])
                except Exception:
                    pass
        elif result.validation_only:
            messagebox.showinfo(
                "Validation Passed",
                f"✅ All validations passed!\n\n{result.message}",
            )
    else:
        app._log("\n❌ " + result.message, "error")
        for err in result.errors:
            app._log(f"   {err}", "error")
        if result.warnings:
            for w in result.warnings:
                app._log(f"   {w}", "warning")
        messagebox.showerror(
            "Processing Failed" if not result.validation_only else "Validation Issues",
            ("❌ Processing failed:" if not result.validation_only else "⚠️ Validation issues found:")
            + "\n\n"
            + result.message
            + ("\n\nDetails:\n" + "\n".join(result.errors[:5]) if result.errors else ""),
        )


def on_progress_error(app, error_text: str):
    app._processing = False
    app._set_buttons_state("normal")
    app._progress_bar.stop()
    app._log("\n❌ Unexpected error:\n" + error_text, "error")
    messagebox.showerror(
        "Unexpected Error",
        f"An unexpected error occurred:\n\n{error_text[:800]}",
    )


def set_progress_buttons_state(app, state: str):
    for btn in [app._run_btn, app._validate_btn, app._clear_btn]:
        btn.config(state=state)
