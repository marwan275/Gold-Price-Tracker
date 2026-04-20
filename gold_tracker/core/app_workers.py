"""Small background worker helpers for GoldTracker."""

from __future__ import annotations

from collections.abc import Callable
import logging
import threading


logger = logging.getLogger(__name__)


class BackgroundWorkerSlot:
    """Allow only one named background thread to run at a time."""

    def __init__(self, name: str) -> None:
        """Create a worker slot with a human-readable name."""
        self.name = name
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._shutdown_requested = False

    def is_running(self) -> bool:
        """Return True when this slot has an active worker thread."""
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def start(self, target: Callable[[], None]) -> bool:
        """Start the target unless a worker is running or shutdown began."""
        with self._lock:
            if self._shutdown_requested or self.is_running():
                return False

            def run() -> None:
                try:
                    target()
                finally:
                    with self._lock:
                        if self._thread is threading.current_thread():
                            self._thread = None

            self._thread = threading.Thread(
                target=run,
                name=f"GoldTracker-{self.name}",
                daemon=True,
            )
            self._thread.start()
            return True

    def request_shutdown(self) -> None:
        """Prevent new workers from starting."""
        with self._lock:
            self._shutdown_requested = True

    def join(self, timeout: float = 2.0) -> bool:
        """Wait up to timeout seconds and report whether the worker remains alive."""
        with self._lock:
            thread = self._thread

        if thread is None or not thread.is_alive():
            return False

        thread.join(timeout=timeout)
        if thread.is_alive():
            logger.warning("%s worker did not stop within %.1fs", self.name, timeout)
            return True
        return False
