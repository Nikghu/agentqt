"""Tests for MD-MKT-012.002.M01 — market/lesson_reflect.py, MD-MKT-012.004.M02 (default
reflect employee), MD-MKT-012.005.M03 (lessons in the pick makers' facts) and the risk check
staying the same with lessons (MD-DSK-009.001.M23)."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.desk.test_desk_lessons import NOW, PULL, _active, _base, _pick, _rows
from tests.market.p5b_support import Env, FakeCtx, query
from tests.market.test_lead_brief import _stage as lead_stage
from tests.market.test_news_review import _stage as news_stage
from tests.market.test_risk_check import _staged as risk_stage
from us_swing.core.desk_contract import StepContext
from us_swing.core.desk_lessons import HEADER, add_candidate, cases, connect
from us_swing.core.desk_steps import DEFAULT_EMPLOYEE_PACKAGES, SKILL_PATHS
from us_swing.desk.registry import default_folders, load_employee
from us_swing.market.lesson_reflect import LessonReflect, LessonReflectSkill, stats_text
from us_swing.market.pick_results import PickResultsStep
from us_swing.market.regime_view import RegimeViewSkill
from us_swing.market.risk_check import RiskVetoes
from us_swing.market.sector_view import SectorViewSkill
from us_swing.market.setup_review import SetupReviewSkill


@pytest.fixture
def home(tmp_path: Path) -> Path:
    return tmp_path / "desk"


def _skill() -> LessonReflectSkill:
    return LessonReflectSkill(lambda: NOW)


def _closed(home: Path) -> list[str]:
    con = connect(home)
    try:
        return [c.key for c in cases(con)]
    finally:
        con.close()


def _answer(*lessons: dict[str, object]) -> LessonReflect:
    return LessonReflect.model_validate({"lessons": list(lessons)})


def _lesson(picks: list[str], text: str = "Pullback longs fail more often",
            tags: dict[str, str] | None = None) -> dict[str, object]:
    return {"text": text, "tags": tags or PULL, "claim": "worse", "picks": picks}


# ---------------- stats ----------------

def test_stats_by_tag(home: Path) -> None:
    """UT-MKT-012.001.M01.T01: Count, win rate and average R per setup."""
    for i, r in enumerate((-1.0, -1.0, 1.0, -1.0)):
        _pick(home, "2026-10-01", f"P{i}", r)
    for i in range(2):
        _pick(home, "2026-10-01", f"B{i}", 2.0, setup="breakout")
    con = connect(home)
    text = stats_text(cases(con))
    con.close()
    assert "setup=pullback: 4 picks, win 25%, average -0.50R" in text
    assert "setup=breakout: 2 picks, win 100%, average +2.00R" in text
    assert text.startswith("All closed picks: 6, average +0.33R")


def test_open_picks_left_out(home: Path) -> None:
    """UT-MKT-012.001.M01.T02: Open and no-fill picks are not counted."""
    _pick(home, "2026-10-01", "A", -1.0)
    _pick(home, "2026-10-01", "B", 0.5, status="open")
    _pick(home, "2026-10-01", "C", 0.0, status="no_fill")
    assert _closed(home) == ["2026-10-01|long|A"]


def test_pick_results_reviews_lessons(home: Path, tmp_path: Path) -> None:
    """UT-MKT-012.001.M01.T03: The Pick results step makes a backed candidate active."""
    lid = add_candidate(home, "Pullbacks fail", PULL, "worse", [], NOW)
    _base(home)
    PickResultsStep(tmp_path / "no-candles.db")(StepContext(1, "manual", NOW, home))
    assert _rows(home, "SELECT status FROM lessons WHERE id = ?", (lid,)) == [("active",)]


# ---------------- facts ----------------

def test_fresh_with_new_picks(home: Path) -> None:
    """UT-MKT-012.002.M01.T01: New closed picks make it fresh; facts hold stats, picks, lessons."""
    keys = _base(home)
    _active(home, "Shorts fail", {"side": "short"})
    facts = _skill().facts(home)
    assert facts.fresh
    for part in ("Results by tag:", "setup=pullback: 5 picks", keys[0], "L-1: Shorts fail"):
        assert part in facts.text


def test_no_new_picks(home: Path) -> None:
    """UT-MKT-012.002.M01.T02: With every closed pick already seen it stays asleep."""
    keys = _base(home)
    _skill().act(FakeCtx(home, _answer()), _skill().facts(home))
    facts = _skill().facts(home)
    assert not facts.fresh and facts.why_stale == "no newly closed picks"
    assert len(keys) == 10


# ---------------- answer ----------------

def test_candidates_kept(home: Path) -> None:
    """UT-MKT-012.003.M01.T01: Two valid lessons are kept, the picks are seen, one brief."""
    keys = _base(home)
    items = _skill().act(FakeCtx(home, _answer(
        _lesson(keys[:5]), _lesson(keys[5:], "Breakouts do better",
                                   {"setup": "breakout"}) | {"claim": "better"})),
        _skill().facts(home))
    assert _rows(home, "SELECT text, status FROM lessons ORDER BY id") == [
        ("Pullback longs fail more often", "active"), ("Breakouts do better", "active")]
    assert len(items) == 1 and "Breakouts do better" in items[0].text
    con = connect(home)
    seen = con.execute("SELECT value FROM memory_state WHERE key = 'reflected_keys'"
                           ).fetchone()[0]
    con.close()
    assert set(json.loads(seen)) == set(keys)


@pytest.mark.parametrize("bad", [
    {"lessons": [_lesson(["k"])] * 4},
    {"lessons": [_lesson(["k"], text="x" * 201)]},
    {"lessons": [_lesson(["k"], tags={"mood": "calm"})]},
])
def test_bad_form(bad: dict[str, object]) -> None:
    """UT-MKT-012.003.M01.T02: 4 lessons, text over 200 or an unknown tag are refused."""
    with pytest.raises(ValidationError):
        LessonReflect.model_validate(bad)


def test_unknown_picks_dropped(home: Path) -> None:
    """UT-MKT-012.003.M01.T03: A lesson naming only unknown picks is dropped; the other kept."""
    keys = _base(home)
    _skill().act(FakeCtx(home, _answer(_lesson(["2020-01-01|long|ZZZ"], "Made up one"),
                                       _lesson(keys[:2]))), _skill().facts(home))
    assert _rows(home, "SELECT text FROM lessons") == [("Pullback longs fail more often",)]


def test_log_line(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-012.006.M01.T01: The run logs how many lessons were kept and dropped."""
    keys = _base(home)
    with caplog.at_level(logging.INFO):
        _skill().act(FakeCtx(home, _answer(_lesson(["x|y|z"], "Made up one"),
                                           _lesson(keys[:2]))), _skill().facts(home))
    assert "[Memory] Kept 1 candidate lesson(s), dropped 1" in caplog.text


# ---------------- default employee ----------------

def test_default_reflect_employee() -> None:
    """UT-MKT-012.004.M02.T01: emp-010 loads as an expert with lesson_reflect on after_run."""
    folders = {f.name: f for f in default_folders(DEFAULT_EMPLOYEE_PACKAGES)}
    hire = load_employee(folders["emp-010"], SKILL_PATHS)
    assert hire is not None
    assert (hire.spec.level, hire.spec.skill, hire.spec.trigger) == (
        "expert", "lesson_reflect", ("after_run",))


def test_unknown_skill_guard() -> None:
    """UT-MKT-012.004.M02.T02: Without the lesson_reflect path emp-010 sleeps; others load."""
    folders = {f.name: f for f in default_folders(DEFAULT_EMPLOYEE_PACKAGES)}
    paths = {k: v for k, v in SKILL_PATHS.items() if k != "lesson_reflect"}
    assert load_employee(folders["emp-010"], paths) is None
    assert load_employee(folders["emp-009"], paths) is not None


# ---------------- pick makers ----------------

def test_pick_makers_get_lessons(p5b: Env) -> None:
    """UT-MKT-012.005.M03.T01: Setup, news, risk and lead facts end with the lessons block."""
    risk = risk_stage(p5b)
    news = news_stage(p5b)
    lead = lead_stage(p5b)
    _active(p5b.home, "Long picks need care", {"side": "long"})
    for skill in (SetupReviewSkill(p5b.candles), news, risk, lead):
        facts = skill.facts(p5b.home)
        assert facts.fresh, type(skill).__name__
        block = facts.text.split("\n\n")[-1]
        assert block.startswith(HEADER) and "Long picks need care" in block


def test_views_get_none(p5b: Env) -> None:
    """UT-MKT-012.005.M03.T02: Regime view and sector view facts hold no lessons."""
    _active(p5b.home, "Long picks need care", {"side": "long"})
    for skill in (RegimeViewSkill(p5b.candles), SectorViewSkill(p5b.candles)):
        assert HEADER not in skill.facts(p5b.home).text


def test_same_risk_result(p5b: Env) -> None:
    """UT-DSK-009.005.M23.T02: The risk check passes the same ideas with or without lessons."""
    def run() -> list[tuple[str, str, str]]:
        skill = risk_stage(p5b)
        skill.act(FakeCtx(p5b.home, RiskVetoes(vetoes=[])), skill.facts(p5b.home))
        return sorted(query(p5b.home, "SELECT symbol, verdict, by FROM risk_check"))

    before = run()
    _active(p5b.home, "Long picks need care", {"side": "long"})
    assert run() == before and before
