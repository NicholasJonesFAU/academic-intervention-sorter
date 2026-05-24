"""
Reusable Tkinter widgets for the Academic Intervention Sorter GUI.

This module intentionally contains only presentation helpers:
  - section_label
  - RoundedButton
  - FilePickerRow

Business logic and processing remain in main.py and the processors package.
"""

import tkinter as tk
from tkinter import filedialog


# ---------------------------------------------------------------------------
# Color system
# ---------------------------------------------------------------------------
NAVY         = "#003366"
NAVY_LIGHT   = "#004488"
NAVY_DARK    = "#1a1f2e"
NAVY_HOVER   = "#252c3d"

RED_ACCENT   = "#c53030"
RED_HOVER    = "#a12424"

WHITE        = "#ffffff"
PANEL_BG     = "#F0F4F8"
PANEL_BG_DARK = "#E2E8F0"
BORDER       = "#CBD5E0"

BTN_MUTED        = "#4A5568"
BTN_MUTED_HOVER  = "#3d4a5c"
BTN_SUCCESS      = "#276749"
BTN_SUCCESS_HOVER = "#1e5038"

TEXT_FG       = "#1A2332"
TEXT_MUTED    = "#4A5568"

BTN_PRIMARY         = dict(bg=NAVY_DARK,     fg=WHITE,    hover_bg=NAVY_HOVER)
BTN_SECONDARY_STYLE = dict(bg="#f0f2f5",     fg=TEXT_FG,  hover_bg="#e2e6ea")
BTN_DANGER          = dict(bg=RED_ACCENT,    fg=WHITE,    hover_bg=RED_HOVER)
BTN_SUCCESS_STYLE   = dict(bg=BTN_SUCCESS,   fg=WHITE,    hover_bg=BTN_SUCCESS_HOVER)
BTN_MUTED_STYLE     = dict(bg=BTN_MUTED,     fg=WHITE,    hover_bg=BTN_MUTED_HOVER)


# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------
FONT_MAIN   = ("Segoe UI", 10)
FONT_BOLD   = ("Segoe UI", 10, "bold")
FONT_HEADER = ("Segoe UI", 15, "bold")
FONT_TITLE  = ("Segoe UI", 11, "bold")
FONT_SUB    = ("Segoe UI", 9)
FONT_SMALL  = ("Segoe UI", 8)
FONT_MONO   = ("Consolas", 9)


def apply_font(family: str) -> None:
    """Keep reusable widgets visually aligned with the app-level font."""
    global FONT_MAIN, FONT_BOLD, FONT_HEADER, FONT_TITLE, FONT_SUB, FONT_SMALL
    FONT_MAIN   = (family, 10)
    FONT_BOLD   = (family, 10, "bold")
    FONT_HEADER = (family, 15, "bold")
    FONT_TITLE  = (family, 11, "bold")
    FONT_SUB    = (family, 9)
    FONT_SMALL  = (family, 8)


def section_label(parent, text: str) -> tk.Frame:
    """Left red-accent bar + uppercase section heading."""
    frame = tk.Frame(parent, bg=PANEL_BG)
    tk.Frame(frame, bg=RED_ACCENT, width=3).pack(side="left", fill="y", padx=(0, 8))
    tk.Label(frame, text=text.upper(), bg=PANEL_BG,
             fg=NAVY_DARK, font=FONT_TITLE).pack(side="left", anchor="w")
    return frame


class RoundedButton(tk.Canvas):
    """
    Canvas-drawn button with rounded corners and consistent hover / active states.

    Use the module-level BTN_* style presets for visual hierarchy:
        RoundedButton(parent, text="Run",   command=fn, **BTN_PRIMARY,        font=FONT_BOLD)
        RoundedButton(parent, text="Clear", command=fn, **BTN_SECONDARY_STYLE, font=FONT_MAIN)
        RoundedButton(parent, text="Reset", command=fn, **BTN_DANGER,          font=FONT_MAIN)
        RoundedButton(parent, text="Done",  command=fn, **BTN_SUCCESS_STYLE,   font=FONT_BOLD)
        RoundedButton(parent, text="Skip",  command=fn, **BTN_MUTED_STYLE,     font=FONT_MAIN)
    """

    _DISABLED_COLOR = "#9aa3b0"

    def __init__(self, parent, text, command=None,
                 bg=NAVY_DARK, fg=WHITE, hover_bg=None,
                 font=None, padx=20, pady=9, radius=6, **kwargs):
        self._bg      = bg
        self._hover   = hover_bg or self._darken(bg)
        self._fg      = fg
        self._text    = text
        self._command = command
        self._radius  = radius
        self._font    = font or FONT_BOLD
        self._padx    = padx
        self._pady    = pady

        # Measure text to size the canvas correctly
        tmp = tk.Label(parent, text=text, font=self._font)
        tmp.update_idletasks()
        w = tmp.winfo_reqwidth() + padx * 2
        h = tmp.winfo_reqheight() + pady * 2
        tmp.destroy()

        super().__init__(parent, width=w, height=h,
                         bg=parent.cget("bg"),
                         highlightthickness=0, cursor="hand2", **kwargs)

        self._draw(self._bg)
        self._bind_active()

    # ── Drawing ────────────────────────────────────────────────────────────

    def _draw(self, color: str) -> None:
        self.delete("all")
        w, h, r = int(self["width"]), int(self["height"]), self._radius
        self.create_arc(0,     0,     r*2,   r*2,   start=90,  extent=90, fill=color, outline=color)
        self.create_arc(w-r*2, 0,     w,     r*2,   start=0,   extent=90, fill=color, outline=color)
        self.create_arc(0,     h-r*2, r*2,   h,     start=180, extent=90, fill=color, outline=color)
        self.create_arc(w-r*2, h-r*2, w,     h,     start=270, extent=90, fill=color, outline=color)
        self.create_rectangle(r, 0,   w-r,   h,     fill=color, outline=color)
        self.create_rectangle(0, r,   w,     h-r,   fill=color, outline=color)
        self.create_text(w//2, h//2, text=self._text, fill=self._fg,
                         font=self._font, anchor="center")

    # ── Interaction ────────────────────────────────────────────────────────

    def _on_press(self) -> None:
        self._draw(self._darken(self._hover))

    def _on_release(self) -> None:
        self._draw(self._hover)
        if self._command:
            self._command()

    # ── Event binding helpers ──────────────────────────────────────────────

    def _bind_active(self) -> None:
        self.bind("<Enter>",           lambda e: self._draw(self._hover))
        self.bind("<Leave>",           lambda e: self._draw(self._bg))
        self.bind("<Button-1>",        lambda e: self._on_press())
        self.bind("<ButtonRelease-1>", lambda e: self._on_release())

    def _unbind_active(self) -> None:
        for seq in ("<Enter>", "<Leave>", "<Button-1>", "<ButtonRelease-1>"):
            self.unbind(seq)

    # ── State management ───────────────────────────────────────────────────

    def config(self, **kwargs) -> None:
        if "state" in kwargs:
            if kwargs["state"] == "disabled":
                self._draw(self._DISABLED_COLOR)
                self._unbind_active()
                self.configure(cursor="")
            elif kwargs["state"] == "normal":
                self._draw(self._bg)
                self._bind_active()
                self.configure(cursor="hand2")
            remaining = {k: v for k, v in kwargs.items() if k != "state"}
        else:
            remaining = kwargs
        if remaining:
            super().config(**remaining)

    # ── Utilities ──────────────────────────────────────────────────────────

    @staticmethod
    def _darken(hex_color: str) -> str:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"#{max(0,r-25):02x}{max(0,g-25):02x}{max(0,b-25):02x}"


class FilePickerRow(tk.Frame):
    """A labeled file-picker row: [Label] [Entry (path)] [Browse button]."""

    def __init__(
        self,
        parent,
        label: str,
        filetypes: list,
        is_directory: bool = False,
        tooltip: str = "",
        **kwargs,
    ):
        super().__init__(parent, bg=PANEL_BG, **kwargs)
        self._path = tk.StringVar()
        self._is_directory = is_directory

        lbl = tk.Label(
            self, text=label, bg=PANEL_BG, fg=TEXT_FG,
            font=FONT_BOLD, width=22, anchor="w",
        )
        lbl.grid(row=0, column=0, padx=(0, 8), sticky="w")

        entry = tk.Entry(
            self, textvariable=self._path, font=FONT_MAIN,
            width=48, relief="flat", bg="#ffffff",
            fg=TEXT_FG, insertbackground=NAVY,
            highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=NAVY,
        )
        entry.grid(row=0, column=1, padx=(0, 8), ipady=5)

        RoundedButton(
            self, text="Browse",
            command=lambda: self._browse(filetypes),
            **BTN_MUTED_STYLE, font=FONT_BOLD, padx=12, pady=5, radius=6,
        ).grid(row=0, column=2)

        if tooltip:
            tip = tk.Label(
                self, text=tooltip, bg=PANEL_BG, fg=TEXT_MUTED,
                font=FONT_SUB,
            )
            tip.grid(row=1, column=1, sticky="w", pady=(2, 0))

        self.columnconfigure(1, weight=1)

    def _browse(self, filetypes):
        if self._is_directory:
            path = filedialog.askdirectory(title="Select Folder")
        else:
            path = filedialog.askopenfilename(filetypes=filetypes)
        if path:
            self._path.set(path)

    @property
    def path(self) -> str:
        return self._path.get().strip()

    @path.setter
    def path(self, value: str):
        self._path.set(value)

