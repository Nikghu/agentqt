"""
Module: MD-MKT-015.004.M03 — market/tuning_replay.py
Parent SRD: SRD-MKT-015.004
Also: SRD-MKT-015.006 (result rows and table), SRD-MKT-015.007 (gain rule)

Replays one desk setup on the last 5 years of Backtest Data daily bars with tested knob
values, and turns each match into a paper trade with the pick results rule: entry at the
trigger, the setup stop, a 2R target and a 10-day exit. Code alone decides the gain.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd

from us_swing.market.candles import BENCHMARK, member_sectors
from us_swing.market.pick_results import ENTRY_DAYS, HOLD_DAYS, Bar, paper_result
from us_swing.market.proof_data import BACKTEST_ROOT, daily_symbols, read_daily
from us_swing.market.setup_knobs import side_of
from us_swing.market.setups import Bars, long_candidates, short_candidates

YEARS = 5
TARGET_R = 2.0
MIN_TRADES = 100
MIN_GAIN = 0.05
CLOSED = ("stop", "target", "time")
Universe = Callable[[], list[tuple[str, str, str]]]
Floats = npt.NDArray[np.float64]


@dataclass(frozen=True)
class Row:
    """Result of the baseline or one variant."""

    label: str
    changes: dict[str, float] = field(default_factory=dict)
    trades: int = 0
    win: float = 0.0
    exp_r: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Plain dict for the ticket state."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Row:
        """Read a row back from the ticket state."""
        return cls(str(data["label"]), {str(k): float(v) for k, v in data["changes"].items()},
                   int(data["trades"]), float(data["win"]), float(data["exp_r"]))


def row_from_r(label: str, changes: Mapping[str, float], rs: Sequence[float]) -> Row:
    """Build a row from the R of each closed trade."""
    if not rs:
        return Row(label, dict(changes))
    wins = sum(1 for r in rs if r > 0)
    return Row(label, dict(changes), len(rs), round(wins / len(rs), 4),
               round(sum(rs) / len(rs), 4))


def load_bars(root: Path = BACKTEST_ROOT, universe: Universe | None = None) -> Bars | None:
    """Daily bars of the S&P 500 members aligned to SPY's days, or ``None`` with no data."""
    available = daily_symbols(root)
    members = member_sectors(available, universe)
    if BENCHMARK not in available or not members.sectors:
        return None
    pb = read_daily([*members.sectors, BENCHMARK], root)
    if pb is None or BENCHMARK not in pb.bars.closes.columns:
        return None
    spy = pb.bars.closes[BENCHMARK].dropna()
    cols = [s for s in members.sectors if s in pb.bars.closes.columns]
    if spy.empty or not cols:
        return None

    def align(frame: pd.DataFrame) -> pd.DataFrame:
        return frame[cols].reindex(spy.index)

    return Bars(align(pb.bars.closes), align(pb.bars.highs), align(pb.bars.lows),
                align(pb.bars.volumes))


def setup_frames(bars: Bars, setup: str, changes: Mapping[str, float]
                 ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Match, trigger and stop frames of one setup with the tested values."""
    values = {setup: dict(changes)}
    make = long_candidates if side_of(setup) == "long" else short_candidates
    for name, match, trigger, stop in make(bars, values):
        if name == setup:
            return match, trigger, stop
    raise ValueError(f"unknown desk setup {setup}")


def _target(side: str, trigger: float, stop: float) -> float:
    risk = abs(trigger - stop)
    return trigger + TARGET_R * risk if side == "long" else trigger - TARGET_R * risk


def _stock_r(side: str, days: Sequence[str], highs: Floats, lows: Floats, closes: Floats,
             starts: npt.NDArray[np.intp], triggers: Floats, stops: Floats) -> list[float]:
    """R of each closed trade of one stock; the stock is busy while a trade runs."""
    rs: list[float] = []
    free = 0
    for i in starts:
        if i < free:
            continue
        span = [j for j in range(i + 1, min(i + 1 + ENTRY_DAYS + HOLD_DAYS, len(days)))
                if not (math.isnan(highs[j]) or math.isnan(lows[j]) or math.isnan(closes[j]))]
        after = [Bar(days[j], float(highs[j]), float(lows[j]), float(closes[j])) for j in span]
        trigger, stop = float(triggers[i]), float(stops[i])
        result = paper_result(side, trigger, stop, _target(side, trigger, stop), after)
        if result is None:
            continue
        if result.status in CLOSED and result.r is not None:
            rs.append(result.r)
            free = span[[b.day for b in after].index(str(result.exit_day))] + 1
        elif result.status == "no_fill":
            free = i + ENTRY_DAYS + 1
        else:
            break
    return rs


def trade_rs(bars: Bars, setup: str, changes: Mapping[str, float]) -> list[float]:
    """R of every closed paper trade of ``setup`` in the last 5 years of ``bars``."""
    match, trigger, stop = setup_frames(bars, setup, changes)
    index = bars.closes.index
    if len(index) == 0:
        return []
    first = index[-1] - pd.DateOffset(years=YEARS)
    in_window = np.asarray(index > first)
    days = [pd.Timestamp(d).date().isoformat() for d in index]
    side = side_of(setup)
    rs: list[float] = []
    for col in bars.closes.columns:
        trig = trigger[col].to_numpy(dtype=float)
        stp = stop[col].to_numpy(dtype=float)
        ok = (match[col].fillna(False).to_numpy(dtype=bool) & in_window
              & ~np.isnan(trig) & ~np.isnan(stp))
        starts = np.flatnonzero(ok)
        if starts.size == 0:
            continue
        rs += _stock_r(side, days, bars.highs[col].to_numpy(dtype=float),
                       bars.lows[col].to_numpy(dtype=float),
                       bars.closes[col].to_numpy(dtype=float), starts, trig, stp)
    return rs


def replay_setup(setup: str, changes: Mapping[str, float], label: str,
                 bars: Bars | None) -> Row | None:
    """Row of one setup with the tested values, or ``None`` when there are no bars."""
    if bars is None:
        return None
    return row_from_r(label, changes, trade_rs(bars, setup, changes))


def _changes_text(changes: Mapping[str, float]) -> str:
    return ", ".join(f"{k} {v:g}" for k, v in changes.items()) or "today's values"


def row_text(row: Row, base: Row | None = None) -> str:
    """One line: label, changes, trades, win rate, expectancy and change against base."""
    text = (f"{row.label} ({_changes_text(row.changes)}): {row.trades:,} trades, "
            f"win {row.win * 100:.0f}%, {row.exp_r:+.2f}R")
    if base is not None and row.label != base.label:
        text += f", change {row.exp_r - base.exp_r:+.2f}R"
    return text


def table_text(rows: Sequence[Row]) -> str:
    """The result table, baseline first."""
    base = rows[0] if rows else None
    return "\n".join(row_text(r, base) for r in rows)


def gain(rows: Sequence[Row]) -> Row | None:
    """The best variant when it beats the baseline by 0.05R on 100 or more trades."""
    if len(rows) < 2:
        return None
    base = rows[0]
    passed = [r for r in rows[1:]
              if r.trades >= MIN_TRADES and r.exp_r - base.exp_r >= MIN_GAIN - 1e-9]
    return max(passed, key=lambda r: r.exp_r) if passed else None
