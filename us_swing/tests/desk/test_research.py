"""Tests for desk/research.py — the research runner (MD-DSK-010.008.M26, step E)."""
from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from tests.desk import research_support as rs
from tests.desk.conftest import FakeClock
from tests.desk.research_support import NOW, ON, SKILLS, add_try, ask, execute, rows, team
from tests.desk.test_harness import FakeCaller
from us_swing.core.desk_contract import StepContext
from us_swing.core.desk_events import post_event
from us_swing.core.desk_research import (
    raise_owner_test,
    StepResult,
    add_ticket_edit,
    apply_ticket_edits,
    connect,
    expire_waiting,
    raise_tickets,
    runnable,
)
from us_swing.core.desk_watch import connect as watch_connect
from us_swing.desk.gateway import Reply
from us_swing.desk.process import DeskProcess
from us_swing.desk.research import ResearchRunner, quiet
from us_swing.desk.router import Router


@pytest.fixture(autouse=True)
def _reset() -> Iterator[None]:
    rs.reset()
    yield


@pytest.fixture
def home(tmp_path: Path) -> Path:
    h = tmp_path / "desk"
    team(h)
    return h


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(NOW)


def _runner(clock: FakeClock, caller: FakeCaller | None = None) -> ResearchRunner:
    return ResearchRunner(lambda: SKILLS, lambda: [], lambda: ON, lambda: "key",
                          caller or FakeCaller(), clock)


def _raise(home: Path, *caps: int, kind: str = "setup_tuning") -> None:
    asks = [ask(kind=kind, cap=c, goal=f"Goal number {i} to test") for i, c in enumerate(caps)]
    raise_tickets(home, "fake_lead", asks, NOW, lambda _t: True)


def _step(runner: ResearchRunner, home: Path) -> None:
    runner(StepContext(1, "event", NOW, home))


def _ticket(home: Path, tid: int = 1) -> tuple[Any, ...]:
    return tuple(rows(home, "SELECT status, end_reason, gain, steps, result FROM tickets "
                            "WHERE id = ?", (tid,))[0])


def _flag(home: Path, when: Any) -> None:
    con = watch_connect(home)
    try:
        with con:
            con.execute("INSERT INTO watch_flags (day, hour, kind, symbol, detail, price, created) "
                        "VALUES ('2026-11-06', 10, 'gap', 'ABC', 'gap', 1.0, ?)",
                        (when.isoformat(timespec="seconds"),))
    finally:
        con.close()


def test_quiet_gap(home: Path) -> None:
    """UT-DSK-010.008.M26.T01: A waiting event or a recent flag ends the quiet gap."""
    connect(home).close()
    assert quiet(home, NOW)
    post_event(home, "market_open", "2026-11-06", NOW)
    assert not quiet(home, NOW)
    execute(home, "UPDATE events SET state = 'done'")
    _flag(home, NOW - timedelta(minutes=10))
    assert not quiet(home, NOW)
    assert quiet(home, NOW + timedelta(minutes=15))


def test_ticket_order(home: Path, clock: FakeClock) -> None:
    """UT-DSK-010.008.M26.T02: Running first, then paused, then the oldest approved."""
    _raise(home, 5_000, 5_000, 5_000)
    raise_tickets(home, "fake_lead", [ask(goal="A later goal to test")],
                  NOW + timedelta(days=1), lambda _t: True)
    execute(home, "UPDATE tickets SET status = 'running' WHERE id = 2")
    execute(home, "UPDATE tickets SET status = 'paused' WHERE id = 3")
    con = connect(home)
    try:
        assert [t.id for t in runnable(con)] == [2, 3, 1, 4]
    finally:
        con.close()
    _step(_runner(clock), home)
    assert rs.STATE.seen == [2]


def test_no_work_without_tickets(home: Path, clock: FakeClock) -> None:
    """UT-DSK-010.008.M26.T03: Only waiting and ended tickets give no work."""
    _raise(home, 30_000, 5_000)
    execute(home, "UPDATE tickets SET status = 'done', ended = ? WHERE id = 2",
            (NOW.isoformat(),))
    assert not _runner(clock).has_work(home)


def test_market_work_first(home: Path, clock: FakeClock) -> None:
    """UT-DSK-010.008.M04.T01: With an event to handle, the tick runs no research step."""
    _raise(home, 5_000)

    class Events:
        handled = 0

        def has_work(self, _home: Path) -> bool:
            return True

        def handle_events(self, _ctx: StepContext) -> None:
            Events.handled += 1

    class Research:
        name = "Research"
        steps = 0

        def has_work(self, _home: Path) -> bool:
            return True

        def __call__(self, _ctx: StepContext) -> None:
            Research.steps += 1

    utc = FakeClock(NOW.replace(hour=2))
    desk = DeskProcess(home, clock=utc, sleep=lambda _s: None, events=Events(),
                       research=Research())
    try:
        assert desk.start()
        desk.tick()
    finally:
        desk.close()
    assert Events.handled == 1 and Research.steps == 0


def test_doer_by_kind(home: Path, clock: FakeClock) -> None:
    """UT-DSK-010.009.M26.T01: The research skill's employee works the step; the lead pays."""
    _raise(home, 5_000)
    runner = _runner(clock)
    assert runner.has_work(home)
    _step(runner, home)
    assert rows(home, "SELECT employee, part, payer, ticket FROM activity") == [
        ("r-1", "research", "l-1", 1)]
    assert _ticket(home)[0] == "running"


def test_no_doer(home: Path, clock: FakeClock, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-010.009.M26.T02: A kind with no research skill waits, logged once a day."""
    caplog.set_level("INFO")
    _raise(home, 5_000, kind="stock_study")
    runner = _runner(clock)
    assert not runner.has_work(home)
    clock.move(120)
    assert not runner.has_work(home)
    assert _ticket(home)[0] == "approved"
    assert caplog.text.count("No employee can work stock study tickets yet") == 1


def test_done_test_met(home: Path, clock: FakeClock) -> None:
    """UT-DSK-010.010.M26.T01: A done outcome ends the ticket with its gain and note."""
    _raise(home, 5_000)
    rs.STATE.results = [StepResult("RSI 40 beats the base", "backtest 40", "done", True)]
    _step(_runner(clock), home)
    status, reason, gain, steps, result = _ticket(home)
    assert (status, reason, gain, steps) == ("done", "done test met", 1, 1)
    assert "RSI 40 beats the base" in result


def test_hard_token_cap(home: Path, clock: FakeClock) -> None:
    """UT-DSK-010.010.M26.T02: No step starts when the tokens left are below the estimate."""
    _raise(home, 10_000)
    add_try(home, "r-1", 7_000, part="research", payer="l-1", ticket=1)
    rs.STATE.step_tokens = 4_000
    caller = FakeCaller()
    _step(_runner(clock, caller), home)
    assert caller.calls == []
    assert _ticket(home)[:2] == ("done", "token cap")


def test_step_and_time_caps(home: Path, clock: FakeClock) -> None:
    """UT-DSK-010.010.M26.T03: A ticket ends at 8 steps or 60 minutes of calls."""
    _raise(home, 9_000, 9_000)
    execute(home, "UPDATE tickets SET steps = 8 WHERE id = 1")
    add_try(home, "r-1", 10, part="research", payer="l-1", ticket=2, seconds=3_660)
    runner = _runner(clock)
    _step(runner, home)
    _step(runner, home)
    assert _ticket(home, 1)[:2] == ("done", "step cap")
    assert _ticket(home, 2)[:2] == ("done", "time cap")


def test_stall_stops(home: Path, clock: FakeClock) -> None:
    """UT-DSK-010.011.M26.T01: Two steps with no news, or the same call twice, end as stuck."""
    _raise(home, 9_000)
    rs.STATE.results = [StepResult("", "a", "go"), StepResult("", "b", "go")]
    runner = _runner(clock)
    _step(runner, home)
    _step(runner, home)
    assert _ticket(home)[:2] == ("stuck", "no new result in 2 steps")
    _raise_more = [ask(goal="Another goal for the stall", cap=9_000)]
    raise_tickets(home, "fake_lead", _raise_more, NOW, lambda _t: True)
    rs.STATE.results = [StepResult("x", "same", "go"), StepResult("y", "same", "go")]
    _step(runner, home)
    _step(runner, home)
    assert _ticket(home, 2)[:2] == ("stuck", "same call twice in a row")


def test_progress_keeps_running(home: Path, clock: FakeClock) -> None:
    """UT-DSK-010.011.M26.T02: Steps with new notes and new calls keep the ticket running."""
    _raise(home, 9_000)
    runner = _runner(clock)
    for _ in range(3):
        _step(runner, home)
    status, _reason, _gain, steps, result = _ticket(home)
    assert (status, steps) == ("running", 3)
    assert result.splitlines() == ["found 1", "found 2", "found 3"]


def test_pause_and_resume(home: Path, clock: FakeClock) -> None:
    """UT-DSK-010.012.M26.T01: A new flag pauses a running ticket; it resumes when quiet."""
    _raise(home, 9_000)
    runner = _runner(clock)
    _step(runner, home)
    _flag(home, clock())
    assert not runner.has_work(home)
    assert _ticket(home)[:2] == ("paused", "market work")
    clock.move(21 * 60)
    assert runner.has_work(home)
    _step(runner, home)
    assert _ticket(home)[0] == "running"


def test_research_part_used_up(home: Path, clock: FakeClock) -> None:
    """UT-DSK-010.012.M26.T02: A used-up research part pauses the ticket with no call."""
    _raise(home, 9_000)
    execute(home, "UPDATE tickets SET status = 'running'")
    add_try(home, "x-9", 18_000, part="research", payer="l-1")
    caller = FakeCaller()
    runner = _runner(clock, caller)
    assert not runner.has_work(home)
    assert _ticket(home)[:2] == ("paused", "research tokens used up for today")
    assert caller.calls == []


def test_pause_on_start(home: Path) -> None:
    """UT-DSK-010.012.M25.T01: A ticket running when the desk starts is paused."""
    _raise(home, 5_000)
    execute(home, "UPDATE tickets SET status = 'running'")
    desk = DeskProcess(home, clock=FakeClock(NOW.replace(hour=2)), sleep=lambda _s: None)
    try:
        assert desk.start()
    finally:
        desk.close()
    assert _ticket(home)[:2] == ("paused", "app closed")


def test_research_done_event(home: Path, clock: FakeClock) -> None:
    """UT-DSK-010.013.M26.T01: An ended ticket posts one research_done event, closed unheard."""
    _raise(home, 5_000)
    rs.STATE.results = [StepResult("found it", "c", "done", True)]
    _step(_runner(clock), home)
    assert rows(home, "SELECT kind, key, state FROM events") == [
        ("research_done", "research_done|2026-11-06|1", "waiting")]
    Router(home, [], lambda *_a: "ok", set(), lambda: NOW).has_work()
    assert rows(home, "SELECT state, note FROM events") == [("done", "nobody listens")]


def test_no_event_for_rejected(home: Path) -> None:
    """UT-DSK-010.013.M26.T02: Rejected and expired tickets post no research_done event."""
    _raise(home, 30_000, 40_000)
    add_ticket_edit(home, 1, "reject", NOW)
    apply_ticket_edits(home, NOW)
    expire_waiting(home, NOW + timedelta(days=4))
    assert rows(home, "SELECT status FROM tickets ORDER BY id") == [("rejected",), ("expired",)]
    assert rows(home, "SELECT name FROM sqlite_master WHERE name = 'events'") == [] or rows(
        home, "SELECT kind FROM events WHERE kind = 'research_done'") == []


def test_ticket_logs(home: Path, clock: FakeClock, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-010.014.M26.T01: Raise, start, pause and end are logged with id and status."""
    caplog.set_level("INFO")
    _raise(home, 50_000)
    add_ticket_edit(home, 1, "approve", NOW)
    apply_ticket_edits(home, NOW)
    runner = _runner(clock, FakeCaller(Reply('{"word": "a"}', 10, 5, 0.0)))
    _step(runner, home)
    _flag(home, clock())
    runner.has_work(home)
    clock.move(21 * 60)
    rs.STATE.results = [StepResult("end", "z", "failed", False)]
    _step(runner, home)
    text = caplog.text
    for line in ("[Research] Lead A raised ticket 1", "waiting",
                 "[Research] Ticket 1 approved by the Master user",
                 "[Research] Ticket 1 started by Expert R", "[Research] Ticket 1 paused: market work",
                 "[Research] Ticket 1 resumed by Expert R",
                 "[Research] Ticket 1 ended failed: done test failed"):
        assert line in text


def test_other_refusal_backs_off(home: Path, clock: FakeClock) -> None:
    """UT-DSK-010.012.M26.T03: A refusal other than the ticket cap pauses and waits 15 minutes."""
    _raise(home, 9_000)
    for _ in range(40 * 4):
        add_try(home, "r-1", 0, part="research", payer="l-1")
    runner = _runner(clock)
    assert runner.has_work(home)
    _step(runner, home)
    status, reason = _ticket(home)[:2]
    assert status == "paused" and "call(s) for today" in reason
    clock.move(60)
    assert not runner.has_work(home)
    clock.move(15 * 60)
    assert runner.has_work(home)


def test_owner_test_ticket(tmp_path: Path) -> None:
    """UT-DSK-010.016.M25.T01: The owner's test is approved in the lead plan holder's name."""
    rs.employee(tmp_path, "l-9", "Lead P", "lead", "lead_brief")
    assert raise_owner_test(tmp_path, 3, NOW) == "ticket 1 approved"
    got = rows(tmp_path, "SELECT kind, topic, status, raised_by, approved_by FROM tickets")
    assert got == [("strategy_test", "SC-3", "approved", "l-9", "master")]


def test_owner_test_no_lead(tmp_path: Path) -> None:
    """UT-DSK-010.016.M25.T02: With no lead plan holder the test is refused."""
    team(tmp_path)
    assert raise_owner_test(tmp_path, 3, NOW).startswith("refused: no active lead")
    assert rows(tmp_path, "SELECT name FROM sqlite_master WHERE name = 'tickets'") == [] or \
        rows(tmp_path, "SELECT COUNT(*) FROM tickets")[0][0] == 0


def test_owner_test_repeat(tmp_path: Path) -> None:
    """UT-DSK-010.016.M25.T03: A second test of a card with an open test is refused."""
    rs.employee(tmp_path, "l-9", "Lead P", "lead", "lead_brief")
    raise_owner_test(tmp_path, 3, NOW)
    assert raise_owner_test(tmp_path, 3, NOW).startswith("refused")
    assert rows(tmp_path, "SELECT COUNT(*) FROM tickets")[0][0] == 1
