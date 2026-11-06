"""Tests for MD-MKT-005.012.M07 — market/risk_check.py (risk check skill)."""
from __future__ import annotations

import logging

import pytest

from tests.market.p5b_support import Env, FakeCtx, Idea, query, set_ideas, set_regime
from us_swing.market.risk_check import RiskCheckSkill, RiskVeto, RiskVetoes

# LNG03 has a stop 0.5% from the trigger and SHT02 has no stop: two code vetoes out of six.
IDEAS: list[Idea] = [
    ("long", "LNG01", "list", 1, "Tech", 50.0, 47.0),
    ("long", "LNG02", "list", 2, "Tech", 50.0, 47.0),
    ("long", "LNG03", "list", 3, "Tech", 100.0, 99.5),
    ("long", "LNG04", "list", 4, "Energy", 50.0, 47.0),
    ("short", "SHT01", "list", 1, "Energy", 50.0, 53.0),
    ("short", "SHT02", "list", 2, "Energy", 50.0, None),
]


def _answer(*vetoes: tuple[str, str]) -> RiskVetoes:
    return RiskVetoes(vetoes=[
        RiskVeto.model_validate({"side": s, "symbol": y, "reason": "Looks stretched today"})
        for s, y in vetoes])


def _staged(env: Env) -> RiskCheckSkill:
    set_regime(env, "Choppy")
    set_ideas(env, IDEAS)
    return RiskCheckSkill(env.candles)


def _rows(env: Env) -> dict[str, tuple[str, str, str]]:
    return {r[0]: (r[1], r[2], r[3]) for r in query(
        env.home, "SELECT symbol, verdict, by, reason FROM risk_check")}


def test_ai_adds_a_veto(p5b: Env) -> None:
    """UT-MKT-005.012.M07.T01: The AI vetoes one passed idea; that row is veto by ai."""
    skill = _staged(p5b)
    skill.act(FakeCtx(p5b.home, _answer(("long", "LNG01"))), skill.facts(p5b.home))
    assert _rows(p5b)["LNG01"] == ("veto", "ai", "Looks stretched today")
    assert _rows(p5b)["LNG02"] == ("pass", "code", "Within the hard limits")


def test_ai_cannot_undo_code_veto(p5b: Env) -> None:
    """UT-MKT-005.012.M07.T02: An AI answer naming a code-vetoed idea leaves it veto by code."""
    skill = _staged(p5b)
    facts = skill.facts(p5b.home)
    passed_part = facts.text.split("you may veto any of these")[1]
    assert "LNG03" not in passed_part and "SHT02" not in passed_part
    assert "Already vetoed by the hard limits: 2 idea(s)" in facts.text
    skill.act(FakeCtx(p5b.home, _answer(("long", "LNG03"))), facts)
    verdict, by, reason = _rows(p5b)["LNG03"]
    assert (verdict, by) == ("veto", "code") and "0.5%" in reason


def test_unknown_idea(p5b: Env, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-005.012.M07.T03: An AI veto for a stock not listed is dropped and logged."""
    skill = _staged(p5b)
    with caplog.at_level(logging.INFO):
        skill.act(FakeCtx(p5b.home, _answer(("long", "ZZZ"))), skill.facts(p5b.home))
    assert "ZZZ" not in _rows(p5b) and all(v[1] == "code" for v in _rows(p5b).values())
    assert any("not open to a veto" in r.getMessage() for r in caplog.records)


def test_missing_views(p5b: Env) -> None:
    """UT-MKT-005.012.M07.T04: Without a sector_view row the facts say it is not available."""
    facts = _staged(p5b).facts(p5b.home)
    assert "Sector view: not available today" in facts.text


def test_one_row_per_idea(p5b: Env) -> None:
    """UT-MKT-005.013.M07.T01: Six ideas give six rows; the feed item counts both kinds."""
    skill = _staged(p5b)
    items = skill.act(FakeCtx(p5b.home, _answer(("short", "SHT01"))), skill.facts(p5b.home))
    assert len(_rows(p5b)) == 6
    assert [(i.kind, i.text) for i in items] == [(
        "info", "Risk check: 3 of 6 idea(s) vetoed (2 by the hard limits, 1 by review)")]


def test_code_vetoes_without_ai(p5b: Env) -> None:
    """UT-MKT-005.013.M07.T02: With no AI answer the code vetoes are stored; the rest pass."""
    skill = _staged(p5b)
    assert skill.act(FakeCtx(p5b.home, None), skill.facts(p5b.home)) == []
    rows = _rows(p5b)
    assert {k for k, v in rows.items() if v[0] == "veto"} == {"LNG03", "SHT02"}
    assert all(v[1] == "code" for v in rows.values()) and len(rows) == 6

def test_second_wake_keeps_ai_vetoes(p5b: Env) -> None:
    """UT-MKT-005.013.M07.T03: A later wake with no valid answer keeps the earlier AI veto."""
    skill = _staged(p5b)
    skill.act(FakeCtx(p5b.home, _answer(("long", "LNG01"))), skill.facts(p5b.home))
    items = skill.act(FakeCtx(p5b.home, None), skill.facts(p5b.home))
    assert items == []
    assert _rows(p5b)["LNG01"] == ("veto", "ai", "Looks stretched today")
    assert _rows(p5b)["LNG03"][:2] == ("veto", "code")


def test_facts_show_news(p5b: Env) -> None:
    """UT-MKT-006.010.M07.T01: news_tags for the day show tone, points and final score in facts."""
    from us_swing.market.store import MarketStore, NewsTagRow

    skill = _staged(p5b)
    store = MarketStore(p5b.home)
    store.replace_day("news_tags", p5b.day, [
        NewsTagRow(p5b.day, "long", "LNG01", "positive", "Good news", 10.0, 82.5)])
    store.close()
    text = skill.facts(p5b.home).text
    assert "News review (points out of 10" in text
    assert "positive" in text and "82.5" in text and "LNG01" in text


def test_facts_news_missing(p5b: Env) -> None:
    """UT-MKT-006.010.M07.T02: without news_tags the facts say the news review is not available."""
    text = _staged(p5b).facts(p5b.home).text
    assert "News review: not available today" in text
