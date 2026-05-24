"""Campaign Trend tab UI builder."""

import tkinter as tk
from tkinter import ttk, scrolledtext

import gui_theme as theme
from gui_widgets import FilePickerRow, RoundedButton, section_label
from gui_logging import configure_log_tags, PURPLE_LOG_TAGS
from utils.config import OUTPUT_DIR


def build_trend_tab(app):
    """Build the Campaign Trend / Master Report tab UI."""
    """Build the Campaign Trend Report tab."""
    outer ,_wheel_on4 ,_wheel_off4 =app ._make_scrollable_tab (app ._trend_tab )

    # Description
    tk .Label (
    outer ,
    text ="Select your three output workbooks in order to analyze how the "
    "at-risk population moved across the semester cycle.",
    bg =theme.PANEL_BG ,fg =theme.TEXT_MUTED ,font =theme.FONT_SUB ,
    wraplength =700 ,justify ="left",
    ).pack (anchor ="w",pady =(0 ,12 ))

    section_label (outer ,"Select Output Workbooks").pack (fill ="x",pady =(0 ,8 ))

    pf =tk .Frame (outer ,bg =theme.PANEL_BG )
    pf .pack (fill ="x")

    app ._trend_pr1_picker =FilePickerRow (
    pf ,label ="Progress Report 1:",
    filetypes =[("Excel Files","*.xlsx"),("All Files","*.*")],
    tooltip ="First progress report output (InterventionSort_...xlsx)",
    )
    app ._trend_pr1_picker .pack (fill ="x",pady =4 )

    app ._trend_mid_picker =FilePickerRow (
    pf ,label ="Midterm:",
    filetypes =[("Excel Files","*.xlsx"),("All Files","*.*")],
    tooltip ="Midterm sort output (MidtermSort_...xlsx)",
    )
    app ._trend_mid_picker .pack (fill ="x",pady =4 )

    app ._trend_pr2_picker =FilePickerRow (
    pf ,label ="Progress Report 2:",
    filetypes =[("Excel Files","*.xlsx"),("All Files","*.*")],
    tooltip ="Second progress report output (InterventionSort_...xlsx)",
    )
    app ._trend_pr2_picker .pack (fill ="x",pady =4 )

    app ._trend_output_picker =FilePickerRow (
    pf ,label ="Output Folder:",
    filetypes =[],is_directory =True ,
    tooltip ="Where the trend report will be saved",
    )
    app ._trend_output_picker .pack (fill ="x",pady =4 )
    app ._trend_output_picker .path =str (OUTPUT_DIR )

    # Optional labels
    lbl_frame =tk .Frame (outer ,bg =theme.PANEL_BG )
    lbl_frame .pack (fill ="x",pady =(8 ,0 ))
    tk .Label (lbl_frame ,text ="Optional — customize checkpoint labels in the report:",
    bg =theme.PANEL_BG ,fg =theme.TEXT_MUTED ,font =theme.FONT_SUB ).pack (anchor ="w")

    name_row =tk .Frame (outer ,bg =theme.PANEL_BG )
    name_row .pack (fill ="x",pady =4 )
    for i ,(label ,default ,attr )in enumerate ([
    ("PR1 Label:","Progress Report 1","_trend_pr1_label"),
    ("Midterm Label:","Midterm","_trend_mid_label"),
    ("PR2 Label:","Progress Report 2","_trend_pr2_label"),
    ]):
        tk .Label (name_row ,text =label ,bg =theme.PANEL_BG ,fg =theme.TEXT_FG ,
        font =theme.FONT_MAIN ,width =14 ,anchor ="w").grid (row =0 ,column =i *2 ,padx =(0 ,4 ))
        var =tk .StringVar (value =default )
        setattr (app ,attr ,var )
        tk .Entry (name_row ,textvariable =var ,font =theme.FONT_MAIN ,width =22 ,
        relief ="flat",bg ="white",
        highlightthickness =1 ,highlightbackground ="#B0BEC5",
        insertbackground =theme.TEXT_FG ).grid (row =0 ,column =i *2 +1 ,padx =(0 ,16 ),ipady =3 )

    ttk .Separator (outer ,orient ="horizontal").pack (fill ="x",pady =14 )

    btn_frame =tk .Frame (outer ,bg =theme.PANEL_BG )
    btn_frame .pack (fill ="x",pady =(0 ,8 ))

    app ._trend_run_btn =RoundedButton (
    btn_frame ,text ='Generate Trend Report',
    command =app ._on_run_trend ,
    **theme.BTN_PRIMARY ,font =theme.FONT_BOLD ,padx =20 ,pady =9 ,
    )
    app ._trend_run_btn .pack (side ="left",padx =(0 ,10 ))

    RoundedButton (
    btn_frame ,text ="Clear",
    **theme.BTN_MUTED_STYLE ,font =theme.FONT_MAIN ,padx =14 ,pady =9 ,
    command =app ._trend_clear_log ,
    ).pack (side ="left")

    app ._trend_progress_bar =ttk .Progressbar (
    outer ,maximum =100 ,mode ="indeterminate"
    )
    app ._trend_progress_bar .pack (fill ="x",pady =(0 ,8 ))

    ttk .Separator (outer ,orient ="horizontal").pack (fill ="x",pady =10 )

    # Master Season Report section
    section_label (outer ,"End-of-Semester Master Report").pack (fill ="x",pady =(0 ,6 ))
    tk .Label (
    outer ,
    text ="Select the three output workbooks from this semester to generate "
    "a combined master report with student list and season summary.",
    bg =theme.PANEL_BG ,fg =theme.TEXT_MUTED ,font =theme.FONT_SUB ,wraplength =700 ,justify ="left",
    ).pack (anchor ="w",pady =(0 ,8 ))

    mf =tk .Frame (outer ,bg =theme.PANEL_BG )
    mf .pack (fill ="x")

    app ._master_pr1_picker =FilePickerRow (
    mf ,label ="Progress Report 1:",
    filetypes =[("Excel Files","*.xlsx"),("All Files","*.*")],
    tooltip ="PR1 output workbook (ProgressReport_...xlsx)",
    )
    app ._master_pr1_picker .pack (fill ="x",pady =3 )

    app ._master_mid_picker =FilePickerRow (
    mf ,label ="Midterm:",
    filetypes =[("Excel Files","*.xlsx"),("All Files","*.*")],
    tooltip ="Midterm output workbook (MidtermSort_...xlsx)",
    )
    app ._master_mid_picker .pack (fill ="x",pady =3 )

    app ._master_pr2_picker =FilePickerRow (
    mf ,label ="Progress Report 2:",
    filetypes =[("Excel Files","*.xlsx"),("All Files","*.*")],
    tooltip ="PR2 output workbook (ProgressReport_...xlsx)",
    )
    app ._master_pr2_picker .pack (fill ="x",pady =3 )

    app ._master_output_picker =FilePickerRow (
    mf ,label ="Output Folder:",
    filetypes =[],is_directory =True ,
    tooltip ="Where the master report will be saved",
    )
    app ._master_output_picker .pack (fill ="x",pady =3 )
    app ._master_output_picker .path =str (OUTPUT_DIR )

    master_btn_frame =tk .Frame (outer ,bg =theme.PANEL_BG )
    master_btn_frame .pack (fill ="x",pady =(10 ,0 ))

    RoundedButton (
    master_btn_frame ,text ="Generate Master Season Report",
    command =app ._on_generate_master_report ,
    **theme.BTN_SUCCESS_STYLE ,font =theme.FONT_BOLD ,padx =20 ,pady =9 ,
    ).pack (side ="left")

    ttk .Separator (outer ,orient ="horizontal").pack (fill ="x",pady =10 )

    section_label (outer ,"Processing Log").pack (fill ="x",pady =(4 ,4 ))

    app ._trend_log_box =scrolledtext .ScrolledText (
    outer ,height =8 ,font =theme.FONT_MONO ,
    bg ="#0A1628",fg ="#C8D6E8",
    relief ="flat",wrap ="word",
    )
    app ._trend_log_box .pack (fill ="both",expand =True )
    app ._trend_log_box .config (state ="disabled")
    app ._trend_log_box .bind ("<Enter>",_wheel_off4 )
    app ._trend_log_box .bind ("<Leave>",_wheel_on4 )
    configure_log_tags(app._trend_log_box, PURPLE_LOG_TAGS)

