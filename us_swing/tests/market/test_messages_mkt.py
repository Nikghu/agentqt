"""Tests for AI Desk v3 M1 in market: asks, send-backs, fix checks, fixed levels, news replies."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any

import pytest

from tests.market.p5b_support import Env, FakeCtx, Idea, listed, query, set_ideas, set_regime
from us_swing.core.desk_agents import Facts, talker
from us_swing.core.desk_messages import Person, accept
from us_swing.core.desk_msg import Data, Draft, InboxReply, Verdict, with_messages
from us_swing.core.desk_registry import fill_registry
from us_swing.market.news_review import NewsReview, NewsReviewSkill
from us_swing.market.risk_check import RiskCheckSkill, RiskVetoes
from us_swing.market.setup_review import (
    SetupReview,
    SetupReviewSkill,
    listed_frame,
)
from us_swing.market.store import IdeaFixRow, MarketStore, NewsTagRow
from us_swing.market.watch import plan_ideas
from us_swing.market.watch_flag import _plan_text

NOW = datetime(2026, 11, 13, 15, 0, tzinfo=UTC)
ROSTER = [Person("emp-a", "Ann", "risk_check"), Person("emp-b", "Bob", "setup_review")]


@dataclass
class TalkCtx(FakeCtx):
    """A fake context that talks: like the gateway it keeps the answer's messages as drafts."""

    talk: bool = True
    drafts: list[Draft] = field(default_factory=list)

    def send(self, draft: Draft) -> None:
        self.drafts.append(draft)

    def ask(self, facts: str, schema: type[Any]) -> Any:
        self.asked.append(facts)
        self.drafts.extend(getattr(self.answer, "messages", None) or [])
        return self.answer


def _grade(symbol: str, grade: str = "A") -> dict[str, str]:
    return {"side": "long", "symbol": symbol, "grade": grade, "note": "Clean setup near trigger"}


def _review(grades: list[dict[str, str]], messages: list[Draft]) -> Any:
    return with_messages(SetupReview).model_validate(
        {"grades": grades, "messages": [m.model_dump(by_alias=True) for m in messages]})


def _ask(*about: str) -> Draft:
    return Draft(type="ask", to="skill:news_review", about=list(about), subject="Any news today",
                 text="Is there news that changes this idea?")


def _grades(env: Env) -> list[tuple[str, str]]:
    return query(env.home, "SELECT symbol, grade FROM setup_review ORDER BY symbol")


def test_held_idea_graded_after_reply(p5b: Env) -> None:
    """UT-MKT-005.019.M05.T01: An asked idea is graded on the inbox wake; the others stay."""
    set_ideas(p5b, listed("long", "LNG", 4))
    skill = SetupReviewSkill(p5b.candles)
    facts = skill.facts(p5b.home)
    ctx = TalkCtx(p5b.home, _review([_grade("LNG01"), _grade("LNG02", "B"), _grade("LNG03", "C")],
                                    [_ask("LNG04")]))
    skill.act(ctx, facts)
    assert [s for s, _ in _grades(p5b)] == ["LNG01", "LNG02", "LNG03"]
    assert [d.type for d in ctx.drafts] == ["ask"]
    inbox_ctx = TalkCtx(p5b.home, SetupReview.model_validate({"grades": [_grade("LNG04", "B")]}))
    assert skill.act(inbox_ctx, replace(facts, inbox=(7,))) == []
    assert _grades(p5b) == [("LNG01", "A"), ("LNG02", "B"), ("LNG03", "C"), ("LNG04", "B")]


def test_more_than_three_asked(p5b: Env, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-005.019.M05.T02: Asks naming 5 ideas keep the first 3; the rest are dropped."""
    set_ideas(p5b, listed("long", "LNG", 6))
    skill = SetupReviewSkill(p5b.candles)
    asks = [_ask("LNG01"), _ask("LNG02", "LNG03"), _ask("LNG04", "LNG05")]
    ctx = TalkCtx(p5b.home, _review([_grade("LNG06")], asks))
    with caplog.at_level(logging.INFO):
        skill.act(ctx, skill.facts(p5b.home))
    assert [d.about for d in ctx.drafts] == [["LNG01"], ["LNG02", "LNG03"]]
    assert any("asked about more than 3 ideas" in r.getMessage() for r in caplog.records)


def test_messages_off_stores_grades(p5b: Env) -> None:
    """UT-MKT-005.019.M05.T03: Without a talking context grades are stored and nothing is sent."""
    set_ideas(p5b, listed("long", "LNG", 3))
    skill = SetupReviewSkill(p5b.candles)
    ctx = FakeCtx(p5b.home, SetupReview.model_validate(
        {"grades": [_grade("LNG01"), _grade("LNG02", "B")]}))
    items = skill.act(ctx, skill.facts(p5b.home))
    assert talker(ctx) is None and not hasattr(ctx, "drafts")
    assert _grades(p5b) == [("LNG01", "A"), ("LNG02", "B")] and len(items) == 1


def _stop_idea(symbol: str = "AMD", stop: float = 88.6) -> Idea:
    return ("long", symbol, "list", 1, "Tech", 100.0, stop)


def _stage_risk(env: Env, ideas: list[Idea]) -> RiskCheckSkill:
    set_regime(env, "Choppy")
    set_ideas(env, ideas)
    return RiskCheckSkill(env.candles)


def test_stop_sent_back(p5b: Env) -> None:
    """UT-MKT-005.020.M07.T01: A stop-only veto is sent back to the setup review, stays vetoed."""
    skill = _stage_risk(p5b, [_stop_idea(), ("long", "OKAY", "list", 2, "Energy", 50.0, 47.0)])
    ctx = TalkCtx(p5b.home, RiskVetoes())
    skill.act(ctx, skill.facts(p5b.home))
    (draft,) = ctx.drafts
    assert draft.type == "send_back" and draft.to == "skill:setup_review"
    assert draft.verdict is not None and draft.verdict.result == "fix"
    assert draft.verdict.reason is not None and draft.verdict.reason.startswith("Stop is ")
    assert (draft.text or "").startswith("long AMD:")
    assert query(p5b.home, "SELECT verdict, by FROM risk_check WHERE symbol = 'AMD'") == [
        ("veto", "code")]


def test_other_vetoes_final(p5b: Env) -> None:
    """UT-MKT-005.020.M07.T02: Downtrend, low trigger and a fourth in a sector are not sent back."""
    ideas: list[Idea] = [
        ("long", "CHEAP", "list", 1, "Energy", 3.0, 2.8),
        ("long", "TEC1", "list", 2, "Tech", 50.0, 47.0),
        ("long", "TEC2", "list", 3, "Tech", 50.0, 47.0),
        ("long", "TEC3", "list", 4, "Tech", 50.0, 47.0),
        ("long", "TEC4", "list", 5, "Tech", 50.0, 47.0),
    ]
    skill = _stage_risk(p5b, ideas)
    ctx = TalkCtx(p5b.home, RiskVetoes())
    skill.act(ctx, skill.facts(p5b.home))
    assert ctx.drafts == []
    assert {r[0] for r in query(p5b.home, "SELECT symbol FROM risk_check WHERE verdict = 'veto'")
            } == {"CHEAP", "TEC4"}
    set_regime(p5b, "Downtrend")
    ctx = TalkCtx(p5b.home, RiskVetoes())
    skill.act(ctx, skill.facts(p5b.home))
    assert ctx.drafts == []
    assert query(p5b.home, "SELECT COUNT(*) FROM risk_check WHERE verdict = 'veto'") == [(5,)]


def _id(line: str) -> int:
    assert line.startswith("stored #"), line
    return int(line.split("#")[1])


def _sent_back(env: Env, draft: Draft) -> int:
    return _id(accept(env.home, [draft], "emp-a", ROSTER, NOW, env.day)[0])


def _fix_reply(env: Env, parent: int, symbol: str, trigger: float, stop: float) -> int:
    data = Data.model_validate({"schema": "idea_fix.v1",
                                "rows": [["long", symbol, trigger, stop]]})
    draft = Draft(type="reply", parent=parent, verdict=Verdict(result="done"), data=data,
                  text="New levels")
    return _id(accept(env.home, [draft], "emp-b", ROSTER, NOW, env.day)[0])


def _first_round(env: Env) -> tuple[RiskCheckSkill, int]:
    """AMD vetoed on its stop, sent back and answered; returns skill and send-back id."""
    skill = _stage_risk(env, [_stop_idea(), ("long", "OKAY", "list", 2, "Energy", 50.0, 47.0)])
    fill_registry(env.home, NOW)
    ctx = TalkCtx(env.home, RiskVetoes())
    skill.act(ctx, skill.facts(env.home))
    sb = _sent_back(env, ctx.drafts[0])
    return skill, sb


def _inbox_wake(env: Env, skill: RiskCheckSkill, reply: int) -> TalkCtx:
    ctx = TalkCtx(env.home, None)
    skill.act(ctx, replace(skill.facts(env.home), inbox=(reply,)))
    assert ctx.asked == []
    return ctx


def _risk_row(env: Env, symbol: str = "AMD") -> tuple[str, str, str]:
    return query(env.home, "SELECT verdict, by, reason FROM risk_check WHERE symbol = ?",
                 (symbol,))[0]


def test_fix_passes(p5b: Env) -> None:
    """UT-MKT-005.022.M07.T01: A fix inside the limits passes AMD by code with no AI call."""
    skill, sb = _first_round(p5b)
    reply = _fix_reply(p5b, sb, "AMD", 100.0, 92.3)
    ctx = _inbox_wake(p5b, skill, reply)
    assert _risk_row(p5b) == ("pass", "code", "Fixed in round 1")
    assert query(p5b.home, "SELECT status, round FROM idea_fixes") == [("pass", 1)]
    assert ctx.drafts == []


def test_fix_still_over_round_one(p5b: Env) -> None:
    """UT-MKT-005.022.M07.T02: A fix still over the limit fails and a round-2 send-back follows."""
    skill, sb = _first_round(p5b)
    reply = _fix_reply(p5b, sb, "AMD", 100.0, 89.5)
    ctx = _inbox_wake(p5b, skill, reply)
    assert query(p5b.home, "SELECT status, round FROM idea_fixes") == [("fail", 1)]
    (draft,) = ctx.drafts
    assert draft.type == "send_back" and draft.parent == reply
    assert _risk_row(p5b)[:2] == ("veto", "code")


def test_fix_still_over_round_two(p5b: Env) -> None:
    """UT-MKT-005.022.M07.T03: A round-2 fix still over stays vetoed and sends nothing more."""
    skill, sb = _first_round(p5b)
    reply = _fix_reply(p5b, sb, "AMD", 100.0, 89.5)
    ctx = _inbox_wake(p5b, skill, reply)
    sb2 = _sent_back(p5b, ctx.drafts[0])
    reply2 = _fix_reply(p5b, sb2, "AMD", 100.0, 89.9)
    ctx2 = _inbox_wake(p5b, skill, reply2)
    verdict, by, why = _risk_row(p5b)
    assert (verdict, by) == ("veto", "code") and why.startswith("Still over after 2 rounds")
    assert ctx2.drafts == []
    assert query(p5b.home, "SELECT status, round FROM idea_fixes ORDER BY round") == [
        ("fail", 1), ("fail", 2)]


def test_fix_for_another_idea(p5b: Env, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-005.022.M07.T04: A fix row for MSFT on AMD's send-back is ignored and logged."""
    skill, sb = _first_round(p5b)
    reply = _fix_reply(p5b, sb, "MSFT", 100.0, 92.3)
    with caplog.at_level(logging.INFO):
        ctx = _inbox_wake(p5b, skill, reply)
    assert any("named another idea" in r.getMessage() for r in caplog.records)
    assert query(p5b.home, "SELECT COUNT(*) FROM idea_fixes") == [(0,)]
    assert _risk_row(p5b)[:2] == ("veto", "code") and ctx.drafts == []


def _fix(env: Env, status: str) -> None:
    store = MarketStore(env.home)
    try:
        store.add_fix(IdeaFixRow(env.day, "long", "AMD", 1, 105.0, 98.0, status, env.day))
    finally:
        store.close()


def _levels(env: Env) -> tuple[tuple[float, float], tuple[float, float], str]:
    store = MarketStore(env.home)
    try:
        row = listed_frame(store, env.day).iloc[0]
    finally:
        store.close()
    ideas, _ = plan_ideas(env.home, env.day)
    amd = next(i for i in ideas if i.symbol == "AMD")
    return (float(row["trigger"]), float(row["stop"])), (amd.trigger, amd.stop), _plan_text(
        env.home, "AMD", env.day)


def test_fixed_levels_used(p5b: Env) -> None:
    """UT-MKT-005.023.M04.T01: A passing fix shows in listed_frame, watcher ideas and plan text."""
    set_ideas(p5b, [_stop_idea()])
    _fix(p5b, "pass")
    frame_levels, watch_levels, text = _levels(p5b)
    assert frame_levels == (105.0, 98.0) and watch_levels == (105.0, 98.0)
    assert "trigger 105.0, stop 98.0" in text


@pytest.mark.parametrize("status", ["fail", "pending"])
def test_fix_not_pass_not_used(p5b: Env, status: str) -> None:
    """UT-MKT-005.023.M04.T02: A failed or pending fix leaves the old levels everywhere."""
    set_ideas(p5b, [_stop_idea()])
    _fix(p5b, status)
    frame_levels, watch_levels, text = _levels(p5b)
    assert frame_levels == (100.0, 88.6) and watch_levels == (100.0, 88.6)
    assert "trigger 100.0, stop 88.6" in text


def _news_stage(env: Env) -> NewsReviewSkill:
    set_ideas(env, listed("long", "LNG", 2))
    return NewsReviewSkill(env.candles)


def _tags(env: Env) -> list[Any]:
    return query(env.home, "SELECT * FROM news_tags ORDER BY symbol")


def test_news_reply_only(p5b: Env) -> None:
    """UT-MKT-006.013.M04.T01: An inbox wake only asks for a reply; tags and feed stay as they are."""
    skill = _news_stage(p5b)
    store = MarketStore(p5b.home)
    store.replace_day("news_tags", p5b.day, [NewsTagRow(
        p5b.day, "long", "LNG01", "positive", "Good news", 2.0, 80.0)])
    store.close()
    before = _tags(p5b)
    reply = InboxReply(messages=[Draft(type="reply", parent=1, verdict=Verdict(result="done"),
                                       text="No news that changes the idea")])
    ctx = TalkCtx(p5b.home, reply)
    facts = Facts("Inbox text", p5b.day, True, inbox=(1,))
    assert skill.act(ctx, facts) == []
    assert ctx.asked == ["Inbox text"] and [d.type for d in ctx.drafts] == ["reply"]
    assert _tags(p5b) == before


def test_news_normal_wake(p5b: Env) -> None:
    """UT-MKT-006.013.M04.T02: A wake without an inbox stores tags and posts the note as before."""
    skill = _news_stage(p5b)
    answer = NewsReview.model_validate({
        "tags": [{"side": "long", "symbol": "LNG01", "tone": "positive",
                  "reason": "Plain reason here"}],
        "market": "CPI is due next week; headlines are mostly calm and about earnings."})
    ctx = TalkCtx(p5b.home, answer)
    items = skill.act(ctx, Facts("Facts text", p5b.day, True))
    assert query(p5b.home, "SELECT tone FROM news_tags WHERE symbol = 'LNG01'") == [("positive",)]
    assert items and ctx.asked == ["Facts text"]


def _fix_draft(parent: int, verdict: Verdict, data: Data | None = None) -> Draft:
    return Draft(type="reply", parent=parent, verdict=verdict, data=data,
                 text="Here is my answer")


def test_fix_reply(p5b: Env) -> None:
    """UT-MKT-005.021.M05.T01: A send-back about AMD is answered with an idea_fix.v1 row."""
    set_ideas(p5b, [_stop_idea(), ("long", "OKAY", "list", 2, "Energy", 50.0, 47.0)])
    skill = SetupReviewSkill(p5b.candles)
    facts = skill.facts(p5b.home)
    skill.act(TalkCtx(p5b.home, SetupReview.model_validate({"grades": [_grade("OKAY", "B")]})),
              facts)
    data = Data.model_validate({"schema": "idea_fix.v1", "rows": [["long", "AMD", 100.0, 92.3]]})
    answer = _review([_grade("AMD", "C")], [_fix_draft(5, Verdict(result="done"), data)])
    ctx = TalkCtx(p5b.home, answer)
    assert skill.act(ctx, replace(facts, inbox=(5,))) == []
    (reply,) = ctx.drafts
    assert reply.type == "reply" and reply.parent == 5
    assert reply.data is not None and reply.data.rows == [["long", "AMD", 100.0, 92.3]]
    assert _grades(p5b) == [("AMD", "C"), ("OKAY", "B")]


def test_fix_dropped(p5b: Env) -> None:
    """UT-MKT-005.021.M05.T02: A model that drops the idea replies with verdict dropped."""
    set_ideas(p5b, [_stop_idea(), ("long", "OKAY", "list", 2, "Energy", 50.0, 47.0)])
    skill = SetupReviewSkill(p5b.candles)
    facts = skill.facts(p5b.home)
    answer = _review([_grade("OKAY")], [_fix_draft(
        5, Verdict(result="dropped", reason="No clean stop can be found"))])
    ctx = TalkCtx(p5b.home, answer)
    skill.act(ctx, replace(facts, inbox=(5,)))
    (reply,) = ctx.drafts
    assert reply.verdict is not None and reply.verdict.result == "dropped"
    assert reply.data is None
