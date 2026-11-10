"""Tests for MD-MKT-005.014.M08 — market/lead_brief.py (lead brief skill)."""
from __future__ import annotations

import logging
from typing import Any

import pytest
from pydantic import ValidationError

from tests.market.p5b_support import Env, FakeCtx, Idea, listed, query, set_ideas, set_regime
from us_swing.market.lead_brief import LeadBrief, LeadBriefSkill, LeadPick
from us_swing.market.risk_check import RiskCheckSkill, RiskVeto, RiskVetoes
from us_swing.market.setup_review import SetupReview, SetupReviewSkill
from us_swing.market.store import MarketStore, RegimeViewRow, SectorViewRow

MORNING = "The market is choppy; favour Tech longs near their triggers and wait for a breakout."

# 8 long and 3 short ideas inside the limits (three sectors, so no cap is hit), plus one long (LNGBAD) that breaks the stop rule.
SECTORS = ("Tech", "Energy", "Health Care")
IDEAS: list[Idea] = [
    *[(s, y, st, r, SECTORS[r % 3], tr, sp) for s, y, st, r, _, tr, sp in
      listed("long", "LNG", 8) + listed("short", "SHT", 3)],
    ("long", "LNGBAD", "list", 9, "Energy", 100.0, 99.5),
]


def _picks(*items: tuple[str, str]) -> list[dict[str, str]]:
    return [{"side": s, "symbol": y, "reason": "Strong setup near its trigger"}
            for s, y in items]


def _brief(*items: tuple[str, str]) -> LeadBrief:
    return LeadBrief.model_validate({"picks": _picks(*items), "morning": MORNING})


def _stage(env: Env, risk: bool = True) -> LeadBriefSkill:
    """Fill the other views for the day the way the earlier employees would."""
    set_regime(env, "Choppy")
    set_ideas(env, IDEAS)
    store = MarketStore(env.home)
    store.write_regime_view(RegimeViewRow(env.day, "Choppy", 0.6, "[]", "Flat tape", "Choppy",
                                          True))
    store.replace_day("sector_view", env.day, [SectorViewRow(
        env.day, '["Tech"]', '["Energy"]', "Money is moving into Tech", "Tech leads")])
    store.close()
    review = SetupReviewSkill(env.candles)
    review.act(FakeCtx(env.home, SetupReview.model_validate({"grades": [
        {"side": "long", "symbol": "LNG01", "grade": "A", "note": "Clean setup near trigger"}]})),
        review.facts(env.home))
    if risk:
        check = RiskCheckSkill(env.candles)
        check.act(FakeCtx(env.home, RiskVetoes(vetoes=[RiskVeto.model_validate(
            {"side": "long", "symbol": "LNG02", "reason": "Gap risk before earnings"})])),
            check.facts(env.home))
    return LeadBriefSkill(env.candles)


def _pickable(text: str) -> str:
    return text.split("Ideas you may pick")[1]


def test_lead_facts(p5b: Env) -> None:
    """UT-MKT-005.014.M08.T01: The text holds each view and only the ideas that passed."""
    facts = _stage(p5b).facts(p5b.home)
    assert facts.fresh and facts.data_day == p5b.day
    for part in ("Regime view: Choppy", "Sector view: favour Tech; avoid Energy",
                 "Setup review grades", "Risk check:"):
        assert part in facts.text
    pickable = _pickable(facts.text)
    assert "LNG01" in pickable and "SHT03" in pickable
    assert "LNG02" not in pickable and "LNGBAD" not in pickable
    assert "Gap risk before earnings" in facts.text


def test_no_risk_rows(p5b: Env) -> None:
    """UT-MKT-005.014.M08.T02: Without risk rows a hard-limit break is left out; view noted."""
    facts = _stage(p5b, risk=False).facts(p5b.home)
    assert "Risk check: not available today" in facts.text
    pickable = _pickable(facts.text)
    assert "LNGBAD" not in pickable and "LNG02" in pickable


def test_valid_answer() -> None:
    """UT-MKT-005.015.M08.T01: 3 long and 2 short picks and a 600-character brief are valid."""
    answer = LeadBrief.model_validate({
        "picks": _picks(*[("long", f"LNG0{i}") for i in (1, 2, 3)],
                        *[("short", f"SHT0{i}") for i in (1, 2)]),
        "morning": "x" * 600})
    assert len(answer.picks) == 5 and len(answer.morning) == 600
    assert isinstance(answer.picks[0], LeadPick)


def test_vetoed_or_extra_picks(p5b: Env, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-005.015.M08.T02: A vetoed pick is dropped and logged; the first 5 long stay."""
    skill = _stage(p5b)
    answer = _brief(("long", "LNG02"), *[("long", f"LNG0{i}") for i in (1, 3, 4, 5, 6, 7, 8)])
    with caplog.at_level(logging.INFO):
        skill.act(FakeCtx(p5b.home, answer), skill.facts(p5b.home))
    rows = query(p5b.home, "SELECT symbol, rank FROM lead_picks ORDER BY rank")
    assert rows == [("LNG01", 1), ("LNG03", 2), ("LNG04", 3), ("LNG05", 4), ("LNG06", 5)]
    logs = [r for r in caplog.records if "Lead brief named" in r.getMessage()]
    assert len(logs) == 1 and "3 pick(s)" in logs[0].getMessage()


@pytest.mark.parametrize("data", [{"morning": "x" * 1300}, {"morning": "short"}])
def test_bad_lead_answer(data: dict[str, Any]) -> None:
    """UT-MKT-005.015.M08.T03: A 1,300-character brief or a 130-character reason is refused."""
    base: dict[str, Any] = {"picks": _picks(("long", "LNG01")), "morning": MORNING}
    with pytest.raises(ValidationError):
        LeadBrief.model_validate({**base, **data})
    with pytest.raises(ValidationError):
        LeadPick.model_validate({"side": "long", "symbol": "AAA", "reason": "x" * 130})


def test_picks_and_morning_brief(p5b: Env) -> None:
    """UT-MKT-005.016.M08.T01: Run twice; rows of the second run with rank; feed kind morning."""
    skill = _stage(p5b)
    facts = skill.facts(p5b.home)
    skill.act(FakeCtx(p5b.home, _brief(("long", "LNG01"), ("short", "SHT01"))), facts)
    items = skill.act(FakeCtx(p5b.home, _brief(("long", "LNG04"), ("long", "LNG03"),
                                               ("short", "SHT02"))), facts)
    assert [(i.kind, i.text, i.data_day) for i in items] == [("morning", MORNING, p5b.day)]
    assert query(p5b.home, "SELECT side, symbol, rank FROM lead_picks "
                 "ORDER BY side, rank") == [
        ("long", "LNG04", 1), ("long", "LNG03", 2), ("short", "SHT02", 1)]


def test_no_lead_answer(p5b: Env) -> None:
    """UT-MKT-005.016.M08.T02: No valid answer gives no picks and no feed item."""
    skill = _stage(p5b)
    assert skill.act(FakeCtx(p5b.home, None), skill.facts(p5b.home)) == []
    assert query(p5b.home, "SELECT * FROM lead_picks") == []


def test_lead_sees_final_score(p5b: Env) -> None:
    """UT-MKT-006.010.M08.T01: news_tags for passed ideas put a final column in the facts."""
    from us_swing.market.store import NewsTagRow

    skill = _stage(p5b)
    store = MarketStore(p5b.home)
    store.replace_day("news_tags", p5b.day, [
        NewsTagRow(p5b.day, "long", "LNG01", "positive", "Good news", 10.0, 91.7)])
    store.close()
    pickable = _pickable(skill.facts(p5b.home).text)
    assert "final" in pickable.splitlines()[1] and "91.7" in pickable


def test_news_review_runs_before_risk_and_lead() -> None:
    """UT-MKT-006.010.M08.T02: the risk check and lead brief needs include news_review."""
    assert "news_review" in RiskCheckSkill.needs and "news_review" in LeadBriefSkill.needs
