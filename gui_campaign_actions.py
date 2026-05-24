"""Campaign/Semester action helpers for the Academic Intervention Sorter GUI."""

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import gui_theme as theme
from gui_widgets import RoundedButton
from gui_dialogs import show_new_semester_dialog
from processors.semester_manager import SemesterManager, SEMESTER_STATUS_ACTIVE
from utils.config import OUTPUT_DIR


def refresh_semester_tab(app):
    """Reload semester data and update the display."""
    sm = SemesterManager()
    sem = sm.active_semester()

    if sem:
        app._sem_name_label.config(text=sem.name, fg=theme.NAVY)
        app._sem_status_label.config(text="● Active", fg="#2E7D32")
        if hasattr(app, "_campaign_season_var"):
            app._campaign_season_var.set(sem.name)
    else:
        app._sem_name_label.config(text="No Active Semester", fg=theme.TEXT_MUTED)
        app._sem_status_label.config(text="")

    from utils.config import (
        CHECKPOINT_STATUS_COMPLETE,
        CHECKPOINT_STATUS_IN_PROGRESS,
        CHECKPOINT_STATUS_NOT_STARTED,
    )

    status_colors = {
        CHECKPOINT_STATUS_NOT_STARTED: "#78909C",
        CHECKPOINT_STATUS_IN_PROGRESS: "#E65100",
        CHECKPOINT_STATUS_COMPLETE: "#2E7D32",
    }

    status_icons = {
        CHECKPOINT_STATUS_NOT_STARTED: "○",
        CHECKPOINT_STATUS_IN_PROGRESS: "◉",
        CHECKPOINT_STATUS_COMPLETE: "✓",
    }

    for cp_name, widgets in app._checkpoint_frames.items():
        if sem:
            cp = sem.get_checkpoint(cp_name)
            icon = status_icons.get(cp.status, "○")
            color = status_colors.get(cp.status, "#78909C")

            widgets["status"].config(text=f"{icon}  {cp.status}", fg=color)

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
            widgets["status"].config(text="○  Not Started", fg=theme.TEXT_MUTED)
            widgets["runs"].config(text="")
            widgets["students"].config(text="")

    app._history_tree.delete(*app._history_tree.get_children())

    for s in sm.all_semesters():
        def cp_val(name):
            cp = s.get_checkpoint(name)
            if cp.status == CHECKPOINT_STATUS_COMPLETE:
                return f"✓ {cp.students_assigned:,}"
            if cp.run_count > 0:
                return f"◉ {cp.students_assigned:,}"
            return "—"

        tag = "active" if s.status == SEMESTER_STATUS_ACTIVE else "done"

        app._history_tree.insert(
            "",
            "end",
            tags=(tag,),
            values=(
                s.name,
                s.status,
                s.created[:10] if s.created else "",
                s.completed[:10] if s.completed else "",
                cp_val("Progress Report 1"),
                cp_val("Midterm"),
                cp_val("Progress Report 2"),
                Path(s.master_report).name if s.master_report else "—",
            ),
        )

    if hasattr(app, "_groups_list_frame"):
        app._rebuild_groups_list()


def rebuild_groups_list(app):
    """Redraw the group list rows from the active semester's group data."""
    for widget in app._groups_list_frame.winfo_children():
        if widget is not app._groups_empty_lbl:
            widget.destroy()

    groups = SemesterManager().get_groups()

    if not groups:
        app._groups_empty_lbl.pack(anchor="w", pady=(4, 8))
        return

    app._groups_empty_lbl.pack_forget()

    hdr = tk.Frame(app._groups_list_frame, bg=theme.PANEL_BG_DARK)
    hdr.pack(fill="x", pady=(0, 2))

    for text, width in [("#", 3), ("Group Name", 18), ("File Path", 0)]:
        tk.Label(
            hdr,
            text=text,
            bg=theme.PANEL_BG_DARK,
            fg=theme.TEXT_MUTED,
            font=theme.FONT_SUB,
            width=width,
            anchor="w",
            padx=6,
        ).pack(side="left")

    tk.Label(
        hdr,
        text="Actions",
        bg=theme.PANEL_BG_DARK,
        fg=theme.TEXT_MUTED,
        font=theme.FONT_SUB,
        width=14,
        anchor="e",
        padx=6,
    ).pack(side="right")

    for i, group in enumerate(groups):
        row = tk.Frame(
            app._groups_list_frame,
            bg=theme.WHITE if i % 2 == 0 else theme.PANEL_BG,
            pady=4,
            padx=6,
        )
        row.pack(fill="x")

        tk.Label(
            row,
            text=str(i + 1),
            bg=row.cget("bg"),
            fg=theme.TEXT_MUTED,
            font=theme.FONT_SUB,
            width=3,
        ).pack(side="left")

        tk.Label(
            row,
            text=group["name"],
            bg=row.cget("bg"),
            fg=theme.TEXT_FG,
            font=theme.FONT_BOLD,
            width=18,
            anchor="w",
        ).pack(side="left")

        path_str = group["file_path"]
        display = Path(path_str).name if path_str else "⚠  No file selected"
        path_color = theme.TEXT_FG if path_str else theme.RED_ACCENT

        path_lbl = tk.Label(
            row,
            text=display,
            bg=row.cget("bg"),
            fg=path_color,
            font=theme.FONT_MAIN,
            anchor="w",
            cursor="hand2",
        )
        path_lbl.pack(side="left", fill="x", expand=True)
        path_lbl.bind("<Button-1>", lambda e, idx=i: app._on_browse_group_file(idx))

        action_frame = tk.Frame(row, bg=row.cget("bg"))
        action_frame.pack(side="right")

        if i > 0:
            RoundedButton(
                action_frame,
                text="▲",
                **theme.BTN_MUTED_STYLE,
                font=theme.FONT_SUB,
                padx=6,
                pady=2,
                command=lambda idx=i: app._on_move_group(idx, -1),
            ).pack(side="left", padx=(0, 2))
        else:
            tk.Frame(action_frame, bg=row.cget("bg"), width=32).pack(side="left", padx=(0, 2))

        if i < len(groups) - 1:
            RoundedButton(
                action_frame,
                text="▼",
                **theme.BTN_MUTED_STYLE,
                font=theme.FONT_SUB,
                padx=6,
                pady=2,
                command=lambda idx=i: app._on_move_group(idx, 1),
            ).pack(side="left", padx=(0, 6))
        else:
            tk.Frame(action_frame, bg=row.cget("bg"), width=32).pack(side="left", padx=(0, 6))

        RoundedButton(
            action_frame,
            text="✕",
            **theme.BTN_DANGER,
            font=theme.FONT_SUB,
            padx=6,
            pady=2,
            command=lambda idx=i: app._on_delete_group(idx),
        ).pack(side="left")


def save_and_refresh_groups(app, groups):
    """Persist group list to the active semester and rebuild the UI."""
    sm = SemesterManager()
    if sm.has_active_semester():
        sm.set_groups(groups)
    app._rebuild_groups_list()


def on_add_group(app):
    """Open the Add Group dialog."""
    sm = SemesterManager()

    if not sm.has_active_semester():
        messagebox.showwarning("No Active Semester", "Start a semester before adding groups.")
        return

    dialog = tk.Toplevel(app)
    dialog.title("Add Group")
    dialog.geometry("500x200")
    dialog.configure(bg=theme.PANEL_BG)
    dialog.resizable(False, False)
    dialog.transient(app)
    dialog.grab_set()

    tk.Label(
        dialog,
        text="Group Name:",
        bg=theme.PANEL_BG,
        fg=theme.TEXT_FG,
        font=theme.FONT_BOLD,
    ).pack(anchor="w", padx=24, pady=(20, 4))

    name_var = tk.StringVar()
    name_entry = tk.Entry(
        dialog,
        textvariable=name_var,
        font=theme.FONT_MAIN,
        width=38,
        relief="flat",
        bg=theme.WHITE,
        highlightthickness=1,
        highlightbackground=theme.BORDER,
        highlightcolor=theme.NAVY_DARK,
        insertbackground=theme.NAVY_DARK,
    )
    name_entry.pack(anchor="w", padx=24, ipady=4)
    name_entry.focus()

    file_var = tk.StringVar()

    file_frame = tk.Frame(dialog, bg=theme.PANEL_BG)
    file_frame.pack(fill="x", padx=24, pady=(10, 0))

    tk.Label(
        file_frame,
        text="Group File (.xlsx):",
        bg=theme.PANEL_BG,
        fg=theme.TEXT_FG,
        font=theme.FONT_BOLD,
    ).pack(anchor="w")

    pick_row = tk.Frame(file_frame, bg=theme.PANEL_BG)
    pick_row.pack(fill="x", pady=(4, 0))

    tk.Entry(
        pick_row,
        textvariable=file_var,
        font=theme.FONT_MAIN,
        width=36,
        relief="flat",
        bg=theme.WHITE,
        highlightthickness=1,
        highlightbackground=theme.BORDER,
    ).pack(side="left", ipady=4, padx=(0, 8))

    RoundedButton(
        pick_row,
        text="Browse",
        **theme.BTN_MUTED_STYLE,
        font=theme.FONT_BOLD,
        padx=10,
        pady=4,
        command=lambda: file_var.set(
            filedialog.askopenfilename(
                filetypes=[("Excel Files", "*.xlsx *.xls"), ("All Files", "*.*")]
            )
            or file_var.get()
        ),
    ).pack(side="left")

    err_lbl = tk.Label(
        dialog,
        text="",
        bg=theme.PANEL_BG,
        fg=theme.RED_ACCENT,
        font=theme.FONT_SUB,
    )
    err_lbl.pack(anchor="w", padx=24)

    bf = tk.Frame(dialog, bg=theme.PANEL_BG)
    bf.pack(fill="x", padx=24, pady=(8, 16))

    def add_group():
        name = name_var.get().strip()

        if not name:
            err_lbl.config(text="Please enter a group name.")
            return

        groups = SemesterManager().get_groups()

        if any(g["name"].lower() == name.lower() for g in groups):
            err_lbl.config(text=f"A group named '{name}' already exists.")
            return

        groups.append({"name": name, "file_path": file_var.get().strip()})
        app._save_and_refresh_groups(groups)
        dialog.destroy()

    RoundedButton(
        bf,
        text="Add Group",
        **theme.BTN_PRIMARY,
        font=theme.FONT_BOLD,
        padx=16,
        pady=8,
        command=add_group,
    ).pack(side="left", padx=(0, 8))

    RoundedButton(
        bf,
        text="Cancel",
        **theme.BTN_MUTED_STYLE,
        font=theme.FONT_MAIN,
        padx=12,
        pady=8,
        command=dialog.destroy,
    ).pack(side="left")

    dialog.wait_window()


def on_browse_group_file(app, index):
    """Open a file picker to update the file path for an existing group."""
    path = filedialog.askopenfilename(
        filetypes=[("Excel Files", "*.xlsx *.xls"), ("All Files", "*.*")]
    )

    if not path:
        return

    groups = SemesterManager().get_groups()

    if 0 <= index < len(groups):
        groups[index]["file_path"] = path
        app._save_and_refresh_groups(groups)


def on_move_group(app, index, direction):
    """Move a group up (-1) or down (+1) in priority order."""
    groups = SemesterManager().get_groups()
    new_idx = index + direction

    if 0 <= new_idx < len(groups):
        groups[index], groups[new_idx] = groups[new_idx], groups[index]
        app._save_and_refresh_groups(groups)


def on_delete_group(app, index):
    """Remove a group from the semester configuration."""
    groups = SemesterManager().get_groups()

    if 0 <= index < len(groups):
        name = groups[index]["name"]

        if not messagebox.askyesno("Remove Group", f"Remove '{name}' from this semester?"):
            return

        groups.pop(index)
        app._save_and_refresh_groups(groups)


def on_copy_previous_groups(app):
    """Copy group names from the previous semester, clearing file paths."""
    sm = SemesterManager()

    if not sm.has_active_semester():
        messagebox.showwarning("No Active Semester", "Start a semester before copying groups.")
        return

    prev = sm.get_previous_semester_groups()

    if not prev:
        messagebox.showinfo("No Previous Groups", "No previous semester has groups configured.")
        return

    existing = sm.get_groups()

    if existing:
        if not messagebox.askyesno(
            "Replace Groups",
            f"This will replace your {len(existing)} current group(s) with "
            f"{len(prev)} group(s) from the previous semester.\n\n"
            "You will need to re-select the files for each group.\n\n"
            "Continue?",
        ):
            return

    app._save_and_refresh_groups(prev)

    messagebox.showinfo(
        "Groups Copied",
        f"Copied {len(prev)} group name(s) from the previous semester.\n\n"
        "Click each file path to select the new files for this semester.",
    )


def check_semester_on_startup(app):
    """Show new semester prompt if no active semester exists."""
    sm = SemesterManager()

    if not sm.has_active_semester():
        app._show_new_semester_dialog(on_startup=True)


def show_new_semester_dialog_wrapper(app, on_startup=False):
    return show_new_semester_dialog(app, on_startup)


def update_semester_header(app, sem):
    """Quick update of just the header label."""
    if sem and hasattr(app, "_sem_name_label"):
        app._sem_name_label.config(text=sem.name, fg=theme.NAVY)
        app._sem_status_label.config(text="Active", fg="#2E7D32")


def on_new_semester(app):
    sm = SemesterManager()

    if sm.has_active_semester():
        messagebox.showwarning(
            "Active Semester Exists",
            f"You already have an active semester: "
            f"'{sm.active_semester().name}'.\n\n"
            "Complete or reset it before starting a new one.",
        )
        return

    app._show_new_semester_dialog()


def on_mark_checkpoint_complete(app, checkpoint_name):
    sm = SemesterManager()

    if not sm.has_active_semester():
        messagebox.showwarning("No Active Semester", "Start a semester first.")
        return

    cp = sm.active_semester().get_checkpoint(checkpoint_name)

    if cp.run_count == 0:
        if not messagebox.askyesno(
            "Mark Complete",
            f"'{checkpoint_name}' has no runs recorded.\n"
            "Mark it complete anyway?",
        ):
            return

    sm.mark_checkpoint_complete(checkpoint_name)
    app._refresh_semester_tab()


def on_reset_checkpoint(app, checkpoint_name):
    if not messagebox.askyesno(
        "Reset Checkpoint",
        f"Reset '{checkpoint_name}'?\n\n"
        "This will clear the assigned students list so all students "
        "are eligible again for this checkpoint.\n\n"
        "This cannot be undone.",
    ):
        return

    sm = SemesterManager()
    cleared = sm.reset_checkpoint(checkpoint_name)

    app._refresh_semester_tab()

    messagebox.showinfo(
        "Checkpoint Reset",
        f"✅ '{checkpoint_name}' reset.\n"
        f"Cleared {cleared:,} student IDs from the assigned list.",
    )


def on_complete_semester(app):
    sm = SemesterManager()

    if not sm.has_active_semester():
        messagebox.showwarning("No Active Semester", "No active semester to complete.")
        return

    sem = sm.active_semester()

    if not messagebox.askyesno(
        "Complete Semester",
        f"Complete semester '{sem.name}'?\n\n"
        "This will:\n"
        "  • Generate the Master Season Report\n"
        "  • Clear the assigned students list\n"
        "  • Move semester to history\n\n"
        "This cannot be undone.",
    ):
        return

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
                if "Progress Report 1" in output_files
                else None,
                mid_path=Path(output_files["Midterm"])
                if "Midterm" in output_files
                else None,
                pr2_path=Path(output_files["Progress Report 2"])
                if "Progress Report 2" in output_files
                else None,
                output_path=out_path,
                season_name=sem.name,
            )

        except Exception as exc:
            if not messagebox.askyesno(
                "Report Error",
                f"Could not generate master report:\n{exc}\n\n"
                "Complete semester anyway?",
            ):
                return

    sm.complete_semester(str(out_path) if out_path else "")
    app._refresh_semester_tab()

    msg = f"✅ Semester '{sem.name}' completed!"

    if out_path:
        msg += f"\n\nMaster Report:\n{out_path}"

    messagebox.showinfo("Semester Complete", msg)


def on_reset_semester(app):
    sm = SemesterManager()

    if not sm.has_active_semester():
        messagebox.showwarning("No Active Semester", "No active semester to reset.")
        return

    sem = sm.active_semester()

    if not messagebox.askyesno(
        "Reset Semester",
        f"Reset semester '{sem.name}'?\n\n"
        "This will clear ALL progress for this semester and "
        "remove it from the active view (history preserved).\n\n"
        "This cannot be undone.",
    ):
        return

    sm.reset_semester()
    app._refresh_semester_tab()

    messagebox.showinfo(
        "Semester Reset",
        f"Semester '{sem.name}' has been reset.\n"
        "Start a new semester when ready.",
    )