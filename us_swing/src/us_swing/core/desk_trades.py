"""
Module: MD-MKT-008.001.M01 — core/desk_trades.py
Parent SRD: SRD-MKT-008.001
Also: SRD-MKT-008.002 (target), SRD-MKT-008.003 (state and expiry), SRD-MKT-008.004
(trade approval and outcome rows), SRD-MKT-008.005 (app process only), SRD-MKT-008.006 (log lines)

Lead picks the Master user may send to Execution. Shared by the GUI (Approvals waiting)
and the app service (re-send on start); it reads ``desk.db`` with plain SQL and never
imports ``desk``, ``market`` or ``gui``. Only the app process writes trade approvals.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Literal, Protocol

from us_swing.core.desk_contract import DB_NAME
from us_swing.core.desk_hiring import _APPROVALS
from us_swing.core.econ_calendar import next_trading_day
from us_swing.data.market_calendar import ET

log = logging.getLogger(__name__)

PickState = Literal["waiting", "approved", "rejected", "expired"]
TRADE_DECISIONS = ("approve", "reject")
_OPEN = time(9, 30)

_PICKS_SQL = """
SELECT l.date, l.side, l.symbol, l.rank, l.reason, i.trigger, i.stop
FROM lead_picks l
JOIN ideas i ON i.date = l.date AND i.side = l.side AND i.symbol = l.symbol
JOIN risk_check r ON r.date = l.date AND r.side = l.side AND r.symbol = l.symbol
WHERE l.date = ? AND r.verdict = 'pass'
ORDER BY l.side, l.rank
"""


@dataclass(frozen=True)
class TradePick:
    """One lead pick with its trade levels and its Master decision state."""

    day: str
    side: str
    symbol: str
    rank: int
    reason: str
    entry: float
    stop: float
    target: float
    expires: datetime
    state: PickState = "waiting"

    @property
    def subject(self) -> str:
        """The ``approvals`` subject of this pick: ``day:side:symbol``."""
        return f"{self.day}:{self.side}:{self.symbol}"


class DeskTradeSink(Protocol):
    """What the GUI needs from the app to send an approved pick to Execution."""

    def desk_pick_qty(self, pick: TradePick) -> int:
        """Shares the pick would be sized to."""
        ...

    def send_desk_pick(self, pick: TradePick) -> tuple[int, str]:
        """Add the pending signal; return ``(qty, "")`` or ``(0, reason)``."""
        ...

    def dismiss_desk_pick(self, pick: TradePick) -> None:
        """Remove the pick's pending signal again."""
        ...


def pick_target(side: str, entry: float, stop: float, r: float) -> float | None:
    """Target at ``r`` times the entry-to-stop gap; ``None`` when the stop is on the wrong side."""
    if side == "long" and stop < entry:
        return round(entry + r * (entry - stop), 2)
    if side == "short" and stop > entry:
        return round(entry - r * (stop - entry), 2)
    return None


def pick_expiry(day: str) -> datetime:
    """The NYSE open of the first trading day after the pick's data day."""
    return datetime.combine(next_trading_day(date.fromisoformat(day)), _OPEN, tzinfo=ET)


def _connect(home: Path) -> sqlite3.Connection | None:
    path = home / DB_NAME
    return sqlite3.connect(path, timeout=5) if path.exists() else None


def _decisions(con: sqlite3.Connection) -> dict[str, str]:
    """Subject → decision of every trade approval row (first row wins)."""
    try:
        rows = con.execute("SELECT subject, decision FROM approvals WHERE kind = 'trade' "
                           "ORDER BY id").fetchall()
    except sqlite3.OperationalError:
        return {}
    out: dict[str, str] = {}
    for subject, decision in rows:
        out.setdefault(subject, decision)
    return out


def _state(decision: str | None, expires: datetime, now: datetime) -> PickState:
    if decision == "approve":
        return "approved"
    if decision == "reject":
        return "rejected"
    return "expired" if now >= expires else "waiting"


def pick_state(home: Path, pick: TradePick, now: datetime) -> PickState:
    """The pick's state now, from its trade approval row and its expiry."""
    con = _connect(home)
    if con is None:
        return _state(None, pick.expires, now)
    try:
        return _state(_decisions(con).get(pick.subject), pick.expires, now)
    finally:
        con.close()


def trade_picks(home: Path, now: datetime, r: float) -> list[TradePick]:
    """Risk-passed lead picks of the latest lead pick day, with levels and state."""
    con = _connect(home)
    if con is None:
        return []
    try:
        try:
            row = con.execute("SELECT MAX(date) FROM lead_picks").fetchone()
            day = row[0] if row else None
            rows = con.execute(_PICKS_SQL, (day,)).fetchall() if day else []
        except sqlite3.OperationalError:
            return []
        decided = _decisions(con)
    finally:
        con.close()
    picks: list[TradePick] = []
    for d, side, symbol, rank, reason, trigger, stop in rows:
        if trigger is None or stop is None:
            continue
        target = pick_target(side, float(trigger), float(stop), r)
        if target is None:
            continue
        expires = pick_expiry(d)
        picks.append(TradePick(d, side, symbol, int(rank or 0), reason or "", float(trigger),
                               float(stop), target, expires,
                               _state(decided.get(f"{d}:{side}:{symbol}"), expires, now)))
    expired = sum(1 for p in picks if p.state == "expired")
    if expired:
        log.info("[AI Desk] %d trade pick(s) expired without a decision", expired)
    return picks


def record_trade_decision(home: Path, pick: TradePick, decision: str, qty: int,
                          now: datetime) -> str:
    """Add the Master's trade decision row; return an empty text, or why it was refused."""
    if decision not in TRADE_DECISIONS:
        return "unknown decision"
    con = sqlite3.connect(home / DB_NAME, timeout=5)
    try:
        with con:
            con.executescript(_APPROVALS)
            state = _state(_decisions(con).get(pick.subject), pick.expires, now)
            if state == "expired":
                return "this pick expired at the market open"
            if state != "waiting":
                return "this pick is already decided"
            detail = json.dumps({"day": pick.day, "side": pick.side, "symbol": pick.symbol,
                                 "rank": pick.rank, "reason": pick.reason, "entry": pick.entry,
                                 "stop": pick.stop, "target": pick.target, "qty": qty})
            con.execute("INSERT INTO approvals (created, kind, subject, decision, detail) "
                        "VALUES (?, 'trade', ?, ?, ?)",
                        (now.isoformat(timespec="seconds"), pick.subject, decision, detail))
    except sqlite3.Error as exc:
        log.error("[AI Desk] Could not save the decision for %s: %s", pick.symbol, exc)
        return "could not save the decision"
    finally:
        con.close()
    log.info("[AI Desk] Trade pick %s %s %s", pick.side, pick.symbol,
             "approved" if decision == "approve" else "rejected")
    return ""


def record_trade_outcome(home: Path, subject: str, outcome: str, now: datetime) -> None:
    """Note that a pick's signal left Execution (``executed`` or ``dismissed``), so a restart
    does not send it again."""
    con = sqlite3.connect(home / DB_NAME, timeout=5)
    try:
        with con:
            con.executescript(_APPROVALS)
            con.execute("INSERT INTO approvals (created, kind, subject, decision, detail) "
                        "VALUES (?, 'trade_done', ?, ?, '')",
                        (now.isoformat(timespec="seconds"), subject, outcome))
    except sqlite3.Error as exc:
        log.error("[AI Desk] Could not note the %s signal for %s: %s", outcome, subject, exc)
    finally:
        con.close()


def approved_picks(home: Path, trading_day: date) -> list[TradePick]:
    """Approved picks of ``trading_day`` (the day after their data day) whose signal has not
    yet been executed or dismissed."""
    con = _connect(home)
    if con is None:
        return []
    try:
        try:
            rows = con.execute("SELECT subject, decision, detail FROM approvals "
                               "WHERE kind = 'trade' ORDER BY id").fetchall()
            done = {r[0] for r in con.execute(
                "SELECT subject FROM approvals WHERE kind = 'trade_done'")}
        except sqlite3.OperationalError:
            return []
    finally:
        con.close()
    seen: set[str] = set(done)
    out: list[TradePick] = []
    for subject, decision, detail in rows:
        if subject in seen:
            continue
        seen.add(subject)
        if decision != "approve":
            continue
        try:
            d = json.loads(detail)
            pick = TradePick(d["day"], d["side"], d["symbol"], int(d.get("rank", 0)),
                             d.get("reason", ""), float(d["entry"]), float(d["stop"]),
                             float(d["target"]), pick_expiry(d["day"]), "approved")
        except (ValueError, KeyError, TypeError):
            log.warning("[AI Desk] A saved trade approval could not be read and was left out")
            continue
        if next_trading_day(date.fromisoformat(pick.day)) == trading_day:
            out.append(pick)
    return out
