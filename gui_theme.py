"""
gui_theme.py — shared colors, button presets, and typography for the
Academic Intervention Sorter Tkinter interface.

Keep visual constants here so main.py and reusable widgets share one source
of truth for styling.
"""

import tkinter as tk

# ---------------------------------------------------------------------------
# Color system  (see gui/theme.py for the canonical reference)
# ---------------------------------------------------------------------------
NAVY         = "#003366"    # FAU brand navy — outer frames, active tab fg, brand labels
NAVY_LIGHT   = "#004488"    # Lighter brand navy — inactive tab bg
NAVY_DARK    = "#1a1f2e"    # Dark charcoal — header inner, primary buttons
NAVY_HOVER   = "#252c3d"    # Hover state for dark-charcoal buttons

RED_ACCENT   = "#c53030"    # Red accent stripe + danger buttons
RED_HOVER    = "#a12424"    # Hover for red buttons

WHITE        = "#ffffff"
PANEL_BG     = "#F0F4F8"    # Panel / content area background
PANEL_BG_DARK = "#E2E8F0"   # Slightly darker panel for contrast
BORDER       = "#CBD5E0"    # Entry highlight / separator

BTN_MUTED        = "#4A5568"    # Slate gray — Cancel, Skip, utility buttons
BTN_MUTED_HOVER  = "#3d4a5c"
BTN_SUCCESS      = "#276749"    # Green — affirmative / complete actions
BTN_SUCCESS_HOVER = "#1e5038"

TEXT_FG       = "#1A2332"
TEXT_MUTED    = "#4A5568"
SUCCESS_COLOR = "#276749"
WARNING_COLOR = "#C05621"
BG_COLOR      = NAVY

# Button style presets — unpack with ** into RoundedButton
# Example: RoundedButton(parent, text="Run", command=fn, **BTN_PRIMARY, font=FONT_BOLD)
BTN_PRIMARY         = dict(bg=NAVY_DARK,     fg=WHITE,    hover_bg=NAVY_HOVER)
BTN_SECONDARY_STYLE = dict(bg="#f0f2f5",     fg=TEXT_FG,  hover_bg="#e2e6ea")
BTN_DANGER          = dict(bg=RED_ACCENT,    fg=WHITE,    hover_bg=RED_HOVER)
BTN_SUCCESS_STYLE   = dict(bg=BTN_SUCCESS,   fg=WHITE,    hover_bg=BTN_SUCCESS_HOVER)
BTN_MUTED_STYLE     = dict(bg=BTN_MUTED,     fg=WHITE,    hover_bg=BTN_MUTED_HOVER)

# ---------------------------------------------------------------------------
# Font loading — Inter from assets/ folder
# ---------------------------------------------------------------------------
def load_inter_fonts() -> str:
    """
    Register Inter font files with tkinter and return the family name.
    Falls back to Segoe UI if font files are not found.
    """
    import tkinter.font as tkfont
    from pathlib import Path

    assets = Path(__file__).parent / "assets"
    fonts = {
        "regular":  assets / "Inter-Regular.ttf",
        "medium":   assets / "Inter-Medium.ttf",
        "semibold": assets / "Inter-SemiBold.ttf",
    }

    if not all(p.exists() for p in fonts.values()):
        return "Segoe UI"

    try:
        import ctypes
        FR_PRIVATE = 0x10
        for path in fonts.values():
            ctypes.windll.gdi32.AddFontResourceExW(str(path), FR_PRIVATE, 0)
        return "Inter"
    except Exception:
        try:
            root_check = tk.Tk()
            root_check.withdraw()
            tkfont.Font(root=root_check, family="Inter")
            root_check.destroy()
            return "Inter"
        except Exception:
            return "Segoe UI"

FONT_FAMILY = None  # Set after tk.Tk() is created

# ---------------------------------------------------------------------------
# Typography — Segoe UI default; updated by _apply_font() after font load
# ---------------------------------------------------------------------------
FONT_MAIN   = ("Segoe UI", 10)
FONT_BOLD   = ("Segoe UI", 10, "bold")
FONT_HEADER = ("Segoe UI", 15, "bold")
FONT_TITLE  = ("Segoe UI", 11, "bold")
FONT_SUB    = ("Segoe UI", 9)
FONT_SMALL  = ("Segoe UI", 8)
FONT_MONO   = ("Consolas", 9)

def apply_font(family: str) -> None:
    """Update all FONT_* globals to use the loaded font family."""
    global FONT_MAIN, FONT_BOLD, FONT_HEADER, FONT_TITLE, FONT_SUB, FONT_SMALL
    FONT_MAIN   = (family, 10)
    FONT_BOLD   = (family, 10, "bold")
    FONT_HEADER = (family, 15, "bold")
    FONT_TITLE  = (family, 11, "bold")
    FONT_SUB    = (family, 9)
    FONT_SMALL  = (family, 8)
    # FONT_MONO intentionally stays Consolas for log boxes

