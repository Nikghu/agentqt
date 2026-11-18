"""
Module: MD-SCR-018.002.M36 — core/stock_context/_earnings.py
Parent SRD: SRD-SCR-018.002

Next earnings date per stock from Yahoo Finance, kept in a JSON cache so each
stock is looked up at most once a day. Sync and network-bound: run off the GUI thread.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterable
from datetime import date
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

DEFAULT_CACHE_PATH = Path.home() / ".usswing" / "earnings_cache.json"

Fetch = Callable[[str], list[date]]


def _yahoo_dates(symbol: str) -> list[date]:
    """Earnings dates Yahoo Finance lists for ``symbol`` (usually one, sometimes a range)."""
    import yfinance as yf  # type: ignore[import-untyped]

    calendar: Any = yf.Ticker(symbol).calendar
    values = calendar.get("Earnings Date", []) if isinstance(calendar, dict) else []
    return [value for value in values if isinstance(value, date)]


class EarningsLookup:
    """Next earnings date per stock, fetched once per stock per day (SRD-SCR-018.002)."""

    def __init__(self, cache_path: Path | None = None, fetch: Fetch | None = None) -> None:
        self._path = cache_path or DEFAULT_CACHE_PATH
        self._fetch = fetch or _yahoo_dates

    def next_dates(self, symbols: Iterable[str], today: date) -> dict[str, date | None]:
        """Return each symbol's first earnings date on or after ``today``, or None.

        Args:
            symbols: Stocks to look up.
            today: The run date; cached answers from this date are reused.

        Returns:
            Symbol → date or None. A failed lookup gives None and is retried next call.
        """
        cache = self._load()
        checked_on = today.isoformat()
        result: dict[str, date | None] = {}
        failed = 0
        for symbol in symbols:
            entry = cache.get(symbol)
            if isinstance(entry, dict) and entry.get("checked") == checked_on:
                saved = entry.get("date")
                result[symbol] = date.fromisoformat(saved) if saved else None
                continue
            try:
                upcoming = [d for d in self._fetch(symbol) if d >= today]
            except Exception:  # noqa: BLE001 — any data-source error only drops this stock
                failed += 1
                result[symbol] = None
                continue
            found = min(upcoming) if upcoming else None
            result[symbol] = found
            cache[symbol] = {"checked": checked_on, "date": found.isoformat() if found else None}
        if failed:
            _log.warning("[Screener] Earnings date lookup failed for %d stock(s)", failed)
        self._save(cache)
        return result

    def _load(self) -> dict[str, Any]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save(self, cache: dict[str, Any]) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(cache, indent=1), encoding="utf-8")
            tmp.replace(self._path)
        except OSError:
            _log.warning("[Screener] Could not save the earnings date cache")
