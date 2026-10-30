"""
Module: MD-BKT-002.040.M13 — backtest/steps/report.py
Parent SRD: SRD-BKT-002.040, SRD-BKT-002.070–.073

Step 4 · Report: stats of one variant from its saved Step 3 rows (trades, day
log, money by day) — returns, risk, trade quality, breakdowns, skip counts, an
equal-weight S&P 500 benchmark and a compare table (SRD-BKT-002.040–.047);
Phase 4b adds exit / hold stats, robustness and the capital × per-trade grid (.070–.073).
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np
import numpy.typing as npt
import pandas as pd

TRADING_DAYS = 252
ET = "America/New_York"
GROUPS = ("strategy", "symbol", "sector", "exit_reason", "hour", "weekday", "hold",
          "score_bucket", "rank")
HOLD_BUCKETS = ((1.0, "under 1 h"), (3.0, "1–3 h"), (24.0, "3 h–1 day"),
                (math.inf, "over 1 day"))
MONTE_CARLO_RUNS = 1000
MONTE_CARLO_SEED = 7
BREAKDOWN_COLUMNS = ["group", "trades", "net_pnl", "win_rate", "avg_pnl"]
COMPARE_STATS = ("Net P&L", "Return", "CAGR", "Max drawdown", "Sharpe", "Win rate",
                 "Profit factor", "Trades")

FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class Stat:
    """One measure; ``kind`` says how to show it: usd, pct, ratio, count or days."""

    name: str
    value: float
    kind: str


@dataclass(frozen=True)
class Report:
    """Step 4 output of one variant.

    ``daily`` has date, equity, drawdown (fraction) and benchmark; ``monthly`` has
    year, month and pnl; ``trades`` adds sector, hour and weekday columns.
    """

    label: str
    capital: float
    stats: tuple[Stat, ...]
    daily: pd.DataFrame
    monthly: pd.DataFrame
    skips: pd.DataFrame
    trades: pd.DataFrame
    per_trade_pct: float = math.nan

    def stat(self, name: str) -> float:
        """Value of the stat called ``name``."""
        return next(s.value for s in self.stats if s.name == name)


def normalize(trades: pd.DataFrame, money: pd.DataFrame, day_log: pd.DataFrame
              ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Same dtypes for in-memory results and rows read back from ``results.db``."""
    trades = trades.copy()
    for col in ("entry_ts", "exit_ts"):
        trades[col] = pd.to_datetime(trades[col], utc=True)
    money = money.copy()
    money["date"] = pd.to_datetime(money["date"]).dt.date
    money = money.sort_values("date", ignore_index=True)
    return trades.sort_values("exit_ts", ignore_index=True), money, day_log.copy()


def daily_equity(money: pd.DataFrame, capital: float) -> pd.DataFrame:
    """Date, equity and drawdown from the peak so far (SRD-BKT-002.042)."""
    equity = money["equity"].astype(float).to_numpy()
    peak = np.maximum.accumulate(np.concatenate(([capital], equity)))[1:]
    return pd.DataFrame({"date": money["date"], "equity": equity,
                         "drawdown": equity / peak - 1.0})


def _returns(daily: pd.DataFrame, capital: float) -> FloatArray:
    equity = daily["equity"].to_numpy(dtype=np.float64)
    prev = np.concatenate(([capital], equity[:-1]))
    return np.asarray(equity / prev - 1.0, dtype=np.float64)



def _cagr(daily: pd.DataFrame, capital: float) -> float:
    if daily.empty or capital <= 0:
        return math.nan
    days = (daily["date"].iloc[-1] - daily["date"].iloc[0]).days + 1
    end = float(daily["equity"].iloc[-1])
    return (end / capital) ** (365.25 / days) - 1.0 if end > 0 else -1.0


def _invested_share(trades: pd.DataFrame, days: Sequence[date]) -> float:
    if not len(days):
        return 0.0
    held: set[date] = set()
    for start, end in zip(trades["entry_ts"].dt.tz_convert(ET).dt.date,
                          trades["exit_ts"].dt.tz_convert(ET).dt.date):
        held.update(pd.date_range(start, end).date)
    return len(held & set(days)) / len(days)


def returns_stats(trades: pd.DataFrame, daily: pd.DataFrame, capital: float) -> list[Stat]:
    """Net P&L, return, CAGR and share of days with a position (SRD-BKT-002.041)."""
    end = float(daily["equity"].iloc[-1]) if not daily.empty else capital
    return [
        Stat("Net P&L", end - capital, "usd"),
        Stat("Return", end / capital - 1.0 if capital else math.nan, "pct"),
        Stat("CAGR", _cagr(daily, capital), "pct"),
        Stat("Time invested", _invested_share(trades, list(daily["date"])), "pct"),
    ]


def _longest_drawdown(drawdown: FloatArray) -> int:
    longest = run = 0
    for below in drawdown < 0:
        run = run + 1 if below else 0
        longest = max(longest, run)
    return longest


def risk_stats(trades: pd.DataFrame, daily: pd.DataFrame, capital: float) -> list[Stat]:
    """Drawdown, Sharpe, Sortino, Calmar, worst day and trade (SRD-BKT-002.042)."""
    rets = _returns(daily, capital)
    equity = daily["equity"].to_numpy(dtype=np.float64)
    peak = np.maximum.accumulate(np.concatenate(([capital], equity)))[1:]
    max_dd = float(daily["drawdown"].min()) if not daily.empty else 0.0
    sd = float(np.std(rets, ddof=1)) if len(rets) > 1 else 0.0
    down = np.minimum(rets, 0.0)
    down_sd = float(np.sqrt(np.mean(down ** 2))) if len(rets) else 0.0
    mean = float(np.mean(rets)) if len(rets) else 0.0
    cagr = _cagr(daily, capital)
    day_pnl = np.diff(np.concatenate(([capital], equity)))
    return [
        Stat("Max drawdown", max_dd, "pct"),
        Stat("Max drawdown $", float((equity - peak).min()) if len(equity) else 0.0, "usd"),
        Stat("Longest drawdown", float(_longest_drawdown(daily["drawdown"].to_numpy())),
             "days"),
        Stat("Sharpe", mean / sd * math.sqrt(TRADING_DAYS) if sd > 0 else math.nan, "ratio"),
        Stat("Sortino", mean / down_sd * math.sqrt(TRADING_DAYS) if down_sd > 0 else math.nan,
             "ratio"),
        Stat("Calmar", cagr / -max_dd if max_dd < 0 else math.nan, "ratio"),
        Stat("Worst day", float(day_pnl.min()) if len(day_pnl) else 0.0, "usd"),
        Stat("Worst trade", float(trades["net_pnl"].min()) if not trades.empty else 0.0,
             "usd"),
    ]


def _longest_streak(wins: Sequence[bool], value: bool) -> int:
    longest = run = 0
    for w in wins:
        run = run + 1 if w == value else 0
        longest = max(longest, run)
    return longest


def trade_stats(trades: pd.DataFrame) -> list[Stat]:
    """Win rate, averages, payoff, profit factor, expectancy, streaks (SRD-BKT-002.043)."""
    pnl = trades["net_pnl"].astype(float)
    wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(losses.mean()) if len(losses) else 0.0
    gross_loss = -float(losses.sum())
    won = list(pnl > 0)
    return [
        Stat("Trades", float(len(pnl)), "count"),
        Stat("Win rate", len(wins) / len(pnl) if len(pnl) else math.nan, "pct"),
        Stat("Average win", avg_win, "usd"),
        Stat("Average loss", avg_loss, "usd"),
        Stat("Payoff", avg_win / -avg_loss if avg_loss < 0 else math.nan, "ratio"),
        Stat("Profit factor", float(wins.sum()) / gross_loss if gross_loss > 0 else math.nan,
             "ratio"),
        Stat("Expectancy", float(pnl.mean()) if len(pnl) else 0.0, "usd"),
        Stat("Longest win streak", float(_longest_streak(won, True)), "count"),
        Stat("Longest loss streak", float(_longest_streak(won, False)), "count"),
    ]


def _hours(trades: pd.DataFrame) -> pd.Series:
    return (trades["exit_ts"] - trades["entry_ts"]).dt.total_seconds() / 3600.0


def exit_hold_stats(trades: pd.DataFrame) -> list[Stat]:
    """Average MAE, MFE, profit given back and hold time (SRD-BKT-002.070)."""
    if trades.empty:
        return [Stat(n, math.nan, k) for n, k in (
            ("Average MAE", "usd"), ("Average MFE", "usd"), ("Profit given back", "usd"),
            ("Median hold", "hours"), ("Longest hold", "hours"))]
    mfe = trades["mfe"].astype(float)
    hours = _hours(trades)
    return [
        Stat("Average MAE", float(trades["mae"].astype(float).mean()), "usd"),
        Stat("Average MFE", float(mfe.mean()), "usd"),
        Stat("Profit given back", float((mfe - trades["net_pnl"].astype(float)).mean()), "usd"),
        Stat("Median hold", float(hours.median()), "hours"),
        Stat("Longest hold", float(hours.max()), "hours"),
    ]


def _max_drawdowns(pnl: FloatArray, capital: float, runs: int, seed: int) -> FloatArray:
    rng = np.random.default_rng(seed)
    out = np.empty(runs)
    for i in range(runs):
        equity = capital + np.cumsum(rng.permutation(pnl))
        peak = np.maximum.accumulate(np.concatenate(([capital], equity)))[1:]
        out[i] = float((equity / peak - 1.0).min())
    return out


def robustness_stats(trades: pd.DataFrame, daily: pd.DataFrame, capital: float) -> list[Stat]:
    """Monte Carlo drawdown, half-period P&L and P&L without the top 5 (SRD-BKT-002.072)."""
    pnl = trades["net_pnl"].to_numpy(dtype=np.float64)
    dds = (_max_drawdowns(pnl, capital, MONTE_CARLO_RUNS, MONTE_CARLO_SEED)
           if len(pnl) and capital > 0 else np.array([math.nan]))
    if daily.empty:
        first = second = 0.0
    else:
        start, end = daily["date"].iloc[0], daily["date"].iloc[-1]
        middle = start + (end - start) / 2
        exits = trades["exit_ts"].dt.tz_convert(ET).dt.date
        first = float(trades.loc[exits <= middle, "net_pnl"].sum())
        second = float(trades.loc[exits > middle, "net_pnl"].sum())
    return [
        Stat("Monte Carlo drawdown, bad 5%", float(np.percentile(dds, 5)), "pct"),
        Stat("Monte Carlo drawdown, median", float(np.percentile(dds, 50)), "pct"),
        Stat("Monte Carlo drawdown, good 5%", float(np.percentile(dds, 95)), "pct"),
        Stat("First half P&L", first, "usd"),
        Stat("Second half P&L", second, "usd"),
        Stat("P&L without top 5 trades", float(pnl.sum() - np.sort(pnl)[-5:].sum()), "usd"),
    ]


def monthly_pnl(daily: pd.DataFrame, capital: float) -> pd.DataFrame:
    """P&L per calendar month from day-to-day equity change (SRD-BKT-002.041)."""
    equity = daily["equity"].to_numpy(dtype=np.float64)
    change = np.diff(np.concatenate(([capital], equity)))
    stamps = pd.to_datetime(daily["date"])
    frame = pd.DataFrame({"year": stamps.dt.year, "month": stamps.dt.month, "pnl": change})
    return frame.groupby(["year", "month"])["pnl"].sum().reset_index()


def _hold_bucket(hours: float) -> str:
    return next(name for limit, name in HOLD_BUCKETS if hours < limit)


def _score_buckets(scores: pd.Series) -> list[str]:
    """Quartile ranges of the score, or the score itself when there are few values."""
    values = scores.astype(float)
    if values.nunique() < 4:
        return [f"{v:.2f}" for v in values]
    bins = pd.qcut(values, 4, duplicates="drop")
    return [f"{iv.left:.2f}–{iv.right:.2f}" for iv in bins]


def with_groups(trades: pd.DataFrame, sectors: Mapping[str, str]) -> pd.DataFrame:
    """Add sector, entry hour (ET), weekday, hold time, score bucket and rank group columns."""
    local = trades["entry_ts"].dt.tz_convert(ET)
    out = trades.assign(
        sector=[sectors.get(str(s), "Unknown") for s in trades["symbol"]],
        hour=[f"{h:02d}:00" for h in local.dt.hour],
        weekday=list(local.dt.day_name()),
        hold=[_hold_bucket(h) for h in _hours(trades)],
    )
    out["score_bucket"] = _score_buckets(trades["score"]) if not trades.empty else []
    out["rank"] = [str(int(r)) for r in trades["rank"]]
    return out


def breakdown(trades: pd.DataFrame, by: str) -> pd.DataFrame:
    """Trades, net P&L, win rate and average P&L per group, best first (SRD-BKT-002.044).

    Raises:
        ValueError: ``by`` is not one of ``GROUPS``.
    """
    if by not in GROUPS:
        raise ValueError(f"Unknown group {by!r}")
    if trades.empty:
        return pd.DataFrame(columns=BREAKDOWN_COLUMNS)
    grouped = trades.groupby(by)["net_pnl"]
    out = pd.DataFrame({
        "trades": grouped.size(), "net_pnl": grouped.sum(),
        "win_rate": grouped.apply(lambda s: float((s > 0).mean())), "avg_pnl": grouped.mean(),
    }).reset_index().rename(columns={by: "group"})
    ordered: pd.DataFrame = out.sort_values("net_pnl", ascending=False, ignore_index=True)
    return ordered.loc[:, BREAKDOWN_COLUMNS]


def skip_counts(day_log: pd.DataFrame) -> pd.DataFrame:
    """Entries taken and each skip reason with its count (SRD-BKT-002.045)."""
    if day_log.empty:
        return pd.DataFrame(columns=["decision", "count"])
    counts = day_log["decision"].value_counts()
    return pd.DataFrame({"decision": counts.index.astype(str), "count": counts.to_numpy()})


def equal_weight_benchmark(closes: Mapping[str, pd.Series], days: Sequence[date],
                           capital: float) -> pd.Series:
    """Capital grown by the average daily return of the stocks (SRD-BKT-002.046).

    ``closes`` maps each stock to its daily closes indexed by date; a day's return
    uses the stock's previous close, so the first test day already counts.
    """
    if not closes or not len(days):
        return pd.Series(np.full(len(days), np.nan), index=list(days), dtype=float)
    rets = pd.DataFrame({s: c.sort_index().pct_change() for s, c in closes.items()})
    mean = rets.reindex(list(days)).mean(axis=1, skipna=True).fillna(0.0)
    return capital * (1.0 + mean).cumprod()


def build_report(label: str, capital: float, trades: pd.DataFrame, money: pd.DataFrame,
                 day_log: pd.DataFrame, sectors: Mapping[str, str],
                 benchmark: pd.Series | None = None) -> Report:
    """All Step 4 measures of one variant from its Step 3 rows (SRD-BKT-002.040)."""
    trades, money, day_log = normalize(trades, money, day_log)
    daily = daily_equity(money, capital)
    daily["benchmark"] = (benchmark.reindex(list(daily["date"])).to_numpy()
                          if benchmark is not None else np.nan)
    stats = (*returns_stats(trades, daily, capital), *risk_stats(trades, daily, capital),
             *trade_stats(trades), *exit_hold_stats(trades),
             *robustness_stats(trades, daily, capital))
    return Report(label, capital, stats, daily, monthly_pnl(daily, capital),
                  skip_counts(day_log), with_groups(trades, sectors))


def heat_map(reports: Sequence[Report]) -> pd.DataFrame:
    """Return by capital (rows) × per-trade % (columns), or empty when one of them is
    the same for every variant (SRD-BKT-002.073)."""
    rows = pd.DataFrame([{"capital": r.capital, "per_trade": r.per_trade_pct,
                          "ret": r.stat("Return")} for r in reports])
    if rows.empty or rows["capital"].nunique() < 2 or rows["per_trade"].nunique() < 2:
        return pd.DataFrame()
    return rows.pivot_table(index="capital", columns="per_trade", values="ret", aggfunc="mean")


def compare(reports: Sequence[Report]) -> pd.DataFrame:
    """One row of key stats per variant (SRD-BKT-002.047)."""
    return pd.DataFrame([{"variant": r.label, **{n: r.stat(n) for n in COMPARE_STATS}}
                         for r in reports])
