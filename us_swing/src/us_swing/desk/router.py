"""
Module: MD-DSK-003.006.M16 — desk/router.py
Parent SRD: SRD-DSK-003.006
Also: SRD-DSK-003.007 (expiry and deadline), SRD-DSK-003.009 (no wake within 30 minutes),
SRD-DSK-003.010 (needs order by events), SRD-DSK-003.011 (a sleeping employee never stops
the chain), SRD-DSK-002.008 (order from skill needs), SRD-DSK-003.012 (no LangGraph),
SRD-DSK-003.014–.019 (``step_done`` baton, retries, skips, partial lead plan, resume),
SRD-DSK-007.008 (one alert when a step fails)

Handles waiting events by priority. The employees an event wakes form a chain: each one
wakes when every employee it needs has a ``step_done``, a failed one is tried again at most
twice, and the chain stops after a failure, except that the lead still writes a partial plan.
Reporting lines are never used for the order.
"""
from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable, Collection, Sequence
from datetime import datetime, timedelta
from graphlib import CycleError, TopologicalSorter
from pathlib import Path
from typing import NamedTuple

from us_swing.core.desk_events import Event, open_events, post_step_done
from us_swing.desk.recorder import Recorder, ny_now
from us_swing.desk.registry import Hire

log = logging.getLogger(__name__)

REWAKE_GAP = timedelta(minutes=30)
RETRY_GAP = timedelta(minutes=5)
MAX_TRIES = 3
Wake = Callable[[Hire, Event, bool, tuple[str, ...]], str]
Alert = Callable[[Hire, Event], None]
_COLUMNS = "id, kind, priority, data_day, created, deadline, expires, parent, due"


class _Step(NamedTuple):
    tries: int
    result: str
    updated: datetime


def _settled(step: _Step | None) -> bool:
    return step is not None and (step.result in ("ok", "slept", "skipped")
                                 or (step.result == "failed" and step.tries >= MAX_TRIES))


def _lost(step: _Step | None) -> bool:
    return step is not None and (step.result == "skipped"
                                 or (step.result == "failed" and step.tries >= MAX_TRIES))


def _edges(hires: Sequence[Hire], known: Collection[str],
           warn: bool = True) -> dict[str, list[str]]:
    """Map each employee id to the ids it must wait for; unknown need keys are logged."""
    by_skill: dict[str, list[str]] = {}
    for hire in hires:
        by_skill.setdefault(hire.skill.key, []).append(hire.spec.id)
    edges: dict[str, list[str]] = {}
    for hire in hires:
        before: list[str] = []
        for key in hire.skill.needs:
            if key not in known:
                if warn:
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
                 known: Collection[str], clock: Callable[[], datetime] = ny_now,
                 alert: Alert | None = None) -> None:
        """Bind the desk folder, employees, wake function, known skill keys, clock and the
        alert raised when a step fails for good."""
        self._home = home
        self._hires = list(hires)
        self._wake = wake
        self._known = known
        self._clock = clock
        self._alert = alert

    def has_work(self) -> bool:
        """True when a due waiting event wakes someone; events nobody listens to are closed."""
        con = open_events(self._home)
        try:
            self._expire(con)
            work = False
            for event in self._waiting(con):
                if event.parent is not None or self._listeners(event):
                    work = True
                else:
                    log.debug("[AI Desk] Nobody listens to %s for %s", event.kind,
                              event.data_day)
                    self._finish(con, event, "done", "nobody listens")
            return work
        finally:
            con.close()

    def handle(self) -> None:
        """Handle every due waiting event, most urgent first, including new ``step_done``s."""
        con = open_events(self._home)
        try:
            self._expire(con)
            seen: set[int] = set()
            while event := next((e for e in self._waiting(con) if e.id not in seen), None):
                seen.add(event.id)
                note = self._handle_one(con, event)
                now = self._clock()
                late = event.deadline is not None and now > datetime.fromisoformat(
                    event.deadline)
                if late and event.parent is None:
                    minutes = int((now - datetime.fromisoformat(event.created)).total_seconds()
                                  // 60)
                    log.warning("[AI Desk] Event %s for %s was handled late, after %d minutes",
                                _label(event.kind), event.data_day, minutes)
                self._finish(con, event, "late" if late else "done", note)
        finally:
            con.close()

    def _handle_one(self, con: sqlite3.Connection, event: Event) -> str:
        trigger = event if event.parent is None else self._event(con, event.parent)
        if trigger is None:
            return "trigger gone"
        chain = self._listeners(trigger)
        if not chain:
            return "0 employee(s)"
        try:
            edges = _edges(chain, self._known, warn=event.parent is None)
            order = _order(edges)
            if order is None:
                log.warning("[AI Desk] The skills woken by %s need each other in a loop; "
                            "nobody is woken", _label(trigger.kind))
                return "loop in needs"
            return self._advance(con, trigger, chain, edges, order)
        except Exception:  # noqa: BLE001 — closed by the caller, so it is not retried
            log.exception("[AI Desk] Could not run the employees for %s", _label(trigger.kind))
            return "failed"

    def _advance(self, con: sqlite3.Connection, trigger: Event, chain: Sequence[Hire],
                 edges: dict[str, list[str]], order: Sequence[str]) -> str:
        """Wake every employee of the chain that is ready now; return the chain's note."""
        by_id = {h.spec.id: h for h in chain}
        steps = self._steps(con, trigger.id)
        for emp in order:
            hire, step = by_id[emp], steps.get(emp)
            if _settled(step):
                continue
            if step is not None and step.result == "running":
                steps[emp] = self._cut(con, trigger, hire, step.tries)
                continue
            if step is not None and self._clock() < step.updated + RETRY_GAP:
                continue
            needs = edges[emp]
            lost = [n for n in needs if _lost(steps.get(n))]
            if lost and hire.spec.level != "lead":
                log.info("[AI Desk] %s will not run: it needs %s, which did not finish",
                         hire.spec.name, ", ".join(by_id[n].spec.name for n in lost))
                steps[emp] = self._end(con, trigger, hire, 0, "skipped")
                continue
            if not all(_settled(steps.get(n)) for n in needs):
                continue
            steps[emp] = self._try(con, trigger, hire, (step.tries if step else 0) + 1,
                                   tuple(by_id[n].spec.name for n in lost))
        if not all(_settled(steps.get(emp)) for emp in order):
            done = sum(_settled(steps.get(emp)) for emp in order)
            return f"{done} of {len(order)} step(s) done"
        note = "chain partial" if any(_lost(steps.get(e)) for e in order) else "chain full"
        with con:
            con.execute("UPDATE events SET note = ? WHERE id = ?", (note, trigger.id))
        return note

    def _try(self, con: sqlite3.Connection, trigger: Event, hire: Hire, tries: int,
             missing: tuple[str, ...]) -> _Step:
        """Wake one employee once and record the try; a failure is retried after 5 minutes."""
        self._write(con, trigger, hire.spec.id, tries, "running")
        retry = tries > 1
        if not retry and self._too_soon(hire, trigger):
            result = "slept"
        else:
            if missing:
                log.info("[AI Desk] %s is writing a partial plan without %s", hire.spec.name,
                         ", ".join(missing))
            try:
                result = self._wake(hire, trigger, retry, missing)
            except Exception:  # noqa: BLE001 — logged; counted as a failed try
                log.exception("[AI Desk] %s failed", hire.spec.name)
                result = "failed"
        if result == "failed" and tries < MAX_TRIES:
            log.warning("[AI Desk] %s failed; trying again in 5 minutes (try %d of %d)",
                        hire.spec.name, tries + 1, MAX_TRIES)
            now = self._clock()
            self._write(con, trigger, hire.spec.id, tries, result)
            post_step_done(con, trigger, hire.spec.id, tries, result, now, now + RETRY_GAP)
            return _Step(tries, result, now)
        return self._end(con, trigger, hire, tries, result)

    def _cut(self, con: sqlite3.Connection, trigger: Event, hire: Hire, tries: int) -> _Step:
        """A try left running when the app closed counts as a failed try."""
        log.info("[AI Desk] %s was stopped when the app closed; counted as a failed try",
                 hire.spec.name)
        if tries >= MAX_TRIES:
            return self._end(con, trigger, hire, tries, "failed")
        now = self._clock()
        self._write(con, trigger, hire.spec.id, tries, "failed")
        post_step_done(con, trigger, hire.spec.id, tries, "failed", now, now + RETRY_GAP)
        return _Step(tries, "failed", now)

    def _end(self, con: sqlite3.Connection, trigger: Event, hire: Hire, tries: int,
             result: str) -> _Step:
        """Record a step's last result, post its ``step_done`` and alert when it failed."""
        now = self._clock()
        self._write(con, trigger, hire.spec.id, tries, result)
        post_step_done(con, trigger, hire.spec.id, tries, result, now)
        if result == "failed":
            log.warning("[AI Desk] %s failed %d times; the steps that need it will not run",
                        hire.spec.name, tries)
            if self._alert is not None:
                try:
                    self._alert(hire, trigger)
                except Exception:  # noqa: BLE001 — an alert problem never stops the chain
                    log.exception("[AI Desk] Could not raise the partial plan alert")
        return _Step(tries, result, now)

    def _write(self, con: sqlite3.Connection, trigger: Event, employee: str, tries: int,
               result: str) -> None:
        with con:
            con.execute("INSERT OR REPLACE INTO steps (event_id, employee, tries, result, "
                        "updated) VALUES (?, ?, ?, ?, ?)",
                        (trigger.id, employee, tries, result,
                         self._clock().isoformat(timespec="seconds")))

    def _steps(self, con: sqlite3.Connection, event_id: int) -> dict[str, _Step]:
        rows = con.execute("SELECT employee, tries, result, updated FROM steps "
                           "WHERE event_id = ?", (event_id,)).fetchall()
        return {str(e): _Step(int(n), str(r), datetime.fromisoformat(str(u)))
                for e, n, r, u in rows}

    def _listeners(self, event: Event) -> list[Hire]:
        return [h for h in self._hires if event.kind in h.spec.trigger]

    def _event(self, con: sqlite3.Connection, event_id: int) -> Event | None:
        row = con.execute(f"SELECT {_COLUMNS} FROM events WHERE id = ?", (event_id,)).fetchone()
        return Event(*row) if row else None

    def _waiting(self, con: sqlite3.Connection) -> list[Event]:
        rows = con.execute(f"SELECT {_COLUMNS} FROM events WHERE state = 'waiting'").fetchall()
        now = self._clock()
        events = [Event(*row) for row in rows]
        due = [e for e in events if e.due is None or datetime.fromisoformat(e.due) <= now]
        return sorted(due, key=lambda e: (e.priority, datetime.fromisoformat(e.created)))

    def _expire(self, con: sqlite3.Connection) -> None:
        now = self._clock()
        rows = con.execute(f"SELECT {_COLUMNS} FROM events WHERE state = 'waiting'").fetchall()
        for event in (Event(*row) for row in rows):
            if now > datetime.fromisoformat(event.expires):
                log.info("[AI Desk] Event %s for %s expired before it was handled",
                         _label(event.kind), event.data_day)
                self._finish(con, event, "expired", "expired")
                if event.parent is not None:
                    self._retry_expired(con, event.parent)

    def _retry_expired(self, con: sqlite3.Connection, trigger_id: int) -> None:
        """Raise the alert for steps whose retry can no longer run because the chain expired."""
        trigger = self._event(con, trigger_id)
        if trigger is None:
            return
        for hire in self._listeners(trigger):
            step = self._steps(con, trigger_id).get(hire.spec.id)
            if step is not None and step.result == "failed" and step.tries < MAX_TRIES:
                self._write(con, trigger, hire.spec.id, MAX_TRIES, "failed")
                log.warning("[AI Desk] %s failed and its chain expired before the next try",
                            hire.spec.name)
                if self._alert is not None:
                    try:
                        self._alert(hire, trigger)
                    except Exception:  # noqa: BLE001 — an alert problem never stops the desk
                        log.exception("[AI Desk] Could not raise the partial plan alert")

    def _finish(self, con: sqlite3.Connection, event: Event, state: str, note: str) -> None:
        with con:
            con.execute("UPDATE events SET state = ?, handled = ?, note = ? WHERE id = ?",
                        (state, self._clock().isoformat(timespec="seconds"), note, event.id))

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
