"""
Module: MD-MKT-019.005.M03 — market/card_replay.py
Parent SRD: SRD-MKT-019.005
Also: SRD-MKT-019.006 (baseline), SRD-MKT-019.007 (score and pass rule)

Replays a checked card recipe on all Backtest Data daily bars of the S&P 500 members. A
signal day needs every entry block to pass on the last 260 bars; each signal becomes a paper
trade with the pick results rule (fill within 5 days, 2R target, 10-day exit). Code alone
scores the trades and decides pass or fail.
"""
from __future__ import annotations

import math
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from us_swing.core.indicator_rules import BarArrays, Condition, Rule, RuleContext, evaluate_rule
from us_swing.core.price_patterns import PatternRule, evaluate_pattern
from us_swing.market.candles import BENCHMARK, member_sectors
from us_swing.market.card_recipe import Recipe
from us_swing.market.pick_results import ENTRY_DAYS, HOLD_DAYS, Bar, paper_result
from us_swing.market.proof_data import BACKTEST_ROOT, daily_symbols, read_daily

WARMUP = 200
WINDOW = 260
BASE_EVERY = 10
ATR_DAYS = 14
TARGET_R = 2.0
MIN_TRADES = 30
MIN_AVG_R = 0.2
TIME_LIMIT_S = 600.0
_COUNTED = ("stop", "target", "time")


class TooSlow(Exception):
    """The replay ran past its time limit."""


@dataclass(frozen=True)
class Stock:
    """One stock's daily bars, oldest first."""

    symbol: str
    days: tuple[str, ...]
    arrays: BarArrays


@dataclass(frozen=True)
class Trade:
    """One paper trade: stock, signal day and R."""

    symbol: str
    day: str
    r: float


@dataclass(frozen=True)
class Score:
    """The numbers of one test; ``passed`` is decided by code."""

    trades: int
    win_rate: float
    avg_r: float
    worst_run: int
    base_trades: int
    base_r: float
    first_day: str
    last_day: str
    passed: bool


def load_data(root: Path = BACKTEST_ROOT,
              members: Callable[[set[str]], set[str]] | None = None) -> list[Stock]:
    """Daily bars of the S&P 500 members in Backtest Data; empty when there are none."""
    available = daily_symbols(root)
    chosen = (members(available) if members is not None
              else set(member_sectors(available).sectors))
    chosen.discard(BENCHMARK)
    if not chosen:
        return []
    pb = read_daily(sorted(chosen), root)
    if pb is None:
        return []
    out: list[Stock] = []
    for sym in sorted(pb.bars.closes.columns):
        frame = pd.DataFrame({"open": pb.opens[sym], "high": pb.bars.highs[sym],
                              "low": pb.bars.lows[sym], "close": pb.bars.closes[sym],
                              "volume": pb.bars.volumes[sym]}).dropna()
        if len(frame) <= WARMUP + 1:
            continue
        arrays = BarArrays(*(frame[c].to_numpy(dtype=np.float64)
                             for c in ("open", "high", "low", "close", "volume")))
        out.append(Stock(sym, tuple(d.strftime("%Y-%m-%d") for d in frame.index), arrays))
    return out


def _window(arrays: BarArrays, end: int) -> BarArrays:
    start = max(0, end + 1 - WINDOW)
    return BarArrays(arrays.open[start:end + 1], arrays.high[start:end + 1],
                     arrays.low[start:end + 1], arrays.close[start:end + 1],
                     arrays.volume[start:end + 1])


def _rules(recipe: Recipe) -> tuple[list[Rule], list[PatternRule]]:
    rules = [Rule(b.id, Condition(b.condition), b.value, b.to, dict(b.params))
             for b in recipe.indicators]
    return rules, [PatternRule(p.id, dict(p.params)) for p in recipe.patterns]


def _signal(symbol: str, window: BarArrays, rules: Sequence[Rule],
            patterns: Sequence[PatternRule], ctx: RuleContext) -> bool:
    return (all(evaluate_rule(r, symbol, window, ctx)[0] for r in rules)
            and all(evaluate_pattern(p, window) for p in patterns))


def _atr(arrays: BarArrays, i: int) -> float:
    lo = max(1, i + 1 - ATR_DAYS)
    prev = arrays.close[lo - 1:i]
    hi, low = arrays.high[lo:i + 1], arrays.low[lo:i + 1]
    tr = np.maximum(hi - low, np.maximum(np.abs(hi - prev), np.abs(low - prev)))
    return float(tr.mean()) if len(tr) else math.nan


def levels(recipe: Recipe, arrays: BarArrays, i: int) -> tuple[float, float, float] | None:
    """Trigger, stop and 2R target for a signal on day ``i``, or ``None`` when they do not fit."""
    long = recipe.side == "long"
    if recipe.entry == "next_open":
        trigger = float(arrays.open[i + 1])
    else:
        trigger = float(arrays.high[i] if long else arrays.low[i])
    kind, n = recipe.stop.kind, recipe.stop.n
    if kind == "signal_bar":
        stop = float(arrays.low[i] if long else arrays.high[i])
    elif kind == "n_day":
        lo = max(0, i + 1 - int(n))
        stop = float(arrays.low[lo:i + 1].min() if long else arrays.high[lo:i + 1].max())
    elif kind == "atr":
        stop = trigger - n * _atr(arrays, i) if long else trigger + n * _atr(arrays, i)
    else:
        stop = trigger * (1 - n / 100) if long else trigger * (1 + n / 100)
    risk = trigger - stop if long else stop - trigger
    if not math.isfinite(risk) or risk <= 0:
        return None
    return trigger, stop, trigger + TARGET_R * risk if long else trigger - TARGET_R * risk


def _trade(recipe: Recipe, stock: Stock, i: int) -> tuple[Trade, int] | None:
    found = levels(recipe, stock.arrays, i)
    if found is None:
        return None
    a = stock.arrays
    end = min(len(stock.days), i + 1 + ENTRY_DAYS + HOLD_DAYS)
    bars = [Bar(stock.days[j], float(a.high[j]), float(a.low[j]), float(a.close[j]))
            for j in range(i + 1, end)]
    result = paper_result(recipe.side, *found, bars)
    if result is None or result.status not in _COUNTED or result.r is None:
        return None
    exit_at = stock.days.index(result.exit_day) if result.exit_day else i
    return Trade(stock.symbol, stock.days[i], float(result.r)), exit_at


def replay(recipe: Recipe, data: Sequence[Stock], limit_s: float = TIME_LIMIT_S
           ) -> list[Trade]:
    """Trades of a checked recipe, one open trade per stock at a time.

    Raises:
        TooSlow: The replay ran longer than ``limit_s`` seconds.
    """
    rules, patterns = _rules(recipe)
    ctx = RuleContext()
    trades: list[Trade] = []
    deadline = time.monotonic() + limit_s
    for stock in data:
        if time.monotonic() > deadline:
            raise TooSlow
        i, last = WARMUP, len(stock.days) - 2
        while i <= last:
            if _signal(stock.symbol, _window(stock.arrays, i), rules, patterns, ctx):
                done = _trade(recipe, stock, i)
                if done is not None:
                    trades.append(done[0])
                    i = max(i, done[1]) + 1
                    continue
            i += 1
    return trades


def baseline(recipe: Recipe, data: Sequence[Stock]) -> list[Trade]:
    """Trades on every 10th stock-day with the recipe's entry type, stop and exit only."""
    trades: list[Trade] = []
    for stock in data:
        for i in range(WARMUP, len(stock.days) - 1, BASE_EVERY):
            done = _trade(recipe, stock, i)
            if done is not None:
                trades.append(done[0])
    return trades


def worst_run(rs: Sequence[float]) -> int:
    """The longest run of losing trades."""
    best = run = 0
    for r in rs:
        run = run + 1 if r < 0 else 0
        best = max(best, run)
    return best


def score(trades: Sequence[Trade], base: Sequence[Trade]) -> Score:
    """Score the trades against the baseline; pass needs 30+ trades and avg R above 0.2 and base."""
    ordered = sorted(trades, key=lambda t: t.day)
    rs = [t.r for t in ordered]
    n = len(rs)
    avg = round(sum(rs) / n, 3) if n else 0.0
    base_r = round(sum(t.r for t in base) / len(base), 3) if base else 0.0
    passed = n >= MIN_TRADES and avg > MIN_AVG_R and avg > base_r
    return Score(n, sum(1 for r in rs if r > 0) / n if n else 0.0, avg,
                 worst_run(rs), len(base), base_r,
                 ordered[0].day if n else "", ordered[-1].day if n else "", passed)


def score_text(s: Score) -> str:
    """The score as a short table and the pass line."""
    lines = [f"Trades: {s.trades:,} ({s.first_day or '-'} to {s.last_day or '-'})",
             f"Win rate: {s.win_rate:.0%}", f"Average R: {s.avg_r:+.2f}",
             f"Worst losing run: {s.worst_run}",
             f"Baseline: {s.base_trades:,} trades, {s.base_r:+.2f}R",
             f"Result: {'pass' if s.passed else 'fail'} (needs {MIN_TRADES}+ trades, average "
             f"R above {MIN_AVG_R:+.2f} and above the baseline)"]
    return "\n".join(lines)
