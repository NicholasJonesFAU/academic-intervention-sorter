"""
main.py — Tkinter GUI entry point for the Academic Intervention Sorter.

Architecture:
  - GUI is completely decoupled from business logic
  - All processing is delegated to PipelineController
  - GUI only handles file selection, progress display, and result reporting
"""

import sys
import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

# Ensure the app root is on sys.path
sys.path.insert(0, str(Path(__file__).parent))

from processors.pipeline_controller import PipelineController, PipelineInputs, PipelineResult
from processors.midterm_pipeline_controller import MidtermPipelineController, MidtermPipelineInputs
from utils.settings_manager import get_settings, reload_settings, SETTINGS_PATH
from processors.report_status_processor import ReportStatusProcessor
from processors.report_status_exporter import ReportStatusExporter
from processors.department_mapper import DepartmentMapper
from utils.config import APP_NAME, APP_VERSION, OUTPUT_DIR
from utils.logging_utils import setup_logger

logger = setup_logger("intervention_sorter")


# ---------------------------------------------------------------------------
# Color / style constants for the GUI
# ---------------------------------------------------------------------------
BG_COLOR = "#1F3864"          # Dark navy header
PANEL_BG = "#F4F6FB"          # Light gray panel
BTN_PRIMARY = "#2F5496"       # Primary button blue
BTN_SECONDARY = "#5C6BC0"     # Validation mode button
BTN_DANGER = "#C62828"        # Error / cancel
TEXT_FG = "#1A1A2E"           # Body text
ACCENT_FG = "#2F5496"         # Accent text
SUCCESS_COLOR = "#1B5E20"     # Dark green
WARNING_COLOR = "#E65100"     # Orange warning
FONT_MAIN = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_HEADER = ("Segoe UI", 16, "bold")
FONT_SUB = ("Segoe UI", 9)
FONT_MONO = ("Consolas", 9)


def section_label(parent, text: str) -> tk.Label:
    return tk.Label(
        parent, text=text.upper(), bg=PANEL_BG,
        fg=ACCENT_FG, font=("Segoe UI", 9, "bold"),
    )


class FilePickerRow(tk.Frame):
    """A labeled file-picker row: [Label] [Entry (path)] [Browse button]."""

    def __init__(
        self,
        parent,
        label: str,
        filetypes: list,
        is_directory: bool = False,
        tooltip: str = "",
        **kwargs,
    ):
        super().__init__(parent, bg=PANEL_BG, **kwargs)
        self._path = tk.StringVar()
        self._is_directory = is_directory

        lbl = tk.Label(
            self, text=label, bg=PANEL_BG, fg=TEXT_FG,
            font=FONT_BOLD, width=22, anchor="w",
        )
        lbl.grid(row=0, column=0, padx=(0, 8), sticky="w")

        entry = tk.Entry(
            self, textvariable=self._path, font=FONT_MAIN,
            width=48, relief="flat", bg="white",
            fg=TEXT_FG, insertbackground=TEXT_FG,
            highlightthickness=1, highlightbackground="#B0BEC5",
        )
        entry.grid(row=0, column=1, padx=(0, 8), ipady=4)

        browse_btn = tk.Button(
            self, text="Browse…", font=FONT_MAIN,
            bg=BTN_PRIMARY, fg="white", relief="flat",
            padx=10, pady=4, cursor="hand2",
            command=lambda: self._browse(filetypes),
        )
        browse_btn.grid(row=0, column=2)

        if tooltip:
            tip = tk.Label(
                self, text=tooltip, bg=PANEL_BG, fg="#78909C",
                font=FONT_SUB,
            )
            tip.grid(row=1, column=1, sticky="w", pady=(2, 0))

        self.columnconfigure(1, weight=1)

    def _browse(self, filetypes):
        if self._is_directory:
            path = filedialog.askdirectory(title="Select Folder")
        else:
            path = filedialog.askopenfilename(filetypes=filetypes)
        if path:
            self._path.set(path)

    @property
    def path(self) -> str:
        return self._path.get().strip()

    @path.setter
    def path(self, value: str):
        self._path.set(value)


class InterventionSorterApp(tk.Tk):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME}  v{APP_VERSION}")
        self.geometry("860x760")
        self.minsize(760, 620)
        self.configure(bg=PANEL_BG)
        self.resizable(True, True)

        self._processing = False
        self._processing = False
        self._midterm_processing = False
        self._exclude_var = tk.BooleanVar(value=False)
        self._midterm_exclude_var = tk.BooleanVar(value=False)
        self._build_ui()
        self._set_defaults()
        self._report_processing = False

        logger.info("GUI initialized: %s v%s", APP_NAME, APP_VERSION)

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        # ── Header banner ──────────────────────────────────────────
        header = tk.Frame(self, bg=BG_COLOR, pady=16)
        header.pack(fill="x")
        tk.Label(
            header, text=f"🎓  {APP_NAME}", bg=BG_COLOR, fg="white",
            font=FONT_HEADER,
        ).pack()
        tk.Label(
            header, text="Academic Advising Intervention Workflow  •  " + f"v{APP_VERSION}",
            bg=BG_COLOR, fg="#90CAF9", font=FONT_SUB,
        ).pack(pady=(2, 0))

        # ── Notebook tabs ──────────────────────────────────────────
        style = ttk.Style()
        style.configure("TNotebook.Tab", font=FONT_BOLD, padding=[12, 6])
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=0, pady=0)

        # Tab 1: Intervention Sorter
        tab1 = tk.Frame(notebook, bg=PANEL_BG)
        notebook.add(tab1, text="  📋  Progress Report Sorter  ")

        # Tab 2: Faculty Report Status
        tab2 = tk.Frame(notebook, bg=PANEL_BG)
        notebook.add(tab2, text="  📊  Faculty Report Status  ")

        # Tab 3: Midterm Sorter
        tab3 = tk.Frame(notebook, bg=PANEL_BG)
        notebook.add(tab3, text="  📝  Midterm Sorter  ")
        self._midterm_tab = tab3

        # Tab 4: Settings
        tab4 = tk.Frame(notebook, bg=PANEL_BG)
        notebook.add(tab4, text="  ⚙️  Settings  ")
        self._settings_tab = tab4

        content = tk.Frame(tab1, bg=PANEL_BG, padx=24, pady=16)
        content.pack(fill="both", expand=True)

        # ── File pickers ───────────────────────────────────────────
        section_label(content, "Input Files").pack(anchor="w", pady=(0, 8))

        picker_frame = tk.Frame(content, bg=PANEL_BG)
        picker_frame.pack(fill="x")

        self._progress_picker = FilePickerRow(
            picker_frame,
            label="Progress Report:",
            filetypes=[("Excel/CSV Files", "*.xlsx *.xls *.csv"), ("Excel Files", "*.xlsx *.xls"), ("CSV Files", "*.csv"), ("All Files", "*.*")],
            tooltip="Excel (.xlsx) or CSV file with student at-risk data",
        )
        self._progress_picker.pack(fill="x", pady=4)

        self._contact_picker = FilePickerRow(
            picker_frame,
            label="Contact Report:",
            filetypes=[("Excel Files", "*.xlsx *.xls"), ("All Files", "*.*")],
            tooltip="Excel file with student phone/email",
        )
        self._contact_picker.pack(fill="x", pady=4)

        self._control_picker = FilePickerRow(
            picker_frame,
            label="Group Control File:",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            tooltip="TXT file: TabName|filename.xlsx (one per line, ordered by priority)",
        )
        self._control_picker.pack(fill="x", pady=4)

        self._group_dir_picker = FilePickerRow(
            picker_frame,
            label="Group Files Folder:",
            filetypes=[],
            is_directory=True,
            tooltip="Folder containing group Excel files listed in the control file",
        )
        self._group_dir_picker.pack(fill="x", pady=4)

        self._output_picker = FilePickerRow(
            picker_frame,
            label="Output Folder:",
            filetypes=[],
            is_directory=True,
            tooltip="Where the output Excel workbook will be saved",
        )
        self._output_picker.pack(fill="x", pady=4)

        ttk.Separator(content, orient="horizontal").pack(fill="x", pady=14)

        # ── Buttons ────────────────────────────────────────────────
        btn_frame = tk.Frame(content, bg=PANEL_BG)
        btn_frame.pack(fill="x")

        self._run_btn = tk.Button(
            btn_frame,
            text="▶  Run Full Processing",
            font=FONT_BOLD,
            bg=BTN_PRIMARY, fg="white",
            relief="flat", padx=20, pady=10,
            cursor="hand2",
            command=self._on_run,
        )
        self._run_btn.pack(side="left", padx=(0, 10))

        self._validate_btn = tk.Button(
            btn_frame,
            text="🔍  Validate Only",
            font=FONT_MAIN,
            bg=BTN_SECONDARY, fg="white",
            relief="flat", padx=14, pady=10,
            cursor="hand2",
            command=self._on_validate,
        )
        self._validate_btn.pack(side="left", padx=(0, 10))

        self._clear_btn = tk.Button(
            btn_frame,
            text="⟳  Clear",
            font=FONT_MAIN,
            bg="#78909C", fg="white",
            relief="flat", padx=14, pady=10,
            cursor="hand2",
            command=self._on_clear,
        )
        self._clear_btn.pack(side="left")

        # ── Progress bar ───────────────────────────────────────────
        self._progress_var = tk.DoubleVar(value=0)
        self._progress_bar = ttk.Progressbar(
            content, variable=self._progress_var,
            maximum=100, mode="indeterminate",
        )
        self._progress_bar.pack(fill="x", pady=(12, 0))

        # ── Status log ─────────────────────────────────────────────
        section_label(content, "Processing Log").pack(anchor="w", pady=(12, 4))

        self._log_box = scrolledtext.ScrolledText(
            content, height=10, font=FONT_MONO,
            bg="#0D1117", fg="#C9D1D9",
            insertbackground="white",
            relief="flat",
            wrap="word",
        )
        self._log_box.pack(fill="both", expand=True)
        self._log_box.config(state="disabled")

        # Tag styles for log
        self._log_box.tag_config("success", foreground="#4CAF50")
        self._log_box.tag_config("error", foreground="#F44336")
        self._log_box.tag_config("warning", foreground="#FF9800")
        self._log_box.tag_config("info", foreground="#90CAF9")
        self._log_box.tag_config("step", foreground="#CE93D8")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_run(self):
        if self._processing:
            return
        inputs = self._collect_inputs()
        if inputs is None:
            return
        self._start_processing(inputs, validate_only=False)

    def _on_validate(self):
        if self._processing:
            return
        inputs = self._collect_inputs()
        if inputs is None:
            return
        self._start_processing(inputs, validate_only=True)

    def _on_clear(self):
        self._log_box.config(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.config(state="disabled")
        self._progress_var.set(0)
        self._progress_bar.stop()

    def _collect_inputs(self) -> PipelineInputs | None:
        """Gather file paths from pickers and validate they're not empty."""
        errors = []
        paths = {
            "Progress Report": self._progress_picker.path,
            "Contact Report": self._contact_picker.path,
            "Group Control File": self._control_picker.path,
            "Group Files Folder": self._group_dir_picker.path,
            "Output Folder": self._output_picker.path,
        }
        for label, val in paths.items():
            if not val:
                errors.append(f"• {label} is required.")

        if errors:
            messagebox.showerror(
                "Missing Inputs",
                "Please provide all required files:\n\n" + "\n".join(errors),
            )
            return None

        return PipelineInputs(
            progress_report=Path(paths["Progress Report"]),
            contact_report=Path(paths["Contact Report"]),
            control_file=Path(paths["Group Control File"]),
            group_dir=Path(paths["Group Files Folder"]),
            output_dir=Path(paths["Output Folder"]),
        )

    def _start_processing(self, inputs: PipelineInputs, validate_only: bool):
        """Run the pipeline in a background thread to keep the GUI responsive."""
        self._processing = True
        self._set_buttons_state("disabled")
        self._progress_bar.start(12)
        self._log("=" * 60, "info")
        self._log(
            "VALIDATION CHECK" if validate_only else "STARTING FULL PROCESSING",
            "step",
        )
        self._log("=" * 60, "info")

        def _worker():
            try:
                controller = PipelineController(
                    progress_callback=lambda msg: self.after(0, self._log, msg, "step")
                )
                if validate_only:
                    result = controller.validate_only(inputs)
                else:
                    result = controller.run(inputs)
                self.after(0, self._on_complete, result)
            except Exception:
                err = traceback.format_exc()
                self.after(0, self._on_error, err)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_complete(self, result: PipelineResult):
        self._processing = False
        self._set_buttons_state("normal")
        self._progress_bar.stop()
        self._progress_var.set(100 if result.success else 0)

        if result.success:
            self._log("\n✅ " + result.message, "success")
            if not result.validation_only and result.output_path:
                self._log(f"\n📁 Output: {result.output_path}", "success")
                messagebox.showinfo(
                    "Processing Complete",
                    f"✅ Processing completed successfully!\n\n"
                    f"Output file:\n{result.output_path}\n\n"
                    f"{result.message}",
                )
            elif result.validation_only:
                messagebox.showinfo(
                    "Validation Passed",
                    f"✅ All validations passed!\n\n{result.message}",
                )
        else:
            self._log("\n❌ " + result.message, "error")
            for err in result.errors:
                self._log(f"   {err}", "error")
            if result.warnings:
                for w in result.warnings:
                    self._log(f"   {w}", "warning")
            messagebox.showerror(
                "Processing Failed" if not result.validation_only else "Validation Issues",
                f"{'❌ Processing failed:' if not result.validation_only else '⚠️ Validation issues found:'}\n\n"
                + result.message
                + ("\n\nDetails:\n" + "\n".join(result.errors[:5]) if result.errors else ""),
            )

    def _on_error(self, error_text: str):
        self._processing = False
        self._set_buttons_state("normal")
        self._progress_bar.stop()
        self._log("\n❌ Unexpected error:\n" + error_text, "error")
        messagebox.showerror("Unexpected Error", f"An unexpected error occurred:\n\n{error_text[:800]}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _log(self, message: str, tag: str = "info"):
        self._log_box.config(state="normal")
        self._log_box.insert("end", message + "\n", tag)
        self._log_box.see("end")
        self._log_box.config(state="disabled")

    def _set_buttons_state(self, state: str):
        for btn in [self._run_btn, self._validate_btn, self._clear_btn]:
            btn.config(state=state)

    def _set_defaults(self):
        """Pre-fill output folder to the default output directory."""
        self._output_picker.path = str(OUTPUT_DIR)
        self._build_report_status_tab()
        self._build_midterm_tab()
        self._build_settings_tab()

    def _build_report_status_tab(self):
        """Build the Faculty Report Status tab UI."""
        # Find tab2 — it's the second child of the notebook
        notebook = None
        for widget in self.winfo_children():
            if isinstance(widget, ttk.Notebook):
                notebook = widget
                break
        if not notebook:
            return
        tab2 = notebook.winfo_children()[1]

        content2 = tk.Frame(tab2, bg=PANEL_BG, padx=24, pady=16)
        content2.pack(fill="both", expand=True)

        section_label(content2, "Input Files").pack(anchor="w", pady=(0, 8))

        pf = tk.Frame(content2, bg=PANEL_BG)
        pf.pack(fill="x")

        self._status_picker = FilePickerRow(
            pf, label="Report Status File:",
            filetypes=[("Excel/CSV Files", "*.xlsx *.xls *.csv"), ("Excel Files", "*.xlsx *.xls"), ("CSV Files", "*.csv"), ("All Files", "*.*")],
            tooltip="Excel file showing which professors have submitted progress reports",
        )
        self._status_picker.pack(fill="x", pady=4)

        self._mapping_picker = FilePickerRow(
            pf, label="Dept/College Mapping:",
            filetypes=[("Excel Files", "*.xlsx *.xls"), ("All Files", "*.*")],
            tooltip="Excel file mapping course prefixes to departments and colleges",
        )
        self._mapping_picker.pack(fill="x", pady=4)

        self._report_output_picker = FilePickerRow(
            pf, label="Output Folder:",
            filetypes=[], is_directory=True,
            tooltip="Where the faculty completion workbook will be saved",
        )
        self._report_output_picker.pack(fill="x", pady=4)
        self._report_output_picker.path = str(OUTPUT_DIR)

        ttk.Separator(content2, orient="horizontal").pack(fill="x", pady=14)

        btn_frame2 = tk.Frame(content2, bg=PANEL_BG)
        btn_frame2.pack(fill="x")

        self._report_run_btn = tk.Button(
            btn_frame2,
            text="▶  Generate Faculty Report",
            font=FONT_BOLD,
            bg=BTN_PRIMARY, fg="white",
            relief="flat", padx=20, pady=10,
            cursor="hand2",
            command=self._on_run_report_status,
        )
        self._report_run_btn.pack(side="left")

        self._report_progress_bar = ttk.Progressbar(
            content2, maximum=100, mode="indeterminate"
        )
        self._report_progress_bar.pack(fill="x", pady=(12, 0))

        section_label(content2, "Processing Log").pack(anchor="w", pady=(12, 4))

        self._report_log_box = scrolledtext.ScrolledText(
            content2, height=14, font=FONT_MONO,
            bg="#0D1117", fg="#C9D1D9",
            relief="flat", wrap="word",
        )
        self._report_log_box.pack(fill="both", expand=True)
        self._report_log_box.config(state="disabled")
        self._report_log_box.tag_config("success", foreground="#4CAF50")
        self._report_log_box.tag_config("error",   foreground="#F44336")
        self._report_log_box.tag_config("step",    foreground="#CE93D8")
        self._report_log_box.tag_config("info",    foreground="#90CAF9")

    def _on_run_report_status(self):
        if self._report_processing:
            return

        status_path  = self._status_picker.path
        mapping_path = self._mapping_picker.path
        output_dir   = self._report_output_picker.path

        errors = []
        if not status_path:   errors.append("• Report Status File is required.")
        if not mapping_path:  errors.append("• Dept/College Mapping File is required.")
        if not output_dir:    errors.append("• Output Folder is required.")
        if errors:
            messagebox.showerror("Missing Inputs", "\n".join(errors))
            return

        self._report_processing = True
        self._report_run_btn.config(state="disabled")
        self._report_progress_bar.start(12)
        self._report_log("=" * 55, "info")
        self._report_log("GENERATING FACULTY REPORT STATUS", "step")
        self._report_log("=" * 55, "info")

        def _worker():
            try:
                from datetime import datetime
                from utils.config import LOG_DATE_FORMAT, OUTPUT_FILENAME_PATTERN
                timestamp = datetime.now().strftime(LOG_DATE_FORMAT)
                out_path = Path(output_dir) / f"FacultyCompletion_{timestamp}.xlsx"

                self._report_log("Loading department mapping...", "step")
                mapper = DepartmentMapper()
                mapper.load(Path(mapping_path))

                self._report_log("Loading report status file...", "step")
                proc = ReportStatusProcessor()
                proc.load(Path(status_path), mapper)

                overall = proc.overall_stats()
                self._report_log(
                    f"Sections loaded: {overall['total_sections']:,}  |  "
                    f"Submitted: {overall['submitted']:,}  |  "
                    f"Overall: {overall['completion_pct']}%", "info"
                )

                self._report_log("Building workbook with charts...", "step")
                exporter = ReportStatusExporter()
                exporter.export(proc, out_path, Path(status_path).name)

                self.after(0, self._on_report_complete, True, str(out_path), overall)
            except Exception as exc:
                import traceback
                self.after(0, self._on_report_complete, False, traceback.format_exc(), {})

        import threading
        threading.Thread(target=_worker, daemon=True).start()

    def _on_report_complete(self, success: bool, message: str, overall: dict):
        self._report_processing = False
        self._report_run_btn.config(state="normal")
        self._report_progress_bar.stop()
        if success:
            summary = (
                "\u2705 Faculty completion report generated!\n\n"
                "Overall completion: {}%\n"
                "Submitted: {:,} / {:,} sections\n\n"
                "Output:\n{}"
            ).format(
                overall.get("completion_pct", 0),
                overall.get("submitted", 0),
                overall.get("total_sections", 0),
                message,
            )
            self._report_log("\n\u2705 Done! Overall: {}%".format(overall.get("completion_pct", 0)), "success")
            self._report_log("\U0001f4c1 Output: " + message, "success")
            messagebox.showinfo("Report Complete", summary)
        else:
            self._report_log("\n\u274c Failed: " + message[:200], "error")
            messagebox.showerror("Report Failed", "\u274c Report failed:\n\n" + message[:400])



    def _build_midterm_tab(self):
        """Build the Midterm Sorter tab UI."""
        tab = self._midterm_tab
        outer = tk.Frame(tab, bg=PANEL_BG, padx=24, pady=16)
        outer.pack(fill="both", expand=True)

        section_label(outer, "Input Files").pack(anchor="w", pady=(0, 8))

        pf = tk.Frame(outer, bg=PANEL_BG)
        pf.pack(fill="x")

        self._midterm_file_picker = FilePickerRow(
            pf, label="Midterm Grade File:",
            filetypes=[("Excel/CSV Files", "*.xlsx *.xls *.csv"), ("All Files", "*.*")],
            tooltip="Canvas midterm export — xlsx or csv",
        )
        self._midterm_file_picker.pack(fill="x", pady=4)

        self._midterm_contact_picker = FilePickerRow(
            pf, label="Contact Report:",
            filetypes=[("Excel Files", "*.xlsx *.xls"), ("All Files", "*.*")],
            tooltip="Same contact report used in Progress Report Sorter",
        )
        self._midterm_contact_picker.pack(fill="x", pady=4)

        self._midterm_control_picker = FilePickerRow(
            pf, label="Group Control File:",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            tooltip="TXT file: TabName|filename.xlsx  (one per line, ordered by priority)",
        )
        self._midterm_control_picker.pack(fill="x", pady=4)

        self._midterm_group_dir_picker = FilePickerRow(
            pf, label="Group Files Folder:",
            filetypes=[], is_directory=True,
            tooltip="Folder containing group Excel files listed in the control file",
        )
        self._midterm_group_dir_picker.pack(fill="x", pady=4)

        self._midterm_output_picker = FilePickerRow(
            pf, label="Output Folder:",
            filetypes=[], is_directory=True,
            tooltip="Where the output workbook will be saved",
        )
        self._midterm_output_picker.pack(fill="x", pady=4)
        self._midterm_output_picker.path = str(OUTPUT_DIR)

        # Exclude checkbox
        chk_frame = tk.Frame(outer, bg=PANEL_BG)
        chk_frame.pack(fill="x", pady=(8, 0))
        tk.Checkbutton(
            chk_frame,
            text="Exclude students already assigned in a previous run this campaign",
            variable=self._midterm_exclude_var,
            bg=PANEL_BG, fg=TEXT_FG, font=FONT_MAIN,
            activebackground=PANEL_BG, selectcolor="white", cursor="hand2",
        ).pack(side="left")
        tk.Label(
            chk_frame, text="(reads/writes assigned_students.txt in output folder)",
            bg=PANEL_BG, fg="#78909C", font=FONT_SUB,
        ).pack(side="left", padx=(8, 0))

        ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=14)

        # Buttons — pack BEFORE the log box so they're always visible
        btn_frame = tk.Frame(outer, bg=PANEL_BG)
        btn_frame.pack(fill="x", pady=(0, 8))

        self._midterm_run_btn = tk.Button(
            btn_frame,
            text="▶  Run Midterm Sort",
            font=FONT_BOLD, bg=BTN_PRIMARY, fg="white",
            relief="flat", padx=20, pady=10, cursor="hand2",
            command=self._on_run_midterm,
        )
        self._midterm_run_btn.pack(side="left", padx=(0, 10))

        tk.Button(
            btn_frame,
            text="⟳  Clear",
            font=FONT_MAIN, bg="#78909C", fg="white",
            relief="flat", padx=14, pady=10, cursor="hand2",
            command=lambda: self._midterm_clear_log(),
        ).pack(side="left")

        self._midterm_progress_bar = ttk.Progressbar(
            outer, maximum=100, mode="indeterminate"
        )
        self._midterm_progress_bar.pack(fill="x", pady=(0, 8))

        section_label(outer, "Processing Log").pack(anchor="w", pady=(4, 4))

        self._midterm_log_box = scrolledtext.ScrolledText(
            outer, height=10, font=FONT_MONO,
            bg="#0D1117", fg="#C9D1D9",
            relief="flat", wrap="word",
        )
        self._midterm_log_box.pack(fill="both", expand=True)
        self._midterm_log_box.config(state="disabled")
        self._midterm_log_box.tag_config("success", foreground="#4CAF50")
        self._midterm_log_box.tag_config("error",   foreground="#F44336")
        self._midterm_log_box.tag_config("warning", foreground="#FF9800")
        self._midterm_log_box.tag_config("info",    foreground="#90CAF9")
        self._midterm_log_box.tag_config("step",    foreground="#CE93D8")

    def _on_run_midterm(self):
        if self._midterm_processing:
            return
        errors = []
        paths = {
            "Midterm Grade File": self._midterm_file_picker.path,
            "Contact Report":     self._midterm_contact_picker.path,
            "Group Control File": self._midterm_control_picker.path,
            "Group Files Folder": self._midterm_group_dir_picker.path,
            "Output Folder":      self._midterm_output_picker.path,
        }
        for label, val in paths.items():
            if not val:
                errors.append(f"  {label} is required.")
        if errors:
            messagebox.showerror(
                "Missing Inputs",
                "Please provide all required files:\n\n" + "\n".join(errors)
            )
            return

        inputs = MidtermPipelineInputs(
            midterm_file=Path(paths["Midterm Grade File"]),
            contact_report=Path(paths["Contact Report"]),
            control_file=Path(paths["Group Control File"]),
            group_dir=Path(paths["Group Files Folder"]),
            output_dir=Path(paths["Output Folder"]),
            exclude_previous=self._midterm_exclude_var.get(),
        )

        self._midterm_processing = True
        self._midterm_run_btn.config(state="disabled")
        self._midterm_progress_bar.start(12)
        self._midterm_log_write("=" * 55, "info")
        self._midterm_log_write("STARTING MIDTERM SORT", "step")
        self._midterm_log_write("=" * 55, "info")

        import threading
        def _worker():
            try:
                controller = MidtermPipelineController(
                    progress_callback=lambda msg: self.after(
                        0, self._midterm_log_write, msg, "step"
                    )
                )
                result = controller.run(inputs)
                self.after(0, self._on_midterm_complete, result)
            except Exception:
                import traceback
                self.after(0, self._on_midterm_error, traceback.format_exc())

        threading.Thread(target=_worker, daemon=True).start()

    def _on_midterm_complete(self, result):
        self._midterm_processing = False
        self._midterm_run_btn.config(state="normal")
        self._midterm_progress_bar.stop()
        if result.success:
            self._midterm_log_write("\n\u2705 " + result.message, "success")
            self._midterm_log_write("\U0001f4c1 Output: " + str(result.output_path), "success")
            messagebox.showinfo(
                "Midterm Sort Complete",
                "\u2705 Midterm sort completed!\n\n" + result.message +
                "\n\nOutput:\n" + str(result.output_path),
            )
        else:
            self._midterm_log_write("\n\u274c " + result.message, "error")
            for e in result.errors[:3]:
                self._midterm_log_write("  " + e[:300], "error")
            messagebox.showerror(
                "Midterm Sort Failed",
                "\u274c Processing failed:\n\n" + result.message +
                ("\n\n" + result.errors[0][:400] if result.errors else ""),
            )

    def _on_midterm_error(self, error_text: str):
        self._midterm_processing = False
        self._midterm_run_btn.config(state="normal")
        self._midterm_progress_bar.stop()
        self._midterm_log_write("\n\u274c Unexpected error:\n" + error_text[:400], "error")
        messagebox.showerror("Unexpected Error", error_text[:600])

    def _midterm_clear_log(self):
        self._midterm_log_box.config(state="normal")
        self._midterm_log_box.delete("1.0", "end")
        self._midterm_log_box.config(state="disabled")

    def _midterm_log_write(self, message: str, tag: str = "info"):
        self._midterm_log_box.config(state="normal")
        self._midterm_log_box.insert("end", message + "\n", tag)
        self._midterm_log_box.see("end")
        self._midterm_log_box.config(state="disabled")

    def _build_settings_tab(self):
        """Build the Settings tab — column mapping editor."""
        tab3 = self._settings_tab
        settings = get_settings()

        canvas = tk.Canvas(tab3, bg=PANEL_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab3, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=PANEL_BG, padx=24, pady=16)
        canvas_window = canvas.create_window((0, 0), window=inner, anchor="nw")

        def on_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(canvas_window, width=canvas.winfo_width())
        inner.bind("<Configure>", on_configure)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

        # Mouse wheel scrolling
        def on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        self._setting_vars = {}

        def add_section(parent, title, color):
            tk.Label(parent, text=title, bg=color, fg="white",
                     font=FONT_BOLD, padx=8, pady=6,
                     anchor="w").pack(fill="x", pady=(16, 4))

        def add_field(parent, key, label, value, tooltip=""):
            row = tk.Frame(parent, bg=PANEL_BG)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=label, bg=PANEL_BG, fg=TEXT_FG,
                     font=FONT_MAIN, width=32, anchor="w").pack(side="left")
            var = tk.StringVar(value=value)
            self._setting_vars[key] = var
            entry = tk.Entry(row, textvariable=var, font=FONT_MAIN,
                             width=36, relief="flat", bg="white",
                             highlightthickness=1, highlightbackground="#B0BEC5",
                             insertbackground=TEXT_FG)
            entry.pack(side="left", ipady=3)
            if tooltip:
                tk.Label(row, text=f"  {tooltip}", bg=PANEL_BG,
                         fg="#78909C", font=FONT_SUB).pack(side="left")

        # Progress Report section
        add_section(inner, "Progress Report — Column Names", BTN_PRIMARY)
        tk.Label(inner, text="Enter the exact column header from your file for each field.",
                 bg=PANEL_BG, fg="#546E7A", font=FONT_SUB).pack(anchor="w")

        pm = settings.progress_report_map
        pr_fields = [
            ("progress.student_name",  "Student Name",           pm.get("student_name",  ""), "Full name column"),
            ("progress.student_id",    "Student ID",             pm.get("student_id",    ""), "Z-number column"),
            ("progress.course_number", "Course Number",          pm.get("course_number", ""), "e.g. MAC1105"),
            ("progress.course",        "Course Name",            pm.get("course",        ""), "Full course title"),
            ("progress.at_risk",       "At-Risk Flag",           pm.get("at_risk",       ""), "Column containing Yes/No/True/False"),
            ("progress.letter_grade",  "Grade",                  pm.get("letter_grade",  ""), "Progress report grade"),
            ("progress.absences",      "Absences",               pm.get("absences",      ""), "Number of absences"),
            ("progress.alert_reasons", "Alert Reasons",          pm.get("alert_reasons", ""), ""),
            ("progress.comments",      "Comments",               pm.get("comments",      ""), "Professor comments"),
        ]
        for key, label, value, tip in pr_fields:
            add_field(inner, key, label, value, tip)

        # Contact Report section
        add_section(inner, "Contact Report — Column Names", "#375623")
        tk.Label(inner, text="Enter the exact column header from your contact export for each field.",
                 bg=PANEL_BG, fg="#546E7A", font=FONT_SUB).pack(anchor="w")

        cm = settings.contact_report_map
        cr_fields = [
            ("contact.student_id",      "Student ID",       cm.get("student_id",      ""), "Must match progress report ID"),
            ("contact.phone_cellular",  "Cellular Phone",   cm.get("phone_cellular",  ""), "First preference"),
            ("contact.phone_local",     "Local Phone",      cm.get("phone_local",     ""), "Second preference"),
            ("contact.phone_permanent", "Permanent Phone",  cm.get("phone_permanent", ""), "Third preference"),
            ("contact.email",           "Email",            cm.get("email",           ""), ""),
        ]
        for key, label, value, tip in cr_fields:
            add_field(inner, key, label, value, tip)

        # Buttons
        btn_row = tk.Frame(inner, bg=PANEL_BG)
        btn_row.pack(fill="x", pady=(20, 8))

        tk.Button(
            btn_row, text="💾  Save Settings",
            font=FONT_BOLD, bg=BTN_PRIMARY, fg="white",
            relief="flat", padx=20, pady=10, cursor="hand2",
            command=self._on_save_settings,
        ).pack(side="left", padx=(0, 10))

        tk.Button(
            btn_row, text="↩  Reset to Defaults",
            font=FONT_MAIN, bg="#78909C", fg="white",
            relief="flat", padx=14, pady=10, cursor="hand2",
            command=self._on_reset_settings,
        ).pack(side="left")

        self._settings_status = tk.Label(
            inner, text="", bg=PANEL_BG, fg=SUCCESS_COLOR, font=FONT_MAIN
        )
        self._settings_status.pack(anchor="w", pady=(8, 0))

    def _on_save_settings(self):
        """Read all entry fields and save to settings.json."""
        settings = get_settings()

        for key, var in self._setting_vars.items():
            section, field_name = key.split(".", 1)
            value = var.get().strip()
            if section == "progress":
                settings.progress_report_map[field_name] = value
            elif section == "contact":
                settings.contact_report_map[field_name] = value

        try:
            settings.save()
            reload_settings()
            self._settings_status.config(
                text="✅ Settings saved successfully! Changes take effect on next run.",
                fg=SUCCESS_COLOR,
            )
        except Exception as exc:
            self._settings_status.config(
                text=f"❌ Save failed: {exc}", fg="#C62828"
            )

    def _on_reset_settings(self):
        """Reset all fields to config.py defaults."""
        from utils.config import PROGRESS_REPORT_COLUMN_MAP, CONTACT_REPORT_COLUMN_MAP
        if not messagebox.askyesno(
            "Reset Settings",
            "Reset all column mappings to defaults?\nThis cannot be undone."
        ):
            return

        settings = get_settings()
        settings.reset_to_defaults()
        settings.save()
        reload_settings()

        # Refresh entry fields
        pm = settings.progress_report_map
        cm = settings.contact_report_map
        mapping = {
            "progress.student_name":   pm.get("student_name",  ""),
            "progress.student_id":     pm.get("student_id",    ""),
            "progress.course_number":  pm.get("course_number", ""),
            "progress.course":         pm.get("course",        ""),
            "progress.at_risk":        pm.get("at_risk",       ""),
            "progress.letter_grade":   pm.get("letter_grade",  ""),
            "progress.absences":       pm.get("absences",      ""),
            "progress.alert_reasons":  pm.get("alert_reasons", ""),
            "progress.comments":       pm.get("comments",      ""),
            "contact.student_id":      cm.get("student_id",      ""),
            "contact.phone_cellular":  cm.get("phone_cellular",  ""),
            "contact.phone_local":     cm.get("phone_local",     ""),
            "contact.phone_permanent": cm.get("phone_permanent", ""),
            "contact.email":           cm.get("email",           ""),
        }
        for key, value in mapping.items():
            if key in self._setting_vars:
                self._setting_vars[key].set(value)

        self._settings_status.config(
            text="↩ Reset to defaults.", fg="#2F5496"
        )

    def _report_log(self, message: str, tag: str = "info"):
        self._report_log_box.config(state="normal")
        self._report_log_box.insert("end", message + "\n", tag)
        self._report_log_box.see("end")
        self._report_log_box.config(state="disabled")



# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import traceback
    try:
        app = InterventionSorterApp()
        app.mainloop()
    except Exception:
        traceback.print_exc()
        input("\nPress Enter to close...")
