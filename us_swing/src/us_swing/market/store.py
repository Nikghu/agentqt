"""
Module: MD-MKT-001.007.M04 — market/store.py
Parent SRD: SRD-MKT-001.007
Also: MD-MKT-002.008.M04 — sector and stock RS tables (SRD-MKT-002.008)
Also: MD-MKT-003.010.M06 — score, idea and reason tables (SRD-MKT-003.010)
Also: MD-MKT-004.006.M03 — proof run and stat tables (SRD-MKT-004.006)
Also: MD-MKT-005.003.M02 — regime view table (SRD-MKT-005.003); P5b AI view tables
(SRD-MKT-005.008, .010, .013, .016)
Also: MD-MKT-006.008.M05 — news tables (SRD-MKT-006.001, .003, .008)
Also: MD-MKT-007.004.M03 — append-only ``canvas_pages`` report page versions (SRD-MKT-007.004)
Also: MD-MKT-009.004.M02 — ``pick_results`` paper results (SRD-MKT-009.004)

Market tables in ``desk.db``: ``regime_snapshot``, ``breadth_daily``, ``vix_daily``,
``sector_daily``, ``stock_rs``, ``stock_score``, ``ideas``, ``idea_reasons``,
``proof_run``, ``proof_stats``, ``regime_view``, ``sector_view``, ``setup_review``,
``risk_check`` and ``lead_picks``.
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
CREATE TABLE IF NOT EXISTS proof_run (
    run_id INTEGER PRIMARY KEY, created TEXT, data_first TEXT, data_last TEXT,
    scored_first TEXT, scored_last TEXT, years REAL, stocks INTEGER, days INTEGER,
    long_result TEXT, short_result TEXT, seconds REAL
);
CREATE TABLE IF NOT EXISTS proof_stats (
    run_id INTEGER, side TEXT, kind TEXT, grp TEXT, horizon INTEGER, n INTEGER,
    days INTEGER, win_rate REAL, avg_ret REAL, avg_vs_spy REAL,
    PRIMARY KEY (run_id, side, kind, grp, horizon)
);
CREATE TABLE IF NOT EXISTS regime_view (
    date TEXT PRIMARY KEY, regime TEXT, confidence REAL, reasons TEXT, brief TEXT,
    rule_regime TEXT, agrees INTEGER
);
CREATE TABLE IF NOT EXISTS sector_view (
    date TEXT PRIMARY KEY, favour TEXT, avoid TEXT, rotation TEXT,
    brief TEXT
);
CREATE TABLE IF NOT EXISTS setup_review (
    date TEXT, side TEXT, symbol TEXT, grade TEXT, note TEXT,
    PRIMARY KEY (date, side, symbol)
);
CREATE TABLE IF NOT EXISTS risk_check (
    date TEXT, side TEXT, symbol TEXT, verdict TEXT, by TEXT, reason TEXT,
    PRIMARY KEY (date, side, symbol)
);
CREATE TABLE IF NOT EXISTS lead_picks (
    date TEXT, side TEXT, symbol TEXT, rank INTEGER, reason TEXT,
    PRIMARY KEY (date, side, symbol)
);
CREATE TABLE IF NOT EXISTS news_items (
    id INTEGER PRIMARY KEY, date TEXT, symbol TEXT, source TEXT, published TEXT, title TEXT,
    link TEXT, fetched TEXT, UNIQUE (symbol, link), UNIQUE (symbol, title)
);
CREATE TABLE IF NOT EXISTS news_tags (
    date TEXT, side TEXT, symbol TEXT, tone TEXT, reason TEXT, points REAL, final_score REAL,
    PRIMARY KEY (date, side, symbol)
);
CREATE TABLE IF NOT EXISTS canvas_pages (
    id INTEGER PRIMARY KEY, date TEXT, version INTEGER, title TEXT, html TEXT, created TEXT,
    UNIQUE (date, version)
);
CREATE TRIGGER IF NOT EXISTS canvas_pages_no_update BEFORE UPDATE ON canvas_pages
BEGIN SELECT RAISE(ABORT, 'canvas_pages is append-only'); END;
CREATE TRIGGER IF NOT EXISTS canvas_pages_no_delete BEFORE DELETE ON canvas_pages
BEGIN SELECT RAISE(ABORT, 'canvas_pages is append-only'); END;
CREATE TABLE IF NOT EXISTS pick_results (
    date TEXT, side TEXT, symbol TEXT, status TEXT, entry_day TEXT, entry REAL, exit_day TEXT,
    exit REAL, r REAL, PRIMARY KEY (date, side, symbol)
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


@dataclass(frozen=True)
class ProofRunRow:
    """One ``proof_run`` row without its id; results are pass, fail or not enough data."""

    created: str
    data_first: str
    data_last: str
    scored_first: str
    scored_last: str
    years: float
    stocks: int
    days: int
    long_result: str
    short_result: str
    seconds: float


@dataclass(frozen=True)
class ProofStatRow:
    """One ``proof_stats`` row without its run id; kind is band, setup or status."""

    side: str
    kind: str
    grp: str
    horizon: int
    n: int
    days: int
    win_rate: float
    avg_ret: float
    avg_vs_spy: float


@dataclass(frozen=True)
class RegimeViewRow:
    """One ``regime_view`` row; ``reasons`` is a JSON list."""

    date: str
    regime: str
    confidence: float
    reasons: str
    brief: str
    rule_regime: str
    agrees: bool


@dataclass(frozen=True)
class SectorViewRow:
    """One ``sector_view`` row; ``favour`` and ``avoid`` are JSON lists."""

    date: str
    favour: str
    avoid: str
    rotation: str
    brief: str


@dataclass(frozen=True)
class SetupReviewRow:
    """One ``setup_review`` row: the grade (A, B or C) of one listed idea."""

    date: str
    side: str
    symbol: str
    grade: str
    note: str


@dataclass(frozen=True)
class RiskCheckRow:
    """One ``risk_check`` row: ``verdict`` is pass or veto, ``by`` is code or ai."""

    date: str
    side: str
    symbol: str
    verdict: str
    by: str
    reason: str


@dataclass(frozen=True)
class LeadPickRow:
    """One ``lead_picks`` row; ``rank`` is the lead's order within the side."""

    date: str
    side: str
    symbol: str
    rank: int
    reason: str


@dataclass(frozen=True)
class NewsItemRow:
    """One ``news_items`` row; ``symbol`` is empty for market headlines, times are UTC ISO."""

    date: str
    symbol: str
    source: str
    published: str
    title: str
    link: str | None
    fetched: str


@dataclass(frozen=True)
class PickResultRow:
    """One ``pick_results`` row: the paper result of one lead pick."""

    date: str
    side: str
    symbol: str
    status: str
    entry_day: str | None
    entry: float | None
    exit_day: str | None
    exit: float | None
    r: float | None


PICK_STATUSES = ("no_fill", "open", "stop", "target", "time")


@dataclass(frozen=True)
class NewsTagRow:
    """One ``news_tags`` row; ``tone`` is positive, neutral, negative or none (not asked yet)."""

    date: str
    side: str
    symbol: str
    tone: str
    reason: str
    points: float
    final_score: float


_DAY_TABLES: dict[str, type] = {
    "sector_view": SectorViewRow, "setup_review": SetupReviewRow,
    "risk_check": RiskCheckRow, "lead_picks": LeadPickRow, "news_tags": NewsTagRow,
}
DayRow = SectorViewRow | SetupReviewRow | RiskCheckRow | LeadPickRow | NewsTagRow


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

    def write_proof(self, run: ProofRunRow, stats: list[ProofStatRow]) -> int:
        """Add one proof run and its stats in one transaction; return the new run id."""
        names = [f.name for f in fields(ProofRunRow)]
        with self._con:
            cur = self._con.execute(
                f"INSERT INTO proof_run ({', '.join(names)}) "  # noqa: S608
                f"VALUES ({', '.join('?' * len(names))})", tuple(vars(run).values()))
            run_id = int(cur.lastrowid or 0)
            stat_names = ["run_id", *(f.name for f in fields(ProofStatRow))]
            self._con.executemany(
                f"INSERT INTO proof_stats ({', '.join(stat_names)}) "  # noqa: S608
                f"VALUES ({', '.join('?' * len(stat_names))})",
                [(run_id, *(_clean(v) for v in vars(r).values())) for r in stats])
        return run_id

    def latest_proof(self) -> tuple[int, ProofRunRow, list[ProofStatRow]] | None:
        """Return the newest proof run with its stats, or ``None`` when there is none."""
        names = [f.name for f in fields(ProofRunRow)]
        row = self._con.execute(
            f"SELECT run_id, {', '.join(names)} FROM proof_run "  # noqa: S608
            "ORDER BY run_id DESC LIMIT 1").fetchone()
        if row is None:
            return None
        stat_names = [f.name for f in fields(ProofStatRow)]
        stats = [ProofStatRow(*r) for r in self._con.execute(
            f"SELECT {', '.join(stat_names)} FROM proof_stats WHERE run_id = ? "  # noqa: S608
            "ORDER BY side, kind, grp, horizon", (row[0],))]
        return int(row[0]), ProofRunRow(*row[1:]), stats

    def write_regime_view(self, row: RegimeViewRow) -> None:
        """Insert or replace the regime view of one day."""
        with self._con:
            self._put("regime_view", RegimeViewRow, [tuple(vars(row).values())])

    def replace_day(self, table: str, day: str, rows: list[DayRow]) -> None:
        """Replace one day of an AI view table in one transaction.

        Raises:
            ValueError: When ``table`` is not an AI view table or a row is for another day.
        """
        kind = _DAY_TABLES.get(table)
        if kind is None or not day or any(type(r) is not kind or r.date != day for r in rows):
            raise ValueError(f"rows do not fit {table} for {day}")
        with self._con:
            self._con.execute(f"DELETE FROM {table} WHERE date = ?", (day,))  # noqa: S608
            self._put(table, kind, [tuple(vars(r).values()) for r in rows])

    def replace_pick_results(self, rows: list[PickResultRow]) -> None:
        """Replace every paper result in one transaction.

        Raises:
            ValueError: When a row has an unknown status.
        """
        if any(r.status not in PICK_STATUSES for r in rows):
            raise ValueError("unknown pick result status")
        with self._con:
            self._con.execute("DELETE FROM pick_results")
            self._put("pick_results", PickResultRow, [astuple(r) for r in rows])

    def add_news(self, rows: list[NewsItemRow]) -> int:
        """Store headlines; return how many are new.

        A headline already stored for the stock (same link or same title) is moved to the
        new day instead, so a story seen again stays in that day's facts.
        """
        names = [f.name for f in fields(NewsItemRow)]
        insert = (f"INSERT OR IGNORE INTO news_items ({', '.join(names)}) "  # noqa: S608
                  f"VALUES ({', '.join('?' * len(names))})")
        added = 0
        with self._con:
            for r in rows:
                cur = self._con.execute(
                    "UPDATE news_items SET date = ?, fetched = ? WHERE symbol = ? "
                    "AND (link = ? OR title = ?)", (r.date, r.fetched, r.symbol, r.link, r.title))
                if cur.rowcount == 0:
                    added += self._con.execute(insert, astuple(r)).rowcount
        return added

    def delete_news_before(self, published: str) -> int:
        """Delete headlines published before ``published`` (UTC ISO); return how many."""
        with self._con:
            cur = self._con.execute("DELETE FROM news_items WHERE published < ?", (published,))
        return cur.rowcount

    def add_page(self, day: str, title: str, html: str, created: str) -> int:
        """Add a report page as the next version of ``day``; return the version number."""
        with self._con:
            row = self._con.execute("SELECT COALESCE(MAX(version), 0) + 1 FROM canvas_pages "
                                    "WHERE date = ?", (day,)).fetchone()
            version = int(row[0])
            self._con.execute("INSERT INTO canvas_pages (date, version, title, html, created) "
                              "VALUES (?, ?, ?, ?, ?)", (day, version, title, html, created))
        return version

    def read_frame(self, sql: str, params: tuple[str, ...] = ()) -> pd.DataFrame:
        """Return the result of a read-only ``SELECT`` on the market tables as a frame."""
        return pd.read_sql_query(sql, self._con, params=list(params))

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
