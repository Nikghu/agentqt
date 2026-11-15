"""Tests for MD-DSK-013.003.M40 — desk/tool_builder.py (AI Desk v3 M7b): chat asks become
requests, the facts, the answer with one fix round, the checks on sample stocks, the states and
the reply. The model is a queue of made-up answers; most runs use a stand-in for the sandbox.

Stock and employee names here are made up.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path

import pytest

from tests.desk import builder_support as bs
from us_swing.core.desk_agents import Facts
from us_swing.core.desk_built_tools import (
    CHECKS,
    EXPIRED,
    FAILED,
    REVIEW,
    STOPPED,
    ToolAnswer,
    add_request,
    ask_tool,
    built_tool_rows,
    disable_tool,
    enable_tool,
    get_request,
    set_request,
    tool_requests,
)
from us_swing.core.desk_messages import read_message
from us_swing.core.desk_msg import Draft, ReplyBody, Verdict
from us_swing.core.desk_registry import list_formats, list_tools
from us_swing.core.desk_tasks import plan_rows
from us_swing.desk.sandbox import run_code
from us_swing.desk.tool_builder import NO_ANSWER, NOTHING, ToolBuilderSkill, facts_text, run_checks

NOW = bs.NOW
BAD = "import os\n" + bs.GOOD_CODE


def _skill(runs: bs.Runs | None = None) -> ToolBuilderSkill:
    return ToolBuilderSkill(clock=lambda: NOW, run=runs or bs.Runs())


def _home(tmp_path: Path, on: bool = True) -> Path:
    bs.on(tmp_path, tool_builder_on=on)
    bs.team(tmp_path)
    bs.stocks(tmp_path)
    return tmp_path


def _act(home: Path, answers: list[ToolAnswer | None], inbox: tuple[int, ...] = (),
         runs: bs.Runs | None = None, extra: tuple[Draft, ...] = ()) -> bs.Ctx:
    ctx = bs.Ctx(home, answers, extra)
    _skill(runs).act(ctx, Facts("Tool builder", bs.DAY, True, inbox=inbox))
    return ctx


def _replies(ctx: bs.Ctx) -> list[Draft]:
    return [d for d in ctx.drafts if d.type == "reply"]


# ── chat asks (SRD-DSK-013.002) ─────────────────────────────────────────────


def test_chat_ask_to_request(tmp_path: Path) -> None:
    """UT-DSK-013.002.M40.T01: An ask becomes one chat request with its id, asker, text and the
    upper-cased stocks."""
    home = _home(tmp_path)
    mid = bs.ask(home, {"request": "Percent below the 52-week high", "symbols": ["avgo", "MU"]})
    _act(home, [bs.answer()], (mid,))
    (req,) = tool_requests(home)
    assert (req.source, req.message, req.asker, req.text, req.symbols) == (
        "chat", mid, bs.ASKER, "Percent below the 52-week high", ("AVGO", "MU"))


def test_request_text_fallback(tmp_path: Path) -> None:
    """UT-DSK-013.002.M40.T02: With no request input the text is the goal; with no want it is
    the ask's text."""
    home = _home(tmp_path)
    first = bs.ask(home, {}, goal="Gap of each stock today")
    second = bs.ask(home, None, text="Build a volume ratio tool")
    _act(home, [bs.answer(), bs.answer(name="volume_ratio")], (first, second))
    texts = {r.message: r.text for r in tool_requests(home)}
    assert texts == {first: "Gap of each stock today", second: "Build a volume ratio tool"}


def test_reply_in_inbox_is_no_request(tmp_path: Path) -> None:
    """UT-DSK-013.002.M40.T03: A reply in the builder's inbox makes no request and gets no
    reply."""
    home = _home(tmp_path)
    question = bs.accept(home, [Draft(type="ask", to=bs.ASKER, subject="Which stocks?",
                                      text="Which stocks?")], bs.BUILDER, bs.ROSTER, NOW,
                         bs.DAY)
    asked = int(question[0].split("#")[1])
    answer = bs.accept(home, [Draft(type="reply", parent=asked, text="AVGO",
                                    verdict=Verdict(result="done"))], bs.ASKER,
                       bs.ROSTER, NOW, bs.DAY)
    reply = int(answer[0].split("#")[1])
    found = read_message(home, reply)
    assert found is not None and isinstance(found.body, ReplyBody)
    ctx = _act(home, [], (reply,))
    assert tool_requests(home) == [] and ctx.drafts == [] and ctx.asked == 0


# ── the wake (SRD-DSK-013.003) ──────────────────────────────────────────────


def test_all_new_requests(tmp_path: Path) -> None:
    """UT-DSK-013.003.M40.T01: Two new requests are both built in one wake, oldest first, with
    one AI call each."""
    home = _home(tmp_path)
    first = ask_tool(home, "Below the high", NOW - timedelta(minutes=2))
    second = ask_tool(home, "Volume ratio", NOW - timedelta(minutes=1))
    ctx = _act(home, [bs.answer(), bs.answer(name="volume_ratio")])
    assert ctx.asked == 2
    assert f"#{first} " in ctx.texts[0] and f"#{second} " in ctx.texts[1]
    assert [(r.id, r.state) for r in tool_requests(home)] == [(second, "done"), (first, "done")]


def test_nothing_to_do(tmp_path: Path) -> None:
    """UT-DSK-013.003.M40.T02: With no request and no ask the facts are not fresh."""
    home = _home(tmp_path)
    facts = _skill().facts(home)
    assert (facts.fresh, facts.why_stale) == (False, NOTHING)
    ask_tool(home, "Below the high", NOW)
    assert _skill().facts(home).fresh is True


def test_old_request_expires(tmp_path: Path) -> None:
    """UT-DSK-013.003.M40.T03: A new request made 25 hours ago is set expired, with no AI call."""
    home = _home(tmp_path)
    rid = ask_tool(home, "Below the high", NOW - timedelta(hours=25))
    ctx = _act(home, [bs.answer()])
    req = get_request(home, rid)
    assert req is not None and (req.state, req.reason) == ("expired", EXPIRED)
    assert ctx.asked == 0


# ── facts (SRD-DSK-013.004) ─────────────────────────────────────────────────


def test_facts_text(tmp_path: Path) -> None:
    """UT-DSK-013.004.M40.T01: The facts hold the request, its stocks, the read functions, the
    rules, the built tools and the taken format names."""
    home = _home(tmp_path)
    bs.version(home)
    rid = add_request(home, "chat", None, bs.ASKER, "Gap of each stock", ["ZZA"], NOW)
    req = get_request(home, rid)
    assert req is not None
    text = facts_text(home, req)
    assert f"Tool request #{rid} from Quill: Gap of each stock" in text
    assert "Sample stocks: ZZA" in text
    for name in ("daily_bars(symbol", "intraday_bars(symbol", "desk_rows(source"):
        assert name in text
    assert "- Use only these names:" in text and "- No import" in text
    assert f"- {bs.NAME} v1 (review): Below the 52-week high: below_high" in text
    assert "Taken format names:" in text and "setup_table" in text


def test_no_code_or_paths_in_facts(tmp_path: Path) -> None:
    """UT-DSK-013.004.M40.T02: The facts name a built tool, its title and columns, but hold none
    of its code and no file path."""
    home = _home(tmp_path)
    tool = bs.version(home)
    rid = add_request(home, "tools", None, "master", "Another tool", [], NOW)
    req = get_request(home, rid)
    assert req is not None
    text = facts_text(home, req)
    assert tool.name in text and "high_of(bars)" not in text
    assert tool.file not in text and "v1.py" not in text and str(home) not in text


def test_first_tool_facts(tmp_path: Path) -> None:
    """UT-DSK-013.004.M40.T03: With no built tool and no stocks: "Built tools: none" and no
    sample line."""
    home = _home(tmp_path)
    rid = add_request(home, "tools", None, "master", "First tool", [], NOW)
    req = get_request(home, rid)
    assert req is not None
    text = facts_text(home, req)
    assert "Built tools: none" in text and "Sample stocks" not in text
    assert "from the Master user" in text


# ── answer, refusal, fix round (SRD-DSK-013.005, .008) ──────────────────────


def test_refusal(tmp_path: Path) -> None:
    """UT-DSK-013.005.M40.T01: An answer with only a refusal refuses the request; no version and
    one AI call."""
    home = _home(tmp_path)
    rid = ask_tool(home, "Count today's headlines", NOW)
    ctx = _act(home, [ToolAnswer(refuse="needs news")])
    req = get_request(home, rid)
    assert req is not None and (req.state, req.reason) == ("refused", "needs news")
    assert built_tool_rows(home) == [] and ctx.asked == 1


def test_fix_round(tmp_path: Path) -> None:
    """UT-DSK-013.008.M40.T01: Code that imports gets one more call with the problem; v1 is
    failed with the rules note and v2 waits in review."""
    home = _home(tmp_path)
    rid = ask_tool(home, "Below the high", NOW)
    ctx = _act(home, [bs.answer(code=BAD), bs.answer()])
    v2, v1 = built_tool_rows(home)
    assert (v1.state, v1.checks[0].note) == (FAILED, "line 1: import is not allowed")
    assert v2.state == REVIEW and ctx.asked == 2
    assert "Your last answer had these problems:" in ctx.texts[1]
    assert "import is not allowed" in ctx.texts[1]
    req = get_request(home, rid)
    assert req is not None and (req.state, req.tool) == ("done", v2.id)


def test_still_bad(tmp_path: Path) -> None:
    """UT-DSK-013.008.M40.T02: Two answers that break the rules: both versions failed, the
    request failed, exactly 2 AI calls and no sandbox run."""
    home = _home(tmp_path)
    rid = ask_tool(home, "Below the high", NOW)
    runs = bs.Runs()
    ctx = _act(home, [bs.answer(code=BAD), bs.answer(code=BAD), bs.answer()], runs=runs)
    assert [t.state for t in built_tool_rows(home)] == [FAILED, FAILED]
    req = get_request(home, rid)
    assert req is not None and req.state == "failed"
    assert req.reason == "the tool failed its checks: line 1: import is not allowed"
    assert ctx.asked == 2 and runs.calls == []


def test_fix_after_failed_checks(tmp_path: Path) -> None:
    """UT-DSK-013.008.M40.T03: A first version that crashes on the made-up stock is failed; the
    fixed second one waits in review."""
    home = _home(tmp_path)
    ask_tool(home, "Below the high", NOW)
    ctx = _act(home, [bs.answer(code=bs.GOOD_CODE + "# crash\n"), bs.answer()])
    v2, v1 = built_tool_rows(home)
    assert v1.state == FAILED and not v1.checks[4].ok
    assert v1.checks[4].note == "ZZZZZ: error: IndexError: list index out of range"
    assert v2.state == REVIEW and ctx.asked == 2


def test_model_messages_dropped(tmp_path: Path) -> None:
    """UT-DSK-013.008.M40.T04: A message the model adds is dropped; only the reply goes out."""
    home = _home(tmp_path)
    mid = bs.ask(home, {"request": "Below the high"})
    extra = Draft(type="ask", to=bs.ASKER, subject="Hello", text="Hello")
    ctx = _act(home, [bs.answer()], (mid,), extra=(extra,))
    assert [d.type for d in ctx.drafts] == ["reply"]


# ── checks and states (SRD-DSK-013.014, .015) ───────────────────────────────


def test_all_checks_pass(tmp_path: Path) -> None:
    """UT-DSK-013.014.M40.T01: A good tool on 2 stocks with daily files passes all 5 checks in a
    real sandbox; the made-up stock shows its reason."""
    home = _home(tmp_path)
    for symbol in ("ZZA", "ZZB"):
        bs.daily_file(tmp_path / "bt", symbol, 60)
    tool = bs.version(home)
    checks, sample = run_checks(home, tool, ["ZZA", "ZZB"], run_code, tmp_path / "bt")
    assert [c.ok for c in checks] == [True] * 5
    assert sample == ["ZZA: below_high 0.31", "ZZB: below_high 0.31",
                      "ZZZZZ: fewer than 20 daily bars"]


@pytest.mark.parametrize(("marker", "failed", "note"), [
    ("# wrong", {"Full row", "Value types"}, "ZZA below_high: wrong value"),
    ("# crash", {"No data"}, "ZZZZZ: error: IndexError: list index out of range"),
    ("# hang", {"Time and memory", "Full row", "Value types", "No data"},
     "took longer than 60 s"),
])
def test_checks_fail(tmp_path: Path, marker: str, failed: set[str], note: str) -> None:
    """UT-DSK-013.014.M40.T02: A wrong value, no full row, a crash on the made-up stock and a
    run past its limit each fail their checks with notes."""
    home = _home(tmp_path)
    tool = bs.version(home, code=bs.GOOD_CODE + marker + "\n")
    checks, _sample = run_checks(home, tool, ["ZZA"], bs.Runs())
    assert {c.check for c in checks if not c.ok} == failed
    assert note in [c.note for c in checks]


def test_review_state(tmp_path: Path) -> None:
    """UT-DSK-013.015.M40.T01: All checks pass: the version waits in review and nothing is
    written to the registry, the formats or the plans."""
    home = _home(tmp_path)
    ask_tool(home, "Below the high", NOW)
    _act(home, [bs.answer()])
    (tool,) = built_tool_rows(home)
    assert tool.state == REVIEW and tool.passed == len(CHECKS)
    assert [t for t in list_tools(home) if t.name.startswith("built.")] == []
    assert [f for f in list_formats(home) if f.name == bs.NAME] == []
    assert [p for p in plan_rows(home) if p.format.startswith(bs.NAME)] == []


def test_failed_state(tmp_path: Path) -> None:
    """UT-DSK-013.015.M40.T02: One failed check makes the version failed."""
    home = _home(tmp_path)
    ask_tool(home, "Below the high", NOW)
    _act(home, [bs.answer(code=bs.GOOD_CODE + "# crash\n"),
                bs.answer(code=bs.GOOD_CODE + "# crash\n")])
    assert [t.state for t in built_tool_rows(home)] == [FAILED, FAILED]


# ── reply (SRD-DSK-013.016) ─────────────────────────────────────────────────


def test_done_reply(tmp_path: Path) -> None:
    """UT-DSK-013.016.M40.T01: A built chat request gets one done reply naming the tool and its
    checks."""
    home = _home(tmp_path)
    mid = bs.ask(home, {"request": "Below the high"})
    ctx = _act(home, [bs.answer()], (mid,))
    (reply,) = _replies(ctx)
    assert reply.parent == mid and reply.verdict is not None and reply.verdict.result == "done"
    assert reply.text is not None and f"({bs.NAME} v1)" in reply.text
    assert "5 of 5 checks passed" in reply.text
    (req,) = tool_requests(home)
    assert req.state == "done"


def test_failed_and_refused_replies(tmp_path: Path) -> None:
    """UT-DSK-013.016.M40.T02: A refusal, two bad answers and no answer each give one reply:
    refused with the reason, failed, and failed with "the model gave no answer"."""
    home = _home(tmp_path)
    asks = [bs.ask(home, {"request": f"Tool {n}"}) for n in range(3)]
    ctx = _act(home, [ToolAnswer(refuse="needs news"), bs.answer(code=BAD),
                      bs.answer(code=BAD), None], tuple(asks))
    got = {d.parent: (d.verdict.result if d.verdict else "", d.verdict.reason if d.verdict
                      else "") for d in _replies(ctx)}
    assert got == {asks[0]: ("refused", "needs news"),
                   asks[1]: ("failed", "the tool failed its checks: line 1: import is not "
                                       "allowed"),
                   asks[2]: ("failed", NO_ANSWER)}


# ── logs (SRD-DSK-013.024) ──────────────────────────────────────────────────


def test_log_lines(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-013.024.M40.T01: A build, an Enable, a Disable and a stopped run log
    "[Tool builder]" lines with no code and no file path."""
    home = _home(tmp_path)
    caplog.set_level(logging.INFO)
    ask_tool(home, "Below the high", NOW)
    _act(home, [bs.answer()])
    (tool,) = built_tool_rows(home)
    assert enable_tool(home, tool.id, NOW) == "" and disable_tool(home, tool.id, NOW) == ""
    run_code(home, "def tool(symbol):\n    while True:\n        pass\n", bs.COLUMNS, ["ZZA"],
             secs=2)
    lines = [r.getMessage() for r in caplog.records if "[Tool builder]" in r.getMessage()]
    for part in ("Request #1 saved", f"Tool {bs.NAME} v1 waits for review: 5 of 5 checks passed",
                 f"Tool {bs.NAME} v1 enabled", f"Tool {bs.NAME} v1 disabled",
                 "A tool run was stopped: took longer than 2 s"):
        assert any(part in line for line in lines), part
    assert not any("def tool" in line or "tools/" in line or "v1.py" in line for line in lines)



# ── code review fixes (2026-11-16) ──────────────────────────────────────────


def test_stale_requests_end(tmp_path: Path) -> None:
    """UT-DSK-013.003.M40.T04: A request left new for over a day wakes the builder and expires;
    one left building by a stopped desk fails with the reason."""
    home = _home(tmp_path)
    old = ask_tool(home, "Below the high", NOW - timedelta(hours=25))
    stuck = ask_tool(home, "Gap today", NOW - timedelta(hours=26))
    set_request(home, stuck, "building", "", NOW - timedelta(hours=26))
    assert _skill().facts(home).fresh is True
    ctx = _act(home, [])
    states = {r.id: (r.state, r.reason) for r in tool_requests(home)}
    assert states == {old: ("expired", EXPIRED), stuck: ("failed", STOPPED)}
    assert ctx.asked == 0 and _skill().facts(home).fresh is False


def test_cut_stocks_fail_the_time_check(tmp_path: Path) -> None:
    """UT-DSK-013.014.M40.T03: Stocks cut at the time limit fail "Time and memory" with how many
    were not run."""
    home = _home(tmp_path)
    tool = bs.version(home, code=bs.GOOD_CODE + "# slow\n")
    checks, sample = run_checks(home, tool, ["ZZA", "ZZB"], bs.Runs())
    time_check = checks[1]
    assert (time_check.ok, time_check.note) == (
        False, "2 stock(s) not run: the time limit was reached")
    assert sample[1] == "ZZB: not run: the time limit was reached"
