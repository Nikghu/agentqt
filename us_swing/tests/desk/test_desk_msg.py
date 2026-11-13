"""Tests for MD-DSK-011.001.M27 — core/desk_msg.py."""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from pydantic import ValidationError

from tests.desk.conftest import FakeClock
from us_swing.core.desk_msg import (
    AskBody,
    DecisionBody,
    State,
    Thread,
    body_schema,
    dump,
    load,
    message_schema,
    parse_body,
    reason,
)
from us_swing.desk.process import DeskProcess

AT = "2026-11-12T08:20:04-05:00"
DUE = "2026-11-12T08:45:00-05:00"
WANT = {"goal": "Find semis ready to break out", "done_when": "every symbol has a row",
        "inputs": {"symbols": ["AVGO", "MU"]}, "schema": "setup_table.v1"}
DATA = {"schema": "setup_table.v1", "cols": ["symbol", "rs"], "rows": [["AVGO", 92]]}


def _msg(body: dict[str, Any], **head: Any) -> dict[str, Any]:
    kind = body["type"]
    data: dict[str, Any] = {"id": 2, "thread": 1, "sender": "emp-003", "at": AT,
                            "state": "submitted", "body": body}
    if kind in ("reply", "send_back", "decision"):
        data["parent"] = 1
    if kind not in ("reply", "send_back"):
        data["to"] = ["skill:regime_view", "emp-002"] if kind == "meeting" else "emp-006"
    data.update(head)
    return data


EXAMPLES: dict[str, dict[str, Any]] = {
    "ask": _msg({"type": "ask", "subject": "Table for 2 semis", "want": WANT}, due=DUE),
    "task": _msg({"type": "task", "card": "TC-0731-A",
                  "want": {**WANT, "tools": ["step.regime@1"]}}, to="champion:technical"),
    "reply": _msg({"type": "reply", "verdict": {"result": "done"}, "data": DATA},
                  meta={"used": ["step.regime@1"], "secs": 1.4}),
    "send_back": _msg({"type": "send_back", "verdict": {"result": "fix", "reason": "Stop 11%"},
                       "text": "Tighten the stop."}, due=DUE),
    "handover": _msg({"type": "handover", "subject": "Ideas ready", "text": "Six ideas."}),
    "escalate": _msg({"type": "escalate", "subject": "NVDA plan broken", "text": "Below stop.",
                      "about": ["NVDA"], "flags": [{"about": "NVDA", "note": "Downgrade"}]},
                     to="boss", meta={"ai": {"tok": 330, "model": "haiku"}}),
    "meeting": _msg({"type": "meeting", "subject": "Choppy or strong?", "text": "One reason."}),
    "decision": _msg({"type": "decision", "subject": "Semis only",
                      "verdict": {"result": "decided", "agreed": ["emp-002"],
                                  "disagreed": ["emp-001"]}}, state="completed"),
    "feedback": _msg({"type": "feedback", "subject": "Grades were right", "text": "3 of 4.",
                      "data": {"schema": "pick_results.v1", "ref": "desk.db:pick_results/46",
                               "n": 4}}, state="completed"),
}


def _refused(data: dict[str, Any]) -> str:
    with pytest.raises(ValidationError) as exc:
        load(data)
    return reason(exc.value)


def _body(kind: str, **change: Any) -> dict[str, Any]:
    data = dict(EXAMPLES[kind])
    data["body"] = {**data["body"], **change}
    return data


def test_round_trip_every_type() -> None:
    """UT-DSK-011.001.M27.T01: Round trip of every type."""
    for kind, data in EXAMPLES.items():
        msg = load(data)
        assert msg.type == kind
        out = dump(msg)
        assert "schema" not in out
        assert load(out) == msg


def test_broken_envelope() -> None:
    """UT-DSK-011.001.M27.T02: Broken envelope."""
    ask = EXAMPLES["ask"]
    assert _refused({k: v for k, v in ask.items() if k != "body"}).startswith("body")
    assert _refused({k: v for k, v in ask.items() if k != "at"}).startswith("at")
    assert "extra" in _refused({**ask, "priority": 1}).lower()


def test_thread_row() -> None:
    """UT-DSK-011.002.M27.T01: Thread row."""
    thread = Thread(id=701, starter="emp-003", msgs=2, rounds=1,
                    opened=datetime(2026, 11, 12, 13, 20, tzinfo=UTC))
    assert thread.state == "open"
    assert Thread.model_validate_json(thread.model_dump_json()) == thread


def test_bad_thread_state() -> None:
    """UT-DSK-011.002.M27.T02: Bad thread state."""
    opened = datetime(2026, 11, 12, tzinfo=UTC)
    with pytest.raises(ValidationError):
        Thread(id=1, starter="emp-003", msgs=1, state="paused", opened=opened)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        Thread(id=1, starter="emp-003", msgs=1, rounds=-1, opened=opened)


def test_header_rules_met() -> None:
    """UT-DSK-011.003.M27.T01: Header rules met."""
    ask = load(EXAMPLES["ask"])
    assert ask.parent is None and ask.due is not None
    reply = load(EXAMPLES["reply"])
    assert reply.parent == 1 and reply.due is None


def test_header_rules_broken() -> None:
    """UT-DSK-011.003.M27.T02: Header rules broken."""
    assert "due" in _refused({**EXAMPLES["handover"], "due": DUE})
    assert "parent" in _refused({k: v for k, v in EXAMPLES["reply"].items() if k != "parent"})
    assert _refused({**EXAMPLES["ask"], "at": "2026-11-12T08:20:04"}).startswith("at")


def test_good_addresses() -> None:
    """UT-DSK-011.004.M27.T01: Good addresses."""
    for to in ("emp-003", "skill:news_review", "champion:technical", "boss", "master"):
        assert load({**EXAMPLES["ask"], "to": to}).to == to
    assert load(EXAMPLES["meeting"]).to == ["skill:regime_view", "emp-002"]


def test_bad_addresses() -> None:
    """UT-DSK-011.004.M27.T02: Bad addresses."""
    ask = EXAMPLES["ask"]
    assert _refused({**ask, "to": "Expert 3"}).startswith("to")
    assert _refused({**ask, "to": "skill:News"}).startswith("to")
    assert "list" in _refused({**ask, "to": ["emp-001", "emp-002"]})
    assert "left out" in _refused({**EXAMPLES["reply"], "to": "emp-001"})
    assert "needs to" in _refused({k: v for k, v in ask.items() if k != "to"})
    assert _refused({**EXAMPLES["meeting"], "to": []}).startswith("to")


def test_type_picks_body() -> None:
    """UT-DSK-011.005.M27.T01: Type picks the body."""
    assert isinstance(parse_body(EXAMPLES["ask"]["body"]), AskBody)
    assert isinstance(parse_body(EXAMPLES["decision"]["body"]), DecisionBody)
    msg = load(EXAMPLES["decision"])
    assert msg.type == msg.body.type == "decision"


def test_foreign_and_unknown_keys() -> None:
    """UT-DSK-011.005.M27.T02: Foreign and unknown keys."""
    assert "verdict" in _refused(_body("ask", verdict={"result": "done"}))
    assert "colour" in _refused(_body("reply", colour="red"))
    assert _refused(_body("ask", type="chat")).startswith("body")


def test_refused_reply_needs_only_reason() -> None:
    """UT-DSK-011.006.M27.T01: Refused reply needs only a reason."""
    data = _msg({"type": "reply", "verdict": {"result": "refused", "reason": "No tool for it."}},
                state="refused")
    assert load(data).state is State.REFUSED


def test_missing_required_fields() -> None:
    """UT-DSK-011.006.M27.T02: Missing required fields."""
    ask = dict(EXAMPLES["ask"])
    ask["body"] = {"type": "ask", "want": WANT}
    assert "subject" in _refused(ask)
    assert "text or data" in _refused(_msg({"type": "reply", "verdict": {"result": "done"}}))
    assert "reason" in _refused(_msg({"type": "reply", "verdict": {"result": "refused"}}))
    assert "want" in _refused(_msg({"type": "task", "card": "TC-1"}))


def test_limits_at_edge() -> None:
    """UT-DSK-011.007.M27.T01: Limits at the edge."""
    flags = [{"about": f"S{i}", "note": "n"} for i in range(5)]
    data = _body("escalate", subject="s" * 80, text="t" * 600,
                 about=[f"S{i}" for i in range(20)], flags=flags)
    assert len(load(data).body.subject) == 80  # type: ignore[union-attr]


def test_limits_passed() -> None:
    """UT-DSK-011.007.M27.T02: Limits passed."""
    assert _refused(_body("escalate", subject="s" * 81))
    assert _refused(_body("escalate", subject="two\nlines"))
    assert _refused(_body("escalate", text="t" * 601))
    assert _refused(_body("escalate", about=[f"S{i}" for i in range(21)]))
    assert _refused(_body("escalate", flags=[{"about": "A", "note": "n"}] * 6))
    assert _refused(_body("send_back", verdict={"result": "fix", "reason": "r" * 201}))


def test_want_on_task() -> None:
    """UT-DSK-011.008.M27.T01: Want on a task."""
    msg = load(EXAMPLES["task"])
    assert msg.body.want.tools == ["step.regime@1"]  # type: ignore[union-attr]
    assert "max_tokens" not in dump(msg)["body"]["want"]


def test_bad_want() -> None:
    """UT-DSK-011.008.M27.T02: Bad want."""
    assert "task" in _refused(_body("ask", want={**WANT, "tools": ["step.regime@1"]}))
    assert _refused(_body("ask", want={**WANT, "goal": "g" * 121}))
    assert _refused(_body("task", want={**WANT, "tools": ["step.regime"]}))


def test_verdicts_by_type() -> None:
    """UT-DSK-011.009.M27.T01: Verdicts by type."""
    assert load(_body("reply", verdict={"result": "partial"}))
    assert load(EXAMPLES["send_back"])
    assert load(EXAMPLES["decision"]).body.verdict.agreed == ["emp-002"]  # type: ignore[union-attr]


def test_verdict_of_another_type() -> None:
    """UT-DSK-011.009.M27.T02: Verdict of another type."""
    assert "fix, reject" in _refused(_body("send_back", verdict={"result": "done"}))
    assert "done" in _refused(_body("reply", verdict={"result": "decided"}))
    assert "decision" in _refused(_body("reply", verdict={"result": "done",
                                                          "agreed": ["emp-001"]}))


def test_data_block_forms() -> None:
    """UT-DSK-011.010.M27.T01: Data block forms."""
    rows = [["S", i] for i in range(200)]
    assert load(_body("reply", data={**DATA, "rows": rows}))
    assert load(_body("reply", data={"schema": "pick_results.v1", "ref": "desk.db:x/1",
                                     "n": 480}))


def test_bad_data_block() -> None:
    """UT-DSK-011.010.M27.T02: Bad data block."""
    def bad(data: dict[str, Any]) -> str:
        return _refused(_body("reply", data=data))
    assert bad({**DATA, "rows": [["S", i] for i in range(201)]})
    assert "not both" in bad({**DATA, "ref": "desk.db:x/1", "n": 1})
    assert "neither" in bad({"schema": "setup_table.v1"})
    assert "n is given" in bad({"schema": "setup_table.v1", "ref": "desk.db:x/1"})
    assert "n is given" in bad({**DATA, "n": 1})
    assert bad({**DATA, "schema": "scores_v1"})


def test_meta_only_when_set() -> None:
    """UT-DSK-011.011.M27.T01: Meta only when set."""
    assert "meta" not in dump(load(EXAMPLES["handover"]))
    out = dump(load({**EXAMPLES["handover"], "meta": {"used": ["data.recipe@1"]}}))
    assert out["meta"] == {"used": ["data.recipe@1"]}
    assert all(v not in (None, [], {}) for v in out["body"].values())


def test_bad_meta() -> None:
    """UT-DSK-011.011.M27.T02: Bad meta."""
    assert "not desk.msg/1" in _refused({**EXAMPLES["ask"], "meta": {"schema": "desk.msg/1"}})
    assert "cost" in _refused({**EXAMPLES["ask"], "meta": {"cost": 0.1}})


def test_state_names() -> None:
    """UT-DSK-011.012.M27.T01: State names."""
    assert [s.value for s in State] == [
        "submitted", "working", "input_required", "completed", "failed", "canceled",
        "refused", "expired",
    ]


def test_unknown_state() -> None:
    """UT-DSK-011.012.M27.T02: Unknown state."""
    assert _refused({**EXAMPLES["ask"], "state": "open"}).startswith("state")
    assert _refused({**EXAMPLES["ask"], "state": "blocked"}).startswith("state")


def test_json_schema_accepts_dumps() -> None:
    """UT-DSK-011.013.M27.T01: JSON Schema accepts the dumps."""
    schema = message_schema()
    for data in EXAMPLES.values():
        jsonschema.validate(dump(load(data)), schema)


def test_json_schema_refuses() -> None:
    """UT-DSK-011.013.M27.T02: JSON Schema refuses what models refuse."""
    schema = body_schema("ask")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"type": "ask"}, schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"type": "ask", "subject": "s", "extra": 1}, schema)


def test_format_only() -> None:
    """UT-DSK-011.014.M27.T01: Format only."""
    src = Path(__file__).parents[2] / "src" / "us_swing"
    users = [p.name for p in src.rglob("*.py")
             if p.name not in ("desk_msg.py", "desk_registry.py")
             and "desk_msg" in p.read_text(encoding="utf-8")]
    assert users == []


def test_no_message_tables(home: Path, clock: FakeClock) -> None:
    """UT-DSK-011.014.M27.T02: No message tables."""
    proc = DeskProcess(home, clock=clock, sleep=lambda _s: None)
    assert proc.start()
    proc.close()
    con = sqlite3.connect(home / "desk.db")
    names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    con.close()
    assert "tools" in names
    assert not {"messages", "threads"} & names
