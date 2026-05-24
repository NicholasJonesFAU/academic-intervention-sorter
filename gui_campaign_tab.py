"""Campaign/Semester Manager tab UI builder."""

import tkinter as tk
from tkinter import ttk

import gui_theme as theme
from gui_widgets import section_label, RoundedButton


def build_campaign_tab(app):
    """Build the redesigned Campaigns / Semester Manager tab."""
    self = app
    tab =self ._campaign_tab 
    outer ,_wheel_on5 ,_wheel_off5 =self ._make_scrollable_tab (tab )

    # ── Active semester header ────────────────────────────────
    self ._sem_header_frame =tk .Frame (outer ,bg =theme.PANEL_BG )
    self ._sem_header_frame .pack (fill ="x",pady =(0 ,12 ))

    self ._sem_name_label =tk .Label (
    self ._sem_header_frame ,text ="No Active Semester",
    bg =theme.PANEL_BG ,fg =theme.TEXT_FG ,font =theme.FONT_HEADER ,
    )
    self ._sem_name_label .pack (side ="left")

    self ._sem_status_label =tk .Label (
    self ._sem_header_frame ,text ="",
    bg =theme.PANEL_BG ,fg =theme.TEXT_MUTED ,font =theme.FONT_MAIN ,
    )
    self ._sem_status_label .pack (side ="left",padx =(12 ,0 ))

    ttk .Separator (outer ,orient ="horizontal").pack (fill ="x",pady =(0 ,12 ))

    # ── Checkpoint cards ──────────────────────────────────────
    section_label (outer ,"Checkpoints").pack (fill ="x",pady =(0 ,8 ))

    self ._checkpoint_frames ={}
    cards_frame =tk .Frame (outer ,bg =theme.PANEL_BG )
    cards_frame .pack (fill ="x",pady =(0 ,12 ))

    from utils .config import SEMESTER_CHECKPOINTS 
    colors =[theme.NAVY ,"#1A6B3C","#9B2226"]
    for i ,cp_name in enumerate (SEMESTER_CHECKPOINTS ):
        card =tk .Frame (cards_frame ,bg ="#ffffff",bd =1 ,relief ="solid",
        padx =16 ,pady =12 )

        card .grid (row =0 ,column =i ,padx =(0 ,12 ),sticky ="nsew")
        cards_frame .columnconfigure (i ,weight =1 )

        tk .Label (card ,text =cp_name ,bg ="white",fg =theme.TEXT_FG ,
        font =theme.FONT_BOLD ).pack (anchor ="w")

        status_lbl =tk .Label (card ,text ="Not Started",bg ="white",
        fg =theme.TEXT_MUTED ,font =theme.FONT_MAIN )
        status_lbl .pack (anchor ="w",pady =(4 ,0 ))

        runs_lbl =tk .Label (card ,text ="",bg ="white",
        fg =theme.TEXT_MUTED ,font =theme.FONT_SUB )
        runs_lbl .pack (anchor ="w")

        students_lbl =tk .Label (card ,text ="",bg ="white",
        fg =theme.TEXT_MUTED ,font =theme.FONT_SUB )
        students_lbl .pack (anchor ="w")

        # Mark Complete / Reset buttons
        btn_frame =tk .Frame (card ,bg ="white")
        btn_frame .pack (anchor ="w",pady =(8 ,0 ))

        complete_btn =RoundedButton (
        btn_frame ,text ="Mark Complete",
        bg =colors [i ],fg =theme.WHITE ,font =theme.FONT_SUB ,padx =8 ,pady =4 ,
        command =lambda n =cp_name :self ._on_mark_checkpoint_complete (n ),
        )
        complete_btn .pack (side ="left",padx =(0 ,6 ))

        reset_btn =RoundedButton (
        btn_frame ,text ="Reset",
        **theme.BTN_MUTED_STYLE ,font =theme.FONT_SUB ,padx =8 ,pady =4 ,
        command =lambda n =cp_name :self ._on_reset_checkpoint (n ),
        )
        reset_btn .pack (side ="left")

        self ._checkpoint_frames [cp_name ]={
        "card":card ,
        "status":status_lbl ,
        "runs":runs_lbl ,
        "students":students_lbl ,
        "complete_btn":complete_btn ,
        "reset_btn":reset_btn ,
        "color":colors [i ],
        }

    ttk .Separator (outer ,orient ="horizontal").pack (fill ="x",pady =12 )

    # ── Group configuration ───────────────────────────────────
    grp_header =tk .Frame (outer ,bg =theme.PANEL_BG )
    grp_header .pack (fill ="x",pady =(0 ,6 ))
    section_label (grp_header ,"Groups").pack (side ="left")
    tk .Label (
    grp_header ,
    text ="Priority order — first match wins each run",
    bg =theme.PANEL_BG ,fg =theme.TEXT_MUTED ,font =theme.FONT_SUB ,
    ).pack (side ="left",padx =(12 ,0 ))

    # Scrollable group list container
    self ._groups_list_frame =tk .Frame (outer ,bg =theme.PANEL_BG )
    self ._groups_list_frame .pack (fill ="x")

    # Empty-state label shown when no groups are configured
    self ._groups_empty_lbl =tk .Label (
    self ._groups_list_frame ,
    text ="No groups configured — add groups below or use a control file.",
    bg =theme.PANEL_BG ,fg =theme.TEXT_MUTED ,font =theme.FONT_SUB ,
    )
    self ._groups_empty_lbl .pack (anchor ="w",pady =(4 ,8 ))

    # Buttons below the list
    grp_btn_frame =tk .Frame (outer ,bg =theme.PANEL_BG )
    grp_btn_frame .pack (fill ="x",pady =(6 ,0 ))

    RoundedButton (
    grp_btn_frame ,text ="+ Add Group",
    **theme.BTN_PRIMARY ,font =theme.FONT_BOLD ,padx =14 ,pady =7 ,
    command =self ._on_add_group ,
    ).pack (side ="left",padx =(0 ,8 ))

    RoundedButton (
    grp_btn_frame ,text ="Copy from Previous Semester",
    **theme.BTN_MUTED_STYLE ,font =theme.FONT_MAIN ,padx =12 ,pady =7 ,
    command =self ._on_copy_previous_groups ,
    ).pack (side ="left")

    ttk .Separator (outer ,orient ="horizontal").pack (fill ="x",pady =12 )

    # ── Semester actions ──────────────────────────────────────
    section_label (outer ,"Semester Actions").pack (fill ="x",pady =(0 ,8 ))

    action_frame =tk .Frame (outer ,bg =theme.PANEL_BG )
    action_frame .pack (fill ="x",pady =(0 ,12 ))

    self ._new_sem_btn =RoundedButton (
    action_frame ,text ='Start New Semester',
    command =self ._on_new_semester ,
    **theme.BTN_PRIMARY ,font =theme.FONT_BOLD ,padx =16 ,pady =9 ,
    )
    self ._new_sem_btn .pack (side ="left",padx =(0 ,8 ))

    self ._complete_sem_btn =RoundedButton (
    action_frame ,text ='Complete Semester',
    command =self ._on_complete_semester ,
    **theme.BTN_SUCCESS_STYLE ,font =theme.FONT_MAIN ,padx =14 ,pady =8 ,
    )
    self ._complete_sem_btn .pack (side ="left",padx =(0 ,8 ))

    self ._reset_sem_btn =RoundedButton (
    action_frame ,text ='Reset Semester',
    command =self ._on_reset_semester ,
    **theme.BTN_DANGER ,font =theme.FONT_MAIN ,padx =14 ,pady =8 ,
    )
    self ._reset_sem_btn .pack (side ="left",padx =(0 ,8 ))

    RoundedButton (
    action_frame ,text ="Refresh",
    **theme.BTN_MUTED_STYLE ,font =theme.FONT_MAIN ,padx =14 ,pady =9 ,
    command =self ._refresh_semester_tab ,
    ).pack (side ="left")

    ttk .Separator (outer ,orient ="horizontal").pack (fill ="x",pady =12 )

    # ── History ───────────────────────────────────────────────
    section_label (outer ,"Semester History").pack (fill ="x",pady =(0 ,6 ))

    hist_frame =tk .Frame (outer ,bg =theme.PANEL_BG )
    hist_frame .pack (fill ="both",expand =True )

    cols =("Semester","Status","Created","Completed",
    "PR1","Midterm","PR2","Master Report")
    self ._history_tree =ttk .Treeview (
    hist_frame ,columns =cols ,show ="headings",height =8 
    )
    widths =[160 ,90 ,150 ,150 ,90 ,90 ,90 ,200 ]
    for col ,w in zip (cols ,widths ):
        self ._history_tree .heading (col ,text =col )
        self ._history_tree .column (col ,width =w ,anchor ="center")
    self ._history_tree .column ("Semester",anchor ="w")
    self ._history_tree .column ("Master Report",anchor ="w")

    vsb =ttk .Scrollbar (hist_frame ,orient ="vertical",
    command =self ._history_tree .yview )
    self ._history_tree .configure (yscrollcommand =vsb .set )
    self ._history_tree .pack (side ="left",fill ="both",expand =True )
    vsb .pack (side ="right",fill ="y")
    self ._history_tree .bind ("<Enter>",_wheel_off5 )
    self ._history_tree .bind ("<Leave>",_wheel_on5 )

    # Initial refresh
    self ._refresh_semester_tab ()

    # ------------------------------------------------------------------
    # Semester tab methods
    # ------------------------------------------------------------------

    # ── Group list UI helpers ──────────────────────────────────────

