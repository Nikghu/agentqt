"""
Module: MD-SCR-019.002.M40 — core/stock_context/_cache.py
Parent SRD: SRD-SCR-018.002, SRD-SCR-019.002

Daily JSON cache shared by the earnings and news lookups: one answer per
symbol per day, so each stock is looked up at most once a day.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)


class DailyCache:
    """Symbol → value checked on a given day, kept in one JSON file."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data = self._load()

    def get(self, symbol: str, day: str) -> tuple[bool, Any]:
        """``(True, value)`` when ``symbol`` was checked on ``day``, else ``(False, None)``."""
        entry = self._data.get(symbol)
        if isinstance(entry, dict) and entry.get("checked") == day and "value" in entry:
            return True, entry.get("value")
        return False, None

    def put(self, symbol: str, day: str, value: Any) -> None:
        self._data[symbol] = {"checked": day, "value": value}

    def save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._data, indent=1), encoding="utf-8")
            tmp.replace(self._path)
        except OSError:
            _log.warning("[Screener] Could not save the %s file", self._path.name)

    def _load(self) -> dict[str, Any]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}
