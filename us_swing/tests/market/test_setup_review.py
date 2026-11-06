"""Tests for MD-MKT-005.009.M05 — market/setup_review.py (setup review skill)."""
from __future__ import annotations

import logging
from typing import Any

import pytest
from pydantic import ValidationError

from tests.market.p5b_support import Env, FakeCtx, listed, query, set_ideas
from us_swing.market.setup_review import SetupGrade, SetupReview, SetupReviewSkill


def _grade(side: str, symbol: str, grade: str = "A") -> dict[str, str]:
    return {"side": side, "symbol": symbol, "grade": grade, "note": "Clean setup near trigger"}


def _review(*grades: dict[str, str]) -> SetupReview:
    return SetupReview.model_validate({"grades": list(grades)})


def test_setup_facts(p5b: Env) -> None:
    """UT-MKT-005.009.M05.T01: 10 long and 3 short in the text with parts and reasons; no Watch."""
    watch = [("long", f"WATCH{i}", "watch", 20 + i, "Tech", 50.0, 47.0) for i in range(1, 3)]
    set_ideas(p5b, listed("long", "LNG", 12) + listed("short", "SHT", 3) + watch)
    facts = SetupReviewSkill(p5b.candles).facts(p5b.home)
    assert facts.fresh and facts.data_day == p5b.day
    assert "LNG10" in facts.text and "LNG11" not in facts.text and "LNG12" not in facts.text
    assert all(f"SHT0{i}" in facts.text for i in (1, 2, 3))
    assert "WATCH" not in facts.text
    for part in ("rs_part", "flow_part", "sector_part", "Strong relative strength; Money flowing"):
        assert part in facts.text


def test_no_listed_ideas(p5b: Env) -> None:
    """UT-MKT-005.009.M05.T02: Only Watch rows make the facts stale with a no-ideas reason."""
    set_ideas(p5b, [("long", "WATCH1", "watch", 1, "Tech", 50.0, 47.0)])
    facts = SetupReviewSkill(p5b.candles).facts(p5b.home)
    assert not facts.fresh and "no listed ideas" in facts.why_stale


def test_grades_stored(p5b: Env) -> None:
    """UT-MKT-005.010.M05.T01: Grades A, B and C for three ideas make three rows."""
    set_ideas(p5b, listed("long", "LNG", 3))
    skill = SetupReviewSkill(p5b.candles)
    items = skill.act(FakeCtx(p5b.home, _review(
        _grade("long", "LNG01", "A"), _grade("long", "LNG02", "B"), _grade("long", "LNG03", "C"))),
        skill.facts(p5b.home))
    assert query(p5b.home, "SELECT side, symbol, grade FROM setup_review ORDER BY symbol") == [
        ("long", "LNG01", "A"), ("long", "LNG02", "B"), ("long", "LNG03", "C")]
    assert [i.text for i in items] == ["Setup review: 3 idea(s) graded - A 1, B 1, C 1"]


def test_unknown_or_repeated_idea(p5b: Env, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-005.010.M05.T02: A stock not in the facts and a second grade are dropped; one log."""
    set_ideas(p5b, listed("long", "LNG", 2))
    skill = SetupReviewSkill(p5b.candles)
    answer = _review(_grade("long", "LNG01", "A"), _grade("long", "LNG01", "C"),
                     _grade("long", "NOPE", "B"), _grade("long", "LNG02", "B"))
    with caplog.at_level(logging.INFO):
        skill.act(FakeCtx(p5b.home, answer), skill.facts(p5b.home))
    assert query(p5b.home, "SELECT symbol, grade FROM setup_review ORDER BY symbol") == [
        ("LNG01", "A"), ("LNG02", "B")]
    logs = [r for r in caplog.records if "Setup review named" in r.getMessage()]
    assert len(logs) == 1 and "2 stock(s)" in logs[0].getMessage()


@pytest.mark.parametrize("data", [{"grade": "D"}, {"note": "x" * 130}, {"side": "flat"}])
def test_bad_grade(data: dict[str, Any]) -> None:
    """UT-MKT-005.010.M05.T03: Grade D or a 130-character note is refused by the schema."""
    with pytest.raises(ValidationError):
        SetupGrade.model_validate({**_grade("long", "AAA"), **data})
    with pytest.raises(ValidationError):
        SetupReview.model_validate({"grades": [{**_grade("long", "AAA"), **data}]})
