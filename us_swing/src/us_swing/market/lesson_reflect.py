"""
Module: MD-MKT-012.002.M01 — market/lesson_reflect.py
Parent SRD: SRD-MKT-012.002
Also: SRD-MKT-012.001 (stats of closed picks by tag), SRD-MKT-012.003 (answer form),
SRD-MKT-012.006 (log line)

The reflect skill: on a day with newly closed lead picks, shows the model the results by tag
and asks for at most 3 candidate lessons with the picks that prove them. Code keeps only
picks it knows and stores each lesson as a candidate; code decides when it becomes active.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from us_swing.core.desk_agents import AgentContext, Facts, FeedItem
from us_swing.core.desk_lessons import (
    TAG_KEYS,
    Case,
    add_candidate,
    cases,
    connect,
    get_state,
    lesson_rows,
    set_state,
)
from us_swing.data.market_calendar import ET

log = logging.getLogger(__name__)

KEY = "lesson_reflect"
SEEN = "reflected_keys"
MAX_NEW = 50
TagKey = Literal["side", "setup", "regime", "sector", "grade", "tone"]
_RULES = (
    "Rules: write at most 3 lessons, each one short sentence a trader can use when picking. "
    "Each lesson names 1 to 3 tags from the stats, says whether such picks do better or worse "
    "than the average, and lists the pick keys (date|side|symbol) that show it. A lesson may "
    "only make picking stricter; never suggest wider stops, more capital or skipping approval. "
    "Return an empty list when the results show nothing clear."
)


class Candidate(BaseModel):
    """One candidate lesson in the model's answer."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=5, max_length=200)
    tags: dict[TagKey, str] = Field(min_length=1, max_length=3)
    claim: Literal["better", "worse"]
    picks: list[str] = Field(min_length=1, max_length=20)


class LessonReflect(BaseModel):
    """The model's answer for the reflect skill, checked by the gateway."""

    model_config = ConfigDict(extra="forbid")

    lessons: list[Candidate] = Field(default_factory=list, max_length=3)


def _now() -> datetime:
    return datetime.now(ET)


def stats_text(all_cases: Sequence[Case]) -> str:
    """Count, win rate and average R of closed picks by each tag value with 2 or more picks."""
    if not all_cases:
        return "No closed picks yet."
    total = sum(c.r for c in all_cases) / len(all_cases)
    lines = [f"All closed picks: {len(all_cases)}, average {total:+.2f}R"]
    for key in TAG_KEYS:
        groups: dict[str, list[float]] = {}
        for c in all_cases:
            if key in c.tags:
                groups.setdefault(c.tags[key], []).append(c.r)
        for value, rs in sorted(groups.items()):
            if len(rs) < 2:
                continue
            wins = sum(1 for r in rs if r > 0)
            lines.append(f"{key}={value}: {len(rs)} picks, win {wins * 100 // len(rs)}%, "
                         f"average {sum(rs) / len(rs):+.2f}R")
    return "\n".join(lines)


def _seen(home: Path) -> set[str]:
    con = connect(home)
    try:
        text = get_state(con, SEEN)
    finally:
        con.close()
    return set(json.loads(text)) if text else set()


def _closed(home: Path) -> list[Case]:
    con = connect(home)
    try:
        return cases(con)
    finally:
        con.close()


class LessonReflectSkill:
    """Turns newly closed picks into at most 3 candidate lessons."""

    key = KEY
    needs: tuple[str, ...] = ()
    answer = LessonReflect

    def __init__(self, clock: Callable[[], datetime] = _now) -> None:
        """Set the clock; injectable for tests."""
        self._clock = clock

    def facts(self, home: Path) -> Facts:
        """Stats, the newly closed picks and the active lessons; fresh only with new picks."""
        day = self._clock().date().isoformat()
        closed = _closed(home)
        seen = _seen(home)
        new = [c for c in closed if c.key not in seen]
        if not new:
            return Facts("", day, False, "no newly closed picks")
        active = lesson_rows(home, "active")
        text = "\n".join([
            "Results by tag:", stats_text(closed), "",
            "Newly closed picks (key, tags, R):",
            *(f"{c.key}: {json.dumps(c.tags, sort_keys=True)}, {c.r:+.2f}R"
              for c in new[-MAX_NEW:]), "",
            "Active lessons:",
            *([f"L-{x.id}: {x.text}" for x in active] or ["(none)"]), "",
            _RULES,
        ])
        return Facts(text, day, True)

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        """Ask for candidates, keep those with known picks and mark the picks as seen."""
        reply = ctx.ask(facts.text, LessonReflect)
        if reply is None:
            return []
        closed = _closed(ctx.home)
        known = {c.key for c in closed}
        kept: list[str] = []
        dropped = 0
        now = self._clock()
        for cand in reply.lessons:
            picks = [p for p in cand.picks if p in known]
            if not picks:
                dropped += 1
                continue
            try:
                add_candidate(ctx.home, cand.text, {str(k): v for k, v in cand.tags.items()},
                              cand.claim, picks, now)
            except ValueError:
                dropped += 1
                continue
            kept.append(cand.text)
        con = connect(ctx.home)
        try:
            set_state(con, SEEN, json.dumps(sorted(known)))
        finally:
            con.close()
        log.info("[Memory] Kept %d candidate lesson(s), dropped %d", len(kept), dropped)
        if not kept:
            return []
        text = "New candidate lessons:\n" + "\n".join(f"- {t}" for t in kept)
        return [FeedItem("info", text, facts.data_day)]
