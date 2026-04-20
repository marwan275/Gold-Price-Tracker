"""Shared Tkinter UI helpers for GoldTracker."""

from collections.abc import Callable
from typing import Any
import tkinter as tk

from ..config import COLORS


def create_surface(
    parent: tk.Widget,
    inner_bg: str | None = None,
) -> tuple[tk.Frame, tk.Frame]:
    """Create a bordered surface shell and its inner panel."""
    shell = tk.Frame(parent, bg=COLORS["border"], padx=1, pady=1)
    panel = tk.Frame(shell, bg=inner_bg or COLORS["bg_secondary"])
    panel.pack(fill=tk.BOTH, expand=True)
    return shell, panel


def _button_style(variant: str) -> dict[str, str]:
    """Return the color palette for a styled button variant."""
    if variant == "primary":
        return {
            "bg": COLORS["button_primary"],
            "fg": COLORS["button_primary_text"],
            "hover_bg": COLORS["button_primary_active"],
            "hover_fg": COLORS["button_primary_text"],
            "border": COLORS["button_primary"],
            "hover_border": COLORS["gold"],
        }
    if variant == "action_secondary":
        return {
            "bg": COLORS["bg_tertiary"],
            "fg": COLORS["text_primary"],
            "hover_bg": COLORS["button_bg"],
            "hover_fg": COLORS["text_primary"],
            "border": COLORS["border"],
            "hover_border": COLORS["button_active"],
        }
    if variant == "danger":
        return {
            "bg": COLORS["bg_tertiary"],
            "fg": COLORS["error"],
            "hover_bg": COLORS["button_bg"],
            "hover_fg": COLORS["error"],
            "border": COLORS["border"],
            "hover_border": COLORS["error"],
        }
    if variant == "stepper":
        return {
            "bg": COLORS["button_bg"],
            "fg": COLORS["text_primary"],
            "hover_bg": COLORS["button_active"],
            "hover_fg": COLORS["text_primary"],
            "border": COLORS["button_active"],
            "hover_border": COLORS["gold"],
        }
    return {
        "bg": COLORS["button_bg"],
        "fg": COLORS["text_primary"],
        "hover_bg": COLORS["button_active"],
        "hover_fg": COLORS["text_primary"],
        "border": COLORS["button_active"],
        "hover_border": COLORS["gold"],
    }


def create_styled_button(
    parent: tk.Widget,
    text: str,
    command: Callable[[], None],
    font: Any,
    variant: str = "secondary",
    icon: str | None = None,
    padx: int = 12,
    pady: int = 7,
    width: int | None = None,
) -> tk.Button:
    """Create a project-styled button with stored palette metadata."""
    style = _button_style(variant)
    label = f"{icon}  {text}" if icon else text
    options: dict[str, Any] = {}
    if width is not None:
        options["width"] = width

    button = tk.Button(
        parent,
        text=label,
        font=font,
        fg=style["fg"],
        bg=style["bg"],
        activebackground=style["hover_bg"],
        activeforeground=style["hover_fg"],
        bd=0,
        relief="flat",
        overrelief="flat",
        highlightthickness=1,
        highlightbackground=style["border"],
        highlightcolor=style["border"],
        disabledforeground=COLORS["text_muted"],
        padx=padx,
        pady=pady,
        cursor="hand2",
        command=command,
        **options,
    )
    button._gold_tracker_style = style
    bind_button_hover(button)
    return button


def restore_button_style(button: tk.Button) -> None:
    """Restore the default colors for a custom-styled button."""
    style = getattr(button, "_gold_tracker_style", None)
    if not style:
        return

    button.config(
        bg=style["bg"],
        fg=style["fg"],
        activebackground=style["hover_bg"],
        activeforeground=style["hover_fg"],
        highlightbackground=style["border"],
        highlightcolor=style["border"],
    )


def bind_button_hover(button: tk.Button) -> None:
    """Bind hover styling to a custom-styled button."""

    def on_enter(_event):
        if str(button.cget("state")) == tk.DISABLED:
            return

        style = getattr(button, "_gold_tracker_style", None)
        if not style:
            return

        button.config(
            bg=style["hover_bg"],
            fg=style["hover_fg"],
            activebackground=style["hover_bg"],
            activeforeground=style["hover_fg"],
            highlightbackground=style["hover_border"],
            highlightcolor=style["hover_border"],
        )

    def on_leave(_event):
        if str(button.cget("state")) == tk.DISABLED:
            return

        restore_button_style(button)

    button.bind("<Enter>", on_enter)
    button.bind("<Leave>", on_leave)
