"""Single-window application shell with sidebar navigation."""

from collections.abc import Callable
import tkinter as tk
from tkinter import font as tkfont

from ..config import APP_NAME, COLORS, FONT_FAMILY
from .components import create_styled_button, restore_button_style


class AppShell:
    """Own the persistent sidebar and switch the central content view."""

    def __init__(
        self,
        root: tk.Misc,
        on_show_dashboard: Callable[[], None],
        on_show_profit: Callable[[], None],
        on_show_history: Callable[[], None],
    ) -> None:
        """Build the app shell around the main content host."""
        self.root = root
        self._views: dict[str, tk.Widget] = {}
        self._active_view: str | None = None
        self._nav_buttons: dict[str, tk.Button] = {}
        self._nav_default_styles: dict[str, dict[str, str]] = {}

        self._build_fonts()
        self._build_ui(
            on_show_dashboard=on_show_dashboard,
            on_show_profit=on_show_profit,
            on_show_history=on_show_history,
        )

    def add_view(self, name: str, frame: tk.Widget) -> None:
        """Register a content frame that can be shown by name."""
        self._views[name] = frame

    def remove_view(self, name: str) -> None:
        """Forget a registered content frame."""
        self._views.pop(name, None)
        if self._active_view == name:
            self._active_view = None

    def show_view(self, name: str) -> None:
        """Raise one registered content frame and update sidebar selection."""
        frame = self._views.get(name)
        if frame is None:
            return

        for view in self._views.values():
            view.pack_forget()
        frame.pack(fill=tk.BOTH, expand=True)
        self._active_view = name
        self._sync_nav_state(name)

    def set_history_enabled(self, enabled: bool) -> None:
        """Enable or disable the history sidebar action."""
        button = self._nav_buttons.get("history")
        if button is None:
            return
        button.config(state=tk.NORMAL if enabled else tk.DISABLED)
        if enabled:
            button.config(cursor="hand2")
            if self._active_view == "history":
                self._sync_nav_state("history")
            else:
                restore_button_style(button)
        else:
            button.config(
                fg=COLORS["text_muted"],
                bg=COLORS["bg_tertiary"],
                activebackground=COLORS["bg_tertiary"],
                activeforeground=COLORS["text_muted"],
                highlightbackground=COLORS["border"],
                highlightcolor=COLORS["border"],
                cursor="",
            )

    def _build_fonts(self) -> None:
        """Create fonts used in the shell."""
        self.brand_font = tkfont.Font(family=FONT_FAMILY, size=18, weight="bold")
        self.subtitle_font = tkfont.Font(family=FONT_FAMILY, size=10)
        self.nav_font = tkfont.Font(family=FONT_FAMILY, size=11, weight="bold")

    def _build_ui(
        self,
        on_show_dashboard: Callable[[], None],
        on_show_profit: Callable[[], None],
        on_show_history: Callable[[], None],
    ) -> None:
        """Create the shell frame, sidebar, and content host."""
        self.shell = tk.Frame(self.root, bg=COLORS["bg_primary"])
        self.shell.pack(fill=tk.BOTH, expand=True)
        self.shell.grid_columnconfigure(1, weight=1)
        self.shell.grid_rowconfigure(0, weight=1)

        sidebar = tk.Frame(
            self.shell,
            bg=COLORS["bg_secondary"],
            padx=14,
            pady=18,
            width=220,
        )
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)

        tk.Label(
            sidebar,
            text=APP_NAME.replace(" Tracker", "\nTracker", 1),
            font=self.brand_font,
            fg=COLORS["gold"],
            bg=COLORS["bg_secondary"],
            justify="center",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 18))

        self._create_nav_button(
            sidebar,
            name="dashboard",
            text="Dashboard",
            icon="⌂",
            command=on_show_dashboard,
            row=1,
        )
        self._create_nav_button(
            sidebar,
            name="profit",
            text="Calculator",
            icon="$",
            command=on_show_profit,
            row=2,
        )
        self._create_nav_button(
            sidebar,
            name="history",
            text="History",
            icon="▤",
            command=on_show_history,
            row=3,
        )

        tk.Label(
            sidebar,
            text="Prices update automatically in the background.",
            font=self.subtitle_font,
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_secondary"],
            wraplength=170,
            justify="left",
        ).grid(row=4, column=0, sticky="sw", pady=(28, 0))

        self.content_frame = tk.Frame(self.shell, bg=COLORS["bg_primary"])
        self.content_frame.grid(row=0, column=1, sticky="nsew")

    def _create_nav_button(
        self,
        parent: tk.Widget,
        name: str,
        text: str,
        icon: str,
        command: Callable[[], None],
        row: int,
    ) -> None:
        """Create a sidebar navigation button."""
        button = create_styled_button(
            parent,
            text=text,
            command=command,
            font=self.nav_font,
            variant="action_secondary",
            icon=icon,
            padx=10,
            pady=10,
        )
        button.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        self._nav_buttons[name] = button
        self._nav_default_styles[name] = dict(button._gold_tracker_style)

    def _sync_nav_state(self, active_name: str) -> None:
        """Style the active sidebar item."""
        for name, button in self._nav_buttons.items():
            if str(button.cget("state")) == tk.DISABLED:
                continue
            if name == active_name:
                button._gold_tracker_style = {
                    "bg": COLORS["button_primary"],
                    "fg": COLORS["button_primary_text"],
                    "hover_bg": COLORS["button_primary_active"],
                    "hover_fg": COLORS["button_primary_text"],
                    "border": COLORS["gold"],
                    "hover_border": COLORS["gold"],
                }
                button.config(
                    bg=COLORS["button_primary"],
                    fg=COLORS["button_primary_text"],
                    activebackground=COLORS["button_primary_active"],
                    activeforeground=COLORS["button_primary_text"],
                    highlightbackground=COLORS["gold"],
                    highlightcolor=COLORS["gold"],
                )
            else:
                button._gold_tracker_style = self._nav_default_styles[name]
                restore_button_style(button)
