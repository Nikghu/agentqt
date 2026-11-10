"""Tests for MD-MKT-005.017.M09 — default employee files, skill list and the evening chain.

Employee names here are made up: the skills must never depend on who uses them.
"""
from __future__ import annotations

import importlib
import json
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

import us_swing.market
from tests.market.p5b_support import Env, query, set_ideas, set_regime
from us_swing.core.desk_ai_settings import DeskAiSettings
from us_swing.core.desk_contract import StepContext
from us_swing.core.desk_steps import DEFAULT_EMPLOYEE_PACKAGES, SKILL_PATHS
from us_swing.desk.employees_step import EmployeesStep
from us_swing.desk.gateway import Reply
from us_swing.desk.registry import default_folders, load_employee
from us_swing.market.regime_view import RegimeViewSkill
from us_swing.market.risk_check import RiskCheckSkill
from us_swing.market.sector_view import SectorViewSkill
from us_swing.market.setup_review import SetupReviewSkill

GENERIC_NAME = re.compile(r"^(Lead|Expert|Champion|Junior) \d+$")
P5B_SKILLS = {"emp-002": "sector_flow_view", "emp-003": "setup_review", "emp-004": "risk_check",
              "emp-005": "lead_brief"}
_CANDLES: list[Path] = [Path()]


def _folders() -> dict[str, Path]:
    return {f.name: f for f in default_folders(DEFAULT_EMPLOYEE_PACKAGES)}


def _job(folder: Path) -> dict[str, object]:
    data = yaml.safe_load((folder / "job.yaml").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_default_files_valid() -> None:
    """UT-MKT-005.017.M09.T01: emp-002 to emp-005 load with skill, after_run, caps 3 and USD 3."""
    folders = _folders()
    for emp, skill in P5B_SKILLS.items():
        hire = load_employee(folders[emp], SKILL_PATHS)
        assert hire is not None, emp
        spec = hire.spec
        assert (spec.skill, spec.trigger, spec.calls_per_day, spec.monthly_cost_usd) == (
            skill, ("after_run",), 3, 3.0)
        assert GENERIC_NAME.match(spec.name)
        assert "{name}" not in hire.soul and spec.name in hire.soul


def test_no_real_names_in_defaults() -> None:
    """UT-MKT-005.017.M09.T02: Every shipped default name matches the generic level pattern."""
    folders = _folders()
    assert set(P5B_SKILLS) <= set(folders)
    for folder in folders.values():
        name = str(_job(folder)["name"])
        assert GENERIC_NAME.match(name), f"{folder.name}: {name}"
        soul = (folder / "soul.md").read_text(encoding="utf-8")
        assert not re.search(r"\b[A-Z]{4,}\b(?= (is|will|speaks))", soul)


def test_skill_list() -> None:
    """UT-MKT-005.018.M09.T01: The skill keys (five, news_review in P5c, report_page in P5d, lead_chat in P9, data_recipe in P10) load to skills with a matching key."""
    assert set(SKILL_PATHS) == {"regime_view", "sector_flow_view", "setup_review", "risk_check", "news_review",
                                "lead_brief", "report_page", "lead_chat",
                                "data_recipe"}
    for key, path in SKILL_PATHS.items():
        module, _, cls = path.partition(":")
        skill = getattr(importlib.import_module(module), cls)()
        assert skill.key == key


def test_no_desk_import() -> None:
    """UT-MKT-005.018.M09.T02: No source under market imports us_swing.desk."""
    root = Path(us_swing.market.__file__).parent
    pattern = re.compile(r"^\s*(from|import)\s+us_swing\.desk(\.|\s|$)", re.MULTILINE)
    files = sorted(root.glob("*.py"))
    assert len(files) > 5
    bad = [f.name for f in files if pattern.search(f.read_text(encoding="utf-8"))]
    assert bad == []


def _regime() -> RegimeViewSkill:
    return RegimeViewSkill(_CANDLES[0])


def _sector() -> SectorViewSkill:
    return SectorViewSkill(_CANDLES[0])


def _setup() -> SetupReviewSkill:
    return SetupReviewSkill(_CANDLES[0])


def _risk() -> RiskCheckSkill:
    return RiskCheckSkill(_CANDLES[0])


def _lead() -> object:
    from us_swing.market.lead_brief import LeadBriefSkill  # noqa: PLC0415

    return LeadBriefSkill(_CANDLES[0])


def _hire(home: Path, number: int, source: str) -> None:
    """Copy a default employee folder under a made-up id and name."""
    import shutil  # noqa: PLC0415

    folder = home / "employees" / f"x-{number}"
    shutil.copytree(_folders()[source], folder)
    text = (folder / "job.yaml").read_text(encoding="utf-8")
    text = re.sub(r"(?m)^id: .*$", f"id: x-{number}", text)
    text = re.sub(r"(?m)^name: .*$", f"name: Tester {'ABCDE'[number - 1]}", text)
    text = re.sub(r"(?m)^reports_to: .*$", "reports_to: null", text)
    (folder / "job.yaml").write_text(text, encoding="utf-8")


def test_full_evening_chain(p5b: Env) -> None:
    """UT-MKT-005.018.M09.T03: Views, risk rows, picks and evening brief stored; lead ran last."""
    _CANDLES[0] = p5b.candles
    for number, source in enumerate(("emp-001", "emp-002", "emp-003", "emp-004", "emp-005"), 1):
        _hire(p5b.home, number, source)
    set_regime(p5b, "Choppy")
    set_ideas(p5b, [("long", "ZZA", "list", 1, "Tech", 50.0, 47.0)])
    ((symbol, side),) = query(p5b.home, "SELECT symbol, side FROM ideas WHERE status = 'list' "
                                        "AND date = ?", (p5b.day,))
    sectors = [str(r[0]) for r in query(p5b.home, "SELECT sector FROM sector_daily "
                                        "WHERE date = ? ORDER BY rank", (p5b.day,))]
    answers = {
        "Tester A": {"regime": "Choppy", "confidence": 0.6, "reasons": ["Breadth is mixed"],
                     "brief": "Trend is flat and breadth is mixed, so the market looks choppy."},
        "Tester B": {"favour": sectors[:1], "avoid": sectors[-1:],
                     "rotation": "Money is moving into the leading sector",
                     "brief": "The leading sector gets the money, so favour it for now."},
        "Tester C": {"grades": [{"side": side, "symbol": symbol, "grade": "B",
                                 "note": "Decent setup near its trigger"}]},
        "Tester D": {"vetoes": []},
        "Tester E": {"picks": [{"side": side, "symbol": symbol,
                                "reason": "Best setup that passed the risk check"}],
                     "evening": "The market is mixed today; one idea passed every check and "
                                "it is the only pick for tomorrow."},
    }

    def caller(source: str, model: str, system: str, user: str, key: str) -> Reply:
        name = next(n for n in answers if n in system)
        return Reply(json.dumps(answers[name]), 500, 50, 0.0)

    skills = {"regime_view": "tests.market.test_p5b_defaults:_regime",
              "sector_flow_view": "tests.market.test_p5b_defaults:_sector",
              "setup_review": "tests.market.test_p5b_defaults:_setup",
              "risk_check": "tests.market.test_p5b_defaults:_risk",
              "lead_brief": "tests.market.test_p5b_defaults:_lead"}
    step = EmployeesStep(lambda: skills, lambda: [],
                         lambda: DeskAiSettings(claude_on=True, claude_model="claude-haiku-5-5"),
                         lambda: "", caller)
    step(StepContext(7, "manual", datetime.now(UTC), p5b.home))

    for table in ("regime_view", "sector_view", "setup_review", "risk_check", "lead_picks"):
        assert len(query(p5b.home, f"SELECT * FROM {table}")) == 1, table  # noqa: S608
    assert query(p5b.home, "SELECT verdict, by FROM risk_check") == [("pass", "code")]
    assert query(p5b.home, "SELECT symbol, rank FROM lead_picks") == [(symbol, 1)]
    con = sqlite3.connect(p5b.home / "desk.db")
    try:
        order = [r[0] for r in con.execute("SELECT employee FROM activity ORDER BY id")]
        kinds = dict(con.execute("SELECT employee_id, kind FROM briefs").fetchall())
    finally:
        con.close()
    assert sorted(order) == ["x-1", "x-2", "x-3", "x-4", "x-5"]
    assert order[-1] == "x-5" and order.index("x-4") > order.index("x-3")
    assert kinds["x-5"] == "evening"


@pytest.mark.parametrize("emp", sorted(P5B_SKILLS))
def test_soul_has_name_placeholder(emp: str) -> None:
    """UT-MKT-005.017.M09.T03: Each default soul holds the name placeholder to fill in."""
    assert "{name}" in (_folders()[emp] / "soul.md").read_text(encoding="utf-8")


def test_news_default_file_valid() -> None:
    """UT-MKT-006.011.M06.T01: emp-006 loads with news_review, after_run, caps 3 and USD 3."""
    hire = load_employee(_folders()["emp-006"], SKILL_PATHS)
    assert hire is not None
    spec = hire.spec
    assert (spec.skill, spec.trigger, spec.calls_per_day, spec.monthly_cost_usd) == (
        "news_review", ("after_run",), 3, 3.0)
    assert GENERIC_NAME.match(spec.name)
    assert "{name}" not in hire.soul and spec.name in hire.soul


def test_news_skill_step_order_and_boundary() -> None:
    """UT-MKT-006.011.M06.T02: news_review loads, News runs after Ideas, no desk import."""
    from us_swing.core.desk_steps import STEP_PATHS  # noqa: PLC0415

    module, _, cls = SKILL_PATHS["news_review"].partition(":")
    assert getattr(importlib.import_module(module), cls)().key == "news_review"
    names = [p.partition(":")[0].rsplit(".", 1)[1] for p in STEP_PATHS]
    assert names.index("news_step") == names.index("idea_step") + 1
    root = Path(us_swing.market.__file__).parent
    pattern = re.compile(r"^\s*(from|import)\s+us_swing\.desk(\.|\s|$)", re.MULTILINE)
    for name in ("news.py", "news_step.py", "news_review.py"):
        assert not pattern.search((root / name).read_text(encoding="utf-8")), name


def test_report_default_file_valid() -> None:
    """UT-MKT-007.007.M04.T01: emp-007 loads with report_page, after_run, caps 3 and USD 3."""
    hire = load_employee(_folders()["emp-007"], SKILL_PATHS)
    assert hire is not None
    spec = hire.spec
    assert (spec.skill, spec.trigger, spec.calls_per_day, spec.monthly_cost_usd) == (
        "report_page", ("after_run",), 3, 3.0)
    assert GENERIC_NAME.match(spec.name) and spec.level == "expert"
    assert "{name}" not in hire.soul and spec.name in hire.soul


def test_report_skill_and_boundary() -> None:
    """UT-MKT-007.007.M04.T02: report_page loads from the skill list; market never imports desk."""
    module, _, cls = SKILL_PATHS["report_page"].partition(":")
    assert getattr(importlib.import_module(module), cls)().key == "report_page"
    root = Path(us_swing.market.__file__).parent
    pattern = re.compile(r"^\s*(from|import)\s+us_swing\.desk(\.|\s|$)", re.MULTILINE)
    for path in root.glob("*.py"):
        assert not pattern.search(path.read_text(encoding="utf-8")), path.name
