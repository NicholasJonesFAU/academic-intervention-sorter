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
from gui_campaign_actions import (
    rebuild_groups_list,
    save_and_refresh_groups,
    on_add_group,
    on_browse_group_file,
    on_move_group,
    on_delete_group,
    on_copy_previous_groups,
    check_semester_on_startup,
    refresh_semester_tab,
    update_semester_header,
    on_new_semester,
    on_mark_checkpoint_complete,
    on_reset_checkpoint,
    on_complete_semester,
    on_reset_semester,
)
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

    def _rebuild_groups_list(self) -> None:
        return rebuild_groups_list(self)

    def _save_and_refresh_groups(self, groups: list) -> None:
        return save_and_refresh_groups(self, groups)

    def _on_add_group(self) -> None:
        return on_add_group(self)

    def _on_browse_group_file(self, index: int) -> None:
        return on_browse_group_file(self, index)

    def _on_move_group(self, index: int, direction: int) -> None:
        return on_move_group(self, index, direction)

    def _on_delete_group(self, index: int) -> None:
        return on_delete_group(self, index)

    def _on_copy_previous_groups(self) -> None:
        return on_copy_previous_groups(self)

    def _check_semester_on_startup(self):
        return check_semester_on_startup(self)

    def _show_new_semester_dialog(self, on_startup: bool = False):
        return show_new_semester_dialog(self, on_startup)

    def _refresh_semester_tab(self):
        return refresh_semester_tab(self)

    def _update_semester_header(self, sem):
        return update_semester_header(self, sem)

    def _on_new_semester(self):
        return on_new_semester(self)

    def _on_mark_checkpoint_complete(self, checkpoint_name: str):
        return on_mark_checkpoint_complete(self, checkpoint_name)

    def _on_reset_checkpoint(self, checkpoint_name: str):
        return on_reset_checkpoint(self, checkpoint_name)

    def _on_complete_semester(self):
        return on_complete_semester(self)

    def _on_reset_semester(self):
        return on_reset_semester(self)


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
