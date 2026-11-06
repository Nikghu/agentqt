"""
Module: MD-DSK-003.006.M16 — desk/router.py
Parent SRD: SRD-DSK-003.006
Also: SRD-DSK-003.007 (expiry and deadline), SRD-DSK-003.009 (no wake within 30 minutes),
SRD-DSK-003.010 (one LangGraph graph per event), SRD-DSK-003.011 (a failed node never stops
the graph), SRD-DSK-002.008 (order from skill needs), SRD-DSK-003.012 (only desk uses
LangGraph)

Handles waiting events by priority. The employees an event wakes run as one LangGraph
graph: an employee runs after the employees whose skills its skill needs. Reporting lines
are never used for the order.
"""
from __future__ import annotations

import logging
import operator
import os
import sqlite3
from collections.abc import Callable, Collection, Sequence
from datetime import datetime, timedelta
from graphlib import CycleError, TopologicalSorter
from pathlib import Path
from typing import Annotated, Any, TypedDict

from us_swing.core.desk_events import Event, open_events
from us_swing.desk.recorder import Recorder, ny_now
from us_swing.desk.registry import Hire

log = logging.getLogger(__name__)

REWAKE_GAP = timedelta(minutes=30)
Wake = Callable[[Hire, Event], None]


class _GraphState(TypedDict):
    done: Annotated[list[str], operator.add]


def _edges(hires: Sequence[Hire], known: Collection[str]) -> dict[str, list[str]]:
    """Map each employee id to the ids it must wait for; unknown need keys are logged."""
    by_skill: dict[str, list[str]] = {}
    for hire in hires:
        by_skill.setdefault(hire.skill.key, []).append(hire.spec.id)
    edges: dict[str, list[str]] = {}
    for hire in hires:
        before: list[str] = []
        for key in hire.skill.needs:
            if key not in known:
                log.warning("[AI Desk] Skill %s needs unknown skill %s; it is left out",
                            hire.skill.key, key)
                continue
            if key != hire.skill.key:
                before.extend(by_skill.get(key, []))
        edges[hire.spec.id] = before
    return edges


def run_order(hires: Sequence[Hire], known: Collection[str]) -> list[str] | None:
    """Return employee ids in a valid run order, or ``None`` when the needs form a loop."""
    return _order(_edges(hires, known))


def _order(edges: dict[str, list[str]]) -> list[str] | None:
    try:
        return list(TopologicalSorter(edges).static_order())
    except CycleError:
        return None


class Router:
    """Expires, orders and handles waiting events for one set of loaded employees."""

    def __init__(self, home: Path, hires: Sequence[Hire], wake: Wake,
                 known: Collection[str], clock: Callable[[], datetime] = ny_now) -> None:
        """Bind the desk folder, employees, the wake function and the known skill keys."""
        self._home = home
        self._hires = list(hires)
        self._wake = wake
        self._known = known
        self._clock = clock

    def has_work(self) -> bool:
        """True when a waiting event wakes someone; events nobody listens to are closed."""
        con = open_events(self._home)
        try:
            self._expire(con)
            work = False
            for event in self._waiting(con):
                if self._listeners(event):
                    work = True
                else:
                    log.debug("[AI Desk] Nobody listens to %s for %s", event.kind,
                              event.data_day)
                    self._finish(con, event, "done", "nobody listens")
            return work
        finally:
            con.close()

    def handle(self) -> None:
        """Handle every waiting event, most urgent first."""
        con = open_events(self._home)
        try:
            self._expire(con)
            for event in self._waiting(con):
                woken = self._listeners(event)
                note = f"{len(woken)} employee(s)"
                if woken:
                    try:
                        note = self._run_graph(event, woken) or note
                    except Exception:  # noqa: BLE001 — closed below, so it is not retried
                        log.exception("[AI Desk] Could not run the employees for %s",
                                      _label(event.kind))
                        note = "failed"
                now = self._clock()
                late = event.deadline is not None and now > datetime.fromisoformat(
                    event.deadline)
                if late:
                    minutes = int((now - datetime.fromisoformat(event.created)).total_seconds()
                                  // 60)
                    log.warning("[AI Desk] Event %s for %s was handled late, after %d minutes",
                                _label(event.kind), event.data_day, minutes)
                self._finish(con, event, "late" if late else "done", note)
        finally:
            con.close()

    def _listeners(self, event: Event) -> list[Hire]:
        return [h for h in self._hires if event.kind in h.spec.trigger]

    def _waiting(self, con: sqlite3.Connection) -> list[Event]:
        rows = con.execute("SELECT id, kind, priority, data_day, created, deadline, expires "
                           "FROM events WHERE state = 'waiting'").fetchall()
        events = [Event(*row) for row in rows]
        return sorted(events, key=lambda e: (e.priority, datetime.fromisoformat(e.created)))

    def _expire(self, con: sqlite3.Connection) -> None:
        now = self._clock()
        for event in self._waiting(con):
            if now > datetime.fromisoformat(event.expires):
                log.info("[AI Desk] Event %s for %s expired before it was handled",
                         _label(event.kind), event.data_day)
                self._finish(con, event, "expired", "expired")

    def _finish(self, con: sqlite3.Connection, event: Event, state: str, note: str) -> None:
        with con:
            con.execute("UPDATE events SET state = ?, handled = ?, note = ? WHERE id = ?",
                        (state, self._clock().isoformat(timespec="seconds"), note, event.id))

    def _run_graph(self, event: Event, woken: Sequence[Hire]) -> str | None:
        """Run the woken employees as one graph; return a note when nobody was run."""
        edges = _edges(woken, self._known)
        if _order(edges) is None:
            log.warning("[AI Desk] The skills woken by %s need each other in a loop; "
                        "nobody is woken", _label(event.kind))
            return "loop in needs"
        os.environ.setdefault("LANGSMITH_TRACING", "false")
        from langgraph.graph import END, START, StateGraph  # noqa: PLC0415 — tracing off first

        needed = {i for before in edges.values() for i in before}
        graph: Any = StateGraph(_GraphState)
        for hire in woken:
            graph.add_node(hire.spec.id, self._node(hire, event))
        for hire in woken:
            before = edges[hire.spec.id]
            graph.add_edge(before if len(before) > 1 else (before[0] if before else START),
                           hire.spec.id)
            if hire.spec.id not in needed:
                graph.add_edge(hire.spec.id, END)
        graph.compile().invoke({"done": []}, {"max_concurrency": 1})
        return None

    def _node(self, hire: Hire, event: Event) -> Callable[[_GraphState], dict[str, list[str]]]:
        def run(_: _GraphState) -> dict[str, list[str]]:
            try:
                if self._too_soon(hire, event):
                    return {"done": []}
                self._wake(hire, event)
            except Exception:  # noqa: BLE001 — logged; the rest of the graph still runs
                log.exception("[AI Desk] %s failed", hire.spec.name)
            return {"done": [hire.spec.id]}
        return run

    def _too_soon(self, hire: Hire, event: Event) -> bool:
        if event.priority == 0:
            return False
        recorder = Recorder(self._home)
        try:
            last = recorder.last_wake(hire.spec.id)
        finally:
            recorder.close()
        if last is None:
            return False
        gap = self._clock() - last
        if gap >= REWAKE_GAP:
            return False
        log.info("[AI Desk] %s woke %d minutes ago; next wake after 30 minutes",
                 hire.spec.name, int(gap.total_seconds() // 60))
        return True


def _label(kind: str) -> str:
    return kind.replace("_", " ")
