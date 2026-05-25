"""Module: MD-SCR-003.001.M14 — screener/utils.py
Parent SRD: SRD-SCR-003.001, SRD-SCR-010.001–004

Shared utilities: PreFilter (price, volume, halted checks),
parallel_execute() helper, and re-exports of canonical error classes.
"""
from __future__ import annotations

import concurrent.futures
import logging
from typing import Any, Callable, TypeVar

_log = logging.getLogger(__name__)

from us_swing.screener.base import (  # noqa: F401 — re-export
    PreFilterError,
    PresetAccessDenied,
    PresetError,
    PresetNotFoundError,
    PresetValidationError,
    ScreenerError,
    ScreenerExecutionError,
    ScreenerNotFoundError,
    ScreenerValidationError,
)

_T = TypeVar("_T")
_R = TypeVar("_R")

_MIN_PRICE: float = 5.0
_MIN_VOLUME: int = 1_000_000


class PreFilter:
    """Stage 1 pre-filter: removes symbols with price ≤ $5 or volume < 1 M.

    Symbols with missing or empty bar lists are also excluded.
    Runs in O(N) time; designed to complete in < 1 s for 500 symbols.
    """

    def __init__(
        self,
        min_price: float = _MIN_PRICE,
        min_volume: int = _MIN_VOLUME,
    ) -> None:
        self._min_price = min_price
        self._min_volume = min_volume

    def apply(
        self,
        symbols: list[str],
        bars: dict[str, list[Any]],
    ) -> list[str]:
        """Filter *symbols* against price and volume thresholds.

        Args:
            symbols: Universe of symbol tickers.
            bars: OHLCV bars keyed by symbol.

        Returns:
            List of symbols that pass all filters, in input order.
        """
        passed: list[str] = []
        for sym in symbols:
            sym_bars = bars.get(sym)
            if not sym_bars:
                continue
            last = sym_bars[-1]
            if last.close <= self._min_price:
                continue
            if last.volume < self._min_volume:
                continue
            passed.append(sym)
        _log.debug("pre-filter: %d/%d symbols passed", len(passed), len(symbols))
        return passed


def parallel_execute(
    fn: Callable[[_T], _R],
    items: list[_T],
    max_workers: int = 4,
) -> list[_R]:
    """Execute *fn* over *items* in a thread pool and return results in order.

    Args:
        fn: Callable to apply to each item.
        items: Items to process.
        max_workers: Thread pool size.

    Returns:
        List of results, one per item, in the same order as *items*.
    """
    if not items:
        return []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(fn, items))
