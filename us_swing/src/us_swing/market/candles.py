"""
Module: MD-MKT-001.001.M01 — market/candles.py
Parent SRD: SRD-MKT-001.001
Also: MD-MKT-002.001.M01 — member sectors (SRD-MKT-002.001)

Read-only daily bars from the app's ``candles.db`` for SPY and the S&P 500 members.
"""
from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable, Iterable
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

CANDLE_DB = Path.home() / ".usswing" / "candles.db"
BENCHMARK = "SPY"


@dataclass(frozen=True)
class DailyBars:
    """Wide daily frames: one column per symbol, one row per date."""

    closes: pd.DataFrame
    highs: pd.DataFrame
    lows: pd.DataFrame


class CandleReader:
    """Reads ``price_1d`` without ever writing to ``candles.db``."""

    def __init__(self, path: Path = CANDLE_DB) -> None:
        """Remember the file.

        Raises:
            FileNotFoundError: When ``path`` does not exist.
        """
        if not path.exists():
            raise FileNotFoundError(path)
        self._uri = f"{path.as_uri()}?mode=ro"

    def symbols(self) -> set[str]:
        """Return every symbol with daily bars."""
        with closing(sqlite3.connect(self._uri, uri=True)) as con:
            return {r[0] for r in con.execute("SELECT DISTINCT symbol FROM price_1d")}

    def read(self, symbols: Iterable[str]) -> DailyBars:
        """Return closes, highs and lows for ``symbols`` as wide frames by date."""
        wanted = sorted(set(symbols))
        marks = ",".join("?" * len(wanted))
        con = sqlite3.connect(self._uri, uri=True)
        try:
            frame = pd.read_sql_query(
                f"SELECT symbol, datetime, high, low, close FROM price_1d "  # noqa: S608
                f"WHERE symbol IN ({marks}) ORDER BY symbol, datetime",
                con,
                params=tuple(wanted),
            )
        finally:
            con.close()
        frame["date"] = pd.to_datetime(frame["datetime"]).dt.normalize()
        frame = frame.drop_duplicates(["symbol", "date"], keep="last")

        def wide(col: str) -> pd.DataFrame:
            return frame.pivot(index="date", columns="symbol", values=col).sort_index()

        return DailyBars(wide("close"), wide("high"), wide("low"))


@dataclass(frozen=True)
class Members:
    """Member symbols found in the candles, out of how many are listed."""

    symbols: list[str]
    listed: int
    note: str = ""


def member_symbols(
    available: set[str],
    universe: Callable[[], list[tuple[str, str]]] | None = None,
) -> Members:
    """Return S&P 500 member symbols that have daily bars, SPY excluded.

    Args:
        available: Symbols present in ``candles.db``.
        universe: Returns ``(symbol, ibkr_symbol)`` pairs; defaults to the saved
            S&P 500 list. When it fails, every available symbol except SPY is used.
    """
    try:
        pairs = (universe or _saved_universe)()
    except Exception as exc:  # noqa: BLE001 — fall back to the candles on any list failure
        log.warning("[Regime] S&P 500 list not available, using all stocks with candles: %s", exc)
        found = sorted(available - {BENCHMARK})
        return Members(found, len(found), "all stocks with candles")
    pairs = [p for p in pairs if BENCHMARK not in p]
    found = sorted({next((s for s in pair if s in available), "") for pair in pairs} - {""})
    if len(found) < len(pairs):
        log.info("[Regime] %d of %d S&P 500 stocks have no daily candles",
                 len(pairs) - len(found), len(pairs))
    return Members(found, len(pairs))


@dataclass(frozen=True)
class SectorMembers:
    """Sector of each member found in the candles, out of how many are listed."""

    sectors: dict[str, str]
    listed: int


def member_sectors(
    available: set[str],
    universe: Callable[[], list[tuple[str, str, str]]] | None = None,
) -> SectorMembers:
    """Return the sector of each S&P 500 member that has daily bars, SPY excluded.

    Args:
        available: Symbols present in ``candles.db``.
        universe: Returns ``(symbol, ibkr_symbol, sector)`` rows; defaults to the
            saved S&P 500 list. When it fails, no sectors are returned.
    """
    try:
        rows = (universe or _saved_sectors)()
    except Exception as exc:  # noqa: BLE001 — no list means no sectors, never a failed run
        log.warning("[Sectors] S&P 500 list not available, sectors not computed: %s", exc)
        return SectorMembers({}, 0)
    rows = [r for r in rows if BENCHMARK not in r[:2]]
    out: dict[str, str] = {}
    no_sector = 0
    for symbol, ibkr_symbol, sector in rows:
        found = next((s for s in (symbol, ibkr_symbol) if s in available), "")
        if not found:
            continue
        if not sector.strip():
            no_sector += 1
            continue
        out[found] = sector.strip()
    if no_sector:
        log.info("[Sectors] %d stock(s) have no sector in the S&P 500 list and are left out",
                 no_sector)
    return SectorMembers(out, len(rows))


def _saved_universe() -> list[tuple[str, str]]:
    from us_swing.core.backtest_bridge import load_universe  # noqa: PLC0415 — heavy import

    return [(r.symbol, r.ibkr_symbol) for r in load_universe()]


def _saved_sectors() -> list[tuple[str, str, str]]:
    from us_swing.core.backtest_bridge import load_universe  # noqa: PLC0415 — heavy import

    return [(r.symbol, r.ibkr_symbol, r.sector) for r in load_universe()]
