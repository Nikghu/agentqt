"""
Module: MD-MKT-003.005.M04 — market/score.py
Parent SRD: SRD-MKT-003.005

Swing Readiness Score per stock, day and side, the extended penalty, the daily idea
and Watch lists, and plain-word reasons (DD-MKT-003.001.D01).
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from us_swing.market.flow import MIN_DOLLAR_VOLUME, dollar_volume, money_flow, roll
from us_swing.market.setups import Bars, SetupResult, long_setups, short_setups, sma

SIDES = ("long", "short")
NEWS_SCALE = 100 / 90
MIN_SCORE = 60.0
LIST_SIZE = 10
EXTENDED = 0.08
EXTENDED_PENALTY = 10.0
EARNINGS_DAYS = 5
HISTORY_ROWS = 460
NO_SETUP = "No setup"
_QUADRANT = {
    "long": {"Leading": 1.0, "Improving": 0.75, "Weakening": 0.25, "Lagging": 0.0},
    "short": {"Lagging": 1.0, "Weakening": 0.75, "Improving": 0.25, "Leading": 0.0},
}
_REGIME = {
    "long": {"Uptrend": 1.0, "Choppy": 0.5, "Downtrend": 0.0},
    "short": {"Downtrend": 1.0, "Choppy": 0.5, "Uptrend": 0.0},
}
_AGAINST = {"long": "Downtrend", "short": "Uptrend"}
WEIGHTS = {"rs": 20.0, "flow": 20.0, "setup": 20.0, "sector": 15.0, "regime": 15.0}


@dataclass(frozen=True)
class MarketInputs:
    """Everything the score needs, aligned to SPY's days (index) and members (columns)."""

    bars: Bars
    spy: pd.Series
    ratings: pd.DataFrame
    sector_of: Mapping[str, str]
    quadrant: pd.DataFrame
    sector_rank: pd.DataFrame
    regime: pd.Series


@dataclass(frozen=True)
class Idea:
    """One listed or Watch idea for a day and side."""

    symbol: str
    side: str
    status: str
    rank: int
    score: float
    sector: str
    setup: str
    trigger: float
    stop: float
    reasons: tuple[str, ...]


def _by_sector(frame: pd.DataFrame, index: pd.Index, cols: list[str],
               sector_of: Mapping[str, str]) -> pd.DataFrame:
    out = frame.reindex(index=index).reindex(columns=[sector_of[c] for c in cols])
    out.columns = pd.Index(cols)
    return out


def readiness_score(
    fractions: Mapping[str, pd.DataFrame], penalty: pd.DataFrame
) -> pd.DataFrame:
    """Return the 0–100 score from the five 0–1 parts and the penalty points.

    Parts are weighted by ``WEIGHTS`` (90 points), scaled by 100/90 while news is not
    scored, then the penalty is taken off; the score never goes below 0.
    """
    raw = sum((WEIGHTS[k] * v for k, v in fractions.items()), 0.0 * penalty)
    return (raw * NEWS_SCALE - penalty).clip(lower=0.0).round(1)


def _side_frames(bars: Bars, side: str, setups: SetupResult,
                 shared: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    c = bars.closes
    long = side == "long"
    rating = shared["rating"]
    rs_extreme = shared["rs_high"] if long else shared["rs_low"]
    rs = 0.75 * (rating if long else 100 - rating) / 99 + 0.25 * rs_extreme.astype(float)
    flow = shared["flow"] if long else 1 - shared["flow"]
    rank = shared["sector_rank"]
    sector = (0.7 * shared["quadrant"].map(_QUADRANT[side].get).astype(float)
              + 0.3 * ((11 - rank) if long else (rank - 1)) / 10)
    regime = shared["regime"].map(_REGIME[side].get).astype(float)
    has_setup = setups.name.notna()
    hi20, lo20 = roll(bars.highs, 20, "max"), roll(bars.lows, 20, "min")
    trigger = setups.trigger.where(has_setup, hi20 if long else lo20)
    stop = setups.stop.where(has_setup, lo20 if long else hi20)
    sma20 = sma(c, 20)
    extended = (c > (1 + EXTENDED) * sma20) if long else (c < (1 - EXTENDED) * sma20)
    penalty = extended.astype(float) * EXTENDED_PENALTY
    fractions = {"rs": rs, "flow": flow, "setup": setups.tightness, "sector": sector,
                 "regime": regime}
    parts = {f"{k}_part": WEIGHTS[k] * v for k, v in fractions.items()}
    score = readiness_score(fractions, penalty)
    valid = (shared["liquid"] & rating.notna() & flow.notna() & sector.notna()
             & regime.notna() & c.notna())
    return {"score": score.where(valid), **parts, "penalty": penalty,
            "setup": setups.name.where(has_setup, NO_SETUP), "trigger": trigger,
            "stop": stop, "extended": c / sma20 - 1}


def score_frame(inp: MarketInputs, days: Sequence[pd.Timestamp]) -> pd.DataFrame:
    """Return one row per scored (date, symbol, side) for ``days``.

    Columns: score, the five parts in points, penalty, setup, trigger, stop and the
    facts used for reasons (rating, rs_extreme, acc, dist, sector, quadrant,
    sector_rank, regime, close, extended).
    """
    picked = pd.DatetimeIndex(list(days))
    start = max(0, int(inp.bars.closes.index.searchsorted(picked[0])) - HISTORY_ROWS)
    b = Bars(*(f.iloc[start:] for f in (inp.bars.closes, inp.bars.highs, inp.bars.lows,
                                        inp.bars.volumes)))
    c = b.closes
    cols = list(c.columns)
    flow, acc, dist = money_flow(c, b.highs, b.lows, b.volumes)
    rs_line = c.div(inp.spy.reindex(c.index), axis=0)
    shared = {
        "rating": inp.ratings.reindex(index=c.index, columns=cols).astype(float),
        "rs_high": rs_line >= roll(rs_line, 63, "max"),
        "rs_low": rs_line <= roll(rs_line, 63, "min"),
        "flow": flow,
        "liquid": dollar_volume(c, b.volumes) >= MIN_DOLLAR_VOLUME,
        "quadrant": _by_sector(inp.quadrant, c.index, cols, inp.sector_of),
        "sector_rank": _by_sector(inp.sector_rank, c.index, cols, inp.sector_of).astype(float),
        "regime": pd.DataFrame(np.repeat(inp.regime.reindex(c.index).to_numpy()[:, None],
                                         len(cols), axis=1), index=c.index, columns=cols),
    }
    facts = {"rating": shared["rating"], "acc": acc, "dist": dist, "close": c,
             "quadrant": shared["quadrant"], "sector_rank": shared["sector_rank"],
             "regime": shared["regime"]}
    out: list[pd.DataFrame] = []
    for side, setups in (("long", long_setups(b)), ("short", short_setups(b))):
        frames = {**_side_frames(b, side, setups, shared), **facts,
                  "rs_extreme": shared["rs_high" if side == "long" else "rs_low"]}
        data = {k: f.loc[picked].to_numpy().ravel() for k, f in frames.items()}
        index = pd.MultiIndex.from_product([picked, cols], names=["date", "symbol"])
        table = pd.DataFrame(data, index=index)
        table["sector"] = np.tile([inp.sector_of[s] for s in cols], len(picked))
        table["side"] = side
        out.append(table[table["score"].notna()])
    return pd.concat(out).set_index("side", append=True)


def _earnings_note(symbol: str, earnings: Mapping[str, date | None] | None,
                   data_day: date) -> str | None:
    if earnings is None or symbol not in earnings:
        return None
    when = earnings[symbol]
    if when is None:
        return "Earnings not checked"
    if when < data_day:
        return None
    n = int(np.busday_count(data_day, when))
    if n > EARNINGS_DAYS:
        return None
    return "Earnings today" if n == 0 else f"Earnings in {n} day{'s' if n > 1 else ''}"


def _reasons(row: Mapping[Any, Any], side: str, notes: list[str]) -> tuple[str, ...]:
    long = side == "long"
    out = list(notes)
    if row["penalty"] > 0:
        out.append(f"{abs(row['extended']) * 100:.1f}% {'above' if long else 'below'} "
                   "the 20-day average")
    rating = int(row["rating"])
    if (rating >= 70 if long else rating <= 30) or row["rs_extreme"]:
        line = f", RS line at a 3-month {'high' if long else 'low'}" if row["rs_extreme"] else ""
        out.append(f"RS rating {rating}{line}")
    acc, dist = int(row["acc"]), int(row["dist"])
    if (acc > dist) if long else (dist > acc):
        out.append(f"{acc} accumulation and {dist} distribution days in 25 sessions")
    if _QUADRANT[side].get(str(row["quadrant"]), 0.0) >= 0.75:
        out.append(f"{row['sector']} sector {str(row['quadrant']).lower()}, "
                   f"rank {int(row['sector_rank'])}")
    if row["setup"] != NO_SETUP:
        gap = abs(row["trigger"] - row["close"]) / row["close"] * 100
        where = (f"{gap:.1f}% {'below' if long else 'above'} the trigger" if gap >= 0.05
                 else "at the trigger")
        out.append(f"{row['setup']}, {where}")
    if _REGIME[side].get(str(row["regime"])) == 1.0:
        out.append(f"Regime {row['regime']}")
    return tuple(out[:5])


def pick_ideas(day: pd.DataFrame, side: str, data_day: date,
               earnings: Mapping[str, date | None] | None = None) -> list[Idea]:
    """Return the listed and Watch ideas of one day and side.

    Args:
        day: Rows of ``score_frame`` for one date and side, indexed by symbol.
        side: ``long`` or ``short``.
        data_day: The candle day being scored.
        earnings: Next earnings date by symbol (``None`` value = fetch failed); only
            given for the latest day.
    """
    ranked = day[day["score"] >= MIN_SCORE].reset_index()
    ranked = ranked.sort_values(["score", "symbol"], ascending=[False, True])
    ideas: list[Idea] = []
    listed = watched = 0
    for row in ranked.to_dict("records"):
        notes = [n for n in (_earnings_note(row["symbol"], earnings, data_day),) if n]
        if row["regime"] == _AGAINST[side]:
            notes.append(f"Against the {row['regime']}")
        watch = any(n != "Earnings not checked" for n in notes)
        if not watch and listed >= LIST_SIZE:
            continue
        if watch:
            watched += 1
        else:
            listed += 1
        ideas.append(Idea(
            str(row["symbol"]), side, "watch" if watch else "list",
            watched if watch else listed, float(row["score"]), str(row["sector"]),
            str(row["setup"]), float(row["trigger"]), float(row["stop"]),
            _reasons(row, side, notes),
        ))
    return ideas
