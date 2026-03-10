import os
import time
import threading
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

class ConfigWatcher:
    """Watch configuration file for changes and trigger reload callbacks."""

    def __init__(self, config_path: str, callback: Callable, poll_interval: int = 5):
        """
        Initialize config watcher.

        Args:
            config_path: Path to configuration file
            callback: Function to call when config changes (receives new config dict)
            poll_interval: Seconds between file modification checks
        """
        self.config_path = config_path
        self.callback = callback
        self.poll_interval = poll_interval
        self.last_modified = 0
        self.last_size = 0
        self._stop_event = threading.Event()
        self._watch_thread: Optional[threading.Thread] = None
        self._running = False

    def start(self):
        """Start watching for configuration changes."""
        if self._running:
            logger.debug("Config watcher already running")
            return

        # Get initial file stats
        try:
            stat = os.stat(self.config_path)
            self.last_modified = stat.st_mtime
            self.last_size = stat.st_size
        except FileNotFoundError:
            logger.error(f"Config file not found: {self.config_path}")
            return

        self._running = True
        self._stop_event.clear()
        self._watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._watch_thread.start()
        logger.info(f"Config watcher started for {self.config_path}")

    def stop(self):
        """Stop watching for configuration changes."""
        if not self._running:
            return

        self._stop_event.set()
        if self._watch_thread and self._watch_thread.is_alive():
            self._watch_thread.join(timeout=self.poll_interval + 1)
        self._running = False
        logger.info("Config watcher stopped")

    def _watch_loop(self):
        """Main watch loop checking for file changes."""
        while not self._stop_event.is_set():
            try:
                self._check_for_changes()
            except Exception as e:
                logger.error(f"Error checking config file: {str(e)}")

            # Wait with stop event check
            self._stop_event.wait(self.poll_interval)

    def _check_for_changes(self):
        """Check if configuration file has been modified."""
        try:
            stat = os.stat(self.config_path)
            current_modified = stat.st_mtime
            current_size = stat.st_size

            # Check if file has changed (mtime or size)
            if current_modified != self.last_modified or current_size != self.last_size:
                logger.info(f"Configuration file change detected: {self.config_path}")

                # Debounce: wait a moment to ensure write is complete
                time.sleep(0.5)

                # Update tracked stats
                self.last_modified = current_modified
                self.last_size = current_size

                # Trigger callback
                try:
                    self.callback()
                except Exception as e:
                    logger.error(f"Config reload callback failed: {str(e)}")

        except FileNotFoundError:
            logger.warning(f"Config file temporarily unavailable: {self.config_path}")
        except Exception as e:
            logger.error(f"Unexpected error checking config file: {str(e)}")
