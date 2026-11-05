"""
Module: MD-MKT-001.007.M04 — market/store.py
Parent SRD: SRD-MKT-001.007
Also: MD-MKT-002.008.M04 — sector and stock RS tables (SRD-MKT-002.008)
Also: MD-MKT-003.010.M06 — score, idea and reason tables (SRD-MKT-003.010)

Market tables in ``desk.db``: ``regime_snapshot``, ``breadth_daily``, ``vix_daily``,
``sector_daily``, ``stock_rs``, ``stock_score``, ``ideas`` and ``idea_reasons``.
"""
from __future__ import annotations

import math
import sqlite3
from dataclasses import astuple, dataclass, fields
from datetime import date
from pathlib import Path

import pandas as pd

from us_swing.core.desk_contract import DB_NAME

_SCHEMA = """
CREATE TABLE IF NOT EXISTS regime_snapshot (
    date TEXT PRIMARY KEY, regime TEXT, volatility TEXT, vol20 REAL, vol_pct REAL,
    spy_close REAL, sma50 REAL, sma200 REAL, vix REAL, vix3m REAL,
    fear TEXT, fear_score INTEGER, note TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS breadth_daily (
    date TEXT PRIMARY KEY, members INTEGER, pct_above_20 REAL, pct_above_50 REAL,
    pct_above_200 REAL, new_highs INTEGER, new_lows INTEGER, advancers INTEGER,
    decliners INTEGER
);
CREATE TABLE IF NOT EXISTS vix_daily (date TEXT PRIMARY KEY, vix REAL, vix3m REAL);
CREATE TABLE IF NOT EXISTS sector_daily (
    date TEXT, sector TEXT, line REAL, rel_1m REAL, rel_3m REAL, rel_6m REAL,
    rank INTEGER, rs_ratio REAL, rs_momentum REAL, quadrant TEXT, members INTEGER,
    PRIMARY KEY (date, sector)
);
CREATE TABLE IF NOT EXISTS stock_rs (
    date TEXT, symbol TEXT, sector TEXT, score REAL, rs_rating INTEGER,
    sector_rank INTEGER, sector_size INTEGER, PRIMARY KEY (date, symbol)
);
CREATE TABLE IF NOT EXISTS stock_score (
    date TEXT, symbol TEXT, side TEXT, score REAL, rs_part REAL, flow_part REAL,
    setup_part REAL, sector_part REAL, regime_part REAL, penalty REAL, setup TEXT,
    trigger REAL, stop REAL, PRIMARY KEY (date, symbol, side)
);
CREATE TABLE IF NOT EXISTS ideas (
    date TEXT, side TEXT, symbol TEXT, status TEXT, rank INTEGER, score REAL, sector TEXT,
    setup TEXT, trigger REAL, stop REAL, PRIMARY KEY (date, side, symbol)
);
CREATE TABLE IF NOT EXISTS idea_reasons (
    date TEXT, side TEXT, symbol TEXT, seq INTEGER, reason TEXT,
    PRIMARY KEY (date, side, symbol, seq)
);
"""


@dataclass(frozen=True)
class RegimeRow:
    """One ``regime_snapshot`` row."""

    date: str
    regime: str
    volatility: str
    vol20: float
    vol_pct: float
    spy_close: float
    sma50: float
    sma200: float
    vix: float | None
    vix3m: float | None
    fear: str
    fear_score: int
    note: str
    created_at: str


@dataclass(frozen=True)
class BreadthRow:
    """One ``breadth_daily`` row."""

    date: str
    members: int
    pct_above_20: float | None
    pct_above_50: float | None
    pct_above_200: float | None
    new_highs: int
    new_lows: int
    advancers: int
    decliners: int


@dataclass(frozen=True)
class SectorRow:
    """One ``sector_daily`` row."""

    date: str
    sector: str
    line: float
    rel_1m: float | None
    rel_3m: float | None
    rel_6m: float | None
    rank: int | None
    rs_ratio: float | None
    rs_momentum: float | None
    quadrant: str | None
    members: int


@dataclass(frozen=True)
class StockRsRow:
    """One ``stock_rs`` row."""

    date: str
    symbol: str
    sector: str
    score: float
    rs_rating: int
    sector_rank: int
    sector_size: int


@dataclass(frozen=True)
class ScoreRow:
    """One ``stock_score`` row; parts are in points before the 100/90 scale."""

    date: str
    symbol: str
    side: str
    score: float
    rs_part: float
    flow_part: float
    setup_part: float
    sector_part: float
    regime_part: float
    penalty: float
    setup: str
    trigger: float | None
    stop: float | None


@dataclass(frozen=True)
class IdeaRow:
    """One ``ideas`` row; status is ``list`` or ``watch``."""

    date: str
    side: str
    symbol: str
    status: str
    rank: int
    score: float
    sector: str
    setup: str
    trigger: float | None
    stop: float | None


@dataclass(frozen=True)
class ReasonRow:
    """One ``idea_reasons`` row."""

    date: str
    side: str
    symbol: str
    seq: int
    reason: str


def _clean(value: object) -> object:
    return None if isinstance(value, float) and math.isnan(value) else value


class MarketStore:
    """Read and write the market tables beside the desk tables."""

    def __init__(self, home: Path) -> None:
        """Open ``desk.db`` in ``home`` and create the market tables when missing."""
        home.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(home / DB_NAME, timeout=5)
        self._con.execute("PRAGMA journal_mode=WAL")
        self._con.execute("PRAGMA busy_timeout=5000")
        with self._con:
            self._con.executescript(_SCHEMA)

    def close(self) -> None:
        """Close the connection."""
        self._con.close()

    def last_date(self, table: str) -> date | None:
        """Return the newest date in ``regime_snapshot``, ``breadth_daily`` or ``vix_daily``."""
        if table not in {"regime_snapshot", "breadth_daily", "vix_daily"}:
            raise ValueError(f"unknown table {table}")
        row = self._con.execute(f"SELECT MAX(date) FROM {table}").fetchone()  # noqa: S608
        return date.fromisoformat(row[0]) if row and row[0] else None

    def stored_dates(self) -> set[str]:
        """Return every ISO date already in ``regime_snapshot``."""
        return {r[0] for r in self._con.execute("SELECT date FROM regime_snapshot")}

    def write_days(self, regimes: list[RegimeRow], breadths: list[BreadthRow]) -> None:
        """Insert or replace whole days in one transaction.

        Raises:
            ValueError: When a row has no date.
        """
        if any(not r.date for r in regimes) or any(not r.date for r in breadths):
            raise ValueError("market row without a date")
        with self._con:
            self._put("regime_snapshot", RegimeRow, [astuple(r) for r in regimes])
            self._put("breadth_daily", BreadthRow, [astuple(r) for r in breadths])

    def stored_sector_dates(self) -> set[str]:
        """Return every ISO date already in ``sector_daily``."""
        return {r[0] for r in self._con.execute("SELECT DISTINCT date FROM sector_daily")}

    def write_sector_days(self, sectors: list[SectorRow], stocks: list[StockRsRow]) -> None:
        """Replace whole days of sector and stock rows in one transaction.

        Raises:
            ValueError: When a row has no date.
        """
        if any(not r.date for r in sectors) or any(not r.date for r in stocks):
            raise ValueError("sector row without a date")
        days = sorted({r.date for r in sectors} | {r.date for r in stocks})
        with self._con:
            for table in ("sector_daily", "stock_rs"):
                self._con.executemany(
                    f"DELETE FROM {table} WHERE date = ?", [(d,) for d in days]  # noqa: S608
                )
            self._put("sector_daily", SectorRow, [tuple(vars(r).values()) for r in sectors])
            self._put("stock_rs", StockRsRow, [tuple(vars(r).values()) for r in stocks])

    def stored_idea_dates(self) -> set[str]:
        """Return every ISO date already in ``stock_score``."""
        return {r[0] for r in self._con.execute("SELECT DISTINCT date FROM stock_score")}

    def write_idea_days(
        self, days: list[str], scores: list[ScoreRow], ideas: list[IdeaRow],
        reasons: list[ReasonRow],
    ) -> None:
        """Replace whole ``days`` of score, idea and reason rows in one transaction.

        Every day in ``days`` is cleared first, so a day that now has no rows keeps none.

        Raises:
            ValueError: When a day or row has no date.
        """
        rows: list[ScoreRow | IdeaRow | ReasonRow] = [*scores, *ideas, *reasons]
        if any(not d for d in days) or any(not r.date for r in rows):
            raise ValueError("idea row without a date")
        days = sorted(set(days) | {r.date for r in rows})
        with self._con:
            for table in ("stock_score", "ideas", "idea_reasons"):
                self._con.executemany(
                    f"DELETE FROM {table} WHERE date = ?", [(d,) for d in days]  # noqa: S608
                )
            self._put("stock_score", ScoreRow, [tuple(vars(r).values()) for r in scores])
            self._put("ideas", IdeaRow, [tuple(vars(r).values()) for r in ideas])
            self._put("idea_reasons", ReasonRow, [tuple(vars(r).values()) for r in reasons])

    def read_frame(self, sql: str) -> pd.DataFrame:
        """Return the result of a read-only ``SELECT`` on the market tables as a frame."""
        return pd.read_sql_query(sql, self._con)

    def _put(self, table: str, kind: type, rows: list[tuple[object, ...]]) -> None:
        names = [f.name for f in fields(kind)]
        sql = (f"INSERT OR REPLACE INTO {table} ({', '.join(names)}) "  # noqa: S608
               f"VALUES ({', '.join('?' * len(names))})")
        self._con.executemany(sql, [tuple(_clean(v) for v in r) for r in rows])

    def write_vix(self, frame: pd.DataFrame) -> int:
        """Store VIX rows (index = date, columns ``vix``, ``vix3m``); return how many."""
        vix: list[float] = frame["vix"].astype(float).tolist()
        vix3m: list[float] = frame["vix3m"].astype(float).tolist()
        rows = [
            (ts.date().isoformat(), _clean(a), _clean(b))
            for ts, a, b in zip(pd.DatetimeIndex(frame.index), vix, vix3m, strict=True)
        ]
        with self._con:
            self._con.executemany(
                "INSERT OR REPLACE INTO vix_daily (date, vix, vix3m) VALUES (?, ?, ?)", rows
            )
        return len(rows)

    def vix_by_date(self) -> dict[str, tuple[float | None, float | None]]:
        """Return stored VIX and VIX3M by ISO date."""
        return {
            r[0]: (r[1], r[2])
            for r in self._con.execute("SELECT date, vix, vix3m FROM vix_daily")
        }
