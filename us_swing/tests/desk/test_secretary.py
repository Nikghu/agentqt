"""Tests for desk/secretary.py — the desk secretary's weekly hire proposals (AI Desk v3 M7a).

Module: MD-DSK-006.016.M36. Employee names are made up.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.desk import proposal_support as ps
from us_swing.core.desk_agents import Facts
from us_swing.core.desk_ai_settings import DeskAiSettings, save_settings
from us_swing.core.desk_memory import log_failure
from us_swing.core.desk_messages import Person, accept, expire_due, inbox, refuse_inbox
from us_swing.core.desk_msg import Draft
from us_swing.core.desk_proposals import (
    AGREE,
    NO_ANSWER,
    NO_BOSS,
    NO_VIEW,
    OFF,
    PENDING,
    WAITING,
    decide_proposal,
    note_view,
    proposal_rows,
    save_proposal,
)
from us_swing.desk.secretary import ONLY_PROPOSALS, HirePick, HireReviewAnswer

ROSTER = [Person(ps.BOSS, "Helm", "boss_desk"), Person(ps.SEC, "Ledger", "hire_review", ps.BOSS)]


def _pick(candidate: str = "C1", model: str = "m", why: str = "Fails most mornings.") -> HirePick:
    return HirePick(candidate=candidate, source="openrouter", model=model, why=why)


def _answer(*picks: HirePick) -> HireReviewAnswer:
    return HireReviewAnswer(picks=list(picks))


def _act(home: Path, answer: HireReviewAnswer | None = None, *inbox_ids: int) -> ps.Ctx:
    ctx = ps.Ctx(home, answer)
    ps.secretary().act(ctx, Facts("facts", ps.DAY, True, inbox=tuple(inbox_ids)))
    return ctx


def _two_failing(home: Path) -> None:
    """The setup reviewer and a made-up second employee both fail."""
    ps.team(home)
    ps.hire(home, "emp-g", "Gale", "skill_y")
    ps.failing(home)
    ps.failing(home, "emp-g")


# ── facts (SRD-DSK-006.016) ─────────────────────────────────────────────────


def test_facts(home: Path) -> None:
    """UT-DSK-006.016.M36.T01: Fresh facts list the candidates, seats, this week's failure rows
    and the models."""
    _two_failing(home)
    for n in range(3):
        log_failure(home, "emp-p", f"refused: unknown format f{n}.v1", ps.DAY, ps.NOW)
    old = (ps.NOW - timedelta(days=10)).date().isoformat()
    log_failure(home, "emp-p", "an old failure", old, ps.NOW)
    facts = ps.secretary().facts(home)
    assert facts.fresh and facts.data_day == ps.DAY
    lines = facts.text.splitlines()
    assert ("- C1: failing need, skill setup review, level expert, holder Quill on "
            "openrouter / m") in lines
    assert any(line.startswith("- C2: failing need, skill skill y") for line in lines)
    assert "- expert: 3 of 8" in lines and "- junior: 0 of 30" in lines
    assert sum("refused: unknown format" in line for line in lines) == 3
    assert "an old failure" not in facts.text
    assert "- openrouter: default, m" in lines


def test_no_candidate(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-006.016.M36.T02: With no candidate the secretary makes no AI call."""
    ps.team(home)
    with caplog.at_level(logging.INFO):
        ctx = _act(home, _answer(_pick()))
    assert ctx.asked == 0 and ctx.drafts == [] and proposal_rows(home) == []
    assert "[Hiring] No hire need found for the week" in caplog.text


def test_ask_in_the_inbox(home: Path) -> None:
    """UT-DSK-006.016.M36.T03: An ask in the secretary's inbox gets a refused reply by code."""
    ps.team(home)
    out = accept(home, [Draft(type="ask", to=ps.SEC, subject="Any staff news?", text="Tell me")],
                 ps.BOSS, ROSTER, ps.NOW, ps.DAY)
    ctx = _act(home, None, int(out[0].split("#")[1]))
    assert ctx.asked == 0
    assert [(d.type, d.verdict.result if d.verdict else "", d.verdict.reason if d.verdict else "")
            for d in ctx.drafts] == [("reply", "refused", ONLY_PROPOSALS)]


# ── picks (SRD-DSK-006.017) ─────────────────────────────────────────────────


def test_picks_kept(home: Path) -> None:
    """UT-DSK-006.017.M36.T01: Two good picks make two proposals and two asks."""
    _two_failing(home)
    ctx = _act(home, _answer(_pick("C1"), _pick("C2")))
    assert ctx.asked == 1
    assert [(p.skill, p.state) for p in proposal_rows(home)] == [("skill_y", WAITING),
                                                                ("setup_review", WAITING)]
    assert len(ctx.drafts) == 2


def test_bad_picks_dropped(home: Path) -> None:
    """UT-DSK-006.017.M36.T02: An unknown candidate, an unknown model and a second pick for one
    skill are dropped; only the first good pick is kept."""
    ps.team(home)
    ps.hire(home, "emp-h", "Hale", "setup_review")
    ps.failing(home)
    ps.failing(home, "emp-h")
    assert _act(home, _answer(_pick("C9"), _pick("C1", model="zz"))).drafts == []
    assert proposal_rows(home) == []
    ctx = _act(home, _answer(_pick("C1"), _pick("C2")))
    assert [(p.skill, p.holder) for p in proposal_rows(home)] == [("setup_review", ps.FAIL)]
    assert len(ctx.drafts) == 1


class _TalkingModel(ps.Ctx):
    """Like the gateway when talking: the model's own messages land in the drafts."""

    def ask(self, facts: str, schema: type) -> object:
        self.drafts.append(Draft(type="ask", to=ps.FAIL, subject="Are you fine?", text="Tell me"))
        return super().ask(facts, schema)


def test_model_messages_dropped(home: Path) -> None:
    """UT-DSK-006.017.M36.T04: A message the model adds itself is dropped; only the code's ask to
    the boss is sent."""
    ps.team(home)
    ps.failing(home)
    ctx = _TalkingModel(home, _answer(_pick()))
    ps.secretary().act(ctx, Facts("facts", ps.DAY, True))
    assert [(d.type, d.to) for d in ctx.drafts] == [("ask", ps.BOSS)]


def test_answer_limits() -> None:
    """UT-DSK-006.017.M36.T03: Three picks or a reason of 301 characters are refused."""
    with pytest.raises(ValidationError):
        HireReviewAnswer.model_validate({"picks": [_pick().model_dump()] * 3})
    with pytest.raises(ValidationError):
        _pick(why="x" * 301)


# ── save and ask (SRD-DSK-006.018) ──────────────────────────────────────────


def test_saved_and_asked(home: Path) -> None:
    """UT-DSK-006.018.M36.T01: A kept pick is a waiting row with a pending view, and one ask to
    the boss carries its ``hire_proposal.v1`` row."""
    ps.team(home)
    ps.failing(home)
    ctx = _act(home, _answer(_pick()))
    found = proposal_rows(home)
    assert [(p.state, p.view, p.view_by, p.author, p.source, p.model) for p in found] == [
        (WAITING, PENDING, ps.BOSS, ps.SEC, "openrouter", "m")]
    draft = ctx.drafts[0]
    assert (draft.type, draft.to, draft.subject) == ("ask", ps.BOSS, "Hire proposal: setup review")
    assert draft.want is not None and draft.want.schema_id == "hire_proposal.v1"
    assert draft.want.inputs["proposal"] == found[0].id
    assert draft.want.inputs["holder"] == "Quill" and draft.want.inputs["need"] == "failing"
    assert draft.text is not None and "Why: Fails most mornings." in draft.text
    assert "Model: openrouter/m" in draft.text
    out = accept(home, ctx.drafts, ps.SEC, ROSTER, ps.NOW, ps.DAY)
    assert out[0].startswith("stored")


def test_no_boss(home: Path) -> None:
    """UT-DSK-006.018.M36.T02: With no active boss the proposal has view none and no ask."""
    ps.team(home, boss=False)
    ps.failing(home)
    ctx = _act(home, _answer(_pick()))
    assert [(p.state, p.view, p.view_note) for p in proposal_rows(home)] == [
        (WAITING, NO_VIEW, NO_BOSS)]
    assert ctx.drafts == []


# ── code replies (SRD-DSK-006.021) ──────────────────────────────────────────


def _replies(home: Path) -> list[int]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return [r[0] for r in con.execute(
            "SELECT id FROM messages WHERE type = 'reply' ORDER BY id").fetchall()]
    finally:
        con.close()


def test_code_reply_gives_no_view(home: Path) -> None:
    """UT-DSK-006.021.M36.T01: An expired ask and an ask refused by code give view none with the
    reason, set by the secretary with no AI call."""
    _two_failing(home)
    ctx = _act(home, _answer(_pick("C1"), _pick("C2")))
    accept(home, ctx.drafts, ps.SEC, ROSTER, ps.NOW, ps.DAY)
    second = [m for m in inbox(home, ps.BOSS) if m.body["want"]["inputs"]["skill"] == "skill_y"]
    refuse_inbox(home, second, "Helm cannot work now", ps.NOW)
    expire_due(home, ps.NOW + timedelta(minutes=11), ROSTER)
    after = _act(home, None, *_replies(home))
    assert after.asked == 0
    views = {p.skill: (p.view, p.view_note) for p in proposal_rows(home)}
    assert views == {"setup_review": (NO_VIEW, "no reply within 10 minutes"),
                     "skill_y": (NO_VIEW, "Helm cannot work now")}


def test_ai_view_is_kept(home: Path) -> None:
    """UT-DSK-006.021.M36.T02: A view already set by the boss turn is not changed by the
    secretary."""
    ps.team(home)
    ps.failing(home)
    ctx = _act(home, _answer(_pick()))
    accept(home, ctx.drafts, ps.SEC, ROSTER, ps.NOW, ps.DAY)
    pid = proposal_rows(home)[0].id
    assert note_view(home, pid, AGREE, ps.BOSS, "fits the plan", ps.NOW)
    expire_due(home, ps.NOW + timedelta(minutes=11), ROSTER)
    _act(home, None, *_replies(home))
    assert (proposal_rows(home)[0].view, proposal_rows(home)[0].view_note) == (
        AGREE, "fits the plan")


def test_no_answer_after_a_day(home: Path) -> None:
    """UT-DSK-006.021.M36.T03: At the weekly turn a view still pending after a day gets none with
    "no answer from the boss"; one made today stays pending."""
    ps.team(home)
    old = save_proposal(home, ps.SEC, ps.need(), "why", "openrouter", "m", ps.BOSS,
                        ps.NOW - timedelta(days=2))
    new = save_proposal(home, ps.SEC, ps.need("risk_check"), "why", "openrouter", "m", ps.BOSS,
                        ps.NOW)
    ctx = _act(home, _answer(_pick()))
    assert ctx.asked == 0
    views = {p.id: (p.view, p.view_note) for p in proposal_rows(home)}
    assert views == {old: (NO_VIEW, NO_ANSWER), new: (PENDING, "")}


# ── switch and logs (SRD-DSK-006.024, .027) ─────────────────────────────────


def test_messages_off(home: Path) -> None:
    """UT-DSK-006.024.M36.T01: With hire proposals on but messages off the facts are not fresh."""
    ps.team(home)
    ps.failing(home)
    save_settings(DeskAiSettings(hire_proposals_on=True), home)
    facts = ps.secretary().facts(home)
    assert (facts.fresh, facts.why_stale) == (False, OFF)


def test_log_lines(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-006.027.M36.T01: A sent proposal, a view, an approve and a turn with no candidate
    each log one ``[Hiring]`` line."""
    ps.team(home)
    ps.failing(home)
    with caplog.at_level(logging.INFO):
        _act(home, _answer(_pick()))
        pid = proposal_rows(home)[0].id
        note_view(home, pid, AGREE, ps.BOSS, "fits", ps.NOW)
        assert decide_proposal(home, pid, "approve", ps.NOW) == ""
        _act(home, _answer(_pick()))
    text = caplog.text
    assert f"[Hiring] Proposal #{pid} sent to Helm: trial for setup review" in text
    assert f"[Hiring] Helm agrees with proposal #{pid}" in text
    assert f"[Hiring] Proposal #{pid} approved: trial hire Expert 1 started" in text
    assert "[Hiring] No hire need found for the week" in text
