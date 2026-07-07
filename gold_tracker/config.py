"""Central configuration values for the GoldTracker application.

The module keeps UI, networking, caching, and logging values in one place so the
rest of the codebase can stay focused on behavior rather than constants.
"""

APP_NAME = "GoldTracker"
WINDOW_TITLE = "24K Gold Tracker"
WINDOW_SIZE = "1000x820"
FONT_FAMILY = "Segoe UI"
APP_ICON_PATH = "assets/gold_tracker.ico"

COLORS = {
    "bg_primary": "#1a1a2e",
    "bg_secondary": "#16213e",
    "bg_tertiary": "#102947",
    "gold": "#ffd700",
    "success": "#00ff88",
    "error": "#ff6666",
    "warning": "#ffb347",
    "text_primary": "#ffffff",
    "text_secondary": "#888888",
    "text_soft": "#b9cbe0",
    "text_muted": "#666666",
    "text_dim": "#555555",
    "border": "#29496b",
    "button_bg": "#0f3460",
    "button_active": "#1a4980",
    "button_primary": "#f4c95d",
    "button_primary_active": "#ffd86e",
    "button_primary_text": "#102947",
}

EGYPT_URL = "https://shop.bulliontradingcenter.com/product/10g-ingot-al-masjid-annabawi"
EGYPT_UNIT_GRAMS = 10
CHROME_DRIVER_PATH = ""
WORLDWIDE_API_URL = "https://GoldPrice.Today/api.php?data=live"
WORLDWIDE_CURRENCY = "EGP"

KEY_WORLDWIDE = "WORLDWIDE"
KEY_EGYPT = "EGYPT"

REFRESH_INTERVAL_MS = 60000
HISTORY_DAYS = 365
HISTORY_WINDOW_TITLE = "Gold Price History"
HISTORY_WINDOW_SIZE = "1040x720"
HISTORY_WINDOW_MIN_WIDTH = 1040
HISTORY_WINDOW_MIN_HEIGHT = 720
HISTORY_CHART_MONTH_INTERVAL = 2
PROFIT_WINDOW_TITLE = "Profit Calculator"
PROFIT_WINDOW_SIZE = "900x760"
PROFIT_WINDOW_MIN_WIDTH = 760
PROFIT_WINDOW_MIN_HEIGHT = 620

CACHE_DURATION_SECONDS = 60
STALE_CACHE_MAX_AGE_SECONDS = 300
FETCH_RETRY_ATTEMPTS = 3
FETCH_RETRY_BACKOFF_SECONDS = 1.5
REQUEST_TIMEOUT_SECONDS = 10
PAGE_LOAD_TIMEOUT_SECONDS = 30
SELENIUM_WAIT_TIMEOUT_SECONDS = 15

LOG_LEVEL = "INFO"
LOG_FILE_NAME = "gold_tracker.log"
LOG_MAX_BYTES = 1048576
LOG_BACKUP_COUNT = 3

MIN_VALID_PRICE = 1000
TROY_OUNCE_TO_GRAMS = 31.1034768
