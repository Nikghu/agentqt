"""
Module: MD-GUI-034.011.M10 — core/desk_floor.py
Parent SRD: SRD-GUI-034.011
Also: MD-GUI-034.012.M11 — sector strength, rotation and RS leaders (SRD-GUI-034.012)
Also: MD-GUI-034.013.M12 — idea list (SRD-GUI-034.013)
Also: MD-GUI-034.014.M13 — score proof (SRD-GUI-034.014)
Also: MD-GUI-034.015.M14 — AI feed briefs (SRD-GUI-034.015)
Also: MD-GUI-034.017.M16 — month AI cost (SRD-GUI-034.017)
Also: MD-GUI-034.018.M17 — latest news, news tags and calendar (SRD-GUI-034.018–.020)
Also: MD-GUI-034.022.M19 — report page versions for AI Desk Pages (SRD-GUI-034.022)
Also: MD-GUI-034.032.M22 — weekly reports for AI Desk Reports (SRD-GUI-034.032)
Also: MD-GUI-034.054.M32 — AI feed cards (SRD-GUI-034.054)
Also: MD-GUI-034.047.M29 — market tiles, breadth history and header chips (SRD-GUI-034.045, .047, .049)
Also: MD-MKT-011.007.M05 — approved asked panels (SRD-MKT-011.007)

Market Floor data from ``desk.db``: the real regime, breadth, sectors and RS leaders when
the desk has them, the fallback provider (sample data) for every other product.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any

from us_swing.core.desk_ai_settings import load_settings
from us_swing.core.desk_contract import DB_NAME, FloorData, ProductDescriptor, desk_home
from us_swing.core.desk_data_asks import approved_products
from us_swing.core.desk_feed import FeedCard, feed_cards
from us_swing.core.desk_recipes import DataRecipe, run_recipe
from us_swing.core.econ_calendar import events_between, trading_days_after

REGIME_ID = "regime.today"
BREADTH_ID = "breadth.daily"
_REGIME_COLUMNS = ("regime", "volatility", "fear", "vix", "data_date", "note")
_BREADTH_COLUMNS = ("measure", "value", "reading")
SECTORS_ID = "sectors.rank"
RRG_ID = "sectors.rrg"
TILES_ID = "market.tiles"
HISTORY_ID = "breadth.history"
HISTORY_DAYS = 60
_TILE_COLUMNS = ("title", "value", "note")
_HISTORY_COLUMNS = ("date", "value")
LEADERS_ID = "rs.leaders"
LEADERS_LIMIT = 30
_SECTOR_COLUMNS = ("rank", "sector", "rel_1m", "rel_3m", "rel_6m", "quadrant")
_RRG_COLUMNS = ("sector", "rs_ratio", "rs_momentum", "quadrant")
_LEADER_COLUMNS = ("symbol", "sector", "rs_rating", "sector_rank")
IDEAS_ID = "ideas.top"
_IDEA_COLUMNS = ("symbol", "side", "score", "setup", "sector", "trigger", "stop", "why")
_IDEA_FILTERS: dict[str, tuple[str, ...]] = {"side": ("long", "short"),
                                              "status": ("list", "watch")}
PROOF_ID = "proof.bands"
_PROOF_COLUMNS = ("group", "n", "win_10d", "vs_spy_5d", "vs_spy_10d", "vs_spy_20d")
_PROOF_FILTERS = {"side": ("long", "short"), "kind": ("band", "setup", "status")}
_PROOF_ORDER = {"under 40": 0, "40-50": 1, "50-60": 2, "60-70": 3, "70-80": 4, "80+": 5,
                "list": 0, "watch": 1, "none": 2}
_FULL_YEARS = 5.0
FEED_LIMIT = 20
NEWS_ID = "news.latest"
TAGS_ID = "news.tags"
CALENDAR_ID = "calendar.week"
NEWS_LIMIT = 50
CALENDAR_DAYS = 10
_NEWS_COLUMNS = ("time", "headline", "symbol", "tone")
_TONES = ("positive", "neutral", "negative")
_TAG_COLUMNS = ("symbol", "side", "tone", "points", "final", "reason")
_CALENDAR_COLUMNS = ("date", "time", "event", "importance")
_REAL_FILTERS: dict[str, dict[str, tuple[str, ...]]] = {
    IDEAS_ID: _IDEA_FILTERS, NEWS_ID: {"tone": _TONES},
    CALENDAR_ID: {"importance": ("high", "medium")},
}
NY = ZoneInfo("America/New_York")
ASKED_PREFIX = "asked."


@dataclass(frozen=True)
class MonthCost:
    """This month's AI use: API spend against the budget, and rows by employee and model."""

    month: str
    budget_usd: float
    spent_usd: float
    by_employee: list[tuple[str, str, str, str]]
    by_model: list[tuple[str, str, str, str]]


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


@dataclass(frozen=True)
class PageVersion:
    """One report page version for the AI Desk Pages list; ``saved`` is New York time."""

    page_id: int
    day: str
    version: int
    title: str
    saved: str


class DeskFloorData:
    """``FloorData`` that reads the market tables in ``desk.db`` read-only."""

    def __init__(self, fallback: FloorData, home: Path | None = None,
                 clock: Callable[[], datetime] | None = None) -> None:
        """Use ``fallback`` for products the desk does not provide yet; ``clock`` is for tests."""
        self._fallback = fallback
        self._home = home or desk_home()
        self._path = self._home / DB_NAME
        self._clock = clock or (lambda: datetime.now(NY))

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
            NEWS_ID: (self._query("SELECT 1 FROM news_items LIMIT 1"), _NEWS_COLUMNS, None),
            CALENDAR_ID: (True, _CALENDAR_COLUMNS, None),
            TILES_ID: (self._latest_regime(), _TILE_COLUMNS, None),
            HISTORY_ID: (self._latest_breadth(), _HISTORY_COLUMNS, None),
        }
        out: list[ProductDescriptor] = []
        for product in self._fallback.products():
            found, columns, day = real.get(product.id, (None, (), None))
            if not found:
                out.append(product)
                continue
            title = f"{product.title} ({day})" if day else product.title
            filters = _REAL_FILTERS.get(product.id, product.filters)
            out.append(replace(product, title=title, columns=columns, filters=filters,
                               sample=False))
        tags_day = self._tags_day()
        out.append(ProductDescriptor(
            TAGS_ID, f"News tags ({tags_day})" if tags_day else "News tags", "table",
            ("table",), _TAG_COLUMNS, {"side": ("long", "short")},
        ))
        if run := self._latest_proof():
            out.append(ProductDescriptor(
                PROOF_ID, _proof_title(run), "table", ("table",), _PROOF_COLUMNS, _PROOF_FILTERS,
            ))
        if leaders_day := self._leaders_day():
            out.append(ProductDescriptor(
                LEADERS_ID, f"RS leaders ({leaders_day})", "table", ("table",), _LEADER_COLUMNS,
                {"sector": self._leader_sectors(leaders_day)},
            ))
        out += [ProductDescriptor(f"{ASKED_PREFIX}{p.id}", f"{p.title} (asked)", "table",
                                  ("table",), tuple(p.recipe.columns))
                for p in approved_products(self._home) if p.recipe is not None]
        return out

    def _asked(self, product_id: str) -> list[dict[str, Any]]:
        recipes: dict[str, DataRecipe] = {f"{ASKED_PREFIX}{p.id}": p.recipe
                                          for p in approved_products(self._home)
                                          if p.recipe is not None}
        recipe = recipes.get(product_id)
        return run_recipe(self._home, recipe) if recipe is not None else []

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
        if product_id == NEWS_ID and (news := self._news(filters.get("tone"))) is not None:
            return news
        if product_id == TAGS_ID:
            return self._tags(filters.get("side"))
        if product_id == CALENDAR_ID:
            return self._calendar(filters.get("importance"))
        if product_id == TILES_ID and (tiles := self._tiles()):
            return tiles
        if product_id == HISTORY_ID and (history := self._history()):
            return history
        if product_id.startswith(ASKED_PREFIX):
            return self._asked(product_id)
        return self._fallback.rows(product_id, filters)

    def _tiles(self) -> list[dict[str, Any]]:
        """Five market tiles: regime, above 50-day, highs and lows, ideas, leading sector."""
        regimes = self._query_all(
            "SELECT regime FROM regime_snapshot ORDER BY date DESC LIMIT ?", (HISTORY_DAYS,))
        if not regimes:
            return []
        current = regimes[0][0]
        streak = next((i for i, r in enumerate(regimes) if r[0] != current), len(regimes))
        tiles = [{"title": "Regime", "value": current, "note": f"trend · day {streak}"}]
        breadth = self._query_all(
            "SELECT date, pct_above_50, new_highs, new_lows FROM breadth_daily "
            "ORDER BY date DESC LIMIT 6")
        if breadth:
            day, p50, highs, lows = breadth[0]
            back = breadth[-1][1] if len(breadth) == 6 else None
            change = "-" if p50 is None or back is None else f"{p50 - back:+.0f} pts in 5 days"
            tiles += [{"title": "Above 50-day", "value": _pct(p50), "note": change},
                      {"title": "New highs · lows", "value": f"{highs} · {lows}", "note": day}]
        if ideas_day := self._ideas_day():
            counts = dict(self._query_all(
                "SELECT side, COUNT(*) FROM ideas WHERE date = ? AND status = 'list' "
                "GROUP BY side", (ideas_day,)))
            tiles.append({"title": "Ideas", "note": ideas_day,
                          "value": f"{counts.get('long', 0)} L · {counts.get('short', 0)} S"})
        if sectors := self._latest_sectors():
            _day, _rank, sector, rel_1m, *_rest = sectors[0]
            tiles.append({"title": "Leading sector", "value": sector,
                          "note": f"{_signed_pct(rel_1m)} vs SPY 1M"})
        return tiles

    def _history(self) -> list[dict[str, Any]]:
        """Share of stocks above the 50-day line for the last 60 days, oldest first."""
        rows = self._query_all(
            "SELECT date, pct_above_50 FROM breadth_daily WHERE pct_above_50 IS NOT NULL "
            "ORDER BY date DESC LIMIT ?", (HISTORY_DAYS,))
        return [{"date": day, "value": f"{value:.2f}"} for day, value in reversed(rows)]

    def chips(self) -> list[tuple[str, str]]:
        """Header chips as ``(text, tone)``; tone is good, warn, bad or info.

        Chips with no data are left out.
        """
        out: list[tuple[str, str]] = []
        regime = self._query(
            "SELECT regime, fear, vix, vix3m FROM regime_snapshot ORDER BY date DESC LIMIT 1")
        if regime:
            name, fear, vix, vix3m = regime
            tone = {"Uptrend": "good", "Downtrend": "bad"}.get(str(name), "warn")
            out.append((f"{name} trend", tone))
            if fear:
                out.append((f"Fear: {fear}", "info"))
            if vix is not None:
                if vix3m is None:
                    out.append((f"VIX {vix:.1f}", "info"))
                elif vix3m > vix:
                    out.append((f"VIX {vix:.1f} · contango", "info"))
                else:
                    out.append((f"VIX {vix:.1f} · backwardation", "warn"))
        breadth = self._query("SELECT pct_above_50 FROM breadth_daily ORDER BY date DESC LIMIT 1")
        if breadth and breadth[0] is not None:
            p50 = float(breadth[0])
            tone = "good" if p50 >= 60 else "bad" if p50 < 40 else "warn"
            out.append((f"Above 50-day {p50:.0f}%", tone))
        today = self._clock().astimezone(NY).date()
        event = next((e for e in events_between(today, trading_days_after(today, CALENDAR_DAYS))
                      if e.importance == "high"), None)
        if event is not None:
            out.append((f"{event.name} {event.day:%a} {event.time:%H:%M}", "info"))
        return out

    def _news(self, tone: str | None) -> list[dict[str, Any]] | None:
        """Newest headlines with the latest news tone of their stock; ``None`` when none."""
        rows = self._query_all(
            "SELECT n.published, n.title, n.symbol, (SELECT t.tone FROM news_tags t WHERE "
            "t.symbol = n.symbol AND n.symbol <> '' ORDER BY t.date DESC LIMIT 1) "
            "FROM news_items n ORDER BY n.published DESC LIMIT ?", (NEWS_LIMIT,))
        if not rows:
            return None
        out = [{"time": _ny_time(published), "headline": title, "symbol": symbol or "market",
                "tone": t if t in _TONES else "-"} for published, title, symbol, t in rows]
        return [r for r in out if not tone or r["tone"] == tone]

    def _tags_day(self) -> str | None:
        row = self._query("SELECT MAX(date) FROM news_tags")
        return row[0] if row and row[0] else None

    def _tags(self, side: str | None) -> list[dict[str, Any]]:
        day = self._tags_day()
        if day is None:
            return []
        rows = self._query_all(
            "SELECT symbol, side, tone, points, final_score, reason FROM news_tags "
            "WHERE date = ? AND (? IS NULL OR side = ?) ORDER BY final_score DESC, symbol",
            (day, side, side))
        return [{"symbol": sym, "side": sd, "tone": tone, "points": f"{points:.0f}",
                 "final": f"{final:.1f}", "reason": reason}
                for sym, sd, tone, points, final, reason in rows]

    def _calendar(self, importance: str | None) -> list[dict[str, Any]]:
        """Economic events from today to ``CALENDAR_DAYS`` trading days ahead (New York)."""
        today = self._clock().astimezone(NY).date()
        last = trading_days_after(today, CALENDAR_DAYS)
        return [{"date": e.day.strftime("%a %m-%d"), "time": e.time.strftime("%H:%M"),
                 "event": e.name, "importance": e.importance}
                for e in events_between(today, last)
                if not importance or e.importance == importance]

    def feed(self) -> list[dict[str, str]] | None:
        """Return the latest AI feed briefs, newest first, or ``None`` when there are none."""
        rows = self._query_all(
            "SELECT created, data_day, author, kind, text FROM briefs ORDER BY id DESC LIMIT ?",
            (FEED_LIMIT,))
        if not rows:
            return None
        return [{"time": f"{str(created)[11:16]} · {day}", "author": author, "kind": kind,
                 "text": text} for created, day, author, kind, text in rows]

    @property
    def home(self) -> Path:
        """The desk folder this reader uses."""
        return self._path.parent

    def feed_cards(self, now: datetime | None = None) -> list[FeedCard] | None:
        """Return the AI feed cards, newest first, or ``None`` when the desk has none."""
        return feed_cards(self._path.parent, now or self._clock()) or None

    def month_cost(self, month: str | None = None) -> MonthCost | None:
        """Return this month's AI use (New York month), or ``None`` when nothing ran yet."""
        month = month or datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m")
        where = "FROM activity WHERE substr(started, 1, 7) = ?"
        by_employee = self._query_all(
            "SELECT COALESCE(MAX(employee_name), employee), COUNT(*), "
            f"SUM(tokens_in + tokens_out), SUM(cost_usd) {where} "
            "GROUP BY employee ORDER BY 1", (month,))
        if not by_employee:
            return None
        by_model = self._query_all(
            f"SELECT source || ' / ' || model, COUNT(*), SUM(tokens_in + tokens_out), "
            f"SUM(cost_usd) {where} GROUP BY source, model ORDER BY 1", (month,))
        spent = sum(float(r[3] or 0) for r in by_employee)

        def fmt(rows: list[tuple[Any, ...]]) -> list[tuple[str, str, str, str]]:
            return [(str(name), f"{calls:,}", f"{int(tokens or 0):,}", f"${float(cost or 0):.4f}")
                    for name, calls, tokens, cost in rows]

        budget = load_settings(self._path.parent).monthly_budget_usd
        return MonthCost(month, budget, spent, fmt(by_employee), fmt(by_model))

    def report_pages(self) -> list[PageVersion]:
        """Return every report page version, newest day first and newest version first."""
        rows = self._query_all("SELECT id, date, version, title, created FROM canvas_pages "
                               "ORDER BY date DESC, version DESC")
        return [PageVersion(int(i), str(d), int(v), str(t), _ny_saved(str(c)))
                for i, d, v, t, c in rows]

    def weekly_reports(self) -> list[tuple[str, str]]:
        """Return ``(title, text)`` of every weekly report, newest week first."""
        rows = self._query_all("SELECT title, text FROM desk_reports ORDER BY week DESC")
        return [(str(t), str(x)) for t, x in rows]

    def report_page(self, page_id: int) -> tuple[str, str] | None:
        """Return ``(title, html)`` of one report page version, or ``None``."""
        rows = self._query_all("SELECT title, html FROM canvas_pages WHERE id = ?", (page_id,))
        return (str(rows[0][0]), str(rows[0][1])) if rows else None

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


def _ny_saved(created: str) -> str:
    """A UTC ISO time as ``YYYY-MM-DD HH:MM`` New York time; unreadable text is kept."""
    try:
        return datetime.fromisoformat(created).astimezone(NY).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return created


def _ny_time(published: str) -> str:
    try:
        return datetime.fromisoformat(published).astimezone(NY).strftime("%m-%d %H:%M")
    except ValueError:
        return "-"


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
