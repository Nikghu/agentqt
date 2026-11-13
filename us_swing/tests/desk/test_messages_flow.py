"""Tests for the M1 message flow through the gateway (M11), router (M16) and employees step (M10).

Employee names here are made up: code must never depend on them.
"""
from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from us_swing.core.desk_agents import AgentContext, Facts, FeedItem
from us_swing.core.desk_ai_settings import DeskAiSettings
from us_swing.core.desk_contract import StepContext
from us_swing.core.desk_messages import Person, accept, inbox
from us_swing.core.desk_msg import Draft, InboxReply
from us_swing.desk.employees_step import EmployeesStep
from us_swing.desk.gateway import Gateway, Reply
from us_swing.desk.recorder import NY, Attempt, Recorder
from us_swing.desk.registry import load_employee

NOW = datetime(2026, 11, 6, 9, 0, tzinfo=NY)
DAY = "2026-11-06"
SOUL = "You are {name}, {title}."
SKILLS = {k: f"tests.desk.test_messages_flow:{v}" for k, v in
          (("asker", "AskerSkill"), ("answerer", "AnswererSkill"),
           ("follower", "FollowerSkill"))}
ON = DeskAiSettings(openrouter_on=True, openrouter_model="m", claude_on=True,
                    claude_model="c", messages_on=True)
OFF = replace(ON, messages_on=False)
ASK_JSON = {"word": "x", "messages": [{"type": "ask", "to": "skill:answerer", "subject": "Q",
                                       "text": "Any news for NVDA?"}]}


class View(BaseModel):
    """Answer of the fake skills."""

    word: str


@dataclass
class World:
    """What the fake skills do and saw this test."""

    fresh: dict[str, bool] = field(default_factory=dict)
    answer_inbox: bool = True
    woke: list[tuple[str, tuple[int, ...]]] = field(default_factory=list)


W = World()


@pytest.fixture(autouse=True)
def _reset() -> Iterator[None]:
    global W
    W = World()
    yield


class _Base:
    key = ""
    needs: tuple[str, ...] = ()
    answer = View
    talks = True

    def facts(self, home: Path) -> Facts:
        fresh = W.fresh.get(self.key, True)
        return Facts(f"facts of {self.key}", DAY, fresh, "" if fresh else "news is old")

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        W.woke.append((self.key, facts.inbox))
        view = ctx.ask(facts.text, View)
        return [FeedItem("info", f"{self.key} {view.word}", DAY)] if view and not facts.inbox \
            else []


class AskerSkill(_Base):
    """Asks the answerer on its normal wake."""

    key = "asker"


class AnswererSkill(_Base):
    """Answers its inbox with a reply only."""

    key = "answerer"

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        if facts.inbox:
            W.woke.append((self.key, facts.inbox))
            if W.answer_inbox:
                ctx.ask(facts.text, InboxReply)
            return []
        return super().act(ctx, facts)


class FollowerSkill(_Base):
    """Needs the asker, so it shows when the asker's turn is done."""

    key = "follower"
    needs = ("asker",)


class Caller:
    """Answers by who is asked and what the inbox holds; records every call."""

    def __init__(self, asker_tokens: int = 100) -> None:
        self.calls: list[tuple[str, str]] = []
        self.asker_tokens = asker_tokens

    def __call__(self, source: str, model: str, system: str, user: str, key: str) -> Reply:
        who = re.search(r"You are (\w+)", system)
        name = who.group(1) if who else "?"
        self.calls.append((name, system))
        if "INBOX" in user and "ask from" in user:
            parent = int(re.search(r"#(\d+) ask from", user).group(1))  # type: ignore[union-attr]
            body = {"messages": [{"type": "reply", "parent": parent,
                                  "verdict": {"result": "done"}, "text": "Earnings Thursday"}]}
        elif name == "Asker" and "INBOX" not in user:
            body = ASK_JSON
        else:
            body = {"word": "ok"}
        tokens = self.asker_tokens if name == "Asker" else 100
        return Reply(json.dumps(body), tokens, 20, 0.0)


def _job(emp_id: str, name: str, skill: str, extra: str = "") -> str:
    return f"""id: {emp_id}
name: {name}
title: Test helper
level: expert
reports_to: null
skill: {skill}
version: 1
trigger: after_run
models:
  primary: {{source: openrouter, model: m}}
  backup: {{source: claude, model: default}}
calls_per_day: 20
monthly_cost_usd: 3.0
kpis: [valid answers]
{extra}"""


def _team(home: Path, extra: dict[str, str] | None = None) -> None:
    for emp_id, name, skill in (("emp-a", "Asker", "asker"), ("emp-b", "Answerer", "answerer"),
                                ("emp-c", "Follower", "follower")):
        folder = home / "employees" / emp_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "job.yaml").write_text(_job(emp_id, name, skill, (extra or {}).get(emp_id, "")),
                                         encoding="utf-8")
        (folder / "soul.md").write_text(SOUL, encoding="utf-8")


CLOCK = [NOW]


def _step(caller: Caller, settings: DeskAiSettings = ON) -> EmployeesStep:
    return EmployeesStep(lambda: SKILLS, lambda: [], lambda: settings, lambda: "key", caller,
                         lambda: CLOCK[0])


def _run(step: EmployeesStep, home: Path) -> None:
    step(StepContext(1, "manual", CLOCK[0], home))


def _rows(home: Path, sql: str) -> list[Any]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute(sql).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        con.close()


@pytest.fixture
def home(tmp_path: Path) -> Path:
    CLOCK[0] = NOW
    return tmp_path / "desk"


def _order(names: list[str]) -> list[str]:
    return [n for n in names]


# ── M11 gateway ──────────────────────────────────────────────────────────────


def _gateway(home: Path, talk: bool) -> tuple[Gateway, Caller, Recorder]:
    _team(home)
    hire = load_employee(home / "employees" / "emp-a", SKILLS)
    assert hire is not None
    rec, caller = Recorder(home), Caller()
    return Gateway(home, hire, rec, ON, "key", 1, DAY, caller, lambda: NOW, talk=talk), \
        caller, rec


def test_talking_gateway(home: Path) -> None:
    """UT-DSK-011.016.M11.T01: Talking gateway."""
    gate, caller, rec = _gateway(home, True)
    assert gate.ask("facts", View) is not None
    rec.close()
    assert '"messages"' in caller.calls[0][1]
    assert [d.type for d in gate.drafts] == ["ask"]


def test_quiet_gateway(home: Path) -> None:
    """UT-DSK-011.016.M11.T02: Quiet gateway."""
    gate, caller, rec = _gateway(home, False)
    assert gate.ask("facts", View) is not None
    rec.close()
    assert '"messages"' not in caller.calls[0][1] and gate.drafts == []


# ── M10 / M16 flow ───────────────────────────────────────────────────────────


def test_ask_and_reply_in_one_run(home: Path) -> None:
    """UT-DSK-011.027.M10.T01: Ask and reply in one run."""
    _team(home)
    _run(_step(Caller()), home)
    assert [k for k, _ in W.woke] == ["asker", "answerer", "answerer", "asker", "follower"] \
        or [k for k, _ in W.woke] == ["answerer", "asker", "answerer", "asker", "follower"]
    assert _rows(home, "SELECT type, sender, receiver, state FROM messages ORDER BY id") == [
        ("ask", "emp-a", "emp-b", "completed"), ("reply", "emp-b", "emp-a", "completed")]
    asker_inbox = [box for k, box in W.woke if k == "asker" and box]
    assert asker_inbox == [(2,)]


def test_chain_waits_for_reply(home: Path) -> None:
    """UT-DSK-011.029.M16.T01: Chain waits for the reply."""
    _team(home)
    _run(_step(Caller()), home)
    order = [k for k, _ in W.woke]
    assert order.index("follower") > max(i for i, k in enumerate(order) if k == "asker")


def test_nothing_open(home: Path) -> None:
    """UT-DSK-011.029.M16.T02: Nothing open."""
    _team(home)
    _run(_step(Caller(), OFF), home)
    assert [k for k, _ in W.woke].count("asker") == 1
    assert "follower" in [k for k, _ in W.woke]


def test_expiry_releases_chain(home: Path) -> None:
    """UT-DSK-011.029.M16.T03: Expiry releases the chain."""
    _team(home)
    W.answer_inbox = False
    step = _step(Caller())
    _run(step, home)
    assert "follower" not in [k for k, _ in W.woke]
    CLOCK[0] = NOW + timedelta(minutes=11)
    step.handle_events(StepContext(1, "manual", CLOCK[0], home))
    assert "follower" in [k for k, _ in W.woke]
    assert ("expired",) in _rows(home, "SELECT state FROM messages WHERE type = 'ask'")


def test_receiver_cannot_work(home: Path) -> None:
    """UT-DSK-011.028.M10.T01: Receiver cannot work."""
    _team(home)
    W.fresh["answerer"] = False
    _run(_step(Caller()), home)
    replies = _rows(home, "SELECT sender, receiver, body FROM messages WHERE type = 'reply'")
    assert len(replies) == 1 and replies[0][:2] == ("emp-b", "emp-a")
    verdict = json.loads(replies[0][2])["verdict"]
    assert verdict["result"] == "refused" and "news is old" in verdict["reason"]
    assert ("asker", (2,)) in W.woke


def test_receiver_works(home: Path) -> None:
    """UT-DSK-011.028.M10.T02: Receiver works."""
    _team(home)
    _run(_step(Caller()), home)
    bodies = [json.loads(b) for (b,) in _rows(home, "SELECT body FROM messages "
                                                     "WHERE type = 'reply'")]
    assert [b["verdict"]["result"] for b in bodies] == ["done"]


def test_starter_pays(home: Path) -> None:
    """UT-DSK-011.030.M10.T01: Starter pays."""
    _team(home)
    _run(_step(Caller()), home)
    rows = _rows(home, "SELECT employee, payer, part, message FROM activity "
                       "WHERE message IS NOT NULL ORDER BY id")
    assert ("emp-b", "emp-a", "plan", 1) in rows


def test_starter_out_of_tokens(home: Path) -> None:
    """UT-DSK-011.030.M10.T02: Starter out of tokens."""
    _team(home, {"emp-a": "tokens_per_day: 1000"})
    _run(_step(Caller(asker_tokens=900)), home)  # the asker's own call uses its plan part
    calls_b = _rows(home, "SELECT COUNT(*) FROM activity WHERE employee = 'emp-b' "
                          "AND message IS NOT NULL")
    assert calls_b == [(0,)]
    reply = _rows(home, "SELECT body FROM messages WHERE type = 'reply'")
    assert "used up" in json.loads(reply[0][0])["verdict"]["reason"]


def test_messages_on(home: Path) -> None:
    """UT-DSK-011.031.M10.T01: Messages on."""
    _team(home)
    caller = Caller()
    _run(_step(caller), home)
    assert any('"messages"' in system for _, system in caller.calls)
    assert _rows(home, "SELECT COUNT(*) FROM messages") == [(2,)]


def test_messages_off(home: Path) -> None:
    """UT-DSK-011.031.M10.T02: Messages off."""
    _team(home)
    caller = Caller()
    _run(_step(caller, OFF), home)
    assert not any('"messages"' in system for _, system in caller.calls)
    assert [k for k, _ in W.woke] in (["asker", "answerer", "follower"],
                                      ["answerer", "asker", "follower"])


def test_nothing_stored_while_off(home: Path) -> None:
    """UT-DSK-011.014.M29.T02: Nothing stored while off."""
    _team(home)
    _run(_step(Caller(), OFF), home)
    assert _rows(home, "SELECT COUNT(*) FROM messages") in ([], [(0,)])
    assert _rows(home, "SELECT COUNT(*) FROM events WHERE kind = 'message'") == [(0,)]


def test_addressed_wake(home: Path) -> None:
    """UT-DSK-011.025.M16.T01: Addressed wake."""
    _team(home)
    roster = [Person("emp-a", "Asker", "asker"), Person("emp-b", "Answerer", "answerer")]
    accept(home, [Draft(type="ask", to="emp-b", subject="Q", text="Any news?")], "emp-a",
           roster, CLOCK[0], DAY)
    step = _step(Caller())
    step.handle_events(StepContext(1, "manual", CLOCK[0], home))
    assert [k for k, _ in W.woke] == ["answerer", "asker"]  # the reply wakes the asker


def test_target_not_loaded(home: Path) -> None:
    """UT-DSK-011.025.M16.T02: Target not loaded."""
    _team(home)
    roster = [Person("emp-a", "Asker", "asker"), Person("emp-z", "Ghost", "answerer")]
    accept(home, [Draft(type="ask", to="emp-z", subject="Q", text="Any news?")], "emp-a",
           roster, CLOCK[0], DAY)
    _step(Caller()).handle_events(StepContext(1, "manual", CLOCK[0], home))
    assert W.woke == []
    assert _rows(home, "SELECT state, note FROM events WHERE kind = 'message'") == [
        ("done", "nobody listens")]


def test_no_rewake_gap(home: Path) -> None:
    """UT-DSK-011.025.M16.T03: No rewake gap."""
    _team(home)
    rec = Recorder(home)
    rec.add(Attempt(1, "emp-b", "Answerer", 1, DAY, (NOW - timedelta(minutes=5)).isoformat(),
                    "openrouter", "m", 1, "p", "a", True, "", 1, 1, 0.0, 1.0))
    rec.close()
    roster = [Person("emp-a", "Asker", "asker"), Person("emp-b", "Answerer", "answerer")]
    accept(home, [Draft(type="ask", to="emp-b", subject="Q", text="Any news?")], "emp-a",
           roster, CLOCK[0], DAY)
    _step(Caller()).handle_events(StepContext(1, "manual", CLOCK[0], home))
    assert [k for k, _ in W.woke] == ["answerer", "asker"]
    rec = Recorder(home)
    last = rec.last_wake("emp-b")
    rec.close()
    assert last == NOW - timedelta(minutes=5)
    assert inbox(home, "emp-a") == []  # the asker read the reply


class CodeOnlySkill(_Base):
    """Finishes its turn without asking the model."""

    key = "codeonly"

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        W.woke.append((self.key, facts.inbox))
        return [FeedItem("info", "code only", DAY)]


def test_code_only_turn_is_ok(home: Path) -> None:
    """UT-DSK-003.014.M10.T02: A turn with no model call ends ok: no retry, no alert."""
    folder = home / "employees" / "emp-x"
    folder.mkdir(parents=True)
    (folder / "job.yaml").write_text(_job("emp-x", "Coder", "codeonly"), encoding="utf-8")
    (folder / "soul.md").write_text(SOUL, encoding="utf-8")
    skills = {"codeonly": "tests.desk.test_messages_flow:CodeOnlySkill"}
    step = EmployeesStep(lambda: skills, lambda: [], lambda: OFF, lambda: "key", Caller(),
                         lambda: CLOCK[0], send=lambda _text: None)
    _run(step, home)
    assert _rows(home, "SELECT result, tries FROM steps") == [("ok", 1)]
    assert _rows(home, "SELECT COUNT(*) FROM alerts") in ([], [(0,)])
