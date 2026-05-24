"""Faculty Report Status tab UI construction.

This module keeps the tab layout separate from main.py while leaving the
processing actions on the main application class.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext

import gui_theme as theme
from gui_widgets import FilePickerRow, RoundedButton, section_label
from gui_logging import configure_log_tags, PURPLE_LOG_TAGS
from utils.config import OUTPUT_DIR


def build_report_status_tab(app) -> None:
    """Build the Faculty Report Status tab UI onto the existing app instance."""
    notebook = None
    for widget in app.winfo_children():
        if isinstance(widget, ttk.Notebook):
            notebook = widget
            break
    if not notebook:
        return

    tab = notebook.winfo_children()[1]
    content, wheel_on, wheel_off = app._make_scrollable_tab(tab)

    section_label(content, "Input Files").pack(fill="x", pady=(0, 8))

    picker_frame = tk.Frame(content, bg=theme.PANEL_BG)
    picker_frame.pack(fill="x")

    app._status_picker = FilePickerRow(
        picker_frame,
        label="Report Status File:",
        filetypes=[
            ("Excel/CSV Files", "*.xlsx *.xls *.csv"),
            ("Excel Files", "*.xlsx *.xls"),
            ("CSV Files", "*.csv"),
            ("All Files", "*.*"),
        ],
        tooltip="Excel file showing which professors have submitted progress reports",
    )
    app._status_picker.pack(fill="x", pady=4)

    app._mapping_picker = FilePickerRow(
        picker_frame,
        label="Dept/College Mapping:",
        filetypes=[("Excel Files", "*.xlsx *.xls"), ("All Files", "*.*")],
        tooltip="Excel file mapping course prefixes to departments and colleges",
    )
    app._mapping_picker.pack(fill="x", pady=4)

    app._report_output_picker = FilePickerRow(
        picker_frame,
        label="Output Folder:",
        filetypes=[],
        is_directory=True,
        tooltip="Where the faculty completion workbook will be saved",
    )
    app._report_output_picker.pack(fill="x", pady=4)
    app._report_output_picker.path = str(OUTPUT_DIR)

    ttk.Separator(content, orient="horizontal").pack(fill="x", pady=14)

    button_frame = tk.Frame(content, bg=theme.PANEL_BG)
    button_frame.pack(fill="x")

    app._report_run_btn = RoundedButton(
        button_frame,
        text="Generate Faculty Report",
        command=app._on_run_report_status,
        **theme.BTN_PRIMARY,
        font=theme.FONT_BOLD,
        padx=20,
        pady=9,
    )
    app._report_run_btn.pack(side="left")

    app._report_progress_bar = ttk.Progressbar(
        content,
        maximum=100,
        mode="indeterminate",
    )
    app._report_progress_bar.pack(fill="x", pady=(12, 0))

    section_label(content, "Processing Log").pack(fill="x", pady=(12, 4))

    app._report_log_box = scrolledtext.ScrolledText(
        content,
        height=14,
        font=theme.FONT_MONO,
        bg="#0A1628",
        fg="#C8D6E8",
        relief="flat",
        wrap="word",
    )
    app._report_log_box.pack(fill="both", expand=True)
    app._report_log_box.config(state="disabled")
    app._report_log_box.bind("<Enter>", wheel_off)
    app._report_log_box.bind("<Leave>", wheel_on)
    configure_log_tags(app._report_log_box, PURPLE_LOG_TAGS)
