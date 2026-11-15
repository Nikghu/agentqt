"""Tests for the hire proposal GUI (AI Desk v3 M7a): the Ask card, Approve and Reject, the
Proposals list in Hiring and the Hire proposals switch.

Modules: MD-GUI-034.054.M32 (cards), MD-GUI-034.053.M31 (card buttons), MD-GUI-034.027.M21
(Hiring) and MD-GUI-034.016.M15 (settings). Employee names are made up.
"""
from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from tests.desk import proposal_support as ps
from us_swing.core.desk_ai_settings import load_settings
from us_swing.core.desk_feed import FeedCard, ask_cards
from us_swing.core.desk_hiring import employees
from us_swing.core.desk_proposals import (
    AGREE,
    DECIDED,
    REJECTED,
    decide_proposal,
    note_view,
    proposal_rows,
    save_proposal,
)
from us_swing.gui.ai_desk_hiring import NO_PROPOSALS, HiringPanel
from us_swing.gui.ai_desk_settings import DeskAiSettingsForm
from us_swing.gui.floor_feed import FeedCardWidget, FeedContext

WHY = "Setup review fails most mornings."


def _proposal(home: Path, skill: str = "setup_review") -> int:
    return save_proposal(home, ps.SEC, ps.need(skill), WHY, "openrouter", "m", ps.BOSS, ps.NOW)


def _cards(home: Path) -> list[FeedCard]:
    return [c for c in ask_cards(home, ps.NOW) if c.ref == "proposal"]


def _widget(qtbot: QtBot, home: Path, card: FeedCard) -> FeedCardWidget:
    widget = FeedCardWidget(card, FeedContext(home, None, lambda: ps.NOW))
    qtbot.addWidget(widget)
    return widget


# ── card (SRD-GUI-034.081) ──────────────────────────────────────────────────


def test_proposal_card(tmp_path: Path) -> None:
    """UT-GUI-034.081.M32.T01: A waiting proposal is one Ask card with its need, evidence, why,
    model and the boss's view."""
    ps.team(tmp_path)
    pid = _proposal(tmp_path)
    note_view(tmp_path, pid, AGREE, ps.BOSS, "fits the plan", ps.NOW)
    cards = _cards(tmp_path)
    assert [(c.kind, c.sender, c.subject, c.item) for c in cards] == [
        ("ask", "Hiring", "Hire proposal · setup review", pid)]
    assert cards[0].text.splitlines() == [
        "Failing employee. Quill (setup review): 9 valid answers in 15 tries over the last 5 "
        "data days (60%).", f"Why: {WHY}", "Model: openrouter/m", "Helm agrees: fits the plan"]


def test_no_card_once_decided(tmp_path: Path) -> None:
    """UT-GUI-034.081.M32.T02: Approved and rejected proposals have no card."""
    ps.team(tmp_path)
    first, second = _proposal(tmp_path), _proposal(tmp_path, "risk_check")
    assert decide_proposal(tmp_path, first, "approve", ps.NOW) == ""
    assert decide_proposal(tmp_path, second, "reject", ps.NOW) == ""
    assert _cards(tmp_path) == []


# ── buttons (SRD-GUI-034.082) ───────────────────────────────────────────────


def test_approve_and_reject(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.082.M31.T01: Approve starts the trial hire and Reject closes the other card;
    both cards are gone after the reload."""
    ps.team(tmp_path)
    first, second = _proposal(tmp_path), _proposal(tmp_path, "risk_check")
    widgets = {c.item: _widget(qtbot, tmp_path, c) for c in _cards(tmp_path)}
    approve, reject = widgets[first], widgets[second]
    assert approve.approve_btn is not None and reject.reject_btn is not None
    assert approve.approve_btn.isEnabled()
    with qtbot.waitSignal(approve.decided, timeout=2000):
        approve.approve_btn.click()
    with qtbot.waitSignal(reject.decided, timeout=2000):
        reject.reject_btn.click()
    assert [e.skill for e in employees(tmp_path) if e.status == "shadow"] == ["setup_review"]
    assert [p.state for p in proposal_rows(tmp_path)] == [REJECTED, "approved"]
    assert _cards(tmp_path) == []


def test_refused_approve(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.082.M31.T02: With the expert seats full the card shows the reason and keeps
    its buttons."""
    ps.team(tmp_path)
    for n in range(6):
        ps.hire(tmp_path, f"emp-0{n}", f"Seat {n}", f"skill_{n}")
    _proposal(tmp_path)
    widget = _widget(qtbot, tmp_path, _cards(tmp_path)[0])
    assert widget.approve_btn is not None
    widget.approve_btn.click()
    assert not widget.note.isHidden()
    assert widget.note.text() == "all 8 expert seats are taken"
    assert widget.approve_btn.isEnabled()
    assert len(_cards(tmp_path)) == 1


def test_decided_elsewhere(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.082.M31.T03: A card whose proposal was decided on another card shows that and
    turns its buttons off."""
    ps.team(tmp_path)
    _proposal(tmp_path)
    card = _cards(tmp_path)[0]
    command, floor = _widget(qtbot, tmp_path, card), _widget(qtbot, tmp_path, card)
    assert command.reject_btn is not None and floor.approve_btn is not None
    with qtbot.waitSignal(command.decided, timeout=2000):
        command.reject_btn.click()
    floor.approve_btn.click()
    assert floor.note.text() == DECIDED
    assert floor.reject_btn is not None
    assert not floor.approve_btn.isEnabled() and not floor.reject_btn.isEnabled()


# ── Proposals list (SRD-GUI-034.083) ────────────────────────────────────────


def test_proposals_list(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.083.M21.T01: Hiring shows the proposals newest first; choosing one shows its
    evidence, why and view."""
    ps.team(tmp_path)
    _proposal(tmp_path)
    _proposal(tmp_path, "risk_check")
    panel = HiringPanel(tmp_path)
    qtbot.addWidget(panel)
    table = panel.proposals
    assert table.rowCount() == 2
    assert [table.item(r, 1).text() for r in range(2)] == ["risk check", "setup review"]
    assert [table.item(0, c).text() for c in range(2, 6)] == [
        "failing", "openrouter/m", "pending", "waiting"]
    table.setCurrentCell(1, 0)
    text = panel.proposal_detail.text()
    assert "Quill (setup review)" in text and f"Why: {WHY}" in text
    assert text.endswith("Waiting for Helm's view.")
    assert panel.no_proposals.isHidden()


def test_chosen_proposal_kept(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.083.M21.T03: The chosen proposal stays chosen after a reload with a new one."""
    ps.team(tmp_path)
    _proposal(tmp_path)
    _proposal(tmp_path, "risk_check")
    panel = HiringPanel(tmp_path)
    qtbot.addWidget(panel)
    panel.proposals.setCurrentCell(1, 0)
    _proposal(tmp_path, "news_review")
    panel.reload()
    row = panel.proposals.currentRow()
    assert panel.proposals.item(row, 1).text() == "setup review"
    assert "Quill (setup review)" in panel.proposal_detail.text()


def test_no_proposals(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.083.M21.T02: With no proposal Hiring shows the empty note."""
    ps.team(tmp_path)
    panel = HiringPanel(tmp_path)
    qtbot.addWidget(panel)
    assert panel.no_proposals.text() == NO_PROPOSALS == "No proposals yet"
    assert not panel.no_proposals.isHidden() and panel.proposals.isHidden()


# ── switch (SRD-GUI-034.084) ────────────────────────────────────────────────


def test_hire_proposals_switch(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.084.M15.T01: Ticking Hire proposals saves hire_proposals_on."""
    form = DeskAiSettingsForm(tmp_path)
    qtbot.addWidget(form)
    assert not form.hire_proposals_on.isChecked()
    form.messages_on.setChecked(True)
    form.hire_proposals_on.setChecked(True)
    assert form.save()
    assert load_settings(tmp_path).hire_proposals_on is True


def test_hire_proposals_need_messages(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.084.M15.T02: The Hire proposals box is greyed while agent messages are off."""
    form = DeskAiSettingsForm(tmp_path)
    qtbot.addWidget(form)
    assert not form.hire_proposals_on.isEnabled()
    form.messages_on.setChecked(True)
    assert form.hire_proposals_on.isEnabled()
    form.messages_on.setChecked(False)
    assert not form.hire_proposals_on.isEnabled()
