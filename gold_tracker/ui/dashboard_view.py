"""Main dashboard view for GoldTracker."""

from collections.abc import Callable
import tkinter as tk
from tkinter import font as tkfont

from ..config import COLORS, FONT_FAMILY, WINDOW_TITLE
from .components import create_styled_button, create_surface, restore_button_style


class MainDashboardView:
    """Build and manage the main application dashboard widgets."""

    def __init__(
        self,
        root: tk.Misc,
        grams_var: tk.StringVar,
        total_value_var: tk.StringVar,
        trend_text_var: tk.StringVar,
        egypt_price_var: tk.StringVar,
        world_price_var: tk.StringVar,
        last_update_var: tk.StringVar,
        price_note_var: tk.StringVar,
        on_decrease_grams: Callable[[], None],
        on_increase_grams: Callable[[], None],
        on_grams_change: Callable[..., None],
        validate_numeric_input: Callable[[str], bool],
        on_refresh: Callable[[], None],
        on_copy_value: Callable[[], None],
        on_show_history: Callable[[], None],
        on_profit_calculator: Callable[[], None],
    ) -> None:
        """Create the dashboard view and wire widget callbacks."""
        self.root = root
        self.grams_var = grams_var
        self.total_value_var = total_value_var
        self.trend_text_var = trend_text_var
        self.egypt_price_var = egypt_price_var
        self.world_price_var = world_price_var
        self.last_update_var = last_update_var
        self.price_note_var = price_note_var

        self._build_fonts()
        self._build_ui(
            on_decrease_grams=on_decrease_grams,
            on_increase_grams=on_increase_grams,
            on_grams_change=on_grams_change,
            validate_numeric_input=validate_numeric_input,
            on_refresh=on_refresh,
            on_copy_value=on_copy_value,
            on_show_history=on_show_history,
            on_profit_calculator=on_profit_calculator,
        )

    def focus_grams_entry(self) -> None:
        """Place keyboard focus on the grams input field."""
        self.grams_entry.focus_set()

    def disable_button(self, button: tk.Button) -> None:
        """Apply the neutral disabled state used by dashboard actions."""
        button.config(
            state=tk.DISABLED,
            fg=COLORS["text_muted"],
            bg=COLORS["bg_tertiary"],
            activebackground=COLORS["bg_tertiary"],
            activeforeground=COLORS["text_muted"],
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["border"],
            cursor="",
        )

    def enable_button(self, button: tk.Button) -> None:
        """Re-enable a dashboard button and restore its default style."""
        button.config(state=tk.NORMAL, cursor="hand2")
        self.restore_button_style(button)

    def restore_button_style(self, button: tk.Button) -> None:
        """Restore the default colors for a custom-styled button."""
        restore_button_style(button)

    def _build_fonts(self) -> None:
        """Create the font objects shared by the dashboard widgets."""
        self.title_font = tkfont.Font(family=FONT_FAMILY, size=28, weight="bold")
        self.subtitle_font = tkfont.Font(family=FONT_FAMILY, size=11)
        self.section_font = tkfont.Font(family=FONT_FAMILY, size=11, weight="bold")
        self.helper_font = tkfont.Font(family=FONT_FAMILY, size=10)
        self.stepper_font = tkfont.Font(family=FONT_FAMILY, size=22, weight="bold")
        self.grams_font = tkfont.Font(family=FONT_FAMILY, size=30, weight="bold")
        self.value_font = tkfont.Font(family=FONT_FAMILY, size=38, weight="bold")
        self.metric_font = tkfont.Font(family=FONT_FAMILY, size=16, weight="bold")
        self.action_font = tkfont.Font(family=FONT_FAMILY, size=12, weight="bold")
        self.trend_font = tkfont.Font(family=FONT_FAMILY, size=12, weight="bold")

    def _build_ui(
        self,
        on_decrease_grams: Callable[[], None],
        on_increase_grams: Callable[[], None],
        on_grams_change: Callable[..., None],
        validate_numeric_input: Callable[[str], bool],
        on_refresh: Callable[[], None],
        on_copy_value: Callable[[], None],
        on_show_history: Callable[[], None],
        on_profit_calculator: Callable[[], None],
    ) -> None:
        """Construct the full main-window dashboard layout."""
        container = tk.Frame(self.root, bg=COLORS["bg_primary"], padx=24, pady=18)
        container.pack(fill=tk.BOTH, expand=True)
        container.grid_columnconfigure(0, weight=1)

        header_shell, header = self._create_surface(container)
        header_shell.grid(row=0, column=0, sticky="ew")
        header.configure(padx=24, pady=18)

        tk.Label(
            header,
            text=WINDOW_TITLE,
            font=self.title_font,
            fg=COLORS["gold"],
            bg=COLORS["bg_secondary"],
        ).pack(anchor="w")

        tk.Label(
            header,
            text="Track Egypt and global gold prices live, then open history when you need broader market context.",
            font=self.subtitle_font,
            fg=COLORS["text_soft"],
            bg=COLORS["bg_secondary"],
            wraplength=760,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        hero_row = tk.Frame(container, bg=COLORS["bg_primary"])
        hero_row.grid(row=1, column=0, sticky="ew", pady=(18, 14))
        hero_row.grid_columnconfigure(0, weight=1)
        hero_row.grid_columnconfigure(1, weight=1)

        controls_shell, controls_card = self._create_surface(hero_row)
        controls_shell.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        controls_card.configure(padx=20, pady=18)

        tk.Label(
            controls_card,
            text="WEIGHT SELECTOR",
            font=self.section_font,
            fg=COLORS["text_soft"],
            bg=COLORS["bg_secondary"],
        ).pack(anchor="w")

        tk.Label(
            controls_card,
            text="Type grams directly or use the stepper. Decimals are supported.",
            font=self.subtitle_font,
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_secondary"],
            wraplength=340,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        stepper_shell, stepper = self._create_surface(
            controls_card,
            inner_bg=COLORS["bg_tertiary"],
        )
        stepper_shell.pack(fill=tk.X, pady=(14, 10))
        stepper.configure(padx=10, pady=8)
        stepper.grid_columnconfigure(1, weight=1)

        self._create_stepper_button(stepper, "−", on_decrease_grams).grid(
            row=0,
            column=0,
            padx=(0, 10),
            pady=0,
        )

        validation_command = (self.root.register(validate_numeric_input), "%P")
        self.grams_entry = tk.Entry(
            stepper,
            textvariable=self.grams_var,
            font=self.grams_font,
            fg=COLORS["gold"],
            bg=COLORS["bg_tertiary"],
            bd=0,
            relief="flat",
            width=6,
            justify="center",
            insertbackground=COLORS["gold"],
            validate="key",
            validatecommand=validation_command,
        )
        self.grams_entry.grid(row=0, column=1, padx=10, pady=0, sticky="ew")
        self.grams_entry.bind("<KeyRelease>", on_grams_change)

        self._create_stepper_button(stepper, "+", on_increase_grams).grid(
            row=0,
            column=2,
            padx=(10, 0),
            pady=0,
        )

        tk.Label(
            controls_card,
            text="Your estimate recalculates automatically whenever the market feed changes.",
            font=self.helper_font,
            fg=COLORS["text_soft"],
            bg=COLORS["bg_secondary"],
            wraplength=340,
            justify="left",
        ).pack(anchor="w")

        estimate_shell, estimate_card = self._create_surface(hero_row)
        estimate_shell.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        estimate_card.configure(padx=20, pady=18)

        tk.Label(
            estimate_card,
            text="PORTFOLIO ESTIMATE",
            font=self.section_font,
            fg=COLORS["text_soft"],
            bg=COLORS["bg_secondary"],
        ).pack(anchor="w")

        tk.Label(
            estimate_card,
            text="The main value card follows the Egypt market first and falls back safely when needed.",
            font=self.subtitle_font,
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_secondary"],
            wraplength=340,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        value_band = tk.Frame(
            estimate_card,
            bg=COLORS["bg_tertiary"],
            padx=18,
            pady=16,
        )
        value_band.pack(fill=tk.X, pady=(14, 10))

        self.value_display = tk.Label(
            value_band,
            textvariable=self.total_value_var,
            font=self.value_font,
            fg=COLORS["success"],
            bg=COLORS["bg_tertiary"],
            anchor="w",
        )
        self.value_display.pack(anchor="w")

        tk.Label(
            estimate_card,
            textvariable=self.price_note_var,
            font=self.helper_font,
            fg=COLORS["text_soft"],
            bg=COLORS["bg_secondary"],
            wraplength=340,
            justify="left",
        ).pack(anchor="w")

        self.trend_label = tk.Label(
            estimate_card,
            textvariable=self.trend_text_var,
            font=self.trend_font,
            fg=COLORS["text_soft"],
            bg=COLORS["bg_tertiary"],
            padx=14,
            pady=8,
        )
        self.trend_label.pack(anchor="w", pady=(10, 0))

        summary_row = tk.Frame(container, bg=COLORS["bg_primary"])
        summary_row.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        for column in range(3):
            summary_row.grid_columnconfigure(column, weight=1)

        self._build_summary_card(
            summary_row,
            column=0,
            title="EGYPT MARKET",
            value_var=self.egypt_price_var,
            note="Local market per gram",
            accent=COLORS["gold"],
        )
        self._build_summary_card(
            summary_row,
            column=1,
            title="WORLD MARKET",
            value_var=self.world_price_var,
            note="Converted live price per gram",
            accent=COLORS["warning"],
        )
        self._build_summary_card(
            summary_row,
            column=2,
            title="LAST SYNC",
            value_var=self.last_update_var,
            note="Most recent refresh time",
            accent=COLORS["success"],
        )

        status_shell, status_panel = self._create_surface(container)
        status_shell.grid(row=3, column=0, sticky="ew", pady=(0, 12))

        self.status_label = tk.Label(
            status_panel,
            text="Preparing live market sync...",
            font=self.subtitle_font,
            fg=COLORS["text_soft"],
            bg=COLORS["bg_secondary"],
            padx=18,
            pady=10,
            justify="center",
        )
        self.status_label.pack(fill=tk.X)

        actions_shell, actions_panel = self._create_surface(container)
        actions_shell.grid(row=4, column=0, sticky="ew")
        actions_panel.configure(padx=12, pady=12)
        for column in range(2):
            actions_panel.grid_columnconfigure(column, weight=1)

        self.refresh_btn = self._create_action_button(
            actions_panel,
            "Refresh data",
            on_refresh,
            icon="↻",
        )
        self.refresh_btn.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(0, 8),
        )
        self.copy_btn = self._create_action_button(
            actions_panel,
            "Copy value",
            on_copy_value,
            icon="⧉",
        )
        self.copy_btn.grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(8, 0),
        )
        self.history_btn = None
        self.profit_calculator_btn = None

    def _create_surface(
        self,
        parent: tk.Widget,
        inner_bg: str | None = None,
    ) -> tuple[tk.Frame, tk.Frame]:
        """Create a framed dashboard surface and its inner panel."""
        return create_surface(parent, inner_bg=inner_bg)

    def _build_summary_card(
        self,
        parent: tk.Widget,
        column: int,
        title: str,
        value_var: tk.StringVar,
        note: str,
        accent: str,
    ) -> None:
        """Build one of the compact market summary cards."""
        shell, panel = self._create_surface(parent)
        shell.grid(
            row=0,
            column=column,
            sticky="nsew",
            padx=(0 if column == 0 else 6, 0 if column == 2 else 6),
        )
        panel.configure(padx=14, pady=12)

        tk.Frame(panel, bg=accent, height=4).pack(fill=tk.X, pady=(0, 10))
        tk.Label(
            panel,
            text=title,
            font=self.section_font,
            fg=COLORS["text_soft"],
            bg=COLORS["bg_secondary"],
        ).pack(anchor="w")
        tk.Label(
            panel,
            textvariable=value_var,
            font=self.metric_font,
            fg=COLORS["text_primary"],
            bg=COLORS["bg_secondary"],
        ).pack(anchor="w", pady=(10, 6))
        tk.Label(
            panel,
            text=note,
            font=self.helper_font,
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_secondary"],
            wraplength=220,
            justify="left",
        ).pack(anchor="w")

    def _create_stepper_button(
        self,
        parent: tk.Widget,
        text: str,
        command: Callable[[], None],
    ) -> tk.Button:
        """Create one of the grams stepper buttons."""
        return create_styled_button(
            parent,
            text=text,
            command=command,
            font=self.stepper_font,
            variant="stepper",
            width=3,
            padx=0,
            pady=10,
        )

    def _create_action_button(
        self,
        parent: tk.Widget,
        text: str,
        command: Callable[[], None],
        icon: str,
        variant: str = "secondary",
    ) -> tk.Button:
        """Create a dashboard action button with icon and variant styling."""
        button_variant = "primary" if variant == "primary" else "action_secondary"
        return create_styled_button(
            parent,
            text=text,
            command=command,
            font=self.action_font,
            variant=button_variant,
            icon=icon,
            padx=18,
            pady=11,
        )
