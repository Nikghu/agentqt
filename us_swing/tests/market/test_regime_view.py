"""Tests for FO-MKT-005 regime view skill — market/regime_view.py, regime_view, default files.

Employee names here are made up: the skill must never depend on who uses it.
"""
from __future__ import annotations

import logging
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from tests.market.test_idea_step import N, _Earnings, _make, _steps
from us_swing.core.desk_employee import load
from us_swing.core.desk_agents import Facts
from us_swing.core.desk_ai_settings import DeskAiSettings
from us_swing.core.desk_contract import StepContext
from us_swing.core.desk_steps import DEFAULT_EMPLOYEE_PACKAGES, SKILL_PATHS
from us_swing.desk.employees_step import EmployeesStep
from us_swing.desk.gateway import Reply
from us_swing.desk.registry import default_folders, load_employee
from us_swing.market import regime_view
from us_swing.market.regime_view import RegimeView, RegimeViewSkill
from us_swing.market.store import MarketStore, RegimeViewRow

BRIEF = "Trend is flat and breadth is mixed, so the market looks choppy for now."
GOOD_JSON = ('{"regime": "Choppy", "confidence": 0.6, "reasons": ["SPY near its 50-day '
             'average", "Breadth is mixed"], "brief": "' + BRIEF + '"}')


@pytest.fixture(scope="module")
def market(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """A desk.db filled by the real P1-P3 steps on synthetic candles."""
    root = tmp_path_factory.mktemp("regime_view")
    candles, home = root / "candles.db", root / "desk"
    _make(candles)
    for step in _steps(candles, N, _Earnings()):
        step(StepContext(1, "manual", datetime.now(UTC), home))
    return candles, home


def _copy(market: tuple[Path, Path], tmp_path: Path) -> tuple[Path, Path]:
    candles, home = market
    shutil.copytree(home, tmp_path / "desk")
    shutil.copy(candles, tmp_path / "candles.db")
    return tmp_path / "candles.db", tmp_path / "desk"


@dataclass
class FakeCtx:
    """Context whose ask returns a fixed view."""

    home: Path
    view: BaseModel | None

    def ask(self, facts: str, schema: type[Any]) -> Any:
        return self.view


def _rule(home: Path) -> tuple[str, str]:
    con = sqlite3.connect(home / "desk.db")
    try:
        day, regime = con.execute(
            "SELECT date, regime FROM regime_snapshot ORDER BY date DESC LIMIT 1").fetchone()
    finally:
        con.close()
    return str(day), str(regime)


def _view(regime: str) -> RegimeView:
    return RegimeView(regime=regime, confidence=0.6, reasons=["Breadth is mixed"], brief=BRIEF)


def _rows(home: Path) -> list[Any]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute("SELECT date, regime, rule_regime, agrees FROM regime_view").fetchall()
    finally:
        con.close()


def test_facts_built(market: tuple[Path, Path]) -> None:
    """UT-MKT-005.001.M01.T01: Facts hold regime, breadth, sectors, ideas and proof; fresh."""
    candles, home = market
    facts = RegimeViewSkill(candles).facts(home)
    assert facts.fresh and facts.data_day == _rule(home)[0]
    for part in ("Regime by the rules, last 20 days", "Breadth today", "Sectors today",
                 "Ideas today", "Score proof on past data: no proof run yet"):
        assert part in facts.text


def test_stale_data(market: tuple[Path, Path], tmp_path: Path) -> None:
    """UT-MKT-005.001.M01.T02: A newer SPY candle than the regime day makes the facts stale."""
    candles, home = _copy(market, tmp_path)
    con = sqlite3.connect(candles)
    con.execute("INSERT INTO price_1d VALUES ('SPY', '2099-01-02T00:00:00', 1, 1, 1, 1, 1)")
    con.commit()
    con.close()
    facts = RegimeViewSkill(candles).facts(home)
    assert not facts.fresh
    assert _rule(home)[0] in facts.why_stale and "2099-01-02" in facts.why_stale


def test_no_regime_rows(tmp_path: Path) -> None:
    """UT-MKT-005.001.M01.T03: An empty desk.db gives stale facts."""
    facts = RegimeViewSkill(tmp_path / "candles.db").facts(tmp_path / "desk")
    assert not facts.fresh and facts.why_stale == "no market regime data yet"


@pytest.mark.parametrize("data", [
    {"regime": "Sideways"}, {"confidence": 1.4}, {"reasons": ["one a", "two b", "three", "four"]},
    {"brief": "x" * 401}, {"reasons": ["no"]}, {"reasons": ["x" * 141]}, {"extra": 1},
])
def test_answer_schema_refuses(data: dict[str, Any]) -> None:
    """UT-MKT-005.002.M01.T01: Bad regime, confidence, reasons, brief or extra key are refused."""
    base = {"regime": "Choppy", "confidence": 0.5, "reasons": ["Breadth is mixed"],
            "brief": BRIEF}
    with pytest.raises(ValidationError):
        RegimeView.model_validate({**base, **data})


def test_answer_schema_accepts() -> None:
    """UT-MKT-005.002.M01.T02: A good answer becomes a view; limits are in the schema shown."""
    view = RegimeView.model_validate_json(GOOD_JSON)
    assert (view.regime, view.confidence, len(view.reasons)) == ("Choppy", 0.6, 2)
    items = RegimeView.model_json_schema()["properties"]["reasons"]["items"]
    assert items["maxLength"] == 140


def _facts(home: Path) -> Facts:
    return Facts("facts", _rule(home)[0], True)


def test_agreeing_view(market: tuple[Path, Path], tmp_path: Path) -> None:
    """UT-MKT-005.004.M01.T01: Agreeing with the rules gives the brief only; agrees 1."""
    candles, home = _copy(market, tmp_path)
    day, rule = _rule(home)
    items = RegimeViewSkill(candles).act(FakeCtx(home, _view(rule)), _facts(home))
    assert [(i.kind, i.text, i.data_day) for i in items] == [("info", BRIEF, day)]
    assert _rows(home) == [(day, rule, rule, 1)]


def test_disagreeing_view(market: tuple[Path, Path], tmp_path: Path) -> None:
    """UT-MKT-005.004.M01.T02: Disagreeing adds the plain note; agrees 0."""
    candles, home = _copy(market, tmp_path)
    day, rule = _rule(home)
    other = "Downtrend" if rule != "Downtrend" else "Uptrend"
    (item,) = RegimeViewSkill(candles).act(FakeCtx(home, _view(other)), _facts(home))
    assert item.text == f"{BRIEF} I read the market as {other}; the rules say {rule}."
    assert _rows(home) == [(day, other, rule, 0)]


def test_no_valid_answer(market: tuple[Path, Path], tmp_path: Path) -> None:
    """UT-MKT-005.004.M01.T03: No valid answer gives no feed item."""
    candles, home = _copy(market, tmp_path)
    assert RegimeViewSkill(candles).act(FakeCtx(home, None), _facts(home)) == []


def test_no_view_no_row(market: tuple[Path, Path], tmp_path: Path) -> None:
    """UT-MKT-005.003.M01.T01: No valid answer leaves regime_view empty."""
    candles, home = _copy(market, tmp_path)
    RegimeViewSkill(candles).act(FakeCtx(home, None), _facts(home))
    assert _rows(home) == []


def test_view_replaced(tmp_path: Path) -> None:
    """UT-MKT-005.003.M02.T01: A second view for the same day replaces the first."""
    store = MarketStore(tmp_path)
    store.write_regime_view(RegimeViewRow("2026-11-04", "Choppy", 0.5, "[]", BRIEF, "Choppy",
                                          True))
    store.write_regime_view(RegimeViewRow("2026-11-04", "Uptrend", 0.7, "[]", BRIEF, "Choppy",
                                          False))
    store.close()
    assert _rows(tmp_path) == [("2026-11-04", "Uptrend", "Choppy", 0)]


def _default_folder() -> Path:
    folders = [f for f in default_folders(DEFAULT_EMPLOYEE_PACKAGES)
               if load(f).spec.skill == regime_view.KEY]
    assert len(folders) == 1
    return folders[0]


def test_default_files_valid() -> None:
    """UT-MKT-005.005.M03.T01: The shipped default employee for this skill is valid."""
    hire = load_employee(_default_folder(), SKILL_PATHS)
    assert hire is not None
    spec = hire.spec
    assert (spec.skill, spec.trigger, spec.calls_per_day, spec.monthly_cost_usd) == (
        "regime_view", ("after_run",), 3, 3.0)
    assert (spec.models.primary.source, spec.models.backup.source) == ("claude", "openrouter")
    assert "{name}" not in hire.soul and spec.name in hire.soul


def test_full_run(market: tuple[Path, Path], tmp_path: Path) -> None:
    """UT-MKT-005.005.M03.T02: In a desk run the employee leaves activity, a view and a brief."""
    candles, home = _copy(market, tmp_path)
    folder = home / "employees" / "x-7"
    shutil.copytree(_default_folder(), folder)
    job = (folder / "employee.md").read_text(encoding="utf-8")
    spec = load(folder).spec
    job = job.replace(f"id: {spec.id}", "id: x-7").replace(f"name: {spec.name}",
                                                          "name: Made Up Name")
    (folder / "employee.md").write_text(job, encoding="utf-8")

    def caller(source: str, model: str, system: str, user: str, key: str) -> Reply:
        assert "Made Up Name" in system
        return Reply(GOOD_JSON, 900, 80, 0.0)

    _CANDLES[0] = candles
    step = EmployeesStep(lambda: {"regime_view": "tests.market.test_regime_view:_skill_here"},
                         lambda: [],
                         lambda: DeskAiSettings(claude_on=True, claude_model="claude-haiku-5-5"),
                         lambda: "", caller)
    step(StepContext(5, "manual", datetime.now(UTC), home))
    con = sqlite3.connect(home / "desk.db")
    try:
        activity = con.execute("SELECT employee, employee_name, source, model, valid, "
                               "tokens_in, cost_usd FROM activity").fetchall()
        briefs = con.execute("SELECT author, employee_id FROM briefs").fetchall()
    finally:
        con.close()
    assert activity == [("x-7", "Made Up Name", "claude", "claude-haiku-5-5", 1, 900, 0.0)]
    assert len(_rows(home)) == 1
    assert briefs == [("Made Up Name", "x-7")]


_CANDLES: list[Path] = [Path()]


def _skill_here() -> RegimeViewSkill:
    return RegimeViewSkill(_CANDLES[0])


def test_broken_default_copy(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-005.005.M03.T03: A copy of the default job file without a trigger stays asleep."""
    folder = tmp_path / "copy"
    shutil.copytree(_default_folder(), folder)
    job = folder / "employee.md"
    job.write_text(job.read_text(encoding="utf-8").replace("trigger:\n- after_run\n", ""),
                   encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        assert load_employee(folder, SKILL_PATHS) is None
    assert "not valid, it stays asleep" in caplog.text
