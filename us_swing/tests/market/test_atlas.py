"""Tests for FO-MKT-005 ATLAS — market/atlas.py, atlas_view and its job files."""
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
from us_swing.core.desk_agents import Facts
from us_swing.core.desk_ai_settings import DeskAiSettings
from us_swing.core.desk_contract import StepContext
from us_swing.desk.employees_step import EmployeesStep
from us_swing.desk.gateway import Reply
from us_swing.desk.registry import load_employee
from us_swing.market.atlas import Atlas, AtlasView
from us_swing.market.store import AtlasRow, MarketStore

BRIEF = "Trend is flat and breadth is mixed, so the market looks choppy for now."
GOOD_JSON = ('{"regime": "Choppy", "confidence": 0.6, "reasons": ["SPY near its 50-day '
             'average", "Breadth is mixed"], "brief": "' + BRIEF + '"}')


@pytest.fixture(scope="module")
def market(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """A desk.db filled by the real P1-P3 steps on synthetic candles."""
    root = tmp_path_factory.mktemp("atlas")
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


def _view(regime: str) -> AtlasView:
    return AtlasView(regime=regime, confidence=0.6, reasons=["Breadth is mixed"], brief=BRIEF)


def _atlas_rows(home: Path) -> list[Any]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute("SELECT date, regime, rule_regime, agrees FROM atlas_view").fetchall()
    finally:
        con.close()


def test_facts_built(market: tuple[Path, Path]) -> None:
    """UT-MKT-005.001.M01.T01: Facts hold regime, breadth, sectors, ideas and proof; fresh."""
    candles, home = market
    facts = Atlas(candles).facts(home)
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
    facts = Atlas(candles).facts(home)
    assert not facts.fresh
    assert _rule(home)[0] in facts.why_stale and "2099-01-02" in facts.why_stale


def test_no_regime_rows(tmp_path: Path) -> None:
    """UT-MKT-005.001.M01.T03: An empty desk.db gives stale facts."""
    facts = Atlas(tmp_path / "candles.db").facts(tmp_path / "desk")
    assert not facts.fresh and facts.why_stale == "no market regime data yet"


@pytest.mark.parametrize("data", [
    {"regime": "Sideways"}, {"confidence": 1.4}, {"reasons": ["one a", "two b", "three", "four"]},
    {"brief": "x" * 401}, {"reasons": ["no"]}, {"extra": 1},
])
def test_answer_schema_refuses(data: dict[str, Any]) -> None:
    """UT-MKT-005.002.M01.T01: Bad regime, confidence, reasons, brief or extra key are refused."""
    base = {"regime": "Choppy", "confidence": 0.5, "reasons": ["Breadth is mixed"],
            "brief": BRIEF}
    with pytest.raises(ValidationError):
        AtlasView.model_validate({**base, **data})


def test_answer_schema_accepts() -> None:
    """UT-MKT-005.002.M01.T02: A good answer becomes an AtlasView."""
    view = AtlasView.model_validate_json(GOOD_JSON)
    assert (view.regime, view.confidence, len(view.reasons)) == ("Choppy", 0.6, 2)


def _facts(home: Path) -> Facts:
    return Facts("facts", _rule(home)[0], True)


def test_agreeing_view(market: tuple[Path, Path], tmp_path: Path) -> None:
    """UT-MKT-005.004.M01.T01: Agreeing with the rules gives the brief only; agrees 1."""
    candles, home = _copy(market, tmp_path)
    day, rule = _rule(home)
    items = Atlas(candles).act(FakeCtx(home, _view(rule)), _facts(home))
    assert [(i.author, i.kind, i.text, i.data_day) for i in items] == [
        ("ATLAS", "info", BRIEF, day)]
    assert _atlas_rows(home) == [(day, rule, rule, 1)]


def test_disagreeing_view(market: tuple[Path, Path], tmp_path: Path) -> None:
    """UT-MKT-005.004.M01.T02: Disagreeing adds the plain note; agrees 0."""
    candles, home = _copy(market, tmp_path)
    day, rule = _rule(home)
    other = "Downtrend" if rule != "Downtrend" else "Uptrend"
    (item,) = Atlas(candles).act(FakeCtx(home, _view(other)), _facts(home))
    assert item.text == f"{BRIEF} I read the market as {other}; the rules say {rule}."
    assert _atlas_rows(home) == [(day, other, rule, 0)]


def test_no_valid_answer(market: tuple[Path, Path], tmp_path: Path) -> None:
    """UT-MKT-005.004.M01.T03: No valid answer gives no feed item."""
    candles, home = _copy(market, tmp_path)
    assert Atlas(candles).act(FakeCtx(home, None), _facts(home)) == []


def test_no_view_no_row(market: tuple[Path, Path], tmp_path: Path) -> None:
    """UT-MKT-005.003.M01.T01: No valid answer leaves atlas_view empty."""
    candles, home = _copy(market, tmp_path)
    Atlas(candles).act(FakeCtx(home, None), _facts(home))
    assert _atlas_rows(home) == []


def test_view_replaced(tmp_path: Path) -> None:
    """UT-MKT-005.003.M02.T01: A second view for the same day replaces the first."""
    store = MarketStore(tmp_path)
    store.write_atlas(AtlasRow("2026-11-04", "Choppy", 0.5, "[]", BRIEF, "Choppy", True))
    store.write_atlas(AtlasRow("2026-11-04", "Uptrend", 0.7, "[]", BRIEF, "Choppy", False))
    store.close()
    assert _atlas_rows(tmp_path) == [("2026-11-04", "Uptrend", "Choppy", 0)]


def test_job_files_valid() -> None:
    """UT-MKT-005.005.M03.T01: The shipped job files load with trigger after_run and caps."""
    hire = load_employee(Atlas())
    assert hire is not None
    spec = hire.spec
    assert (spec.name, spec.trigger, spec.calls_per_day, spec.monthly_cost_usd) == (
        "ATLAS", "after_run", 3, 3.0)
    assert (spec.models.primary.source, spec.models.backup.source) == ("claude", "openrouter")
    assert "ATLAS" in hire.soul


def test_full_run(market: tuple[Path, Path], tmp_path: Path) -> None:
    """UT-MKT-005.005.M03.T02: In a desk run ATLAS leaves activity, atlas_view and one brief."""
    candles, home = _copy(market, tmp_path)
    caller_calls: list[str] = []

    def caller(source: str, model: str, system: str, user: str, key: str) -> Reply:
        caller_calls.append(model)
        return Reply(GOOD_JSON, 900, 80, 0.0)

    step = EmployeesStep(lambda: ["tests.market.test_atlas:_atlas_here"],
                         lambda: DeskAiSettings(claude_on=True, claude_model="claude-haiku-5-5"),
                         lambda: "", caller)
    _CANDLES[0] = candles
    step(StepContext(5, "manual", datetime.now(UTC), home))
    con = sqlite3.connect(home / "desk.db")
    try:
        activity = con.execute("SELECT employee, source, model, valid, tokens_in, cost_usd "
                               "FROM activity").fetchall()
        briefs = con.execute("SELECT author, text FROM briefs").fetchall()
    finally:
        con.close()
    assert activity == [("ATLAS", "claude", "claude-haiku-5-5", 1, 900, 0.0)]
    assert len(_atlas_rows(home)) == 1
    assert [a for a, _ in briefs] == ["ATLAS"]


_CANDLES: list[Path] = [Path()]


def _atlas_here() -> Atlas:
    return Atlas(_CANDLES[0])


def test_broken_job_copy(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-005.005.M03.T03: A copy of the ATLAS job file without a trigger stays asleep."""
    folder = tmp_path / "atlas"
    shutil.copytree(Atlas.folder, folder)
    job = folder / "job.yaml"
    job.write_text(job.read_text(encoding="utf-8").replace("trigger: after_run\n", ""),
                   encoding="utf-8")
    broken = Atlas()
    broken.folder = folder
    with caplog.at_level(logging.WARNING):
        assert load_employee(broken) is None
    assert "ATLAS job file is not valid" in caplog.text
