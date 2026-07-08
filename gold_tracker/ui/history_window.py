"""Dedicated history window UI for GoldTracker."""

from collections.abc import Callable
import logging
import tkinter as tk
from tkinter import font as tkfont

try:
    import matplotlib.dates as mdates
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    from matplotlib.ticker import FuncFormatter

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

from ..config import (
    COLORS,
    FONT_FAMILY,
    HISTORY_CHART_MONTH_INTERVAL,
    HISTORY_WINDOW_MIN_HEIGHT,
    HISTORY_WINDOW_MIN_WIDTH,
    HISTORY_WINDOW_SIZE,
    HISTORY_WINDOW_TITLE,
)
from ..models import HistoricalPriceSeries


logger = logging.getLogger(__name__)


class HistoryWindowError(Exception):
    """Raised when the history window cannot be shown."""


def history_window_available() -> bool:
    """Return True when matplotlib chart dependencies imported successfully."""
    return MATPLOTLIB_AVAILABLE


def history_window_unavailable_message() -> str:
    """Return the message shown when matplotlib is missing."""
    return "Install matplotlib: pip install matplotlib"


class HistoryWindow:
    """Interactive top-level window for historical gold price analysis."""

    def __init__(
        self,
        parent: tk.Misc,
        history_series: HistoricalPriceSeries,
        on_close: Callable[[], None] | None = None,
        embedded: bool = False,
    ):
        """Create the history window and initialize its chart state."""
        if not history_window_available():
            raise HistoryWindowError(history_window_unavailable_message())

        self.history_series = history_series
        self._on_close = on_close
        self._embedded = embedded
        self._closed = False
        self._figure = None
        self._canvas = None

        if self._embedded:
            self.window = tk.Frame(parent, bg=COLORS["bg_primary"])
        else:
            self.window = tk.Toplevel(parent)
            self.window.title(HISTORY_WINDOW_TITLE)
            self.window.geometry(HISTORY_WINDOW_SIZE)
            self.window.minsize(HISTORY_WINDOW_MIN_WIDTH, HISTORY_WINDOW_MIN_HEIGHT)
            self.window.configure(bg=COLORS["bg_primary"])
            self.window.resizable(True, True)
            self.window.transient(parent)
            self.window.protocol("WM_DELETE_WINDOW", self.close)
            self.window.bind("<Escape>", lambda _event: self.close())

        self._build_ui()
        self.lift()

    def is_open(self) -> bool:
        """Return True while the underlying window still exists."""
        return bool(self.window and self.window.winfo_exists())

    def lift(self) -> None:
        """Bring the window to the front."""
        if self.is_open():
            if self._embedded:
                self.window.focus_set()
                return
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()

    def close(self) -> None:
        """Destroy the history window and notify the parent app."""
        if self._closed:
            return

        self._closed = True

        if self._figure is not None:
            self._figure.clear()
            self._figure = None

        if self._canvas is not None:
            self._canvas.get_tk_widget().destroy()
            self._canvas = None

        if self.window and self.window.winfo_exists():
            self.window.destroy()

        if self._on_close is not None:
            try:
                self._on_close()
            except Exception:
                logger.exception("History window close callback failed")

    def _build_ui(self) -> None:
        """Build the overall history window layout."""
        container = tk.Frame(self.window, bg=COLORS["bg_primary"], padx=24, pady=24)
        container.pack(fill=tk.BOTH, expand=True)

        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(2, weight=1)

        self._build_header(container).grid(row=0, column=0, sticky="ew")
        self._build_stats_row(container).grid(
            row=1, column=0, sticky="ew", pady=(18, 18)
        )
        self._build_chart_panel(container).grid(row=2, column=0, sticky="nsew")
        self._build_footer(container).grid(row=3, column=0, sticky="ew", pady=(16, 0))

    def _build_header(self, parent: tk.Widget) -> tk.Frame:
        """Build the header panel with title and range badges."""
        header_shell = tk.Frame(parent, bg=COLORS["border"], padx=1, pady=1)

        header = tk.Frame(header_shell, bg=COLORS["bg_secondary"], padx=22, pady=20)
        header.pack(fill=tk.X)

        left = tk.Frame(header, bg=COLORS["bg_secondary"])
        left.pack(side=tk.LEFT, fill=tk.X, expand=True)

        title_font = tkfont.Font(family=FONT_FAMILY, size=22, weight="bold")
        subtitle_font = tkfont.Font(family=FONT_FAMILY, size=11)

        tk.Label(
            left,
            text="History Overview",
            font=title_font,
            fg=COLORS["gold"],
            bg=COLORS["bg_secondary"],
        ).pack(anchor="w")

        tk.Label(
            left,
            text="Daily gold futures closes converted into USD per gram for faster context.",
            font=subtitle_font,
            fg=COLORS["text_soft"],
            bg=COLORS["bg_secondary"],
        ).pack(anchor="w", pady=(6, 0))

        badge_frame = tk.Frame(header, bg=COLORS["bg_secondary"])
        badge_frame.pack(side=tk.RIGHT, anchor="n")

        self._build_badge(badge_frame, self.history_series.date_range_label).pack(
            anchor="e"
        )
        self._build_badge(
            badge_frame,
            f"{self.history_series.point_count} sessions",
        ).pack(anchor="e", pady=(8, 0))

        return header_shell

    def _build_stats_row(self, parent: tk.Widget) -> tk.Frame:
        """Build the summary cards shown above the chart."""
        row = tk.Frame(parent, bg=COLORS["bg_primary"])
        for index in range(4):
            row.grid_columnconfigure(index, weight=1)

        change_tone = self._change_tone()
        change_symbol = {"up": "▲", "down": "▼", "flat": "●"}[
            self.history_series.change_direction
        ]
        change_value = f"{change_symbol} {self.history_series.absolute_change:+.2f}"
        change_note = (
            f"{self.history_series.percent_change:+.2f}% vs the first visible close"
        )

        stats = [
            (
                "Current",
                f"${self.history_series.latest_price:,.2f}",
                "Latest close",
                COLORS["gold"],
            ),
            (
                "Range Low",
                f"${self.history_series.lowest_price:,.2f}",
                "Lowest close in view",
                COLORS["warning"],
            ),
            (
                "Range High",
                f"${self.history_series.highest_price:,.2f}",
                "Highest close in view",
                COLORS["success"],
            ),
            ("Change", change_value, change_note, change_tone),
        ]

        for index, (title, value, note, tone) in enumerate(stats):
            self._build_stat_card(row, title, value, note, tone).grid(
                row=0,
                column=index,
                sticky="nsew",
                padx=(0 if index == 0 else 6, 0 if index == len(stats) - 1 else 6),
            )

        return row

    def _build_chart_panel(self, parent: tk.Widget) -> tk.Frame:
        """Build the chart panel and embed the matplotlib canvas."""
        chart_shell = tk.Frame(parent, bg=COLORS["border"], padx=1, pady=1)

        chart_panel = tk.Frame(chart_shell, bg=COLORS["bg_secondary"], padx=20, pady=18)
        chart_panel.pack(fill=tk.BOTH, expand=True)
        chart_panel.grid_columnconfigure(0, weight=1)
        chart_panel.grid_rowconfigure(1, weight=1)

        header_row = tk.Frame(chart_panel, bg=COLORS["bg_secondary"])
        header_row.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header_row.grid_columnconfigure(0, weight=1)

        heading_font = tkfont.Font(family=FONT_FAMILY, size=14, weight="bold")
        meta_font = tkfont.Font(family=FONT_FAMILY, size=10)

        left = tk.Frame(header_row, bg=COLORS["bg_secondary"])
        left.grid(row=0, column=0, sticky="w")

        right = tk.Frame(header_row, bg=COLORS["bg_secondary"])
        right.grid(row=0, column=1, sticky="e")

        tk.Label(
            left,
            text="Trend View",
            font=heading_font,
            fg=COLORS["text_primary"],
            bg=COLORS["bg_secondary"],
        ).pack(anchor="w")

        tk.Label(
            left,
            text="Gold line shows the close, the dashed line shows the average, and the final point is highlighted.",
            font=meta_font,
            fg=COLORS["text_soft"],
            bg=COLORS["bg_secondary"],
        ).pack(anchor="w", pady=(4, 0))

        self._build_badge(right, f"Avg ${self.history_series.average_price:,.2f}").pack(
            anchor="e"
        )

        canvas_frame = tk.Frame(chart_panel, bg=COLORS["bg_secondary"])
        canvas_frame.grid(row=1, column=0, sticky="nsew")

        self._figure = Figure(
            figsize=(10.2, 6.2), dpi=100, facecolor=COLORS["bg_secondary"]
        )
        axis = self._figure.add_subplot(111)
        self._plot_chart(axis)
        self._figure.subplots_adjust(left=0.09, right=0.985, top=0.95, bottom=0.20)

        self._canvas = FigureCanvasTkAgg(self._figure, master=canvas_frame)
        self._canvas.draw()
        canvas_widget = self._canvas.get_tk_widget()
        canvas_widget.configure(bg=COLORS["bg_secondary"], highlightthickness=0)
        canvas_widget.pack(fill=tk.BOTH, expand=True)

        return chart_shell

    def _build_footer(self, parent: tk.Widget) -> tk.Frame:
        """Build the source metadata row and close action."""
        footer_shell = tk.Frame(parent, bg=COLORS["border"], padx=1, pady=1)

        footer = tk.Frame(footer_shell, bg=COLORS["bg_secondary"], padx=18, pady=14)
        footer.pack(fill=tk.X)

        meta_font = tkfont.Font(family=FONT_FAMILY, size=10)
        tk.Label(
            footer,
            text=(
                f"Source: {self.history_series.source_label}  |  Unit: {self.history_series.unit_label}  |  "
                f"Range: {self.history_series.date_range_label}"
            ),
            font=meta_font,
            fg=COLORS["text_soft"],
            bg=COLORS["bg_secondary"],
            justify="left",
            wraplength=760,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        return footer_shell

    def _build_badge(self, parent: tk.Widget, text: str) -> tk.Label:
        """Build one of the compact metadata badges used in the header and chart."""
        return tk.Label(
            parent,
            text=text,
            font=tkfont.Font(family=FONT_FAMILY, size=10, weight="bold"),
            fg=COLORS["text_primary"],
            bg=COLORS["bg_tertiary"],
            padx=12,
            pady=6,
        )

    def _build_stat_card(
        self,
        parent: tk.Widget,
        title: str,
        value: str,
        note: str,
        accent_color: str,
    ) -> tk.Frame:
        """Build a compact stat card for the history summary row."""
        shell = tk.Frame(parent, bg=COLORS["border"], padx=1, pady=1)

        card = tk.Frame(shell, bg=COLORS["bg_secondary"], padx=16, pady=16)
        card.pack(fill=tk.BOTH, expand=True)

        tk.Frame(card, bg=accent_color, height=4).pack(fill=tk.X, pady=(0, 12))
        tk.Label(
            card,
            text=title,
            font=tkfont.Font(family=FONT_FAMILY, size=10, weight="bold"),
            fg=COLORS["text_soft"],
            bg=COLORS["bg_secondary"],
        ).pack(anchor="w")
        tk.Label(
            card,
            text=value,
            font=tkfont.Font(family=FONT_FAMILY, size=18, weight="bold"),
            fg=accent_color,
            bg=COLORS["bg_secondary"],
        ).pack(anchor="w", pady=(8, 6))
        tk.Label(
            card,
            text=note,
            font=tkfont.Font(family=FONT_FAMILY, size=9),
            fg=COLORS["text_soft"],
            bg=COLORS["bg_secondary"],
            wraplength=170,
            justify="left",
        ).pack(anchor="w")

        return shell

    def _plot_chart(self, axis) -> None:
        """Render the historical price series and supporting annotations."""
        series = self.history_series
        change_tone = self._change_tone()
        price_span = max(series.highest_price - series.lowest_price, 1)
        chart_floor = series.lowest_price - (price_span * 0.18)
        chart_ceiling = series.highest_price + (price_span * 0.12)

        axis.set_facecolor(COLORS["bg_secondary"])
        axis.plot(
            series.dates,
            series.prices,
            color=COLORS["gold"],
            linewidth=2.8,
            solid_capstyle="round",
        )
        axis.fill_between(
            series.dates,
            series.prices,
            chart_floor,
            color=COLORS["gold"],
            alpha=0.10,
        )
        axis.axhline(
            series.average_price,
            color=COLORS["warning"],
            linewidth=1.2,
            linestyle=(0, (5, 4)),
            alpha=0.85,
        )
        axis.scatter(
            [series.end_date],
            [series.latest_price],
            s=74,
            color=change_tone,
            edgecolors=COLORS["bg_primary"],
            linewidths=1.3,
            zorder=4,
        )
        axis.annotate(
            f"${series.latest_price:,.2f}",
            xy=(series.end_date, series.latest_price),
            xytext=(-18, -20 if series.change_direction != "down" else 18),
            textcoords="offset points",
            ha="right",
            color=COLORS["text_primary"],
            fontsize=10,
            bbox={
                "boxstyle": "round,pad=0.35",
                "facecolor": COLORS["bg_tertiary"],
                "edgecolor": change_tone,
                "linewidth": 1.0,
            },
            arrowprops={"arrowstyle": "-", "color": change_tone, "linewidth": 1.2},
        )

        axis.set_xlim(series.start_date, series.end_date)
        axis.set_ylim(chart_floor, chart_ceiling)
        axis.margins(x=0.02)
        axis.set_xlabel(
            "Date range", color=COLORS["text_soft"], fontsize=11, labelpad=14
        )
        axis.set_ylabel(
            series.unit_label, color=COLORS["text_soft"], fontsize=11, labelpad=10
        )
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        axis.xaxis.set_major_locator(
            mdates.MonthLocator(interval=HISTORY_CHART_MONTH_INTERVAL)
        )
        axis.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"${value:,.0f}"))

        axis.tick_params(colors=COLORS["text_soft"], labelsize=10, pad=6)
        axis.grid(axis="y", color=COLORS["border"], alpha=0.35, linewidth=0.9)
        axis.grid(axis="x", color=COLORS["border"], alpha=0.14, linewidth=0.7)

        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
        axis.spines["left"].set_color(COLORS["border"])
        axis.spines["bottom"].set_color(COLORS["border"])

    def _change_tone(self) -> str:
        """Return the accent color that matches the overall trend direction."""
        if self.history_series.change_direction == "up":
            return COLORS["success"]
        if self.history_series.change_direction == "down":
            return COLORS["error"]
        return COLORS["warning"]
