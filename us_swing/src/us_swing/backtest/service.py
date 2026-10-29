"""
Module: MD-BKT-002.008.M05 — backtest/service.py
Parent SRD: SRD-BKT-002.008, SRD-BKT-002.017

``BacktestService``: the one entry point for the GUI, the CLI and (later) MCP.
Phase 0–1: data check estimate and the Step 1 (Stocks) run.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

import pandas as pd

from us_swing.backtest.cache import StepCache
from us_swing.backtest.results import ResultsStore
from us_swing.backtest.spec import Period, RunPlan
from us_swing.backtest.steps import stocks
from us_swing.backtest.store import BacktestStore
from us_swing.backtest.universe import UniverseRecord, resolve

_log = logging.getLogger(__name__)

_EDGE_DAYS = 5

PresetLoader = Callable[[str, str], dict[str, Any]]


@dataclass(frozen=True)
class Estimate:
    """Data check result shown before every run (SRD-BKT-002.008)."""

    symbols: list[str]
    missing_1d: list[str]
    missing_3m: list[str]
    benchmark_ok: bool
    days_total: int
    days_cached: int
    errors: list[str]


@dataclass(frozen=True)
class DailyList:
    """Step 1 output: the cache key, the period's trading days and the ranked list."""

    key: str
    days: list[date]
    frame: pd.DataFrame


def _misses(store: BacktestStore, symbol: str, tf: str, period: Period, today: date) -> bool:
    span = store.coverage(symbol, tf)  # type: ignore[arg-type]  # tf is "1d" or "3m"
    if span is None:
        return True
    end = min(period.end, today)
    return (span[0] - period.start).days > _EDGE_DAYS or (end - span[1]).days > _EDGE_DAYS


class BacktestService:
    """Estimate and run backtests from a ``RunPlan``.

    Args:
        records: Returns the universe records (symbol, sector, market_cap).
        presets: Loads a preset dict by (preset id, user id).
    """

    def __init__(
        self,
        store: BacktestStore,
        cache: StepCache,
        results: ResultsStore,
        records: Callable[[], Sequence[UniverseRecord]],
        presets: PresetLoader,
    ) -> None:
        self._store = store
        self._cache = cache
        self._results = results
        self._records = records
        self._presets = presets

    def estimate(self, plan: RunPlan, user_id: str, today: date | None = None) -> Estimate:
        """Return the stock count, missing candles and Step 1 day counts."""
        today = today or datetime.now(timezone.utc).date()
        symbols = resolve(plan.universe, self._records())
        errors = plan.validate()
        preset: dict[str, Any] | None = None
        if plan.screener.preset_id:
            try:
                preset = self._presets(plan.screener.preset_id, user_id)
            except Exception as exc:  # noqa: BLE001 — shown to the user as a message
                errors.append(f"Screener preset could not be loaded: {exc}")
        if preset is not None:
            errors += stocks.refusals(plan, preset)
        days_total = days_cached = 0
        if not errors and preset is not None:
            days = stocks.trading_days(self._store, plan.period, symbols)
            todo = stocks.missing_days(self._cache, stocks.rules_key(preset, symbols), days)
            days_total, days_cached = len(days), len(days) - len(todo)
        return Estimate(
            symbols=symbols,
            missing_1d=[s for s in symbols if _misses(self._store, s, "1d", plan.period, today)],
            missing_3m=[s for s in symbols if _misses(self._store, s, "3m", plan.period, today)],
            benchmark_ok=self._store.coverage(stocks.BENCHMARK, "1d") is not None,
            days_total=days_total,
            days_cached=days_cached,
            errors=errors,
        )

    def run_stocks(
        self,
        plan: RunPlan,
        user_id: str,
        *,
        workers: int = 4,
        progress: stocks.Progress | None = None,
        cancel: stocks.Cancel | None = None,
    ) -> DailyList:
        """Run Step 1 and record the run (SRD-BKT-002.017).

        Raises:
            ValueError: the plan is not valid.
            StepRefused, StepCancelled: from Step 1.
        """
        errors = plan.validate()
        if errors:
            raise ValueError("; ".join(errors))
        records = self._records()
        symbols = resolve(plan.universe, records)
        caps = {r.symbol: float(cap) for r in records
                if (cap := getattr(r, "market_cap", None)) is not None}
        preset = self._presets(plan.screener.preset_id, user_id)
        self._cache.cleanup(datetime.now(timezone.utc))
        run_id = self._results.start_run(plan, datetime.now(timezone.utc))
        status, message = "failed", ""
        try:
            key, days = stocks.run_stocks(
                plan, preset, symbols, self._store, self._cache, caps,
                workers=workers, progress=progress, cancel=cancel,
            )
            status = "done"
        except stocks.StepCancelled:
            status = "cancelled"
            raise
        except Exception as exc:
            message = str(exc)
            raise
        finally:
            self._results.finish_run(run_id, status, datetime.now(timezone.utc), message)
        _log.info("[Backtest] Stock lists ready for %d day(s)", len(days))
        return DailyList(key, days, stocks.daily_list(self._cache, key, days))
