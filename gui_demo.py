"""Demo-mode helpers for loading bundled synthetic sample files."""

from pathlib import Path
from tkinter import messagebox


def load_progress_demo_files(app) -> None:
    """
    Populate the Progress Report Sorter tab with bundled synthetic demo files.

    Expected repo layout:
        sample_data/
            progress_report_sample.csv
            contact_report_sample.xlsx
            group_control.txt
            group_files/
    """
    repo_root = Path(__file__).resolve().parent
    sample_dir = repo_root / "sample_data"
    group_dir = sample_dir / "group_files"
    output_dir = sample_dir / "demo_outputs"

    demo_paths = {
        "Progress Report": sample_dir / "progress_report_sample.csv",
        "Contact Report": sample_dir / "contact_report_sample.xlsx",
        "Group Control File": sample_dir / "group_control.txt",
        "Group Files Folder": group_dir,
    }

    missing = [label for label, path in demo_paths.items() if not path.exists()]
    if missing:
        messagebox.showerror(
            "Demo Files Not Found",
            "The demo files could not be loaded.\n\n"
            "Make sure the sample_data folder is in the same folder as main.py.\n\n"
            "Missing:\n" + "\n".join(f"• {label}" for label in missing),
        )
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    app._progress_picker.path = str(demo_paths["Progress Report"])
    app._contact_picker.path = str(demo_paths["Contact Report"])
    app._control_picker.path = str(demo_paths["Group Control File"])
    app._group_dir_picker.path = str(demo_paths["Group Files Folder"])
    app._output_picker.path = str(output_dir)

    if hasattr(app, "_exclude_var"):
        app._exclude_var.set(False)

    if hasattr(app, "_log"):
        app._log("✅ Demo files loaded. Click 'Run Full Processing' to test the sample workflow.", "success")

    messagebox.showinfo(
        "Demo Files Loaded",
        "Synthetic demo files have been loaded.\n\n"
        "You can now click 'Run Full Processing' to generate a sample output workbook.",
    )
