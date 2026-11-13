"""Tests for AI Desk v3 M4 chat sessions: MD-MKT-010.001.M01 (core/desk_chat.py) and
MD-MKT-010.003.M03 (market/lead_chat.py). Employee names here are made up."""
from __future__ import annotations

import json
from dataclasses import replace
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, TypeVar

import pytest
from pydantic import BaseModel

import tests.desk.test_harness as th
from us_swing.core import desk_chat as dc
from us_swing.core import desk_memory
from us_swing.core.desk_ai_settings import DeskAiSettings, save_settings
from us_swing.core.desk_contract import DB_NAME, StepContext
from us_swing.core.desk_messages import Person, accept, inbox, refuse_inbox
from us_swing.core.desk_msg import Draft, Verdict
from us_swing.data.market_calendar import ET
from us_swing.desk.employees_step import EmployeesStep
from us_swing.desk.gateway import Reply
from us_swing.market import lead_chat as lc

T = TypeVar("T", bound=BaseModel)
NOW = datetime(2026, 11, 7, 12, 0, tzinfo=ET)
ROSTER = [Person("lead", "Lead", "lead_chat"), Person("exp", "Expert", "other")]
SUMMARY = {"summary": "Talked about tech.", "remember": [
    {"kind": "note", "text": "Tech topic summary"},
    {"kind": "note", "text": "Master prefers short answers"}]}


def _rows(home: Path, sql: str) -> list[tuple[Any, ...]]:
    con = sqlite3.connect(home / DB_NAME)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


class _Ctx:
    """Fake context: answers by schema; records the schemas asked."""

    def __init__(self, home: Path, answer: str | None = "An answer.",
                 summary: dict[str, Any] | None = None) -> None:
        self.home, self._answer, self._summary = home, answer, summary or SUMMARY
        self.asked: list[type[BaseModel]] = []

    def ask(self, facts: str, schema: type[T]) -> T | None:
        self.asked.append(schema)
        if schema is lc.LeadChatSummary:
            return None if self._answer is None else schema.model_validate(self._summary)
        return None if self._answer is None else schema.model_validate({"answer": self._answer})


class _Talk(_Ctx):
    """A talker context: each answer also writes the given drafts."""

    def __init__(self, home: Path, drafts: list[Draft]) -> None:
        super().__init__(home)
        self.talk = True
        self.drafts: list[Draft] = []
        self._new = drafts
        self.facts_seen = ""

    def send(self, draft: Draft) -> None:
        self.drafts.append(draft)

    def ask(self, facts: str, schema: type[T]) -> T | None:
        self.facts_seen = facts
        self.drafts.extend(self._new)
        return super().ask(facts, schema)


def _skill(now: datetime = NOW) -> lc.LeadChatSkill:
    return lc.LeadChatSkill(Path("missing-candles.db"), lambda: now)


def _new(home: Path, now: datetime = NOW, text: str = "Tech?") -> int:
    return dc.session_for(home, now, None, text, new=True)


def _talk(home: Path, sid: int, text: str, now: datetime = NOW, reply: str = "Ok.") -> int:
    qid = dc.ask_question(home, text, now, session=sid)
    dc.add_reply(home, qid, reply, True, now)
    return qid


def _ask_ask(subject: str = "x") -> Draft:
    return Draft(type="ask", to="exp", subject=subject, text="Your view?")


def _team(home: Path, qid: int, result: str = "done") -> None:
    asked = accept(home, [_ask_ask(dc.team_subject(qid))], "lead", ROSTER, NOW, "2026-11-07")
    assert asked == ["stored #1"] or asked[0].startswith("stored")
    row = inbox(home, "exp")[0]
    if result == "refused":
        refuse_inbox(home, [row], "not my area", NOW)
        return
    accept(home, [Draft(type="reply", parent=row.id, text="Team view: calm.",
                        verdict=Verdict(result="done"))], "exp", ROSTER, NOW, "2026-11-07")


def _replied(home: Path, text: str = "Why?") -> int:
    qid = dc.ask_question(home, text, NOW)
    dc.add_reply(home, qid, "First answer.", True, NOW)
    return qid


def test_sessions_off_default(tmp_path: Path) -> None:
    """UT-MKT-010.009.M01.T01: sessions are off by default and a plain ask makes no session."""
    assert DeskAiSettings().sessions_on is False
    qid = dc.ask_question(tmp_path, "Why?", NOW)
    assert _rows(tmp_path, f"SELECT session FROM chat WHERE id = {qid}") == [(None,)]
    assert _rows(tmp_path, "SELECT * FROM chat_sessions") == []


def test_off_facts_as_p9(tmp_path: Path) -> None:
    """UT-MKT-010.009.M03.T02: with sessions off, facts show the last 6 turns, no summary."""
    for i in range(8):
        dc.add_reply(tmp_path, dc.ask_question(tmp_path, f"Earlier {i}?", NOW), f"A{i}", True, NOW)
    dc.ask_question(tmp_path, "Now?", NOW)
    text = _skill().facts(tmp_path).text
    recent = text.split("Recent chat:")[1].split("Today (")[0]
    assert len([ln for ln in recent.splitlines() if ln.startswith(("Master:", "Lead:"))]) == 6
    assert "Session summary" not in text


def test_same_session_within_2h(tmp_path: Path) -> None:
    """UT-MKT-010.010.M01.T01: questions 90 minutes apart share one session titled by the first."""
    first = dc.session_for(tmp_path, NOW, None, "First topic question")
    dc.ask_question(tmp_path, "First topic question", NOW, session=first)
    later = NOW + timedelta(minutes=90)
    second = dc.session_for(tmp_path, later, None, "Other")
    dc.ask_question(tmp_path, "Other", later, session=second)
    assert first == second
    assert _rows(tmp_path, "SELECT DISTINCT session FROM chat") == [(first,)]
    assert dc.get_session(tmp_path, first).title == "First topic question"  # type: ignore[union-attr]


def test_new_session_after_2h(tmp_path: Path) -> None:
    """UT-MKT-010.010.M01.T02: a question 150 minutes later starts a new session."""
    first = dc.session_for(tmp_path, NOW, None, "One")
    second = dc.session_for(tmp_path, NOW + timedelta(minutes=150), None, "Two")
    assert first != second


def test_new_session_new_ny_day(tmp_path: Path) -> None:
    """UT-MKT-010.010.M01.T03: a question after midnight New York time starts a new session."""
    late = datetime(2026, 11, 7, 23, 30, tzinfo=ET)
    first = dc.session_for(tmp_path, late, None, "One")
    second = dc.session_for(tmp_path, late + timedelta(hours=1), None, "Two")
    assert first != second


def test_chosen_session(tmp_path: Path) -> None:
    """UT-MKT-010.010.M01.T04: a question goes into the chosen older session; rows never change."""
    old = _new(tmp_path, NOW, "Old")
    newer = _new(tmp_path, NOW + timedelta(minutes=10), "Newer")
    before = _rows(tmp_path, "SELECT * FROM chat")
    later = NOW + timedelta(minutes=20)
    chosen = dc.session_for(tmp_path, later, old, "Back to old")
    qid = dc.ask_question(tmp_path, "Back to old", later, session=chosen)
    assert chosen == old != newer
    assert _rows(tmp_path, f"SELECT session FROM chat WHERE id = {qid}") == [(old,)]
    assert _rows(tmp_path, "SELECT * FROM chat")[:len(before)] == before


def test_reopen_closed(tmp_path: Path) -> None:
    """UT-MKT-010.011.M01.T01: asking in a closed session opens it again and keeps its summary."""
    sid = _new(tmp_path)
    dc.close_session(tmp_path, sid)
    dc.save_summary(tmp_path, sid, "Kept summary")
    assert dc.get_session(tmp_path, sid).state == "closed"  # type: ignore[union-attr]
    dc.session_for(tmp_path, NOW + timedelta(minutes=5), sid, "More")
    got = dc.get_session(tmp_path, sid)
    assert got is not None and (got.state, got.summary) == ("open", "Kept summary")


def test_open_stays_open(tmp_path: Path) -> None:
    """UT-MKT-010.011.M01.T02: asking in an open session keeps it open and adds no session."""
    sid = _new(tmp_path)
    assert dc.session_for(tmp_path, NOW + timedelta(minutes=5), sid, "More") == sid
    assert [s.state for s in dc.sessions(tmp_path)] == ["open"]


def test_quiet_24h_closes(tmp_path: Path) -> None:
    """UT-MKT-010.012.M01.T01: a session quiet for 25 hours becomes closing on the next save."""
    old = _new(tmp_path, NOW - timedelta(hours=25))
    dc.session_for(tmp_path, NOW, None, "Fresh")
    assert dc.get_session(tmp_path, old).state == "closing"  # type: ignore[union-attr]


def test_quiet_under_24h_stays(tmp_path: Path) -> None:
    """UT-MKT-010.012.M01.T02: a session quiet for 23 hours stays open."""
    old = _new(tmp_path, NOW - timedelta(hours=23))
    dc.session_for(tmp_path, NOW, None, "Fresh")
    assert dc.get_session(tmp_path, old).state == "open"  # type: ignore[union-attr]


def test_new_discussion_closes(tmp_path: Path) -> None:
    """UT-MKT-010.012.M01.T03: close_session marks an open session closing."""
    sid = _new(tmp_path)
    dc.close_session(tmp_path, sid)
    assert dc.get_session(tmp_path, sid).state == "closing"  # type: ignore[union-attr]


def test_session_facts(tmp_path: Path) -> None:
    """UT-MKT-010.013.M03.T01: facts hold the session summary and only its own last 6 turns."""
    other = _new(tmp_path, NOW - timedelta(minutes=30), "Other")
    _talk(tmp_path, other, "Other topic?")
    sid = _new(tmp_path, NOW - timedelta(minutes=20), "Mine")
    for i in range(7):
        _talk(tmp_path, sid, f"Mine {i}?", NOW - timedelta(minutes=10))
    dc.close_session(tmp_path, sid)
    dc.save_summary(tmp_path, sid, "Mine is about tech")
    dc.session_for(tmp_path, NOW, sid, "x")
    dc.ask_question(tmp_path, "Now?", NOW, session=sid)
    text = _skill().facts(tmp_path).text
    recent = text.split("Recent chat:")[1].split("Today (")[0]
    assert "Session summary: Mine is about tech" in recent
    assert "Other topic?" not in recent and "Mine 3?" not in recent and "Mine 4?" in recent
    assert len([ln for ln in recent.splitlines() if ln.startswith(("Master:", "Lead:"))]) == 6


def test_no_summary_line(tmp_path: Path) -> None:
    """UT-MKT-010.013.M03.T02: a session without a summary has no summary line."""
    other = _new(tmp_path, NOW - timedelta(minutes=30), "Other")
    _talk(tmp_path, other, "Other topic?")
    sid = _new(tmp_path, NOW - timedelta(minutes=5), "Fresh")
    _talk(tmp_path, sid, "Mine 1?", NOW - timedelta(minutes=4))
    dc.ask_question(tmp_path, "Now?", NOW, session=sid)
    text = _skill().facts(tmp_path).text
    assert "Session summary" not in text
    assert "Master: Mine 1?" in text and "Other topic?" not in text


def test_closing_summary(tmp_path: Path) -> None:
    """UT-MKT-010.014.M03.T01: a closing session gets one AI call, a summary and state closed."""
    _on(tmp_path)
    sid = _new(tmp_path)
    _talk(tmp_path, sid, "Tech?")
    dc.close_session(tmp_path, sid)
    ctx = _Ctx(tmp_path)
    skill = _skill()
    skill.act(ctx, skill.facts(tmp_path))
    assert ctx.asked == [lc.LeadChatSummary]
    got = dc.get_session(tmp_path, sid)
    assert got is not None and (got.state, got.summary) == ("closed", "Talked about tech.")


def test_no_closing_no_summary(tmp_path: Path) -> None:
    """UT-MKT-010.014.M03.T02: only an open question gives the answer call and no summary call."""
    sid = _new(tmp_path)
    dc.ask_question(tmp_path, "Tech?", NOW, session=sid)
    ctx = _Ctx(tmp_path)
    skill = _skill()
    skill.act(ctx, skill.facts(tmp_path))
    assert ctx.asked == [lc.LeadChatAnswer]


def test_failed_summary_retried(tmp_path: Path) -> None:
    """UT-MKT-010.014.M03.T03: a failed summary leaves the session closing for the next wake."""
    _on(tmp_path)
    sid = _new(tmp_path)
    _talk(tmp_path, sid, "Tech?")
    dc.close_session(tmp_path, sid)
    skill = _skill()
    skill.act(_Ctx(tmp_path, answer=None), skill.facts(tmp_path))
    assert dc.get_session(tmp_path, sid).state == "closing"  # type: ignore[union-attr]
    skill.act(_Ctx(tmp_path), skill.facts(tmp_path))
    assert dc.get_session(tmp_path, sid).state == "closed"  # type: ignore[union-attr]


def test_two_summaries_a_wake(tmp_path: Path) -> None:
    """UT-MKT-010.014.M03.T04: three closing sessions give two summaries; the third waits."""
    _on(tmp_path)
    for i in range(3):
        sid = _new(tmp_path, NOW, f"Topic {i}")
        _talk(tmp_path, sid, f"Topic {i}?")
        dc.close_session(tmp_path, sid)
    ctx = _Ctx(tmp_path)
    skill = _skill()
    skill.act(ctx, skill.facts(tmp_path))
    assert len(ctx.asked) == 2
    assert [s.state for s in dc.sessions(tmp_path)].count("closing") == 1
    assert len(dc.closing_sessions(tmp_path)) == 1


def _step_run(home: Path, settings: DeskAiSettings) -> None:
    settings = replace(settings, sessions_on=True)
    save_settings(settings, home)
    th.employee(home, "c-1", th.job("c-1", "Chat Person", "lead", "lead_chat")
                .replace("trigger: after_run", "trigger: chat_question"))
    now = datetime.now(ET)
    sid = dc.session_for(home, now, None, "Tech?", new=True)
    qid = dc.ask_question(home, "Tech?", now, session=sid)
    dc.add_reply(home, qid, "Calm.", True, now)
    dc.close_session(home, sid)
    caller = th.FakeCaller(Reply(json.dumps(SUMMARY), 100, 20, 0.0))
    step = EmployeesStep(lambda: {"lead_chat": "us_swing.market.lead_chat:LeadChatSkill"},
                         lambda: [], lambda: settings, lambda: "key", caller,
                         lambda: datetime.now(ET))
    step.handle_events(StepContext(1, "event", datetime.now(ET), home))
    assert len(caller.calls) == 1


def _memories(home: Path) -> list[tuple[Any, ...]]:
    if not (home / "memory.db").exists():
        return []
    con = desk_memory.connect(home)
    try:
        return con.execute("SELECT owner, kind FROM memories").fetchall()
    finally:
        con.close()


def test_notes_kept_memory_on(tmp_path: Path) -> None:
    """UT-MKT-010.015.M03.T01: with Memory v2 on, the summary's 2 notes go to memory.db."""
    home = tmp_path / "desk"
    _step_run(home, DeskAiSettings(openrouter_on=True, openrouter_model="m", memory_v2_on=True))
    assert _memories(home) == [("c-1", "note"), ("c-1", "note")]
    assert dc.sessions(home)[0].summary == "Talked about tech."


def test_no_notes_memory_off(tmp_path: Path) -> None:
    """UT-MKT-010.015.M03.T02: with Memory v2 off no note is kept, the summary still is."""
    home = tmp_path / "desk"
    _step_run(home, DeskAiSettings(openrouter_on=True, openrouter_model="m"))
    assert _memories(home) == []
    got = dc.sessions(home)[0]
    assert (got.state, got.summary) == ("closed", "Talked about tech.")


def _on(home: Path, on: bool = True) -> None:
    save_settings(DeskAiSettings(sessions_on=on, messages_on=on), home)


def _answer_with(home: Path, drafts: list[Draft]) -> tuple[_Talk, int]:
    sid = _new(home)
    qid = dc.ask_question(home, "Tech?", NOW, session=sid)
    ctx = _Talk(home, drafts)
    skill = _skill()
    skill.act(ctx, skill.facts(home))
    return ctx, qid


def test_one_ask_kept(tmp_path: Path) -> None:
    """UT-MKT-010.016.M03.T01: one ask is kept, named after the question; the reply is saved."""
    _on(tmp_path)
    ctx, qid = _answer_with(tmp_path, [_ask_ask("anything")])
    assert [(d.type, d.subject) for d in ctx.drafts] == [("ask", f"Chat question #{qid}")]
    assert _rows(tmp_path, "SELECT text FROM chat WHERE role = 'lead'") == [("An answer.",)]
    assert lc.ASK_HINT in ctx.facts_seen


def test_extra_drafts_dropped(tmp_path: Path) -> None:
    """UT-MKT-010.016.M03.T02: with 2 asks and a send_back only the first ask is kept."""
    _on(tmp_path)
    drafts = [_ask_ask("one"), _ask_ask("two"),
              Draft(type="send_back", parent=1, verdict=Verdict(result="fix"), text="no")]
    ctx, _ = _answer_with(tmp_path, drafts)
    assert len(ctx.drafts) == 1 and ctx.drafts[0].type == "ask"


def test_sessions_off_no_draft(tmp_path: Path) -> None:
    """UT-MKT-010.016.M03.T03: with sessions off no draft is kept."""
    _on(tmp_path, False)
    ctx, _ = _answer_with(tmp_path, [_ask_ask()])
    assert ctx.drafts == [] and lc.ASK_HINT not in ctx.facts_seen


def test_update_from_reply(tmp_path: Path) -> None:
    """UT-MKT-010.017.M03.T01: a team reply gives one update row linked to the question."""
    _on(tmp_path)
    qid = _replied(tmp_path)
    _team(tmp_path, qid)
    ctx = _Ctx(tmp_path, "Team says calm.")
    skill = _skill()
    skill.act(ctx, skill.facts(tmp_path))
    assert _rows(tmp_path, "SELECT role, text, reply_to FROM chat WHERE role = 'update'") == [
        ("update", "Team says calm.", qid)]
    assert ctx.asked == [lc.LeadChatAnswer]


def test_refused_reply_update(tmp_path: Path) -> None:
    """UT-MKT-010.017.M03.T02: a refused team reply gives a code-written update, no AI call."""
    _on(tmp_path)
    qid = _replied(tmp_path)
    _team(tmp_path, qid, "refused")
    ctx = _Ctx(tmp_path)
    skill = _skill()
    skill.act(ctx, skill.facts(tmp_path))
    rows = _rows(tmp_path, "SELECT text, reply_to FROM chat WHERE role = 'update'")
    assert len(rows) == 1 and rows[0][1] == qid
    assert rows[0][0].startswith("The team could not answer") and "not my area" in rows[0][0]
    assert ctx.asked == []


def test_one_update_only(tmp_path: Path) -> None:
    """UT-MKT-010.017.M03.T03: a second wake adds no update and makes no AI call."""
    _on(tmp_path)
    qid = _replied(tmp_path)
    _team(tmp_path, qid)
    skill = _skill()
    skill.act(_Ctx(tmp_path, "Team says calm."), skill.facts(tmp_path))
    assert not skill.facts(tmp_path).fresh
    again = _Ctx(tmp_path, "Second.")
    skill.act(again, skill.facts(tmp_path))
    assert again.asked == []
    assert len(_rows(tmp_path, "SELECT id FROM chat WHERE role = 'update'")) == 1


def test_note_waiting_for_team(tmp_path: Path) -> None:
    """UT-MKT-010.018.M01.T01: a replied question with an open team ask shows the team note."""
    qid = _replied(tmp_path)
    accept(tmp_path, [_ask_ask(dc.team_subject(qid))], "lead", ROSTER, NOW, "2026-11-07")
    assert dc.question_note(tmp_path, qid, NOW, True) == dc.TEAM == "Waiting for the team"


def test_note_clears(tmp_path: Path) -> None:
    """UT-MKT-010.018.M01.T02: after the update row the note is empty."""
    qid = _replied(tmp_path)
    accept(tmp_path, [_ask_ask(dc.team_subject(qid))], "lead", ROSTER, NOW, "2026-11-07")
    assert dc.add_update(tmp_path, qid, "Update.", NOW)
    assert dc.question_note(tmp_path, qid, NOW, True) == ""


def test_logs(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-010.019.M03.T01: summary and update log lines carry the session and question."""
    _on(tmp_path)
    sid = _new(tmp_path)
    qid = _talk(tmp_path, sid, "Tech?")
    _team(tmp_path, qid)
    dc.close_session(tmp_path, sid)
    skill = _skill()
    with caplog.at_level(logging.INFO, logger="us_swing.market.lead_chat"):
        skill.act(_Ctx(tmp_path, "Team says calm."), skill.facts(tmp_path))
    assert f"[Chat] Session {sid} summary saved" in caplog.text
    assert f"[Chat] Update for question {qid} saved" in caplog.text


def test_off_no_summary(tmp_path: Path) -> None:
    """UT-MKT-010.009.M03.T03: with sessions off a closing session gets no AI call."""
    _on(tmp_path, False)
    sid = _new(tmp_path)
    _talk(tmp_path, sid, "Tech?")
    dc.close_session(tmp_path, sid)
    skill = _skill()
    facts = skill.facts(tmp_path)
    ctx = _Ctx(tmp_path)
    skill.act(ctx, facts)
    got = dc.get_session(tmp_path, sid)
    assert not facts.fresh and ctx.asked == []
    assert got is not None and got.state == "closing"


def test_bad_text_no_session(tmp_path: Path) -> None:
    """UT-MKT-010.010.M01.T05: an empty or too long question makes no session."""
    for text in ("  ", "x" * 501):
        with pytest.raises(ValueError):
            dc.session_for(tmp_path, NOW, None, text)
    assert dc.sessions(tmp_path) == []
