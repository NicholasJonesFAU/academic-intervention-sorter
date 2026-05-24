"""Action handlers for the Campaign Trend and Master Season Report tab."""

import threading
import traceback
from datetime import datetime
from pathlib import Path
from tkinter import messagebox

from processors.season_report import SeasonReportGenerator
from processors.semester_manager import SemesterManager
from processors.trend_analyzer import TrendAnalyzer
from processors.trend_exporter import TrendExporter
from utils.config import LOG_DATE_FORMAT, TREND_OUTPUT_FILENAME_PATTERN


def run_trend_report(app):
    """Generate the campaign trend report in a background thread."""
    if app._trend_processing:
        return

    paths = {
        "PR1": app._trend_pr1_picker.path,
        "Mid": app._trend_mid_picker.path,
        "PR2": app._trend_pr2_picker.path,
        "Output": app._trend_output_picker.path,
    }

    if not any([paths["PR1"], paths["Mid"], paths["PR2"]]):
        messagebox.showerror("Missing Input", "Please select at least one output workbook.")
        return
    if not paths["Output"]:
        messagebox.showerror("Missing Input", "Please select an output folder.")
        return

    app._trend_processing = True
    app._trend_run_btn.config(state="disabled")
    app._trend_progress_bar.start(12)
    app._trend_log_write("=" * 55, "info")
    app._trend_log_write("GENERATING CAMPAIGN TREND REPORT", "step")
    app._trend_log_write("=" * 55, "info")

    pr1_path = Path(paths["PR1"]) if paths["PR1"] else None
    mid_path = Path(paths["Mid"]) if paths["Mid"] else None
    pr2_path = Path(paths["PR2"]) if paths["PR2"] else None
    out_dir = Path(paths["Output"])
    pr1_label = app._trend_pr1_label.get().strip() or "PR1"
    mid_label = app._trend_mid_label.get().strip() or "Midterm"
    pr2_label = app._trend_pr2_label.get().strip() or "PR2"

    def _worker():
        try:
            timestamp = datetime.now().strftime(LOG_DATE_FORMAT)
            out_path = out_dir / TREND_OUTPUT_FILENAME_PATTERN.format(timestamp=timestamp)
            out_dir.mkdir(parents=True, exist_ok=True)

            app.after(0, app._trend_log_write, "Loading workbooks...", "step")
            analyzer = TrendAnalyzer()
            analyzer.load(pr1_path, mid_path, pr2_path)

            overall = analyzer.overall_stats()
            app.after(
                0,
                app._trend_log_write,
                f"Total unique at-risk students: {overall['total_unique_students']:,}",
                "info",
            )
            if pr1_path:
                app.after(0, app._trend_log_write, f"{pr1_label}: {overall['pr1_count']:,} students", "info")
            if mid_path:
                app.after(0, app._trend_log_write, f"{mid_label}: {overall['mid_count']:,} students", "info")
            if pr2_path:
                app.after(0, app._trend_log_write, f"{pr2_label}: {overall['pr2_count']:,} students", "info")

            app.after(0, app._trend_log_write, "Building report with charts...", "step")
            exporter = TrendExporter()
            exporter.export(analyzer, out_path, pr1_label, mid_label, pr2_label)

            app.after(0, app._on_trend_complete, True, str(out_path), overall)
        except Exception:
            app.after(0, app._on_trend_complete, False, traceback.format_exc(), {})

    threading.Thread(target=_worker, daemon=True).start()


def generate_master_report(app):
    """Generate the end-of-semester master season report."""
    out_dir = app._master_output_picker.path
    if not out_dir:
        messagebox.showerror("Missing Input", "Please select an output folder.")
        return

    paths = {
        "pr1": app._master_pr1_picker.path,
        "mid": app._master_mid_picker.path,
        "pr2": app._master_pr2_picker.path,
    }
    if not any(paths.values()):
        messagebox.showerror("Missing Input", "Please select at least one output workbook.")
        return

    season = app._campaign_season_var.get().strip() if hasattr(app, "_campaign_season_var") else ""
    pr1_label = app._trend_pr1_label.get().strip() or "Progress Report 1"
    mid_label = app._trend_mid_label.get().strip() or "Midterm"
    pr2_label = app._trend_pr2_label.get().strip() or "Progress Report 2"

    app._trend_log_write("=" * 55, "info")
    app._trend_log_write("GENERATING MASTER SEASON REPORT", "step")
    app._trend_log_write("=" * 55, "info")

    def _worker():
        try:
            timestamp = datetime.now().strftime(LOG_DATE_FORMAT)
            season_label = season.replace(" ", "_") if season else "Season"
            out_path = Path(out_dir) / f"MasterReport_{season_label}_{timestamp}.xlsx"
            Path(out_dir).mkdir(parents=True, exist_ok=True)

            app.after(0, app._trend_log_write, "Loading output workbooks...", "step")
            generator = SeasonReportGenerator()
            generator.generate(
                pr1_path=Path(paths["pr1"]) if paths["pr1"] else None,
                mid_path=Path(paths["mid"]) if paths["mid"] else None,
                pr2_path=Path(paths["pr2"]) if paths["pr2"] else None,
                output_path=out_path,
                season_name=season,
                pr1_label=pr1_label,
                mid_label=mid_label,
                pr2_label=pr2_label,
            )
            app.after(0, app._on_master_report_done, True, str(out_path))
        except Exception:
            app.after(0, app._on_master_report_done, False, traceback.format_exc())

    threading.Thread(target=_worker, daemon=True).start()


def handle_master_report_done(app, success, message):
    """Handle completion of the master season report."""
    if success:
        app._trend_log_write("\n✅ Master report generated!", "success")
        app._trend_log_write("📁 Output: " + message, "success")
        messagebox.showinfo(
            "Master Report Complete",
            "✅ Master Season Report generated!\n\nOutput:\n" + message,
        )
    else:
        app._trend_log_write("\n❌ Failed:\n" + message[:400], "error")
        messagebox.showerror(
            "Master Report Failed",
            "❌ Failed to generate report:\n\n" + message[:400],
        )


def handle_trend_complete(app, success, message, overall):
    """Handle completion of the campaign trend report."""
    app._trend_processing = False
    app._semester_mgr = SemesterManager()
    app._trend_run_btn.config(state="normal")
    app._trend_progress_bar.stop()

    if success:
        app._trend_log_write("\n✅ Report generated!", "success")
        app._trend_log_write("📁 Output: " + message, "success")
        messagebox.showinfo(
            "Trend Report Complete",
            "✅ Campaign Trend Report generated!\n\n"
            f"Total unique students: {overall.get('total_unique_students', 0):,}\n"
            f"Output:\n{message}",
        )
    else:
        app._trend_log_write("\n❌ Failed:\n" + message[:400], "error")
        messagebox.showerror(
            "Trend Report Failed",
            "❌ Report generation failed:\n\n" + message[:500],
        )
