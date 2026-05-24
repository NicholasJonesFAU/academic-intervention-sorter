"""
main.py — Tkinter GUI entry point for the Academic Intervention Sorter.

Architecture:
  - GUI is completely decoupled from business logic
  - All processing is delegated to PipelineController
  - GUI only handles file selection, progress display, and result reporting
"""

import sys 
import threading 
import traceback 
from pathlib import Path 
import tkinter as tk 
from tkinter import ttk ,filedialog ,messagebox ,scrolledtext 
from gui_widgets import section_label ,RoundedButton ,FilePickerRow 
from gui_dialogs import show_group_selection_dialog, ensure_season_set, show_new_semester_dialog
from gui_logging import append_log, clear_log, configure_log_tags, PURPLE_LOG_TAGS
from gui_progress_tab import build_progress_report_sorter_tab
from gui_report_status_tab import build_report_status_tab
from gui_report_status_actions import run_report_status, handle_report_status_complete
from gui_midterm_tab import build_midterm_tab
from gui_trend_tab import build_trend_tab
from gui_trend_actions import run_trend_report, generate_master_report, handle_trend_complete, handle_master_report_done
from gui_campaign_tab import build_campaign_tab
from gui_settings_tab import build_settings_tab
from gui_help_tab import build_help_tab
from gui_midterm_actions import run_midterm_sort, handle_midterm_complete, handle_midterm_error
from gui_progress_actions import (
    on_run_progress,
    on_validate_progress,
    on_prerun_check_progress,
    show_precheck_results,
    on_clear_progress,
    collect_progress_inputs,
    start_progress_processing,
    on_progress_complete,
    on_progress_error,
    set_progress_buttons_state,
)

# Ensure the app root is on sys.path
sys .path .insert (0 ,str (Path (__file__ ).parent ))

from processors .pipeline_controller import PipelineController ,PipelineInputs ,PipelineResult 
from processors .midterm_pipeline_controller import MidtermPipelineController ,MidtermPipelineInputs 
from processors .trend_analyzer import TrendAnalyzer 
from processors .campaign_manager import CampaignManager 
from processors .semester_manager import SemesterManager ,SEMESTER_STATUS_ACTIVE 
from processors .season_report import SeasonReportGenerator 
from processors .prerun_checker import PreRunChecker 
from processors .summary_enhancer import SummaryEnhancer 
from processors .trend_exporter import TrendExporter 
from utils .settings_manager import get_settings ,reload_settings ,SETTINGS_PATH 
from processors .report_status_processor import ReportStatusProcessor 
from processors .report_status_exporter import ReportStatusExporter 
from processors .department_mapper import DepartmentMapper 
from utils .config import APP_NAME ,APP_VERSION ,OUTPUT_DIR 
from utils .logging_utils import setup_logger 

logger =setup_logger ("intervention_sorter")


import gui_theme as theme 

class InterventionSorterApp (tk .Tk ):
    """Main application window."""

    def __init__ (self ):
        super ().__init__ ()
        self .title (f"{APP_NAME }  v{APP_VERSION }")
        self .geometry ("900x780")
        self .minsize (800 ,640 )
        self .configure (bg =theme.NAVY )
        self .resizable (True ,True )

        self ._processing =False 
        # Load Inter font
        theme .FONT_FAMILY =theme .load_inter_fonts ()
        theme .apply_font (theme .FONT_FAMILY )

        self ._processing =False 
        self ._midterm_processing =False 
        self ._trend_processing =False 
        self ._semester_mgr =SemesterManager ()
        self ._exclude_var =tk .BooleanVar (value =False )
        self ._midterm_exclude_var =tk .BooleanVar (value =False )
        self ._build_ui ()
        self ._set_defaults ()
        self .after (200 ,self ._check_semester_on_startup )
        self ._report_processing =False 

        logger .info ("GUI initialized: %s v%s",APP_NAME ,APP_VERSION )

        # ------------------------------------------------------------------
        # Scroll area helpers
        # ------------------------------------------------------------------

    @staticmethod 
    def _make_scrollable_tab (parent :tk .Widget ,padx :int =24 ,pady :int =16 ):
        """
        Wrap a tab in a vertically scrollable canvas.

        Returns (inner_frame, activate_fn, deactivate_fn) where:
          inner_frame   — pack/grid content into this
          activate_fn   — call to enable mousewheel scroll (bind to canvas <Enter>)
          deactivate_fn — call to disable mousewheel scroll (bind to canvas <Leave>
                          and also to any ScrolledText <Enter> inside the tab)

        Usage:
            inner, on, off = self._make_scrollable_tab(tab)
            # ... build content inside inner ...
            self._log_box.bind("<Enter>", lambda e: off())
            self._log_box.bind("<Leave>", lambda e: on())
        """
        canvas =tk .Canvas (parent ,bg =theme.PANEL_BG ,highlightthickness =0 )
        vsb =ttk .Scrollbar (parent ,orient ="vertical",command =canvas .yview )
        canvas .configure (yscrollcommand =vsb .set )
        vsb .pack (side ="right",fill ="y")
        canvas .pack (side ="left",fill ="both",expand =True )

        inner =tk .Frame (canvas ,bg =theme.PANEL_BG ,padx =padx ,pady =pady )
        win_id =canvas .create_window ((0 ,0 ),window =inner ,anchor ="nw")

        def _resize (e =None ):
            canvas .configure (scrollregion =canvas .bbox ("all"))
            canvas .itemconfig (win_id ,width =canvas .winfo_width ())

        inner .bind ("<Configure>",_resize )
        canvas .bind ("<Configure>",lambda e :canvas .itemconfig (win_id ,width =e .width ))

        def _wheel (e ):
            canvas .yview_scroll (int (-1 *(e .delta /120 )),"units")

        def activate (e =None ):
            canvas .bind_all ("<MouseWheel>",_wheel )

        def deactivate (e =None ):
            canvas .unbind_all ("<MouseWheel>")

        canvas .bind ("<Enter>",activate )
        canvas .bind ("<Leave>",deactivate )

        return inner ,activate ,deactivate 

        # ------------------------------------------------------------------
        # UI Construction
        # ------------------------------------------------------------------

    def _build_ui (self ):
    # ── Header banner ──────────────────────────────────────────
        header =tk .Frame (self ,bg =theme.NAVY )
        header .pack (fill ="x")

        # Red accent top stripe
        tk .Frame (header ,bg =theme.RED_ACCENT ,height =4 ).pack (fill ="x")

        # Content row
        header_inner =tk .Frame (header ,bg =theme.NAVY_DARK ,pady =14 ,padx =20 )
        header_inner .pack (fill ="x")

        # Left: App name
        tk .Label (
        header_inner ,text =APP_NAME .upper (),
        bg =theme.NAVY_DARK ,fg =theme.WHITE ,
        font =(theme.FONT_HEADER [0 ],14 ,"bold"),
        ).pack (side ="left")

        tk .Label (
        header_inner ,text ="  |  Academic Advising Intervention Workflow",
        bg =theme.NAVY_DARK ,fg ="#A0B4CC",
        font =theme.FONT_MAIN ,
        ).pack (side ="left")

        # Right: Version badge
        ver_frame =tk .Frame (header_inner ,bg =theme.RED_ACCENT ,padx =8 ,pady =2 )
        ver_frame .pack (side ="right")
        tk .Label (
        ver_frame ,text =f"v{APP_VERSION }",
        bg =theme.RED_ACCENT ,fg =theme.NAVY_DARK ,
        font =(theme.FONT_MAIN [0 ],9 ,"bold"),
        ).pack ()

        # Red accent bottom stripe
        tk .Frame (header ,bg =theme.RED_ACCENT ,height =2 ).pack (fill ="x")

        # ── Notebook tabs ──────────────────────────────────────────
        style =ttk .Style ()
        style .theme_use ("clam")

        # Notebook container
        style .configure ("TNotebook",
        background =theme.NAVY ,
        borderwidth =0 ,
        tabmargins =[2 ,4 ,0 ,0 ],
        )
        # Inactive tabs
        style .configure ("TNotebook.Tab",
        font =(theme.FONT_BOLD [0 ],theme.FONT_BOLD [1 ],"bold"),
        padding =[18 ,8 ],
        background =theme.NAVY_DARK ,
        foreground ="#A0B4CC",
        borderwidth =0 ,
        )
        # Active tab
        style .map ("TNotebook.Tab",
        background =[("selected",theme.PANEL_BG ),("active",theme.NAVY_DARK )],
        foreground =[("selected",theme.NAVY ),("active",theme.WHITE )],
        expand =[("selected",[1 ,1 ,1 ,0 ])],
        )
        # Separator styling
        style .configure ("TSeparator",background =theme.BORDER )

        # Scrollbar
        style .configure ("TScrollbar",
        background =theme.PANEL_BG_DARK ,
        troughcolor =theme.PANEL_BG ,
        borderwidth =0 ,
        arrowcolor =theme.NAVY ,
        )

        # Progressbar
        style .configure ("TProgressbar",
        background =theme.RED_ACCENT ,
        troughcolor =theme.PANEL_BG_DARK ,
        borderwidth =0 ,
        )

        notebook =ttk .Notebook (self ,style ="TNotebook")
        notebook .pack (fill ="both",expand =True ,padx =0 ,pady =0 )

        # Tab 1: Intervention Sorter
        tab1 =tk .Frame (notebook ,bg =theme.PANEL_BG )
        notebook .add (tab1 ,text ="  Progress Report Sorter  ")

        # Tab 2: Faculty Report Status
        tab2 =tk .Frame (notebook ,bg =theme.PANEL_BG )
        notebook .add (tab2 ,text ="  Faculty Report Status  ")

        # Tab 3: Midterm Sorter
        tab3 =tk .Frame (notebook ,bg =theme.PANEL_BG )
        notebook .add (tab3 ,text ="  Midterm Sorter  ")
        self ._midterm_tab =tab3 

        # Tab 4: Campaign Trend
        tab4 =tk .Frame (notebook ,bg =theme.PANEL_BG )
        notebook .add (tab4 ,text ="  Campaign Trend  ")
        self ._trend_tab =tab4 

        # Tab 5: Campaign Manager
        tab5 =tk .Frame (notebook ,bg =theme.PANEL_BG )
        notebook .add (tab5 ,text ="  Campaigns  ")
        self ._campaign_tab =tab5 

        # Tab 6: Settings
        tab6 =tk .Frame (notebook ,bg =theme.PANEL_BG )
        notebook .add (tab6 ,text ="  Settings  ")
        self ._settings_tab =tab6 

        # Tab 7: Help
        tab7 =tk .Frame (notebook ,bg =theme.PANEL_BG )
        notebook .add (tab7 ,text ="  Help  ")
        self ._help_tab =tab7 

        build_progress_report_sorter_tab(self, tab1)

        # ------------------------------------------------------------------
        # Actions
        # ------------------------------------------------------------------

    def _show_group_selection_dialog(self, control_path: str, group_dir: str, checkpoint_name: str) -> tuple:
        return show_group_selection_dialog(self, control_path, group_dir, checkpoint_name)

    def _ensure_season_set(self) -> bool:
        return ensure_season_set(self)

    def _on_run(self):
        return on_run_progress(self)
    def _on_validate(self):
        return on_validate_progress(self)
    def _on_prerun_check(self):
        return on_prerun_check_progress(self)
    def _show_precheck_results(self, results):
        return show_precheck_results(self, results)
    def _on_clear(self):
        return on_clear_progress(self)
    def _collect_inputs(self):
        return collect_progress_inputs(self)
    def _start_processing(self, inputs, validate_only):
        return start_progress_processing(self, inputs, validate_only)
    def _on_complete(self, result):
        return on_progress_complete(self, result)
    def _on_error(self, error_text: str):
        return on_progress_error(self, error_text)
    def _log (self ,message :str ,tag :str ="info"):
        append_log(self._log_box, message, tag)

    def _set_buttons_state(self, state: str):
        return set_progress_buttons_state(self, state)
    def _set_defaults (self ):
        """Pre-fill output folder to the default output directory."""
        self ._output_picker .path =str (OUTPUT_DIR )
        self ._build_report_status_tab ()
        self ._build_midterm_tab ()
        self ._build_trend_tab ()
        self ._build_campaign_tab ()
        self ._build_settings_tab ()
        self ._build_help_tab ()

    def _build_report_status_tab(self):
        """Build the Faculty Report Status tab UI."""
        build_report_status_tab(self)

    def _on_run_report_status(self):
        return run_report_status(self)

    def _on_report_complete(self, success: bool, message: str, overall: dict):
        return handle_report_status_complete(self, success, message, overall)



    def _build_midterm_tab(self):
        """Build the Midterm Sorter tab UI."""
        build_midterm_tab(self)

    def _on_run_midterm(self):
        run_midterm_sort(self)

    def _on_midterm_complete(self, result):
        handle_midterm_complete(self, result)

    def _on_midterm_error(self, error_text: str):
        handle_midterm_error(self, error_text)

    def _midterm_clear_log(self):
        clear_log(self._midterm_log_box)

    def _midterm_log_write(self, message: str, tag: str = "info"):
        append_log(self._midterm_log_box, message, tag)


    def _build_trend_tab(self):
        build_trend_tab(self)

    def _on_run_trend(self):
        run_trend_report(self)

    def _on_generate_master_report(self):
        generate_master_report(self)

    def _on_master_report_done(self, success, message):
        handle_master_report_done(self, success, message)

    def _on_trend_complete(self, success, message, overall):
        handle_trend_complete(self, success, message, overall)

    def _trend_clear_log(self):
        clear_log(self._trend_log_box)

    def _trend_log_write(self, message, tag="info"):
        append_log(self._trend_log_box, message, tag)


    def _build_campaign_tab(self):
        build_campaign_tab(self)

    def _rebuild_groups_list (self )->None :
        """Redraw the group list rows from the active semester's group data."""
        # Destroy existing rows (skip the empty label widget)
        for widget in self ._groups_list_frame .winfo_children ():
            if widget is not self ._groups_empty_lbl :
                widget .destroy ()

        groups =SemesterManager ().get_groups ()

        if not groups :
            self ._groups_empty_lbl .pack (anchor ="w",pady =(4 ,8 ))
            return 

        self ._groups_empty_lbl .pack_forget ()

        # Column header
        hdr =tk .Frame (self ._groups_list_frame ,bg =theme.PANEL_BG_DARK )
        hdr .pack (fill ="x",pady =(0 ,2 ))
        for text ,w in [("#",3 ),("Group Name",18 ),("File Path",0 )]:
            tk .Label (hdr ,text =text ,bg =theme.PANEL_BG_DARK ,fg =theme.TEXT_MUTED ,
            font =theme.FONT_SUB ,width =w ,anchor ="w",
            padx =6 ).pack (side ="left")
        tk .Label (hdr ,text ="Actions",bg =theme.PANEL_BG_DARK ,fg =theme.TEXT_MUTED ,
        font =theme.FONT_SUB ,width =14 ,anchor ="e",padx =6 ).pack (side ="right")

        for i ,group in enumerate (groups ):
            row =tk .Frame (self ._groups_list_frame ,
            bg =theme.WHITE if i %2 ==0 else theme.PANEL_BG ,
            pady =4 ,padx =6 )
            row .pack (fill ="x")

            # Priority number
            tk .Label (row ,text =str (i +1 ),bg =row .cget ("bg"),
            fg =theme.TEXT_MUTED ,font =theme.FONT_SUB ,width =3 ).pack (side ="left")

            # Group name (editable label)
            tk .Label (row ,text =group ["name"],bg =row .cget ("bg"),
            fg =theme.TEXT_FG ,font =theme.FONT_BOLD ,width =18 ,
            anchor ="w").pack (side ="left")

            # File path — truncated, clickable to re-browse
            path_str =group ["file_path"]
            display =(Path (path_str ).name if path_str 
            else "⚠  No file selected")
            path_color =theme.TEXT_FG if path_str else theme.RED_ACCENT 
            path_lbl =tk .Label (row ,text =display ,bg =row .cget ("bg"),
            fg =path_color ,font =theme.FONT_MAIN ,
            anchor ="w",cursor ="hand2")
            path_lbl .pack (side ="left",fill ="x",expand =True )
            path_lbl .bind ("<Button-1>",
            lambda e ,idx =i :self ._on_browse_group_file (idx ))

            # Action buttons
            action_frame =tk .Frame (row ,bg =row .cget ("bg"))
            action_frame .pack (side ="right")

            if i >0 :
                RoundedButton (action_frame ,text ="▲",
                **theme.BTN_MUTED_STYLE ,font =theme.FONT_SUB ,padx =6 ,pady =2 ,
                command =lambda idx =i :self ._on_move_group (idx ,-1 ),
                ).pack (side ="left",padx =(0 ,2 ))
            else :
                tk .Frame (action_frame ,bg =row .cget ("bg"),width =32 ).pack (side ="left",padx =(0 ,2 ))

            if i <len (groups )-1 :
                RoundedButton (action_frame ,text ="▼",
                **theme.BTN_MUTED_STYLE ,font =theme.FONT_SUB ,padx =6 ,pady =2 ,
                command =lambda idx =i :self ._on_move_group (idx ,1 ),
                ).pack (side ="left",padx =(0 ,6 ))
            else :
                tk .Frame (action_frame ,bg =row .cget ("bg"),width =32 ).pack (side ="left",padx =(0 ,6 ))

            RoundedButton (action_frame ,text ="✕",
            **theme.BTN_DANGER ,font =theme.FONT_SUB ,padx =6 ,pady =2 ,
            command =lambda idx =i :self ._on_delete_group (idx ),
            ).pack (side ="left")

    def _save_and_refresh_groups (self ,groups :list )->None :
        """Persist group list to the active semester and rebuild the UI."""
        sm =SemesterManager ()
        if sm .has_active_semester ():
            sm .set_groups (groups )
        self ._rebuild_groups_list ()

        # ── Group actions ──────────────────────────────────────────────

    def _on_add_group (self )->None :
        """Open the Add Group dialog."""
        sm =SemesterManager ()
        if not sm .has_active_semester ():
            messagebox .showwarning ("No Active Semester",
            "Start a semester before adding groups.")
            return 

        dialog =tk .Toplevel (self )
        dialog .title ("Add Group")
        dialog .geometry ("500x200")
        dialog .configure (bg =theme.PANEL_BG )
        dialog .resizable (False ,False )
        dialog .transient (self )
        dialog .grab_set ()

        tk .Label (dialog ,text ="Group Name:",bg =theme.PANEL_BG ,fg =theme.TEXT_FG ,
        font =theme.FONT_BOLD ).pack (anchor ="w",padx =24 ,pady =(20 ,4 ))

        name_var =tk .StringVar ()
        name_entry =tk .Entry (dialog ,textvariable =name_var ,font =theme.FONT_MAIN ,
        width =38 ,relief ="flat",bg =theme.WHITE ,
        highlightthickness =1 ,highlightbackground =theme.BORDER ,
        highlightcolor =theme.NAVY_DARK ,insertbackground =theme.NAVY_DARK )
        name_entry .pack (anchor ="w",padx =24 ,ipady =4 )
        name_entry .focus ()

        file_var =tk .StringVar ()
        file_frame =tk .Frame (dialog ,bg =theme.PANEL_BG )
        file_frame .pack (fill ="x",padx =24 ,pady =(10 ,0 ))
        tk .Label (file_frame ,text ="Group File (.xlsx):",bg =theme.PANEL_BG ,
        fg =theme.TEXT_FG ,font =theme.FONT_BOLD ).pack (anchor ="w")
        pick_row =tk .Frame (file_frame ,bg =theme.PANEL_BG )
        pick_row .pack (fill ="x",pady =(4 ,0 ))
        file_entry =tk .Entry (pick_row ,textvariable =file_var ,font =theme.FONT_MAIN ,
        width =36 ,relief ="flat",bg =theme.WHITE ,
        highlightthickness =1 ,highlightbackground =theme.BORDER )
        file_entry .pack (side ="left",ipady =4 ,padx =(0 ,8 ))
        RoundedButton (pick_row ,text ="Browse",
        **theme.BTN_MUTED_STYLE ,font =theme.FONT_BOLD ,padx =10 ,pady =4 ,
        command =lambda :file_var .set (
        filedialog .askopenfilename (
        filetypes =[("Excel Files","*.xlsx *.xls"),
        ("All Files","*.*")])or file_var .get ()
        )).pack (side ="left")

        err_lbl =tk .Label (dialog ,text ="",bg =theme.PANEL_BG ,
        fg =theme.RED_ACCENT ,font =theme.FONT_SUB )
        err_lbl .pack (anchor ="w",padx =24 )

        bf =tk .Frame (dialog ,bg =theme.PANEL_BG )
        bf .pack (fill ="x",padx =24 ,pady =(8 ,16 ))

        def on_add ():
            name =name_var .get ().strip ()
            if not name :
                err_lbl .config (text ="Please enter a group name.")
                return 
            groups =SemesterManager ().get_groups ()
            if any (g ["name"].lower ()==name .lower ()for g in groups ):
                err_lbl .config (text =f"A group named '{name }' already exists.")
                return 
            groups .append ({"name":name ,"file_path":file_var .get ().strip ()})
            self ._save_and_refresh_groups (groups )
            dialog .destroy ()

        RoundedButton (bf ,text ="Add Group",
        **theme.BTN_PRIMARY ,font =theme.FONT_BOLD ,padx =16 ,pady =8 ,
        command =on_add ).pack (side ="left",padx =(0 ,8 ))
        RoundedButton (bf ,text ="Cancel",
        **theme.BTN_MUTED_STYLE ,font =theme.FONT_MAIN ,padx =12 ,pady =8 ,
        command =dialog .destroy ).pack (side ="left")

        dialog .wait_window ()

    def _on_browse_group_file (self ,index :int )->None :
        """Open a file picker to update the file path for an existing group."""
        path =filedialog .askopenfilename (
        filetypes =[("Excel Files","*.xlsx *.xls"),("All Files","*.*")]
        )
        if not path :
            return 
        groups =SemesterManager ().get_groups ()
        if 0 <=index <len (groups ):
            groups [index ]["file_path"]=path 
            self ._save_and_refresh_groups (groups )

    def _on_move_group (self ,index :int ,direction :int )->None :
        """Move a group up (-1) or down (+1) in priority order."""
        groups =SemesterManager ().get_groups ()
        new_idx =index +direction 
        if 0 <=new_idx <len (groups ):
            groups [index ],groups [new_idx ]=groups [new_idx ],groups [index ]
            self ._save_and_refresh_groups (groups )

    def _on_delete_group (self ,index :int )->None :
        """Remove a group from the semester configuration."""
        groups =SemesterManager ().get_groups ()
        if 0 <=index <len (groups ):
            name =groups [index ]["name"]
            if not messagebox .askyesno ("Remove Group",
            f"Remove '{name }' from this semester?"):
                return 
            groups .pop (index )
            self ._save_and_refresh_groups (groups )

    def _on_copy_previous_groups (self )->None :
        """Copy group names from the previous semester, clearing file paths."""
        sm =SemesterManager ()
        if not sm .has_active_semester ():
            messagebox .showwarning ("No Active Semester",
            "Start a semester before copying groups.")
            return 
        prev =sm .get_previous_semester_groups ()
        if not prev :
            messagebox .showinfo ("No Previous Groups",
            "No previous semester has groups configured.")
            return 
        existing =sm .get_groups ()
        if existing :
            if not messagebox .askyesno (
            "Replace Groups",
            f"This will replace your {len (existing )} current group(s) with "
            f"{len (prev )} group(s) from the previous semester.\n\n"
            "You will need to re-select the files for each group.\n\n"
            "Continue?"
            ):
                return 
        self ._save_and_refresh_groups (prev )
        messagebox .showinfo (
        "Groups Copied",
        f"Copied {len (prev )} group name(s) from the previous semester.\n\n"
        "Click each file path to select the new files for this semester."
        )

    def _check_semester_on_startup (self ):
        """Show new semester prompt if no active semester exists."""
        sm =SemesterManager ()
        if not sm .has_active_semester ():
            self ._show_new_semester_dialog (on_startup =True )

    def _show_new_semester_dialog(self, on_startup: bool = False):
        return show_new_semester_dialog(self, on_startup)

    def _refresh_semester_tab (self ):
        """Reload semester data and update the display."""
        sm =SemesterManager ()
        sem =sm .active_semester ()

        # Update header
        if sem :
            self ._sem_name_label .config (text =sem .name ,fg =theme.NAVY )
            self ._sem_status_label .config (
            text =f"● Active",
            fg ="#2E7D32"
            )
            if hasattr (self ,"_campaign_season_var"):
                self ._campaign_season_var .set (sem .name )
        else :
            self ._sem_name_label .config (text ="No Active Semester",fg =theme.TEXT_MUTED )
            self ._sem_status_label .config (text ="")

            # Update checkpoint cards
        from utils .config import (SEMESTER_CHECKPOINTS ,
        CHECKPOINT_STATUS_NOT_STARTED ,
        CHECKPOINT_STATUS_IN_PROGRESS ,
        CHECKPOINT_STATUS_COMPLETE )

        STATUS_COLORS ={
        CHECKPOINT_STATUS_NOT_STARTED :"#78909C",
        CHECKPOINT_STATUS_IN_PROGRESS :"#E65100",
        CHECKPOINT_STATUS_COMPLETE :"#2E7D32",
        }
        STATUS_ICONS ={
        CHECKPOINT_STATUS_NOT_STARTED :"○",
        CHECKPOINT_STATUS_IN_PROGRESS :"◉",
        CHECKPOINT_STATUS_COMPLETE :"✓",
        }

        for cp_name ,widgets in self ._checkpoint_frames .items ():
            if sem :
                cp =sem .get_checkpoint (cp_name )
                icon =STATUS_ICONS .get (cp .status ,"○")
                color =STATUS_COLORS .get (cp .status ,"#78909C")
                widgets ["status"].config (
                text =f"{icon }  {cp .status }",fg =color 
                )
                if cp .run_count >0 :
                    widgets ["runs"].config (text =f"Runs: {cp .run_count }")
                    widgets ["students"].config (
                    text =f"Assigned: {cp .students_assigned :,} | "
                    f"Unmatched: {cp .students_unmatched :,}"
                    )
                else :
                    widgets ["runs"].config (text ="No runs yet")
                    widgets ["students"].config (text ="")
            else :
                widgets ["status"].config (text ="○  Not Started",fg =theme.TEXT_MUTED )
                widgets ["runs"].config (text ="")
                widgets ["students"].config (text ="")

                # Update history tree
        self ._history_tree .delete (*self ._history_tree .get_children ())
        for s in sm .all_semesters ():
            def cp_val (name ):
                cp =s .get_checkpoint (name )
                if cp .status ==CHECKPOINT_STATUS_COMPLETE :
                    return f"✓ {cp .students_assigned :,}"
                elif cp .run_count >0 :
                    return f"◉ {cp .students_assigned :,}"
                return "—"

            tag ="active"if s .status ==SEMESTER_STATUS_ACTIVE else "done"
            self ._history_tree .insert ("","end",tags =(tag ,),values =(
            s .name ,
            s .status ,
            s .created [:10 ]if s .created else "",
            s .completed [:10 ]if s .completed else "",
            cp_val ("Progress Report 1"),
            cp_val ("Midterm"),
            cp_val ("Progress Report 2"),
            Path (s .master_report ).name if s .master_report else "—",
            ))

            # Rebuild the group list display
        if hasattr (self ,"_groups_list_frame"):
            self ._rebuild_groups_list ()

            # Pre-fill file pickers if semester has saved paths
        if sem :
            if sem .contact_report :
                if hasattr (self ,"_contact_picker")and not self ._contact_picker .path :
                    self ._contact_picker .path =sem .contact_report 
                if hasattr (self ,"_midterm_contact_picker")and not self ._midterm_contact_picker .path :
                    self ._midterm_contact_picker .path =sem .contact_report 
            if sem .control_file :
                if hasattr (self ,"_control_picker")and not self ._control_picker .path :
                    self ._control_picker .path =sem .control_file 
                if hasattr (self ,"_midterm_control_picker")and not self ._midterm_control_picker .path :
                    self ._midterm_control_picker .path =sem .control_file 
            if sem .group_folder :
                if hasattr (self ,"_group_dir_picker")and not self ._group_dir_picker .path :
                    self ._group_dir_picker .path =sem .group_folder 
                if hasattr (self ,"_midterm_group_dir_picker")and not self ._midterm_group_dir_picker .path :
                    self ._midterm_group_dir_picker .path =sem .group_folder 

                    # Auto-populate trend/master report pickers
            output_files =sem .output_files ()
            cp_to_picker ={
            "Progress Report 1":"_trend_pr1_picker",
            "Midterm":"_trend_mid_picker",
            "Progress Report 2":"_trend_pr2_picker",
            }
            for cp_name ,picker_attr in cp_to_picker .items ():
                if cp_name in output_files and hasattr (self ,picker_attr ):
                    picker =getattr (self ,picker_attr )
                    if not picker .path :
                        picker .path =output_files [cp_name ]
                        # Same for master report pickers
            master_cp_to_picker ={
            "Progress Report 1":"_master_pr1_picker",
            "Midterm":"_master_mid_picker",
            "Progress Report 2":"_master_pr2_picker",
            }
            for cp_name ,picker_attr in master_cp_to_picker .items ():
                if cp_name in output_files and hasattr (self ,picker_attr ):
                    picker =getattr (self ,picker_attr )
                    if not picker .path :
                        picker .path =output_files [cp_name ]

    def _update_semester_header (self ,sem ):
        """Quick update of just the header label."""
        if sem and hasattr (self ,"_sem_name_label"):
            self ._sem_name_label .config (text =sem .name ,fg =theme.NAVY )
            self ._sem_status_label .config (text ="Active",fg ="#2E7D32")

    def _on_new_semester (self ):
        sm =SemesterManager ()
        if sm .has_active_semester ():
            messagebox .showwarning ("Active Semester Exists",
            f"You already have an active semester: "
            f"'{sm .active_semester ().name }'.\n\n"
            "Complete or reset it before starting a new one.")
            return 
        self ._show_new_semester_dialog ()

    def _on_mark_checkpoint_complete (self ,checkpoint_name :str ):
        sm =SemesterManager ()
        if not sm .has_active_semester ():
            messagebox .showwarning ("No Active Semester",
            "Start a semester first.")
            return 
        cp =sm .active_semester ().get_checkpoint (checkpoint_name )
        if cp .run_count ==0 :
            if not messagebox .askyesno ("Mark Complete",
            f"'{checkpoint_name }' has no runs recorded.\n"
            "Mark it complete anyway?"):
                return 
        sm .mark_checkpoint_complete (checkpoint_name )
        self ._refresh_semester_tab ()

    def _on_reset_checkpoint (self ,checkpoint_name :str ):
        if not messagebox .askyesno ("Reset Checkpoint",
        f"Reset '{checkpoint_name }'?\n\n"
        "This will clear the assigned students list so all students "
        "are eligible again for this checkpoint.\n\n"
        "This cannot be undone."):
            return 
        sm =SemesterManager ()
        cleared =sm .reset_checkpoint (checkpoint_name )
        self ._refresh_semester_tab ()
        messagebox .showinfo ("Checkpoint Reset",
        f"✅ '{checkpoint_name }' reset.\n"
        f"Cleared {cleared :,} student IDs from the assigned list.")

    def _on_complete_semester (self ):
        sm =SemesterManager ()
        if not sm .has_active_semester ():
            messagebox .showwarning ("No Active Semester","No active semester to complete.")
            return 
        sem =sm .active_semester ()
        if not messagebox .askyesno ("Complete Semester",
        f"Complete semester '{sem .name }'?\n\n"
        "This will:\n"
        "  • Generate the Master Season Report\n"
        "  • Clear the assigned students list\n"
        "  • Move semester to history\n\n"
        "This cannot be undone."):
            return 

            # Generate master report first
        output_files =sem .output_files ()
        out_path =None 
        if output_files :
            try :
                from datetime import datetime 
                from utils .config import LOG_DATE_FORMAT 
                from processors .season_report import SeasonReportGenerator 
                timestamp =datetime .now ().strftime (LOG_DATE_FORMAT )
                season_label =sem .name .replace (" ","_")
                out_path =OUTPUT_DIR /f"MasterReport_{season_label }_{timestamp }.xlsx"
                OUTPUT_DIR .mkdir (parents =True ,exist_ok =True )

                gen =SeasonReportGenerator ()
                gen .generate (
                pr1_path =Path (output_files ["Progress Report 1"])
                if "Progress Report 1"in output_files else None ,
                mid_path =Path (output_files ["Midterm"])
                if "Midterm"in output_files else None ,
                pr2_path =Path (output_files ["Progress Report 2"])
                if "Progress Report 2"in output_files else None ,
                output_path =out_path ,
                season_name =sem .name ,
                )
            except Exception as exc :
                if not messagebox .askyesno ("Report Error",
                f"Could not generate master report:\n{exc }\n\n"
                "Complete semester anyway?"):
                    return 

        sm .complete_semester (str (out_path )if out_path else "")
        self ._refresh_semester_tab ()

        msg =f"✅ Semester '{sem .name }' completed!"
        if out_path :
            msg +=f"\n\nMaster Report:\n{out_path }"
        messagebox .showinfo ("Semester Complete",msg )

    def _on_reset_semester (self ):
        sm =SemesterManager ()
        if not sm .has_active_semester ():
            messagebox .showwarning ("No Active Semester","No active semester to reset.")
            return 
        sem =sm .active_semester ()
        if not messagebox .askyesno ("Reset Semester",
        f"Reset semester '{sem .name }'?\n\n"
        "This will clear ALL progress for this semester and "
        "remove it from the active view (history preserved).\n\n"
        "This cannot be undone."):
            return 
        sm .reset_semester ()
        self ._refresh_semester_tab ()
        messagebox .showinfo ("Semester Reset",
        f"Semester '{sem .name }' has been reset.\n"
        "Start a new semester when ready.")


    def _build_settings_tab(self):
        build_settings_tab(self)

    def _build_help_tab(self):
        build_help_tab(self)

    def _on_save_settings (self ):
        """Read all entry fields and save to settings.json."""
        settings =get_settings ()

        for key ,var in self ._setting_vars .items ():
            section ,field_name =key .split (".",1 )
            value =var .get ().strip ()
            if section =="progress":
                settings .progress_report_map [field_name ]=value 
            elif section =="contact":
                settings .contact_report_map [field_name ]=value 
            elif section =="midterm":
                settings .midterm_map [field_name ]=value 
            elif section =="faculty":
                settings .faculty_map [field_name ]=value 

        try :
            settings .save ()
            reload_settings ()
            self ._settings_status .config (
            text ="Settings saved. Changes take effect on next run.",
            fg =theme.SUCCESS_COLOR ,
            )
        except Exception as exc :
            self ._settings_status .config (
            text =f"❌ Save failed: {exc }",fg ="#C62828"
            )

    def _on_reset_settings (self ):
        """Reset all fields to config.py defaults."""
        if not messagebox .askyesno (
        "Reset Settings",
        "Reset ALL column mappings to defaults?\nThis cannot be undone."
        ):
            return 

        settings =get_settings ()
        settings .reset_to_defaults ()
        settings .save ()
        reload_settings ()

        # Refresh all entry fields from reset values
        all_maps ={
        "progress":settings .progress_report_map ,
        "contact":settings .contact_report_map ,
        "midterm":settings .midterm_map ,
        "faculty":settings .faculty_map ,
        }
        for key ,var in self ._setting_vars .items ():
            section ,field_name =key .split (".",1 )
            if section in all_maps :
                var .set (all_maps [section ].get (field_name ,""))

        self ._settings_status .config (text ="Reset to defaults.",fg ="#2F5496")

    def _report_log (self ,message :str ,tag :str ="info"):
        append_log(self._report_log_box, message, tag)



        # ---------------------------------------------------------------------------
        # Entry point
        # ---------------------------------------------------------------------------

if __name__ =="__main__":
    import traceback 
    try :
        app =InterventionSorterApp ()
        app .mainloop ()
    except Exception :
        traceback .print_exc ()
        input ("\nPress Enter to close...")
