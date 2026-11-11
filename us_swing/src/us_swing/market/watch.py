"""
Module: MD-MKT-013.001.M01 — market/watch.py
Parent SRD: SRD-MKT-013.001
Also: SRD-MKT-013.002 (trigger), SRD-MKT-013.003 (stop and target), SRD-MKT-013.004 (volume),
SRD-MKT-013.005 (gap), SRD-MKT-013.006 (SPY move), SRD-MKT-013.007 (headlines),
SRD-DSK-003.025 (pass log), SRD-DSK-007.009 (trade alerts)

The market watchers, run by the desk every 5 minutes in market hours. Plain code only: it
reads today's 3-minute bars that the app writes into ``candles.db`` and the open trades the
app writes into ``desk.db``, and stores a flag when something happens. It never places,
changes or closes a trade.
"""
from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from pathlib import Path

from us_swing.core.desk_alerts import raise_alert
from us_swing.core.desk_watch import (
    BENCHMARK,
    NY,
    add_flag,
    connect,
    flagged_today,
    open_trades,
    plan_day,
)
from us_swing.market.candles import CANDLE_DB, CandleReader
from us_swing.market.news import Headline, fetch_symbol

log = logging.getLogger(__name__)

STALE = timedelta(minutes=15)
VOLUME_TIMES = 3.0
VOLUME_BARS = 20
GAP_PCT = 3.0
FIRST_BAR = time(9, 36)  # the 09:30 bar must be there to judge a gap
RECENT = timedelta(minutes=10)  # bars since about the last pass
SPY_PCT = 1.5
NEWS_EVERY = timedelta(minutes=15)
OPEN = time(9, 30)
Fetch = Callable[[str], list[Headline] | None]
_last_news: dict[str, datetime] = {}


@dataclass(frozen=True)
class Bar:
    """One 3-minute bar; ``at`` is New York time."""

    at: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class Idea:
    """One listed idea of the plan day."""

    side: str
    symbol: str
    trigger: float
    stop: float


def today_bars(candles: Path, symbols: Sequence[str], now: datetime) -> dict[str, list[Bar]]:
    """Today's (New York) 3-minute bars for ``symbols``, oldest first; read-only."""
    if not candles.exists() or not symbols:
        return {}
    day = now.astimezone(NY).date()
    since = datetime.combine(day, time(0, 0), NY).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S")
    marks = ",".join("?" * len(symbols))
    con = sqlite3.connect(f"{candles.as_uri()}?mode=ro", uri=True, timeout=2)
    try:
        rows = con.execute(
            f"SELECT symbol, datetime, open, high, low, close, volume FROM price_3m "
            f"WHERE symbol IN ({marks}) AND datetime >= ? ORDER BY datetime",
            (*symbols, since)).fetchall()
    except sqlite3.Error:
        return {}
    finally:
        con.close()
    out: dict[str, list[Bar]] = {}
    for sym, at, o, h, lo, c, v in rows:
        when = datetime.fromisoformat(str(at)).replace(tzinfo=UTC).astimezone(NY)
        out.setdefault(str(sym), []).append(Bar(when, float(o), float(h), float(lo), float(c),
                                                float(v or 0)))
    return out


def plan_ideas(home: Path, day: str) -> tuple[list[Idea], list[str]]:
    """Listed ideas (with trigger and stop) and lead picks of the newest plan day."""
    con = connect(home)
    try:
        plan = plan_day(con, day)
        if plan is None:
            return [], []
        ideas = [Idea(str(s), str(y), float(t), float(p)) for s, y, t, p in con.execute(
            'SELECT side, symbol, "trigger", stop FROM ideas WHERE date = ? AND status = '
            "'list' AND \"trigger\" IS NOT NULL AND stop IS NOT NULL", (plan,))]
        has_picks = con.execute("SELECT 1 FROM sqlite_master WHERE name = 'lead_picks'"
                                ).fetchone()
        picks = [str(r[0]) for r in con.execute(
            "SELECT symbol FROM lead_picks WHERE date = ?", (plan,))] if has_picks else []
        return ideas, picks
    finally:
        con.close()


def prev_closes(candles: Path, home: Path, symbols: Sequence[str], day: str
                ) -> dict[str, float]:
    """The last daily close before ``day`` for each symbol that has one."""
    try:
        closes = CandleReader(candles, home).read(symbols).closes
    except (FileNotFoundError, sqlite3.Error):
        return {}
    out: dict[str, float] = {}
    for sym in closes.columns:
        series = closes[sym].dropna()
        before = series[[str(i)[:10] < day for i in series.index]]
        if not before.empty:
            out[str(sym)] = float(before.iloc[-1])
    return out


class _Pass:
    """One watcher pass: collects new flags."""

    def __init__(self, home: Path, now: datetime) -> None:
        self.home, self.now = home, now
        self.day = now.astimezone(NY).date().isoformat()
        self.kinds: list[str] = []

    def flag(self, kind: str, symbol: str, detail: str, price: float,
             daily: bool = False, key: str = "") -> bool:
        """Store one flag; ``daily`` keeps it to once a day for that ``key``."""
        if daily and flagged_today(self.home, kind, symbol, self.day, key):
            return False
        if add_flag(self.home, kind, symbol, detail, price, self.now, key) is None:
            return False
        self.kinds.append(kind)
        return True


def _fresh(bars: dict[str, list[Bar]], now: datetime) -> dict[str, list[Bar]]:
    return {s: b for s, b in bars.items() if b and now - b[-1].at <= STALE}


def _triggers(p: _Pass, ideas: Sequence[Idea], bars: dict[str, list[Bar]]) -> None:
    for idea in ideas:
        got = bars.get(idea.symbol)
        if not got:
            continue
        hit = (max(b.high for b in got) >= idea.trigger if idea.side == "long"
               else min(b.low for b in got) <= idea.trigger)
        if hit:
            p.flag("trigger_hit", idea.symbol, f"{idea.side} trigger {idea.trigger:.2f}",
                   got[-1].close, daily=True, key=f"{idea.side} trigger {idea.trigger:.2f}")


def _trades(p: _Pass, bars: dict[str, list[Bar]]) -> None:
    for trade in open_trades(p.home):
        got = bars.get(trade.symbol)
        if not got:
            continue
        last, long_ = got[-1], trade.side == "long"
        recent = [b for b in got if p.now - b.at <= RECENT] or [last]
        low, high = min(b.low for b in recent), max(b.high for b in recent)
        has_stop = trade.stop > 0  # a stop of 0 means the trade has none
        if has_stop and ((low <= trade.stop) if long_ else (high >= trade.stop)):
            if p.flag("stop_touch", trade.symbol, f"{trade.side} stop {trade.stop:.2f}",
                      last.close, daily=True, key=f"stop {trade.stop:.2f}"):
                raise_alert(p.home, "trade_stop", trade.symbol, 0,
                            f"{trade.symbol} {trade.side} trade touched its stop "
                            f"{trade.stop:.2f}; last {last.close:.2f}", p.now)
        target = trade.target
        if target is not None and ((high >= target) if long_ else (low <= target)):
            if p.flag("target_touch", trade.symbol, f"{trade.side} target {target:.2f}",
                      last.close, daily=True, key=f"target {target:.2f}"):
                raise_alert(p.home, "trade_target", trade.symbol, 0,
                            f"{trade.symbol} {trade.side} trade touched its target "
                            f"{target:.2f}; last {last.close:.2f}", p.now)


def _volume(p: _Pass, symbols: Sequence[str], bars: dict[str, list[Bar]]) -> None:
    for sym in symbols:
        got = bars.get(sym, [])
        if len(got) <= VOLUME_BARS:
            continue
        before = got[-VOLUME_BARS - 1:-1]
        mean = sum(b.volume for b in before) / len(before)
        if mean > 0 and got[-1].volume >= VOLUME_TIMES * mean:
            p.flag("volume_spike", sym, f"{got[-1].volume / mean:.1f} times the usual volume",
                   got[-1].close)


def _gaps(p: _Pass, symbols: Sequence[str], bars: dict[str, list[Bar]],
          prev: dict[str, float]) -> None:
    for sym in symbols:
        got, close = bars.get(sym), prev.get(sym)
        if not got or not close or got[0].at.time() > FIRST_BAR:
            continue  # no previous close, or the day's first bar is missing
        pct = (got[0].open / close - 1) * 100
        if abs(pct) > GAP_PCT:
            p.flag("gap", sym, f"opened {pct:+.1f}% from the last close", got[0].open,
                   daily=True, key="gap")


def _spy(p: _Pass, bars: dict[str, list[Bar]], prev: dict[str, float]) -> None:
    got, close = bars.get(BENCHMARK), prev.get(BENCHMARK)
    if not got or not close:
        return
    pct = (got[-1].close / close - 1) * 100
    if abs(pct) > SPY_PCT:
        way = "up" if pct > 0 else "down"
        p.flag("regime_move", BENCHMARK, f"SPY {pct:+.1f}% from the last close", got[-1].close,
               daily=True, key=f"SPY {way}")


def _seen_titles(home: Path, symbol: str) -> set[str]:
    con = connect(home)
    try:
        has = con.execute("SELECT 1 FROM sqlite_master WHERE name = 'news_items'").fetchone()
        rows = con.execute("SELECT title FROM news_items WHERE symbol = ?",
                           (symbol,)).fetchall() if has else []
    finally:
        con.close()
    return {str(r[0]) for r in rows}


def _headlines(p: _Pass, symbols: Sequence[str], bars: dict[str, list[Bar]],
               fetch: Fetch) -> None:
    last = _last_news.get(str(p.home))
    if last is not None and p.now - last < NEWS_EVERY:
        return
    _last_news[str(p.home)] = p.now
    opened = datetime.combine(p.now.astimezone(NY).date(), OPEN, NY)
    for sym in symbols:
        found = fetch(sym)
        if not found:
            continue
        seen = _seen_titles(p.home, sym)
        for item in found:
            if item.published < opened or item.title in seen:
                continue
            if flagged_today(p.home, "headline", sym, p.day, item.title[:120]):
                continue
            price = bars[sym][-1].close if bars.get(sym) else 0.0
            if p.flag("headline", sym, item.title[:300], price, key=item.title[:120]):
                break


def run_watch(home: Path, now: datetime, candles: Path = CANDLE_DB,
              fetch: Fetch = fetch_symbol) -> int:
    """Run every watcher once; return how many new flags were stored."""
    p = _Pass(home, now)
    ideas, picks = plan_ideas(home, p.day)
    trade_syms = [t.symbol for t in open_trades(home)]
    plan_syms = list(dict.fromkeys([i.symbol for i in ideas] + picks))
    watched = list(dict.fromkeys(plan_syms + trade_syms + [BENCHMARK]))
    bars = _fresh(today_bars(candles, watched, now), now)
    prev = prev_closes(candles, home, plan_syms + [BENCHMARK], p.day)
    news_syms = list(dict.fromkeys(picks + trade_syms))
    checks: tuple[tuple[str, Callable[[], None]], ...] = (
        ("trigger", lambda: _triggers(p, ideas, bars)),
        ("trade", lambda: _trades(p, bars)),
        ("volume", lambda: _volume(p, plan_syms, bars)),
        ("gap", lambda: _gaps(p, plan_syms, bars, prev)),
        ("market", lambda: _spy(p, bars, prev)),
        ("headline", lambda: _headlines(p, news_syms, bars, fetch)),
    )
    for name, check in checks:
        try:
            check()
        except Exception:  # noqa: BLE001 — one watcher failing never stops the others
            log.exception("[Watch] The %s watcher failed", name)
    if p.kinds:
        log.info("[Watch] %d new flag(s): %s", len(p.kinds), ", ".join(sorted(set(p.kinds))))
    return len(p.kinds)
