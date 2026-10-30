"""
Module: MD-BKT-002.008.M05 — backtest/service.py
Parent SRD: SRD-BKT-002.008, SRD-BKT-002.017, SRD-BKT-002.029, SRD-BKT-002.039,
            SRD-BKT-002.040, SRD-BKT-002.060, SRD-BKT-002.080–.081, SRD-MCP-007.005

``BacktestService``: the one entry point for the GUI, the CLI and MCP.
Phase 0–4: data check estimate, Step 1 (Stocks), Step 2 (Signals), Step 3 (Portfolio),
Step 4 (Report).
"""
from __future__ import annotations

import logging
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, TypeVar

import pandas as pd

from us_swing.backtest.cache import StepCache
from us_swing.backtest.results import ResultsStore, RunRow
from us_swing.backtest.spec import Period, RunPlan, Variant
from us_swing.backtest.steps import portfolio, recorded, report, signals, stocks
from us_swing.backtest.store import BacktestStore, StoredTf
from us_swing.backtest.universe import UniverseRecord, resolve

_log = logging.getLogger(__name__)

_EDGE_DAYS = 5
_BENCHMARK_LOOKBACK_DAYS = 10

PresetLoader = Callable[[str, str], dict[str, Any]]
StrategyLoader = Callable[[], Sequence[dict[str, Any]]]
_T = TypeVar("_T")


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
    recorded: bool = False  # days_cached counts sessions with a saved screener list


@dataclass(frozen=True)
class DailyList:
    """Step 1 output: the cache key, the period's sessions and the ranked list.

    ``data_days`` maps each session to the trading day whose close made its list.
    """

    key: str
    days: list[date]
    frame: pd.DataFrame
    data_days: dict[date, date]


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
        strategies: Returns the live strategies as dicts (Step 2).
    """

    def __init__(
        self,
        store: BacktestStore,
        cache: StepCache,
        results: ResultsStore,
        records: Callable[[], Sequence[UniverseRecord]],
        presets: PresetLoader,
        strategies: StrategyLoader = tuple,
        screener_results: Path = recorded.RESULTS_DIR,
    ) -> None:
        self._screener_results = screener_results
        self._store = store
        self._cache = cache
        self._results = results
        self._records = records
        self._presets = presets
        self._strategies = strategies

    def estimate(self, plan: RunPlan, user_id: str, today: date | None = None) -> Estimate:
        """Return the stock count, missing candles and Step 1 day counts."""
        today = today or datetime.now(timezone.utc).date()
        symbols = resolve(plan.universe, self._records())
        errors = plan.validate()
        if plan.screener.recorded:
            return self._estimate_recorded(plan, symbols, errors, today)
        preset: dict[str, Any] | None = None
        if plan.screener.preset_id:
            try:
                preset = self._presets(plan.screener.preset_id, user_id)
            except Exception as exc:  # noqa: BLE001 — shown to the user as a message
                errors.append(f"Screener preset could not be loaded: {exc}")
        if preset is not None:
            errors += stocks.refusals(plan, preset, stocks.has_benchmark(self._store))
        spy = [stocks.BENCHMARK] if preset and stocks.needs_benchmark(preset) else []
        days_total = days_cached = 0
        if not errors and preset is not None:
            days = list(stocks.sessions(self._store, plan.period, symbols).values())
            todo = stocks.missing_days(self._cache, stocks.rules_key(preset, symbols), days)
            days_total, days_cached = len(days), len(days) - len(todo)
        return Estimate(
            symbols=symbols,
            missing_1d=[s for s in [*symbols, *spy]
                        if _misses(self._store, s, "1d", plan.period, today)],
            missing_3m=[s for s in symbols if _misses(self._store, s, "3m", plan.period, today)],
            benchmark_ok=self._store.coverage(stocks.BENCHMARK, "1d") is not None,
            days_total=days_total,
            days_cached=days_cached,
            errors=errors,
        )

    def _estimate_recorded(self, plan: RunPlan, symbols: list[str], errors: list[str],
                           today: date) -> Estimate:
        """Data check for saved screener lists: sessions with a list (SRD-BKT-002.081)."""
        total = with_list = 0
        if not errors:
            sessions = list(stocks.sessions(self._store, plan.period, symbols))
            frame = recorded.load_lists(plan.screener.preset_id, sessions, set(symbols),
                                        self._screener_results)
            total, with_list = len(sessions), frame["date"].nunique()
            if total and not with_list:
                errors.append("No saved screener list for this preset in the period")
        return Estimate(
            symbols=symbols,
            missing_1d=[s for s in symbols if _misses(self._store, s, "1d", plan.period, today)],
            missing_3m=[s for s in symbols if _misses(self._store, s, "3m", plan.period, today)],
            benchmark_ok=self._store.coverage(stocks.BENCHMARK, "1d") is not None,
            days_total=total, days_cached=with_list, errors=errors, recorded=True,
        )

    def saved_days(self, preset_id: str) -> list[date]:
        """Dates of the screener lists the app saved for a preset (SRD-GUI-031.060)."""
        return recorded.saved_days(preset_id, self._screener_results)

    def run_stocks(
        self,
        plan: RunPlan,
        user_id: str,
        *,
        workers: int = 4,
        progress: stocks.Progress | None = None,
        cancel: stocks.Cancel | None = None,
        record: bool = True,
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
        if plan.screener.recorded:
            return self._recorded(plan, lambda _run_id: self._saved_lists(plan, symbols), record)
        caps = {r.symbol: float(cap) for r in records
                if (cap := getattr(r, "market_cap", None)) is not None}
        preset = self._presets(plan.screener.preset_id, user_id)
        self._cache.cleanup(datetime.now(timezone.utc))
        key, by_session = self._recorded(plan, lambda _run_id: stocks.run_stocks(
            plan, preset, symbols, self._store, self._cache, caps,
            workers=workers, progress=progress, cancel=cancel,
        ), record)
        _log.info("[Backtest] Stock lists ready for %d session(s)", len(by_session))
        return DailyList(key, list(by_session), stocks.daily_list(self._cache, key, by_session),
                         by_session)

    def _saved_lists(self, plan: RunPlan, symbols: list[str]) -> DailyList:
        """Step 1 from the saved screener lists (SRD-BKT-002.080)."""
        by_session = stocks.sessions(self._store, plan.period, symbols)
        frame = recorded.load_lists(plan.screener.preset_id, list(by_session), set(symbols),
                                    self._screener_results)
        _log.info("[Backtest] Saved screener lists found for %d of %d session(s)",
                  frame["date"].nunique(), len(by_session))
        return DailyList(f"recorded-{plan.screener.preset_id}", list(by_session), frame,
                         by_session)

    def run_signals(
        self,
        plan: RunPlan,
        daily: DailyList,
        *,
        workers: int = 4,
        progress: stocks.Progress | None = None,
        cancel: stocks.Cancel | None = None,
        record: bool = True,
    ) -> pd.DataFrame:
        """Run Step 2 on Step 1's list and record the run (SRD-BKT-002.029).

        Raises:
            ValueError: no strategy picked, or a name is not in the live store.
            StepCancelled: from Step 2.
        """
        chosen = self._chosen_strategies(plan)
        frame = self._recorded(plan, lambda _run_id: signals.run_signals(
            plan.period, chosen, daily.frame, plan.screener.top_n, self._store, self._cache,
            workers=workers, progress=progress, cancel=cancel,
        ), record)
        _log.info("[Backtest] Found %d signal period(s) for %d strategy(ies)",
                  len(frame), len(chosen))
        return frame

    def run_portfolio(
        self,
        plan: RunPlan,
        daily: DailyList,
        found: pd.DataFrame,
        *,
        progress: stocks.Progress | None = None,
        cancel: stocks.Cancel | None = None,
        started: Callable[[str], None] | None = None,
    ) -> list[portfolio.VariantResult]:
        """Run Step 3 for every variant and save the rows (SRD-BKT-002.039).

        ``started`` gets the saved run id before Step 3 begins (SRD-MCP-007.005).

        Raises:
            ValueError: no strategy picked, or a name is not in the live store.
            StepRefused, StepCancelled: from Step 3.
        """
        chosen = self._chosen_strategies(plan)

        def work(run_id: str) -> list[portfolio.VariantResult]:
            if started is not None:
                started(run_id)
            results = portfolio.run_portfolio(
                plan, chosen, daily.frame, daily.days, found, self._store,
                progress=progress, cancel=cancel,
            )
            for i, res in enumerate(results):
                self._results.save_variant(run_id, i, res.variant, res.trades, res.day_log,
                                           res.money)
            return results

        results = self._recorded(plan, work)
        _log.info("[Backtest] Portfolio done: %d trade(s) in %d variant(s)",
                  sum(len(r.trades) for r in results), len(results))
        return results

    def build_reports(self, plan: RunPlan, results: Sequence[portfolio.VariantResult]
                      ) -> list[report.Report]:
        """Step 4 for each variant, with the equal-weight benchmark (SRD-BKT-002.040–.046)."""
        records = self._records()
        sectors = {r.symbol: str(getattr(r, "sector", "") or "Unknown") for r in records}
        closes = self._closes(resolve(plan.universe, records), plan.period)
        out = []
        for res in results:
            days = sorted(pd.to_datetime(res.money["date"]).dt.date)
            bench = report.equal_weight_benchmark(closes, days, res.variant.capital)
            rep = report.build_report(variant_label(res.variant), res.variant.capital,
                                      res.trades, res.money, res.day_log, sectors, bench)
            per_trade = res.variant.strategies[0][2] if res.variant.strategies else math.nan
            out.append(replace(rep, per_trade_pct=per_trade))
        return out

    def saved_results(self, run_id: str) -> list[portfolio.VariantResult]:
        """Step 3 rows of a saved run, one per variant, in order."""
        return [
            portfolio.VariantResult(variant, self._results.read_table("trades", vid),
                                    self._results.read_table("day_log", vid),
                                    self._results.read_table("money_daily", vid))
            for vid, variant in self._results.list_variants(run_id)
        ]

    def saved_reports(self) -> list[SavedReport]:
        """Saved runs with Step 3 results, newest first, with their first variant's numbers."""
        out = []
        for run in self._results.list_reports():
            variants = self._results.list_variants(run.run_id)
            vid, variant = variants[0]
            trades = self._results.read_table("trades", vid)
            equity = self._results.read_table("money_daily", vid)["equity"].astype(float)
            net = float(trades["net_pnl"].astype(float).sum())
            dd = float((equity / equity.cummax() - 1.0).min()) if len(equity) else 0.0
            out.append(SavedReport(run, RunPlan.from_json(run.plan_json), len(trades), net,
                                   net / variant.capital, dd))
        return out

    def open_run(self, run_id: str, user_id: str, *, workers: int = 4,
                 progress: stocks.Progress | None = None,
                 cancel: stocks.Cancel | None = None) -> OpenedRun:
        """Read a saved run back: Steps 1–2 from the step cache, Step 3 from ``results.db``.

        Raises:
            ValueError: the run id is unknown.
        """
        run = self._results.get_run(run_id)
        if run is None:
            raise ValueError(f"No saved run {run_id}")
        plan = RunPlan.from_json(run.plan_json)
        daily = self.run_stocks(plan, user_id, workers=workers, progress=progress,
                                cancel=cancel, record=False)
        found = (self.run_signals(plan, daily, workers=workers, progress=progress,
                                  cancel=cancel, record=False)
                 if plan.strategies else None)
        results = self.saved_results(run_id)
        return OpenedRun(plan, daily, found, results, self.build_reports(plan, results))

    def get_run(self, run_id: str) -> RunRow | None:
        """One saved run, or None when the id is unknown."""
        return self._results.get_run(run_id)

    def rename_run(self, run_id: str, name: str) -> None:
        """Rename a saved run (SRD-BKT-002.060)."""
        self._results.rename_run(run_id, name)

    def set_note(self, run_id: str, note: str) -> None:
        """Save a note on a run (SRD-BKT-002.060)."""
        self._results.set_note(run_id, note)

    def delete_run(self, run_id: str) -> None:
        """Delete a saved run and all its rows (SRD-BKT-002.060)."""
        self._results.delete_run(run_id)
        _log.info("[Backtest] Saved run deleted")

    def report_for_run(self, run_id: str) -> list[report.Report]:
        """Step 4 from a saved run's rows in ``results.db``, without running Steps 1–3.

        Raises:
            ValueError: the run id is unknown.
        """
        run = self._results.get_run(run_id)
        if run is None:
            raise ValueError(f"No saved run {run_id}")
        return self.build_reports(RunPlan.from_json(run.plan_json), self.saved_results(run_id))

    def bars(self, symbol: str, tf: StoredTf, start: date, end: date) -> pd.DataFrame:
        """Saved bars of one stock for the Inspector chart (SRD-GUI-031.052)."""
        return self._store.read(symbol, tf, start, end)

    def _closes(self, symbols: Sequence[str], period: Period) -> dict[str, pd.Series]:
        start = period.start - timedelta(days=_BENCHMARK_LOOKBACK_DAYS)
        out: dict[str, pd.Series] = {}
        for sym in symbols:
            frame = self._store.read(sym, "1d", start, period.end)
            if not frame.empty:
                out[sym] = pd.Series(frame["close"].to_numpy(dtype=float),
                                     index=[ts.date() for ts in frame["ts"]])
        return out

    def _chosen_strategies(self, plan: RunPlan) -> list[dict[str, Any]]:
        if not plan.strategies:
            raise ValueError("Pick at least one strategy")
        live = {str(s["name"]): s for s in self._strategies()}
        missing = [s.id for s in plan.strategies if s.id not in live]
        if missing:
            raise ValueError("; ".join(f"Strategy {m} is not in the strategy list"
                                       for m in missing))
        return [dict(live[s.id]) for s in plan.strategies]

    def _recorded(self, plan: RunPlan, work: Callable[[str], _T], record: bool = True) -> _T:
        """Run ``work(run_id)`` inside a results row: done, cancelled or failed."""
        if not record:
            return work("")
        run_id = self._results.start_run(plan, datetime.now(timezone.utc))
        status, message = "failed", ""
        try:
            result = work(run_id)
            status = "done"
        except stocks.StepCancelled:
            status = "cancelled"
            raise
        except Exception as exc:
            message = str(exc)
            raise
        finally:
            self._results.finish_run(run_id, status, datetime.now(timezone.utc), message)
        return result


@dataclass(frozen=True)
class SavedReport:
    """One saved run for the Reports table: key numbers of its first variant."""

    run: RunRow
    plan: RunPlan
    trades: int
    net_pnl: float
    return_pct: float
    max_dd_pct: float


@dataclass(frozen=True)
class OpenedRun:
    """A saved run read back for the Inspector and Detail Report (SRD-GUI-031.055)."""

    plan: RunPlan
    daily: DailyList
    signals: pd.DataFrame | None
    results: list[portfolio.VariantResult]
    reports: list[report.Report]


def stocks_text(plan: RunPlan) -> str:
    """Short text for the run's stocks: "S&P 500", the sectors or the names."""
    uni = plan.universe
    if uni.mode == "sector":
        return ", ".join(uni.sectors) or "No sector"
    if uni.mode == "names":
        return ", ".join(uni.names[:5]) + (" …" if len(uni.names) > 5 else "")
    return "S&P 500"


def variant_label(variant: Variant) -> str:
    """"$2,000 · ST_AUTO 100%/100%": capital, then each strategy's allocation and per-trade %."""
    parts = [f"{sid} {alloc:g}%/{per:g}%" for sid, alloc, per in variant.strategies]
    return " · ".join([f"${variant.capital:,.0f}", *parts])
