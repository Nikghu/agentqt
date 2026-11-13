"""
Module: MD-MKT-020.002.M01 — core/desk_day.py
Parent SRD: SRD-MKT-020.002
Also: SRD-MKT-020.003 (stand-up), .005 (clash), .006 (one huddle a day), .010 (huddle block),
.012-.013 (day call and votes), .017 (vote results stored), .018 (day-call line), .019 (has a
handover), .022 (day-end rows), SRD-GUI-034.078 (tiles), SRD-GUI-035.018 (day strip)

The company day in ``desk.db`` (AI Desk v3 M5): the stand-up built by code, the huddle, the
lead's day call with who agreed, its check after 5 trading days, and the day-end handover.
Shared by the desk and the GUI; only prompt text and display rows, never a trade.
Design: DD-MKT-020.001.D01.
"""
from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from us_swing.core.desk_contract import DB_NAME
from us_swing.core.desk_memory import add_trading_days
from us_swing.data.market_calendar import get_exchange_status

NY = ZoneInfo("America/New_York")
CHECK_DAYS = 5
STANDUP_CHARS = 1200
DEFENSIVE = frozenset({"Utilities", "Consumer Staples", "Health Care", "Real Estate"})
MARKETS = ("Uptrend", "Choppy", "Downtrend")
VOTE_PARTS = {"regime_view": "market", "sector_flow_view": "sector"}
NO_HANDOVER = "No handover note yet."
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)

SCHEMA = """
CREATE TABLE IF NOT EXISTS day_brief (
    day TEXT PRIMARY KEY, standup TEXT DEFAULT '', standup_at TEXT DEFAULT '',
    clash TEXT DEFAULT '', huddle INTEGER DEFAULT 0, huddle_at TEXT DEFAULT '',
    plan_at TEXT DEFAULT '', handover TEXT DEFAULT '', feedback TEXT DEFAULT '[]',
    summary TEXT DEFAULT '', day_end_at TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS decisions (
    day TEXT PRIMARY KEY, market TEXT, favour TEXT, note TEXT, huddle INTEGER, made TEXT,
    due TEXT, status TEXT, market_result TEXT DEFAULT '', sector_result TEXT DEFAULT '',
    spy_move REAL, sector_move REAL, checked TEXT
);
CREATE TABLE IF NOT EXISTS decision_votes (
    day TEXT, skill TEXT, part TEXT, stance TEXT, result TEXT DEFAULT '',
    PRIMARY KEY (day, skill)
);
"""


@dataclass(frozen=True)
class Decision:
    """One day call of the lead and its check."""

    day: str
    market: str
    favour: tuple[str, ...]
    note: str
    huddle: bool
    due: str
    status: str
    market_result: str
    sector_result: str


@dataclass(frozen=True)
class Vote:
    """One expert's stance on a day call."""

    skill: str
    part: str
    stance: str
    result: str


@dataclass(frozen=True)
class DayView:
    """What the Command tiles show: the latest day call and the latest handover note."""

    call: Decision | None
    votes: tuple[Vote, ...]
    handover_day: str
    handover: tuple[str, ...]


# ── connections ─────────────────────────────────────────────────────────────


def connect(home: Path) -> sqlite3.Connection:
    """Open ``desk.db`` for writing and make sure the day tables exist."""
    home.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(home / DB_NAME, timeout=10)
    con.executescript(SCHEMA)
    return con


def _read_only(home: Path) -> sqlite3.Connection | None:
    path = home / DB_NAME
    if not path.exists():
        return None
    return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=10)


def _has(con: sqlite3.Connection, table: str) -> bool:
    return con.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                       (table,)).fetchone() is not None


def _one(home: Path, table: str, sql: str, params: tuple[object, ...]
         ) -> tuple[object, ...] | None:
    con = _read_only(home)
    if con is None:
        return None
    try:
        if not _has(con, table):
            return None
        row = con.execute(sql, params).fetchone()
        return tuple(row) if row else None
    finally:
        con.close()


def _all(home: Path, table: str, sql: str, params: tuple[object, ...] = ()
         ) -> list[tuple[object, ...]]:
    con = _read_only(home)
    if con is None:
        return []
    try:
        if not _has(con, table):
            return []
        return [tuple(r) for r in con.execute(sql, params).fetchall()]
    finally:
        con.close()


def _stamp(now: datetime) -> str:
    return now.astimezone(NY).isoformat(timespec="seconds")


def _set(home: Path, day: str, **values: object) -> None:
    cols = ", ".join(f"{k} = ?" for k in values)
    con = connect(home)
    try:
        with con:
            con.execute("INSERT OR IGNORE INTO day_brief (day) VALUES (?)", (day,))
            con.execute(f"UPDATE day_brief SET {cols} WHERE day = ?",  # noqa: S608 — own keys
                        (*values.values(), day))
    finally:
        con.close()


def _list(text: object) -> tuple[str, ...]:
    try:
        data = json.loads(str(text or "[]"))
    except ValueError:
        return ()
    return tuple(str(x) for x in data) if isinstance(data, list) else ()


# ── stand-up (SRD-MKT-020.003, .004) ───────────────────────────────────────


def last_handover(home: Path, before: str) -> tuple[str, tuple[str, ...]]:
    """The newest handover note before ``before`` as ``(day, lines)``; ``("", ())`` if none."""
    row = _one(home, "day_brief", "SELECT day, handover FROM day_brief WHERE day < ? AND "
               "handover != '' ORDER BY day DESC LIMIT 1", (before,))
    return (str(row[0]), _list(row[1])) if row else ("", ())


def _regime_line(home: Path, day: str) -> str:
    row = _one(home, "regime_view", "SELECT regime, confidence, reasons FROM regime_view "
               "WHERE date = ?", (day,))
    if row is None:
        return "Regime view: no view today."
    reasons = _list(row[2])
    first = f" {reasons[0]}" if reasons else ""
    return f"Regime view: {row[0]}, confidence {float(str(row[1] or 0)):.0%}.{first}"


def _sector_line(home: Path, day: str) -> str:
    row = _one(home, "sector_view", "SELECT favour, avoid FROM sector_view WHERE date = ?",
               (day,))
    if row is None:
        return "Sector/flow: no view today."
    favour, avoid = _list(row[0]), _list(row[1])
    return (f"Sector/flow: favour {', '.join(favour) or 'none'}; "
            f"avoid {', '.join(avoid) or 'none'}.")


def _setup_line(home: Path, day: str) -> str:
    rows = _all(home, "setup_review", "SELECT grade FROM setup_review WHERE date = ?", (day,))
    if not rows:
        return "Setup review: no view today."
    count = {g: sum(1 for (x,) in rows if x == g) for g in ("A", "B", "C")}
    return (f"Setup review: {len(rows)} ideas graded: {count['A']} A, {count['B']} B, "
            f"{count['C']} C.")


def _news_line(home: Path, day: str) -> str:
    rows = _all(home, "news_tags", "SELECT tone FROM news_tags WHERE date = ?", (day,))
    if not rows:
        return "News review: no view today."
    bad = sum(1 for (tone,) in rows if tone == "negative")
    return f"News review: {len(rows)} ideas tagged; {bad} with bad news."


def _risk_line(home: Path, day: str) -> str:
    rows = _all(home, "risk_check", "SELECT verdict, by FROM risk_check WHERE date = ?", (day,))
    if not rows:
        return "Risk check: no view today."
    vetoed = [by for verdict, by in rows if verdict == "veto"]
    by_code = sum(1 for by in vetoed if by == "code")
    return (f"Risk check: {len(rows) - len(vetoed)} passed, {len(vetoed)} vetoed "
            f"({by_code} by code).")


def standup_text(home: Path, day: str) -> str:
    """The stand-up for ``day``: yesterday's handover and two short lines per view."""
    hday, lines = last_handover(home, day)
    handover = f"Handover from {hday}: {' / '.join(lines)}" if lines else NO_HANDOVER
    parts = [f"Stand-up for {day}", handover, _regime_line(home, day), _sector_line(home, day),
             _setup_line(home, day), _news_line(home, day), _risk_line(home, day)]
    text = "\n".join(parts)
    return text if len(text) <= STANDUP_CHARS else text[:STANDUP_CHARS - 3] + "..."


def save_standup(home: Path, day: str, text: str, now: datetime) -> None:
    """Keep the stand-up of ``day`` and its time."""
    _set(home, day, standup=text, standup_at=_stamp(now))


# ── clash and huddle (SRD-MKT-020.005, .006, .010) ─────────────────────────


def clash(regime: str | None, favour: Sequence[str]) -> str | None:
    """The clash between the regime view and the sector/flow view, or ``None``."""
    chosen = set(favour)
    if not regime or not chosen:
        return None
    names = ", ".join(favour)
    if regime == "Downtrend" and not chosen & DEFENSIVE:
        return f"Regime view says Downtrend but sector/flow favours {names}."
    if regime == "Uptrend" and chosen <= DEFENSIVE:
        return f"Regime view says Uptrend but sector/flow favours only defensive {names}."
    return None


def views(home: Path, day: str) -> tuple[str | None, tuple[str, ...]]:
    """The day's regime view regime and sector/flow favoured sectors."""
    regime = _one(home, "regime_view", "SELECT regime FROM regime_view WHERE date = ?", (day,))
    sector = _one(home, "sector_view", "SELECT favour FROM sector_view WHERE date = ?", (day,))
    return (str(regime[0]) if regime else None), (_list(sector[0]) if sector else ())


def can_huddle(home: Path) -> bool:
    """True when an employee holds each skill a huddle asks, so the meeting is not refused."""
    held = {str(s) for (s,) in _all(home, "roster", "SELECT DISTINCT skill FROM roster")}
    return set(VOTE_PARTS) <= held


def huddle_called(home: Path, day: str) -> bool:
    """True when a huddle was already called for ``day``."""
    row = _one(home, "day_brief", "SELECT huddle FROM day_brief WHERE day = ?", (day,))
    return bool(row and row[0])


def mark_huddle(home: Path, day: str, why: str, now: datetime) -> None:
    """Note that the huddle of ``day`` was called and why."""
    _set(home, day, huddle=1, clash=why, huddle_at=_stamp(now))


def _meetings(home: Path, day: str) -> list[tuple[object, ...]]:
    return _all(home, "messages", "SELECT id, receiver, state FROM messages WHERE data_day = ? "
                "AND type = 'meeting' ORDER BY id", (day,))


def huddle_open(home: Path, day: str) -> bool:
    """True while a huddle meeting of ``day`` waits for its reply."""
    return any(state == "submitted" for _id, _to, state in _meetings(home, day))


def _names(home: Path) -> dict[str, str]:
    return {str(i): str(n) for i, n in _all(home, "roster", "SELECT id, name FROM roster")}


def huddle_block(home: Path, day: str) -> str:
    """The huddle's clash and each reply; empty when no huddle ran on ``day``."""
    row = _one(home, "day_brief", "SELECT clash FROM day_brief WHERE day = ? AND huddle = 1",
               (day,))
    meetings = _meetings(home, day)
    if row is None or not meetings:
        return ""
    names = _names(home)
    lines = [f"Huddle (one round): {row[0]}"]
    for mid, receiver, _state in meetings:
        reply = _one(home, "messages", "SELECT body, type FROM messages WHERE parent = ? AND "
                     "type = 'reply' ORDER BY id LIMIT 1", (mid,))
        text = "no answer"
        if reply is not None:
            body = json.loads(str(reply[0]) or "{}")
            failed = body.get("verdict", {}).get("result") in ("failed", "refused")
            text = "no answer" if failed else str(body.get("text") or "no answer")
        lines.append(f"{names.get(str(receiver), str(receiver))}: {text}")
    return "\n".join(lines)


# ── day call and votes (SRD-MKT-020.012, .013, .017, .018) ─────────────────


def save_call(home: Path, day: str, market: str, favour: Sequence[str], note: str,
              due: str, now: datetime) -> list[Vote]:
    """Keep the lead's day call of ``day`` and the experts' stances; return the votes.

    A call already checked stays as it is, with its results (a rerun of the same day).
    """
    done = _one(home, "decisions", "SELECT 1 FROM decisions WHERE day = ? AND status = "
                "'checked'", (day,))
    if done:
        return votes_of(home, day)
    regime, chosen = views(home, day)
    votes: list[Vote] = []
    if regime:
        votes.append(Vote("regime_view", "market",
                          "agreed" if regime == market else "disagreed", ""))
    if chosen:
        votes.append(Vote("sector_flow_view", "sector",
                          "agreed" if set(chosen) & set(favour) else "disagreed", ""))
    huddle = huddle_called(home, day)
    con = connect(home)
    try:
        with con:
            con.execute("INSERT OR REPLACE INTO decisions (day, market, favour, note, huddle, "
                        "made, due, status) VALUES (?, ?, ?, ?, ?, ?, ?, 'open')",
                        (day, market, json.dumps(list(favour)), note, int(huddle),
                         _stamp(now), due))
            con.execute("DELETE FROM decision_votes WHERE day = ?", (day,))
            con.executemany("INSERT INTO decision_votes (day, skill, part, stance) "
                            "VALUES (?, ?, ?, ?)",
                            [(day, v.skill, v.part, v.stance) for v in votes])
            con.execute("INSERT OR IGNORE INTO day_brief (day) VALUES (?)", (day,))
            con.execute("UPDATE day_brief SET plan_at = ? WHERE day = ?", (_stamp(now), day))
    finally:
        con.close()
    return votes


def _decision(row: Sequence[object]) -> Decision:
    day, market, favour, note, huddle, due, status, mres, sres = row
    return Decision(str(day), str(market), _list(favour), str(note or ""), bool(huddle),
                    str(due), str(status), str(mres or ""), str(sres or ""))


_DECISION_COLS = "day, market, favour, note, huddle, due, status, market_result, sector_result"


def due_calls(home: Path, last_day: str) -> list[Decision]:
    """Open day calls whose check day is on or before ``last_day``."""
    rows = _all(home, "decisions", f"SELECT {_DECISION_COLS} FROM decisions "  # noqa: S608
                "WHERE status = 'open' AND due <= ? ORDER BY day", (last_day,))
    return [_decision(r) for r in rows]


def votes_of(home: Path, day: str) -> list[Vote]:
    """The votes on the day call of ``day``."""
    rows = _all(home, "decision_votes", "SELECT skill, part, stance, result FROM "
                "decision_votes WHERE day = ? ORDER BY skill", (day,))
    return [Vote(str(s), str(p), str(st), str(r or "")) for s, p, st, r in rows]


def save_results(home: Path, day: str, market_result: str, sector_result: str,
                 spy_move: float, sector_move: float | None, results: Mapping[str, str],
                 checked: str) -> None:
    """Close the day call of ``day`` with its results and each vote's result."""
    con = connect(home)
    try:
        with con:
            con.execute("UPDATE decisions SET status = 'checked', market_result = ?, "
                        "sector_result = ?, spy_move = ?, sector_move = ?, checked = ? "
                        "WHERE day = ?", (market_result, sector_result, round(spy_move, 2),
                                          None if sector_move is None else round(sector_move, 2),
                                          checked, day))
            con.executemany("UPDATE decision_votes SET result = ? WHERE day = ? AND skill = ?",
                            [(r, day, skill) for skill, r in results.items()])
    finally:
        con.close()


def day_call_line(home: Path, skill: str) -> str:
    """One line on the checked day calls ``skill`` voted on; empty when there are none."""
    rows = _all(home, "decision_votes", "SELECT result FROM decision_votes WHERE skill = ? "
                "AND result != ''", (skill,))
    if not rows:
        return ""
    right = sum(1 for (r,) in rows if r == "right")
    wrong = sum(1 for (r,) in rows if r == "wrong")
    return f"Day calls you voted on: {len(rows)} checked, {right} right, {wrong} wrong."


# ── day-end (SRD-MKT-020.019, .022) ────────────────────────────────────────


def _trading(day: datetime) -> bool:
    return get_exchange_status(datetime.combine(day.date(), time(12, 0), NY)) == "open"


def day_end_day(now: datetime) -> str:
    """The latest closed trading day: today from 16:00 New York time, else the one before."""
    now_ny = now.astimezone(NY)
    if _trading(now_ny) and now_ny.time() >= MARKET_CLOSE:
        return now_ny.date().isoformat()
    day = now_ny - timedelta(days=1)
    while not _trading(day):
        day -= timedelta(days=1)
    return day.date().isoformat()


def plan_day(home: Path, closed: str) -> str:
    """The data day of the plan traded on ``closed``: the newest plan day before it.

    The morning plan uses the last full day of candles, so the plan traded on a day has an
    earlier data day. Empty when no plan or stand-up was kept before ``closed``.
    """
    rows = [_one(home, "day_brief", "SELECT MAX(day) FROM day_brief WHERE day < ? AND "
                 "(standup != '' OR plan_at != '')", (closed,)),
            _one(home, "lead_picks", "SELECT MAX(date) FROM lead_picks WHERE date < ?",
                 (closed,))]
    days = [str(r[0]) for r in rows if r and r[0]]
    return max(days, default="")



def has_handover(home: Path, day: str) -> bool:
    """True when ``day`` already has its handover note."""
    row = _one(home, "day_brief", "SELECT handover FROM day_brief WHERE day = ?", (day,))
    return bool(row and _list(row[0]))


def save_day_end(home: Path, day: str, handover: Sequence[str],
                 feedback: Sequence[tuple[str, str]], summary: str, now: datetime) -> None:
    """Keep the day-end of ``day``: handover lines, feedback per skill and the code summary."""
    _set(home, day, handover=json.dumps(list(handover)),
         feedback=json.dumps([list(f) for f in feedback]), summary=summary,
         day_end_at=_stamp(now))


def decision_of(home: Path, day: str) -> Decision | None:
    """The day call of ``day``, or ``None``."""
    row = _one(home, "decisions", f"SELECT {_DECISION_COLS} FROM decisions "  # noqa: S608
               "WHERE day = ?", (day,))
    return _decision(row) if row else None


def clash_of(home: Path, day: str) -> str:
    """The huddle's clash text of ``day``; empty when no huddle was called."""
    row = _one(home, "day_brief", "SELECT clash FROM day_brief WHERE day = ? AND huddle = 1",
               (day,))
    return str(row[0]) if row else ""


# ── GUI reads (SRD-GUI-034.078, SRD-GUI-035.018) ────────────────────────────


def day_view(home: Path) -> DayView:
    """The latest day call with its votes and the latest handover note."""
    row = _one(home, "decisions", f"SELECT {_DECISION_COLS} FROM decisions "  # noqa: S608
               "ORDER BY day DESC LIMIT 1", ())
    call = _decision(row) if row else None
    hday, lines = last_handover(home, "9999-12-31")
    return DayView(call, tuple(votes_of(home, call.day)) if call else (), hday, lines)


def _clock(stamp: object) -> str:
    text = str(stamp or "")
    return text[11:16] if len(text) >= 16 else ""


def day_phases(home: Path, day: str, now: datetime) -> list[tuple[str, str]]:
    """Phases of the plan of data day ``day`` (traded the next trading day) as
    ``(name, state)``; state is a time, ``open``, ``done``, ``skipped`` or ``waiting``."""
    row = _one(home, "day_brief", "SELECT standup_at, huddle, huddle_at, plan_at, day_end_at "
               "FROM day_brief WHERE day = ?", (day,))
    standup, huddle, huddle_at, plan, end = row if row else ("", 0, "", "", "")
    planned = bool(plan)
    now_ny = now.astimezone(NY)
    traded = add_trading_days(day, 1)
    today = now_ny.date().isoformat()
    if today > traded or (today == traded and now_ny.time() >= MARKET_CLOSE):
        market = "done"
    elif today == traded and now_ny.time() >= MARKET_OPEN:
        market = "open"
    else:
        market = "waiting"
    return [
        ("Stand-up", _clock(standup) or "waiting"),
        ("Huddle", _clock(huddle_at) if huddle else ("skipped" if planned else "waiting")),
        ("Plan", _clock(plan) or "waiting"),
        ("Market hours", market),
        ("Day-end", _clock(end) or "waiting"),
    ]


def skill_names(home: Path) -> dict[str, str]:
    """Employee name per skill (the first id that holds it), for the GUI."""
    rows = _all(home, "roster", "SELECT skill, name FROM roster ORDER BY id DESC")
    return {str(s): str(n) for s, n in rows}
