"""Module: MD-INF-005.001.M01 — monitoring/logging_setup.py
Parent SRD: SRD-INF-005.001, SRD-INF-005.002

Initialises the root logger with:
- Daily file handler: one file per calendar day, named us_swing_YYYY-MM-DD.log.
  At midnight the handler transparently opens tomorrow's file; yesterday's file
  is left on disk.  Files older than ``retention_days`` (default 30) are deleted.
- StreamHandler to stderr at WARNING+.
- sys.excepthook for uncaught-exception logging.

Call ``configure_logging()`` once at application startup, before any
other module emits log records.
"""
from __future__ import annotations

import datetime
import logging
import sys
import time
import traceback
import zoneinfo
from logging.handlers import BaseRotatingHandler
from pathlib import Path

_DATEFMT = "%Y-%m-%dT%H:%M:%S%z"


def _resolve_tz(name: str | None) -> datetime.tzinfo:
    """Return the zone for *name*, falling back to the machine's local zone.

    Args:
        name: An IANA zone name such as ``'US/Eastern'``, or None/empty for local.
    """
    if name:
        try:
            return zoneinfo.ZoneInfo(name)
        except Exception:
            pass
    local = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
    return local or datetime.timezone.utc


# ── Daily date-stamped file handler ──────────────────────────────────────────

class _DailyDateHandler(BaseRotatingHandler):
    """File handler that opens a new ``us_swing_YYYY-MM-DD.log`` each calendar day.

    Unlike the stdlib ``TimedRotatingFileHandler``, the *active* log file always
    carries today's date in its name.  No renaming occurs on rollover — the old
    file simply stays where it is (already correctly named) and a new dated file
    is opened.

    Args:
        log_dir:       Directory for log files (must already exist).
        backup_count:  How many daily files to keep.  Oldest deleted first.
                       0 means keep forever.
        encoding:      File encoding (default ``'utf-8'``).
        tz:            Zone deciding which calendar day a record belongs to.
    """

    def __init__(
        self,
        log_dir: Path,
        backup_count: int = 30,
        encoding: str = "utf-8",
        tz: datetime.tzinfo | None = None,
    ) -> None:
        self._log_dir     = log_dir
        self._backup_count = backup_count
        self._tz          = tz or _resolve_tz(None)
        self._current_date = self._today()
        filename = str(self._dated_path(self._current_date))
        super().__init__(filename, mode="a", encoding=encoding, delay=False)
        self._compute_next_rollover()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _dated_path(self, date: datetime.date) -> Path:
        return self._log_dir / f"us_swing_{date:%Y-%m-%d}.log"

    def _today(self) -> datetime.date:
        return datetime.datetime.now(self._tz).date()

    def _compute_next_rollover(self) -> None:
        """Set self.rolloverAt to the next midnight in the logging zone."""
        tomorrow = self._today() + datetime.timedelta(days=1)
        midnight = datetime.datetime.combine(tomorrow, datetime.time.min, tzinfo=self._tz)
        self.rolloverAt = midnight.timestamp()

    def shouldRollover(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        return time.time() >= self.rolloverAt

    def doRollover(self) -> None:
        # Close the current stream (leaves the old dated file intact).
        if self.stream:
            self.stream.flush()
            self.stream.close()
            self.stream = None  # type: ignore[assignment]

        # Open a new stream for today's date.
        self._current_date = self._today()
        self.baseFilename  = str(self._dated_path(self._current_date))
        self.stream        = self._open()

        # Prune files beyond retention window.
        if self._backup_count > 0:
            files = sorted(self._log_dir.glob("us_swing_????-??-??.log"))
            while len(files) > self._backup_count:
                files.pop(0).unlink(missing_ok=True)

        self._compute_next_rollover()


# ── Public API ────────────────────────────────────────────────────────────────

def configure_logging(
    log_dir: Path,
    level: str = "INFO",
    retention_days: int = 30,
    timezone: str | None = None,
) -> None:
    """Set up root logger with a daily dated file handler + stderr stream.

    Args:
        log_dir:        Directory for log files (created if absent).
        level:          Root log level string (e.g. ``'DEBUG'``, ``'INFO'``).
        retention_days: Number of daily log files to keep (default 30).
        timezone:       IANA zone for timestamps and daily rollover, e.g.
                        ``'US/Eastern'``.  Defaults to the machine's local zone.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    tz = _resolve_tz(timezone)

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(numeric_level)
    logging.getLogger("ib_insync").setLevel(logging.WARNING)

    # Avoid duplicate handlers when called more than once (e.g. in tests).
    if not any(isinstance(h, _DailyDateHandler) for h in root.handlers):
        file_handler = _DailyDateHandler(log_dir, backup_count=retention_days, tz=tz)
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(_formatter(tz))
        root.addHandler(file_handler)

    if not any(isinstance(h, logging.StreamHandler)
               and not isinstance(h, _DailyDateHandler)
               for h in root.handlers):
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setLevel(logging.WARNING)
        stream_handler.setFormatter(_formatter(tz))
        root.addHandler(stream_handler)

    _install_excepthook()
    logging.getLogger(__name__).info(
        "Logging configured — level=%s log_dir=%s retention=%dd timestamps=%s",
        level, log_dir, retention_days, tz,
    )


class _ZonedFormatter(logging.Formatter):
    """Stamps every record in a fixed zone, with the true UTC offset."""

    def __init__(self, tz: datetime.tzinfo) -> None:
        super().__init__(
            fmt     = "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
            datefmt = _DATEFMT,
        )
        self._tz = tz

    def formatTime(
        self, record: logging.LogRecord, datefmt: str | None = None
    ) -> str:
        stamped = datetime.datetime.fromtimestamp(record.created, self._tz)
        return stamped.strftime(datefmt or _DATEFMT)


def _formatter(tz: datetime.tzinfo) -> logging.Formatter:
    return _ZonedFormatter(tz)


def _install_excepthook() -> None:
    """Replace sys.excepthook to log all uncaught exceptions at CRITICAL."""
    _original = sys.excepthook

    def _hook(exc_type, exc_value, exc_tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            _original(exc_type, exc_value, exc_tb)
            return
        tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logging.critical("Uncaught exception:\n%s", tb_str)
        _original(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook

    sys.excepthook = _hook
