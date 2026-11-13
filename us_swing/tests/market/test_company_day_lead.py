"""Tests for AI Desk v3 M5 in the lead brief and views: MD-MKT-020.001.M02, .004.M03, .009.M05."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from tests.market.p5b_support import (
    Env,
    FakeCtx,
    execute,
    listed,
    query,
    set_ideas,
    set_regime,
)
from us_swing.core.desk_ai_settings import DeskAiSettings, load_settings, save_settings
from us_swing.core.desk_day import mark_huddle
from us_swing.core.desk_memory import add_trading_days
from us_swing.core.desk_messages import Person, accept, expire_due
from us_swing.core.desk_msg import Draft, InboxReply, Verdict
from us_swing.market.lead_brief import LeadBrief, LeadBriefSkill, LeadBriefWithCall
from us_swing.market.regime_view import RegimeView, RegimeViewSkill
from us_swing.market.sector_view import SectorViewSkill
from us_swing.market.store import MarketStore, RegimeViewRow, SectorViewRow

NY = ZoneInfo("America/New_York")
MORNING = "The market is choppy; favour Tech longs near their triggers and wait for a breakout."
ROSTER = [Person("emp-l", "Lee", "lead_brief"), Person("emp-r", "Ray", "regime_view"),
          Person("emp-s", "Sam", "sector_flow_view")]


@dataclass
class TalkCtx(FakeCtx):
    """A talking fake context that keeps drafts and the schemas it was asked with."""

    talk: bool = True
    drafts: list[Draft] = field(default_factory=list)
    schemas: list[type[Any]] = field(default_factory=list)

    def send(self, draft: Draft) -> None:
        self.drafts.append(draft)

    def ask(self, facts: str, schema: type[Any]) -> Any:
        self.schemas.append(schema)
        return super().ask(facts, schema)


def _on(env: Env, on: bool = True) -> None:
    save_settings(DeskAiSettings(company_day_on=on), env.home)


def _sectors(env: Env) -> list[str]:
    return [str(r[0]) for r in query(env.home, "SELECT sector FROM sector_daily WHERE date = "
                                     "? ORDER BY rank", (env.day,))]


def _stage(env: Env, regime: str = "Choppy", favour: list[str] | None = None) -> LeadBriefSkill:
    set_regime(env, "Choppy")
    set_ideas(env, listed("long", "LNG", 3))
    store = MarketStore(env.home)
    store.write_regime_view(RegimeViewRow(env.day, regime, 0.6, '["Flat tape"]', "brief",
                                          "Choppy", regime == "Choppy"))
    store.replace_day("sector_view", env.day, [SectorViewRow(
        env.day, json.dumps(favour or [_sectors(env)[0]]), "[]", "rotation", "brief")])
    store.close()
    return LeadBriefSkill(env.candles, clock=lambda: datetime(2026, 11, 13, 8, tzinfo=NY))


def _roster(env: Env) -> None:
    execute(env.home, "CREATE TABLE IF NOT EXISTS roster (id TEXT PRIMARY KEY, name TEXT, "
            "title TEXT, level TEXT, reports_to TEXT, skill TEXT, version INTEGER, hash TEXT, "
            "loaded_at TEXT)")
    for person in ROSTER:
        execute(env.home, "INSERT OR REPLACE INTO roster (id, name, skill) VALUES (?, ?, ?)",
                (person.id, person.name, person.skill))


def _clash(env: Env, roster: bool = True) -> LeadBriefSkill:
    if roster:
        _roster(env)
    growth = [s for s in _sectors(env) if s not in ("Utilities", "Consumer Staples",
                                                     "Health Care", "Real Estate")][:1]
    return _stage(env, "Downtrend", growth)


def _answer(market: str = "Uptrend", favour: list[str] | None = None) -> LeadBriefWithCall:
    return LeadBriefWithCall.model_validate({
        "picks": [], "morning": MORNING,
        "call": {"market": market, "favour": favour or ["Energy"], "note": "Lean long"}})


def test_setting_default_and_save(tmp_path: Path) -> None:
    """UT-MKT-020.001.M02.T01: Off by default; saved on is read back on."""
    assert load_settings(tmp_path).company_day_on is False
    save_settings(DeskAiSettings(company_day_on=True), tmp_path)
    assert load_settings(tmp_path).company_day_on is True


def test_standup_in_facts(p5b: Env) -> None:
    """UT-MKT-020.004.M03.T01: With the day on, facts start with the stand-up; act saves it."""
    _on(p5b)
    skill = _stage(p5b)
    facts = skill.facts(p5b.home)
    assert facts.text.startswith(f"Stand-up for {p5b.day}")
    assert "Day call: also give the market" in facts.text
    skill.act(FakeCtx(p5b.home, _answer(favour=[_sectors(p5b)[0]])), facts)
    assert query(p5b.home, "SELECT standup != '' FROM day_brief WHERE day = ?",
                 (p5b.day,)) == [(1,)]


def test_no_standup_when_off(p5b: Env) -> None:
    """UT-MKT-020.004.M03.T02: With the day off, no stand-up and no day row."""
    skill = _stage(p5b)
    assert not skill.facts(p5b.home).text.startswith("Stand-up")
    assert query(p5b.home, "SELECT name FROM sqlite_master WHERE name = 'day_brief'") == []


def test_switch_off(p5b: Env) -> None:
    """UT-MKT-020.001.M03.T01: Off: plain schema, no draft and no day rows even on a clash."""
    skill = _clash(p5b)
    ctx = TalkCtx(p5b.home, LeadBrief.model_validate({"picks": [], "morning": MORNING}))
    skill.act(ctx, skill.facts(p5b.home))
    assert ctx.schemas == [LeadBrief] and ctx.drafts == []
    assert query(p5b.home, "SELECT name FROM sqlite_master WHERE name = 'decisions'") == []


def test_huddle_called(p5b: Env) -> None:
    """UT-MKT-020.006.M03.T01: A clash sends one meeting to both views and asks nothing."""
    _on(p5b)
    skill = _clash(p5b)
    ctx = TalkCtx(p5b.home, _answer())
    assert skill.act(ctx, skill.facts(p5b.home)) == []
    assert ctx.asked == []
    assert [(d.type, d.to) for d in ctx.drafts] == [
        ("meeting", "skill:regime_view,skill:sector_flow_view")]
    assert query(p5b.home, "SELECT huddle FROM day_brief WHERE day = ?", (p5b.day,)) == [(1,)]


def test_one_huddle_a_day(p5b: Env) -> None:
    """UT-MKT-020.006.M03.T02: With a huddle already called, the brief is asked."""
    _on(p5b)
    skill = _clash(p5b)
    mark_huddle(p5b.home, p5b.day, "earlier clash", datetime(2026, 11, 13, 7, tzinfo=NY))
    ctx = TalkCtx(p5b.home, _answer(favour=[_sectors(p5b)[0]]))
    skill.act(ctx, skill.facts(p5b.home))
    assert ctx.drafts == [] and ctx.schemas == [LeadBriefWithCall]


def test_no_huddle_without_holders(p5b: Env) -> None:
    """UT-MKT-020.006.M03.T04: With no employee holding a view skill, no huddle is tried."""
    _on(p5b)
    skill = _clash(p5b, roster=False)
    ctx = TalkCtx(p5b.home, _answer(favour=[_sectors(p5b)[0]]))
    skill.act(ctx, skill.facts(p5b.home))
    assert ctx.drafts == [] and ctx.schemas == [LeadBriefWithCall]


def test_no_huddle_for_fakes(p5b: Env) -> None:
    """UT-MKT-020.006.M03.T03: A plain fake context never huddles."""
    _on(p5b)
    skill = _clash(p5b)
    ctx = FakeCtx(p5b.home, _answer(favour=[_sectors(p5b)[0]]))
    skill.act(ctx, skill.facts(p5b.home))
    assert len(ctx.asked) == 1


def _huddle_rows(env: Env) -> list[int]:
    now = datetime(2026, 11, 13, 8, tzinfo=NY)
    mark_huddle(env.home, env.day, "Regime view says Downtrend", now)
    draft = Draft(type="meeting", to="skill:regime_view,skill:sector_flow_view",
                  subject="Huddle", text="Clash")
    accept(env.home, [draft], "emp-l", ROSTER, now, env.day, meetings=True)
    return [int(r[0]) for r in query(env.home, "SELECT id FROM messages WHERE type = "
                                     "'meeting' ORDER BY id")]


def test_wait_while_open(p5b: Env) -> None:
    """UT-MKT-020.010.M03.T01: An inbox wake with a meeting open asks nothing."""
    _on(p5b)
    skill = _clash(p5b)
    first, _second = _huddle_rows(p5b)
    accept(p5b.home, [Draft(type="reply", parent=first, verdict=Verdict(result="done"),
                            text="Breadth fell")], "emp-r", ROSTER,
           datetime(2026, 11, 13, 8, 2, tzinfo=NY), p5b.day, meetings=True)
    ctx = TalkCtx(p5b.home, _answer())
    assert skill.act(ctx, replace(skill.facts(p5b.home), inbox=(9,))) == []
    assert ctx.asked == []


def test_huddle_block(p5b: Env) -> None:
    """UT-MKT-020.010.M03.T02: After the replies the facts hold the huddle; the brief is asked."""
    _on(p5b)
    skill = _clash(p5b)
    first, _second = _huddle_rows(p5b)
    accept(p5b.home, [Draft(type="reply", parent=first, verdict=Verdict(result="done"),
                            text="Breadth fell 4 days")], "emp-r", ROSTER,
           datetime(2026, 11, 13, 8, 2, tzinfo=NY), p5b.day, meetings=True)
    expire_due(p5b.home, datetime(2026, 11, 13, 8, 30, tzinfo=NY), ROSTER)
    facts = skill.facts(p5b.home)
    assert "Huddle (one round): Regime view says Downtrend" in facts.text
    assert "Ray: Breadth fell 4 days" in facts.text and "Sam: no answer" in facts.text
    ctx = TalkCtx(p5b.home, _answer(favour=[_sectors(p5b)[0]]))
    skill.act(ctx, replace(facts, inbox=(9,)))
    assert ctx.schemas == [LeadBriefWithCall]


def test_call_in_answer(p5b: Env) -> None:
    """UT-MKT-020.011.M03.T01: The day call is saved with its votes; picks as before."""
    _on(p5b)
    skill = _stage(p5b)
    first = _sectors(p5b)[0]
    ctx = FakeCtx(p5b.home, _answer("Uptrend", [first]))
    skill.act(ctx, skill.facts(p5b.home))
    row = query(p5b.home, "SELECT market, favour, due, status FROM decisions")
    assert row == [("Uptrend", json.dumps([first]), add_trading_days(p5b.day, 5), "open")]
    assert query(p5b.home, "SELECT skill, stance FROM decision_votes ORDER BY skill") == [
        ("regime_view", "disagreed"), ("sector_flow_view", "agreed")]


def test_unknown_sectors(p5b: Env, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-020.011.M03.T02: A call with only unknown sectors is not saved."""
    _on(p5b)
    skill = _stage(p5b)
    with caplog.at_level(logging.INFO):
        skill.act(FakeCtx(p5b.home, _answer("Uptrend", ["Crypto"])), skill.facts(p5b.home))
    assert query(p5b.home, "SELECT COUNT(*) FROM decisions") == [(0,)]
    assert any("not in the list" in r.getMessage() for r in caplog.records)


def test_regime_view_replies_only(p5b: Env) -> None:
    """UT-MKT-020.009.M05.T01: A meeting wake asks only for the reply; the view stays."""
    _stage(p5b, "Downtrend")
    skill = RegimeViewSkill(p5b.candles)
    reply = InboxReply.model_validate({"messages": [{"type": "reply", "parent": 1,
                                                     "text": "Breadth fell"}]})
    ctx = TalkCtx(p5b.home, reply)
    assert skill.act(ctx, replace(skill.facts(p5b.home), inbox=(1,))) == []
    assert ctx.schemas == [InboxReply]
    assert query(p5b.home, "SELECT regime FROM regime_view WHERE date = ?",
                 (p5b.day,)) == [("Downtrend",)]


def test_sector_view_replies_only(p5b: Env) -> None:
    """UT-MKT-020.009.M05.T02: The sector/flow view also replies only."""
    _stage(p5b, "Downtrend")
    before = query(p5b.home, "SELECT favour FROM sector_view")
    skill = SectorViewSkill(p5b.candles)
    reply = InboxReply.model_validate({"messages": [{"type": "reply", "parent": 2,
                                                     "text": "RS still rising"}]})
    ctx = TalkCtx(p5b.home, reply)
    assert skill.act(ctx, replace(skill.facts(p5b.home), inbox=(2,))) == []
    assert ctx.schemas == [InboxReply]
    assert query(p5b.home, "SELECT favour FROM sector_view") == before


def test_normal_wake(p5b: Env) -> None:
    """UT-MKT-020.009.M05.T03: Without a talking context the view is asked and saved."""
    _stage(p5b, "Downtrend")
    skill = RegimeViewSkill(p5b.candles)
    view = RegimeView.model_validate({"regime": "Uptrend", "confidence": 0.7,
                                      "reasons": ["Breadth improved"],
                                      "brief": "The tape is turning up with better breadth."})
    ctx = FakeCtx(p5b.home, view)
    assert skill.act(ctx, replace(skill.facts(p5b.home), inbox=(1,))) != []
    assert query(p5b.home, "SELECT regime FROM regime_view WHERE date = ?",
                 (p5b.day,)) == [("Uptrend",)]

