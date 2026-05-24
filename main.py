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
from processors.trend_analyzer import TrendAnalyzer
from processors.campaign_manager import CampaignManager
from processors.semester_manager import SemesterManager, SEMESTER_STATUS_ACTIVE
from processors.season_report import SeasonReportGenerator
from processors.prerun_checker import PreRunChecker
from processors.summary_enhancer import SummaryEnhancer
from processors.trend_exporter import TrendExporter
from utils.settings_manager import get_settings, reload_settings, SETTINGS_PATH
from processors.report_status_processor import ReportStatusProcessor
from processors.report_status_exporter import ReportStatusExporter
from processors.department_mapper import DepartmentMapper
from utils.config import APP_NAME, APP_VERSION, OUTPUT_DIR
from utils.logging_utils import setup_logger

logger = setup_logger("intervention_sorter")


# ---------------------------------------------------------------------------
# Color system  (see gui/theme.py for the canonical reference)
# ---------------------------------------------------------------------------
NAVY         = "#003366"    # FAU brand navy — outer frames, active tab fg, brand labels
NAVY_LIGHT   = "#004488"    # Lighter brand navy — inactive tab bg
NAVY_DARK    = "#1a1f2e"    # Dark charcoal — header inner, primary buttons
NAVY_HOVER   = "#252c3d"    # Hover state for dark-charcoal buttons

RED_ACCENT   = "#c53030"    # Red accent stripe + danger buttons
RED_HOVER    = "#a12424"    # Hover for red buttons

WHITE        = "#ffffff"
PANEL_BG     = "#F0F4F8"    # Panel / content area background
PANEL_BG_DARK = "#E2E8F0"   # Slightly darker panel for contrast
BORDER       = "#CBD5E0"    # Entry highlight / separator

BTN_MUTED        = "#4A5568"    # Slate gray — Cancel, Skip, utility buttons
BTN_MUTED_HOVER  = "#3d4a5c"
BTN_SUCCESS      = "#276749"    # Green — affirmative / complete actions
BTN_SUCCESS_HOVER = "#1e5038"

TEXT_FG       = "#1A2332"
TEXT_MUTED    = "#4A5568"
SUCCESS_COLOR = "#276749"
WARNING_COLOR = "#C05621"
BG_COLOR      = NAVY

# Button style presets — unpack with ** into RoundedButton
# Example: RoundedButton(parent, text="Run", command=fn, **BTN_PRIMARY, font=FONT_BOLD)
BTN_PRIMARY         = dict(bg=NAVY_DARK,     fg=WHITE,    hover_bg=NAVY_HOVER)
BTN_SECONDARY_STYLE = dict(bg="#f0f2f5",     fg=TEXT_FG,  hover_bg="#e2e6ea")
BTN_DANGER          = dict(bg=RED_ACCENT,    fg=WHITE,    hover_bg=RED_HOVER)
BTN_SUCCESS_STYLE   = dict(bg=BTN_SUCCESS,   fg=WHITE,    hover_bg=BTN_SUCCESS_HOVER)
BTN_MUTED_STYLE     = dict(bg=BTN_MUTED,     fg=WHITE,    hover_bg=BTN_MUTED_HOVER)

# ---------------------------------------------------------------------------
# Font loading — Inter from assets/ folder
# ---------------------------------------------------------------------------
def _load_inter_fonts() -> str:
    """
    Register Inter font files with tkinter and return the family name.
    Falls back to Segoe UI if font files are not found.
    """
    import tkinter.font as tkfont
    from pathlib import Path

    assets = Path(__file__).parent / "assets"
    fonts = {
        "regular":  assets / "Inter-Regular.ttf",
        "medium":   assets / "Inter-Medium.ttf",
        "semibold": assets / "Inter-SemiBold.ttf",
    }

    if not all(p.exists() for p in fonts.values()):
        return "Segoe UI"

    try:
        import ctypes
        FR_PRIVATE = 0x10
        for path in fonts.values():
            ctypes.windll.gdi32.AddFontResourceExW(str(path), FR_PRIVATE, 0)
        return "Inter"
    except Exception:
        try:
            root_check = tk.Tk()
            root_check.withdraw()
            tkfont.Font(root=root_check, family="Inter")
            root_check.destroy()
            return "Inter"
        except Exception:
            return "Segoe UI"

_FONT_FAMILY = None  # Set after tk.Tk() is created

# ---------------------------------------------------------------------------
# Typography — Segoe UI default; updated by _apply_font() after font load
# ---------------------------------------------------------------------------
FONT_MAIN   = ("Segoe UI", 10)
FONT_BOLD   = ("Segoe UI", 10, "bold")
FONT_HEADER = ("Segoe UI", 15, "bold")
FONT_TITLE  = ("Segoe UI", 11, "bold")
FONT_SUB    = ("Segoe UI", 9)
FONT_SMALL  = ("Segoe UI", 8)
FONT_MONO   = ("Consolas", 9)

def _apply_font(family: str) -> None:
    """Update all FONT_* globals to use the loaded font family."""
    global FONT_MAIN, FONT_BOLD, FONT_HEADER, FONT_TITLE, FONT_SUB, FONT_SMALL
    FONT_MAIN   = (family, 10)
    FONT_BOLD   = (family, 10, "bold")
    FONT_HEADER = (family, 15, "bold")
    FONT_TITLE  = (family, 11, "bold")
    FONT_SUB    = (family, 9)
    FONT_SMALL  = (family, 8)
    # FONT_MONO intentionally stays Consolas for log boxes


def section_label(parent, text: str) -> tk.Frame:
    """Left red-accent bar + uppercase section heading."""
    frame = tk.Frame(parent, bg=PANEL_BG)
    tk.Frame(frame, bg=RED_ACCENT, width=3).pack(side="left", fill="y", padx=(0, 8))
    tk.Label(frame, text=text.upper(), bg=PANEL_BG,
             fg=NAVY_DARK, font=FONT_TITLE).pack(side="left", anchor="w")
    return frame


class RoundedButton(tk.Canvas):
    """
    Canvas-drawn button with rounded corners and consistent hover / active states.

    Use the module-level BTN_* style presets for visual hierarchy:
        RoundedButton(parent, text="Run",   command=fn, **BTN_PRIMARY,        font=FONT_BOLD)
        RoundedButton(parent, text="Clear", command=fn, **BTN_SECONDARY_STYLE, font=FONT_MAIN)
        RoundedButton(parent, text="Reset", command=fn, **BTN_DANGER,          font=FONT_MAIN)
        RoundedButton(parent, text="Done",  command=fn, **BTN_SUCCESS_STYLE,   font=FONT_BOLD)
        RoundedButton(parent, text="Skip",  command=fn, **BTN_MUTED_STYLE,     font=FONT_MAIN)
    """

    _DISABLED_COLOR = "#9aa3b0"

    def __init__(self, parent, text, command=None,
                 bg=NAVY_DARK, fg=WHITE, hover_bg=None,
                 font=None, padx=20, pady=9, radius=6, **kwargs):
        self._bg      = bg
        self._hover   = hover_bg or self._darken(bg)
        self._fg      = fg
        self._text    = text
        self._command = command
        self._radius  = radius
        self._font    = font or FONT_BOLD
        self._padx    = padx
        self._pady    = pady

        # Measure text to size the canvas correctly
        tmp = tk.Label(parent, text=text, font=self._font)
        tmp.update_idletasks()
        w = tmp.winfo_reqwidth() + padx * 2
        h = tmp.winfo_reqheight() + pady * 2
        tmp.destroy()

        super().__init__(parent, width=w, height=h,
                         bg=parent.cget("bg"),
                         highlightthickness=0, cursor="hand2", **kwargs)

        self._draw(self._bg)
        self._bind_active()

    # ── Drawing ────────────────────────────────────────────────────────────

    def _draw(self, color: str) -> None:
        self.delete("all")
        w, h, r = int(self["width"]), int(self["height"]), self._radius
        self.create_arc(0,     0,     r*2,   r*2,   start=90,  extent=90, fill=color, outline=color)
        self.create_arc(w-r*2, 0,     w,     r*2,   start=0,   extent=90, fill=color, outline=color)
        self.create_arc(0,     h-r*2, r*2,   h,     start=180, extent=90, fill=color, outline=color)
        self.create_arc(w-r*2, h-r*2, w,     h,     start=270, extent=90, fill=color, outline=color)
        self.create_rectangle(r, 0,   w-r,   h,     fill=color, outline=color)
        self.create_rectangle(0, r,   w,     h-r,   fill=color, outline=color)
        self.create_text(w//2, h//2, text=self._text, fill=self._fg,
                         font=self._font, anchor="center")

    # ── Interaction ────────────────────────────────────────────────────────

    def _on_press(self) -> None:
        self._draw(self._darken(self._hover))

    def _on_release(self) -> None:
        self._draw(self._hover)
        if self._command:
            self._command()

    # ── Event binding helpers ──────────────────────────────────────────────

    def _bind_active(self) -> None:
        self.bind("<Enter>",           lambda e: self._draw(self._hover))
        self.bind("<Leave>",           lambda e: self._draw(self._bg))
        self.bind("<Button-1>",        lambda e: self._on_press())
        self.bind("<ButtonRelease-1>", lambda e: self._on_release())

    def _unbind_active(self) -> None:
        for seq in ("<Enter>", "<Leave>", "<Button-1>", "<ButtonRelease-1>"):
            self.unbind(seq)

    # ── State management ───────────────────────────────────────────────────

    def config(self, **kwargs) -> None:
        if "state" in kwargs:
            if kwargs["state"] == "disabled":
                self._draw(self._DISABLED_COLOR)
                self._unbind_active()
                self.configure(cursor="")
            elif kwargs["state"] == "normal":
                self._draw(self._bg)
                self._bind_active()
                self.configure(cursor="hand2")
            remaining = {k: v for k, v in kwargs.items() if k != "state"}
        else:
            remaining = kwargs
        if remaining:
            super().config(**remaining)

    # ── Utilities ──────────────────────────────────────────────────────────

    @staticmethod
    def _darken(hex_color: str) -> str:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"#{max(0,r-25):02x}{max(0,g-25):02x}{max(0,b-25):02x}"


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
            width=48, relief="flat", bg="#ffffff",
            fg=TEXT_FG, insertbackground=NAVY,
            highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=NAVY,
        )
        entry.grid(row=0, column=1, padx=(0, 8), ipady=5)

        RoundedButton(
            self, text="Browse",
            command=lambda: self._browse(filetypes),
            **BTN_MUTED_STYLE, font=FONT_BOLD, padx=12, pady=5, radius=6,
        ).grid(row=0, column=2)

        if tooltip:
            tip = tk.Label(
                self, text=tooltip, bg=PANEL_BG, fg=TEXT_MUTED,
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
        self.geometry("900x780")
        self.minsize(800, 640)
        self.configure(bg=NAVY)
        self.resizable(True, True)

        self._processing = False
        # Load Inter font
        global _FONT_FAMILY
        _FONT_FAMILY = _load_inter_fonts()
        _apply_font(_FONT_FAMILY)

        self._processing = False
        self._midterm_processing = False
        self._trend_processing = False
        self._semester_mgr = SemesterManager()
        self._exclude_var = tk.BooleanVar(value=False)
        self._midterm_exclude_var = tk.BooleanVar(value=False)
        self._build_ui()
        self._set_defaults()
        self.after(200, self._check_semester_on_startup)
        self._report_processing = False

        logger.info("GUI initialized: %s v%s", APP_NAME, APP_VERSION)

    # ------------------------------------------------------------------
    # Scroll area helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_scrollable_tab(parent: tk.Widget, padx: int = 24, pady: int = 16):
        """
        Wrap a tab in a vertically scrollable canvas.

        Returns (inner_frame, activate_fn, deactivate_fn) where:
          inner_frame   — pack/grid content into this
          activate_fn   — call to enable mousewheel scroll (bind to canvas <Enter>)
          deactivate_fn — call to disable mousewheel scroll (bind to canvas <Leave>
                          and also to any ScrolledText <Enter> inside the tab)

        Usage:
            inner, on, off = self._make_scrollable_tab(tab)
            # ... build content inside inner ...
            self._log_box.bind("<Enter>", lambda e: off())
            self._log_box.bind("<Leave>", lambda e: on())
        """
        canvas = tk.Canvas(parent, bg=PANEL_BG, highlightthickness=0)
        vsb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=PANEL_BG, padx=padx, pady=pady)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _resize(e=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(win_id, width=canvas.winfo_width())

        inner.bind("<Configure>", _resize)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))

        def _wheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

        def activate(e=None):
            canvas.bind_all("<MouseWheel>", _wheel)

        def deactivate(e=None):
            canvas.unbind_all("<MouseWheel>")

        canvas.bind("<Enter>", activate)
        canvas.bind("<Leave>", deactivate)

        return inner, activate, deactivate

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        # ── Header banner ──────────────────────────────────────────
        header = tk.Frame(self, bg=NAVY)
        header.pack(fill="x")

        # Red accent top stripe
        tk.Frame(header, bg=RED_ACCENT, height=4).pack(fill="x")

        # Content row
        header_inner = tk.Frame(header, bg=NAVY_DARK, pady=14, padx=20)
        header_inner.pack(fill="x")

        # Left: App name
        tk.Label(
            header_inner, text=APP_NAME.upper(),
            bg=NAVY_DARK, fg=WHITE,
            font=(FONT_HEADER[0], 14, "bold"),
        ).pack(side="left")

        tk.Label(
            header_inner, text="  |  Academic Advising Intervention Workflow",
            bg=NAVY_DARK, fg="#A0B4CC",
            font=FONT_MAIN,
        ).pack(side="left")

        # Right: Version badge
        ver_frame = tk.Frame(header_inner, bg=RED_ACCENT, padx=8, pady=2)
        ver_frame.pack(side="right")
        tk.Label(
            ver_frame, text=f"v{APP_VERSION}",
            bg=RED_ACCENT, fg=NAVY_DARK,
            font=(FONT_MAIN[0], 9, "bold"),
        ).pack()

        # Red accent bottom stripe
        tk.Frame(header, bg=RED_ACCENT, height=2).pack(fill="x")

        # ── Notebook tabs ──────────────────────────────────────────
        style = ttk.Style()
        style.theme_use("clam")

        # Notebook container
        style.configure("TNotebook",
            background=NAVY,
            borderwidth=0,
            tabmargins=[2, 4, 0, 0],
        )
        # Inactive tabs
        style.configure("TNotebook.Tab",
            font=(FONT_BOLD[0], FONT_BOLD[1], "bold"),
            padding=[18, 8],
            background=NAVY_DARK,
            foreground="#A0B4CC",
            borderwidth=0,
        )
        # Active tab
        style.map("TNotebook.Tab",
            background=[("selected", PANEL_BG), ("active", NAVY_DARK)],
            foreground=[("selected", NAVY),     ("active", WHITE)],
            expand=[("selected", [1, 1, 1, 0])],
        )
        # Separator styling
        style.configure("TSeparator", background=BORDER)

        # Scrollbar
        style.configure("TScrollbar",
            background=PANEL_BG_DARK,
            troughcolor=PANEL_BG,
            borderwidth=0,
            arrowcolor=NAVY,
        )

        # Progressbar
        style.configure("TProgressbar",
            background=RED_ACCENT,
            troughcolor=PANEL_BG_DARK,
            borderwidth=0,
        )

        notebook = ttk.Notebook(self, style="TNotebook")
        notebook.pack(fill="both", expand=True, padx=0, pady=0)

        # Tab 1: Intervention Sorter
        tab1 = tk.Frame(notebook, bg=PANEL_BG)
        notebook.add(tab1, text="  Progress Report Sorter  ")

        # Tab 2: Faculty Report Status
        tab2 = tk.Frame(notebook, bg=PANEL_BG)
        notebook.add(tab2, text="  Faculty Report Status  ")

        # Tab 3: Midterm Sorter
        tab3 = tk.Frame(notebook, bg=PANEL_BG)
        notebook.add(tab3, text="  Midterm Sorter  ")
        self._midterm_tab = tab3

        # Tab 4: Campaign Trend
        tab4 = tk.Frame(notebook, bg=PANEL_BG)
        notebook.add(tab4, text="  Campaign Trend  ")
        self._trend_tab = tab4

        # Tab 5: Campaign Manager
        tab5 = tk.Frame(notebook, bg=PANEL_BG)
        notebook.add(tab5, text="  Campaigns  ")
        self._campaign_tab = tab5

        # Tab 6: Settings
        tab6 = tk.Frame(notebook, bg=PANEL_BG)
        notebook.add(tab6, text="  Settings  ")
        self._settings_tab = tab6

        # Tab 7: Help
        tab7 = tk.Frame(notebook, bg=PANEL_BG)
        notebook.add(tab7, text="  Help  ")
        self._help_tab = tab7

        content, _wheel_on, _wheel_off = self._make_scrollable_tab(tab1, padx=28, pady=18)

        # ── File pickers ───────────────────────────────────────────
        section_label(content, "Input Files").pack(fill="x", pady=(0, 10))

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

        # Exclude previously assigned checkbox
        chk_frame = tk.Frame(content, bg=PANEL_BG)
        chk_frame.pack(fill="x", pady=(8, 0))
        tk.Checkbutton(
            chk_frame,
            text="Exclude students already assigned in a previous run this campaign",
            variable=self._exclude_var,
            bg=PANEL_BG, fg=TEXT_FG,
            font=FONT_MAIN,
            activebackground=PANEL_BG,
            selectcolor="white",
            cursor="hand2",
        ).pack(side="left")
        tk.Label(
            chk_frame,
            text="(reads/writes assigned_students.txt in output folder)",
            bg=PANEL_BG, fg=TEXT_MUTED, font=FONT_SUB,
        ).pack(side="left", padx=(8, 0))

        ttk.Separator(content, orient="horizontal").pack(fill="x", pady=14)

        # ── Buttons ────────────────────────────────────────────────
        btn_frame = tk.Frame(content, bg=PANEL_BG)
        btn_frame.pack(fill="x")

        self._run_btn = RoundedButton(
            btn_frame, text='Run Full Processing',
            command=self._on_run,
            **BTN_PRIMARY, font=FONT_BOLD, padx=20, pady=9,
        )
        self._run_btn.pack(side="left", padx=(0, 10))

        self._validate_btn = RoundedButton(
            btn_frame, text='Validate Only',
            command=self._on_validate,
            **BTN_SECONDARY_STYLE, font=FONT_MAIN, padx=14, pady=8,
        )
        self._validate_btn.pack(side="left", padx=(0, 10))

        self._precheck_btn = RoundedButton(
            btn_frame, text='Pre-Run Check',
            command=self._on_prerun_check,
            **BTN_DANGER, font=FONT_MAIN, padx=14, pady=8,
        )
        self._precheck_btn.pack(side="left", padx=(0, 10))

        self._clear_btn = RoundedButton(
            btn_frame, text='Clear',
            command=self._on_clear,
            **BTN_SECONDARY_STYLE, font=FONT_MAIN, padx=14, pady=8,
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
        section_label(content, "Processing Log").pack(fill="x", pady=(10, 4))

        self._log_box = scrolledtext.ScrolledText(
            content, height=10, font=FONT_MONO,
            bg="#0A1628", fg="#C8D6E8",
            insertbackground="white",
            relief="flat",
            wrap="word",
        )
        self._log_box.pack(fill="both", expand=True)
        self._log_box.config(state="disabled")
        self._log_box.bind("<Enter>", _wheel_off)
        self._log_box.bind("<Leave>", _wheel_on)

        # Tag styles for log
        self._log_box.tag_config("success", foreground="#68D391")
        self._log_box.tag_config("error", foreground="#FC8181")
        self._log_box.tag_config("warning", foreground="#F6AD55")
        self._log_box.tag_config("info", foreground="#90CDF4")
        self._log_box.tag_config("step", foreground=RED_ACCENT)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _show_group_selection_dialog(
        self,
        control_path: str,
        group_dir: str,
        checkpoint_name: str,
    ) -> tuple:
        """
        Show a checklist of groups before a run.
        Returns (proceed: bool, skip_groups: set)

        Source priority:
          1. Active semester groups (if configured)
          2. Control file (fallback)
        """
        from processors.semester_manager import SemesterManager

        sm = SemesterManager()
        semester_groups = sm.get_groups()

        if semester_groups:
            # Use semester-configured groups — list of {name, file_path}
            groups = [(g["name"], Path(g["file_path"]).name if g["file_path"] else "")
                      for g in semester_groups]
        else:
            # Fall back to parsing the control file
            from processors.group_matcher import GroupMatcher
            from utils.logging_utils import QALog
            try:
                matcher = GroupMatcher(QALog())
                groups = matcher.read_group_names(Path(control_path))
            except Exception:
                return True, set()

        if not groups:
            return True, set()

        # Get previously saved selection
        sm = SemesterManager()
        saved_selection = sm.get_group_selection(checkpoint_name)
        # saved_selection is the list of SELECTED groups from last run

        dialog = tk.Toplevel(self)
        dialog.title(f"Select Groups — {checkpoint_name}")
        dialog.geometry("460x520")
        dialog.configure(bg=PANEL_BG)
        dialog.resizable(False, True)
        dialog.transient(self)
        dialog.grab_set()

        result = {"proceed": False, "skip_groups": set()}

        # Header
        tk.Label(dialog,
                 text=f"Select which groups to produce for this run.",
                 bg=PANEL_BG, fg=TEXT_FG, font=FONT_BOLD,
                 wraplength=420).pack(pady=(16, 2), padx=20, anchor="w")
        tk.Label(dialog,
                 text="Unchecked groups will be skipped — their students go to unmatched buckets.",
                 bg=PANEL_BG, fg=TEXT_MUTED, font=FONT_SUB,
                 wraplength=420).pack(padx=20, anchor="w")

        ttk.Separator(dialog, orient="horizontal").pack(fill="x", pady=8, padx=20)

        # Scrollable group list
        list_frame = tk.Frame(dialog, bg=PANEL_BG)
        list_frame.pack(fill="both", expand=True, padx=20)

        check_vars = {}
        for tab_name, filename in groups:
            var = tk.BooleanVar(value=(
                tab_name in saved_selection if saved_selection else True
            ))
            check_vars[tab_name] = var
            row = tk.Frame(list_frame, bg=PANEL_BG)
            row.pack(fill="x", pady=2)
            tk.Checkbutton(
                row, text=f"  {tab_name}",
                variable=var,
                bg=PANEL_BG, fg=TEXT_FG, font=FONT_BOLD,
                activebackground=PANEL_BG, selectcolor="white",
                cursor="hand2",
            ).pack(side="left")
            tk.Label(row, text=f"({filename})",
                     bg=PANEL_BG, fg=TEXT_MUTED, font=FONT_SUB).pack(side="left")

        ttk.Separator(dialog, orient="horizontal").pack(fill="x", pady=8, padx=20)

        # Unmatched buckets (always included, shown as info)
        tk.Label(dialog,
                 text="Risk_1_2 and Risk_3_Plus are always included",
                 bg=PANEL_BG, fg=TEXT_MUTED, font=FONT_SUB).pack(padx=20, anchor="w")

        ttk.Separator(dialog, orient="horizontal").pack(fill="x", pady=8, padx=20)

        # Select all / none shortcuts
        shortcut_frame = tk.Frame(dialog, bg=PANEL_BG)
        shortcut_frame.pack(fill="x", padx=20, pady=(0, 8))
        RoundedButton(shortcut_frame, text="Select All",
                      **BTN_MUTED_STYLE, font=FONT_SUB, padx=8, pady=4,
                      command=lambda: [v.set(True) for v in check_vars.values()]
                      ).pack(side="left", padx=(0, 6))
        RoundedButton(shortcut_frame, text="Select None",
                      **BTN_MUTED_STYLE, font=FONT_SUB, padx=8, pady=4,
                      command=lambda: [v.set(False) for v in check_vars.values()]
                      ).pack(side="left")

        # Action buttons
        bf = tk.Frame(dialog, bg=PANEL_BG)
        bf.pack(fill="x", padx=20, pady=(0, 16))

        def on_run():
            selected = [name for name, var in check_vars.items() if var.get()]
            skip = {name for name in check_vars if not check_vars[name].get()}
            if not selected:
                messagebox.showwarning("No Groups Selected",
                    "Please select at least one group, or cancel.",
                    parent=dialog)
                return
            # Save selection to semester
            sm = SemesterManager()
            if sm.has_active_semester():
                sm.save_group_selection(checkpoint_name, selected)
            result["proceed"] = True
            result["skip_groups"] = skip
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        RoundedButton(bf, text="Run with Selected Groups",
                      **BTN_PRIMARY, font=FONT_BOLD, padx=16, pady=8,
                      command=on_run).pack(side="left", padx=(0, 8))
        RoundedButton(bf, text="Cancel",
                      **BTN_MUTED_STYLE, font=FONT_MAIN, padx=12, pady=8,
                      command=on_cancel).pack(side="left")

        dialog.wait_window()
        return result["proceed"], result["skip_groups"]

    def _ensure_season_set(self) -> bool:
        """
        Check that a season name and checkpoint type are set.
        If not, show a prompt dialog and let the user fill them in.
        Returns True if ready to proceed, False if user cancelled.
        """
        if not hasattr(self, "_campaign_season_var"):
            return True

        season = self._campaign_season_var.get().strip()
        checkpoint = self._checkpoint_type_var.get().strip() if hasattr(self, "_checkpoint_type_var") else ""

        if season and checkpoint:
            return True

        # Show prompt dialog
        dialog = tk.Toplevel(self)
        dialog.title("Name This Campaign Run")
        dialog.geometry("480x280")
        dialog.configure(bg=PANEL_BG)
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        result = {"proceed": False}

        # Header
        tk.Label(
            dialog,
            text="Before running, please name this campaign.",
            bg=PANEL_BG, fg=TEXT_FG, font=FONT_BOLD,
            wraplength=440,
        ).pack(pady=(20, 4), padx=24, anchor="w")
        tk.Label(
            dialog,
            text="This keeps your run history organized by season.",
            bg=PANEL_BG, fg=TEXT_MUTED, font=FONT_SUB,
        ).pack(padx=24, anchor="w")

        # Season name field
        f1 = tk.Frame(dialog, bg=PANEL_BG)
        f1.pack(fill="x", padx=24, pady=(16, 6))
        tk.Label(f1, text="Season Name:", bg=PANEL_BG, fg=TEXT_FG,
                 font=FONT_MAIN, width=16, anchor="w").pack(side="left")
        season_var = tk.StringVar(value=season or "")
        tk.Entry(f1, textvariable=season_var, font=FONT_MAIN, width=28,
                 relief="flat", bg="white",
                 highlightthickness=1, highlightbackground="#B0BEC5",
                 insertbackground=TEXT_FG).pack(side="left", ipady=4)

        # Checkpoint type
        from utils.config import CHECKPOINT_TYPES
        f2 = tk.Frame(dialog, bg=PANEL_BG)
        f2.pack(fill="x", padx=24, pady=(0, 16))
        tk.Label(f2, text="Checkpoint:", bg=PANEL_BG, fg=TEXT_FG,
                 font=FONT_MAIN, width=16, anchor="w").pack(side="left")
        cp_var = tk.StringVar(value=checkpoint or CHECKPOINT_TYPES[0])
        for ct in CHECKPOINT_TYPES:
            tk.Radiobutton(
                f2, text=ct, variable=cp_var, value=ct,
                bg=PANEL_BG, fg=TEXT_FG, font=FONT_MAIN,
                activebackground=PANEL_BG, selectcolor="white",
            ).pack(side="left", padx=(0, 8))

        # Buttons
        bf = tk.Frame(dialog, bg=PANEL_BG)
        bf.pack(fill="x", padx=24, pady=(0, 20))

        def on_proceed():
            s = season_var.get().strip()
            if not s:
                tk.Label(dialog, text="Please enter a season name.",
                         bg=PANEL_BG, fg="#C62828", font=FONT_SUB).pack()
                return
            self._campaign_season_var.set(s)
            self._checkpoint_type_var.set(cp_var.get())
            result["proceed"] = True
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        RoundedButton(bf, text="Proceed",
                      **BTN_PRIMARY, font=FONT_BOLD, padx=16, pady=8,
                      command=on_proceed).pack(side="left", padx=(0, 8))
        RoundedButton(bf, text="Cancel",
                      **BTN_MUTED_STYLE, font=FONT_MAIN, padx=12, pady=8,
                      command=on_cancel).pack(side="left")

        dialog.wait_window()
        return result["proceed"]

    def _on_run(self):
        if self._processing:
            return
        if not self._ensure_season_set():
            return
        inputs = self._collect_inputs()
        if inputs is None:
            return
        # Group selection dialog
        if self._control_picker.path and self._group_dir_picker.path:
            checkpoint = (self._checkpoint_type_var.get()
                         if hasattr(self, "_checkpoint_type_var") else "Progress Report 1")
            proceed, skip_groups = self._show_group_selection_dialog(
                self._control_picker.path,
                self._group_dir_picker.path,
                checkpoint,
            )
            if not proceed:
                return
            inputs.skip_groups = skip_groups
        self._start_processing(inputs, validate_only=False)

    def _on_validate(self):
        if self._processing:
            return
        inputs = self._collect_inputs()
        if inputs is None:
            return
        self._start_processing(inputs, validate_only=True)

    def _on_prerun_check(self):
        """Run pre-flight data quality checks without a full pipeline run."""
        paths = {
            "Progress Report":  self._progress_picker.path,
            "Contact Report":   self._contact_picker.path,
            "Group Control":    self._control_picker.path,
            "Group Folder":     self._group_dir_picker.path,
        }
        missing = [k for k, v in paths.items() if not v]
        if missing:
            messagebox.showerror("Missing Files",
                "Please select files first:\n" + "\n".join(f"  • {m}" for m in missing))
            return

        self._log("=" * 55, "info")
        self._log("PRE-RUN DATA QUALITY CHECK", "step")
        self._log("=" * 55, "info")

        import threading
        def _worker():
            checker = PreRunChecker()
            all_results = []
            progress_ids = None

            # Check progress report
            self.after(0, self._log, "Checking progress report...", "step")
            pr_results = checker.check_progress_report(
                Path(paths["Progress Report"])
            )
            all_results.extend(pr_results)

            # Extract at-risk IDs for cross-checks
            try:
                from utils.settings_manager import get_settings
                from utils.normalization import normalize_student_id_series, normalize_at_risk_series
                import pandas as pd
                col = get_settings().progress_report_map
                df = pd.read_csv(paths["Progress Report"], dtype=str, keep_default_na=False) \
                    if paths["Progress Report"].endswith(".csv") \
                    else pd.read_excel(paths["Progress Report"], dtype=str,
                                       keep_default_na=False, engine="openpyxl")
                df.columns = [str(c).strip() for c in df.columns]
                if col["at_risk"] in df.columns and col["student_id"] in df.columns:
                    at_risk_mask = normalize_at_risk_series(df[col["at_risk"]])
                    progress_ids = set(
                        normalize_student_id_series(df[at_risk_mask][col["student_id"]])
                        .replace("", pd.NA).dropna()
                    )
            except Exception:
                pass

            # Check contact report
            self.after(0, self._log, "Checking contact report...", "step")
            cr_results = checker.check_contact_report(
                Path(paths["Contact Report"]), progress_ids
            )
            all_results.extend(cr_results)

            # Check group files
            self.after(0, self._log, "Checking group files...", "step")
            gf_results = checker.check_group_files(
                Path(paths["Group Control"]),
                Path(paths["Group Folder"]),
                progress_ids,
            )
            all_results.extend(gf_results)

            self.after(0, self._show_precheck_results, all_results)

        threading.Thread(target=_worker, daemon=True).start()

    def _show_precheck_results(self, results):
        """Display pre-run check results in the log and a summary popup."""
        errors   = [r for r in results if r.level == "error"]
        warnings = [r for r in results if r.level == "warning"]
        infos    = [r for r in results if r.level == "info"]

        for r in infos:
            self._log(f"  ℹ️  {r.message}", "info")
        for r in warnings:
            self._log(f"  ⚠️  {r.message}", "warning")
        for r in errors:
            self._log(f"  ❌  {r.message}", "error")

        if errors:
            self._log("\n❌ Pre-run check found errors — fix before running.", "error")
            messagebox.showerror("Pre-Run Check Failed",
                f"Found {len(errors)} error(s) and {len(warnings)} warning(s).\n\n"
                + "\n".join(f"❌ {r.message[:120]}" for r in errors[:5]))
        elif warnings:
            self._log(f"\n⚠️  Pre-run check passed with {len(warnings)} warning(s).", "warning")
            messagebox.showwarning("Pre-Run Check — Warnings",
                f"No errors found but {len(warnings)} warning(s):\n\n"
                + "\n".join(f"⚠️ {r.message[:120]}" for r in warnings[:5])
                + "\n\nYou can still run — check warnings in the log.")
        else:
            self._log("\n✅ Pre-run check passed — all files look good!", "success")
            messagebox.showinfo("Pre-Run Check Passed",
                "✅ All files validated successfully!\n\nReady to run.")

    def _on_clear(self):
        self._log_box.config(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.config(state="disabled")
        self._progress_var.set(0)
        self._progress_bar.stop()

    def _collect_inputs(self) -> PipelineInputs | None:
        """
        Gather file paths from pickers and validate they're not empty.

        When the active semester has groups configured, the control file and
        group folder are optional — semester groups take precedence.
        """
        semester_groups = SemesterManager().get_groups()
        using_semester_groups = bool(semester_groups)

        errors = []
        always_required = {
            "Progress Report": self._progress_picker.path,
            "Contact Report":  self._contact_picker.path,
            "Output Folder":   self._output_picker.path,
        }
        for label, val in always_required.items():
            if not val:
                errors.append(f"• {label} is required.")

        # Control file + group dir only required if no semester groups set
        if not using_semester_groups:
            if not self._control_picker.path:
                errors.append("• Group Control File is required (no semester groups configured).")
            if not self._group_dir_picker.path:
                errors.append("• Group Files Folder is required (no semester groups configured).")

        if errors:
            messagebox.showerror(
                "Missing Inputs",
                "Please provide all required files:\n\n" + "\n".join(errors),
            )
            return None

        season = self._campaign_season_var.get().strip() if hasattr(self, "_campaign_season_var") else ""
        checkpoint = self._checkpoint_type_var.get() if hasattr(self, "_checkpoint_type_var") else "Progress Report"

        # Provide dummy Paths for control_file/group_dir when not used
        control_file = Path(self._control_picker.path) if self._control_picker.path else Path(".")
        group_dir    = Path(self._group_dir_picker.path) if self._group_dir_picker.path else Path(".")

        return PipelineInputs(
            progress_report=Path(always_required["Progress Report"]),
            contact_report=Path(always_required["Contact Report"]),
            control_file=control_file,
            group_dir=group_dir,
            output_dir=Path(always_required["Output Folder"]),
            exclude_previous=self._exclude_var.get(),
            season=season,
            checkpoint_type=checkpoint,
            semester_groups=semester_groups if using_semester_groups else None,
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
                # Ask if they want to open the file
                if messagebox.askyesno(
                    "Processing Complete",
                    f"Processing completed successfully!\n\n"
                    f"Output file:\n{result.output_path}\n\n"
                    f"{result.message}\n\n"
                    f"Open the output file now?",
                ):
                    import subprocess, sys
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
        self._build_trend_tab()
        self._build_campaign_tab()
        self._build_settings_tab()
        self._build_help_tab()

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

        content2, _wheel_on2, _wheel_off2 = self._make_scrollable_tab(tab2)

        section_label(content2, "Input Files").pack(fill="x", pady=(0, 8))

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

        self._report_run_btn = RoundedButton(
            btn_frame2, text='Generate Faculty Report',
            command=self._on_run_report_status,
            **BTN_PRIMARY, font=FONT_BOLD, padx=20, pady=9,
        )
        self._report_run_btn.pack(side="left")

        self._report_progress_bar = ttk.Progressbar(
            content2, maximum=100, mode="indeterminate"
        )
        self._report_progress_bar.pack(fill="x", pady=(12, 0))

        section_label(content2, "Processing Log").pack(fill="x", pady=(12, 4))

        self._report_log_box = scrolledtext.ScrolledText(
            content2, height=14, font=FONT_MONO,
            bg="#0A1628", fg="#C8D6E8",
            relief="flat", wrap="word",
        )
        self._report_log_box.pack(fill="both", expand=True)
        self._report_log_box.config(state="disabled")
        self._report_log_box.bind("<Enter>", _wheel_off2)
        self._report_log_box.bind("<Leave>", _wheel_on2)
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
        outer, _wheel_on3, _wheel_off3 = self._make_scrollable_tab(tab)

        section_label(outer, "Input Files").pack(fill="x", pady=(0, 8))

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
            activebackground=PANEL_BG, selectcolor="#ffffff", cursor="hand2",
        ).pack(side="left")
        tk.Label(
            chk_frame, text="(reads/writes assigned_students.txt in output folder)",
            bg=PANEL_BG, fg=TEXT_MUTED, font=FONT_SUB,
        ).pack(side="left", padx=(8, 0))

        ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=14)

        # Buttons — pack BEFORE the log box so they're always visible
        btn_frame = tk.Frame(outer, bg=PANEL_BG)
        btn_frame.pack(fill="x", pady=(0, 8))

        self._midterm_run_btn = RoundedButton(
            btn_frame, text='Run Midterm Sort',
            command=self._on_run_midterm,
            **BTN_PRIMARY, font=FONT_BOLD, padx=20, pady=9,
        )
        self._midterm_run_btn.pack(side="left", padx=(0, 10))

        RoundedButton(
            btn_frame, text="Clear",
            **BTN_MUTED_STYLE, font=FONT_MAIN, padx=14, pady=9,
            command=self._midterm_clear_log,
        ).pack(side="left")

        self._midterm_progress_bar = ttk.Progressbar(
            outer, maximum=100, mode="indeterminate"
        )
        self._midterm_progress_bar.pack(fill="x", pady=(0, 8))

        section_label(outer, "Processing Log").pack(fill="x", pady=(4, 4))

        self._midterm_log_box = scrolledtext.ScrolledText(
            outer, height=10, font=FONT_MONO,
            bg="#0A1628", fg="#C8D6E8",
            relief="flat", wrap="word",
        )
        self._midterm_log_box.pack(fill="both", expand=True)
        self._midterm_log_box.config(state="disabled")
        self._midterm_log_box.bind("<Enter>", _wheel_off3)
        self._midterm_log_box.bind("<Leave>", _wheel_on3)
        self._midterm_log_box.tag_config("success", foreground="#4CAF50")
        self._midterm_log_box.tag_config("error",   foreground="#F44336")
        self._midterm_log_box.tag_config("warning", foreground="#FF9800")
        self._midterm_log_box.tag_config("info",    foreground="#90CAF9")
        self._midterm_log_box.tag_config("step",    foreground="#CE93D8")

    def _on_run_midterm(self):
        if self._midterm_processing:
            return
        if not self._ensure_season_set():
            return

        semester_groups = SemesterManager().get_groups()
        using_semester_groups = bool(semester_groups)

        errors = []
        always_required = {
            "Midterm Grade File": self._midterm_file_picker.path,
            "Contact Report":     self._midterm_contact_picker.path,
            "Output Folder":      self._midterm_output_picker.path,
        }
        for label, val in always_required.items():
            if not val:
                errors.append(f"  {label} is required.")
        if not using_semester_groups:
            if not self._midterm_control_picker.path:
                errors.append("  Group Control File is required (no semester groups configured).")
            if not self._midterm_group_dir_picker.path:
                errors.append("  Group Files Folder is required (no semester groups configured).")
        if errors:
            messagebox.showerror(
                "Missing Inputs",
                "Please provide all required files:\n\n" + "\n".join(errors)
            )
            return

        season = self._campaign_season_var.get().strip() if hasattr(self, "_campaign_season_var") else ""
        control_file = Path(self._midterm_control_picker.path) if self._midterm_control_picker.path else Path(".")
        group_dir    = Path(self._midterm_group_dir_picker.path) if self._midterm_group_dir_picker.path else Path(".")

        inputs = MidtermPipelineInputs(
            midterm_file=Path(always_required["Midterm Grade File"]),
            contact_report=Path(always_required["Contact Report"]),
            control_file=control_file,
            group_dir=group_dir,
            output_dir=Path(always_required["Output Folder"]),
            exclude_previous=self._midterm_exclude_var.get(),
            season=season,
            checkpoint_type="Midterm",
            semester_groups=semester_groups if using_semester_groups else None,
        )

        # Group selection dialog — always show so user can pick which groups to produce
        proceed, skip_groups = self._show_group_selection_dialog(
            self._midterm_control_picker.path,
            self._midterm_group_dir_picker.path,
            "Midterm",
        )
        if not proceed:
            return
        inputs.skip_groups = skip_groups

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
        self._trend_processing = False
        self._semester_mgr = SemesterManager()
        self._midterm_run_btn.config(state="normal")
        self._midterm_progress_bar.stop()
        if result.success:
            self._midterm_log_write("\n\u2705 " + result.message, "success")
            self._midterm_log_write("\U0001f4c1 Output: " + str(result.output_path), "success")
            if hasattr(self, '_refresh_campaign_tab'): self._refresh_campaign_tab()
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
        self._trend_processing = False
        self._semester_mgr = SemesterManager()
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


    def _build_trend_tab(self):
        """Build the Campaign Trend Report tab."""
        outer, _wheel_on4, _wheel_off4 = self._make_scrollable_tab(self._trend_tab)

        # Description
        tk.Label(
            outer,
            text="Select your three output workbooks in order to analyze how the "
                 "at-risk population moved across the semester cycle.",
            bg=PANEL_BG, fg=TEXT_MUTED, font=FONT_SUB,
            wraplength=700, justify="left",
        ).pack(anchor="w", pady=(0, 12))

        section_label(outer, "Select Output Workbooks").pack(fill="x", pady=(0, 8))

        pf = tk.Frame(outer, bg=PANEL_BG)
        pf.pack(fill="x")

        self._trend_pr1_picker = FilePickerRow(
            pf, label="Progress Report 1:",
            filetypes=[("Excel Files", "*.xlsx"), ("All Files", "*.*")],
            tooltip="First progress report output (InterventionSort_...xlsx)",
        )
        self._trend_pr1_picker.pack(fill="x", pady=4)

        self._trend_mid_picker = FilePickerRow(
            pf, label="Midterm:",
            filetypes=[("Excel Files", "*.xlsx"), ("All Files", "*.*")],
            tooltip="Midterm sort output (MidtermSort_...xlsx)",
        )
        self._trend_mid_picker.pack(fill="x", pady=4)

        self._trend_pr2_picker = FilePickerRow(
            pf, label="Progress Report 2:",
            filetypes=[("Excel Files", "*.xlsx"), ("All Files", "*.*")],
            tooltip="Second progress report output (InterventionSort_...xlsx)",
        )
        self._trend_pr2_picker.pack(fill="x", pady=4)

        self._trend_output_picker = FilePickerRow(
            pf, label="Output Folder:",
            filetypes=[], is_directory=True,
            tooltip="Where the trend report will be saved",
        )
        self._trend_output_picker.pack(fill="x", pady=4)
        self._trend_output_picker.path = str(OUTPUT_DIR)

        # Optional labels
        lbl_frame = tk.Frame(outer, bg=PANEL_BG)
        lbl_frame.pack(fill="x", pady=(8, 0))
        tk.Label(lbl_frame, text="Optional — customize checkpoint labels in the report:",
                 bg=PANEL_BG, fg=TEXT_MUTED, font=FONT_SUB).pack(anchor="w")

        name_row = tk.Frame(outer, bg=PANEL_BG)
        name_row.pack(fill="x", pady=4)
        for i, (label, default, attr) in enumerate([
            ("PR1 Label:",     "Progress Report 1", "_trend_pr1_label"),
            ("Midterm Label:", "Midterm",            "_trend_mid_label"),
            ("PR2 Label:",     "Progress Report 2", "_trend_pr2_label"),
        ]):
            tk.Label(name_row, text=label, bg=PANEL_BG, fg=TEXT_FG,
                     font=FONT_MAIN, width=14, anchor="w").grid(row=0, column=i*2, padx=(0,4))
            var = tk.StringVar(value=default)
            setattr(self, attr, var)
            tk.Entry(name_row, textvariable=var, font=FONT_MAIN, width=22,
                     relief="flat", bg="white",
                     highlightthickness=1, highlightbackground="#B0BEC5",
                     insertbackground=TEXT_FG).grid(row=0, column=i*2+1, padx=(0,16), ipady=3)

        ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=14)

        btn_frame = tk.Frame(outer, bg=PANEL_BG)
        btn_frame.pack(fill="x", pady=(0, 8))

        self._trend_run_btn = RoundedButton(
            btn_frame, text='Generate Trend Report',
            command=self._on_run_trend,
            **BTN_PRIMARY, font=FONT_BOLD, padx=20, pady=9,
        )
        self._trend_run_btn.pack(side="left", padx=(0, 10))

        RoundedButton(
            btn_frame, text="Clear",
            **BTN_MUTED_STYLE, font=FONT_MAIN, padx=14, pady=9,
            command=self._trend_clear_log,
        ).pack(side="left")

        self._trend_progress_bar = ttk.Progressbar(
            outer, maximum=100, mode="indeterminate"
        )
        self._trend_progress_bar.pack(fill="x", pady=(0, 8))

        ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=10)

        # Master Season Report section
        section_label(outer, "End-of-Semester Master Report").pack(fill="x", pady=(0, 6))
        tk.Label(
            outer,
            text="Select the three output workbooks from this semester to generate "
                 "a combined master report with student list and season summary.",
            bg=PANEL_BG, fg=TEXT_MUTED, font=FONT_SUB, wraplength=700, justify="left",
        ).pack(anchor="w", pady=(0, 8))

        mf = tk.Frame(outer, bg=PANEL_BG)
        mf.pack(fill="x")

        self._master_pr1_picker = FilePickerRow(
            mf, label="Progress Report 1:",
            filetypes=[("Excel Files", "*.xlsx"), ("All Files", "*.*")],
            tooltip="PR1 output workbook (ProgressReport_...xlsx)",
        )
        self._master_pr1_picker.pack(fill="x", pady=3)

        self._master_mid_picker = FilePickerRow(
            mf, label="Midterm:",
            filetypes=[("Excel Files", "*.xlsx"), ("All Files", "*.*")],
            tooltip="Midterm output workbook (MidtermSort_...xlsx)",
        )
        self._master_mid_picker.pack(fill="x", pady=3)

        self._master_pr2_picker = FilePickerRow(
            mf, label="Progress Report 2:",
            filetypes=[("Excel Files", "*.xlsx"), ("All Files", "*.*")],
            tooltip="PR2 output workbook (ProgressReport_...xlsx)",
        )
        self._master_pr2_picker.pack(fill="x", pady=3)

        self._master_output_picker = FilePickerRow(
            mf, label="Output Folder:",
            filetypes=[], is_directory=True,
            tooltip="Where the master report will be saved",
        )
        self._master_output_picker.pack(fill="x", pady=3)
        self._master_output_picker.path = str(OUTPUT_DIR)

        master_btn_frame = tk.Frame(outer, bg=PANEL_BG)
        master_btn_frame.pack(fill="x", pady=(10, 0))

        RoundedButton(
            master_btn_frame, text="Generate Master Season Report",
            command=self._on_generate_master_report,
            **BTN_SUCCESS_STYLE, font=FONT_BOLD, padx=20, pady=9,
        ).pack(side="left")

        ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=10)

        section_label(outer, "Processing Log").pack(fill="x", pady=(4, 4))

        self._trend_log_box = scrolledtext.ScrolledText(
            outer, height=8, font=FONT_MONO,
            bg="#0A1628", fg="#C8D6E8",
            relief="flat", wrap="word",
        )
        self._trend_log_box.pack(fill="both", expand=True)
        self._trend_log_box.config(state="disabled")
        self._trend_log_box.bind("<Enter>", _wheel_off4)
        self._trend_log_box.bind("<Leave>", _wheel_on4)
        self._trend_log_box.tag_config("success", foreground="#4CAF50")
        self._trend_log_box.tag_config("error",   foreground="#F44336")
        self._trend_log_box.tag_config("info",    foreground="#90CAF9")
        self._trend_log_box.tag_config("step",    foreground="#CE93D8")

    def _on_run_trend(self):
        if self._trend_processing:
            return

        paths = {
            "PR1":    self._trend_pr1_picker.path,
            "Mid":    self._trend_mid_picker.path,
            "PR2":    self._trend_pr2_picker.path,
            "Output": self._trend_output_picker.path,
        }

        # At least one workbook required; output always required
        if not any([paths["PR1"], paths["Mid"], paths["PR2"]]):
            messagebox.showerror("Missing Input",
                "Please select at least one output workbook.")
            return
        if not paths["Output"]:
            messagebox.showerror("Missing Input", "Please select an output folder.")
            return

        self._trend_processing = True
        self._trend_run_btn.config(state="disabled")
        self._trend_progress_bar.start(12)
        self._trend_log_write("=" * 55, "info")
        self._trend_log_write("GENERATING CAMPAIGN TREND REPORT", "step")
        self._trend_log_write("=" * 55, "info")

        pr1_path  = Path(paths["PR1"])  if paths["PR1"]  else None
        mid_path  = Path(paths["Mid"])  if paths["Mid"]  else None
        pr2_path  = Path(paths["PR2"])  if paths["PR2"]  else None
        out_dir   = Path(paths["Output"])
        pr1_label = self._trend_pr1_label.get().strip() or "PR1"
        mid_label = self._trend_mid_label.get().strip() or "Midterm"
        pr2_label = self._trend_pr2_label.get().strip() or "PR2"

        import threading
        def _worker():
            try:
                from datetime import datetime
                from utils.config import TREND_OUTPUT_FILENAME_PATTERN, LOG_DATE_FORMAT
                timestamp = datetime.now().strftime(LOG_DATE_FORMAT)
                out_path  = out_dir / TREND_OUTPUT_FILENAME_PATTERN.format(timestamp=timestamp)
                out_dir.mkdir(parents=True, exist_ok=True)

                self.after(0, self._trend_log_write, "Loading workbooks...", "step")
                analyzer = TrendAnalyzer()
                analyzer.load(pr1_path, mid_path, pr2_path)

                overall = analyzer.overall_stats()
                self.after(0, self._trend_log_write,
                    f"Total unique at-risk students: {overall['total_unique_students']:,}", "info")
                if pr1_path:
                    self.after(0, self._trend_log_write,
                        f"{pr1_label}: {overall['pr1_count']:,} students", "info")
                if mid_path:
                    self.after(0, self._trend_log_write,
                        f"{mid_label}: {overall['mid_count']:,} students", "info")
                if pr2_path:
                    self.after(0, self._trend_log_write,
                        f"{pr2_label}: {overall['pr2_count']:,} students", "info")

                self.after(0, self._trend_log_write, "Building report with charts...", "step")
                exporter = TrendExporter()
                exporter.export(analyzer, out_path, pr1_label, mid_label, pr2_label)

                self.after(0, self._on_trend_complete, True, str(out_path), overall)
            except Exception:
                import traceback
                self.after(0, self._on_trend_complete, False, traceback.format_exc(), {})

        threading.Thread(target=_worker, daemon=True).start()

    def _on_generate_master_report(self):
        """Generate the end-of-semester master season report."""
        out_dir = self._master_output_picker.path
        if not out_dir:
            messagebox.showerror("Missing Input", "Please select an output folder.")
            return

        paths = {
            "pr1": self._master_pr1_picker.path,
            "mid": self._master_mid_picker.path,
            "pr2": self._master_pr2_picker.path,
        }
        if not any(paths.values()):
            messagebox.showerror("Missing Input",
                "Please select at least one output workbook.")
            return

        season = self._campaign_season_var.get().strip() if hasattr(self, "_campaign_season_var") else ""
        pr1_label = self._trend_pr1_label.get().strip() or "Progress Report 1"
        mid_label = self._trend_mid_label.get().strip() or "Midterm"
        pr2_label = self._trend_pr2_label.get().strip() or "Progress Report 2"

        self._trend_log_write("=" * 55, "info")
        self._trend_log_write("GENERATING MASTER SEASON REPORT", "step")
        self._trend_log_write("=" * 55, "info")

        import threading
        def _worker():
            try:
                from datetime import datetime
                from utils.config import LOG_DATE_FORMAT
                timestamp = datetime.now().strftime(LOG_DATE_FORMAT)
                season_label = season.replace(" ", "_") if season else "Season"
                out_path = Path(out_dir) / f"MasterReport_{season_label}_{timestamp}.xlsx"
                Path(out_dir).mkdir(parents=True, exist_ok=True)

                self.after(0, self._trend_log_write, "Loading output workbooks...", "step")
                gen = SeasonReportGenerator()
                gen.generate(
                    pr1_path=Path(paths["pr1"]) if paths["pr1"] else None,
                    mid_path=Path(paths["mid"]) if paths["mid"] else None,
                    pr2_path=Path(paths["pr2"]) if paths["pr2"] else None,
                    output_path=out_path,
                    season_name=season,
                    pr1_label=pr1_label,
                    mid_label=mid_label,
                    pr2_label=pr2_label,
                )
                self.after(0, self._on_master_report_done, True, str(out_path))
            except Exception:
                import traceback
                self.after(0, self._on_master_report_done, False, traceback.format_exc())

        threading.Thread(target=_worker, daemon=True).start()

    def _on_master_report_done(self, success, message):
        if success:
            self._trend_log_write("\n\u2705 Master report generated!", "success")
            self._trend_log_write("\U0001f4c1 Output: " + message, "success")
            messagebox.showinfo("Master Report Complete",
                "\u2705 Master Season Report generated!\n\nOutput:\n" + message)
        else:
            self._trend_log_write("\n\u274c Failed:\n" + message[:400], "error")
            messagebox.showerror("Master Report Failed",
                "\u274c Failed to generate report:\n\n" + message[:400])

    def _on_trend_complete(self, success, message, overall):
        self._trend_processing = False
        self._semester_mgr = SemesterManager()
        self._trend_run_btn.config(state="normal")
        self._trend_progress_bar.stop()
        if success:
            self._trend_log_write("\n\u2705 Report generated!", "success")
            self._trend_log_write("\U0001f4c1 Output: " + message, "success")
            messagebox.showinfo(
                "Trend Report Complete",
                "\u2705 Campaign Trend Report generated!\n\n"
                f"Total unique students: {overall.get('total_unique_students', 0):,}\n"
                f"Output:\n{message}",
            )
        else:
            self._trend_log_write("\n\u274c Failed:\n" + message[:400], "error")
            messagebox.showerror("Trend Report Failed",
                "\u274c Report generation failed:\n\n" + message[:500])

    def _trend_clear_log(self):
        self._trend_log_box.config(state="normal")
        self._trend_log_box.delete("1.0", "end")
        self._trend_log_box.config(state="disabled")

    def _trend_log_write(self, message, tag="info"):
        self._trend_log_box.config(state="normal")
        self._trend_log_box.insert("end", message + "\n", tag)
        self._trend_log_box.see("end")
        self._trend_log_box.config(state="disabled")


    def _build_campaign_tab(self):
        """Build the redesigned Campaigns / Semester Manager tab."""
        tab = self._campaign_tab
        outer, _wheel_on5, _wheel_off5 = self._make_scrollable_tab(tab)

        # ── Active semester header ────────────────────────────────
        self._sem_header_frame = tk.Frame(outer, bg=PANEL_BG)
        self._sem_header_frame.pack(fill="x", pady=(0, 12))

        self._sem_name_label = tk.Label(
            self._sem_header_frame, text="No Active Semester",
            bg=PANEL_BG, fg=TEXT_FG, font=FONT_HEADER,
        )
        self._sem_name_label.pack(side="left")

        self._sem_status_label = tk.Label(
            self._sem_header_frame, text="",
            bg=PANEL_BG, fg=TEXT_MUTED, font=FONT_MAIN,
        )
        self._sem_status_label.pack(side="left", padx=(12, 0))

        ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=(0, 12))

        # ── Checkpoint cards ──────────────────────────────────────
        section_label(outer, "Checkpoints").pack(fill="x", pady=(0, 8))

        self._checkpoint_frames = {}
        cards_frame = tk.Frame(outer, bg=PANEL_BG)
        cards_frame.pack(fill="x", pady=(0, 12))

        from utils.config import SEMESTER_CHECKPOINTS
        colors = [NAVY, "#1A6B3C", "#9B2226"]
        for i, cp_name in enumerate(SEMESTER_CHECKPOINTS):
            card = tk.Frame(cards_frame, bg="#ffffff", bd=1, relief="solid",
                            padx=16, pady=12)

            card.grid(row=0, column=i, padx=(0, 12), sticky="nsew")
            cards_frame.columnconfigure(i, weight=1)

            tk.Label(card, text=cp_name, bg="white", fg=TEXT_FG,
                     font=FONT_BOLD).pack(anchor="w")

            status_lbl = tk.Label(card, text="Not Started", bg="white",
                                  fg=TEXT_MUTED, font=FONT_MAIN)
            status_lbl.pack(anchor="w", pady=(4, 0))

            runs_lbl = tk.Label(card, text="", bg="white",
                                fg=TEXT_MUTED, font=FONT_SUB)
            runs_lbl.pack(anchor="w")

            students_lbl = tk.Label(card, text="", bg="white",
                                    fg=TEXT_MUTED, font=FONT_SUB)
            students_lbl.pack(anchor="w")

            # Mark Complete / Reset buttons
            btn_frame = tk.Frame(card, bg="white")
            btn_frame.pack(anchor="w", pady=(8, 0))

            complete_btn = RoundedButton(
                btn_frame, text="Mark Complete",
                bg=colors[i], fg=WHITE, font=FONT_SUB, padx=8, pady=4,
                command=lambda n=cp_name: self._on_mark_checkpoint_complete(n),
            )
            complete_btn.pack(side="left", padx=(0, 6))

            reset_btn = RoundedButton(
                btn_frame, text="Reset",
                **BTN_MUTED_STYLE, font=FONT_SUB, padx=8, pady=4,
                command=lambda n=cp_name: self._on_reset_checkpoint(n),
            )
            reset_btn.pack(side="left")

            self._checkpoint_frames[cp_name] = {
                "card": card,
                "status": status_lbl,
                "runs": runs_lbl,
                "students": students_lbl,
                "complete_btn": complete_btn,
                "reset_btn": reset_btn,
                "color": colors[i],
            }

        ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=12)

        # ── Group configuration ───────────────────────────────────
        grp_header = tk.Frame(outer, bg=PANEL_BG)
        grp_header.pack(fill="x", pady=(0, 6))
        section_label(grp_header, "Groups").pack(side="left")
        tk.Label(
            grp_header,
            text="Priority order — first match wins each run",
            bg=PANEL_BG, fg=TEXT_MUTED, font=FONT_SUB,
        ).pack(side="left", padx=(12, 0))

        # Scrollable group list container
        self._groups_list_frame = tk.Frame(outer, bg=PANEL_BG)
        self._groups_list_frame.pack(fill="x")

        # Empty-state label shown when no groups are configured
        self._groups_empty_lbl = tk.Label(
            self._groups_list_frame,
            text="No groups configured — add groups below or use a control file.",
            bg=PANEL_BG, fg=TEXT_MUTED, font=FONT_SUB,
        )
        self._groups_empty_lbl.pack(anchor="w", pady=(4, 8))

        # Buttons below the list
        grp_btn_frame = tk.Frame(outer, bg=PANEL_BG)
        grp_btn_frame.pack(fill="x", pady=(6, 0))

        RoundedButton(
            grp_btn_frame, text="+ Add Group",
            **BTN_PRIMARY, font=FONT_BOLD, padx=14, pady=7,
            command=self._on_add_group,
        ).pack(side="left", padx=(0, 8))

        RoundedButton(
            grp_btn_frame, text="Copy from Previous Semester",
            **BTN_MUTED_STYLE, font=FONT_MAIN, padx=12, pady=7,
            command=self._on_copy_previous_groups,
        ).pack(side="left")

        ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=12)

        # ── Semester actions ──────────────────────────────────────
        section_label(outer, "Semester Actions").pack(fill="x", pady=(0, 8))

        action_frame = tk.Frame(outer, bg=PANEL_BG)
        action_frame.pack(fill="x", pady=(0, 12))

        self._new_sem_btn = RoundedButton(
            action_frame, text='Start New Semester',
            command=self._on_new_semester,
            **BTN_PRIMARY, font=FONT_BOLD, padx=16, pady=9,
        )
        self._new_sem_btn.pack(side="left", padx=(0, 8))

        self._complete_sem_btn = RoundedButton(
            action_frame, text='Complete Semester',
            command=self._on_complete_semester,
            **BTN_SUCCESS_STYLE, font=FONT_MAIN, padx=14, pady=8,
        )
        self._complete_sem_btn.pack(side="left", padx=(0, 8))

        self._reset_sem_btn = RoundedButton(
            action_frame, text='Reset Semester',
            command=self._on_reset_semester,
            **BTN_DANGER, font=FONT_MAIN, padx=14, pady=8,
        )
        self._reset_sem_btn.pack(side="left", padx=(0, 8))

        RoundedButton(
            action_frame, text="Refresh",
            **BTN_MUTED_STYLE, font=FONT_MAIN, padx=14, pady=9,
            command=self._refresh_semester_tab,
        ).pack(side="left")

        ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=12)

        # ── History ───────────────────────────────────────────────
        section_label(outer, "Semester History").pack(fill="x", pady=(0, 6))

        hist_frame = tk.Frame(outer, bg=PANEL_BG)
        hist_frame.pack(fill="both", expand=True)

        cols = ("Semester", "Status", "Created", "Completed",
                "PR1", "Midterm", "PR2", "Master Report")
        self._history_tree = ttk.Treeview(
            hist_frame, columns=cols, show="headings", height=8
        )
        widths = [160, 90, 150, 150, 90, 90, 90, 200]
        for col, w in zip(cols, widths):
            self._history_tree.heading(col, text=col)
            self._history_tree.column(col, width=w, anchor="center")
        self._history_tree.column("Semester", anchor="w")
        self._history_tree.column("Master Report", anchor="w")

        vsb = ttk.Scrollbar(hist_frame, orient="vertical",
                             command=self._history_tree.yview)
        self._history_tree.configure(yscrollcommand=vsb.set)
        self._history_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._history_tree.bind("<Enter>", _wheel_off5)
        self._history_tree.bind("<Leave>", _wheel_on5)

        # Initial refresh
        self._refresh_semester_tab()

    # ------------------------------------------------------------------
    # Semester tab methods
    # ------------------------------------------------------------------

    # ── Group list UI helpers ──────────────────────────────────────

    def _rebuild_groups_list(self) -> None:
        """Redraw the group list rows from the active semester's group data."""
        # Destroy existing rows (skip the empty label widget)
        for widget in self._groups_list_frame.winfo_children():
            if widget is not self._groups_empty_lbl:
                widget.destroy()

        groups = SemesterManager().get_groups()

        if not groups:
            self._groups_empty_lbl.pack(anchor="w", pady=(4, 8))
            return

        self._groups_empty_lbl.pack_forget()

        # Column header
        hdr = tk.Frame(self._groups_list_frame, bg=PANEL_BG_DARK)
        hdr.pack(fill="x", pady=(0, 2))
        for text, w in [("#", 3), ("Group Name", 18), ("File Path", 0)]:
            tk.Label(hdr, text=text, bg=PANEL_BG_DARK, fg=TEXT_MUTED,
                     font=FONT_SUB, width=w, anchor="w",
                     padx=6).pack(side="left")
        tk.Label(hdr, text="Actions", bg=PANEL_BG_DARK, fg=TEXT_MUTED,
                 font=FONT_SUB, width=14, anchor="e", padx=6).pack(side="right")

        for i, group in enumerate(groups):
            row = tk.Frame(self._groups_list_frame,
                           bg=WHITE if i % 2 == 0 else PANEL_BG,
                           pady=4, padx=6)
            row.pack(fill="x")

            # Priority number
            tk.Label(row, text=str(i + 1), bg=row.cget("bg"),
                     fg=TEXT_MUTED, font=FONT_SUB, width=3).pack(side="left")

            # Group name (editable label)
            tk.Label(row, text=group["name"], bg=row.cget("bg"),
                     fg=TEXT_FG, font=FONT_BOLD, width=18,
                     anchor="w").pack(side="left")

            # File path — truncated, clickable to re-browse
            path_str = group["file_path"]
            display = (Path(path_str).name if path_str
                       else "⚠  No file selected")
            path_color = TEXT_FG if path_str else RED_ACCENT
            path_lbl = tk.Label(row, text=display, bg=row.cget("bg"),
                                fg=path_color, font=FONT_MAIN,
                                anchor="w", cursor="hand2")
            path_lbl.pack(side="left", fill="x", expand=True)
            path_lbl.bind("<Button-1>",
                          lambda e, idx=i: self._on_browse_group_file(idx))

            # Action buttons
            action_frame = tk.Frame(row, bg=row.cget("bg"))
            action_frame.pack(side="right")

            if i > 0:
                RoundedButton(action_frame, text="▲",
                              **BTN_MUTED_STYLE, font=FONT_SUB, padx=6, pady=2,
                              command=lambda idx=i: self._on_move_group(idx, -1),
                              ).pack(side="left", padx=(0, 2))
            else:
                tk.Frame(action_frame, bg=row.cget("bg"), width=32).pack(side="left", padx=(0,2))

            if i < len(groups) - 1:
                RoundedButton(action_frame, text="▼",
                              **BTN_MUTED_STYLE, font=FONT_SUB, padx=6, pady=2,
                              command=lambda idx=i: self._on_move_group(idx, 1),
                              ).pack(side="left", padx=(0, 6))
            else:
                tk.Frame(action_frame, bg=row.cget("bg"), width=32).pack(side="left", padx=(0,6))

            RoundedButton(action_frame, text="✕",
                          **BTN_DANGER, font=FONT_SUB, padx=6, pady=2,
                          command=lambda idx=i: self._on_delete_group(idx),
                          ).pack(side="left")

    def _save_and_refresh_groups(self, groups: list) -> None:
        """Persist group list to the active semester and rebuild the UI."""
        sm = SemesterManager()
        if sm.has_active_semester():
            sm.set_groups(groups)
        self._rebuild_groups_list()

    # ── Group actions ──────────────────────────────────────────────

    def _on_add_group(self) -> None:
        """Open the Add Group dialog."""
        sm = SemesterManager()
        if not sm.has_active_semester():
            messagebox.showwarning("No Active Semester",
                                   "Start a semester before adding groups.")
            return

        dialog = tk.Toplevel(self)
        dialog.title("Add Group")
        dialog.geometry("500x200")
        dialog.configure(bg=PANEL_BG)
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        tk.Label(dialog, text="Group Name:", bg=PANEL_BG, fg=TEXT_FG,
                 font=FONT_BOLD).pack(anchor="w", padx=24, pady=(20, 4))

        name_var = tk.StringVar()
        name_entry = tk.Entry(dialog, textvariable=name_var, font=FONT_MAIN,
                              width=38, relief="flat", bg=WHITE,
                              highlightthickness=1, highlightbackground=BORDER,
                              highlightcolor=NAVY_DARK, insertbackground=NAVY_DARK)
        name_entry.pack(anchor="w", padx=24, ipady=4)
        name_entry.focus()

        file_var = tk.StringVar()
        file_frame = tk.Frame(dialog, bg=PANEL_BG)
        file_frame.pack(fill="x", padx=24, pady=(10, 0))
        tk.Label(file_frame, text="Group File (.xlsx):", bg=PANEL_BG,
                 fg=TEXT_FG, font=FONT_BOLD).pack(anchor="w")
        pick_row = tk.Frame(file_frame, bg=PANEL_BG)
        pick_row.pack(fill="x", pady=(4, 0))
        file_entry = tk.Entry(pick_row, textvariable=file_var, font=FONT_MAIN,
                              width=36, relief="flat", bg=WHITE,
                              highlightthickness=1, highlightbackground=BORDER)
        file_entry.pack(side="left", ipady=4, padx=(0, 8))
        RoundedButton(pick_row, text="Browse",
                      **BTN_MUTED_STYLE, font=FONT_BOLD, padx=10, pady=4,
                      command=lambda: file_var.set(
                          filedialog.askopenfilename(
                              filetypes=[("Excel Files", "*.xlsx *.xls"),
                                         ("All Files", "*.*")]) or file_var.get()
                      )).pack(side="left")

        err_lbl = tk.Label(dialog, text="", bg=PANEL_BG,
                           fg=RED_ACCENT, font=FONT_SUB)
        err_lbl.pack(anchor="w", padx=24)

        bf = tk.Frame(dialog, bg=PANEL_BG)
        bf.pack(fill="x", padx=24, pady=(8, 16))

        def on_add():
            name = name_var.get().strip()
            if not name:
                err_lbl.config(text="Please enter a group name.")
                return
            groups = SemesterManager().get_groups()
            if any(g["name"].lower() == name.lower() for g in groups):
                err_lbl.config(text=f"A group named '{name}' already exists.")
                return
            groups.append({"name": name, "file_path": file_var.get().strip()})
            self._save_and_refresh_groups(groups)
            dialog.destroy()

        RoundedButton(bf, text="Add Group",
                      **BTN_PRIMARY, font=FONT_BOLD, padx=16, pady=8,
                      command=on_add).pack(side="left", padx=(0, 8))
        RoundedButton(bf, text="Cancel",
                      **BTN_MUTED_STYLE, font=FONT_MAIN, padx=12, pady=8,
                      command=dialog.destroy).pack(side="left")

        dialog.wait_window()

    def _on_browse_group_file(self, index: int) -> None:
        """Open a file picker to update the file path for an existing group."""
        path = filedialog.askopenfilename(
            filetypes=[("Excel Files", "*.xlsx *.xls"), ("All Files", "*.*")]
        )
        if not path:
            return
        groups = SemesterManager().get_groups()
        if 0 <= index < len(groups):
            groups[index]["file_path"] = path
            self._save_and_refresh_groups(groups)

    def _on_move_group(self, index: int, direction: int) -> None:
        """Move a group up (-1) or down (+1) in priority order."""
        groups = SemesterManager().get_groups()
        new_idx = index + direction
        if 0 <= new_idx < len(groups):
            groups[index], groups[new_idx] = groups[new_idx], groups[index]
            self._save_and_refresh_groups(groups)

    def _on_delete_group(self, index: int) -> None:
        """Remove a group from the semester configuration."""
        groups = SemesterManager().get_groups()
        if 0 <= index < len(groups):
            name = groups[index]["name"]
            if not messagebox.askyesno("Remove Group",
                                       f"Remove '{name}' from this semester?"):
                return
            groups.pop(index)
            self._save_and_refresh_groups(groups)

    def _on_copy_previous_groups(self) -> None:
        """Copy group names from the previous semester, clearing file paths."""
        sm = SemesterManager()
        if not sm.has_active_semester():
            messagebox.showwarning("No Active Semester",
                                   "Start a semester before copying groups.")
            return
        prev = sm.get_previous_semester_groups()
        if not prev:
            messagebox.showinfo("No Previous Groups",
                                "No previous semester has groups configured.")
            return
        existing = sm.get_groups()
        if existing:
            if not messagebox.askyesno(
                "Replace Groups",
                f"This will replace your {len(existing)} current group(s) with "
                f"{len(prev)} group(s) from the previous semester.\n\n"
                "You will need to re-select the files for each group.\n\n"
                "Continue?"
            ):
                return
        self._save_and_refresh_groups(prev)
        messagebox.showinfo(
            "Groups Copied",
            f"Copied {len(prev)} group name(s) from the previous semester.\n\n"
            "Click each file path to select the new files for this semester."
        )

    def _check_semester_on_startup(self):
        """Show new semester prompt if no active semester exists."""
        sm = SemesterManager()
        if not sm.has_active_semester():
            self._show_new_semester_dialog(on_startup=True)

    def _show_new_semester_dialog(self, on_startup: bool = False):
        """Show dialog to create a new semester."""
        dialog = tk.Toplevel(self)
        dialog.title("Start New Semester")
        dialog.geometry("460x240")
        dialog.configure(bg=PANEL_BG)
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        msg = ("Welcome! Let's set up your semester campaign." if on_startup
               else "Create a new semester campaign.")

        tk.Label(dialog, text=msg, bg=PANEL_BG, fg=TEXT_FG,
                 font=FONT_BOLD, wraplength=400).pack(pady=(24, 4), padx=24, anchor="w")
        tk.Label(dialog, text="All runs this semester will be organized together.",
                 bg=PANEL_BG, fg=TEXT_MUTED, font=FONT_SUB).pack(padx=24, anchor="w")

        f = tk.Frame(dialog, bg=PANEL_BG)
        f.pack(fill="x", padx=24, pady=(20, 0))
        tk.Label(f, text="Semester Name:", bg=PANEL_BG, fg=TEXT_FG,
                 font=FONT_MAIN, width=16, anchor="w").pack(side="left")
        name_var = tk.StringVar(value="")
        entry = tk.Entry(f, textvariable=name_var, font=FONT_BOLD, width=26,
                         relief="flat", bg="white",
                         highlightthickness=1, highlightbackground="#B0BEC5",
                         insertbackground=TEXT_FG)
        entry.pack(side="left", ipady=5)
        entry.focus()

        err_lbl = tk.Label(dialog, text="", bg=PANEL_BG, fg="#C62828", font=FONT_SUB)
        err_lbl.pack(padx=24, anchor="w")

        bf = tk.Frame(dialog, bg=PANEL_BG)
        bf.pack(fill="x", padx=24, pady=(12, 0))

        def on_create():
            name = name_var.get().strip()
            if not name:
                err_lbl.config(text="Please enter a semester name.")
                return
            try:
                sm = SemesterManager()
                sem = sm.create_semester(name)
                # Set season var on main window
                if hasattr(self, "_campaign_season_var"):
                    self._campaign_season_var.set(name)
                dialog.destroy()
                self._refresh_semester_tab()
                self._update_semester_header(sem)
            except ValueError as e:
                err_lbl.config(text=str(e))

        def on_skip():
            dialog.destroy()

        RoundedButton(bf, text="Create Semester",
                      **BTN_PRIMARY, font=FONT_BOLD, padx=16, pady=8,
                      command=on_create).pack(side="left", padx=(0, 8))

        if on_startup:
            RoundedButton(bf, text="Skip for now",
                          **BTN_MUTED_STYLE, font=FONT_MAIN, padx=12, pady=8,
                          command=on_skip).pack(side="left")

        dialog.wait_window()

    def _refresh_semester_tab(self):
        """Reload semester data and update the display."""
        sm = SemesterManager()
        sem = sm.active_semester()

        # Update header
        if sem:
            self._sem_name_label.config(text=sem.name, fg=NAVY)
            self._sem_status_label.config(
                text=f"● Active",
                fg="#2E7D32"
            )
            if hasattr(self, "_campaign_season_var"):
                self._campaign_season_var.set(sem.name)
        else:
            self._sem_name_label.config(text="No Active Semester", fg=TEXT_MUTED)
            self._sem_status_label.config(text="")

        # Update checkpoint cards
        from utils.config import (SEMESTER_CHECKPOINTS,
                                  CHECKPOINT_STATUS_NOT_STARTED,
                                  CHECKPOINT_STATUS_IN_PROGRESS,
                                  CHECKPOINT_STATUS_COMPLETE)

        STATUS_COLORS = {
            CHECKPOINT_STATUS_NOT_STARTED: "#78909C",
            CHECKPOINT_STATUS_IN_PROGRESS: "#E65100",
            CHECKPOINT_STATUS_COMPLETE:    "#2E7D32",
        }
        STATUS_ICONS = {
            CHECKPOINT_STATUS_NOT_STARTED: "○",
            CHECKPOINT_STATUS_IN_PROGRESS: "◉",
            CHECKPOINT_STATUS_COMPLETE:    "✓",
        }

        for cp_name, widgets in self._checkpoint_frames.items():
            if sem:
                cp = sem.get_checkpoint(cp_name)
                icon = STATUS_ICONS.get(cp.status, "○")
                color = STATUS_COLORS.get(cp.status, "#78909C")
                widgets["status"].config(
                    text=f"{icon}  {cp.status}", fg=color
                )
                if cp.run_count > 0:
                    widgets["runs"].config(text=f"Runs: {cp.run_count}")
                    widgets["students"].config(
                        text=f"Assigned: {cp.students_assigned:,} | "
                             f"Unmatched: {cp.students_unmatched:,}"
                    )
                else:
                    widgets["runs"].config(text="No runs yet")
                    widgets["students"].config(text="")
            else:
                widgets["status"].config(text="○  Not Started", fg=TEXT_MUTED)
                widgets["runs"].config(text="")
                widgets["students"].config(text="")

        # Update history tree
        self._history_tree.delete(*self._history_tree.get_children())
        for s in sm.all_semesters():
            def cp_val(name):
                cp = s.get_checkpoint(name)
                if cp.status == CHECKPOINT_STATUS_COMPLETE:
                    return f"✓ {cp.students_assigned:,}"
                elif cp.run_count > 0:
                    return f"◉ {cp.students_assigned:,}"
                return "—"

            tag = "active" if s.status == SEMESTER_STATUS_ACTIVE else "done"
            self._history_tree.insert("", "end", tags=(tag,), values=(
                s.name,
                s.status,
                s.created[:10] if s.created else "",
                s.completed[:10] if s.completed else "",
                cp_val("Progress Report 1"),
                cp_val("Midterm"),
                cp_val("Progress Report 2"),
                Path(s.master_report).name if s.master_report else "—",
            ))

        # Rebuild the group list display
        if hasattr(self, "_groups_list_frame"):
            self._rebuild_groups_list()

        # Pre-fill file pickers if semester has saved paths
        if sem:
            if sem.contact_report:
                if hasattr(self, "_contact_picker") and not self._contact_picker.path:
                    self._contact_picker.path = sem.contact_report
                if hasattr(self, "_midterm_contact_picker") and not self._midterm_contact_picker.path:
                    self._midterm_contact_picker.path = sem.contact_report
            if sem.control_file:
                if hasattr(self, "_control_picker") and not self._control_picker.path:
                    self._control_picker.path = sem.control_file
                if hasattr(self, "_midterm_control_picker") and not self._midterm_control_picker.path:
                    self._midterm_control_picker.path = sem.control_file
            if sem.group_folder:
                if hasattr(self, "_group_dir_picker") and not self._group_dir_picker.path:
                    self._group_dir_picker.path = sem.group_folder
                if hasattr(self, "_midterm_group_dir_picker") and not self._midterm_group_dir_picker.path:
                    self._midterm_group_dir_picker.path = sem.group_folder

            # Auto-populate trend/master report pickers
            output_files = sem.output_files()
            cp_to_picker = {
                "Progress Report 1": "_trend_pr1_picker",
                "Midterm":           "_trend_mid_picker",
                "Progress Report 2": "_trend_pr2_picker",
            }
            for cp_name, picker_attr in cp_to_picker.items():
                if cp_name in output_files and hasattr(self, picker_attr):
                    picker = getattr(self, picker_attr)
                    if not picker.path:
                        picker.path = output_files[cp_name]
            # Same for master report pickers
            master_cp_to_picker = {
                "Progress Report 1": "_master_pr1_picker",
                "Midterm":           "_master_mid_picker",
                "Progress Report 2": "_master_pr2_picker",
            }
            for cp_name, picker_attr in master_cp_to_picker.items():
                if cp_name in output_files and hasattr(self, picker_attr):
                    picker = getattr(self, picker_attr)
                    if not picker.path:
                        picker.path = output_files[cp_name]

    def _update_semester_header(self, sem):
        """Quick update of just the header label."""
        if sem and hasattr(self, "_sem_name_label"):
            self._sem_name_label.config(text=sem.name, fg=NAVY)
            self._sem_status_label.config(text="Active", fg="#2E7D32")

    def _on_new_semester(self):
        sm = SemesterManager()
        if sm.has_active_semester():
            messagebox.showwarning("Active Semester Exists",
                f"You already have an active semester: "
                f"'{sm.active_semester().name}'.\n\n"
                "Complete or reset it before starting a new one.")
            return
        self._show_new_semester_dialog()

    def _on_mark_checkpoint_complete(self, checkpoint_name: str):
        sm = SemesterManager()
        if not sm.has_active_semester():
            messagebox.showwarning("No Active Semester",
                "Start a semester first.")
            return
        cp = sm.active_semester().get_checkpoint(checkpoint_name)
        if cp.run_count == 0:
            if not messagebox.askyesno("Mark Complete",
                f"'{checkpoint_name}' has no runs recorded.\n"
                "Mark it complete anyway?"):
                return
        sm.mark_checkpoint_complete(checkpoint_name)
        self._refresh_semester_tab()

    def _on_reset_checkpoint(self, checkpoint_name: str):
        if not messagebox.askyesno("Reset Checkpoint",
            f"Reset '{checkpoint_name}'?\n\n"
            "This will clear the assigned students list so all students "
            "are eligible again for this checkpoint.\n\n"
            "This cannot be undone."):
            return
        sm = SemesterManager()
        cleared = sm.reset_checkpoint(checkpoint_name)
        self._refresh_semester_tab()
        messagebox.showinfo("Checkpoint Reset",
            f"✅ '{checkpoint_name}' reset.\n"
            f"Cleared {cleared:,} student IDs from the assigned list.")

    def _on_complete_semester(self):
        sm = SemesterManager()
        if not sm.has_active_semester():
            messagebox.showwarning("No Active Semester", "No active semester to complete.")
            return
        sem = sm.active_semester()
        if not messagebox.askyesno("Complete Semester",
            f"Complete semester '{sem.name}'?\n\n"
            "This will:\n"
            "  • Generate the Master Season Report\n"
            "  • Clear the assigned students list\n"
            "  • Move semester to history\n\n"
            "This cannot be undone."):
            return

        # Generate master report first
        output_files = sem.output_files()
        out_path = None
        if output_files:
            try:
                from datetime import datetime
                from utils.config import LOG_DATE_FORMAT
                from processors.season_report import SeasonReportGenerator
                timestamp = datetime.now().strftime(LOG_DATE_FORMAT)
                season_label = sem.name.replace(" ", "_")
                out_path = OUTPUT_DIR / f"MasterReport_{season_label}_{timestamp}.xlsx"
                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

                gen = SeasonReportGenerator()
                gen.generate(
                    pr1_path=Path(output_files["Progress Report 1"])
                             if "Progress Report 1" in output_files else None,
                    mid_path=Path(output_files["Midterm"])
                             if "Midterm" in output_files else None,
                    pr2_path=Path(output_files["Progress Report 2"])
                             if "Progress Report 2" in output_files else None,
                    output_path=out_path,
                    season_name=sem.name,
                )
            except Exception as exc:
                if not messagebox.askyesno("Report Error",
                    f"Could not generate master report:\n{exc}\n\n"
                    "Complete semester anyway?"):
                    return

        sm.complete_semester(str(out_path) if out_path else "")
        self._refresh_semester_tab()

        msg = f"✅ Semester '{sem.name}' completed!"
        if out_path:
            msg += f"\n\nMaster Report:\n{out_path}"
        messagebox.showinfo("Semester Complete", msg)

    def _on_reset_semester(self):
        sm = SemesterManager()
        if not sm.has_active_semester():
            messagebox.showwarning("No Active Semester", "No active semester to reset.")
            return
        sem = sm.active_semester()
        if not messagebox.askyesno("Reset Semester",
            f"Reset semester '{sem.name}'?\n\n"
            "This will clear ALL progress for this semester and "
            "remove it from the active view (history preserved).\n\n"
            "This cannot be undone."):
            return
        sm.reset_semester()
        self._refresh_semester_tab()
        messagebox.showinfo("Semester Reset",
            f"Semester '{sem.name}' has been reset.\n"
            "Start a new semester when ready.")


    def _build_settings_tab(self):
        """Build the Settings tab — column mapping editor for all file types."""
        tab = self._settings_tab
        settings = get_settings()

        canvas = tk.Canvas(tab, bg=PANEL_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
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

        def _settings_wheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _settings_wheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        inner.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _settings_wheel))

        self._setting_vars = {}

        def add_section(parent, title, color, subtitle=""):
            tk.Label(parent, text=title, bg=color, fg="white",
                     font=FONT_BOLD, padx=8, pady=6,
                     anchor="w").pack(fill="x", pady=(16, 2))
            if subtitle:
                tk.Label(parent, text=subtitle, bg=PANEL_BG, fg=TEXT_MUTED,
                         font=FONT_SUB).pack(anchor="w", pady=(0, 4))

        def add_field(parent, key, label, value, tooltip=""):
            row = tk.Frame(parent, bg=PANEL_BG)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, bg=PANEL_BG, fg=TEXT_FG,
                     font=FONT_MAIN, width=30, anchor="w").pack(side="left")
            var = tk.StringVar(value=value)
            self._setting_vars[key] = var
            entry = tk.Entry(row, textvariable=var, font=FONT_MAIN,
                             width=36, relief="flat", bg="white",
                             highlightthickness=1, highlightbackground="#B0BEC5",
                             insertbackground=TEXT_FG)
            entry.pack(side="left", ipady=3)
            if tooltip:
                tk.Label(row, text=f"  {tooltip}", bg=PANEL_BG,
                         fg=TEXT_MUTED, font=FONT_SUB).pack(side="left")

        # ── Progress Report ───────────────────────────────────────
        add_section(inner, "📋  Progress Report — Column Names", NAVY,
                    "Column headers from your Navigate/EAB progress report export")
        pm = settings.progress_report_map
        for key, label, tip in [
            ("student_name",  "Student Name",                   "Full student name"),
            ("student_id",    "Student ID",                     "Z-number column"),
            ("course_number", "Course Number",                  "e.g. MAC1105"),
            ("course",        "Course Name",                    "Full course title"),
            ("at_risk",       "At-Risk Flag",                   "Column with Yes/No/True/False"),
            ("letter_grade",  "Grade",                          "Progress report grade column"),
            ("absences",      "Absences",                       "Number of absences"),
            ("alert_reasons", "Alert Reasons",                  ""),
            ("comments",      "Comments",                       "Professor free-text comments"),
        ]:
            add_field(inner, f"progress.{key}", label, pm.get(key, ""), tip)

        # ── Contact Report ────────────────────────────────────────
        add_section(inner, "📇  Contact Report — Column Names", "#375623",
                    "Column headers from your student contact export")
        cm = settings.contact_report_map
        for key, label, tip in [
            ("student_id",      "Student ID",        "Must match progress report ID column"),
            ("phone_cellular",  "Cellular Phone",    "First preference for outreach"),
            ("phone_local",     "Local Phone",       "Second preference"),
            ("phone_permanent", "Permanent Phone",   "Third preference"),
            ("email",           "Email",             "Student email column"),
        ]:
            add_field(inner, f"contact.{key}", label, cm.get(key, ""), tip)

        # ── Midterm Grade Report ──────────────────────────────────
        add_section(inner, "📝  Midterm Grade File — Column Names", "#4A235A",
                    "Column headers from your Canvas midterm grade export")
        mm = settings.midterm_map
        for key, label, tip in [
            ("student_id",    "Student ID",        "Z# column"),
            ("last_name",     "Last Name",         ""),
            ("first_name",    "First Name",        ""),
            ("email",         "Email",             "FAU email column"),
            ("college",       "College",           ""),
            ("major",         "Major",             ""),
            ("classification","Classification",    "e.g. Freshman, Sophomore"),
            ("course_prefix", "Course Prefix",     "e.g. MAC, ENC"),
            ("course_number", "Course Number",     "Numeric part, e.g. 1105"),
            ("course_name",   "Course Name",       "Full course title"),
            ("section",       "Section Number",    ""),
            ("credit_hrs",    "Credit Hours",      ""),
            ("midterm_grade", "Midterm Grade",     "Column containing letter grades"),
        ]:
            add_field(inner, f"midterm.{key}", label, mm.get(key, ""), tip)

        # ── Faculty Report Status ─────────────────────────────────
        add_section(inner, "📊  Faculty Report Status — Column Names", "#843C0C",
                    "Column headers from your Navigate progress report campaign export")
        fm = settings.faculty_map
        for key, label, tip in [
            ("first_name",    "Professor First Name",  "Professor Requested First Name"),
            ("last_name",     "Professor Last Name",   "Professor Requested Last Name"),
            ("email",         "Professor Email",       "Professor email column"),
            ("course_number", "Course Number",         "Used to map to department/college"),
            ("section_name",  "Section Name",          "Course section identifier"),
            ("responded",     "Responded Flag",        "Column with Yes/No submission status"),
        ]:
            add_field(inner, f"faculty.{key}", label, fm.get(key, ""), tip)

        # ── Buttons ───────────────────────────────────────────────
        btn_row = tk.Frame(inner, bg=PANEL_BG)
        btn_row.pack(fill="x", pady=(20, 8))

        RoundedButton(btn_row, text="Save Settings",
                      **BTN_PRIMARY, font=FONT_BOLD, padx=20, pady=9,
                      command=self._on_save_settings).pack(side="left", padx=(0, 10))

        RoundedButton(btn_row, text="Reset to Defaults",
                      **BTN_DANGER, font=FONT_MAIN, padx=14, pady=9,
                      command=self._on_reset_settings).pack(side="left")

        self._settings_status = tk.Label(
            inner, text="", bg=PANEL_BG, fg=SUCCESS_COLOR, font=FONT_MAIN
        )
        self._settings_status.pack(anchor="w", pady=(8, 0))



    def _build_help_tab(self):
        """Build the Help/About tab."""
        outer = tk.Frame(self._help_tab, bg=PANEL_BG, padx=24, pady=16)
        outer.pack(fill="both", expand=True)

        # Header
        tk.Label(outer, text=f"{APP_NAME}  —  Version {APP_VERSION}",
                 bg=PANEL_BG, fg="#1a1f2e", font=FONT_HEADER).pack(anchor="w")
        tk.Label(outer, text="Academic Advising Intervention Workflow Tool",
                 bg=PANEL_BG, fg=TEXT_MUTED, font=FONT_MAIN).pack(anchor="w", pady=(2, 16))

        ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=(0, 16))

        # Scrollable help content
        canvas = tk.Canvas(outer, bg=PANEL_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=PANEL_BG)
        canvas_window = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

        def _help_wheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _help_wheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        inner.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _help_wheel))

        def section(title, color=NAVY):
            tk.Label(inner, text=title, bg=color, fg="white",
                     font=FONT_BOLD, padx=8, pady=5,
                     anchor="w").pack(fill="x", pady=(12, 4))

        def para(text, indent=0):
            tk.Label(inner, text=text, bg=PANEL_BG, fg=TEXT_FG,
                     font=FONT_MAIN, wraplength=680, justify="left",
                     padx=indent).pack(anchor="w", pady=1)

        def item(text):
            tk.Label(inner, text=f"  •  {text}", bg=PANEL_BG, fg=TEXT_FG,
                     font=FONT_MAIN, wraplength=660, justify="left").pack(anchor="w")

        section("📋  Progress Report Sorter", NAVY)
        para("Loads your Navigate/EAB progress report export, filters at-risk students, "
             "aggregates courses per student, and sorts them into prioritized intervention groups.")
        item("Supports .xlsx and .csv input files")
        item("First-match-wins group assignment — priority set by control file order")
        item("Unmatched students go to Risk_1_2 or Risk_3_Plus buckets")
        item("Pre-Run Check validates files before committing to a full run")
        item("Exclude previously assigned students using the checkbox")
        item("Group Selection dialog lets you choose which groups to produce per run")

        section("📝  Midterm Sorter", "#4A235A")
        para("Loads your Canvas midterm grade export and flags students with C- or below "
             "(C-, D+, D, D-, F). Uses the same group matching logic as the Progress Report Sorter.")
        item("Accepts .xlsx and .csv files")
        item("At-risk threshold: C- or lower only — W, WM excluded by design")
        item("Course number built from prefix + number columns (e.g. MAC + 1105 = MAC1105)")

        section("📊  Faculty Report Status", "#843C0C")
        para("Analyzes which professors have submitted progress reports. Upload the campaign "
             "export from Navigate and the department/college mapping file.")
        item("Shows completion % by college, department, and individual professor")
        item("Charts included: donut (overall), bar charts by college and department")
        item("Faculty_Download tab lists all faculty with contact info")
        item("Accepts .xlsx and .csv files")

        section("📈  Campaign Trend", "#375623")
        para("Select your three output workbooks (PR1, Midterm, PR2) to analyze how the "
             "at-risk population moved across the semester.")
        item("Student trajectories: Persistent, Recovered Early, Recovered Late, Relapsed, etc.")
        item("Flow analysis: carried forward, recovered, and new students at each transition")
        item("By Group breakdown across all three checkpoints")
        item("Master Season Report: combined end-of-semester workbook with student list")

        section("🗂️  Campaign Manager", "#1F3864")
        para("Manages the full semester lifecycle. Create a semester, track PR1/Midterm/PR2 "
             "progress, and complete it when done.")
        item("File paths (contact, control, group folder) saved on first run — pre-fill all subsequent runs")
        item("Output files automatically organized into semester subfolders")
        item("Mark Complete and Reset buttons per checkpoint")
        item("Complete Semester generates the Master Season Report automatically")
        item("Full history of past semesters preserved")

        section("⚙️  Settings", "#546E7A")
        para("Update column names for all four file types without editing any Python files. "
             "Changes save to settings.json and take effect on next run.")
        item("Progress Report columns (Navigate/EAB export)")
        item("Contact Report columns (student contact export)")
        item("Midterm Grade columns (Canvas export)")
        item("Faculty Report Status columns (Navigate campaign export)")

        section("📁  Output Files", "#2F5496")
        para("All output files are saved to semester-named subfolders in your output folder "
             "(e.g. output/Fall_2026/). Each workbook includes:")
        item("Data tabs: one per group + Risk_1_2 + Risk_3_Plus")
        item("Summary tab with charts: students by group, contact coverage, risk distribution")
        item("Missing_Contacts tab: students with no phone or email found")
        item("QA_Log tab: data quality events for institutional auditing")
        item("Processing_Manifest tab: run metadata for reproducibility")

        section("❓  Common Questions", "#00695C")
        para("Column names don't match?",)
        para("  → Go to the Settings tab and update the column name for that field.", indent=16)
        para("Students not appearing in output?")
        para("  → Check the Pre-Run Check button — it will identify missing column issues.", indent=16)
        para("Want to rerun a checkpoint from scratch?")
        para("  → Use Reset Checkpoint in the Campaigns tab to clear the assigned list.", indent=16)
        para("Starting a new semester?")
        para("  → Complete or Reset the current semester in the Campaigns tab first.", indent=16)

        ttk.Separator(inner, orient="horizontal").pack(fill="x", pady=(20, 8))
        tk.Label(inner,
                 text=f"Built for FAU Academic Advising  •  v{APP_VERSION}  •  "
                      f"Python + pandas + openpyxl + matplotlib",
                 bg=PANEL_BG, fg=TEXT_MUTED, font=FONT_SUB).pack(anchor="w")

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
            elif section == "midterm":
                settings.midterm_map[field_name] = value
            elif section == "faculty":
                settings.faculty_map[field_name] = value

        try:
            settings.save()
            reload_settings()
            self._settings_status.config(
                text="Settings saved. Changes take effect on next run.",
                fg=SUCCESS_COLOR,
            )
        except Exception as exc:
            self._settings_status.config(
                text=f"❌ Save failed: {exc}", fg="#C62828"
            )

    def _on_reset_settings(self):
        """Reset all fields to config.py defaults."""
        if not messagebox.askyesno(
            "Reset Settings",
            "Reset ALL column mappings to defaults?\nThis cannot be undone."
        ):
            return

        settings = get_settings()
        settings.reset_to_defaults()
        settings.save()
        reload_settings()

        # Refresh all entry fields from reset values
        all_maps = {
            "progress": settings.progress_report_map,
            "contact":  settings.contact_report_map,
            "midterm":  settings.midterm_map,
            "faculty":  settings.faculty_map,
        }
        for key, var in self._setting_vars.items():
            section, field_name = key.split(".", 1)
            if section in all_maps:
                var.set(all_maps[section].get(field_name, ""))

        self._settings_status.config(text="Reset to defaults.", fg="#2F5496")

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
