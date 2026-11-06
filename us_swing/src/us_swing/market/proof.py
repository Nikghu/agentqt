"""
Module: MD-MKT-004.002.M02 — market/proof.py
Parent SRD: SRD-MKT-004.002

Score proof on past data: replays the P1–P3 rules on the Backtest Data daily candles,
measures 5, 10 and 20-day forward returns per side, groups them by score band, setup and
idea status, gives each side a pass or fail, and stores and prints the result.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from us_swing.core.desk_contract import desk_home
from us_swing.market.candles import BENCHMARK, member_sectors
from us_swing.market.proof_data import (
    BACKTEST_ROOT,
    ProofBars,
    daily_symbols,
    history_years,
    read_daily,
)
from us_swing.market.regime import averages, regime_series, volatility_series
from us_swing.market.rs import rs_scores, rs_table
from us_swing.market.score import NO_SETUP, SIDES, MarketInputs, pick_ideas, score_frame
from us_swing.market.sectors import sector_lines, sector_table
from us_swing.market.setups import Bars
from us_swing.market.step import MIN_COVERAGE
from us_swing.market.store import MarketStore, ProofRunRow, ProofStatRow

log = logging.getLogger(__name__)

HORIZONS = (5, 10, 20)
PASS_HORIZON = 10
TOP_SCORE = 70.0
LOW_SCORE = 40.0
MIN_SAMPLES = 100
FULL_YEARS = 5.0
CHUNK_DAYS = 250
BANDS = ("under 40", "40-50", "50-60", "60-70", "70-80", "80+")
_EDGES = (-np.inf, 40.0, 50.0, 60.0, 70.0, 80.0, np.inf)
STATUSES = ("list", "watch", "none")
PASS, FAIL, THIN = "pass", "fail", "not enough data"
_READY_COLUMNS = ["rs_ratio", "rs_momentum", "rel_6m"]


def _inputs(pb: ProofBars, sector_of: dict[str, str]) -> tuple[MarketInputs, pd.DataFrame]:
    """Return the score inputs aligned to SPY's days, and the SPY opens and closes."""
    spy = pb.bars.closes[BENCHMARK].dropna()
    cols = [s for s in sector_of if s in pb.bars.closes.columns]

    def align(frame: pd.DataFrame) -> pd.DataFrame:
        return frame[cols].reindex(spy.index)

    closes = align(pb.bars.closes)
    members = {s: sector_of[s] for s in cols}
    regime = pd.concat([regime_series(spy).rename("regime"), volatility_series(spy),
                        averages(spy)], axis=1).dropna(subset=["regime", "volatility",
                                                               "sma200"])
    lines, _ = sector_lines(closes, members)
    sectors = sector_table(lines, spy).dropna(subset=_READY_COLUMNS)
    ratings = rs_table(rs_scores(closes), members)["rs_rating"].unstack("symbol")
    inp = MarketInputs(
        Bars(closes, align(pb.bars.highs), align(pb.bars.lows), align(pb.bars.volumes)),
        spy, ratings, members, sectors["quadrant"].unstack("sector"),
        sectors["rank"].unstack("sector"), regime["regime"],
    )
    spy_bars = pd.DataFrame({"open": pb.opens[BENCHMARK].reindex(spy.index), "close": spy})
    return inp, spy_bars


def _ready_days(inp: MarketInputs, listed: int) -> list[pd.Timestamp]:
    index = inp.bars.closes.index
    ready = (set(index) & set(inp.regime.index) & set(inp.quadrant.index)
             & set(inp.ratings.index))
    coverage = inp.bars.closes.notna().sum(axis=1)
    return [ts for ts in sorted(ready) if coverage.loc[ts] >= MIN_COVERAGE * listed]


def replay(inp: MarketInputs, days: list[pd.Timestamp]) -> pd.DataFrame:
    """Return score, setup and status per (date, symbol, side) for ``days``.

    Status is ``list`` or ``watch`` as the desk would have picked that day (no earnings
    dates are known for past days), else ``none``.
    """
    out: list[pd.DataFrame] = []
    for start in range(0, len(days), CHUNK_DAYS):
        table = score_frame(inp, days[start:start + CHUNK_DAYS])
        status: dict[tuple[object, str, str], str] = {}
        for (ts, side), group in table.groupby(level=["date", "side"], sort=True):
            day = pd.Timestamp(str(ts)).date()
            for idea in pick_ideas(group.droplevel(["date", "side"]), str(side), day, None):
                status[(ts, idea.symbol, str(side))] = idea.status
        part = table[["score", "setup"]].copy()
        part["setup"] = part["setup"].where(part["setup"].notna(), NO_SETUP).astype(str)
        part["status"] = [status.get(key, "none") for key in table.index]
        out.append(part)
    if not out:
        return pd.DataFrame(columns=["score", "setup", "status"])
    return pd.concat(out)


def forward_returns(scores: pd.DataFrame, opens: pd.DataFrame, closes: pd.DataFrame,
                    spy_bars: pd.DataFrame) -> pd.DataFrame:
    """Add ``ret_h`` and ``vs_h`` per horizon: entry at the next open, exit at the close.

    ``opens`` and ``closes`` must be aligned to SPY's days. Short returns are the negative
    of the long ones; a missing entry or exit bar gives NaN.
    """
    out = scores.copy()
    rows = closes.index.get_indexer(scores.index.get_level_values("date"))
    cols = closes.columns.get_indexer(scores.index.get_level_values("symbol"))
    sign = np.where(scores.index.get_level_values("side") == "short", -1.0, 1.0)
    entry = opens.shift(-1).to_numpy()
    spy_entry = spy_bars["open"].shift(-1)
    for h in HORIZONS:
        r = (closes.shift(-h).to_numpy() / entry - 1.0)[rows, cols]
        spy_r = (spy_bars["close"].shift(-h) / spy_entry - 1.0).to_numpy()[rows]
        out[f"ret_{h}"] = sign * r
        out[f"vs_{h}"] = sign * (r - spy_r)
    return out


def _groups(frame: pd.DataFrame) -> dict[str, pd.Series]:
    band = pd.cut(frame["score"], list(_EDGES), labels=list(BANDS), right=False)
    return {"band": band.astype(str), "setup": frame["setup"], "status": frame["status"]}


def group_stats(frame: pd.DataFrame) -> list[ProofStatRow]:
    """Return count, days, win rate and averages per side, group kind, group and horizon."""
    data = frame.reset_index()
    rows: list[ProofStatRow] = []
    for kind, key in _groups(frame).items():
        data["grp"] = key.to_numpy()
        for h in HORIZONS:
            ok = data[data[f"ret_{h}"].notna() & data[f"vs_{h}"].notna()]
            agg = ok.groupby(["side", "grp"]).agg(
                n=(f"ret_{h}", "size"), days=("date", "nunique"),
                win_rate=(f"ret_{h}", lambda x: float((x > 0).mean())),
                avg_ret=(f"ret_{h}", "mean"), avg_vs_spy=(f"vs_{h}", "mean"))
            rows.extend(
                ProofStatRow(str(side), kind, str(grp), h, int(n), int(d), float(w), float(a),
                             float(v))
                for (side, grp), n, d, w, a, v in agg.itertuples(name=None))
    return rows


def verdict(frame: pd.DataFrame, side: str) -> tuple[str, float | None, float | None]:
    """Return pass, fail or not enough data for ``side``, with the 70+ and under-40 averages.

    A side passes when, at 10 days, stocks scoring 70+ beat SPY on average and beat
    stocks scoring under 40; each group needs at least 100 stock-days.
    """
    col = f"vs_{PASS_HORIZON}"
    rows = frame[(frame.index.get_level_values("side") == side) & frame[col].notna()
                 & frame[f"ret_{PASS_HORIZON}"].notna()]
    top = rows.loc[rows["score"] >= TOP_SCORE, col]
    low = rows.loc[rows["score"] < LOW_SCORE, col]
    if len(top) < MIN_SAMPLES or len(low) < MIN_SAMPLES:
        return THIN, None, None
    top_avg, low_avg = float(top.mean()), float(low.mean())
    return (PASS if top_avg > 0 and top_avg > low_avg else FAIL), top_avg, low_avg


def history_note(years: float, first: str) -> str | None:
    """Return the download reminder when daily history is shorter than 5 years."""
    if years >= FULL_YEARS:
        return None
    return (f"Daily history covers {years:.1f} years from {first}. For a fuller test, set "
            "Start date in Settings > Backtest Data to 2020-01-01 and download (this also "
            "downloads 3-minute bars).")


def _pct(x: float) -> str:
    return f"{x * 100:+.2f}%"


def _order(kind: str, groups: set[str]) -> list[str]:
    fixed = {"band": BANDS, "status": STATUSES}.get(kind)
    return [g for g in fixed if g in groups] if fixed else sorted(groups)


def report_text(run: ProofRunRow, stats: list[ProofStatRow]) -> str:
    """Return the plain-text proof report."""
    lines = [
        f"Score proof - data {run.data_first} to {run.data_last} ({run.years:.1f} years), "
        f"{run.stocks} stocks, {run.days} scored days ({run.scored_first} to "
        f"{run.scored_last})",
    ]
    by_key = {(s.side, s.kind, s.grp, s.horizon): s for s in stats}
    results = {"long": run.long_result, "short": run.short_result}
    for side in SIDES:
        lines.append("")
        lines.append(f"{side.upper()} - result: {results[side]}")
        for kind in ("band", "setup", "status"):
            groups = {s.grp for s in stats if s.side == side and s.kind == kind}
            if not groups:
                continue
            lines.append(f"  {kind:<16}{'stock-days':>11}{'win 10d':>9}"
                         f"{'vs SPY 5d':>11}{'10d':>9}{'20d':>9}")
            for grp in _order(kind, groups):
                five = by_key.get((side, kind, grp, 5))
                ten = by_key.get((side, kind, grp, PASS_HORIZON))
                twenty = by_key.get((side, kind, grp, 20))
                n = five.n if five else 0
                cells = [_pct(s.avg_vs_spy) if s else "-" for s in (five, ten, twenty)]
                win = f"{ten.win_rate * 100:.0f}%" if ten else "-"
                lines.append(f"  {grp:<16}{n:>11}{win:>9}{cells[0]:>11}{cells[1]:>9}"
                             f"{cells[2]:>9}")
    lines.extend(["", "Uses today's S&P 500 list for all past days, so stocks that left the "
                      "index are missing."])
    note = history_note(run.years, run.data_first)
    if note:
        lines.append(note)
    return "\n".join(lines)


def run_proof(
    home: Path | None = None,
    root: Path = BACKTEST_ROOT,
    universe: Callable[[], list[tuple[str, str, str]]] | None = None,
) -> str | None:
    """Run the score proof, store it in ``desk.db`` and return the report.

    Args:
        home: Desk folder; defaults to the desk home.
        root: Backtest Data folder.
        universe: Returns ``(symbol, ibkr_symbol, sector)`` rows; defaults to the saved list.

    Returns:
        The report text, or ``None`` when there is no data to test.
    """
    began = time.monotonic()
    available = daily_symbols(root)
    members = member_sectors(available, universe)
    if BENCHMARK not in available or not members.sectors:
        log.warning("[Proof] No SPY or S&P 500 daily candles in Backtest Data; nothing tested")
        return None
    pb = read_daily([*members.sectors, BENCHMARK], root)
    if pb is None:
        return None
    inp, spy_bars = _inputs(pb, members.sectors)
    days = _ready_days(inp, members.listed)
    scores = replay(inp, days)
    if scores.empty:
        log.warning("[Proof] Not enough daily history to score any day; nothing tested")
        return None
    cols = list(inp.bars.closes.columns)
    frame = forward_returns(scores, pb.opens[cols].reindex(spy_bars.index),
                            inp.bars.closes, spy_bars)
    stats = group_stats(frame)
    results = {side: verdict(frame, side) for side in SIDES}
    spy_days = spy_bars.index
    run = ProofRunRow(
        created=datetime.now(UTC).isoformat(timespec="seconds"),
        data_first=spy_days[0].date().isoformat(), data_last=spy_days[-1].date().isoformat(),
        scored_first=days[0].date().isoformat(), scored_last=days[-1].date().isoformat(),
        years=round(history_years(spy_days), 2), stocks=len(cols), days=len(days),
        long_result=results["long"][0], short_result=results["short"][0],
        seconds=round(time.monotonic() - began, 1),
    )
    store = MarketStore(home or desk_home())
    try:
        store.write_proof(run, stats)
    finally:
        store.close()
    log.info("[Proof] Data %s to %s, %d stocks, %d scored days, %.0f s", run.data_first,
             run.data_last, run.stocks, run.days, run.seconds)
    for side, (result, top, low) in results.items():
        detail = (f" (70+ {_pct(top)}, under 40 {_pct(low)} against SPY at 10 days)"
                  if top is not None and low is not None else "")
        log.info("[Proof] %s: %s%s", side.capitalize(), result, detail)
    return report_text(run, stats)
