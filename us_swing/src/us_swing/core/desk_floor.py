"""
Module: MD-GUI-034.011.M10 — core/desk_floor.py
Parent SRD: SRD-GUI-034.011
Also: MD-GUI-034.012.M11 — sector strength, rotation and RS leaders (SRD-GUI-034.012)
Also: MD-GUI-034.013.M12 — idea list (SRD-GUI-034.013)
Also: MD-GUI-034.014.M13 — score proof (SRD-GUI-034.014)

Market Floor data from ``desk.db``: the real regime, breadth, sectors and RS leaders when
the desk has them, the fallback provider (sample data) for every other product.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from us_swing.core.desk_contract import DB_NAME, FloorData, ProductDescriptor, desk_home

REGIME_ID = "regime.today"
BREADTH_ID = "breadth.daily"
_REGIME_COLUMNS = ("regime", "volatility", "fear", "vix", "data_date", "note")
_BREADTH_COLUMNS = ("measure", "value", "reading")
SECTORS_ID = "sectors.rank"
RRG_ID = "sectors.rrg"
LEADERS_ID = "rs.leaders"
LEADERS_LIMIT = 30
_SECTOR_COLUMNS = ("rank", "sector", "rel_1m", "rel_3m", "rel_6m", "quadrant")
_RRG_COLUMNS = ("sector", "rs_ratio", "rs_momentum", "quadrant")
_LEADER_COLUMNS = ("symbol", "sector", "rs_rating", "sector_rank")
IDEAS_ID = "ideas.top"
_IDEA_COLUMNS = ("symbol", "side", "score", "setup", "sector", "trigger", "stop", "why")
_IDEA_FILTERS = {"side": ("long", "short"), "status": ("list", "watch")}
PROOF_ID = "proof.bands"
_PROOF_COLUMNS = ("group", "n", "win_10d", "vs_spy_5d", "vs_spy_10d", "vs_spy_20d")
_PROOF_FILTERS = {"side": ("long", "short"), "kind": ("band", "setup", "status")}
_PROOF_ORDER = {"under 40": 0, "40-50": 1, "50-60": 2, "60-70": 3, "70-80": 4, "80+": 5,
                "list": 0, "watch": 1, "none": 2}
_FULL_YEARS = 5.0


def _signed_pct(value: float | None) -> str:
    return "-" if value is None else f"{value * 100:+.1f}%"


def _num(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f}"


def _price(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def _matches(row: Mapping[str, Any], filters: Mapping[str, str]) -> bool:
    return all(str(row.get(k)) == v for k, v in filters.items())


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value:.0f}%"


def _reading(value: float | None, good: float, weak: float) -> str:
    if value is None:
        return "-"
    return "Healthy" if value >= good else "Weak" if value < weak else "Mixed"


class DeskFloorData:
    """``FloorData`` that reads the market tables in ``desk.db`` read-only."""

    def __init__(self, fallback: FloorData, home: Path | None = None) -> None:
        """Use ``fallback`` for products the desk does not provide yet."""
        self._fallback = fallback
        self._path = (home or desk_home()) / DB_NAME

    def _query(self, sql: str) -> tuple[Any, ...] | None:
        rows = self._query_all(sql)
        return rows[0] if rows else None

    def _query_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        if not self._path.exists():
            return []
        try:
            con = sqlite3.connect(f"{self._path.as_uri()}?mode=ro", uri=True, timeout=2)
            try:
                return [tuple(r) for r in con.execute(sql, params).fetchall()]
            finally:
                con.close()
        except sqlite3.Error:
            return []

    def _latest_sectors(self) -> list[tuple[Any, ...]]:
        return self._query_all(
            "SELECT date, rank, sector, rel_1m, rel_3m, rel_6m, rs_ratio, rs_momentum, quadrant "
            "FROM sector_daily WHERE date = (SELECT MAX(date) FROM sector_daily) "
            "ORDER BY rank IS NULL, rank, sector"
        )

    def _leaders_day(self) -> str | None:
        row = self._query("SELECT MAX(date) FROM stock_rs")
        return row[0] if row and row[0] else None

    def _leader_sectors(self, day: str) -> tuple[str, ...]:
        rows = self._query_all(
            "SELECT DISTINCT sector FROM stock_rs WHERE date = ? ORDER BY sector", (day,)
        )
        return tuple(r[0] for r in rows)

    def _latest_regime(self) -> tuple[Any, ...] | None:
        return self._query(
            "SELECT date, regime, volatility, fear, vix, note FROM regime_snapshot "
            "ORDER BY date DESC LIMIT 1"
        )

    def _latest_breadth(self) -> tuple[Any, ...] | None:
        return self._query(
            "SELECT date, pct_above_20, pct_above_50, pct_above_200, new_highs, new_lows, "
            "advancers, decliners FROM breadth_daily ORDER BY date DESC LIMIT 1"
        )

    def products(self) -> Sequence[ProductDescriptor]:
        """Return the fallback products, marking the ones stored in ``desk.db`` real.

        Sector products carry the data date in their title; RS leaders is listed only
        once the desk has stock ratings.
        """
        sectors = self._latest_sectors()
        sector_day = sectors[0][0] if sectors else None
        ideas_day = self._ideas_day()
        real: dict[str, tuple[object, tuple[str, ...], str | None]] = {
            REGIME_ID: (self._latest_regime(), _REGIME_COLUMNS, None),
            BREADTH_ID: (self._latest_breadth(), _BREADTH_COLUMNS, None),
            SECTORS_ID: (sector_day, _SECTOR_COLUMNS, sector_day),
            RRG_ID: (sector_day, _RRG_COLUMNS, sector_day),
            IDEAS_ID: (ideas_day, _IDEA_COLUMNS, ideas_day),
        }
        out: list[ProductDescriptor] = []
        for product in self._fallback.products():
            found, columns, day = real.get(product.id, (None, (), None))
            if not found:
                out.append(product)
                continue
            title = f"{product.title} ({day})" if day else product.title
            filters = _IDEA_FILTERS if product.id == IDEAS_ID else product.filters
            out.append(replace(product, title=title, columns=columns, filters=filters,
                               sample=False))
        if run := self._latest_proof():
            out.append(ProductDescriptor(
                PROOF_ID, _proof_title(run), "table", ("table",), _PROOF_COLUMNS, _PROOF_FILTERS,
            ))
        if leaders_day := self._leaders_day():
            out.append(ProductDescriptor(
                LEADERS_ID, f"RS leaders ({leaders_day})", "table", ("table",), _LEADER_COLUMNS,
                {"sector": self._leader_sectors(leaders_day)},
            ))
        return out

    def rows(self, product_id: str, filters: Mapping[str, str]) -> list[dict[str, Any]]:
        """Return desk rows for regime and breadth when stored, else fallback rows."""
        if product_id == REGIME_ID and (row := self._latest_regime()):
            day, regime, volatility, fear, vix, note = row
            return [{
                "regime": regime, "volatility": volatility, "fear": fear,
                "vix": "-" if vix is None else f"{vix:.1f}", "data_date": day,
                "note": note or "-",
            }]
        if product_id == BREADTH_ID and (row := self._latest_breadth()):
            day, p20, p50, p200, highs, lows, adv, dec = row
            ratio = f"{adv / dec:.1f} : 1" if dec else "-"
            return [
                {"measure": "Data date", "value": day, "reading": ""},
                {"measure": "Stocks above 20-day average", "value": _pct(p20),
                 "reading": _reading(p20, 60, 40)},
                {"measure": "Stocks above 50-day average", "value": _pct(p50),
                 "reading": _reading(p50, 60, 40)},
                {"measure": "Stocks above 200-day average", "value": _pct(p200),
                 "reading": _reading(p200, 60, 40)},
                {"measure": "New highs minus new lows", "value": f"{highs - lows:+d}",
                 "reading": f"{highs} highs, {lows} lows"},
                {"measure": "Advancing vs declining", "value": ratio,
                 "reading": f"{adv} up, {dec} down"},
            ]
        if product_id in (SECTORS_ID, RRG_ID) and (sectors := self._latest_sectors()):
            rows = [_sector_row(product_id, r) for r in sectors]
            return [r for r in rows if _matches(r, filters)]
        if product_id == LEADERS_ID:
            return self._leaders(filters.get("sector"))
        if product_id == PROOF_ID:
            return self._proof(filters.get("side") or "long", filters.get("kind") or "band")
        if product_id == IDEAS_ID and (day := self._ideas_day()):
            return self._ideas(day, filters.get("side"), filters.get("status") or "list")
        return self._fallback.rows(product_id, filters)

    def _latest_proof(self) -> tuple[Any, ...] | None:
        return self._query(
            "SELECT run_id, scored_first, scored_last, years, long_result, short_result "
            "FROM proof_run ORDER BY run_id DESC LIMIT 1"
        )

    def _proof(self, side: str, kind: str) -> list[dict[str, Any]]:
        run = self._latest_proof()
        if run is None:
            return []
        rows = self._query_all(
            "SELECT grp, horizon, n, win_rate, avg_vs_spy FROM proof_stats "
            "WHERE run_id = ? AND side = ? AND kind = ?", (run[0], side, kind),
        )
        groups: dict[str, dict[str, Any]] = {}
        for grp, horizon, n, win, vs_spy in rows:
            row = groups.setdefault(grp, {"group": grp, "n": "-", "win_10d": "-",
                                          "vs_spy_5d": "-", "vs_spy_10d": "-",
                                          "vs_spy_20d": "-"})
            row[f"vs_spy_{horizon}d"] = "-" if vs_spy is None else f"{vs_spy * 100:+.2f}%"
            if horizon == 5:
                row["n"] = f"{n:,}"
            if horizon == 10:
                row["win_10d"] = _pct(win * 100)
        return [groups[g] for g in sorted(groups, key=lambda g: (_PROOF_ORDER.get(g, 9), g))]

    def _ideas_day(self) -> str | None:
        row = self._query("SELECT MAX(date) FROM ideas")
        return row[0] if row and row[0] else None

    def _ideas(self, day: str, side: str | None, status: str) -> list[dict[str, Any]]:
        rows = self._query_all(
            "SELECT i.symbol, i.side, i.score, i.setup, i.sector, i.trigger, i.stop, r.reason "
            "FROM ideas i LEFT JOIN idea_reasons r ON r.date = i.date AND r.side = i.side "
            "AND r.symbol = i.symbol AND r.seq = 1 "
            "WHERE i.date = ? AND i.status = ? AND (? IS NULL OR i.side = ?) "
            "ORDER BY i.score DESC, i.symbol",
            (day, status, side, side),
        )
        return [
            {"symbol": sym, "side": sd, "score": f"{score:.0f}", "setup": setup,
             "sector": sector, "trigger": _price(trigger), "stop": _price(stop),
             "why": reason or "-"}
            for sym, sd, score, setup, sector, trigger, stop, reason in rows
        ]

    def _leaders(self, sector: str | None) -> list[dict[str, Any]]:
        day = self._leaders_day()
        if day is None:
            return []
        rows = self._query_all(
            "SELECT symbol, sector, rs_rating, sector_rank, sector_size FROM stock_rs "
            "WHERE date = ? AND (? IS NULL OR sector = ?) "
            "ORDER BY rs_rating DESC, score DESC LIMIT ?",
            (day, sector, sector, LEADERS_LIMIT),
        )
        return [
            {"symbol": sym, "sector": sec, "rs_rating": rating,
             "sector_rank": f"{rank} of {size}"}
            for sym, sec, rating, rank, size in rows
        ]


def _proof_title(run: tuple[Any, ...]) -> str:
    _, first, last, years, long_result, short_result = run
    title = f"Score proof ({first} to {last}) · Long {long_result} · Short {short_result}"
    return title + (f" · only {years:.1f} years of data" if years < _FULL_YEARS else "")


def _sector_row(product_id: str, row: tuple[Any, ...]) -> dict[str, Any]:
    _day, rank, sector, rel_1m, rel_3m, rel_6m, ratio, momentum, quadrant = row
    if product_id == RRG_ID:
        return {"sector": sector, "rs_ratio": _num(ratio), "rs_momentum": _num(momentum),
                "quadrant": quadrant or "-"}
    return {"rank": "-" if rank is None else rank, "sector": sector,
            "rel_1m": _signed_pct(rel_1m), "rel_3m": _signed_pct(rel_3m),
            "rel_6m": _signed_pct(rel_6m), "quadrant": quadrant or "-"}
