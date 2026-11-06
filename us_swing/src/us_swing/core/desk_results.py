"""
Module: MD-MKT-009.005.M03 — core/desk_results.py
Parent SRD: SRD-MKT-009.005
Also: SRD-MKT-009.006 (results view and breakdowns)

How lead picks turned out. The app adds a ``pick_trades`` row when an AI Desk trade
closes; the GUI Results section and the weekly report read the shared results view.
Plain SQL on ``desk.db``; this module imports neither ``desk``, ``market`` nor ``gui``,
and groups results by decision and input, never by employee name.
"""
from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from us_swing.core.desk_contract import DB_NAME
from us_swing.core.desk_trades import pick_expiry

log = logging.getLogger(__name__)

_TRADES = """
CREATE TABLE IF NOT EXISTS pick_trades (
    id INTEGER PRIMARY KEY, created TEXT, subject TEXT, symbol TEXT, side TEXT,
    entry_time TEXT, entry REAL, exit_time TEXT, exit REAL, qty INTEGER, pnl REAL, r REAL,
    exit_reason TEXT
);
CREATE TRIGGER IF NOT EXISTS pick_trades_no_update BEFORE UPDATE ON pick_trades
BEGIN SELECT RAISE(ABORT, 'pick_trades is append-only'); END;
CREATE TRIGGER IF NOT EXISTS pick_trades_no_delete BEFORE DELETE ON pick_trades
BEGIN SELECT RAISE(ABORT, 'pick_trades is append-only'); END;
"""
FINISHED = ("stop", "target", "time")


@dataclass(frozen=True)
class Group:
    """Paper totals of one group of picks."""

    label: str
    picks: int = 0
    fills: int = 0
    finished: int = 0
    targets: int = 0
    avg_r: float | None = None

    @property
    def hit_rate(self) -> float | None:
        """Share of finished picks that reached the target."""
        return self.targets / self.finished if self.finished else None


@dataclass(frozen=True)
class PickLine:
    """One lead pick with its decision, paper result and real P&L."""

    day: str
    side: str
    symbol: str
    decision: str
    status: str
    r: float | None
    real_pnl: float | None
    grade: str
    tone: str
    entered: bool = False


@dataclass(frozen=True)
class RealTotals:
    """Totals of the closed AI Desk trades."""

    trades: int = 0
    wins: int = 0
    pnl: float = 0.0
    avg_r: float | None = None


@dataclass(frozen=True)
class ResultsView:
    """Everything the Results section and the weekly report show."""

    picks: tuple[PickLine, ...]
    total: Group
    breakdowns: dict[str, tuple[Group, ...]]
    real: RealTotals


def _risk_r(side: str, entry: float, stop: float, exit_: float) -> float | None:
    risk = entry - stop if side == "long" else stop - entry
    if risk <= 0:
        return None
    return round(((exit_ - entry) if side == "long" else (entry - exit_)) / risk, 2)


def record_pick_trade(home: Path, snap: Any, now: datetime) -> None:
    """Add the real result of one closed AI Desk trade cycle (app process only)."""
    side = "long" if str(snap.direction).upper() == "LONG" else "short"
    entry = float(snap.entry_price)
    exit_ = None if snap.exit_price is None else float(snap.exit_price)
    con = sqlite3.connect(home / DB_NAME, timeout=5)
    try:
        with con:
            con.executescript(_TRADES)
            try:
                row = con.execute(
                    "SELECT subject FROM approvals WHERE kind = 'trade_done' AND decision = "
                    "'executed' AND subject LIKE ? ORDER BY id DESC LIMIT 1",
                    (f"%:{side}:{snap.symbol}",)).fetchone()
            except sqlite3.OperationalError:
                row = None
            con.execute(
                "INSERT INTO pick_trades (created, subject, symbol, side, entry_time, entry, "
                "exit_time, exit, qty, pnl, r, exit_reason) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (now.isoformat(timespec="seconds"), row[0] if row else "", snap.symbol, side,
                 snap.entry_time, entry, snap.exit_time, exit_, int(snap.entry_qty or 0),
                 snap.realized_pnl_usd,
                 _risk_r(side, entry, float(snap.hard_stop_loss or 0.0), exit_)
                 if snap.hard_stop_loss and exit_ is not None else None, snap.exit_reason))
    except sqlite3.Error as exc:
        log.error("[Results] Could not save the closed AI Desk trade for %s: %s", snap.symbol, exc)
        return
    finally:
        con.close()
    log.info("[Results] Closed AI Desk trade %s %s saved", side, snap.symbol)


def _rows(con: sqlite3.Connection, sql: str, args: tuple[Any, ...] = ()) -> list[Any]:
    try:
        return con.execute(sql, args).fetchall()
    except sqlite3.OperationalError:
        return []


def _group(label: str, lines: list[PickLine]) -> Group:
    done = [p for p in lines if p.status in FINISHED and p.r is not None]
    return Group(label, len(lines), sum(1 for p in lines if p.entered),
                 len(done), sum(1 for p in done if p.status == "target"),
                 round(sum(p.r for p in done if p.r is not None) / len(done), 2) if done else None)


def _by(lines: list[PickLine], key: Callable[[PickLine], str]) -> tuple[Group, ...]:
    labels = sorted({key(p) for p in lines})
    return tuple(_group(lab, [p for p in lines if key(p) == lab]) for lab in labels)


def results_view(home: Path, now: datetime, first: str | None = None,
                 last: str | None = None) -> ResultsView:
    """Pick results for data days ``first``..``last`` (all days when not given)."""
    path = home / DB_NAME
    picks: list[Any] = []
    decided: dict[str, str] = {}
    graded: dict[tuple[str, str, str], str] = {}
    toned: dict[tuple[str, str, str], str] = {}
    paper: dict[tuple[str, str, str], tuple[str, float | None, bool]] = {}
    pnl: dict[str, float] = {}
    trades: list[Any] = []
    if path.exists():
        con = sqlite3.connect(path, timeout=5)
        try:
            picks = _rows(con, "SELECT date, side, symbol FROM lead_picks ORDER BY date DESC, "
                               "side, rank")
            for subject, decision in _rows(con, "SELECT subject, decision FROM approvals "
                                                "WHERE kind = 'trade' ORDER BY id"):
                decided.setdefault(subject, decision)
            graded = {(d, s, y): g for d, s, y, g in _rows(
                con, "SELECT date, side, symbol, grade FROM setup_review")}
            toned = {(d, s, y): t for d, s, y, t in _rows(
                con, "SELECT date, side, symbol, tone FROM news_tags")}
            paper = {(d, s, y): (st, r, e is not None) for d, s, y, st, r, e in _rows(
                con, "SELECT date, side, symbol, status, r, entry_day FROM pick_results")}
            trades = _rows(con, "SELECT subject, pnl, r, exit_time FROM pick_trades")
        finally:
            con.close()
    for subject, value, _r, _t in trades:
        if subject:
            pnl[subject] = pnl.get(subject, 0.0) + float(value or 0.0)
    lines: list[PickLine] = []
    for d, side, sym in picks:
        if (first and d < first) or (last and d > last):
            continue
        key, subject = (d, side, sym), f"{d}:{side}:{sym}"
        decision = {"approve": "approved", "reject": "rejected"}.get(
            decided.get(subject, ""), "expired" if now >= pick_expiry(d) else "waiting")
        status, r, entered = paper.get(key, ("", None, False))
        lines.append(PickLine(d, side, sym, decision, status, r, pnl.get(subject),
                              graded.get(key) or "none", toned.get(key) or "none", entered))
    in_range = [t for t in trades if not ((first and str(t[3] or "")[:10] < first)
                                          or (last and str(t[3] or "")[:10] > last))]
    rs = [float(t[2]) for t in in_range if t[2] is not None]
    real = RealTotals(len(in_range), sum(1 for t in in_range if (t[1] or 0) > 0),
                      round(sum(float(t[1] or 0.0) for t in in_range), 2),
                      round(sum(rs) / len(rs), 2) if rs else None)
    return ResultsView(tuple(lines), _group("All", lines), {
        "Decision": _by(lines, lambda p: p.decision),
        "Setup grade": _by(lines, lambda p: p.grade),
        "News tone": _by(lines, lambda p: p.tone),
    }, real)


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{round(100 * value)}%"


def _num(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}"


def group_cells(g: Group) -> list[str]:
    """Table cells of a group: label, picks, fills, finished, hit rate, average R."""
    return [g.label, str(g.picks), str(g.fills), str(g.finished), _pct(g.hit_rate), _num(g.avg_r)]


def results_lines(view: ResultsView) -> list[str]:
    """Plain text lines of a results view for the weekly report."""
    if not view.picks:
        return ["No lead picks this week"]
    t = view.total
    lines = [f"Paper: {t.picks} pick(s), {t.fills} filled, {t.finished} finished, "
             f"hit rate {_pct(t.hit_rate)}, average R {_num(t.avg_r)}"]
    for name, groups in view.breakdowns.items():
        lines.append(f"{name}: " + "; ".join(
            f"{g.label} {g.picks} pick(s), hit {_pct(g.hit_rate)}, R {_num(g.avg_r)}"
            for g in groups))
    r = view.real
    lines.append(f"Real: {r.trades} trade(s), {r.wins} win(s), P&L {r.pnl:.2f}, "
                 f"average R {_num(r.avg_r)}")
    return lines
