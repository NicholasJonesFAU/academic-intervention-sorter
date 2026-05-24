"""Reusable Tkinter dialogs for the Academic Intervention Sorter GUI.

These functions are intentionally thin UI helpers. They receive the main app
instance so they can read and update existing Tkinter variables without changing
application behavior.
"""

from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

import gui_theme as theme
from gui_widgets import RoundedButton
from processors.semester_manager import SemesterManager


def show_group_selection_dialog(app, control_path: str, group_dir: str, checkpoint_name: str) -> tuple:
    """
    Show a checklist of groups before a run.

    Returns:
        tuple[bool, set]: (proceed, skip_groups)

    Source priority:
      1. Active semester groups, if configured
      2. Control file, as a fallback
    """
    sm = SemesterManager()
    semester_groups = sm.get_groups()

    if semester_groups:
        groups = [
            (group["name"], Path(group["file_path"]).name if group["file_path"] else "")
            for group in semester_groups
        ]
    else:
        try:
            from processors.group_matcher import GroupMatcher
            from utils.logging_utils import QALog

            matcher = GroupMatcher(QALog())
            groups = matcher.read_group_names(Path(control_path))
        except Exception:
            return True, set()

    if not groups:
        return True, set()

    saved_selection = sm.get_group_selection(checkpoint_name)

    dialog = tk.Toplevel(app)
    dialog.title(f"Select Groups — {checkpoint_name}")
    dialog.geometry("460x520")
    dialog.configure(bg=theme.PANEL_BG)
    dialog.resizable(False, True)
    dialog.transient(app)
    dialog.grab_set()

    result = {"proceed": False, "skip_groups": set()}

    tk.Label(
        dialog,
        text="Select which groups to produce for this run.",
        bg=theme.PANEL_BG,
        fg=theme.TEXT_FG,
        font=theme.FONT_BOLD,
        wraplength=420,
    ).pack(pady=(16, 2), padx=20, anchor="w")

    tk.Label(
        dialog,
        text="Unchecked groups will be skipped — their students go to unmatched buckets.",
        bg=theme.PANEL_BG,
        fg=theme.TEXT_MUTED,
        font=theme.FONT_SUB,
        wraplength=420,
    ).pack(padx=20, anchor="w")

    ttk.Separator(dialog, orient="horizontal").pack(fill="x", pady=8, padx=20)

    list_frame = tk.Frame(dialog, bg=theme.PANEL_BG)
    list_frame.pack(fill="both", expand=True, padx=20)

    check_vars = {}
    for tab_name, filename in groups:
        selected_by_default = tab_name in saved_selection if saved_selection else True
        var = tk.BooleanVar(value=selected_by_default)
        check_vars[tab_name] = var

        row = tk.Frame(list_frame, bg=theme.PANEL_BG)
        row.pack(fill="x", pady=2)

        tk.Checkbutton(
            row,
            text=f"  {tab_name}",
            variable=var,
            bg=theme.PANEL_BG,
            fg=theme.TEXT_FG,
            font=theme.FONT_BOLD,
            activebackground=theme.PANEL_BG,
            selectcolor="white",
            cursor="hand2",
        ).pack(side="left")

        tk.Label(
            row,
            text=f"({filename})",
            bg=theme.PANEL_BG,
            fg=theme.TEXT_MUTED,
            font=theme.FONT_SUB,
        ).pack(side="left")

    ttk.Separator(dialog, orient="horizontal").pack(fill="x", pady=8, padx=20)

    tk.Label(
        dialog,
        text="Risk_1_2 and Risk_3_Plus are always included",
        bg=theme.PANEL_BG,
        fg=theme.TEXT_MUTED,
        font=theme.FONT_SUB,
    ).pack(padx=20, anchor="w")

    ttk.Separator(dialog, orient="horizontal").pack(fill="x", pady=8, padx=20)

    shortcut_frame = tk.Frame(dialog, bg=theme.PANEL_BG)
    shortcut_frame.pack(fill="x", padx=20, pady=(0, 8))

    RoundedButton(
        shortcut_frame,
        text="Select All",
        command=lambda: [var.set(True) for var in check_vars.values()],
        **theme.BTN_MUTED_STYLE,
        font=theme.FONT_SUB,
        padx=8,
        pady=4,
    ).pack(side="left", padx=(0, 6))

    RoundedButton(
        shortcut_frame,
        text="Select None",
        command=lambda: [var.set(False) for var in check_vars.values()],
        **theme.BTN_MUTED_STYLE,
        font=theme.FONT_SUB,
        padx=8,
        pady=4,
    ).pack(side="left")

    button_frame = tk.Frame(dialog, bg=theme.PANEL_BG)
    button_frame.pack(fill="x", padx=20, pady=(0, 16))

    def on_run():
        selected = [name for name, var in check_vars.items() if var.get()]
        skip = {name for name, var in check_vars.items() if not var.get()}

        if not selected:
            messagebox.showwarning(
                "No Groups Selected",
                "Please select at least one group, or cancel.",
                parent=dialog,
            )
            return

        if sm.has_active_semester():
            sm.save_group_selection(checkpoint_name, selected)

        result["proceed"] = True
        result["skip_groups"] = skip
        dialog.destroy()

    RoundedButton(
        button_frame,
        text="Run with Selected Groups",
        command=on_run,
        **theme.BTN_PRIMARY,
        font=theme.FONT_BOLD,
        padx=16,
        pady=8,
    ).pack(side="left", padx=(0, 8))

    RoundedButton(
        button_frame,
        text="Cancel",
        command=dialog.destroy,
        **theme.BTN_MUTED_STYLE,
        font=theme.FONT_MAIN,
        padx=12,
        pady=8,
    ).pack(side="left")

    dialog.wait_window()
    return result["proceed"], result["skip_groups"]


def ensure_season_set(app) -> bool:
    """
    Ensure the campaign season and checkpoint type are set before running.

    Returns True when the app can proceed and False when the user cancels.
    """
    if not hasattr(app, "_campaign_season_var"):
        return True

    season = app._campaign_season_var.get().strip()
    checkpoint = app._checkpoint_type_var.get().strip() if hasattr(app, "_checkpoint_type_var") else ""

    if season and checkpoint:
        return True

    from utils.config import CHECKPOINT_TYPES

    dialog = tk.Toplevel(app)
    dialog.title("Name This Campaign Run")
    dialog.geometry("480x280")
    dialog.configure(bg=theme.PANEL_BG)
    dialog.resizable(False, False)
    dialog.transient(app)
    dialog.grab_set()

    result = {"proceed": False}

    tk.Label(
        dialog,
        text="Before running, please name this campaign.",
        bg=theme.PANEL_BG,
        fg=theme.TEXT_FG,
        font=theme.FONT_BOLD,
        wraplength=440,
    ).pack(pady=(20, 4), padx=24, anchor="w")

    tk.Label(
        dialog,
        text="This keeps your run history organized by season.",
        bg=theme.PANEL_BG,
        fg=theme.TEXT_MUTED,
        font=theme.FONT_SUB,
    ).pack(padx=24, anchor="w")

    season_frame = tk.Frame(dialog, bg=theme.PANEL_BG)
    season_frame.pack(fill="x", padx=24, pady=(16, 6))

    tk.Label(
        season_frame,
        text="Season Name:",
        bg=theme.PANEL_BG,
        fg=theme.TEXT_FG,
        font=theme.FONT_MAIN,
        width=16,
        anchor="w",
    ).pack(side="left")

    season_var = tk.StringVar(value=season or "")
    tk.Entry(
        season_frame,
        textvariable=season_var,
        font=theme.FONT_MAIN,
        width=28,
        relief="flat",
        bg="white",
        highlightthickness=1,
        highlightbackground="#B0BEC5",
        insertbackground=theme.TEXT_FG,
    ).pack(side="left", ipady=4)

    checkpoint_frame = tk.Frame(dialog, bg=theme.PANEL_BG)
    checkpoint_frame.pack(fill="x", padx=24, pady=(0, 16))

    tk.Label(
        checkpoint_frame,
        text="Checkpoint:",
        bg=theme.PANEL_BG,
        fg=theme.TEXT_FG,
        font=theme.FONT_MAIN,
        width=16,
        anchor="w",
    ).pack(side="left")

    checkpoint_var = tk.StringVar(value=checkpoint or CHECKPOINT_TYPES[0])
    for checkpoint_type in CHECKPOINT_TYPES:
        tk.Radiobutton(
            checkpoint_frame,
            text=checkpoint_type,
            variable=checkpoint_var,
            value=checkpoint_type,
            bg=theme.PANEL_BG,
            fg=theme.TEXT_FG,
            font=theme.FONT_MAIN,
            activebackground=theme.PANEL_BG,
            selectcolor="white",
        ).pack(side="left", padx=(0, 8))

    error_label = tk.Label(dialog, text="", bg=theme.PANEL_BG, fg="#C62828", font=theme.FONT_SUB)
    error_label.pack(padx=24, anchor="w")

    button_frame = tk.Frame(dialog, bg=theme.PANEL_BG)
    button_frame.pack(fill="x", padx=24, pady=(8, 20))

    def on_proceed():
        selected_season = season_var.get().strip()
        if not selected_season:
            error_label.config(text="Please enter a season name.")
            return

        app._campaign_season_var.set(selected_season)
        app._checkpoint_type_var.set(checkpoint_var.get())
        result["proceed"] = True
        dialog.destroy()

    RoundedButton(
        button_frame,
        text="Proceed",
        command=on_proceed,
        **theme.BTN_PRIMARY,
        font=theme.FONT_BOLD,
        padx=16,
        pady=8,
    ).pack(side="left", padx=(0, 8))

    RoundedButton(
        button_frame,
        text="Cancel",
        command=dialog.destroy,
        **theme.BTN_MUTED_STYLE,
        font=theme.FONT_MAIN,
        padx=12,
        pady=8,
    ).pack(side="left")

    dialog.wait_window()
    return result["proceed"]


def show_new_semester_dialog(app, on_startup: bool = False):
    """Show the dialog used to create a new active semester."""
    dialog = tk.Toplevel(app)
    dialog.title("Start New Semester")
    dialog.geometry("460x240")
    dialog.configure(bg=theme.PANEL_BG)
    dialog.resizable(False, False)
    dialog.transient(app)
    dialog.grab_set()

    message = "Welcome! Let's set up your semester campaign." if on_startup else "Create a new semester campaign."

    tk.Label(
        dialog,
        text=message,
        bg=theme.PANEL_BG,
        fg=theme.TEXT_FG,
        font=theme.FONT_BOLD,
        wraplength=400,
    ).pack(pady=(24, 4), padx=24, anchor="w")

    tk.Label(
        dialog,
        text="All runs this semester will be organized together.",
        bg=theme.PANEL_BG,
        fg=theme.TEXT_MUTED,
        font=theme.FONT_SUB,
    ).pack(padx=24, anchor="w")

    form = tk.Frame(dialog, bg=theme.PANEL_BG)
    form.pack(fill="x", padx=24, pady=(20, 0))

    tk.Label(
        form,
        text="Semester Name:",
        bg=theme.PANEL_BG,
        fg=theme.TEXT_FG,
        font=theme.FONT_MAIN,
        width=16,
        anchor="w",
    ).pack(side="left")

    name_var = tk.StringVar(value="")
    entry = tk.Entry(
        form,
        textvariable=name_var,
        font=theme.FONT_BOLD,
        width=26,
        relief="flat",
        bg="white",
        highlightthickness=1,
        highlightbackground="#B0BEC5",
        insertbackground=theme.TEXT_FG,
    )
    entry.pack(side="left", ipady=5)
    entry.focus()

    error_label = tk.Label(dialog, text="", bg=theme.PANEL_BG, fg="#C62828", font=theme.FONT_SUB)
    error_label.pack(padx=24, anchor="w")

    button_frame = tk.Frame(dialog, bg=theme.PANEL_BG)
    button_frame.pack(fill="x", padx=24, pady=(12, 0))

    def on_create():
        name = name_var.get().strip()
        if not name:
            error_label.config(text="Please enter a semester name.")
            return

        try:
            sm = SemesterManager()
            semester = sm.create_semester(name)
            if hasattr(app, "_campaign_season_var"):
                app._campaign_season_var.set(name)
            dialog.destroy()
            app._refresh_semester_tab()
            app._update_semester_header(semester)
        except ValueError as exc:
            error_label.config(text=str(exc))

    RoundedButton(
        button_frame,
        text="Create Semester",
        command=on_create,
        **theme.BTN_PRIMARY,
        font=theme.FONT_BOLD,
        padx=16,
        pady=8,
    ).pack(side="left", padx=(0, 8))

    if on_startup:
        RoundedButton(
            button_frame,
            text="Skip for now",
            command=dialog.destroy,
            **theme.BTN_MUTED_STYLE,
            font=theme.FONT_MAIN,
            padx=12,
            pady=8,
        ).pack(side="left")

    dialog.wait_window()
