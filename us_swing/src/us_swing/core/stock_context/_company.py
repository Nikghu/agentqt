"""
Module: MD-SCR-020.002.M41 — core/stock_context/_company.py
Parent SRD: SRD-SCR-020.002

Last EPS surprise, fundamentals, short interest and analyst changes per stock from
Yahoo Finance. Each part is cached once per stock per day and fetched only when a
ticked context kind needs it. Sync and network-bound: run off the GUI thread.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from us_swing.core.stock_context._cache import DailyCache

_log = logging.getLogger(__name__)

DEFAULT_CACHE_PATH = Path.home() / ".usswing" / "company_cache.json"
_PARTS_BY_KIND: dict[str, tuple[str, ...]] = {
    "surprise": ("eps",),
    "fundamentals": ("info",),
    "short": ("info",),
    "analysts": ("info", "changes"),
}
COMPANY_KINDS: frozenset[str] = frozenset(_PARTS_BY_KIND)
_INFO_KEYS = ("revenueGrowth", "profitMargins", "trailingPE", "debtToEquity",
              "shortPercentOfFloat", "shortRatio", "targetMeanPrice", "currentPrice")
_MAX_CHANGES = 10

Fetch = Callable[[str, str], Any]


@dataclass(frozen=True, slots=True)
class AnalystChange:
    """One analyst rating or target change."""

    day: str
    firm: str
    action: str
    grade: str = ""
    target: float | None = None


@dataclass(frozen=True, slots=True)
class CompanyFacts:
    """Company numbers for one stock; any value may be missing."""

    eps_surprise_pct: float | None = None
    revenue_growth_pct: float | None = None
    margin_pct: float | None = None
    pe: float | None = None
    debt_to_equity: float | None = None
    short_pct: float | None = None
    days_to_cover: float | None = None
    target_mean: float | None = None
    price: float | None = None
    changes: tuple[AnalystChange, ...] = ()


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _positive(value: Any) -> float | None:
    number = _number(value)
    return number if number is not None and number > 0 else None


def _pct(value: Any) -> float | None:
    number = _number(value)
    return None if number is None else round(number * 100, 2)


def _yahoo_part(symbol: str, part: str) -> Any:
    """One cached part for ``symbol``: "info" dict, "eps" fraction or "changes" rows."""
    import yfinance as yf  # type: ignore[import-untyped]

    ticker = yf.Ticker(symbol)
    if part == "info":
        info: Any = ticker.info or {}
        return {key: _number(info.get(key)) for key in _INFO_KEYS}
    if part == "eps":
        history: Any = ticker.earnings_history
        if history is None or history.empty or "surprisePercent" not in history:
            return None
        values = [_number(v) for v in history["surprisePercent"]]
        known = [v for v in values if v is not None]
        return known[-1] if known else None
    table: Any = ticker.upgrades_downgrades
    if table is None or table.empty:
        return []
    rows = table.sort_index(ascending=False).head(_MAX_CHANGES)
    return [{"day": str(when)[:10], "firm": str(row.get("Firm", "")),
             "action": str(row.get("Action", "")), "grade": str(row.get("ToGrade", "")),
             "target": _positive(row.get("currentPriceTarget"))}
            for when, row in rows.iterrows()]


def _facts(parts: Mapping[str, Any]) -> CompanyFacts:
    info = parts.get("info") or {}
    debt = _number(info.get("debtToEquity"))
    changes = tuple(
        AnalystChange(str(c.get("day", "")), str(c.get("firm", "")), str(c.get("action", "")),
                      str(c.get("grade", "")), _positive(c.get("target")))
        for c in parts.get("changes") or [] if isinstance(c, dict)
    )
    return CompanyFacts(
        eps_surprise_pct=_pct(parts.get("eps")),
        revenue_growth_pct=_pct(info.get("revenueGrowth")),
        margin_pct=_pct(info.get("profitMargins")),
        pe=_positive(info.get("trailingPE")),
        debt_to_equity=None if debt is None else round(debt / 100, 2),
        short_pct=_pct(info.get("shortPercentOfFloat")),
        days_to_cover=_number(info.get("shortRatio")),
        target_mean=_positive(info.get("targetMeanPrice")),
        price=_positive(info.get("currentPrice")),
        changes=changes,
    )


class CompanyLookup:
    """Company facts per stock, each Yahoo part fetched once per stock per day."""

    def __init__(self, cache_path: Path | None = None, fetch: Fetch | None = None) -> None:
        self._path = cache_path or DEFAULT_CACHE_PATH
        self._fetch = fetch or _yahoo_part

    def facts(
        self, symbols: Iterable[str], kinds: Iterable[str], today: date
    ) -> dict[str, CompanyFacts]:
        """Return the facts the ticked ``kinds`` need for each symbol (SRD-SCR-020.002).

        Args:
            symbols: Stocks to look up.
            kinds: Ticked context kinds; only their parts are fetched.
            today: The run date; parts cached on this date are reused.

        Returns:
            Symbol → facts. A failed part is left out and retried on the next call.
        """
        needed = sorted({part for kind in kinds for part in _PARTS_BY_KIND.get(kind, ())})
        if not needed:
            return {}
        cache = DailyCache(self._path)
        day = today.isoformat()
        result: dict[str, CompanyFacts] = {}
        failed = 0
        for symbol in symbols:
            hit, saved = cache.get(symbol, day)
            parts: dict[str, Any] = dict(saved) if hit and isinstance(saved, dict) else {}
            fetched = False
            for part in needed:
                if part in parts:
                    continue
                try:
                    parts[part] = self._fetch(symbol, part)
                    fetched = True
                except Exception:  # noqa: BLE001 — any data-source error only drops this part
                    failed += 1
            if fetched:
                cache.put(symbol, day, parts)
            result[symbol] = _facts(parts)
        if failed:
            _log.warning("[Screener] Company data lookup failed for %d part(s)", failed)
        cache.save()
        return result
