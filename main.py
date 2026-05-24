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
from gui_midterm_tab import build_midterm_tab

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

    def _on_run (self ):
        if self ._processing :
            return 
        if not self ._ensure_season_set ():
            return 
        inputs =self ._collect_inputs ()
        if inputs is None :
            return 
            # Group selection dialog
        if self ._control_picker .path and self ._group_dir_picker .path :
            checkpoint =(self ._checkpoint_type_var .get ()
            if hasattr (self ,"_checkpoint_type_var")else "Progress Report 1")
            proceed ,skip_groups =self ._show_group_selection_dialog (
            self ._control_picker .path ,
            self ._group_dir_picker .path ,
            checkpoint ,
            )
            if not proceed :
                return 
            inputs .skip_groups =skip_groups 
        self ._start_processing (inputs ,validate_only =False )

    def _on_validate (self ):
        if self ._processing :
            return 
        inputs =self ._collect_inputs ()
        if inputs is None :
            return 
        self ._start_processing (inputs ,validate_only =True )

    def _on_prerun_check (self ):
        """Run pre-flight data quality checks without a full pipeline run."""
        paths ={
        "Progress Report":self ._progress_picker .path ,
        "Contact Report":self ._contact_picker .path ,
        "Group Control":self ._control_picker .path ,
        "Group Folder":self ._group_dir_picker .path ,
        }
        missing =[k for k ,v in paths .items ()if not v ]
        if missing :
            messagebox .showerror ("Missing Files",
            "Please select files first:\n"+"\n".join (f"  • {m }"for m in missing ))
            return 

        self ._log ("="*55 ,"info")
        self ._log ("PRE-RUN DATA QUALITY CHECK","step")
        self ._log ("="*55 ,"info")

        import threading 
        def _worker ():
            checker =PreRunChecker ()
            all_results =[]
            progress_ids =None 

            # Check progress report
            self .after (0 ,self ._log ,"Checking progress report...","step")
            pr_results =checker .check_progress_report (
            Path (paths ["Progress Report"])
            )
            all_results .extend (pr_results )

            # Extract at-risk IDs for cross-checks
            try :
                from utils .settings_manager import get_settings 
                from utils .normalization import normalize_student_id_series ,normalize_at_risk_series 
                import pandas as pd 
                col =get_settings ().progress_report_map 
                df =pd .read_csv (paths ["Progress Report"],dtype =str ,keep_default_na =False )if paths ["Progress Report"].endswith (".csv")else pd .read_excel (paths ["Progress Report"],dtype =str ,
                keep_default_na =False ,engine ="openpyxl")
                df .columns =[str (c ).strip ()for c in df .columns ]
                if col ["at_risk"]in df .columns and col ["student_id"]in df .columns :
                    at_risk_mask =normalize_at_risk_series (df [col ["at_risk"]])
                    progress_ids =set (
                    normalize_student_id_series (df [at_risk_mask ][col ["student_id"]])
                    .replace ("",pd .NA ).dropna ()
                    )
            except Exception :
                pass 

                # Check contact report
            self .after (0 ,self ._log ,"Checking contact report...","step")
            cr_results =checker .check_contact_report (
            Path (paths ["Contact Report"]),progress_ids 
            )
            all_results .extend (cr_results )

            # Check group files
            self .after (0 ,self ._log ,"Checking group files...","step")
            gf_results =checker .check_group_files (
            Path (paths ["Group Control"]),
            Path (paths ["Group Folder"]),
            progress_ids ,
            )
            all_results .extend (gf_results )

            self .after (0 ,self ._show_precheck_results ,all_results )

        threading .Thread (target =_worker ,daemon =True ).start ()

    def _show_precheck_results (self ,results ):
        """Display pre-run check results in the log and a summary popup."""
        errors =[r for r in results if r .level =="error"]
        warnings =[r for r in results if r .level =="warning"]
        infos =[r for r in results if r .level =="info"]

        for r in infos :
            self ._log (f"  ℹ️  {r .message }","info")
        for r in warnings :
            self ._log (f"  ⚠️  {r .message }","warning")
        for r in errors :
            self ._log (f"  ❌  {r .message }","error")

        if errors :
            self ._log ("\n❌ Pre-run check found errors — fix before running.","error")
            messagebox .showerror ("Pre-Run Check Failed",
            f"Found {len (errors )} error(s) and {len (warnings )} warning(s).\n\n"
            +"\n".join (f"❌ {r .message [:120 ]}"for r in errors [:5 ]))
        elif warnings :
            self ._log (f"\n⚠️  Pre-run check passed with {len (warnings )} warning(s).","warning")
            messagebox .showwarning ("Pre-Run Check — Warnings",
            f"No errors found but {len (warnings )} warning(s):\n\n"
            +"\n".join (f"⚠️ {r .message [:120 ]}"for r in warnings [:5 ])
            +"\n\nYou can still run — check warnings in the log.")
        else :
            self ._log ("\n✅ Pre-run check passed — all files look good!","success")
            messagebox .showinfo ("Pre-Run Check Passed",
            "✅ All files validated successfully!\n\nReady to run.")

    def _on_clear (self ):
        self ._log_box .config (state ="normal")
        self ._log_box .delete ("1.0","end")
        self ._log_box .config (state ="disabled")
        self ._progress_var .set (0 )
        self ._progress_bar .stop ()

    def _collect_inputs (self )->PipelineInputs |None :
        """
        Gather file paths from pickers and validate they're not empty.

        When the active semester has groups configured, the control file and
        group folder are optional — semester groups take precedence.
        """
        semester_groups =SemesterManager ().get_groups ()
        using_semester_groups =bool (semester_groups )

        errors =[]
        always_required ={
        "Progress Report":self ._progress_picker .path ,
        "Contact Report":self ._contact_picker .path ,
        "Output Folder":self ._output_picker .path ,
        }
        for label ,val in always_required .items ():
            if not val :
                errors .append (f"• {label } is required.")

                # Control file + group dir only required if no semester groups set
        if not using_semester_groups :
            if not self ._control_picker .path :
                errors .append ("• Group Control File is required (no semester groups configured).")
            if not self ._group_dir_picker .path :
                errors .append ("• Group Files Folder is required (no semester groups configured).")

        if errors :
            messagebox .showerror (
            "Missing Inputs",
            "Please provide all required files:\n\n"+"\n".join (errors ),
            )
            return None 

        season =self ._campaign_season_var .get ().strip ()if hasattr (self ,"_campaign_season_var")else ""
        checkpoint =self ._checkpoint_type_var .get ()if hasattr (self ,"_checkpoint_type_var")else "Progress Report"

        # Provide dummy Paths for control_file/group_dir when not used
        control_file =Path (self ._control_picker .path )if self ._control_picker .path else Path (".")
        group_dir =Path (self ._group_dir_picker .path )if self ._group_dir_picker .path else Path (".")

        return PipelineInputs (
        progress_report =Path (always_required ["Progress Report"]),
        contact_report =Path (always_required ["Contact Report"]),
        control_file =control_file ,
        group_dir =group_dir ,
        output_dir =Path (always_required ["Output Folder"]),
        exclude_previous =self ._exclude_var .get (),
        season =season ,
        checkpoint_type =checkpoint ,
        semester_groups =semester_groups if using_semester_groups else None ,
        )

    def _start_processing (self ,inputs :PipelineInputs ,validate_only :bool ):
        """Run the pipeline in a background thread to keep the GUI responsive."""
        self ._processing =True 
        self ._set_buttons_state ("disabled")
        self ._progress_bar .start (12 )
        self ._log ("="*60 ,"info")
        self ._log (
        "VALIDATION CHECK"if validate_only else "STARTING FULL PROCESSING",
        "step",
        )
        self ._log ("="*60 ,"info")

        def _worker ():
            try :
                controller =PipelineController (
                progress_callback =lambda msg :self .after (0 ,self ._log ,msg ,"step")
                )
                if validate_only :
                    result =controller .validate_only (inputs )
                else :
                    result =controller .run (inputs )
                self .after (0 ,self ._on_complete ,result )
            except Exception :
                err =traceback .format_exc ()
                self .after (0 ,self ._on_error ,err )

        threading .Thread (target =_worker ,daemon =True ).start ()

    def _on_complete (self ,result :PipelineResult ):
        self ._processing =False 
        self ._set_buttons_state ("normal")
        self ._progress_bar .stop ()
        self ._progress_var .set (100 if result .success else 0 )

        if result .success :
            self ._log ("\n✅ "+result .message ,"success")
            if not result .validation_only and result .output_path :
                self ._log (f"\n📁 Output: {result .output_path }","success")
                # Ask if they want to open the file
                if messagebox .askyesno (
                "Processing Complete",
                f"Processing completed successfully!\n\n"
                f"Output file:\n{result .output_path }\n\n"
                f"{result .message }\n\n"
                f"Open the output file now?",
                ):
                    import subprocess ,sys 
                    try :
                        if sys .platform =="win32":
                            subprocess .Popen (["explorer",str (result .output_path )])
                        elif sys .platform =="darwin":
                            subprocess .Popen (["open",str (result .output_path )])
                        else :
                            subprocess .Popen (["xdg-open",str (result .output_path )])
                    except Exception :
                        pass 
            elif result .validation_only :
                messagebox .showinfo (
                "Validation Passed",
                f"✅ All validations passed!\n\n{result .message }",
                )
        else :
            self ._log ("\n❌ "+result .message ,"error")
            for err in result .errors :
                self ._log (f"   {err }","error")
            if result .warnings :
                for w in result .warnings :
                    self ._log (f"   {w }","warning")
            messagebox .showerror (
            "Processing Failed"if not result .validation_only else "Validation Issues",
            f"{'❌ Processing failed:'if not result .validation_only else '⚠️ Validation issues found:'}\n\n"
            +result .message 
            +("\n\nDetails:\n"+"\n".join (result .errors [:5 ])if result .errors else ""),
            )

    def _on_error (self ,error_text :str ):
        self ._processing =False 
        self ._set_buttons_state ("normal")
        self ._progress_bar .stop ()
        self ._log ("\n❌ Unexpected error:\n"+error_text ,"error")
        messagebox .showerror ("Unexpected Error",f"An unexpected error occurred:\n\n{error_text [:800 ]}")

        # ------------------------------------------------------------------
        # Helpers
        # ------------------------------------------------------------------

    def _log (self ,message :str ,tag :str ="info"):
        append_log(self._log_box, message, tag)

    def _set_buttons_state (self ,state :str ):
        for btn in [self ._run_btn ,self ._validate_btn ,self ._clear_btn ]:
            btn .config (state =state )

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

    def _on_run_report_status (self ):
        if self ._report_processing :
            return 

        status_path =self ._status_picker .path 
        mapping_path =self ._mapping_picker .path 
        output_dir =self ._report_output_picker .path 

        errors =[]
        if not status_path :errors .append ("• Report Status File is required.")
        if not mapping_path :errors .append ("• Dept/College Mapping File is required.")
        if not output_dir :errors .append ("• Output Folder is required.")
        if errors :
            messagebox .showerror ("Missing Inputs","\n".join (errors ))
            return 

        self ._report_processing =True 
        self ._report_run_btn .config (state ="disabled")
        self ._report_progress_bar .start (12 )
        self ._report_log ("="*55 ,"info")
        self ._report_log ("GENERATING FACULTY REPORT STATUS","step")
        self ._report_log ("="*55 ,"info")

        def _worker ():
            try :
                from datetime import datetime 
                from utils .config import LOG_DATE_FORMAT ,OUTPUT_FILENAME_PATTERN 
                timestamp =datetime .now ().strftime (LOG_DATE_FORMAT )
                out_path =Path (output_dir )/f"FacultyCompletion_{timestamp }.xlsx"

                self ._report_log ("Loading department mapping...","step")
                mapper =DepartmentMapper ()
                mapper .load (Path (mapping_path ))

                self ._report_log ("Loading report status file...","step")
                proc =ReportStatusProcessor ()
                proc .load (Path (status_path ),mapper )

                overall =proc .overall_stats ()
                self ._report_log (
                f"Sections loaded: {overall ['total_sections']:,}  |  "
                f"Submitted: {overall ['submitted']:,}  |  "
                f"Overall: {overall ['completion_pct']}%","info"
                )

                self ._report_log ("Building workbook with charts...","step")
                exporter =ReportStatusExporter ()
                exporter .export (proc ,out_path ,Path (status_path ).name )

                self .after (0 ,self ._on_report_complete ,True ,str (out_path ),overall )
            except Exception as exc :
                import traceback 
                self .after (0 ,self ._on_report_complete ,False ,traceback .format_exc (),{})

        import threading 
        threading .Thread (target =_worker ,daemon =True ).start ()

    def _on_report_complete (self ,success :bool ,message :str ,overall :dict ):
        self ._report_processing =False 
        self ._report_run_btn .config (state ="normal")
        self ._report_progress_bar .stop ()
        if success :
            summary =(
            "\u2705 Faculty completion report generated!\n\n"
            "Overall completion: {}%\n"
            "Submitted: {:,} / {:,} sections\n\n"
            "Output:\n{}"
            ).format (
            overall .get ("completion_pct",0 ),
            overall .get ("submitted",0 ),
            overall .get ("total_sections",0 ),
            message ,
            )
            self ._report_log ("\n\u2705 Done! Overall: {}%".format (overall .get ("completion_pct",0 )),"success")
            self ._report_log ("\U0001f4c1 Output: "+message ,"success")
            messagebox .showinfo ("Report Complete",summary )
        else :
            self ._report_log ("\n\u274c Failed: "+message [:200 ],"error")
            messagebox .showerror ("Report Failed","\u274c Report failed:\n\n"+message [:400 ])



    def _build_midterm_tab(self):
        """Build the Midterm Sorter tab UI."""
        build_midterm_tab(self)

    def _on_run_midterm (self ):
        if self ._midterm_processing :
            return 
        if not self ._ensure_season_set ():
            return 

        semester_groups =SemesterManager ().get_groups ()
        using_semester_groups =bool (semester_groups )

        errors =[]
        always_required ={
        "Midterm Grade File":self ._midterm_file_picker .path ,
        "Contact Report":self ._midterm_contact_picker .path ,
        "Output Folder":self ._midterm_output_picker .path ,
        }
        for label ,val in always_required .items ():
            if not val :
                errors .append (f"  {label } is required.")
        if not using_semester_groups :
            if not self ._midterm_control_picker .path :
                errors .append ("  Group Control File is required (no semester groups configured).")
            if not self ._midterm_group_dir_picker .path :
                errors .append ("  Group Files Folder is required (no semester groups configured).")
        if errors :
            messagebox .showerror (
            "Missing Inputs",
            "Please provide all required files:\n\n"+"\n".join (errors )
            )
            return 

        season =self ._campaign_season_var .get ().strip ()if hasattr (self ,"_campaign_season_var")else ""
        control_file =Path (self ._midterm_control_picker .path )if self ._midterm_control_picker .path else Path (".")
        group_dir =Path (self ._midterm_group_dir_picker .path )if self ._midterm_group_dir_picker .path else Path (".")

        inputs =MidtermPipelineInputs (
        midterm_file =Path (always_required ["Midterm Grade File"]),
        contact_report =Path (always_required ["Contact Report"]),
        control_file =control_file ,
        group_dir =group_dir ,
        output_dir =Path (always_required ["Output Folder"]),
        exclude_previous =self ._midterm_exclude_var .get (),
        season =season ,
        checkpoint_type ="Midterm",
        semester_groups =semester_groups if using_semester_groups else None ,
        )

        # Group selection dialog — always show so user can pick which groups to produce
        proceed ,skip_groups =self ._show_group_selection_dialog (
        self ._midterm_control_picker .path ,
        self ._midterm_group_dir_picker .path ,
        "Midterm",
        )
        if not proceed :
            return 
        inputs .skip_groups =skip_groups 

        self ._midterm_processing =True 
        self ._midterm_run_btn .config (state ="disabled")
        self ._midterm_progress_bar .start (12 )
        self ._midterm_log_write ("="*55 ,"info")
        self ._midterm_log_write ("STARTING MIDTERM SORT","step")
        self ._midterm_log_write ("="*55 ,"info")

        import threading 
        def _worker ():
            try :
                controller =MidtermPipelineController (
                progress_callback =lambda msg :self .after (
                0 ,self ._midterm_log_write ,msg ,"step"
                )
                )
                result =controller .run (inputs )
                self .after (0 ,self ._on_midterm_complete ,result )
            except Exception :
                import traceback 
                self .after (0 ,self ._on_midterm_error ,traceback .format_exc ())

        threading .Thread (target =_worker ,daemon =True ).start ()

    def _on_midterm_complete (self ,result ):
        self ._midterm_processing =False 
        self ._trend_processing =False 
        self ._semester_mgr =SemesterManager ()
        self ._midterm_run_btn .config (state ="normal")
        self ._midterm_progress_bar .stop ()
        if result .success :
            self ._midterm_log_write ("\n\u2705 "+result .message ,"success")
            self ._midterm_log_write ("\U0001f4c1 Output: "+str (result .output_path ),"success")
            if hasattr (self ,'_refresh_campaign_tab'):self ._refresh_campaign_tab ()
            messagebox .showinfo (
            "Midterm Sort Complete",
            "\u2705 Midterm sort completed!\n\n"+result .message +
            "\n\nOutput:\n"+str (result .output_path ),
            )
        else :
            self ._midterm_log_write ("\n\u274c "+result .message ,"error")
            for e in result .errors [:3 ]:
                self ._midterm_log_write ("  "+e [:300 ],"error")
            messagebox .showerror (
            "Midterm Sort Failed",
            "\u274c Processing failed:\n\n"+result .message +
            ("\n\n"+result .errors [0 ][:400 ]if result .errors else ""),
            )

    def _on_midterm_error (self ,error_text :str ):
        self ._midterm_processing =False 
        self ._trend_processing =False 
        self ._semester_mgr =SemesterManager ()
        self ._midterm_run_btn .config (state ="normal")
        self ._midterm_progress_bar .stop ()
        self ._midterm_log_write ("\n\u274c Unexpected error:\n"+error_text [:400 ],"error")
        messagebox .showerror ("Unexpected Error",error_text [:600 ])

    def _midterm_clear_log (self ):
        clear_log(self._midterm_log_box)

    def _midterm_log_write (self ,message :str ,tag :str ="info"):
        append_log(self._midterm_log_box, message, tag)


    def _build_trend_tab (self ):
        """Build the Campaign Trend Report tab."""
        outer ,_wheel_on4 ,_wheel_off4 =self ._make_scrollable_tab (self ._trend_tab )

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

        self ._trend_pr1_picker =FilePickerRow (
        pf ,label ="Progress Report 1:",
        filetypes =[("Excel Files","*.xlsx"),("All Files","*.*")],
        tooltip ="First progress report output (InterventionSort_...xlsx)",
        )
        self ._trend_pr1_picker .pack (fill ="x",pady =4 )

        self ._trend_mid_picker =FilePickerRow (
        pf ,label ="Midterm:",
        filetypes =[("Excel Files","*.xlsx"),("All Files","*.*")],
        tooltip ="Midterm sort output (MidtermSort_...xlsx)",
        )
        self ._trend_mid_picker .pack (fill ="x",pady =4 )

        self ._trend_pr2_picker =FilePickerRow (
        pf ,label ="Progress Report 2:",
        filetypes =[("Excel Files","*.xlsx"),("All Files","*.*")],
        tooltip ="Second progress report output (InterventionSort_...xlsx)",
        )
        self ._trend_pr2_picker .pack (fill ="x",pady =4 )

        self ._trend_output_picker =FilePickerRow (
        pf ,label ="Output Folder:",
        filetypes =[],is_directory =True ,
        tooltip ="Where the trend report will be saved",
        )
        self ._trend_output_picker .pack (fill ="x",pady =4 )
        self ._trend_output_picker .path =str (OUTPUT_DIR )

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
            setattr (self ,attr ,var )
            tk .Entry (name_row ,textvariable =var ,font =theme.FONT_MAIN ,width =22 ,
            relief ="flat",bg ="white",
            highlightthickness =1 ,highlightbackground ="#B0BEC5",
            insertbackground =theme.TEXT_FG ).grid (row =0 ,column =i *2 +1 ,padx =(0 ,16 ),ipady =3 )

        ttk .Separator (outer ,orient ="horizontal").pack (fill ="x",pady =14 )

        btn_frame =tk .Frame (outer ,bg =theme.PANEL_BG )
        btn_frame .pack (fill ="x",pady =(0 ,8 ))

        self ._trend_run_btn =RoundedButton (
        btn_frame ,text ='Generate Trend Report',
        command =self ._on_run_trend ,
        **theme.BTN_PRIMARY ,font =theme.FONT_BOLD ,padx =20 ,pady =9 ,
        )
        self ._trend_run_btn .pack (side ="left",padx =(0 ,10 ))

        RoundedButton (
        btn_frame ,text ="Clear",
        **theme.BTN_MUTED_STYLE ,font =theme.FONT_MAIN ,padx =14 ,pady =9 ,
        command =self ._trend_clear_log ,
        ).pack (side ="left")

        self ._trend_progress_bar =ttk .Progressbar (
        outer ,maximum =100 ,mode ="indeterminate"
        )
        self ._trend_progress_bar .pack (fill ="x",pady =(0 ,8 ))

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

        self ._master_pr1_picker =FilePickerRow (
        mf ,label ="Progress Report 1:",
        filetypes =[("Excel Files","*.xlsx"),("All Files","*.*")],
        tooltip ="PR1 output workbook (ProgressReport_...xlsx)",
        )
        self ._master_pr1_picker .pack (fill ="x",pady =3 )

        self ._master_mid_picker =FilePickerRow (
        mf ,label ="Midterm:",
        filetypes =[("Excel Files","*.xlsx"),("All Files","*.*")],
        tooltip ="Midterm output workbook (MidtermSort_...xlsx)",
        )
        self ._master_mid_picker .pack (fill ="x",pady =3 )

        self ._master_pr2_picker =FilePickerRow (
        mf ,label ="Progress Report 2:",
        filetypes =[("Excel Files","*.xlsx"),("All Files","*.*")],
        tooltip ="PR2 output workbook (ProgressReport_...xlsx)",
        )
        self ._master_pr2_picker .pack (fill ="x",pady =3 )

        self ._master_output_picker =FilePickerRow (
        mf ,label ="Output Folder:",
        filetypes =[],is_directory =True ,
        tooltip ="Where the master report will be saved",
        )
        self ._master_output_picker .pack (fill ="x",pady =3 )
        self ._master_output_picker .path =str (OUTPUT_DIR )

        master_btn_frame =tk .Frame (outer ,bg =theme.PANEL_BG )
        master_btn_frame .pack (fill ="x",pady =(10 ,0 ))

        RoundedButton (
        master_btn_frame ,text ="Generate Master Season Report",
        command =self ._on_generate_master_report ,
        **theme.BTN_SUCCESS_STYLE ,font =theme.FONT_BOLD ,padx =20 ,pady =9 ,
        ).pack (side ="left")

        ttk .Separator (outer ,orient ="horizontal").pack (fill ="x",pady =10 )

        section_label (outer ,"Processing Log").pack (fill ="x",pady =(4 ,4 ))

        self ._trend_log_box =scrolledtext .ScrolledText (
        outer ,height =8 ,font =theme.FONT_MONO ,
        bg ="#0A1628",fg ="#C8D6E8",
        relief ="flat",wrap ="word",
        )
        self ._trend_log_box .pack (fill ="both",expand =True )
        self ._trend_log_box .config (state ="disabled")
        self ._trend_log_box .bind ("<Enter>",_wheel_off4 )
        self ._trend_log_box .bind ("<Leave>",_wheel_on4 )
        configure_log_tags(self._trend_log_box, PURPLE_LOG_TAGS)

    def _on_run_trend (self ):
        if self ._trend_processing :
            return 

        paths ={
        "PR1":self ._trend_pr1_picker .path ,
        "Mid":self ._trend_mid_picker .path ,
        "PR2":self ._trend_pr2_picker .path ,
        "Output":self ._trend_output_picker .path ,
        }

        # At least one workbook required; output always required
        if not any ([paths ["PR1"],paths ["Mid"],paths ["PR2"]]):
            messagebox .showerror ("Missing Input",
            "Please select at least one output workbook.")
            return 
        if not paths ["Output"]:
            messagebox .showerror ("Missing Input","Please select an output folder.")
            return 

        self ._trend_processing =True 
        self ._trend_run_btn .config (state ="disabled")
        self ._trend_progress_bar .start (12 )
        self ._trend_log_write ("="*55 ,"info")
        self ._trend_log_write ("GENERATING CAMPAIGN TREND REPORT","step")
        self ._trend_log_write ("="*55 ,"info")

        pr1_path =Path (paths ["PR1"])if paths ["PR1"]else None 
        mid_path =Path (paths ["Mid"])if paths ["Mid"]else None 
        pr2_path =Path (paths ["PR2"])if paths ["PR2"]else None 
        out_dir =Path (paths ["Output"])
        pr1_label =self ._trend_pr1_label .get ().strip ()or "PR1"
        mid_label =self ._trend_mid_label .get ().strip ()or "Midterm"
        pr2_label =self ._trend_pr2_label .get ().strip ()or "PR2"

        import threading 
        def _worker ():
            try :
                from datetime import datetime 
                from utils .config import TREND_OUTPUT_FILENAME_PATTERN ,LOG_DATE_FORMAT 
                timestamp =datetime .now ().strftime (LOG_DATE_FORMAT )
                out_path =out_dir /TREND_OUTPUT_FILENAME_PATTERN .format (timestamp =timestamp )
                out_dir .mkdir (parents =True ,exist_ok =True )

                self .after (0 ,self ._trend_log_write ,"Loading workbooks...","step")
                analyzer =TrendAnalyzer ()
                analyzer .load (pr1_path ,mid_path ,pr2_path )

                overall =analyzer .overall_stats ()
                self .after (0 ,self ._trend_log_write ,
                f"Total unique at-risk students: {overall ['total_unique_students']:,}","info")
                if pr1_path :
                    self .after (0 ,self ._trend_log_write ,
                    f"{pr1_label }: {overall ['pr1_count']:,} students","info")
                if mid_path :
                    self .after (0 ,self ._trend_log_write ,
                    f"{mid_label }: {overall ['mid_count']:,} students","info")
                if pr2_path :
                    self .after (0 ,self ._trend_log_write ,
                    f"{pr2_label }: {overall ['pr2_count']:,} students","info")

                self .after (0 ,self ._trend_log_write ,"Building report with charts...","step")
                exporter =TrendExporter ()
                exporter .export (analyzer ,out_path ,pr1_label ,mid_label ,pr2_label )

                self .after (0 ,self ._on_trend_complete ,True ,str (out_path ),overall )
            except Exception :
                import traceback 
                self .after (0 ,self ._on_trend_complete ,False ,traceback .format_exc (),{})

        threading .Thread (target =_worker ,daemon =True ).start ()

    def _on_generate_master_report (self ):
        """Generate the end-of-semester master season report."""
        out_dir =self ._master_output_picker .path 
        if not out_dir :
            messagebox .showerror ("Missing Input","Please select an output folder.")
            return 

        paths ={
        "pr1":self ._master_pr1_picker .path ,
        "mid":self ._master_mid_picker .path ,
        "pr2":self ._master_pr2_picker .path ,
        }
        if not any (paths .values ()):
            messagebox .showerror ("Missing Input",
            "Please select at least one output workbook.")
            return 

        season =self ._campaign_season_var .get ().strip ()if hasattr (self ,"_campaign_season_var")else ""
        pr1_label =self ._trend_pr1_label .get ().strip ()or "Progress Report 1"
        mid_label =self ._trend_mid_label .get ().strip ()or "Midterm"
        pr2_label =self ._trend_pr2_label .get ().strip ()or "Progress Report 2"

        self ._trend_log_write ("="*55 ,"info")
        self ._trend_log_write ("GENERATING MASTER SEASON REPORT","step")
        self ._trend_log_write ("="*55 ,"info")

        import threading 
        def _worker ():
            try :
                from datetime import datetime 
                from utils .config import LOG_DATE_FORMAT 
                timestamp =datetime .now ().strftime (LOG_DATE_FORMAT )
                season_label =season .replace (" ","_")if season else "Season"
                out_path =Path (out_dir )/f"MasterReport_{season_label }_{timestamp }.xlsx"
                Path (out_dir ).mkdir (parents =True ,exist_ok =True )

                self .after (0 ,self ._trend_log_write ,"Loading output workbooks...","step")
                gen =SeasonReportGenerator ()
                gen .generate (
                pr1_path =Path (paths ["pr1"])if paths ["pr1"]else None ,
                mid_path =Path (paths ["mid"])if paths ["mid"]else None ,
                pr2_path =Path (paths ["pr2"])if paths ["pr2"]else None ,
                output_path =out_path ,
                season_name =season ,
                pr1_label =pr1_label ,
                mid_label =mid_label ,
                pr2_label =pr2_label ,
                )
                self .after (0 ,self ._on_master_report_done ,True ,str (out_path ))
            except Exception :
                import traceback 
                self .after (0 ,self ._on_master_report_done ,False ,traceback .format_exc ())

        threading .Thread (target =_worker ,daemon =True ).start ()

    def _on_master_report_done (self ,success ,message ):
        if success :
            self ._trend_log_write ("\n\u2705 Master report generated!","success")
            self ._trend_log_write ("\U0001f4c1 Output: "+message ,"success")
            messagebox .showinfo ("Master Report Complete",
            "\u2705 Master Season Report generated!\n\nOutput:\n"+message )
        else :
            self ._trend_log_write ("\n\u274c Failed:\n"+message [:400 ],"error")
            messagebox .showerror ("Master Report Failed",
            "\u274c Failed to generate report:\n\n"+message [:400 ])

    def _on_trend_complete (self ,success ,message ,overall ):
        self ._trend_processing =False 
        self ._semester_mgr =SemesterManager ()
        self ._trend_run_btn .config (state ="normal")
        self ._trend_progress_bar .stop ()
        if success :
            self ._trend_log_write ("\n\u2705 Report generated!","success")
            self ._trend_log_write ("\U0001f4c1 Output: "+message ,"success")
            messagebox .showinfo (
            "Trend Report Complete",
            "\u2705 Campaign Trend Report generated!\n\n"
            f"Total unique students: {overall .get ('total_unique_students',0 ):,}\n"
            f"Output:\n{message }",
            )
        else :
            self ._trend_log_write ("\n\u274c Failed:\n"+message [:400 ],"error")
            messagebox .showerror ("Trend Report Failed",
            "\u274c Report generation failed:\n\n"+message [:500 ])

    def _trend_clear_log (self ):
        clear_log(self._trend_log_box)

    def _trend_log_write (self ,message ,tag ="info"):
        append_log(self._trend_log_box, message, tag)


    def _build_campaign_tab (self ):
        """Build the redesigned Campaigns / Semester Manager tab."""
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


    def _build_settings_tab (self ):
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



    def _build_help_tab (self ):
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
