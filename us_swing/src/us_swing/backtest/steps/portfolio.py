"""
Module: MD-BKT-002.030.M12 — backtest/steps/portfolio.py
Parent SRD: SRD-BKT-002.030

Step 3 · Portfolio: one shared account per variant. Signals of the picked
strategies become trades with the live money rules (per-trade size, strategy
limit, margin), next-open fills with costs, stop / target / end time / exit
condition, a per-day Rex limit and the daily loss stop. Every decision is logged.
"""
from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd

from us_swing.backtest.spec import AccountSpec, CostSpec, RunPlan, Variant
from us_swing.backtest.steps.stocks import Cancel, Progress, StepCancelled, StepRefused, top_n
from us_swing.backtest.store import BacktestStore
from us_swing.core.expr.series import ET

_NS_PER_MIN = 60_000_000_000
TRADE_COLUMNS = ["strategy", "symbol", "direction", "entry_ts", "entry_px", "qty", "exit_ts",
                 "exit_px", "exit_reason", "costs", "net_pnl", "mae", "mfe", "score", "rank"]
LOG_COLUMNS = ["ts", "symbol", "strategy", "decision", "margin_available", "strategy_deployed"]
MONEY_COLUMNS = ["date", "start_capital", "deployed", "margin_min", "margin_close",
                 "open_value", "equity"]

IntArray = npt.NDArray[np.int64]
BoolArray = npt.NDArray[np.bool_]


@dataclass(frozen=True)
class StrategyRules:
    """One strategy's live settings plus this variant's money split."""

    name: str
    sign: int
    intraday: bool
    end_minute: int
    stop_pct: float | None
    target_pct: float | None
    rex_count: int
    alloc_pct: float
    per_trade_pct: float

    @classmethod
    def from_live(cls, cfg: Mapping[str, Any], alloc_pct: float, per_trade_pct: float
                  ) -> StrategyRules:
        hour, minute = str(cfg["end_time"]).split(":")[:2]
        return cls(
            name=str(cfg["name"]),
            sign=-1 if str(cfg.get("direction", "LONG")).upper() == "SHORT" else 1,
            intraday=str(cfg.get("trade_type", "Intraday")) == "Intraday",
            end_minute=int(hour) * 60 + int(minute),
            stop_pct=float(cfg["stoploss_value"]) if cfg.get("stoploss_enabled") else None,
            target_pct=float(cfg["target_value"]) if cfg.get("target_enabled") else None,
            rex_count=int(cfg.get("rex_count", 0)),
            alloc_pct=alloc_pct,
            per_trade_pct=per_trade_pct,
        )


@dataclass(frozen=True)
class VariantResult:
    """Step 3 output of one variant."""

    variant: Variant
    trades: pd.DataFrame
    day_log: pd.DataFrame
    money: pd.DataFrame


def refusals(plan: RunPlan, strategies: Sequence[Mapping[str, Any]],
             signals: pd.DataFrame) -> list[str]:
    """Plain messages for what Step 3 cannot do yet (SRD-BKT-002.036)."""
    errors = []
    pnl_names = set(signals.loc[signals["pnl"].astype(bool), "strategy"]) if len(signals) else set()
    for cfg in strategies:
        name = cfg["name"]
        for part, label in (("stoploss", "stop"), ("target", "target")):
            if cfg.get(f"{part}_enabled") and cfg.get(f"{part}_type") == "trailing":
                errors.append(f"Strategy {name} uses a trailing {label}, which comes in a "
                              f"later phase — set it to Fixed to backtest")
        if name in pnl_names:
            errors.append(f"Strategy {name} uses PNL in a condition, which comes in a later phase")
    if plan.account.grow_with_pnl:
        errors.append("Grow with P&L comes in a later phase — untick it to run")
    return errors


def _ns(values: Any) -> IntArray:
    stamps = pd.DatetimeIndex(values).tz_convert("UTC").tz_localize(None)
    return np.asarray(stamps.to_numpy(dtype="datetime64[ns]").view(np.int64), dtype=np.int64)


class _Bars:
    """One stock's 3m bars keyed by close time."""

    def __init__(self, frame: pd.DataFrame) -> None:
        closes = pd.DatetimeIndex(frame["ts"]).tz_convert("UTC") + pd.Timedelta(minutes=3)
        et = closes.tz_convert(ET)
        self.close_ns = _ns(closes)
        self.open = frame["open"].to_numpy(dtype=np.float64)
        self.high = frame["high"].to_numpy(dtype=np.float64)
        self.low = frame["low"].to_numpy(dtype=np.float64)
        self.close = frame["close"].to_numpy(dtype=np.float64)
        self.minute = np.asarray(et.hour * 60 + et.minute)
        self.day = np.asarray(et.date, dtype="datetime64[D]")
        self.index = {int(ns): i for i, ns in enumerate(self.close_ns)}

    def day_range(self, day: date) -> tuple[int, int]:
        target = np.datetime64(day, "D")
        return (int(np.searchsorted(self.day, target, "left")),
                int(np.searchsorted(self.day, target, "right")))


def _windows(bars: _Bars, rows: pd.DataFrame) -> IntArray:
    """Window start (ns) per bar where a condition is true, else 0."""
    out = np.zeros(len(bars.close_ns), dtype=np.int64)
    if rows.empty:
        return out
    starts, ends = _ns(rows["start"]), _ns(rows["end"])
    for start, end in zip(starts, ends):
        i0 = int(np.searchsorted(bars.close_ns, start, "left"))
        i1 = int(np.searchsorted(bars.close_ns, end, "right"))
        out[i0:i1] = start
    return out


@dataclass
class _Position:
    rules: StrategyRules
    symbol: str
    qty: int
    entry_px: float
    entry_ns: int
    window: int
    score: float
    rank: int
    costs: float
    stop: float | None = None
    target: float | None = None
    best: float = 0.0
    worst: float = 0.0

    @property
    def cost(self) -> float:
        return self.entry_px * self.qty


@dataclass
class _Order:
    kind: str
    rules: StrategyRules
    symbol: str
    reason: str = ""
    window: int = 0
    score: float = 0.0
    rank: int = 0


@dataclass
class _Account:
    """The shared account of one variant while it runs."""

    capital: float
    account: AccountSpec
    costs: CostSpec
    positions: dict[str, _Position] = field(default_factory=dict)
    pending: list[_Order] = field(default_factory=list)
    last: dict[str, float] = field(default_factory=dict)
    realized: float = 0.0
    trades: list[tuple[Any, ...]] = field(default_factory=list)
    log: list[tuple[Any, ...]] = field(default_factory=list)
    logged: set[tuple[str, str, int, str]] = field(default_factory=set)

    def open_cost(self, strategy: str | None = None) -> float:
        return sum(p.cost for p in self.positions.values()
                   if strategy is None or p.rules.name == strategy)

    def equity(self) -> float:
        marks = sum(p.rules.sign * (self.last.get(p.symbol, p.entry_px) - p.entry_px) * p.qty
                    for p in self.positions.values())
        return self.capital + self.realized + marks

    def note(self, ns: int, symbol: str, rules: StrategyRules, decision: str, window: int) -> None:
        key = (rules.name, symbol, window, decision)
        if key in self.logged:
            return
        self.logged.add(key)
        self.log.append((ns, symbol, rules.name, decision, self.capital - self.open_cost(),
                         self.open_cost(rules.name)))

    def close(self, pos: _Position, raw: float, ns: int, reason: str) -> None:
        px = raw * (1 - pos.rules.sign * self.costs.slippage_bps / 10_000)
        costs = pos.costs + self.costs.per_order
        net = pos.rules.sign * (px - pos.entry_px) * pos.qty - costs
        self.realized += net
        mfe = max(0.0, pos.rules.sign * (pos.best - pos.entry_px)) * pos.qty
        mae = max(0.0, pos.rules.sign * (pos.entry_px - pos.worst)) * pos.qty
        self.trades.append((pos.rules.name, pos.symbol, "LONG" if pos.rules.sign > 0 else "SHORT",
                            pos.entry_ns, pos.entry_px, pos.qty, ns, px, reason, costs, net,
                            mae, mfe, pos.score, pos.rank))
        del self.positions[pos.symbol]
        self.pending = [o for o in self.pending
                        if not (o.kind == "exit" and o.symbol == pos.symbol)]

    def enter(self, order: _Order, raw: float, ns: int) -> bool:
        rules = order.rules
        if order.symbol in self.positions:
            self.note(ns, order.symbol, rules, "already_held", order.window)
            return False
        px = raw * (1 + rules.sign * self.costs.slippage_bps / 10_000)
        limit = self.capital * rules.alloc_pct / 100
        qty = math.floor(limit * rules.per_trade_pct / 100 / px) if px > 0 else 0
        if qty < 1:
            self.note(ns, order.symbol, rules, "too_expensive", order.window)
            return False
        if self.open_cost(rules.name) >= limit:
            self.note(ns, order.symbol, rules, "strategy_limit", order.window)
            return False
        qty = min(qty, math.floor(max(0.0, self.capital - self.open_cost()) / px))
        if qty < 1:
            self.note(ns, order.symbol, rules, "no_margin", order.window)
            return False
        pos = _Position(rules, order.symbol, qty, px, ns, order.window, order.score, order.rank,
                        self.costs.per_order, best=raw, worst=raw)
        if rules.stop_pct is not None:
            pos.stop = px * (1 - rules.sign * rules.stop_pct / 100)
        if rules.target_pct is not None:
            pos.target = px * (1 + rules.sign * rules.target_pct / 100)
        self.positions[order.symbol] = pos
        self.note(ns, order.symbol, rules, "entered", order.window)
        return True


def _levels(acc: _Account, pos: _Position, bars: _Bars, k: int) -> None:
    """SRD-BKT-002.035 — stop first, then target; a gap through a level fills at the open."""
    o, hi, lo = bars.open[k], bars.high[k], bars.low[k]
    if pos.rules.sign > 0:
        if pos.stop is not None and lo <= pos.stop:
            acc.close(pos, min(o, pos.stop), int(bars.close_ns[k]), "stop")
        elif pos.target is not None and hi >= pos.target:
            acc.close(pos, max(o, pos.target), int(bars.close_ns[k]), "target")
    elif pos.stop is not None and hi >= pos.stop:
        acc.close(pos, max(o, pos.stop), int(bars.close_ns[k]), "stop")
    elif pos.target is not None and lo <= pos.target:
        acc.close(pos, min(o, pos.target), int(bars.close_ns[k]), "target")


class _Sim:
    """Day loop of one variant (DD-BKT-002.030.D01)."""

    def __init__(self, variant: Variant, rules: dict[str, StrategyRules], plan: RunPlan,
                 picks: dict[date, dict[str, tuple[float, int]]], bars: dict[str, _Bars],
                 entry: dict[tuple[str, str], IntArray],
                 exits: dict[tuple[str, str], BoolArray]) -> None:
        self.acc = _Account(variant.capital, plan.account, plan.costs)
        self.rules, self.picks, self.bars = rules, picks, bars
        self.entry, self.exits = entry, exits
        self.when_full = plan.account.when_full
        self.money: list[tuple[Any, ...]] = []

    def run_day(self, day: date) -> None:
        acc = self.acc
        picks = self.picks.get(day, {})
        names = (set(picks) | set(acc.positions) | {o.symbol for o in acc.pending}) & set(self.bars)
        ranges = {s: self.bars[s].day_range(day) for s in names}
        times = sorted({int(ns) for s, (i0, i1) in ranges.items()
                        for ns in self.bars[s].close_ns[i0:i1]})
        start_equity = acc.equity()
        margin_min = acc.capital - acc.open_cost()
        rex_used: dict[tuple[str, str], int] = defaultdict(int)
        stopped = False
        for t in times:
            here = {s: self.bars[s].index[t] for s in names if t in self.bars[s].index}
            self._fill(here, t, rex_used)
            for s, k in here.items():
                bars = self.bars[s]
                acc.last[s] = float(bars.close[k])
                pos = acc.positions.get(s)
                if pos is not None:
                    pos.best = (max(pos.best, bars.high[k]) if pos.rules.sign > 0
                                else min(pos.best, bars.low[k]))
                    pos.worst = (min(pos.worst, bars.low[k]) if pos.rules.sign > 0
                                 else max(pos.worst, bars.high[k]))
                    _levels(acc, pos, bars, k)
            margin_min = min(margin_min, acc.capital - acc.open_cost())
            loss_pct = acc.account.max_daily_loss_pct
            if (not stopped and loss_pct > 0
                    and acc.equity() - start_equity <= -loss_pct / 100 * start_equity):
                stopped = True
            self._exits_at_close(here, t, ranges)
            self._entries_at_close(here, t, picks, stopped, rex_used)
        for pos in [p for p in acc.positions.values() if p.rules.intraday]:
            i0, i1 = ranges.get(pos.symbol, (0, 0))
            if i1 > i0:
                bars = self.bars[pos.symbol]
                acc.close(pos, float(bars.close[i1 - 1]), int(bars.close_ns[i1 - 1]), "end_time")
        acc.pending = [o for o in acc.pending if not (o.kind == "entry" and o.rules.intraday)]
        deployed = acc.open_cost()
        open_value = sum(acc.last.get(p.symbol, p.entry_px) * p.qty
                         for p in acc.positions.values())
        self.money.append((day, acc.capital, deployed, margin_min, acc.capital - deployed,
                           open_value, acc.equity()))

    def _fill(self, here: dict[str, int], t: int,
              rex_used: dict[tuple[str, str], int]) -> None:
        acc = self.acc
        opened = t - 3 * _NS_PER_MIN
        ready = [o for o in acc.pending if o.symbol in here]
        acc.pending = [o for o in acc.pending if o.symbol not in here]
        for order in sorted(ready, key=lambda o: o.kind != "exit"):
            bars, k = self.bars[order.symbol], here[order.symbol]
            if order.kind == "exit":
                pos = acc.positions.get(order.symbol)
                if pos is not None:
                    acc.close(pos, float(bars.open[k]), opened, order.reason)
            elif acc.enter(order, float(bars.open[k]), opened):
                rex_used[(order.rules.name, order.symbol)] += 1

    def _exits_at_close(self, here: dict[str, int], t: int,
                        ranges: dict[str, tuple[int, int]]) -> None:
        acc = self.acc
        for s, k in here.items():
            pos = acc.positions.get(s)
            if pos is None or any(o.kind == "exit" and o.symbol == s for o in acc.pending):
                continue
            bars = self.bars[s]
            if pos.rules.intraday and bars.minute[k] >= pos.rules.end_minute:
                if k + 1 < ranges[s][1]:
                    acc.pending.append(_Order("exit", pos.rules, s, "end_time"))
                else:
                    acc.close(pos, float(bars.close[k]), t, "end_time")
                continue
            flags = self.exits.get((pos.rules.name, s))
            if flags is not None and flags[k]:
                acc.pending.append(_Order("exit", pos.rules, s, "strategy"))

    def _entries_at_close(self, here: dict[str, int], t: int,
                          picks: dict[str, tuple[float, int]], stopped: bool,
                          rex_used: dict[tuple[str, str], int]) -> None:
        acc = self.acc
        wanted: list[_Order] = []
        for s, k in here.items():
            if s not in picks:
                continue
            score, rank = picks[s]
            for rules in self.rules.values():
                windows = self.entry.get((rules.name, s))
                window = int(windows[k]) if windows is not None else 0
                if window == 0:
                    continue
                pos = acc.positions.get(s)
                if pos is not None and pos.rules.name == rules.name and pos.window == window:
                    continue
                if stopped:
                    acc.note(t, s, rules, "daily_loss_stop", window)
                    continue
                if rex_used[(rules.name, s)] > rules.rex_count:
                    acc.note(t, s, rules, "rex_limit", window)
                    continue
                wanted.append(_Order("entry", rules, s, window=window, score=score, rank=rank))
        if self.when_full == "highest_score":
            wanted.sort(key=lambda o: (-o.score, o.window, o.symbol))
        else:
            wanted.sort(key=lambda o: (o.window, -o.score, o.symbol))
        for order in wanted:
            busy = order.symbol in acc.positions or any(o.symbol == order.symbol
                                                        for o in acc.pending)
            if busy:
                acc.note(t, order.symbol, order.rules, "already_held", order.window)
            else:
                acc.pending.append(order)

    def finish(self, variant: Variant) -> VariantResult:
        acc = self.acc
        for pos in list(acc.positions.values()):
            bars = self.bars[pos.symbol]
            acc.close(pos, float(bars.close[-1]), int(bars.close_ns[-1]), "end_of_test")
        trades = pd.DataFrame(acc.trades, columns=TRADE_COLUMNS)
        log = pd.DataFrame(acc.log, columns=LOG_COLUMNS)
        for frame, cols in ((trades, ("entry_ts", "exit_ts")), (log, ("ts",))):
            for col in cols:
                frame[col] = pd.to_datetime(frame[col].astype("int64"), utc=True)
        return VariantResult(variant, trades, log, pd.DataFrame(self.money, columns=MONEY_COLUMNS))


def picks_by_day(daily: pd.DataFrame, days: Sequence[date], n: int
                 ) -> dict[date, dict[str, tuple[float, int]]]:
    """Day i trades the top-N list made at day i − 1's close."""
    listed = top_n(daily, n)
    by_day: dict[date, dict[str, tuple[float, int]]] = defaultdict(dict)
    for day, symbol, score, rank in zip(listed["date"], listed["symbol"], listed["score"],
                                        listed["rank"]):
        by_day[day][str(symbol)] = (float(score), int(rank))
    ordered = sorted(days)
    return {ordered[i]: by_day.get(ordered[i - 1], {}) for i in range(1, len(ordered))}


def run_portfolio(
    plan: RunPlan,
    strategies: Sequence[Mapping[str, Any]],
    daily: pd.DataFrame,
    days: Sequence[date],
    signals: pd.DataFrame,
    store: BacktestStore,
    *,
    progress: Progress | None = None,
    cancel: Cancel | None = None,
) -> list[VariantResult]:
    """Run every variant of the plan (SRD-BKT-002.030–.038).

    Raises:
        StepRefused: trailing levels, PNL conditions or Grow with P&L.
        StepCancelled: ``cancel`` returned true.
    """
    errors = refusals(plan, strategies, signals)
    if errors:
        raise StepRefused("; ".join(errors))
    report = progress or (lambda _done, _total: None)
    stop: Callable[[], bool] = cancel or (lambda: False)
    live = {str(cfg["name"]): cfg for cfg in strategies}
    picks = picks_by_day(daily, days, plan.screener.top_n)
    symbols = sorted({s for p in picks.values() for s in p})
    bars = {}
    for sym in symbols:
        frame = store.read(sym, "3m", plan.period.start, plan.period.end)
        if not frame.empty:
            bars[sym] = _Bars(frame)
    entry: dict[tuple[str, str], IntArray] = {}
    exits: dict[tuple[str, str], BoolArray] = {}
    for keys, rows in signals.groupby(["strategy", "symbol"]):
        name, sym = str(keys[0]), str(keys[1])
        if sym in bars and name in live:
            entry[(name, sym)] = _windows(bars[sym], rows[rows["kind"] == "entry"])
            exits[(name, sym)] = _windows(bars[sym], rows[rows["kind"] == "exit"]) != 0
    variants = plan.variants()
    ordered = sorted(picks)
    total = len(variants) * len(ordered)
    report(0, total)
    results = []
    for vi, variant in enumerate(variants):
        rules = {name: StrategyRules.from_live(live[name], alloc, per)
                 for name, alloc, per in variant.strategies}
        sim = _Sim(variant, rules, plan, picks, bars, entry, exits)
        for di, day in enumerate(ordered, start=1):
            sim.run_day(day)
            report(vi * len(ordered) + di, total)
            if stop():
                raise StepCancelled
        results.append(sim.finish(variant))
    return results
