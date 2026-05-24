"""
gui/theme.py — Design-token reference for the Academic Intervention Sorter.

All color constants and button-style presets live here.  main.py mirrors these
values; import from this module if you are building new GUI components.

Palette: FAU Navy (#003366) + Dark Charcoal (#1a1f2e) + Red Accent (#c53030)
         on a cool light-gray panel (#F0F4F8).
"""

# ---------------------------------------------------------------------------
# Core palette
# ---------------------------------------------------------------------------

NAVY         = "#003366"    # FAU brand navy — outer frames, active tab fg, brand labels
NAVY_LIGHT   = "#004488"    # Lighter brand navy — inactive tab bg
NAVY_DARK    = "#1a1f2e"    # Dark charcoal — header inner, primary buttons
NAVY_HOVER   = "#252c3d"    # Hover for dark-charcoal buttons

RED_ACCENT   = "#c53030"    # Red accent stripe + danger buttons
RED_HOVER    = "#a12424"    # Hover for red buttons

WHITE        = "#ffffff"
PANEL_BG     = "#F0F4F8"    # Panel / content area background
PANEL_CARD   = "#ffffff"    # Card / inner-content background
PANEL_BG_DARK = "#E2E8F0"   # Slightly darker panel for contrast
BORDER       = "#CBD5E0"    # Entry highlight / separator

# ---------------------------------------------------------------------------
# Button backgrounds
# ---------------------------------------------------------------------------

BTN_SECONDARY       = "#f0f2f5"    # Light-gray secondary buttons
BTN_SECONDARY_HOVER = "#e2e6ea"

BTN_MUTED           = "#4A5568"    # Slate gray — Cancel, Skip, utility
BTN_MUTED_HOVER     = "#3d4a5c"

BTN_SUCCESS         = "#276749"    # Green — affirmative / complete actions
BTN_SUCCESS_HOVER   = "#1e5038"

# ---------------------------------------------------------------------------
# Text / semantic
# ---------------------------------------------------------------------------

TEXT_FG       = "#1A2332"
TEXT_MUTED    = "#4A5568"
TEXT_LIGHT    = "#9aa3b0"
ACCENT_FG     = NAVY
SUCCESS_COLOR = BTN_SUCCESS
WARNING_COLOR = "#C05621"
BG_COLOR      = NAVY           # Outer window background

# ---------------------------------------------------------------------------
# Button style presets
# Unpack with ** into RoundedButton:
#   RoundedButton(parent, text="Run", command=fn, **BTN_PRIMARY, font=FONT_BOLD)
# ---------------------------------------------------------------------------

BTN_PRIMARY         = dict(bg=NAVY_DARK,         fg=WHITE,    hover_bg=NAVY_HOVER)
BTN_SECONDARY_STYLE = dict(bg=BTN_SECONDARY,      fg=TEXT_FG,  hover_bg=BTN_SECONDARY_HOVER)
BTN_DANGER          = dict(bg=RED_ACCENT,          fg=WHITE,    hover_bg=RED_HOVER)
BTN_SUCCESS_STYLE   = dict(bg=BTN_SUCCESS,         fg=WHITE,    hover_bg=BTN_SUCCESS_HOVER)
BTN_MUTED_STYLE     = dict(bg=BTN_MUTED,           fg=WHITE,    hover_bg=BTN_MUTED_HOVER)
