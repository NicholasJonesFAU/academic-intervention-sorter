"""Midterm Sorter tab construction for the Academic Intervention Sorter GUI."""

import tkinter as tk
from tkinter import ttk, scrolledtext

import gui_theme as theme
from gui_widgets import section_label, RoundedButton, FilePickerRow
from gui_logging import configure_log_tags, PURPLE_LOG_TAGS
from utils.config import OUTPUT_DIR


def build_midterm_tab(app) -> None:
    """Build the Midterm Sorter tab UI on the provided app instance."""
    tab = app._midterm_tab
    outer, wheel_on, wheel_off = app._make_scrollable_tab(tab)

    section_label(outer, "Input Files").pack(fill="x", pady=(0, 8))

    picker_frame = tk.Frame(outer, bg=theme.PANEL_BG)
    picker_frame.pack(fill="x")

    app._midterm_file_picker = FilePickerRow(
        picker_frame,
        label="Midterm Grade File:",
        filetypes=[("Excel/CSV Files", "*.xlsx *.xls *.csv"), ("All Files", "*.*")],
        tooltip="Canvas midterm export — xlsx or csv",
    )
    app._midterm_file_picker.pack(fill="x", pady=4)

    app._midterm_contact_picker = FilePickerRow(
        picker_frame,
        label="Contact Report:",
        filetypes=[("Excel Files", "*.xlsx *.xls"), ("All Files", "*.*")],
        tooltip="Same contact report used in Progress Report Sorter",
    )
    app._midterm_contact_picker.pack(fill="x", pady=4)

    app._midterm_control_picker = FilePickerRow(
        picker_frame,
        label="Group Control File:",
        filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
        tooltip="TXT file: TabName|filename.xlsx  (one per line, ordered by priority)",
    )
    app._midterm_control_picker.pack(fill="x", pady=4)

    app._midterm_group_dir_picker = FilePickerRow(
        picker_frame,
        label="Group Files Folder:",
        filetypes=[],
        is_directory=True,
        tooltip="Folder containing group Excel files listed in the control file",
    )
    app._midterm_group_dir_picker.pack(fill="x", pady=4)

    app._midterm_output_picker = FilePickerRow(
        picker_frame,
        label="Output Folder:",
        filetypes=[],
        is_directory=True,
        tooltip="Where the output workbook will be saved",
    )
    app._midterm_output_picker.pack(fill="x", pady=4)
    app._midterm_output_picker.path = str(OUTPUT_DIR)

    checkbox_frame = tk.Frame(outer, bg=theme.PANEL_BG)
    checkbox_frame.pack(fill="x", pady=(8, 0))

    tk.Checkbutton(
        checkbox_frame,
        text="Exclude students already assigned in a previous run this campaign",
        variable=app._midterm_exclude_var,
        bg=theme.PANEL_BG,
        fg=theme.TEXT_FG,
        font=theme.FONT_MAIN,
        activebackground=theme.PANEL_BG,
        selectcolor="#ffffff",
        cursor="hand2",
    ).pack(side="left")

    tk.Label(
        checkbox_frame,
        text="(reads/writes assigned_students.txt in output folder)",
        bg=theme.PANEL_BG,
        fg=theme.TEXT_MUTED,
        font=theme.FONT_SUB,
    ).pack(side="left", padx=(8, 0))

    ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=14)

    button_frame = tk.Frame(outer, bg=theme.PANEL_BG)
    button_frame.pack(fill="x", pady=(0, 8))

    app._midterm_run_btn = RoundedButton(
        button_frame,
        text="Run Midterm Sort",
        command=app._on_run_midterm,
        **theme.BTN_PRIMARY,
        font=theme.FONT_BOLD,
        padx=20,
        pady=9,
    )
    app._midterm_run_btn.pack(side="left", padx=(0, 10))

    RoundedButton(
        button_frame,
        text="Clear",
        **theme.BTN_MUTED_STYLE,
        font=theme.FONT_MAIN,
        padx=14,
        pady=9,
        command=app._midterm_clear_log,
    ).pack(side="left")

    app._midterm_progress_bar = ttk.Progressbar(
        outer,
        maximum=100,
        mode="indeterminate",
    )
    app._midterm_progress_bar.pack(fill="x", pady=(0, 8))

    section_label(outer, "Processing Log").pack(fill="x", pady=(4, 4))

    app._midterm_log_box = scrolledtext.ScrolledText(
        outer,
        height=10,
        font=theme.FONT_MONO,
        bg="#0A1628",
        fg="#C8D6E8",
        relief="flat",
        wrap="word",
    )
    app._midterm_log_box.pack(fill="both", expand=True)
    app._midterm_log_box.config(state="disabled")
    app._midterm_log_box.bind("<Enter>", wheel_off)
    app._midterm_log_box.bind("<Leave>", wheel_on)
    configure_log_tags(app._midterm_log_box, PURPLE_LOG_TAGS)
