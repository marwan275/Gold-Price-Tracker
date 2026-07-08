import logging
import sys
import tkinter as tk
import threading
from datetime import datetime
from pathlib import Path

from .config import (
    WINDOW_TITLE,
    WINDOW_SIZE,
    APP_ICON_PATH,
    COLORS,
    REFRESH_INTERVAL_MS,
    HISTORY_DAYS,
)
from .core.app_workers import BackgroundWorkerSlot
from .logging_config import configure_logging
from .models import HistoricalPriceSeries
from .services.price_fetcher import (
    GoldPriceFetcher,
    PriceFetchError,
    KEY_WORLDWIDE,
    KEY_EGYPT,
    fetch_historical_prices,
)
from .ui.dashboard_view import MainDashboardView
from .ui.app_shell import AppShell
from .ui.history_window import (
    HistoryWindow,
    HistoryWindowError,
    history_window_available,
    history_window_unavailable_message,
)
from .ui.profit_calculator_window import ProfitCalculatorWindow


logger = logging.getLogger(__name__)


def _resource_path(relative_path: str) -> Path:
    """Resolve a bundled resource path for source and PyInstaller runs."""
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return base_path / relative_path


class GoldTracker:
    """Main application controller for the GoldTracker desktop app."""

    def __init__(self, root):
        """Initialize the application window, state, and background services."""
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.geometry(WINDOW_SIZE)
        fixed_width, fixed_height = self._parse_window_size(WINDOW_SIZE)
        self.root.minsize(fixed_width, fixed_height)
        self.root.configure(bg=COLORS["bg_primary"])
        self.root.resizable(True, True)
        self._maximize_root()
        self._set_window_icon()

        self.price_fetcher = GoldPriceFetcher()
        self._state_lock = threading.RLock()

        self.grams = tk.StringVar(value="1")
        self.prices: dict[str, float] = {}
        self.price_per_gram = 0
        self.previous_price = 0
        self.total_value = tk.StringVar(value="Loading...")
        self.last_update = tk.StringVar(value="Pending")
        self.trend_text = tk.StringVar(value="● Awaiting first sync")
        self.egypt_price_text = tk.StringVar(value="Waiting...")
        self.world_price_text = tk.StringVar(value="Waiting...")
        self.price_note_text = tk.StringVar(
            value="Per-gram value appears after the first successful source sync."
        )
        self.dashboard_view: MainDashboardView | None = None
        self.app_shell: AppShell | None = None
        self.dashboard_frame: tk.Frame | None = None
        self.auto_refresh_id = None
        self.is_fetching = False
        self._is_closing = False
        self._fetch_worker = BackgroundWorkerSlot("price refresh")
        self._history_worker = BackgroundWorkerSlot("history loader")
        self.history_window: HistoryWindow | None = None
        self.profit_calculator_window: ProfitCalculatorWindow | None = None

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        logger.info("Initializing GoldTracker UI")
        self.setup_ui()
        self.fetch_price()

    def _set_window_icon(self) -> None:
        """Apply the app icon when the resource is available."""
        icon_path = _resource_path(APP_ICON_PATH)
        if not icon_path.exists():
            logger.debug("App icon was not found at %s", icon_path)
            return

        try:
            self.root.iconbitmap(default=str(icon_path))
        except tk.TclError as exc:
            logger.debug("Could not set app icon: %s", exc)

    def _maximize_root(self) -> None:
        """Open the main application window maximized when the platform supports it."""
        try:
            self.root.state("zoomed")
        except tk.TclError:
            try:
                self.root.attributes("-zoomed", True)
            except tk.TclError as exc:
                logger.debug("Could not maximize app window: %s", exc)

    def _queue_ui_update(self, callback) -> None:
        """Schedule a Tkinter update only while the window is still alive."""
        with self._state_lock:
            if self._is_closing:
                return

        try:
            if self.root.winfo_exists():
                # Tk widgets must only be updated from the main event loop thread.
                self.root.after(0, callback)
        except (tk.TclError, RuntimeError):
            logger.debug("Skipping UI update because the window is closing")

    def _snapshot_price_state(self) -> tuple[dict[str, float], float, float]:
        """Return a consistent snapshot of the live pricing state."""
        with self._state_lock:
            return dict(self.prices), self.price_per_gram, self.previous_price

    def _apply_fetch_success(self, status_text: str, status_color: str) -> None:
        """Render refreshed prices and the caller-provided status message."""
        self._refresh_market_snapshot()
        self.value_display.config(fg=COLORS["success"])
        self.update_display()
        self.update_trend()
        self.update_timestamp()
        self.status_label.config(text=status_text, fg=status_color)

    def _apply_fetch_error(self, status_text: str, reset_value: bool) -> None:
        """Render a failed refresh state without discarding usable old prices."""
        _, price_per_gram, _ = self._snapshot_price_state()

        if price_per_gram <= 0:
            self.egypt_price_text.set("Unavailable")
            self.world_price_text.set("Unavailable")
            self.price_note_text.set(
                "Per-gram value is unavailable until at least one live source responds."
            )
        self.status_label.config(text=status_text, fg=COLORS["error"])
        if reset_value:
            self.total_value.set("Error")
            self.value_display.config(fg=COLORS["error"])

    def _refresh_market_snapshot(self) -> None:
        """Refresh market summary cards and the value note."""
        prices, price_per_gram, _ = self._snapshot_price_state()

        self.egypt_price_text.set(self._format_market_price(prices.get(KEY_EGYPT)))
        self.world_price_text.set(self._format_market_price(prices.get(KEY_WORLDWIDE)))

        if KEY_EGYPT in prices:
            source_label = "Egypt market"
        elif KEY_WORLDWIDE in prices:
            source_label = "Global converted rate"
        else:
            source_label = None

        if source_label and price_per_gram > 0:
            self.price_note_text.set(
                f"Primary feed: {source_label} • {price_per_gram:,.2f} EGP per gram"
            )
        else:
            self.price_note_text.set(
                "Per-gram value appears after the first successful source sync."
            )

        if (
            self.profit_calculator_window is not None
            and self.profit_calculator_window.is_open()
        ):
            self.profit_calculator_window.update_market_price(price_per_gram)

    def _format_market_price(self, price: float | None) -> str:
        """Format a market price for the summary cards."""
        if price is None:
            return "Unavailable"
        return f"{price:,.2f} EGP/g"

    def on_close(self) -> None:
        """Stop background work and close the application cleanly."""
        logger.info("Shutting down GoldTracker")
        with self._state_lock:
            self._is_closing = True

        if self.auto_refresh_id is not None:
            try:
                self.root.after_cancel(self.auto_refresh_id)
            except tk.TclError:
                logger.debug(
                    "Auto-refresh callback was already cleared during shutdown"
                )
            self.auto_refresh_id = None

        self._fetch_worker.request_shutdown()
        self._history_worker.request_shutdown()
        fetch_thread_alive = self._fetch_worker.join()
        self._history_worker.join()

        if fetch_thread_alive:
            logger.warning(
                "Skipping fetcher close because price refresh is still running"
            )
        else:
            try:
                self.price_fetcher.close()
            except Exception:
                logger.exception("Failed to close price fetcher cleanly")

        try:
            if self.history_window is not None and self.history_window.is_open():
                self.history_window.close()
        except Exception:
            logger.exception("Failed to close history window cleanly")
        self.history_window = None

        try:
            if (
                self.profit_calculator_window is not None
                and self.profit_calculator_window.is_open()
            ):
                self.profit_calculator_window.close()
        except Exception:
            logger.exception("Failed to close profit calculator cleanly")
        self.profit_calculator_window = None

        try:
            self.root.destroy()
        except tk.TclError:
            logger.debug("Root window was already destroyed")

    def setup_ui(self):
        """Build the main dashboard view and capture key widget references."""
        self.app_shell = AppShell(
            root=self.root,
            on_show_dashboard=self.show_dashboard,
            on_show_profit=self.show_profit_calculator,
            on_show_history=self.show_history,
        )
        self.dashboard_frame = tk.Frame(
            self.app_shell.content_frame,
            bg=COLORS["bg_primary"],
        )
        self.app_shell.add_view("dashboard", self.dashboard_frame)

        self.dashboard_view = MainDashboardView(
            root=self.dashboard_frame,
            grams_var=self.grams,
            total_value_var=self.total_value,
            trend_text_var=self.trend_text,
            egypt_price_var=self.egypt_price_text,
            world_price_var=self.world_price_text,
            last_update_var=self.last_update,
            price_note_var=self.price_note_text,
            on_decrease_grams=self.decrease_grams,
            on_increase_grams=self.increase_grams,
            on_grams_change=self.on_grams_change,
            validate_numeric_input=self.validate_numeric_input,
            on_refresh=self.fetch_price,
            on_copy_value=self.copy_value,
            on_show_history=self.show_history,
            on_profit_calculator=self.show_profit_calculator,
        )
        self.grams_entry = self.dashboard_view.grams_entry
        self.value_display = self.dashboard_view.value_display
        self.trend_label = self.dashboard_view.trend_label
        self.status_label = self.dashboard_view.status_label
        self.refresh_btn = self.dashboard_view.refresh_btn
        self.history_btn = self.dashboard_view.history_btn
        self.dashboard_view.focus_grams_entry()
        self._sync_history_button_availability()
        self.show_dashboard()
        self.schedule_auto_refresh()

    def show_dashboard(self) -> None:
        """Show the main dashboard inside the app shell."""
        if self.app_shell is not None:
            self.app_shell.show_view("dashboard")
        if self.dashboard_view is not None:
            self.dashboard_view.focus_grams_entry()

    def _parse_window_size(self, window_size: str) -> tuple[int, int]:
        """Parse a Tk geometry size string like 1000x820 into integers."""
        width_text, height_text = window_size.lower().split("x", maxsplit=1)
        return int(width_text), int(height_text)

    def _select_primary_price(
        self, fetched_prices: dict[str, float]
    ) -> tuple[float, str]:
        """Choose the primary price source used by dashboard calculations."""
        if KEY_EGYPT in fetched_prices:
            return fetched_prices[KEY_EGYPT], "Egypt market"
        if KEY_WORLDWIDE in fetched_prices:
            return fetched_prices[KEY_WORLDWIDE], "Global converted rate"
        raise PriceFetchError("No prices available")

    def _build_refresh_status(self, primary_feed: str) -> tuple[str, str]:
        """Return the dashboard status text and color for the latest fetch."""
        status_text = f"Live sync healthy • Primary feed: {primary_feed}"
        status_color = COLORS["success"]
        if self.price_fetcher.last_fetch_used_stale_cache:
            status_text = f"Cached fallback active • Primary feed: {primary_feed}"
            status_color = COLORS["warning"]
        elif self.price_fetcher.last_fetch_warnings:
            status_text = f"One source degraded • Primary feed: {primary_feed}"
            status_color = COLORS["warning"]
        return status_text, status_color

    def fetch_price(self, silent=False):
        """Fetch the latest price data and update the dashboard state."""
        with self._state_lock:
            if self._is_closing or self.is_fetching:
                return
            self.is_fetching = True

        if self.dashboard_view is not None:
            self.dashboard_view.disable_button(self.refresh_btn)

        if silent:
            self.status_label.config(text="Auto-refreshing...", fg=COLORS["text_muted"])
        else:
            self.status_label.config(
                text="Fetching live price...", fg=COLORS["text_muted"]
            )
            self.total_value.set("Loading...")

        def fetch():
            try:
                fetched_prices = self.price_fetcher.fetch()
                new_price, primary_feed = self._select_primary_price(fetched_prices)

                with self._state_lock:
                    self.prices = dict(fetched_prices)
                    self.previous_price = self.price_per_gram
                    self.price_per_gram = new_price

                status_text, status_color = self._build_refresh_status(primary_feed)

                logger.info(
                    "Price refresh completed (stale_cache=%s, warnings=%s)",
                    self.price_fetcher.last_fetch_used_stale_cache,
                    ", ".join(self.price_fetcher.last_fetch_warnings) or "none",
                )
                self._queue_ui_update(
                    lambda: self._apply_fetch_success(status_text, status_color)
                )

            except PriceFetchError as exc:
                logger.warning("Price refresh failed: %s", exc)
                self._queue_ui_update(
                    lambda: self._apply_fetch_error(
                        "Could not fetch price. Check connection.",
                        reset_value=not silent,
                    )
                )

            except Exception as exc:
                logger.exception("Unexpected error during price refresh")
                error_msg = str(exc)[:40]
                self._queue_ui_update(
                    lambda msg=error_msg: self._apply_fetch_error(
                        f"Error: {msg}...",
                        reset_value=not silent,
                    )
                )

            finally:
                with self._state_lock:
                    self.is_fetching = False
                self._queue_ui_update(self._enable_refresh_button)

        # Run network work off the Tk event loop so the window stays responsive.
        if not self._fetch_worker.start(fetch):
            with self._state_lock:
                self.is_fetching = False
                is_closing = self._is_closing

            if not is_closing:
                self._enable_refresh_button()
                status_text = "Auto-refresh skipped; refresh already running"
                if not silent:
                    status_text = "Refresh already running"
                self.status_label.config(text=status_text, fg=COLORS["warning"])

    def update_display(self):
        """Update the calculated portfolio value shown on the dashboard."""
        try:
            grams = float(self.grams.get())
            if grams < 0:
                grams = 0
                self.grams.set("0")
            with self._state_lock:
                price_per_gram = self.price_per_gram
            total = price_per_gram * grams
            self.total_value.set(f"{total:,.2f}")
        except ValueError:
            self.total_value.set("0.00")

    def increase_grams(self):
        """Increase the tracked gold weight by one gram."""
        try:
            current = float(self.grams.get())
            self.grams.set(f"{current + 1:g}")
        except ValueError:
            self.grams.set("1")
        self.update_display()

    def decrease_grams(self):
        """Decrease the tracked gold weight without going below zero."""
        try:
            current = float(self.grams.get())
            self.grams.set(f"{max(current - 1, 0):g}")
        except ValueError:
            self.grams.set("0")
        self.update_display()

    def on_grams_change(self, _event=None):
        """Recalculate the displayed value after text entry changes."""
        self.update_display()

    def validate_numeric_input(self, new_value):
        """Allow empty, integer, or decimal grams input while typing."""
        if new_value == "":
            return True
        if new_value.count(".") > 1:
            return False
        for char in new_value:
            if char not in "0123456789.":
                return False
        return True

    def copy_value(self):
        """Copy the current calculated value to the clipboard."""
        value = self.total_value.get()
        if value and value not in ("Loading...", "Error", "0.00"):
            self.root.clipboard_clear()
            self.root.clipboard_append(value + " EGP")
            original_text = self.status_label.cget("text")
            original_color = self.status_label.cget("fg")
            copied_text = "✓ Copied to clipboard!"
            self.status_label.config(text=copied_text, fg=COLORS["success"])
            self.root.after(
                1500,
                lambda: self._restore_status_message(
                    copied_text,
                    original_text,
                    original_color,
                ),
            )

    def update_trend(self):
        """Update the price trend indicator from the latest price snapshot."""
        _, price_per_gram, previous_price = self._snapshot_price_state()

        if previous_price > 0 and price_per_gram > 0:
            diff = price_per_gram - previous_price
            if diff > 0:
                self.trend_text.set(f"▲ Up {diff:,.2f} EGP")
                self.trend_label.config(fg=COLORS["success"], bg=COLORS["bg_tertiary"])
            elif diff < 0:
                self.trend_text.set(f"▼ Down {abs(diff):,.2f} EGP")
                self.trend_label.config(fg=COLORS["error"], bg=COLORS["bg_tertiary"])
            else:
                self.trend_text.set("● No price change")
                self.trend_label.config(
                    fg=COLORS["text_soft"], bg=COLORS["bg_tertiary"]
                )
        else:
            self.trend_text.set("● Awaiting first sync")
            self.trend_label.config(fg=COLORS["text_soft"], bg=COLORS["bg_tertiary"])

    def update_timestamp(self):
        """Update the dashboard timestamp to the current local time."""
        now = datetime.now().strftime("%I:%M:%S %p").lstrip("0")
        self.last_update.set(now)

    def schedule_auto_refresh(self):
        """Schedule the next automatic background refresh."""
        with self._state_lock:
            if self._is_closing:
                return

        if self.auto_refresh_id:
            self.root.after_cancel(self.auto_refresh_id)

        self.auto_refresh_id = self.root.after(REFRESH_INTERVAL_MS, self.auto_refresh)

    def auto_refresh(self):
        """Refresh prices quietly and schedule the next automatic refresh."""
        with self._state_lock:
            if self._is_closing:
                return

        self.fetch_price(silent=True)
        self.schedule_auto_refresh()

    def show_history(self):
        """Show the history screen with summary cards and a chart."""
        if self.history_window is not None and self.history_window.is_open():
            if self.app_shell is not None:
                self.app_shell.show_view("history")
            self.status_label.config(text="History view focused", fg=COLORS["success"])
            return

        if not history_window_available():
            self.status_label.config(
                text=history_window_unavailable_message(),
                fg=COLORS["error"],
            )
            return

        if self.dashboard_view is not None and self.history_btn is not None:
            self.dashboard_view.disable_button(self.history_btn)
        if self.app_shell is not None:
            self.app_shell.set_history_enabled(False)
        self.status_label.config(text="Loading history...", fg=COLORS["text_muted"])

        def load_and_show():
            try:
                history_series = fetch_historical_prices(days=HISTORY_DAYS)

                logger.info("Loaded %s days of historical gold prices", HISTORY_DAYS)
                self._queue_ui_update(lambda: self._open_history_window(history_series))

            except PriceFetchError as e:
                logger.warning("History load failed: %s", e)
                error_msg = str(e)[:30]
                self._queue_ui_update(
                    lambda msg=error_msg: self.status_label.config(
                        text=f"History error: {msg}...",
                        fg=COLORS["error"],
                    )
                )
                self._queue_ui_update(self._enable_history_button)
            except Exception:
                logger.exception(
                    "Unexpected error while loading historical gold prices"
                )
                self._queue_ui_update(
                    lambda: self.status_label.config(
                        text="Error loading history",
                        fg=COLORS["error"],
                    )
                )
                self._queue_ui_update(self._enable_history_button)

        if not self._history_worker.start(load_and_show):
            self._enable_history_button()
            if not self._is_closing:
                self.status_label.config(
                    text="History is already loading",
                    fg=COLORS["warning"],
                )

    def show_profit_calculator(self):
        """Show the profit calculator screen."""
        _, price_per_gram, _ = self._snapshot_price_state()

        if (
            self.profit_calculator_window is not None
            and self.profit_calculator_window.is_open()
        ):
            self.profit_calculator_window.update_market_price(price_per_gram)
            if self.app_shell is not None:
                self.app_shell.show_view("profit")
            self.status_label.config(
                text="Profit calculator focused", fg=COLORS["success"]
            )
            return

        self.profit_calculator_window = ProfitCalculatorWindow(
            parent=self.app_shell.content_frame if self.app_shell else self.root,
            current_price_per_gram=price_per_gram,
            on_close=self._handle_profit_calculator_closed,
            embedded=True,
        )
        if self.app_shell is not None:
            self.app_shell.add_view("profit", self.profit_calculator_window.window)
            self.app_shell.show_view("profit")
        self.status_label.config(text="Profit calculator opened", fg=COLORS["success"])

    def _handle_profit_calculator_closed(self) -> None:
        """Reset app state after the profit calculator is dismissed."""
        self.profit_calculator_window = None
        if self.app_shell is not None:
            self.app_shell.remove_view("profit")
        if not self._is_closing:
            self.show_dashboard()

    def _open_history_window(self, history_series: HistoricalPriceSeries) -> None:
        """Create the history view once data has loaded."""
        try:
            self.history_window = HistoryWindow(
                parent=self.app_shell.content_frame if self.app_shell else self.root,
                history_series=history_series,
                on_close=self._handle_history_window_closed,
                embedded=True,
            )
        except HistoryWindowError as exc:
            logger.warning("Unable to open history window: %s", exc)
            self.status_label.config(text=str(exc), fg=COLORS["error"])
            self._enable_history_button()
            return

        if self.app_shell is not None:
            self.app_shell.add_view("history", self.history_window.window)
            self.app_shell.show_view("history")

        logger.info("History view opened")
        self.status_label.config(text="History loaded", fg=COLORS["success"])
        self._enable_history_button()

    def _handle_history_window_closed(self) -> None:
        """Reset app state after the history window is dismissed."""
        self.history_window = None
        if self.app_shell is not None:
            self.app_shell.remove_view("history")
        if not self._is_closing:
            self._enable_history_button()
            self.show_dashboard()

    def _enable_history_button(self):
        """Re-enable the history button."""
        if self._is_closing:
            return

        try:
            if self.dashboard_view is not None:
                if self.history_btn is not None:
                    self.dashboard_view.enable_button(self.history_btn)
            if self.app_shell is not None:
                self.app_shell.set_history_enabled(True)
        except tk.TclError:
            logger.debug("History button was already destroyed")

    def _enable_refresh_button(self) -> None:
        """Re-enable the refresh button after a fetch completes."""
        if self._is_closing:
            return

        try:
            if self.dashboard_view is not None:
                self.dashboard_view.enable_button(self.refresh_btn)
                self._sync_history_button_availability()
        except tk.TclError:
            logger.debug("Refresh button was already destroyed")

    def _sync_history_button_availability(self) -> None:
        """Apply the correct startup state for the history button."""
        if self.dashboard_view is None:
            return

        if history_window_available():
            if self.history_btn is not None:
                self.dashboard_view.enable_button(self.history_btn)
            if self.app_shell is not None:
                self.app_shell.set_history_enabled(True)
            return

        # Keep the action visibly unavailable when chart dependencies are missing.
        if self.history_btn is not None:
            self.dashboard_view.disable_button(self.history_btn)
        if self.app_shell is not None:
            self.app_shell.set_history_enabled(False)

    def _restore_status_message(
        self,
        expected_text: str,
        original_text: str,
        original_color: str,
    ) -> None:
        """Restore a transient status message only if nothing newer replaced it."""
        if self._is_closing:
            return

        try:
            if self.status_label.cget("text") == expected_text:
                self.status_label.config(text=original_text, fg=original_color)
        except tk.TclError:
            logger.debug("Status label was already destroyed")


def main():
    """Launch the GoldTracker application."""
    configure_logging()
    logger.info("Starting GoldTracker")
    root = tk.Tk()
    _app = GoldTracker(root)
    try:
        root.mainloop()
    finally:
        logger.info("GoldTracker stopped")


if __name__ == "__main__":
    main()
