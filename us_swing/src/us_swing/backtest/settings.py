"""
Module: MD-BKT-001.004.M02 — backtest/settings.py
Parent SRD: SRD-BKT-001.004

Backtest data settings (``settings.json``) and download state (``state.json``).
A missing or unreadable file loads the defaults.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

SETTINGS_FILE = "settings.json"
STATE_FILE = "state.json"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        _log.warning("[Backtest] Could not read %s — using defaults", path.name)
        return None
    return data if isinstance(data, dict) else None


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


@dataclass(frozen=True)
class BacktestDataSettings:
    """User settings for the backtest data download.

    Attributes:
        start_date: First date to download.
        end_date: Last date to download; ``None`` means up to the latest trading day.
        auto_delta: Whether the daily delta fill runs on its own.
        run_time: Auto delta time of day, US/Eastern.
        run_days: Weekdays the auto delta runs on (0 = Monday).
    """

    start_date: date = date(2016, 1, 1)
    end_date: date | None = None
    auto_delta: bool = True
    run_time: time = time(17, 30)
    run_days: tuple[int, ...] = (0, 1, 2, 3, 4)

    @classmethod
    def load(cls, root: Path) -> BacktestDataSettings:
        """Load settings from ``root``; defaults when missing or unreadable."""
        data = _read_json(root / SETTINGS_FILE)
        if data is None:
            return cls()
        try:
            end = data.get("end_date")
            return cls(
                start_date=date.fromisoformat(data["start_date"]),
                end_date=date.fromisoformat(end) if end else None,
                auto_delta=bool(data["auto_delta"]),
                run_time=time.fromisoformat(data["run_time"]),
                run_days=tuple(int(d) for d in data["run_days"]),
            )
        except (KeyError, TypeError, ValueError):
            _log.warning("[Backtest] Settings file has bad values — using defaults")
            return cls()

    def save(self, root: Path) -> None:
        """Write settings to ``root`` atomically."""
        _write_json(root / SETTINGS_FILE, {
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "auto_delta": self.auto_delta,
            "run_time": self.run_time.strftime("%H:%M"),
            "run_days": list(self.run_days),
        })


@dataclass
class DownloadState:
    """Download progress kept between runs.

    Attributes:
        last_delta: When the last delta fill finished (timezone-aware).
        floors: Per stock, the first date IBKR has 3m data for.
        failed: Stocks whose requests failed in the last run.
    """

    last_delta: datetime | None = None
    floors: dict[str, date] = field(default_factory=dict)
    failed: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, root: Path) -> DownloadState:
        """Load state from ``root``; empty state when missing or unreadable."""
        data = _read_json(root / STATE_FILE)
        if data is None:
            return cls()
        try:
            last = data.get("last_delta")
            return cls(
                last_delta=datetime.fromisoformat(last) if last else None,
                floors={s: date.fromisoformat(d) for s, d in data.get("floors", {}).items()},
                failed=[str(s) for s in data.get("failed", [])],
            )
        except (AttributeError, TypeError, ValueError):
            _log.warning("[Backtest] Download state file has bad values — starting fresh")
            return cls()

    def save(self, root: Path) -> None:
        """Write state to ``root`` atomically."""
        _write_json(root / STATE_FILE, {
            "last_delta": self.last_delta.isoformat() if self.last_delta else None,
            "floors": {s: d.isoformat() for s, d in self.floors.items()},
            "failed": self.failed,
        })
