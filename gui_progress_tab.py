"""Progress Report Sorter tab UI builder."""

import tkinter as tk
from tkinter import ttk, scrolledtext

import gui_theme as theme
from gui_widgets import section_label, RoundedButton, FilePickerRow
from gui_logging import configure_log_tags, DEFAULT_LOG_TAGS


def build_progress_report_sorter_tab(app, tab):
    """Build the Progress Report Sorter tab and attach widgets to app."""
    content ,_wheel_on ,_wheel_off =app._make_scrollable_tab(tab, padx=28, pady=18)

    # ── File pickers ───────────────────────────────────────────
    section_label (content ,"Input Files").pack (fill ="x",pady =(0 ,10 ))

    picker_frame =tk .Frame (content ,bg =theme.PANEL_BG )
    picker_frame .pack (fill ="x")

    app ._progress_picker =FilePickerRow (
    picker_frame ,
    label ="Progress Report:",
    filetypes =[("Excel/CSV Files","*.xlsx *.xls *.csv"),("Excel Files","*.xlsx *.xls"),("CSV Files","*.csv"),("All Files","*.*")],
    tooltip ="Excel (.xlsx) or CSV file with student at-risk data",
    )
    app ._progress_picker .pack (fill ="x",pady =4 )

    app ._contact_picker =FilePickerRow (
    picker_frame ,
    label ="Contact Report:",
    filetypes =[("Excel Files","*.xlsx *.xls"),("All Files","*.*")],
    tooltip ="Excel file with student phone/email",
    )
    app ._contact_picker .pack (fill ="x",pady =4 )

    app ._control_picker =FilePickerRow (
    picker_frame ,
    label ="Group Control File:",
    filetypes =[("Text Files","*.txt"),("All Files","*.*")],
    tooltip ="TXT file: TabName|filename.xlsx (one per line, ordered by priority)",
    )
    app ._control_picker .pack (fill ="x",pady =4 )

    app ._group_dir_picker =FilePickerRow (
    picker_frame ,
    label ="Group Files Folder:",
    filetypes =[],
    is_directory =True ,
    tooltip ="Folder containing group Excel files listed in the control file",
    )
    app ._group_dir_picker .pack (fill ="x",pady =4 )

    app ._output_picker =FilePickerRow (
    picker_frame ,
    label ="Output Folder:",
    filetypes =[],
    is_directory =True ,
    tooltip ="Where the output Excel workbook will be saved",
    )
    app ._output_picker .pack (fill ="x",pady =4 )

    # Exclude previously assigned checkbox
    chk_frame =tk .Frame (content ,bg =theme.PANEL_BG )
    chk_frame .pack (fill ="x",pady =(8 ,0 ))
    tk .Checkbutton (
    chk_frame ,
    text ="Exclude students already assigned in a previous run this campaign",
    variable =app ._exclude_var ,
    bg =theme.PANEL_BG ,fg =theme.TEXT_FG ,
    font =theme.FONT_MAIN ,
    activebackground =theme.PANEL_BG ,
    selectcolor ="white",
    cursor ="hand2",
    ).pack (side ="left")
    tk .Label (
    chk_frame ,
    text ="(reads/writes assigned_students.txt in output folder)",
    bg =theme.PANEL_BG ,fg =theme.TEXT_MUTED ,font =theme.FONT_SUB ,
    ).pack (side ="left",padx =(8 ,0 ))

    ttk .Separator (content ,orient ="horizontal").pack (fill ="x",pady =14 )

    # ── Buttons ────────────────────────────────────────────────
    btn_frame =tk .Frame (content ,bg =theme.PANEL_BG )
    btn_frame .pack (fill ="x")

    app ._run_btn =RoundedButton (
    btn_frame ,text ='Run Full Processing',
    command =app ._on_run ,
    **theme.BTN_PRIMARY ,font =theme.FONT_BOLD ,padx =20 ,pady =9 ,
    )
    app ._run_btn .pack (side ="left",padx =(0 ,10 ))

    app ._validate_btn =RoundedButton (
    btn_frame ,text ='Validate Only',
    command =app ._on_validate ,
    **theme.BTN_SECONDARY_STYLE ,font =theme.FONT_MAIN ,padx =14 ,pady =8 ,
    )
    app ._validate_btn .pack (side ="left",padx =(0 ,10 ))

    app ._precheck_btn =RoundedButton (
    btn_frame ,text ='Pre-Run Check',
    command =app ._on_prerun_check ,
    **theme.BTN_DANGER ,font =theme.FONT_MAIN ,padx =14 ,pady =8 ,
    )
    app ._precheck_btn .pack (side ="left",padx =(0 ,10 ))

    app ._clear_btn =RoundedButton (
    btn_frame ,text ='Clear',
    command =app ._on_clear ,
    **theme.BTN_SECONDARY_STYLE ,font =theme.FONT_MAIN ,padx =14 ,pady =8 ,
    )
    app ._clear_btn .pack (side ="left")

    # ── Progress bar ───────────────────────────────────────────
    app ._progress_var =tk .DoubleVar (value =0 )
    app ._progress_bar =ttk .Progressbar (
    content ,variable =app ._progress_var ,
    maximum =100 ,mode ="indeterminate",
    )
    app ._progress_bar .pack (fill ="x",pady =(12 ,0 ))

    # ── Status log ─────────────────────────────────────────────
    section_label (content ,"Processing Log").pack (fill ="x",pady =(10 ,4 ))

    app ._log_box =scrolledtext .ScrolledText (
    content ,height =10 ,font =theme.FONT_MONO ,
    bg ="#0A1628",fg ="#C8D6E8",
    insertbackground ="white",
    relief ="flat",
    wrap ="word",
    )
    app ._log_box .pack (fill ="both",expand =True )
    app ._log_box .config (state ="disabled")
    app ._log_box .bind ("<Enter>",_wheel_off )
    app ._log_box .bind ("<Leave>",_wheel_on )

    # Tag styles for log
    configure_log_tags(app._log_box, DEFAULT_LOG_TAGS)
