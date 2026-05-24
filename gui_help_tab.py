"""Help/About tab UI builder for Academic Intervention Sorter."""

import tkinter as tk
from tkinter import ttk

import gui_theme as theme
from utils.config import APP_NAME, APP_VERSION


def build_help_tab(self):
    app = self
    """Build the Help/About tab."""
    outer =tk .Frame (self ._help_tab ,bg =theme.PANEL_BG ,padx =24 ,pady =16 )
    outer .pack (fill ="both",expand =True )

    # Header
    tk .Label (outer ,text =f"{APP_NAME }  —  Version {APP_VERSION }",
    bg =theme.PANEL_BG ,fg ="#1a1f2e",font =theme.FONT_HEADER ).pack (anchor ="w")
    tk .Label (outer ,text ="Academic Advising Intervention Workflow Tool",
    bg =theme.PANEL_BG ,fg =theme.TEXT_MUTED ,font =theme.FONT_MAIN ).pack (anchor ="w",pady =(2 ,16 ))

    ttk .Separator (outer ,orient ="horizontal").pack (fill ="x",pady =(0 ,16 ))

    # Scrollable help content
    canvas =tk .Canvas (outer ,bg =theme.PANEL_BG ,highlightthickness =0 )
    scrollbar =ttk .Scrollbar (outer ,orient ="vertical",command =canvas .yview )
    canvas .configure (yscrollcommand =scrollbar .set )
    scrollbar .pack (side ="right",fill ="y")
    canvas .pack (side ="left",fill ="both",expand =True )

    inner =tk .Frame (canvas ,bg =theme.PANEL_BG )
    canvas_window =canvas .create_window ((0 ,0 ),window =inner ,anchor ="nw")
    inner .bind ("<Configure>",lambda e :canvas .configure (scrollregion =canvas .bbox ("all")))
    canvas .bind ("<Configure>",lambda e :canvas .itemconfig (canvas_window ,width =e .width ))

    def _help_wheel (e ):
        canvas .yview_scroll (int (-1 *(e .delta /120 )),"units")
    canvas .bind ("<Enter>",lambda e :canvas .bind_all ("<MouseWheel>",_help_wheel ))
    canvas .bind ("<Leave>",lambda e :canvas .unbind_all ("<MouseWheel>"))
    inner .bind ("<Enter>",lambda e :canvas .bind_all ("<MouseWheel>",_help_wheel ))

    def section (title ,color =theme.NAVY ):
        tk .Label (inner ,text =title ,bg =color ,fg ="white",
        font =theme.FONT_BOLD ,padx =8 ,pady =5 ,
        anchor ="w").pack (fill ="x",pady =(12 ,4 ))

    def para (text ,indent =0 ):
        tk .Label (inner ,text =text ,bg =theme.PANEL_BG ,fg =theme.TEXT_FG ,
        font =theme.FONT_MAIN ,wraplength =680 ,justify ="left",
        padx =indent ).pack (anchor ="w",pady =1 )

    def item (text ):
        tk .Label (inner ,text =f"  •  {text }",bg =theme.PANEL_BG ,fg =theme.TEXT_FG ,
        font =theme.FONT_MAIN ,wraplength =660 ,justify ="left").pack (anchor ="w")

    section ("📋  Progress Report Sorter",theme.NAVY )
    para ("Loads your Navigate/EAB progress report export, filters at-risk students, "
    "aggregates courses per student, and sorts them into prioritized intervention groups.")
    item ("Supports .xlsx and .csv input files")
    item ("First-match-wins group assignment — priority set by control file order")
    item ("Unmatched students go to Risk_1_2 or Risk_3_Plus buckets")
    item ("Pre-Run Check validates files before committing to a full run")
    item ("Exclude previously assigned students using the checkbox")
    item ("Group Selection dialog lets you choose which groups to produce per run")

    section ("📝  Midterm Sorter","#4A235A")
    para ("Loads your Canvas midterm grade export and flags students with C- or below "
    "(C-, D+, D, D-, F). Uses the same group matching logic as the Progress Report Sorter.")
    item ("Accepts .xlsx and .csv files")
    item ("At-risk threshold: C- or lower only — W, WM excluded by design")
    item ("Course number built from prefix + number columns (e.g. MAC + 1105 = MAC1105)")

    section ("📊  Faculty Report Status","#843C0C")
    para ("Analyzes which professors have submitted progress reports. Upload the campaign "
    "export from Navigate and the department/college mapping file.")
    item ("Shows completion % by college, department, and individual professor")
    item ("Charts included: donut (overall), bar charts by college and department")
    item ("Faculty_Download tab lists all faculty with contact info")
    item ("Accepts .xlsx and .csv files")

    section ("📈  Campaign Trend","#375623")
    para ("Select your three output workbooks (PR1, Midterm, PR2) to analyze how the "
    "at-risk population moved across the semester.")
    item ("Student trajectories: Persistent, Recovered Early, Recovered Late, Relapsed, etc.")
    item ("Flow analysis: carried forward, recovered, and new students at each transition")
    item ("By Group breakdown across all three checkpoints")
    item ("Master Season Report: combined end-of-semester workbook with student list")

    section ("🗂️  Campaign Manager","#1F3864")
    para ("Manages the full semester lifecycle. Create a semester, track PR1/Midterm/PR2 "
    "progress, and complete it when done.")
    item ("File paths (contact, control, group folder) saved on first run — pre-fill all subsequent runs")
    item ("Output files automatically organized into semester subfolders")
    item ("Mark Complete and Reset buttons per checkpoint")
    item ("Complete Semester generates the Master Season Report automatically")
    item ("Full history of past semesters preserved")

    section ("⚙️  Settings","#546E7A")
    para ("Update column names for all four file types without editing any Python files. "
    "Changes save to settings.json and take effect on next run.")
    item ("Progress Report columns (Navigate/EAB export)")
    item ("Contact Report columns (student contact export)")
    item ("Midterm Grade columns (Canvas export)")
    item ("Faculty Report Status columns (Navigate campaign export)")

    section ("📁  Output Files","#2F5496")
    para ("All output files are saved to semester-named subfolders in your output folder "
    "(e.g. output/Fall_2026/). Each workbook includes:")
    item ("Data tabs: one per group + Risk_1_2 + Risk_3_Plus")
    item ("Summary tab with charts: students by group, contact coverage, risk distribution")
    item ("Missing_Contacts tab: students with no phone or email found")
    item ("QA_Log tab: data quality events for institutional auditing")
    item ("Processing_Manifest tab: run metadata for reproducibility")

    section ("❓  Common Questions","#00695C")
    para ("Column names don't match?",)
    para ("  → Go to the Settings tab and update the column name for that field.",indent =16 )
    para ("Students not appearing in output?")
    para ("  → Check the Pre-Run Check button — it will identify missing column issues.",indent =16 )
    para ("Want to rerun a checkpoint from scratch?")
    para ("  → Use Reset Checkpoint in the Campaigns tab to clear the assigned list.",indent =16 )
    para ("Starting a new semester?")
    para ("  → Complete or Reset the current semester in the Campaigns tab first.",indent =16 )

    ttk .Separator (inner ,orient ="horizontal").pack (fill ="x",pady =(20 ,8 ))
    tk .Label (inner ,
    text =f"Built for FAU Academic Advising  •  v{APP_VERSION }  •  "
    f"Python + pandas + openpyxl + matplotlib",
    bg =theme.PANEL_BG ,fg =theme.TEXT_MUTED ,font =theme.FONT_SUB ).pack (anchor ="w")

