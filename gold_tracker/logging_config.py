"""Logging setup for the GoldTracker desktop app."""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import (
    APP_DATA_DIR_NAME,
    LOG_BACKUP_COUNT,
    LOG_FILE_NAME,
    LOG_LEVEL,
    LOG_MAX_BYTES,
)


logger = logging.getLogger(__name__)

NOISY_DEPENDENCY_LOGGERS = (
    "WDM",
    "peewee",
    "selenium",
    "urllib3",
    "webdriver_manager",
    "yfinance",
)


def _get_log_directory() -> Path:
    """Return the preferred per-user directory for application log files."""
    local_appdata = os.getenv("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / APP_DATA_DIR_NAME / "logs"

    return Path.home() / f".{APP_DATA_DIR_NAME.lower()}" / "logs"


def configure_logging() -> None:
    """Configure console and rotating file logging for the desktop app."""
    if getattr(configure_logging, "_configured", False):
        return

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    fallback_warning: str | None = None
    log_path: Path | None = None

    try:
        log_dir = _get_log_directory()
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / LOG_FILE_NAME
        handlers.append(
            RotatingFileHandler(
                log_path,
                maxBytes=LOG_MAX_BYTES,
                backupCount=LOG_BACKUP_COUNT,
                encoding="utf-8",
            )
        )
    except OSError as exc:
        fallback_warning = f"Could not initialize file logging: {exc}"

    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=handlers,
        force=True,
    )
    for logger_name in NOISY_DEPENDENCY_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    configure_logging._configured = True

    if log_path is not None:
        logger.info("Logging initialized at %s", log_path)
    if fallback_warning is not None:
        logger.warning(fallback_warning)
