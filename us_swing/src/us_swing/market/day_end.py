"""
Module: MD-MKT-020.020.M08 — market/day_end.py
Parent SRD: SRD-MKT-020.020
Also: SRD-MKT-020.021 (answer), .022 (rows, memory notes, feed item), .024 (log line)

The day-end skill (AI Desk v3 M5): after the close, one lead call reads what happened to the
day's plan and writes the handover note for the next morning's stand-up and one feedback
line per expert. Facts and the summary are built by code. Never places, changes or closes
a trade. Uses only ``core`` types; it never imports the desk harness.
Design: DD-MKT-020.001.D01 §9.
"""
from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from us_swing.core.desk_agents import AgentContext, Facts, FeedItem
from us_swing.core.desk_ai_settings import load_settings
from us_swing.core.desk_contract import DB_NAME
from us_swing.core.desk_day import (
    clash_of,
    day_end_day,
    decision_of,
    has_handover,
    huddle_block,
    plan_day,
    save_day_end,
)
from us_swing.core.desk_memory import write as write_memory
from us_swing.core.desk_msg import Remember

log = logging.getLogger(__name__)

KEY = "day_end"
EXPERTS: tuple[str, ...] = ("regime_view", "sector_flow_view", "setup_review", "news_review",
                            "risk_check")
MAX_FLAGS = 15
MAX_CHECKINS = 3
CHECKIN_CHARS = 300
Line = Annotated[str, StringConstraints(min_length=3, max_length=120)]


class Feedback(BaseModel):
    """One feedback line for the expert that does one skill."""

    model_config = ConfigDict(extra="forbid")

    skill: str = Field(max_length=40)
    text: str = Field(min_length=3, max_length=150)


class DayEnd(BaseModel):
    """The day-end answer: the handover note and the feedback lines."""

    model_config = ConfigDict(extra="forbid")

    handover: list[Line] = Field(min_length=1, max_length=5)
    feedback: list[Feedback] = Field(default_factory=list, max_length=5)


def _now() -> datetime:
    return datetime.now(ZoneInfo("America/New_York"))


def _rows(home: Path, sql: str, params: tuple[object, ...]) -> list[tuple[object, ...]]:
    path = home / DB_NAME
    if not path.exists():
        return []
    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=10)
    try:
        return [tuple(r) for r in con.execute(sql, params).fetchall()]
    except sqlite3.OperationalError:
        return []  # a table not made yet
    finally:
        con.close()


def _picks(home: Path, plan: str) -> list[tuple[str, str, str]]:
    rows = _rows(home, "SELECT p.side, p.symbol, COALESCE(r.status, '') FROM lead_picks p "
                 "LEFT JOIN pick_results r ON r.date = p.date AND r.side = p.side AND "
                 "r.symbol = p.symbol WHERE p.date = ? ORDER BY p.side, p.rank", (plan,))
    return [(str(s), str(y), str(st)) for s, y, st in rows]


def _flags(home: Path, traded: str) -> list[tuple[str, str, str]]:
    rows = _rows(home, "SELECT kind, symbol, COALESCE(verdict, '') FROM watch_flags "
                 "WHERE day = ? ORDER BY id LIMIT ?", (traded, MAX_FLAGS))
    return [(str(k), str(s), str(v)) for k, s, v in rows]


def _checkins(home: Path, traded: str) -> list[str]:
    rows = _rows(home, "SELECT text FROM briefs WHERE text LIKE 'Check-in %' AND "
                 "substr(created, 1, 10) = ? ORDER BY id LIMIT ?", (traded, MAX_CHECKINS))
    return [str(t)[:CHECKIN_CHARS] for (t,) in rows]


def _open_trades(home: Path) -> int:
    rows = _rows(home, "SELECT COUNT(*) FROM open_trades", ())
    return int(str(rows[0][0])) if rows else 0


def summary_text(picks: list[tuple[str, str, str]], flags: list[tuple[str, str, str]],
                 huddle: bool, market: str) -> str:
    """The code summary of the day: picks, flags, huddle and call."""
    triggered = sum(1 for _s, _y, st in picks if st and st != "pending")
    stopped = sum(1 for _s, _y, st in picks if st == "stop")
    return (f"{len(picks)} picks: {triggered} triggered, {stopped} stopped; {len(flags)} "
            f"flags; huddle {'yes' if huddle else 'no'}; call {market or 'none'}")


class DayEndSkill:
    """The day-end skill (a ``Skill``)."""

    key = KEY
    needs: tuple[str, ...] = ()
    answer = DayEnd

    def __init__(self, clock: Callable[[], datetime] = _now) -> None:
        """``clock`` is New York time; injectable for tests."""
        self._clock = clock

    def facts(self, home: Path) -> Facts:
        """Build the facts of the latest closed trading day's plan; no AI call."""
        traded = day_end_day(self._clock())
        plan = plan_day(home, traded)
        if not plan:
            return Facts("", traded, False, f"no plan kept before {traded}")
        if has_handover(home, plan):
            return Facts("", plan, False, f"day-end for {traded} already written")
        call = decision_of(home, plan)
        call_line = (f"Day call: {call.market}, favour {', '.join(call.favour)}. {call.note}"
                     if call else "No day call today.")
        huddle = huddle_block(home, plan) or "No huddle."
        picks = _picks(home, plan)
        flags = _flags(home, traded)
        checkins = _checkins(home, traded)
        lines = [
            f"Day-end for {traded} (plan of data day {plan})",
            call_line.strip(),
            huddle,
            "Picks:\n" + ("\n".join(f"  {s} {y}: {st or 'no result yet'}" for s, y, st in picks)
                          or "  (no picks)"),
            "Watch flags:\n" + ("\n".join(f"  {k} {s}: {v or 'no verdict'}"
                                          for k, s, v in flags) or "  (none)"),
            "Check-in notes:\n" + ("\n".join(f"  {c}" for c in checkins) or "  (none)"),
            f"Open trades: {_open_trades(home)}",
            "Experts you may give feedback to (one line each at most): " + ", ".join(EXPERTS),
        ]
        return Facts("\n\n".join(lines), plan, True)

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        """Ask for the handover and feedback; keep them, and the feedback in memory."""
        answer = ctx.ask(facts.text, DayEnd)
        if answer is None:
            return []
        home, plan, now = ctx.home, facts.data_day, self._clock()
        traded = day_end_day(now)
        feedback: list[tuple[str, str]] = []
        for item in answer.feedback:
            if item.skill in EXPERTS and item.skill not in {s for s, _t in feedback}:
                feedback.append((item.skill, item.text))
        dropped = len(answer.feedback) - len(feedback)
        if dropped:
            log.info("[Company day] Day-end named %d expert(s) that are not on the list or "
                     "named twice", dropped)
        call = decision_of(home, plan)
        summary = summary_text(_picks(home, plan), _flags(home, traded),
                               bool(clash_of(home, plan)), call.market if call else "")
        save_day_end(home, plan, answer.handover, feedback, summary, now)
        if feedback and load_settings(home).memory_v2_on:
            self._remember(home, plan, feedback, now)
        log.info("[Company day] Day-end written for %s: %d handover line(s), %d feedback "
                 "line(s)", traded, len(answer.handover), len(feedback))
        return [FeedItem("info", "Handover: " + " / ".join(answer.handover), plan)]

    def _remember(self, home: Path, plan: str, feedback: list[tuple[str, str]],
                  now: datetime) -> None:
        owners = {str(s): str(i) for s, i in
                  _rows(home, "SELECT skill, MIN(id) FROM roster GROUP BY skill", ())}
        for skill, text in feedback:
            owner = owners.get(skill)
            if owner:
                write_memory(home, str(owner), [Remember(kind="note", text=f"Day-end "
                                                         f"feedback {plan}: {text}")], plan, now)
