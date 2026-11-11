"""Tests for core/desk_research.py — the research queue (MD-DSK-010.001.M25, step E)."""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from us_swing.core.desk_alerts import open_alerts
from us_swing.core.desk_research import (
    add_ticket_edit,
    apply_ticket_edits,
    connect,
    expire_waiting,
    get_ticket,
    raise_tickets,
)
from tests.desk.research_support import NOW, ask, execute, rows, team


@pytest.fixture
def home(tmp_path: Path) -> Path:
    h = tmp_path / "desk"
    team(h)
    return h


def _raise(home: Path, *asks: object, now: object = NOW) -> list[str]:
    sent: list[str] = []
    return raise_tickets(home, "fake_lead", list(asks), now,  # type: ignore[arg-type]
                         lambda text: sent.append(text) or True)


def _status(home: Path, tid: int) -> str:
    con = connect(home)
    try:
        ticket = get_ticket(con, tid)
        assert ticket is not None
        return ticket.status
    finally:
        con.close()


def test_ticket_row(home: Path) -> None:
    """UT-DSK-010.001.M25.T01: A raised ticket is stored with all its fields."""
    assert _raise(home, ask()) == ["ticket 1 approved"]
    (row,) = rows(home, "SELECT kind, topic, goal, done_test, token_cap, step_cap, time_cap_min, "
                        "raised_by, raised_by_name, status, made FROM tickets")
    assert row == ("setup_tuning", "pullback", "Test RSI limits 35 40 45",
                   "Any variant beats the base by 0.05R", 8000, 8, 60, "l-1", "Lead A",
                   "approved", NOW.isoformat(timespec="seconds"))


def test_tables_made_twice(home: Path) -> None:
    """UT-DSK-010.001.M25.T02: Opening the tables twice keeps the rows."""
    _raise(home, ask())
    connect(home).close()
    connect(home).close()
    assert len(rows(home, "SELECT id FROM tickets")) == 1


def test_only_leads_raise(tmp_path: Path) -> None:
    """UT-DSK-010.002.M25.T01: A skill held by an expert cannot raise tickets."""
    home = tmp_path / "desk"
    team(home, lead_level="expert")
    assert _raise(home, ask()) == ["refused: no active lead holds this skill"]
    assert not (home / "desk.db").exists() or rows(home, "SELECT name FROM sqlite_master "
                                                         "WHERE name = 'tickets'") == []


def test_three_a_day(home: Path) -> None:
    """UT-DSK-010.002.M25.T02: The 4th ticket of a day is refused; the next day is open."""
    notes = _raise(home, *(ask(goal=f"Test goal number {i}", topic=f"topic {i}") for i in range(4)))
    assert notes[3] == "refused: 3 tickets a day"
    assert _raise(home, ask(goal="Test goal number 9", topic="topic 9"),
                  now=NOW + timedelta(days=1)) == ["ticket 4 approved"]


def test_lead_raises(home: Path) -> None:
    """UT-DSK-010.002.M25.T03: An active lead's 3 tickets carry its id and name."""
    _raise(home, *(ask(goal=f"Test goal number {i}", topic=f"topic {i}") for i in range(3)))
    assert rows(home, "SELECT DISTINCT raised_by, raised_by_name FROM tickets") == [
        ("l-1", "Lead A")]
    assert len(rows(home, "SELECT id FROM tickets")) == 3


def test_auto_approval_limit(home: Path) -> None:
    """UT-DSK-010.003.M25.T01: 10,000 tokens is approved by itself; 10,001 waits."""
    assert _raise(home, ask(cap=10_000), ask(cap=10_001, goal="Another goal to test")) == [
        "ticket 1 approved", "ticket 2 waiting"]
    assert rows(home, "SELECT approved_by FROM tickets ORDER BY id") == [("auto",), (None,)]


def test_book_tickets_wait(home: Path) -> None:
    """UT-DSK-010.003.M25.T02: A small book ticket still waits for the user."""
    assert _raise(home, ask(kind="book_to_strategy", cap=5_000)) == ["ticket 1 waiting"]


def test_approve_with_new_cap(home: Path) -> None:
    """UT-DSK-010.004.M25.T01: Approve with a cap makes it approved by master with that cap."""
    _raise(home, ask(cap=30_000))
    add_ticket_edit(home, 1, "approve", NOW, 20_000)
    assert apply_ticket_edits(home, NOW) == 1
    assert rows(home, "SELECT status, approved_by, token_cap FROM tickets") == [
        ("approved", "master", 20_000)]
    assert rows(home, "SELECT applied IS NOT NULL FROM ticket_edits") == [(1,)]


def test_reject_and_cap(home: Path) -> None:
    """UT-DSK-010.004.M25.T02: Reject ends a ticket; a cap change keeps it waiting."""
    _raise(home, ask(cap=30_000), ask(cap=40_000, goal="Another goal to test"))
    add_ticket_edit(home, 1, "reject", NOW)
    add_ticket_edit(home, 2, "cap", NOW, 15_000)
    apply_ticket_edits(home, NOW)
    assert rows(home, "SELECT status, token_cap FROM tickets ORDER BY id") == [
        ("rejected", 30_000), ("waiting", 15_000)]


def test_edit_on_ticket_not_waiting(home: Path) -> None:
    """UT-DSK-010.004.M25.T03: An edit on an approved ticket is applied with no change."""
    _raise(home, ask())
    add_ticket_edit(home, 1, "reject", NOW)
    assert apply_ticket_edits(home, NOW) == 0
    assert _status(home, 1) == "approved"
    assert rows(home, "SELECT applied IS NOT NULL FROM ticket_edits") == [(1,)]
    with pytest.raises(ValueError):
        add_ticket_edit(home, 1, "cap", NOW, 500)


def test_expiry(home: Path) -> None:
    """UT-DSK-010.005.M25.T01: A ticket waiting over 3 days expires; 2 days does not."""
    _raise(home, ask(cap=30_000), now=NOW - timedelta(days=2))
    _raise(home, ask(cap=30_000, goal="Another goal to test"),
           now=NOW - timedelta(days=3, minutes=1))
    assert expire_waiting(home, NOW) == 1
    assert rows(home, "SELECT status FROM tickets ORDER BY id") == [("waiting",), ("expired",)]


def test_approved_in_time(home: Path) -> None:
    """UT-DSK-010.005.M25.T02: A ticket approved on day 2 never expires."""
    _raise(home, ask(cap=30_000), now=NOW)
    add_ticket_edit(home, 1, "approve", NOW + timedelta(days=2))
    apply_ticket_edits(home, NOW + timedelta(days=2))
    expire_waiting(home, NOW + timedelta(days=4))
    assert _status(home, 1) == "approved"


def _end(home: Path, tid: int, status: str, days_ago: float, gain: int | None = 0) -> None:
    execute(home, "UPDATE tickets SET status = ?, ended = ?, gain = ? WHERE id = ?",
            (status, (NOW - timedelta(days=days_ago)).isoformat(timespec="seconds"), gain, tid))


def test_repeat_refused(home: Path) -> None:
    """UT-DSK-010.006.M25.T01: The same kind and goal done 10 days ago is a repeat; 31 is not."""
    _raise(home, ask(), now=NOW - timedelta(days=12))
    _end(home, 1, "done", 10, gain=1)
    assert _raise(home, ask(goal="  test RSI   limits 35 40 45 ")) == [
        "refused: repeat of a recent ticket"]
    _end(home, 1, "done", 31, gain=1)
    assert _raise(home, ask()) == ["ticket 2 approved"]


def test_new_goal_added(home: Path) -> None:
    """UT-DSK-010.006.M25.T02: Same kind with a new goal is added."""
    _raise(home, ask(), now=NOW - timedelta(days=12))
    _end(home, 1, "done", 10, gain=1)
    assert _raise(home, ask(goal="Test RSI limits 30 and 50")) == ["ticket 2 approved"]


def _three_no_gain(home: Path, last_days_ago: float) -> None:
    for i in range(3):
        _raise(home, ask(goal=f"Old goal number {i}"), now=NOW - timedelta(days=40 + i))
        _end(home, i + 1, "stuck" if i else "done", last_days_ago + 2 - i)


def test_topic_parked(home: Path) -> None:
    """UT-DSK-010.007.M25.T01: 3 no-gain tickets park a topic; a gain among them frees it."""
    _three_no_gain(home, 1)
    assert _raise(home, ask(goal="New goal on pullbacks")) == ["refused: topic parked"]
    execute(home, "UPDATE tickets SET gain = 1 WHERE id = 1")
    assert _raise(home, ask(goal="New goal on pullbacks")) == ["ticket 4 approved"]


def test_not_parked_yet(home: Path) -> None:
    """UT-DSK-010.007.M25.T02: 2 no-gain tickets, or 3 ending over 30 days ago, do not park."""
    _three_no_gain(home, 31)
    assert _raise(home, ask(goal="New goal on pullbacks")) == ["ticket 4 approved"]
    execute(home, "DELETE FROM tickets WHERE id IN (1, 4)")
    execute(home, "UPDATE tickets SET ended = ?", (NOW.isoformat(timespec="seconds"),))
    assert _raise(home, ask(goal="Second new goal on it")) == ["ticket 5 approved"]


def test_waiting_alert(home: Path) -> None:
    """UT-DSK-007.010.M21.T01: A waiting ticket raises one alert, closed when approved."""
    sent: list[str] = []
    raise_tickets(home, "fake_lead", [ask(cap=30_000)], NOW,
                  lambda text: sent.append(text) or True)
    (alert,) = open_alerts(home, NOW)
    assert alert.title == "Research ticket waiting"
    assert "Test RSI limits" in alert.text and "30,000" in alert.text
    assert len(sent) == 1
    add_ticket_edit(home, 1, "approve", NOW)
    apply_ticket_edits(home, NOW)
    assert open_alerts(home, NOW) == []


def test_no_alert_when_auto(home: Path) -> None:
    """UT-DSK-007.010.M21.T02: An auto-approved ticket raises no alert."""
    _raise(home, ask(cap=8_000))
    assert open_alerts(home, NOW) == []
