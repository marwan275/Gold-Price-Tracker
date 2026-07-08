"""Profit calculator window for GoldTracker."""

from collections.abc import Callable
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import font as tkfont

from ..config import (
    COLORS,
    FONT_FAMILY,
    PROFIT_WINDOW_MIN_HEIGHT,
    PROFIT_WINDOW_MIN_WIDTH,
    PROFIT_WINDOW_SIZE,
    PROFIT_WINDOW_TITLE,
)
from ..services.excel_handler import export_excel, import_excel
from .components import create_styled_button, create_surface


class ProfitCalculatorWindow:
    """Top-level window that calculates portfolio profit from purchase rows."""

    DEFAULT_ROW_COUNT = 3
    ROW_SCROLLBAR_GAP = 10

    def __init__(
        self,
        parent: tk.Misc,
        current_price_per_gram: float,
        on_close: Callable[[], None] | None = None,
        embedded: bool = False,
    ) -> None:
        """Create the profit calculator window."""
        self.current_price_per_gram = current_price_per_gram
        self._on_close = on_close
        self._embedded = embedded
        self._closed = False
        self._rows: list[tuple[tk.StringVar, tk.StringVar]] = []
        self._row_price_per_gram_vars: list[tk.StringVar] = []
        self._row_profit_vars: list[tk.StringVar] = []
        self._row_price_per_gram_labels: list[tk.Label] = []
        self._row_profit_labels: list[tk.Label] = []
        self._row_frames: list[tk.Frame] = []

        self.total_grams_var = tk.StringVar(value="0.00 g")
        self.average_price_var = tk.StringVar(value="0.00 EGP/g")
        self.current_price_var = tk.StringVar(value=self._format_current_price())
        self.cost_basis_var = tk.StringVar(value="0.00 EGP")
        self.current_value_var = tk.StringVar(value="0.00 EGP")
        self.break_even_var = tk.StringVar(value="Break-even price: 0.00 EGP/g")
        self.profit_var = tk.StringVar(value="0.00 EGP")
        self.profit_percent_var = tk.StringVar(value="Profit/loss: 0.00%")

        if self._embedded:
            self.window = tk.Frame(parent, bg=COLORS["bg_primary"])
        else:
            self.window = tk.Toplevel(parent)
            self.window.title(PROFIT_WINDOW_TITLE)
            self.window.geometry(PROFIT_WINDOW_SIZE)
            self.window.minsize(PROFIT_WINDOW_MIN_WIDTH, PROFIT_WINDOW_MIN_HEIGHT)
            self.window.configure(bg=COLORS["bg_primary"])
            self.window.resizable(False, False)
            self.window.transient(parent)
            self.window.protocol("WM_DELETE_WINDOW", self.close)
            self.window.bind("<Escape>", lambda _event: self.close())

        self._build_fonts()
        self._build_ui()
        self._recalculate()
        self.lift()

    def is_open(self) -> bool:
        """Return True while the underlying window still exists."""
        return bool(self.window and self.window.winfo_exists())

    def lift(self) -> None:
        """Bring the calculator window to the front."""
        if self.is_open():
            if self._embedded:
                self.window.focus_set()
                return
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()

    def close(self) -> None:
        """Destroy the calculator window and notify the parent app."""
        if self._closed:
            return

        self._closed = True
        if self.window and self.window.winfo_exists():
            self.window.destroy()

        if self._on_close is not None:
            self._on_close()

    def update_market_price(self, current_price_per_gram: float) -> None:
        """Update the live price used by the calculator."""
        self.current_price_per_gram = current_price_per_gram
        self.current_price_var.set(self._format_current_price())
        self._recalculate()

    def _build_fonts(self) -> None:
        """Create the fonts used by the calculator window."""
        self.title_font = tkfont.Font(family=FONT_FAMILY, size=22, weight="bold")
        self.subtitle_font = tkfont.Font(family=FONT_FAMILY, size=11)
        self.header_font = tkfont.Font(family=FONT_FAMILY, size=11, weight="bold")
        self.small_font = tkfont.Font(family=FONT_FAMILY, size=10)
        self.badge_font = tkfont.Font(family=FONT_FAMILY, size=12, weight="bold")
        self.body_font = tkfont.Font(family=FONT_FAMILY, size=12)
        self.metric_font = tkfont.Font(family=FONT_FAMILY, size=15, weight="bold")
        self.profit_font = tkfont.Font(family=FONT_FAMILY, size=30, weight="bold")

    def _build_ui(self) -> None:
        """Build the calculator layout."""
        container = tk.Frame(self.window, bg=COLORS["bg_primary"], padx=24, pady=22)
        container.pack(fill=tk.BOTH, expand=True)
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(1, weight=1)

        header_shell, header = self._create_surface(container)
        header_shell.grid(row=0, column=0, sticky="ew")
        header.configure(padx=20, pady=16)
        header.grid_columnconfigure(0, weight=1)

        header_text = tk.Frame(header, bg=COLORS["bg_secondary"])
        header_text.grid(row=0, column=0, sticky="ew")
        tk.Label(
            header_text,
            text="Profit Calculator",
            font=self.title_font,
            fg=COLORS["gold"],
            bg=COLORS["bg_secondary"],
        ).pack(anchor="w")
        tk.Label(
            header_text,
            text="Enter each purchase as grams and the total price paid for that row.",
            font=self.subtitle_font,
            fg=COLORS["text_soft"],
            bg=COLORS["bg_secondary"],
        ).pack(anchor="w", pady=(6, 0))

        live_badge = tk.Frame(header, bg=COLORS["bg_tertiary"], padx=14, pady=10)
        live_badge.grid(row=0, column=1, sticky="e", padx=(18, 0))
        tk.Label(
            live_badge,
            text="LIVE PRICE",
            font=self.small_font,
            fg=COLORS["text_soft"],
            bg=COLORS["bg_tertiary"],
        ).pack(anchor="e")
        tk.Label(
            live_badge,
            textvariable=self.current_price_var,
            font=self.badge_font,
            fg=COLORS["success"],
            bg=COLORS["bg_tertiary"],
        ).pack(anchor="e", pady=(4, 0))

        table_shell, table = self._create_surface(container)
        table_shell.grid(row=1, column=0, sticky="nsew", pady=(18, 14))
        table.configure(padx=16, pady=14)
        table.grid_columnconfigure(0, weight=0)
        table.grid_columnconfigure(1, weight=1)
        table.grid_columnconfigure(2, weight=1)
        table.grid_columnconfigure(3, weight=0)
        table.grid_columnconfigure(4, weight=0)
        table.grid_columnconfigure(5, weight=0)
        table.grid_rowconfigure(3, weight=1)

        self._build_table_header(table)
        self._build_table_rows(table)

        summary = tk.Frame(container, bg=COLORS["bg_primary"])
        summary.grid(row=2, column=0, sticky="ew")
        for column in range(3):
            summary.grid_columnconfigure(column, weight=1)

        self._build_metric_card(
            summary,
            column=0,
            title="TOTAL GRAMS",
            value_var=self.total_grams_var,
            accent=COLORS["gold"],
        )
        self._build_metric_card(
            summary,
            column=1,
            title="AVERAGE BOUGHT PRICE",
            value_var=self.average_price_var,
            accent=COLORS["warning"],
        )
        self._build_metric_card(
            summary,
            column=2,
            title="COST BASIS",
            value_var=self.cost_basis_var,
            accent=COLORS["text_soft"],
        )

        profit_shell, profit_panel = self._create_surface(container)
        profit_shell.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        profit_panel.configure(padx=20, pady=16)

        tk.Label(
            profit_panel,
            text="PROFIT / LOSS",
            font=self.header_font,
            fg=COLORS["text_soft"],
            bg=COLORS["bg_secondary"],
        ).pack(anchor="w")
        tk.Label(
            profit_panel,
            textvariable=self.current_value_var,
            font=self.small_font,
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_secondary"],
        ).pack(anchor="w", pady=(4, 0))
        tk.Label(
            profit_panel,
            textvariable=self.break_even_var,
            font=self.small_font,
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_secondary"],
        ).pack(anchor="w", pady=(4, 0))
        self.profit_label = tk.Label(
            profit_panel,
            textvariable=self.profit_var,
            font=self.profit_font,
            fg=COLORS["text_soft"],
            bg=COLORS["bg_secondary"],
        )
        self.profit_label.pack(anchor="w", pady=(6, 0))
        self.profit_percent_label = tk.Label(
            profit_panel,
            textvariable=self.profit_percent_var,
            font=self.badge_font,
            fg=COLORS["text_soft"],
            bg=COLORS["bg_secondary"],
        )
        self.profit_percent_label.pack(anchor="w", pady=(2, 0))

    def _build_table_header(self, table: tk.Frame) -> None:
        """Build the table column labels."""
        tk.Label(
            table,
            text="PURCHASE LOTS",
            font=self.header_font,
            fg=COLORS["gold"],
            bg=COLORS["bg_secondary"],
            padx=8,
            pady=0,
        ).grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 10))

    def _build_table_rows(self, table: tk.Frame) -> None:
        """Build the scrollable editable purchase table."""
        self._validation_command = (
            self.window.register(self._validate_numeric_input),
            "%P",
        )

        actions = tk.Frame(table, bg=COLORS["bg_secondary"])
        actions.grid(row=1, column=0, columnspan=6, sticky="ew", pady=(0, 12))
        add_button = self._create_small_button(
            actions,
            text="+ Add purchase",
            command=self._add_purchase_row,
            variant="primary",
        )
        add_button.pack(side=tk.LEFT)

        file_actions = tk.Frame(actions, bg=COLORS["bg_secondary"])
        file_actions.pack(side=tk.RIGHT)
        export_button = self._create_file_action_button(
            file_actions,
            text="Export xlsx",
            icon="⇧",
            command=self._export_to_excel,
        )
        export_button.pack(side=tk.LEFT, padx=(0, 8))
        import_button = self._create_file_action_button(
            file_actions,
            text="Import xlsx",
            icon="⇩",
            command=self._import_from_excel,
        )
        import_button.pack(side=tk.LEFT)
        self._bind_table_mousewheel(actions)
        self._bind_table_mousewheel(add_button)
        self._bind_table_mousewheel(file_actions)
        self._bind_table_mousewheel(export_button)
        self._bind_table_mousewheel(import_button)

        canvas_shell = tk.Frame(table, bg=COLORS["bg_secondary"])
        canvas_shell.grid(row=3, column=0, columnspan=6, sticky="nsew")
        canvas_shell.grid_columnconfigure(0, weight=1)
        canvas_shell.grid_rowconfigure(0, weight=1)

        self.rows_canvas = tk.Canvas(
            canvas_shell,
            bg=COLORS["bg_secondary"],
            highlightthickness=0,
            height=220,
        )
        scrollbar = tk.Scrollbar(
            canvas_shell,
            orient=tk.VERTICAL,
            command=self.rows_canvas.yview,
        )
        self.rows_canvas.configure(yscrollcommand=scrollbar.set)

        self._build_fixed_table_header(table, scrollbar.winfo_reqwidth())

        self.rows_canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.rows_container = tk.Frame(self.rows_canvas, bg=COLORS["bg_secondary"])
        self._rows_window_id = self.rows_canvas.create_window(
            (0, 0),
            window=self.rows_container,
            anchor="nw",
        )
        self.rows_container.bind(
            "<Configure>",
            lambda _event: self.rows_canvas.configure(
                scrollregion=self.rows_canvas.bbox("all")
            ),
        )
        self.rows_canvas.bind(
            "<Configure>",
            lambda event: self.rows_canvas.itemconfigure(
                self._rows_window_id,
                width=max(event.width - self.ROW_SCROLLBAR_GAP, 0),
            ),
        )
        self._bind_table_mousewheel(self.rows_canvas)
        self._bind_table_mousewheel(self.rows_container)

        self.rows_container.grid_columnconfigure(0, weight=1)

        for _index in range(self.DEFAULT_ROW_COUNT):
            self._add_purchase_row(recalculate=False)

    def _add_purchase_row(self, recalculate: bool = True) -> None:
        """Append one editable purchase row."""
        grams_var = tk.StringVar()
        bought_price_var = tk.StringVar()
        row_price_per_gram_var = tk.StringVar(value="0.00 EGP/g")
        row_profit_var = tk.StringVar(value="0.00 EGP")
        grams_var.trace_add("write", lambda *_args: self._recalculate())
        bought_price_var.trace_add("write", lambda *_args: self._recalculate())

        row_frame = tk.Frame(self.rows_container, bg=COLORS["bg_secondary"])
        self._configure_purchase_grid(row_frame)
        row_frame.grid(sticky="ew", pady=4)

        self._rows.append((grams_var, bought_price_var))
        self._row_price_per_gram_vars.append(row_price_per_gram_var)
        self._row_profit_vars.append(row_profit_var)
        self._row_frames.append(row_frame)
        self._build_purchase_row(
            row_frame,
            grams_var,
            bought_price_var,
            row_price_per_gram_var,
            row_profit_var,
        )
        self._bind_table_mousewheel_tree(row_frame)
        self._renumber_rows()
        if recalculate:
            self._recalculate()

    def _build_purchase_row(
        self,
        row_frame: tk.Frame,
        grams_var: tk.StringVar,
        bought_price_var: tk.StringVar,
        row_price_per_gram_var: tk.StringVar,
        row_profit_var: tk.StringVar,
    ) -> None:
        """Build widgets for one purchase row."""
        tk.Label(
            row_frame,
            text="",
            font=self.body_font,
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_secondary"],
            padx=8,
            pady=6,
            width=3,
        ).grid(row=0, column=0, sticky="ew")

        self._create_table_entry(row_frame, grams_var, self._validation_command).grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(8, 6),
        )
        self._create_table_entry(
            row_frame,
            bought_price_var,
            self._validation_command,
        ).grid(row=0, column=2, sticky="ew", padx=(6, 8))
        price_per_gram_label = tk.Label(
            row_frame,
            textvariable=row_price_per_gram_var,
            font=self.small_font,
            fg=COLORS["text_soft"],
            bg=COLORS["bg_secondary"],
            padx=8,
            pady=6,
            anchor="center",
        )
        price_per_gram_label.grid(row=0, column=3, sticky="ew")
        self._row_price_per_gram_labels.append(price_per_gram_label)
        profit_label = tk.Label(
            row_frame,
            textvariable=row_profit_var,
            font=self.small_font,
            fg=COLORS["text_soft"],
            bg=COLORS["bg_secondary"],
            padx=8,
            pady=6,
            anchor="center",
        )
        profit_label.grid(row=0, column=4, sticky="ew")
        self._row_profit_labels.append(profit_label)
        self._create_small_button(
            row_frame,
            text="Remove",
            command=lambda frame=row_frame: self._remove_purchase_row(frame),
            variant="danger",
        ).grid(row=0, column=5, sticky="e")

    def _configure_purchase_grid(self, frame: tk.Frame) -> None:
        """Apply matching widths to purchase table columns."""
        frame.grid_columnconfigure(0, minsize=48, weight=0)
        frame.grid_columnconfigure(1, minsize=210, weight=1)
        frame.grid_columnconfigure(2, minsize=210, weight=1)
        frame.grid_columnconfigure(3, minsize=150, weight=0)
        frame.grid_columnconfigure(4, minsize=150, weight=0)
        frame.grid_columnconfigure(5, minsize=112, weight=0)

    def _build_fixed_table_header(
        self,
        table: tk.Frame,
        scrollbar_width: int,
    ) -> None:
        """Build column labels above the scrollable purchase rows."""
        header_shell = tk.Frame(table, bg=COLORS["bg_secondary"])
        header_shell.grid(row=2, column=0, columnspan=6, sticky="ew", pady=(0, 8))
        header_shell.grid_columnconfigure(0, weight=1)
        header_shell.grid_columnconfigure(
            1,
            minsize=scrollbar_width + self.ROW_SCROLLBAR_GAP,
            weight=0,
        )

        header_frame = tk.Frame(header_shell, bg=COLORS["bg_secondary"])
        self._configure_purchase_grid(header_frame)
        header_frame.grid(row=0, column=0, sticky="ew")
        tk.Frame(
            header_shell,
            bg=COLORS["bg_secondary"],
            width=scrollbar_width + self.ROW_SCROLLBAR_GAP,
        ).grid(row=0, column=1, sticky="ns")

        labels = ("#", "Grams", "Bought total", "Price/g", "Row P/L", "")
        for column, label in enumerate(labels):
            tk.Label(
                header_frame,
                text=label,
                font=self.header_font,
                fg=COLORS["text_soft"],
                bg=COLORS["bg_tertiary"],
                padx=8,
                pady=8,
                anchor="center",
            ).grid(row=0, column=column, sticky="ew")
        self._bind_table_mousewheel_tree(header_frame)

    def _remove_purchase_row(self, row_frame: tk.Frame) -> None:
        """Remove one purchase row from the calculator."""
        if row_frame not in self._row_frames:
            return

        index = self._row_frames.index(row_frame)
        self._row_frames.pop(index)
        self._rows.pop(index)
        self._row_price_per_gram_vars.pop(index)
        self._row_profit_vars.pop(index)
        self._row_price_per_gram_labels.pop(index)
        self._row_profit_labels.pop(index)
        row_frame.destroy()
        self._renumber_rows()
        self._recalculate()

    def _clear_purchase_rows(self) -> None:
        """Remove all purchase rows from the calculator."""
        for row_frame in self._row_frames:
            row_frame.destroy()
        self._row_frames.clear()
        self._rows.clear()
        self._row_price_per_gram_vars.clear()
        self._row_profit_vars.clear()
        self._row_price_per_gram_labels.clear()
        self._row_profit_labels.clear()

    def _set_purchase_rows(self, rows: list[tuple[str, str]]) -> None:
        """Replace purchase rows with imported values."""
        self._clear_purchase_rows()
        for grams, bought_total in rows:
            self._add_purchase_row(recalculate=False)
            grams_var, bought_price_var = self._rows[-1]
            grams_var.set(grams)
            bought_price_var.set(bought_total)

        if not self._rows:
            self._add_purchase_row(recalculate=False)
        self._renumber_rows()
        self._recalculate()

    def _export_to_excel(self) -> None:
        """Export purchase rows and summary totals to an Excel workbook."""
        file_name = filedialog.asksaveasfilename(
            parent=self.window,
            title="Export profit calculator",
            defaultextension=".xlsx",
            filetypes=(("Excel workbook", "*.xlsx"),),
        )
        if not file_name:
            return

        try:
            export_excel(file_name, self._build_excel_export_data())
        except Exception as exc:
            messagebox.showerror(
                "Export failed",
                f"Could not export profit calculator data.\n\n{exc}",
                parent=self.window,
            )
            return

        messagebox.showinfo(
            "Export complete",
            "Profit calculator data was exported successfully.",
            parent=self.window,
        )

    def _import_from_excel(self) -> None:
        """Import purchase rows from an Excel workbook."""
        file_name = filedialog.askopenfilename(
            parent=self.window,
            title="Import profit calculator",
            filetypes=(("Excel workbook", "*.xlsx"),),
        )
        if not file_name:
            return

        try:
            table = import_excel(file_name)
            rows = self._extract_import_rows(table)
        except Exception as exc:
            messagebox.showerror(
                "Import failed",
                f"Could not import profit calculator data.\n\n{exc}",
                parent=self.window,
            )
            return

        self._set_purchase_rows(rows)
        messagebox.showinfo(
            "Import complete",
            f"Imported {len(rows)} purchase row(s).",
            parent=self.window,
        )

    def _build_excel_export_data(self) -> dict[str, tuple]:
        """Return calculator data in the column-oriented Excel format."""
        purchase_rows = [
            (grams_var.get().strip(), bought_price_var.get().strip())
            for grams_var, bought_price_var in self._rows
            if grams_var.get().strip() or bought_price_var.get().strip()
        ]
        total_grams, average_price, total_cost, profit = self._calculate_totals()
        profit_percentage = self._calculate_profit_percentage(profit, total_cost)
        row_price_per_gram_values = self._calculate_row_price_per_gram_values(
            purchase_rows
        )
        row_profits = self._calculate_row_profits(purchase_rows)
        row_count = max(len(purchase_rows), 1)

        grams = tuple(row[0] for row in purchase_rows) + ("",) * (
            row_count - len(purchase_rows)
        )
        bought_totals = tuple(row[1] for row in purchase_rows) + ("",) * (
            row_count - len(purchase_rows)
        )
        row_prices_per_gram = tuple(row_price_per_gram_values) + ("",) * (
            row_count - len(row_price_per_gram_values)
        )
        row_profit_values = tuple(row_profits) + ("",) * (row_count - len(row_profits))
        summary_blanks = ("",) * (row_count - 1)

        return {
            "grams": grams,
            "bought total": bought_totals,
            "price per gram": row_prices_per_gram,
            "row profit/loss": row_profit_values,
            "total grams": (total_grams, *summary_blanks),
            "average bought price": (average_price, *summary_blanks),
            "cost basis": (total_cost, *summary_blanks),
            "profit/loss": (profit, *summary_blanks),
            "profit/loss %": (profit_percentage, *summary_blanks),
        }

    def _extract_import_rows(self, table: dict[str, tuple]) -> list[tuple[str, str]]:
        """Extract purchase rows from imported Excel data."""
        normalized_headers = {header.strip().lower(): header for header in table}
        if (
            "grams" not in normalized_headers
            or "bought total" not in normalized_headers
        ):
            raise ValueError(
                "Excel file must contain 'grams' and 'bought total' headers"
            )

        grams_values = table[normalized_headers["grams"]]
        bought_total_values = table[normalized_headers["bought total"]]
        row_count = max(len(grams_values), len(bought_total_values))
        rows: list[tuple[str, str]] = []

        for index in range(row_count):
            grams = self._format_import_value(
                grams_values[index] if index < len(grams_values) else None
            )
            bought_total = self._format_import_value(
                bought_total_values[index] if index < len(bought_total_values) else None
            )
            if grams or bought_total:
                rows.append((grams, bought_total))

        return rows

    def _format_import_value(self, value) -> str:
        """Format one imported Excel cell for display in an entry field."""
        if value is None:
            return ""
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value).strip()

    def _renumber_rows(self) -> None:
        """Refresh row numbers after add/remove actions."""
        for index, row_frame in enumerate(self._row_frames, start=1):
            row_frame.grid(row=index - 1, column=0, sticky="ew", pady=4)
            number_label = row_frame.grid_slaves(row=0, column=0)[0]
            number_label.config(text=str(index))

    def _create_table_entry(
        self,
        parent: tk.Widget,
        textvariable: tk.StringVar,
        validation_command: tuple,
    ) -> tk.Entry:
        """Create a numeric table entry."""
        return tk.Entry(
            parent,
            textvariable=textvariable,
            font=self.body_font,
            fg=COLORS["text_primary"],
            bg=COLORS["bg_tertiary"],
            insertbackground=COLORS["gold"],
            relief="flat",
            bd=0,
            justify="center",
            validate="key",
            validatecommand=validation_command,
        )

    def _create_small_button(
        self,
        parent: tk.Widget,
        text: str,
        command: Callable[[], None],
        variant: str = "secondary",
    ) -> tk.Button:
        """Create a compact calculator button."""
        return create_styled_button(
            parent,
            text=text,
            command=command,
            font=self.header_font,
            variant=variant,
            padx=12,
            pady=7,
        )

    def _create_file_action_button(
        self,
        parent: tk.Widget,
        text: str,
        icon: str,
        command: Callable[[], None],
    ) -> tk.Button:
        """Create a compact import/export action button."""
        return create_styled_button(
            parent,
            text=text,
            command=command,
            font=self.header_font,
            variant="action_secondary",
            icon=icon,
            padx=14,
            pady=7,
            width=11,
        )

    def _bind_table_mousewheel(self, widget: tk.Widget) -> None:
        """Bind purchase-table wheel scrolling to one widget only."""
        widget.bind("<MouseWheel>", self._on_mousewheel, add="+")

    def _bind_table_mousewheel_tree(self, widget: tk.Widget) -> None:
        """Bind purchase-table wheel scrolling to a widget and its children."""
        self._bind_table_mousewheel(widget)
        for child in widget.winfo_children():
            self._bind_table_mousewheel_tree(child)

    def _on_mousewheel(self, event) -> None:
        """Scroll the purchase table with the mouse wheel."""
        self.rows_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _build_metric_card(
        self,
        parent: tk.Widget,
        column: int,
        title: str,
        value_var: tk.StringVar,
        accent: str,
    ) -> None:
        """Build a summary metric card."""
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
            font=self.header_font,
            fg=COLORS["text_soft"],
            bg=COLORS["bg_secondary"],
        ).pack(anchor="w")
        tk.Label(
            panel,
            textvariable=value_var,
            font=self.metric_font,
            fg=COLORS["text_primary"],
            bg=COLORS["bg_secondary"],
        ).pack(anchor="w", pady=(8, 0))

    def _create_surface(
        self,
        parent: tk.Widget,
        inner_bg: str | None = None,
    ) -> tuple[tk.Frame, tk.Frame]:
        """Create a framed surface and its inner panel."""
        return create_surface(parent, inner_bg=inner_bg)

    def _recalculate(self) -> None:
        """Recalculate totals and profit from the current rows."""
        total_grams, average_price, total_cost, profit = self._calculate_totals()
        current_value = self.current_price_per_gram * total_grams
        break_even_price = self._calculate_break_even_price(total_grams, total_cost)
        profit_percentage = self._calculate_profit_percentage(profit, total_cost)

        self.total_grams_var.set(f"{total_grams:,.2f} g")
        self.average_price_var.set(f"{average_price:,.2f} EGP/g")
        self.cost_basis_var.set(f"{total_cost:,.2f} EGP")
        self.current_value_var.set(f"Current market value: {current_value:,.2f} EGP")
        self.break_even_var.set(f"Break-even price: {break_even_price:,.2f} EGP/g")
        self.profit_var.set(f"{profit:,.2f} EGP")
        self.profit_percent_var.set(f"Profit/loss: {profit_percentage:+,.2f}%")

        if total_grams <= 0 or self.current_price_per_gram <= 0 or profit == 0:
            color = COLORS["text_soft"]
        elif profit > 0:
            color = COLORS["success"]
        else:
            color = COLORS["error"]

        if hasattr(self, "profit_label"):
            self.profit_label.config(fg=color)
        if hasattr(self, "profit_percent_label"):
            self.profit_percent_label.config(fg=color)
        self._refresh_row_calculated_values()

    def _calculate_totals(self) -> tuple[float, float, float, float]:
        """Calculate numeric totals from the current purchase rows."""
        total_grams = 0.0
        total_cost = 0.0

        for grams_var, bought_price_var in self._rows:
            grams = self._parse_float(grams_var.get())
            bought_total = self._parse_float(bought_price_var.get())
            total_grams += grams
            total_cost += bought_total

        average_price = total_cost / total_grams if total_grams > 0 else 0.0
        profit = (
            self.current_price_per_gram * total_grams - total_cost
            if self.current_price_per_gram > 0
            else 0.0
        )
        return total_grams, average_price, total_cost, profit

    def _calculate_break_even_price(
        self,
        total_grams: float,
        total_cost: float,
    ) -> float:
        """Return the per-gram price needed to avoid a loss."""
        if total_grams <= 0:
            return 0.0
        return total_cost / total_grams

    def _calculate_profit_percentage(self, profit: float, total_cost: float) -> float:
        """Return profit or loss as a percentage of cost basis."""
        if total_cost <= 0:
            return 0.0
        return (profit / total_cost) * 100

    def _calculate_row_price_per_gram(
        self,
        grams_value: str,
        bought_total_value: str,
    ) -> float:
        """Return the bought price per gram for one purchase row."""
        grams = self._parse_float(grams_value)
        bought_total = self._parse_float(bought_total_value)
        if grams <= 0:
            return 0.0
        return bought_total / grams

    def _calculate_row_profit(self, grams_value: str, bought_total_value: str) -> float:
        """Return profit or loss for one purchase row."""
        grams = self._parse_float(grams_value)
        bought_total = self._parse_float(bought_total_value)
        if self.current_price_per_gram <= 0:
            return 0.0
        return (self.current_price_per_gram * grams) - bought_total

    def _calculate_row_profits(
        self,
        rows: list[tuple[str, str]],
    ) -> list[float]:
        """Return row-level profit or loss values for exported purchase rows."""
        return [
            self._calculate_row_profit(grams, bought_total)
            for grams, bought_total in rows
        ]

    def _calculate_row_price_per_gram_values(
        self,
        rows: list[tuple[str, str]],
    ) -> list[float]:
        """Return row-level bought price per gram values for exported rows."""
        return [
            self._calculate_row_price_per_gram(grams, bought_total)
            for grams, bought_total in rows
        ]

    def _refresh_row_calculated_values(self) -> None:
        """Refresh per-row calculated display labels."""
        for (
            (grams_var, bought_price_var),
            row_price_per_gram_var,
            row_profit_var,
            row_price_per_gram_label,
            row_profit_label,
        ) in zip(
            self._rows,
            self._row_price_per_gram_vars,
            self._row_profit_vars,
            self._row_price_per_gram_labels,
            self._row_profit_labels,
            strict=False,
        ):
            price_per_gram = self._calculate_row_price_per_gram(
                grams_var.get(),
                bought_price_var.get(),
            )
            profit = self._calculate_row_profit(
                grams_var.get(),
                bought_price_var.get(),
            )
            row_price_per_gram_var.set(f"{price_per_gram:,.2f} EGP/g")
            row_profit_var.set(f"{profit:+,.2f} EGP")
            row_price_per_gram_label.config(fg=COLORS["text_soft"])

            if self.current_price_per_gram <= 0 or profit == 0:
                color = COLORS["text_soft"]
            elif profit > 0:
                color = COLORS["success"]
            else:
                color = COLORS["error"]
            row_profit_label.config(fg=color)

    def _format_current_price(self) -> str:
        """Format the current market price used for profit calculations."""
        if self.current_price_per_gram <= 0:
            return "Unavailable"
        return f"{self.current_price_per_gram:,.2f} EGP/g"

    def _validate_numeric_input(self, new_value: str) -> bool:
        """Validate numeric input for table cells."""
        if new_value == "":
            return True
        if new_value.count(".") > 1:
            return False
        return all(char in "0123456789." for char in new_value)

    def _parse_float(self, value: str) -> float:
        """Parse a table cell as a positive float."""
        try:
            parsed = float(value)
        except ValueError:
            return 0.0
        return max(parsed, 0.0)
