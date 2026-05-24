"""Settings tab UI builder for Academic Intervention Sorter."""

import tkinter as tk
from tkinter import ttk

import gui_theme as theme
from gui_widgets import RoundedButton
from utils.settings_manager import get_settings


def build_settings_tab(self):
    app = self
    """Build the Settings tab — column mapping editor for all file types."""
    tab =self ._settings_tab 
    settings =get_settings ()

    canvas =tk .Canvas (tab ,bg =theme.PANEL_BG ,highlightthickness =0 )
    scrollbar =ttk .Scrollbar (tab ,orient ="vertical",command =canvas .yview )
    canvas .configure (yscrollcommand =scrollbar .set )
    scrollbar .pack (side ="right",fill ="y")
    canvas .pack (side ="left",fill ="both",expand =True )

    inner =tk .Frame (canvas ,bg =theme.PANEL_BG ,padx =24 ,pady =16 )
    canvas_window =canvas .create_window ((0 ,0 ),window =inner ,anchor ="nw")

    def on_configure (e ):
        canvas .configure (scrollregion =canvas .bbox ("all"))
        canvas .itemconfig (canvas_window ,width =canvas .winfo_width ())
    inner .bind ("<Configure>",on_configure )
    canvas .bind ("<Configure>",lambda e :canvas .itemconfig (canvas_window ,width =e .width ))

    def _settings_wheel (e ):
        canvas .yview_scroll (int (-1 *(e .delta /120 )),"units")
    canvas .bind ("<Enter>",lambda e :canvas .bind_all ("<MouseWheel>",_settings_wheel ))
    canvas .bind ("<Leave>",lambda e :canvas .unbind_all ("<MouseWheel>"))
    inner .bind ("<Enter>",lambda e :canvas .bind_all ("<MouseWheel>",_settings_wheel ))

    self ._setting_vars ={}

    def add_section (parent ,title ,color ,subtitle =""):
        tk .Label (parent ,text =title ,bg =color ,fg ="white",
        font =theme.FONT_BOLD ,padx =8 ,pady =6 ,
        anchor ="w").pack (fill ="x",pady =(16 ,2 ))
        if subtitle :
            tk .Label (parent ,text =subtitle ,bg =theme.PANEL_BG ,fg =theme.TEXT_MUTED ,
            font =theme.FONT_SUB ).pack (anchor ="w",pady =(0 ,4 ))

    def add_field (parent ,key ,label ,value ,tooltip =""):
        row =tk .Frame (parent ,bg =theme.PANEL_BG )
        row .pack (fill ="x",pady =2 )
        tk .Label (row ,text =label ,bg =theme.PANEL_BG ,fg =theme.TEXT_FG ,
        font =theme.FONT_MAIN ,width =30 ,anchor ="w").pack (side ="left")
        var =tk .StringVar (value =value )
        self ._setting_vars [key ]=var 
        entry =tk .Entry (row ,textvariable =var ,font =theme.FONT_MAIN ,
        width =36 ,relief ="flat",bg ="white",
        highlightthickness =1 ,highlightbackground ="#B0BEC5",
        insertbackground =theme.TEXT_FG )
        entry .pack (side ="left",ipady =3 )
        if tooltip :
            tk .Label (row ,text =f"  {tooltip }",bg =theme.PANEL_BG ,
            fg =theme.TEXT_MUTED ,font =theme.FONT_SUB ).pack (side ="left")

            # ── Progress Report ───────────────────────────────────────
    add_section (inner ,"📋  Progress Report — Column Names",theme.NAVY ,
    "Column headers from your Navigate/EAB progress report export")
    pm =settings .progress_report_map 
    for key ,label ,tip in [
    ("student_name","Student Name","Full student name"),
    ("student_id","Student ID","Z-number column"),
    ("course_number","Course Number","e.g. MAC1105"),
    ("course","Course Name","Full course title"),
    ("at_risk","At-Risk Flag","Column with Yes/No/True/False"),
    ("letter_grade","Grade","Progress report grade column"),
    ("absences","Absences","Number of absences"),
    ("alert_reasons","Alert Reasons",""),
    ("comments","Comments","Professor free-text comments"),
    ]:
        add_field (inner ,f"progress.{key }",label ,pm .get (key ,""),tip )

        # ── Contact Report ────────────────────────────────────────
    add_section (inner ,"📇  Contact Report — Column Names","#375623",
    "Column headers from your student contact export")
    cm =settings .contact_report_map 
    for key ,label ,tip in [
    ("student_id","Student ID","Must match progress report ID column"),
    ("phone_cellular","Cellular Phone","First preference for outreach"),
    ("phone_local","Local Phone","Second preference"),
    ("phone_permanent","Permanent Phone","Third preference"),
    ("email","Email","Student email column"),
    ]:
        add_field (inner ,f"contact.{key }",label ,cm .get (key ,""),tip )

        # ── Midterm Grade Report ──────────────────────────────────
    add_section (inner ,"📝  Midterm Grade File — Column Names","#4A235A",
    "Column headers from your Canvas midterm grade export")
    mm =settings .midterm_map 
    for key ,label ,tip in [
    ("student_id","Student ID","Z# column"),
    ("last_name","Last Name",""),
    ("first_name","First Name",""),
    ("email","Email","FAU email column"),
    ("college","College",""),
    ("major","Major",""),
    ("classification","Classification","e.g. Freshman, Sophomore"),
    ("course_prefix","Course Prefix","e.g. MAC, ENC"),
    ("course_number","Course Number","Numeric part, e.g. 1105"),
    ("course_name","Course Name","Full course title"),
    ("section","Section Number",""),
    ("credit_hrs","Credit Hours",""),
    ("midterm_grade","Midterm Grade","Column containing letter grades"),
    ]:
        add_field (inner ,f"midterm.{key }",label ,mm .get (key ,""),tip )

        # ── Faculty Report Status ─────────────────────────────────
    add_section (inner ,"📊  Faculty Report Status — Column Names","#843C0C",
    "Column headers from your Navigate progress report campaign export")
    fm =settings .faculty_map 
    for key ,label ,tip in [
    ("first_name","Professor First Name","Professor Requested First Name"),
    ("last_name","Professor Last Name","Professor Requested Last Name"),
    ("email","Professor Email","Professor email column"),
    ("course_number","Course Number","Used to map to department/college"),
    ("section_name","Section Name","Course section identifier"),
    ("responded","Responded Flag","Column with Yes/No submission status"),
    ]:
        add_field (inner ,f"faculty.{key }",label ,fm .get (key ,""),tip )

        # ── Buttons ───────────────────────────────────────────────
    btn_row =tk .Frame (inner ,bg =theme.PANEL_BG )
    btn_row .pack (fill ="x",pady =(20 ,8 ))

    RoundedButton (btn_row ,text ="Save Settings",
    **theme.BTN_PRIMARY ,font =theme.FONT_BOLD ,padx =20 ,pady =9 ,
    command =self ._on_save_settings ).pack (side ="left",padx =(0 ,10 ))

    RoundedButton (btn_row ,text ="Reset to Defaults",
    **theme.BTN_DANGER ,font =theme.FONT_MAIN ,padx =14 ,pady =9 ,
    command =self ._on_reset_settings ).pack (side ="left")

    self ._settings_status =tk .Label (
    inner ,text ="",bg =theme.PANEL_BG ,fg =theme.SUCCESS_COLOR ,font =theme.FONT_MAIN 
    )
    self ._settings_status .pack (anchor ="w",pady =(8 ,0 ))



