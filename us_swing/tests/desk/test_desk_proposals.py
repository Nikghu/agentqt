"""Tests for core/desk_proposals.py — hire needs, candidates, proposals and gate 1
(AI Desk v3 M7a).

Module: MD-DSK-006.012.M35; also MD-DSK-012.001.M28 (format seed), MD-DSK-004.005.M13
(switch) and MD-DSK-003.004.M15 (event rule). Employee names are made up.
"""
from __future__ import annotations

import sqlite3
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from tests.desk import proposal_support as ps
from us_swing.core.desk_ai_settings import (
    SETTINGS_FILE,
    DeskAiSettings,
    load_settings,
    save_settings,
)
from us_swing.core.desk_events import EVENT_RULES, EventRule
from us_swing.core.desk_hiring import employees
from us_swing.core.desk_proposals import (
    AGREE,
    APPROVED,
    COSTLY,
    DECIDED,
    EMPTY,
    FAILING,
    NOT_SAVED,
    PENDING,
    REJECTED,
    WAITING,
    Need,
    candidates,
    decide_proposal,
    find_needs,
    note_view,
    proposal_rows,
    proposal_text,
    save_proposal,
    waiting_proposals,
)
from us_swing.core.desk_registry import HIRE_PROPOSAL, fill_registry, seed_formats
from us_swing.core.desk_tasks import fill_plans, get_plan
from us_swing.market.lead_brief import LeadBriefSkill

SEATS_FULL = "Seats: 4 of 2 expert seats are taken; raise the cap in Desk settings before you approve."


def _approvals(home: Path) -> list[tuple[Any, ...]]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute("SELECT kind, subject, decision, detail FROM approvals").fetchall()
    finally:
        con.close()


def _lead_team(home: Path, skip: str = "news_review") -> None:
    """A lead brief holder and active holders of every skill it needs but ``skip``."""
    ps.hire(home, "emp-l", "Helm", "lead_brief", level="lead")
    for n, skill in enumerate(LeadBriefSkill.needs):
        if skill != skip:
            ps.hire(home, f"emp-n{n}", f"Holder {n}", skill)


def _empty_need() -> Need:
    return Need(EMPTY, "news_review", "expert", "", ("Nobody holds news review; Helm needs it.",))


# ── need rules (SRD-DSK-006.012–.014) ───────────────────────────────────────


def test_failing_need(home: Path) -> None:
    """UT-DSK-006.012.M35.T01: An employee with 9 valid of 15 tries is a failing need."""
    ps.team(home)
    ps.failing(home)
    found = find_needs(home)
    assert [(n.kind, n.skill, n.level, n.holder) for n in found] == [
        (FAILING, "setup_review", "expert", ps.FAIL)]
    assert found[0].evidence == ("Quill (setup review): 9 valid answers in 15 tries over the "
                                 "last 5 data days (60%).",)


def test_not_failing(home: Path) -> None:
    """UT-DSK-006.012.M35.T02: 4 tries with no valid answer, or 7 valid of 10, is no need."""
    ps.team(home)
    ps.hire(home, "emp-x", "Wren", "skill_x")
    ps.tries(home, ps.FAIL, ps.DAY, 4, 0)
    ps.tries(home, "emp-x", ps.DAY, 10, 7)
    assert find_needs(home) == []


def test_window_and_row_kinds(home: Path) -> None:
    """UT-DSK-006.012.M35.T03: Bad tries on an older 11th data day, in shadow or in replay are
    not counted."""
    ps.team(home)
    window = ps.days(11)
    ps.tries(home, ps.FAIL, window[0], 10, 0)
    for day in window[1:]:
        ps.tries(home, ps.FAIL, day, 1, 1)
    ps.tries(home, ps.FAIL, ps.DAY, 10, 0, shadow=1)
    ps.tries(home, ps.FAIL, ps.DAY, 10, 0, replay=1)
    assert find_needs(home) == []


def test_costly_need(home: Path) -> None:
    """UT-DSK-006.013.M35.T01: At USD 0.05, 0.08, 0.10 and 0.40 per valid answer the last one
    is costly; the middle is 0.09."""
    ps.team(home)
    for n, cost in enumerate((0.05, 0.08, 0.10, 0.40)):
        ps.hire(home, f"emp-c{n}", f"Coster {n}", f"skill_{n}")
        ps.tries(home, f"emp-c{n}", ps.DAY, 4, 4, cost=cost)
    found = find_needs(home)
    assert [(n.kind, n.holder) for n in found] == [(COSTLY, "emp-c3")]
    assert found[0].evidence == ("Coster 3 (skill 3): USD 0.40 per valid answer over the last 1 "
                                 "data day; the desk middle is USD 0.09.",)


def test_no_middle(home: Path) -> None:
    """UT-DSK-006.013.M35.T02: With only 2 employees with a cost, or costs of 0, nobody is
    costly."""
    ps.team(home)
    for n, cost in enumerate((0.05, 0.90)):
        ps.hire(home, f"emp-c{n}", f"Coster {n}", f"skill_{n}")
        ps.tries(home, f"emp-c{n}", ps.DAY, 4, 4, cost=cost)
    assert find_needs(home) == []
    ps.hire(home, "emp-c2", "Coster 2", "skill_2")
    ps.tries(home, "emp-c2", ps.DAY, 4, 4)
    assert find_needs(home) == []


def test_empty_need(home: Path) -> None:
    """UT-DSK-006.014.M35.T01: The lead brief needs news review and its holder is retired."""
    _lead_team(home)
    ps.hire(home, "emp-r", "Retiree", "news_review", status="retired")
    found = find_needs(home)
    assert [(n.kind, n.skill, n.level, n.holder) for n in found] == [
        (EMPTY, "news_review", "expert", "")]
    assert found[0].evidence[0].startswith("Nobody holds news review; Helm")


def test_all_held(home: Path) -> None:
    """UT-DSK-006.014.M35.T02: Every needed skill has an active holder, so no empty need."""
    _lead_team(home, skip="")
    assert find_needs(home) == []


def test_shadow_is_not_a_holder(home: Path) -> None:
    """UT-DSK-006.014.M35.T03: A needed skill held only by a shadow hire is an empty need."""
    _lead_team(home)
    ps.hire(home, "emp-t", "Trial", "news_review", status="shadow")
    assert [(n.kind, n.skill) for n in find_needs(home)] == [(EMPTY, "news_review")]


# ── candidates (SRD-DSK-006.015) ─────────────────────────────────────────────


def test_candidates(home: Path) -> None:
    """UT-DSK-006.015.M35.T01: Failing, costly and empty needs become C1, C2 and C3, each with a
    seat line while the expert seats are full."""
    _lead_team(home)
    save_settings(DeskAiSettings(expert_cap=2), home)
    ps.failing(home, "emp-n2")
    for n, cost in ((0, 0.05), (1, 0.08), (4, 0.40)):
        ps.tries(home, f"emp-n{n}", ps.DAY, 4, 4, cost=cost)
    found = candidates(home, ps.NOW)
    assert [(c.id, c.need.kind, c.need.skill, c.need.level, c.need.holder) for c in found] == [
        ("C1", FAILING, "setup_review", "expert", "emp-n2"),
        ("C2", COSTLY, "risk_check", "expert", "emp-n4"),
        ("C3", EMPTY, "news_review", "expert", "")]
    assert all(c.need.evidence[-1] == SEATS_FULL and len(c.need.evidence) == 2 for c in found)


def test_dropped_candidates(home: Path) -> None:
    """UT-DSK-006.015.M35.T02: A failing lead, a skill with a waiting proposal, a skill with a
    shadow hire and a need rejected 10 days ago give no candidate."""
    _lead_team(home)
    ps.failing(home, "emp-l")
    ps.failing(home, "emp-n2")
    save_proposal(home, ps.SEC, ps.need(holder="emp-n2"), "why", "openrouter", "m", None, ps.NOW)
    for n, cost in ((0, 0.05), (1, 0.08), (4, 0.40)):
        ps.tries(home, f"emp-n{n}", ps.DAY, 4, 4, cost=cost)
    ps.hire(home, "emp-t", "Trial", "risk_check", status="shadow")
    then = ps.NOW - timedelta(days=10)
    gone = save_proposal(home, ps.SEC, _empty_need(), "why", "openrouter", "m", None, then)
    assert decide_proposal(home, gone, "reject", then) == ""
    assert candidates(home, ps.NOW) == []


def test_reject_block_ends(home: Path) -> None:
    """UT-DSK-006.015.M35.T03: A need rejected 31 days ago is a candidate again."""
    _lead_team(home)
    then = ps.NOW - timedelta(days=31)
    gone = save_proposal(home, ps.SEC, _empty_need(), "why", "openrouter", "m", None, then)
    assert decide_proposal(home, gone, "reject", then) == ""
    assert [c.need.skill for c in candidates(home, ps.NOW)] == ["news_review"]


# ── format, switch and event (SRD-DSK-006.019, .024, .011) ──────────────────


def test_format_seeded() -> None:
    """UT-DSK-006.019.M28.T01: ``hire_proposal.v1`` is seeded with 7 columns, key proposal."""
    found = {f.id: f for f in seed_formats()}["hire_proposal.v1"]
    assert found == HIRE_PROPOSAL
    assert [c.name for c in found.columns] == ["proposal", "need", "skill", "holder",
                                               "evidence", "model", "why"]
    assert found.key == "proposal" and all(c.by is None for c in found.columns)


def test_format_has_no_plan(home: Path) -> None:
    """UT-DSK-006.019.M28.T02: Filling the plans makes no plan for ``hire_proposal.v1``."""
    fill_registry(home, ps.NOW)
    fill_plans(home, ps.NOW)
    assert get_plan(home, "hire_proposal.v1") is None
    assert get_plan(home, "setup_table.v1") is not None


def test_switch(home: Path) -> None:
    """UT-DSK-006.024.M13.T01: Hire proposals are off by default; true is kept."""
    assert DeskAiSettings().hire_proposals_on is False
    home.mkdir(parents=True)
    (home / SETTINGS_FILE).write_text('{"messages_on": true}', encoding="utf-8")
    assert load_settings(home).hire_proposals_on is False
    save_settings(DeskAiSettings(hire_proposals_on=True), home)
    assert load_settings(home).hire_proposals_on is True


def test_event_rule() -> None:
    """UT-DSK-006.011.M15.T01: ``weekly_report`` has priority 2, no deadline, 1 day expiry."""
    assert EVENT_RULES["weekly_report"] == EventRule(2, None, timedelta(days=1))


# ── gate 1 (SRD-DSK-006.022, .023) ──────────────────────────────────────────


def test_approve_starts_the_trial(home: Path) -> None:
    """UT-DSK-006.022.M35.T01: Approve starts the trial hire as Expert 4 in shadow."""
    for n in (1, 2, 3):
        ps.hire(home, f"emp-0{n}", f"Expert {n}", f"skill_{n}")
    save_settings(ps.SETTINGS, home)
    pid = save_proposal(home, ps.SEC, ps.need(), "fails most days", "openrouter", "m", ps.BOSS,
                        ps.NOW)
    assert decide_proposal(home, pid, "approve", ps.NOW) == ""
    new = next(e for e in employees(home) if e.name == "Expert 4")
    assert (new.skill, new.level, new.status, new.model) == (
        "setup_review", "expert", "shadow", "openrouter / m")
    found = proposal_rows(home)[0]
    assert (found.state, found.hire) == (APPROVED, new.id)
    assert _approvals(home) == [("proposal", "setup_review", "approve",
                                 f"proposal #{pid}: {new.id}")]


def test_refused_hire(home: Path) -> None:
    """UT-DSK-006.022.M35.T02: With the 8 expert seats taken, Approve returns the reason and the
    proposal keeps waiting."""
    save_settings(DeskAiSettings(expert_cap=8), home)
    for n in range(8):
        ps.hire(home, f"emp-0{n}", f"Seat {n}", f"skill_{n}")
    pid = save_proposal(home, ps.SEC, ps.need(), "why", "openrouter", "m", None, ps.NOW)
    assert decide_proposal(home, pid, "approve", ps.NOW) == "all 8 expert seats are taken"
    assert proposal_rows(home)[0].state == WAITING
    assert len(employees(home)) == 8
    assert _approvals(home) == []


def test_files_error_puts_it_back(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-DSK-006.022.M35.T03: When the employee files cannot be written the proposal is back to
    waiting with the reason, and no approvals row is kept."""
    def broken(*_args: object) -> tuple[str | None, str]:
        raise OSError("disk full")

    monkeypatch.setattr("us_swing.core.desk_proposals.start_hire", broken)
    pid = save_proposal(home, ps.SEC, ps.need(), "why", "openrouter", "m", None, ps.NOW)
    assert decide_proposal(home, pid, "approve", ps.NOW) == (
        "the employee files could not be written: disk full")
    found = proposal_rows(home)[0]
    assert (found.state, found.decided, found.hire) == (WAITING, "", "")
    assert _approvals(home) == []


def test_reject(home: Path) -> None:
    """UT-DSK-006.023.M35.T01: Reject closes the proposal and adds an approvals row."""
    pid = save_proposal(home, ps.SEC, ps.need(), "why", "openrouter", "m", None, ps.NOW)
    assert decide_proposal(home, pid, "reject", ps.NOW) == ""
    assert proposal_rows(home)[0].state == REJECTED
    assert _approvals(home) == [("proposal", "setup_review", "reject", f"proposal #{pid}")]


def test_decided_proposal(home: Path) -> None:
    """UT-DSK-006.023.M35.T02: A decided or unknown proposal cannot be decided again."""
    pid = save_proposal(home, ps.SEC, ps.need(), "why", "openrouter", "m", None, ps.NOW)
    assert decide_proposal(home, pid, "reject", ps.NOW) == ""
    assert decide_proposal(home, pid, "approve", ps.NOW) == DECIDED
    assert decide_proposal(home, pid, "reject", ps.NOW) == DECIDED
    assert decide_proposal(home, 99, "reject", ps.NOW) == DECIDED
    assert decide_proposal(home, pid, "maybe", ps.NOW) == "unknown decision maybe"
    assert len(_approvals(home)) == 1


# ── reads and card text (SRD-DSK-006.026) ───────────────────────────────────


def test_reads_and_card_text(home: Path) -> None:
    """UT-DSK-006.026.M35.T01: Proposals newest first, only the waiting one in the waiting
    list, and its card text with the evidence and the view line."""
    ps.team(home)
    first = save_proposal(home, ps.SEC, ps.need(), "a", "openrouter", "m", ps.BOSS, ps.NOW)
    second = save_proposal(home, ps.SEC, ps.need("risk_check"), "b", "openrouter", "m", None,
                           ps.NOW)
    third = save_proposal(home, ps.SEC, _empty_need(), "Setup review fails most mornings.",
                          "openrouter", "m", ps.BOSS, ps.NOW)
    assert decide_proposal(home, first, "reject", ps.NOW) == ""
    assert decide_proposal(home, second, "reject", ps.NOW) == ""
    assert [p.id for p in proposal_rows(home)] == [third, second, first]
    waiting = waiting_proposals(home)
    assert [p.id for p in waiting] == [third]
    assert waiting[0].view == PENDING
    assert proposal_text(home, waiting[0]).splitlines() == [
        "Empty needed skill. Nobody holds news review; Helm needs it.",
        "Why: Setup review fails most mornings.", "Model: openrouter/m",
        "Waiting for Helm's view."]
    assert note_view(home, third, AGREE, ps.BOSS, "the plan needs it", ps.NOW)
    assert proposal_text(home, waiting_proposals(home)[0]).splitlines()[-1] == (
        "Helm agrees: the plan needs it")


def test_reads_without_data(home: Path) -> None:
    """UT-DSK-006.026.M35.T02: With no desk database the reads are empty."""
    assert proposal_rows(home) == [] and waiting_proposals(home) == []
    assert candidates(home, ps.NOW) == []


def test_broken_database(home: Path) -> None:
    """UT-DSK-006.026.M35.T03: With a broken desk database the screen reads are empty, a decision
    says it was not saved and the candidates raise instead of looking like no proposal."""
    home.mkdir(parents=True)
    (home / "desk.db").write_bytes(b"this is not a database" * 100)
    assert proposal_rows(home) == [] and waiting_proposals(home) == []
    assert decide_proposal(home, 1, "approve", ps.NOW) == NOT_SAVED
    with pytest.raises(sqlite3.DatabaseError):
        candidates(home, ps.NOW)
