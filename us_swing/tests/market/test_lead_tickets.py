"""Tests for lead research tickets (MD-MKT-014.001.M01 lead_brief, M02 checkin_note, step E)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from tests.desk.research_support import NOW, add_try, employee
from tests.market.p5b_support import Env, FakeCtx, query
from tests.market.test_lead_brief import _stage
from us_swing.core.desk_agents import Facts
from us_swing.core.desk_research import KINDS, TicketAsk, raise_tickets
from us_swing.market.checkin_note import CheckinNote, CheckinNoteSkill
from us_swing.market.lead_brief import LeadBrief, LeadBriefSkill

MORNING = "The market is choppy; favour Tech longs near their triggers and wait for a breakout."


def _ticket(kind: str = "setup_tuning", cap: int = 8_000, goal: str = "Test RSI limits 35 40 45"
            ) -> dict[str, Any]:
    return {"kind": kind, "topic": "pullback", "goal": goal,
            "done_test": "Any variant beats the base by 0.05R", "token_cap": cap}


def _brief(*tickets: dict[str, Any]) -> LeadBrief:
    return LeadBrief.model_validate({"picks": [], "morning": MORNING, "tickets": list(tickets)})


def _lead(home: Path, skill: str = "lead_brief") -> None:
    employee(home, "emp-l", "Lead A", "lead", skill)


def _act(env: Env, brief: LeadBrief) -> FakeCtx:
    ctx = FakeCtx(env.home, brief)
    LeadBriefSkill(env.candles, lambda: NOW).act(ctx, Facts("facts", env.day, True))
    return ctx


def _tickets(home: Path) -> list[Any]:
    return query(home, "SELECT kind, token_cap, status FROM tickets ORDER BY id")


def test_ticket_from_lead_plan(p5b: Env) -> None:
    """UT-MKT-014.001.M01.T01: A lead answer with one ticket adds one row; the brief is kept."""
    _lead(p5b.home)
    ctx = FakeCtx(p5b.home, _brief(_ticket()))
    items = LeadBriefSkill(p5b.candles, lambda: NOW).act(ctx, Facts("facts", p5b.day, True))
    assert [i.text for i in items] == [MORNING]
    assert _tickets(p5b.home) == [("setup_tuning", 8_000, "approved")]


def test_at_most_three() -> None:
    """UT-MKT-014.001.M01.T02: An answer with 4 tickets is not valid."""
    with pytest.raises(ValidationError):
        _brief(*(_ticket(goal=f"Goal number {i} to test") for i in range(4)))


def test_ticket_from_checkin(tmp_path: Path) -> None:
    """UT-MKT-014.001.M02.T01: A check-in answer with one ticket adds one row; the note stays."""
    home = tmp_path / "desk"
    _lead(home, "checkin_note")
    reply = CheckinNote(note="Quiet morning; AAA is near its trigger.",
                        tickets=[TicketAsk.model_validate(_ticket())])
    items = CheckinNoteSkill(tmp_path / "candles.db", lambda: NOW).act(
        FakeCtx(home, reply), Facts("facts", "2026-11-06", True))
    assert items[0].text.endswith("Quiet morning; AAA is near its trigger.")
    assert _tickets(home) == [("setup_tuning", 8_000, "approved")]


def test_unknown_kind(p5b: Env) -> None:
    """UT-MKT-014.002.M01.T01: An unknown kind drops only that ticket."""
    _lead(p5b.home)
    _act(p5b, _brief(_ticket(kind="guess"), _ticket(goal="A second goal to test")))
    assert _tickets(p5b.home) == [("setup_tuning", 8_000, "approved")]


def test_known_kinds(p5b: Env) -> None:
    """UT-MKT-014.002.M01.T02: Every one of the 6 kinds is accepted."""
    _lead(p5b.home)
    for i, kind in enumerate(KINDS):
        notes = raise_tickets(p5b.home, "lead_brief", [TicketAsk.model_validate(
            _ticket(kind=kind, goal=f"Goal for kind {kind}"))],
            NOW.replace(day=6 + i // 3), lambda _t: True)
        assert not notes[0].startswith("refused"), (kind, notes)
    assert len(_tickets(p5b.home)) == len(KINDS) == 6


def test_cap_range(p5b: Env) -> None:
    """UT-MKT-014.003.M01.T01: Caps 999 and 100,001 are refused; 1,000 and 100,000 added."""
    _lead(p5b.home)
    _act(p5b, _brief(_ticket(cap=999), _ticket(cap=1_000, goal="Second goal to test"),
                     _ticket(cap=100_000, goal="Third goal to test")))
    _act(p5b, _brief(_ticket(cap=100_001, goal="Fourth goal to test")))
    assert [r[1] for r in _tickets(p5b.home)] == [1_000, 100_000]


def test_cap_inside_range(p5b: Env) -> None:
    """UT-MKT-014.003.M01.T02: A cap of 5,000 is added as asked."""
    _lead(p5b.home)
    _act(p5b, _brief(_ticket(cap=5_000)))
    assert _tickets(p5b.home) == [("setup_tuning", 5_000, "approved")]


def test_research_block(p5b: Env) -> None:
    """UT-MKT-014.004.M01.T01: The facts show tokens left, open tickets and recent results."""
    _lead(p5b.home)
    _act(p5b, _brief(_ticket(), _ticket(goal="An ended goal to test")))
    from tests.desk.research_support import execute

    execute(p5b.home, "UPDATE tickets SET status = 'done', ended = ?, gain = 1, result = "
                      "'RSI 40 beats the base' WHERE id = 2", (NOW.isoformat(),))
    add_try(p5b.home, "emp-l", 5_000, part="research", payer="emp-l")
    _stage(p5b)
    facts = LeadBriefSkill(p5b.candles, lambda: NOW).facts(p5b.home)
    assert "Research tokens today: 5,000 used, 13,000 left of 18,000." in facts.text
    assert "- 1 setup_tuning: Test RSI limits 35 40 45 (approved)" in facts.text
    assert "An ended goal to test (done, gain yes): RSI 40 beats the base" in facts.text


def test_block_limits(p5b: Env) -> None:
    """UT-MKT-014.004.M01.T02: The block stays within 2,400 characters; no lead, no block."""
    _stage(p5b)
    skill = LeadBriefSkill(p5b.candles, lambda: NOW)
    plain = skill.facts(p5b.home).text
    assert plain
    assert "Research tickets:" not in plain
    _lead(p5b.home)
    from tests.desk.research_support import execute

    _act(p5b, _brief(_ticket()))
    for i in range(40):
        execute(p5b.home, "INSERT INTO tickets (kind, topic, goal, done_test, token_cap, "
                          "raised_by, raised_by_name, status, made, ended, gain, result) "
                          "VALUES ('post_mortem', 'losses', ?, 'x', 5000, 'emp-l', 'Lead A', "
                          "'done', ?, ?, 0, ?)",
                (f"Old goal {i} " + "y" * 80, NOW.isoformat(), NOW.isoformat(), "z" * 200))
    text = skill.facts(p5b.home).text
    block = text[text.index("Research tickets:"):]
    assert len(block) <= 2_400
    assert block.rstrip().endswith("do not repeat an open ticket or a recent result.")


def test_lead_never_researches(p5b: Env) -> None:
    """UT-MKT-014.005.M01.T01: The lead asks once; its approved ticket is not worked."""
    _lead(p5b.home)
    ctx = _act(p5b, _brief(_ticket()))
    assert len(ctx.asked) == 1
    assert _tickets(p5b.home) == [("setup_tuning", 8_000, "approved")]
    assert query(p5b.home, "SELECT steps, started FROM tickets") == [(0, None)]


def test_queue_decides(p5b: Env) -> None:
    """UT-MKT-014.005.M01.T02: The queue rules approve the small ticket and hold the big one."""
    _lead(p5b.home)
    _act(p5b, _brief(_ticket(cap=8_000), _ticket(cap=30_000, goal="A bigger goal to test")))
    assert [r[2] for r in _tickets(p5b.home)] == ["approved", "waiting"]


def test_queue_error_keeps_brief(p5b: Env, caplog: pytest.LogCaptureFixture,
                                 monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-MKT-014.005.M01.T03: A queue that cannot be written never loses the brief."""
    _lead(p5b.home)

    def broken(_home: Path) -> Any:
        raise OSError("disk gone")

    monkeypatch.setattr("us_swing.core.desk_research.connect", broken)
    ctx = FakeCtx(p5b.home, _brief(_ticket()))
    items = LeadBriefSkill(p5b.candles, lambda: NOW).act(ctx, Facts("facts", p5b.day, True))
    assert [i.text for i in items] == [MORNING]
    assert "[Research] Could not add the lead's tickets" in caplog.text
