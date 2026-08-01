"""
Gold Tracker - A desktop application to track live gold prices in Egyptian Pounds (EGP).

Modules:
    - app: Main application controller and lifecycle
    - config: Configuration constants and settings
    - logging_config: Console and rotating file logging setup
    - models: Shared application data models
    - core: Background worker helpers
    - services: Price and history data integrations
    - ui: Tkinter views and shared UI components
"""

from pathlib import Path

import tomllib

# Read version and author from pyproject.toml
try:
    _pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    _pyproject = tomllib.loads(_pyproject_path.read_text(encoding="utf-8"))["project"]
    __version__ = _pyproject["version"]
    __author__ = (
        _pyproject["authors"][0]["name"] if _pyproject.get("authors") else "unknown"
    )
except (FileNotFoundError, KeyError, IndexError):
    __version__ = "unknown"
    __author__ = "unknown"
