"""Shared logging helpers for Academic Intervention Sorter GUI log boxes."""

from __future__ import annotations

import tkinter as tk

DEFAULT_LOG_TAGS = {
    "success": "#68D391",
    "error": "#FC8181",
    "warning": "#F6AD55",
    "info": "#90CDF4",
    "step": "#c53030",
}

PURPLE_LOG_TAGS = {
    "success": "#4CAF50",
    "error": "#F44336",
    "warning": "#FF9800",
    "info": "#90CAF9",
    "step": "#CE93D8",
}


def configure_log_tags(log_box: tk.Text, tags: dict[str, str] | None = None) -> None:
    """Apply consistent color tags to a Tkinter Text/ScrolledText log box."""
    for tag, color in (tags or DEFAULT_LOG_TAGS).items():
        log_box.tag_config(tag, foreground=color)


def append_log(log_box: tk.Text, message: str, tag: str = "info") -> None:
    """Append a message to a disabled log box and keep it scrolled to the end."""
    log_box.config(state="normal")
    log_box.insert("end", message + "\n", tag)
    log_box.see("end")
    log_box.config(state="disabled")


def clear_log(log_box: tk.Text) -> None:
    """Clear a disabled log box safely."""
    log_box.config(state="normal")
    log_box.delete("1.0", "end")
    log_box.config(state="disabled")
