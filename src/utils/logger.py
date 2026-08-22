"""
Per-run file logging for the test framework.

As supplied, `_setup_logger` created the log directory, computed a filename, and then
returned a bare `logging.Logger` with no handler, no formatter and no level. Nothing
was ever written, `log_file` was a dead variable, and every `info()` and `debug()` call
was discarded because an unconfigured logger inherits WARNING (ISS-09).
"""

import logging
import time
from datetime import datetime, timezone
from pathlib import Path

# Resolved from this file rather than the working directory, for the same reason
# result_manager.RESULTS_DIR is: "results/logs" as a relative path follows the caller,
# so running from anywhere but the repo root quietly starts a second log tree beside
# them. The two constants are deliberate twins - if the layout ever moves, both move.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "results" / "logs"

# The archive stores measurement timestamps in UTC, so the logs do too: a log line and
# a sample are only correlatable if they are on the same clock. `Z` is in the format
# string because logging's own %(asctime)s carries no zone.
LOG_FORMAT = "%(asctime)sZ %(levelname)-8s %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"
FILENAME_TIME_FORMAT = "%Y%m%dT%H%M%SZ"


class TestLogger:
    """
    A named logger that writes one file per test run under `results/logs/`.

    Detail goes to the file at DEBUG; only warnings and errors reach the console, so
    diagnostics never interleave with the result tables on stdout. Console output goes
    to stderr for the same reason.
    """

    def __init__(
        self,
        test_name: str,
        *,
        level: int = logging.DEBUG,
        console_level: int = logging.WARNING,
        log_dir: Path | str | None = None,
    ):
        self._test_name = test_name
        self._log_dir = Path(log_dir) if log_dir is not None else LOG_DIR

        timestamp = datetime.now(timezone.utc).strftime(FILENAME_TIME_FORMAT)
        self.log_file = self._log_dir / f"{timestamp}_{test_name}.log"

        self.logger = self._setup_logger(level, console_level)

    def _setup_logger(self, level: int, console_level: int) -> logging.Logger:
        logger = logging.getLogger(f"test_{self._test_name}")
        logger.setLevel(level)

        # Handled here and nowhere else. Without this, a caller who has configured the
        # root logger receives every line a second time.
        logger.propagate = False

        # getLogger returns the *same* object for a repeated name, so a second
        # TestLogger with the same test_name would stack a second set of handlers and
        # write every line twice. Adopt the file the name already owns instead, so
        # `log_file` still names the file that is actually being written.
        existing_file_handler = next(
            (h for h in logger.handlers if isinstance(h, logging.FileHandler)), None
        )

        if existing_file_handler is not None:
            self.log_file = Path(existing_file_handler.baseFilename)
            return logger

        self._log_dir.mkdir(parents=True, exist_ok=True)

        formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
        # Default is localtime; the filename and the measurement timestamps are UTC.
        formatter.converter = time.gmtime

        # Explicit UTF-8, never the platform's code page. This is ISS-24's lesson
        # applied to files: a log must not fail, or mangle, based on the machine's
        # locale, and a run archived on Windows has to be readable on Linux.
        file_handler = logging.FileHandler(self.log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(console_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        return logger

    def close(self) -> None:
        """
        Release the log file.

        One run is one logger is one open file handle. Without this a long-lived
        process accumulates them, and on Windows the file stays locked against
        anything that wants to read or move it.
        """
        for handler in list(self.logger.handlers):
            self.logger.removeHandler(handler)
            handler.close()

    def __enter__(self) -> "TestLogger":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    # `*args` is passed through rather than formatted here, so a message that is
    # filtered out by level costs nothing to build.
    def info(self, message: str, *args):
        self.logger.info(message, *args)

    def error(self, message: str, *args):
        self.logger.error(message, *args)

    def debug(self, message: str, *args):
        self.logger.debug(message, *args)

    def warning(self, message: str, *args):
        self.logger.warning(message, *args)
