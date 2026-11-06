"""
Module: MD-MKT-004.001.M01 — market/proof_data.py
Parent SRD: SRD-MKT-004.001

Reads the Backtest Data store's daily files (``<root>/1d/<SYM>.parquet``) for the score
proof. The file layout is the contract: the backtest tool is never imported.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from us_swing.market.candles import DailyBars

log = logging.getLogger(__name__)

BACKTEST_ROOT = Path.home() / ".usswing" / "backtest"
_COLUMNS = ["open", "high", "low", "close", "volume"]


@dataclass(frozen=True)
class ProofBars:
    """Daily bars as wide frames (index = trading day, columns = symbols), with opens."""

    bars: DailyBars
    opens: pd.DataFrame


def daily_symbols(root: Path = BACKTEST_ROOT) -> set[str]:
    """Return the symbols that have a daily file; empty when the folder is missing."""
    folder = root / "1d"
    return {p.stem for p in folder.glob("*.parquet")} if folder.is_dir() else set()


def read_daily(symbols: Iterable[str], root: Path = BACKTEST_ROOT) -> ProofBars | None:
    """Return the daily bars of ``symbols`` that have a file, or ``None`` when none has.

    Args:
        symbols: Stocks to read (file names, e.g. ``BRK B``).
        root: Backtest Data folder.
    """
    parts: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        path = root / "1d" / f"{sym}.parquet"
        if not path.is_file():
            continue
        df = pd.read_parquet(path, columns=["ts", *_COLUMNS])
        df.index = pd.DatetimeIndex(pd.to_datetime(df.pop("ts")).dt.normalize())
        parts[sym] = df[~df.index.duplicated(keep="last")].sort_index()
    if not parts:
        log.warning("[Proof] No daily candles in the Backtest Data folder; nothing tested")
        return None
    wide = {col: pd.DataFrame({s: f[col] for s, f in parts.items()}).sort_index()
            for col in _COLUMNS}
    return ProofBars(DailyBars(wide["close"], wide["high"], wide["low"], wide["volume"]),
                     wide["open"])


def history_years(index: pd.Index) -> float:
    """Return the years between the first and last day of ``index`` (0 when empty)."""
    if len(index) == 0:
        return 0.0
    days = pd.DatetimeIndex(index)
    return float((days[-1] - days[0]).days / 365.25)
