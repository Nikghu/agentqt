"""Tests for MD-MKT-011.001.M01 (core/desk_data_asks.py), MD-MKT-011.002.M02 (data event),
MD-MKT-011.004.M03 (core/desk_recipes.py), MD-MKT-011.003.M04 (data recipe skill),
MD-MKT-011.007.M05 (asked panels in the Floor catalog) and MD-MKT-011.008.M06 (default data
employee). Employee names here are made up."""
from __future__ import annotations

import importlib
import json
import logging
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, TypeVar

import pytest
import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ValidationError

import tests.desk.test_harness as th
from us_swing.core import desk_data_asks as da
from us_swing.core.desk_contract import DB_NAME, StepContext
from us_swing.core.desk_events import post_event
from us_swing.core.desk_floor import DeskFloorData
from us_swing.core.desk_recipes import DataRecipe, check_recipe, recipe_words, run_recipe
from us_swing.core.desk_steps import SKILL_PATHS
from us_swing.data.market_calendar import ET
from us_swing.desk.employees_step import EmployeesStep
from us_swing.desk.gateway import Reply
from us_swing.gui.floor_sample import SampleFloorData
from us_swing.market import data_recipe as dr
from us_swing.market.store import _SCHEMA as MARKET_SCHEMA

T = TypeVar("T", bound=BaseModel)
NOW = datetime(2026, 11, 10, 12, 0, tzinfo=ET)
EMP = Path(dr.__file__).parent / "employees" / "emp-009"
GOOD = {"title": "Tech longs", "source": "scores", "columns": ["symbol", "score", "sector"],
        "filters": [{"column": "side", "op": "=", "value": "long"},
                    {"column": "score", "op": ">", "value": 80},
                    {"column": "sector", "op": "=", "value": "Technology"}],
        "sort": "score", "limit": 2}


def _q(home: Path, sql: str) -> list[tuple[Any, ...]]:
    con = sqlite3.connect(home / DB_NAME)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def _market(home: Path) -> None:
    """Scores and ratings on two days; the latest day has 3 long Technology scores above 80."""
    home.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(home / DB_NAME)
    try:
        con.executescript(MARKET_SCHEMA)
        rows = [("2026-11-06", "OLD", "long", 99.0, "Technology"),
                ("2026-11-09", "AAA", "long", 85.0, "Technology"),
                ("2026-11-09", "BBB", "long", 92.0, "Technology"),
                ("2026-11-09", "CCC", "long", 81.5, "Technology"),
                ("2026-11-09", "DDD", "long", 95.0, "Energy"),
                ("2026-11-09", "EEE", "short", 90.0, "Technology"),
                ("2026-11-09", "FFF", "long", 70.0, "Technology")]
        for day, sym, side, score, sector in rows:
            con.execute("INSERT INTO stock_score (date, symbol, side, score) VALUES (?, ?, ?, ?)",
                        (day, sym, side, score))
            con.execute("INSERT OR IGNORE INTO stock_rs (date, symbol, sector) VALUES (?, ?, ?)",
                        (day, sym, sector))
        con.execute("INSERT INTO sector_daily (date, sector) VALUES ('2026-11-09', 'Technology')")
        con.execute("INSERT INTO sector_daily (date, sector) VALUES ('2026-11-09', 'Energy')")
        con.commit()
    finally:
        con.close()


def _recipe(**change: Any) -> DataRecipe:
    return DataRecipe.model_validate({**GOOD, **change})


class _Ctx:
    def __init__(self, home: Path, answer: dict[str, Any] | None) -> None:
        self.home, self._answer = home, answer

    def ask(self, facts: str, schema: type[T]) -> T | None:
        return None if self._answer is None else schema.model_validate(self._answer)


def _skill(now: datetime = NOW) -> dr.DataRecipeSkill:
    return dr.DataRecipeSkill(lambda: now)


def _proposed(home: Path, recipe: DataRecipe | None = None) -> int:
    rid = da.ask_data(home, "Tech longs", NOW)
    return da.add_asked(home, rid, recipe or _recipe(), "", NOW)


def test_request_saved(tmp_path: Path) -> None:
    """UT-MKT-011.001.M01.T01: a request adds one row and one waiting data_request event."""
    rid = da.ask_data(tmp_path, "  long scores above 80  ", NOW)
    assert _q(tmp_path, "SELECT id, text FROM data_requests") == [(rid, "long scores above 80")]
    assert _q(tmp_path, "SELECT kind, state FROM events") == [("data_request", "waiting")]


def test_bad_request(tmp_path: Path) -> None:
    """UT-MKT-011.001.M01.T02: empty or too long requests are refused."""
    for text in ("   ", "x" * 301):
        with pytest.raises(ValueError):
            da.ask_data(tmp_path, text, NOW)
    assert not (tmp_path / DB_NAME).exists()


def test_append_only(tmp_path: Path) -> None:
    """UT-MKT-011.001.M01.T03: request and asked product rows never change."""
    _proposed(tmp_path)
    con = sqlite3.connect(tmp_path / DB_NAME)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("UPDATE data_requests SET text = 'x'")
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("DELETE FROM asked_products")
    finally:
        con.close()


def test_one_event_per_request(tmp_path: Path) -> None:
    """UT-MKT-011.002.M02.T01: two requests give two priority-0 events with their limits."""
    da.ask_data(tmp_path, "One", NOW)
    da.ask_data(tmp_path, "Two", NOW)
    rows = _q(tmp_path, "SELECT priority, created, deadline, expires FROM events")
    assert len(rows) == 2
    for prio, created, deadline, expires in rows:
        start = datetime.fromisoformat(created)
        assert prio == 0
        assert datetime.fromisoformat(deadline) - start == timedelta(minutes=5)
        assert datetime.fromisoformat(expires) - start == timedelta(hours=2)


def test_unknown_kind(tmp_path: Path) -> None:
    """UT-MKT-011.002.M02.T02: an unknown event kind is still refused."""
    with pytest.raises(ValueError):
        post_event(tmp_path, "data_answer", "2026-11-10", NOW)


def test_desk_end_to_end(tmp_path: Path) -> None:
    """UT-MKT-011.002.M02.T03: the desk wakes the data employee and saves its asked product."""
    home = tmp_path / "desk"
    th.employee(home, "d-1", th.job("d-1", "Data Person", "expert", "data_recipe")
                .replace("trigger: after_run", "trigger: data_request"))
    rid = da.ask_data(home, "Tech longs", datetime.now(ET))
    caller = th.FakeCaller(Reply(json.dumps({"recipe": GOOD, "reason": ""}), 100, 20, 0.0))
    step = EmployeesStep(lambda: {"data_recipe": "us_swing.market.data_recipe:DataRecipeSkill"},
                         lambda: [], lambda: th.ON, lambda: "key", caller)
    assert step.has_work(home)
    step.handle_events(StepContext(1, "event", datetime.now(ET), home))
    assert _q(home, "SELECT request_id, state, title FROM asked_products") == [
        (rid, "proposed", "Tech longs")]
    assert f"Request #{rid}: Tech longs" in caller.calls[0][3]


def test_recipe_facts(tmp_path: Path) -> None:
    """UT-MKT-011.003.M04.T01: facts hold the request, every menu source and the sectors."""
    _market(tmp_path)
    rid = da.ask_data(tmp_path, "Tech longs", NOW)
    facts = _skill().facts(tmp_path)
    assert facts.fresh
    for part in (f"Request #{rid}: Tech longs", "Scores (scores):", "Ideas (ideas):",
                 "Stock RS (stock_rs):", "Sectors (sectors):", "Pick results (pick_results):",
                 "sector: Energy, Technology", "score (number)"):
        assert part in facts.text


def test_nothing_to_build(tmp_path: Path) -> None:
    """UT-MKT-011.003.M04.T02: no request, or only an old one, keeps the employee asleep."""
    assert not _skill().facts(tmp_path).fresh
    da.ask_data(tmp_path, "Old", NOW)
    assert not _skill(NOW + timedelta(hours=3)).facts(tmp_path).fresh


def test_oldest_first(tmp_path: Path) -> None:
    """UT-MKT-011.003.M04.T03: the older open request is built first."""
    older = da.ask_data(tmp_path, "First", NOW)
    da.ask_data(tmp_path, "Second", NOW)
    skill = _skill()
    facts = skill.facts(tmp_path)
    assert f"Request #{older}: First" in facts.text
    skill.act(_Ctx(tmp_path, {"recipe": GOOD}), facts)
    assert _q(tmp_path, "SELECT request_id FROM asked_products") == [(older,)]


def test_recipe_runs(tmp_path: Path) -> None:
    """UT-MKT-011.004.M03.T01: latest day only, matching rows, high to low, row limit."""
    _market(tmp_path)
    assert run_recipe(tmp_path, _recipe()) == [
        {"symbol": "BBB", "score": 92.0, "sector": "Technology"},
        {"symbol": "AAA", "score": 85.0, "sector": "Technology"}]
    low = run_recipe(tmp_path, _recipe(descending=False, limit=10))
    assert [r["symbol"] for r in low] == ["CCC", "AAA", "BBB"]


def test_check_refuses(tmp_path: Path) -> None:
    """UT-MKT-011.004.M03.T02: columns, signs, values and sort outside the menu are refused."""
    bad = [
        (_recipe(columns=["symbol", "price"]), "unknown column price"),
        (_recipe(columns=["symbol", "symbol"]), "column symbol twice"),
        (_recipe(filters=[{"column": "volume", "op": "=", "value": 1}]),
         "unknown filter column volume"),
        (_recipe(filters=[{"column": "sector", "op": ">", "value": "A"}]),
         "sector takes = or != only"),
        (_recipe(filters=[{"column": "score", "op": ">", "value": "high"}]),
         "score needs a number"),
        (_recipe(sort="price"), "unknown sort column price"),
    ]
    for recipe, why in bad:
        assert check_recipe(recipe) == why
        with pytest.raises(ValueError, match=why):
            run_recipe(tmp_path, recipe)
    assert check_recipe(_recipe()) == ""


def test_no_sql_from_model(tmp_path: Path) -> None:
    """UT-MKT-011.004.M03.T03: values are bound, names come from the menu, limit is capped."""
    _market(tmp_path)
    attack = "x'; DROP TABLE stock_score;--"
    assert run_recipe(tmp_path, _recipe(filters=[{"column": "symbol", "op": "=",
                                                  "value": attack}])) == []
    assert _q(tmp_path, "SELECT COUNT(*) FROM stock_score") == [(7,)]
    assert check_recipe(_recipe(columns=["symbol FROM ideas; --"])).startswith("unknown column")
    with pytest.raises(ValidationError):
        _recipe(limit=101)
    with pytest.raises(ValidationError):
        DataRecipe.model_validate({**GOOD, "sql": "SELECT 1"})


def test_read_only_and_empty(tmp_path: Path) -> None:
    """UT-MKT-011.004.M03.T04: no desk.db or a missing table gives no rows and no file."""
    assert run_recipe(tmp_path, _recipe()) == []
    assert not (tmp_path / DB_NAME).exists()
    da.ask_data(tmp_path, "Make the file", NOW)
    assert run_recipe(tmp_path, _recipe()) == []


def test_recipe_words() -> None:
    """UT-MKT-011.004.M03.T05: the recipe reads as source, columns, filters, sort and limit."""
    words = recipe_words(_recipe(filters=GOOD["filters"][:2]))
    assert words == ("Scores · symbol, score, sector · side = long, score > 80 · "
                     "score high to low · up to 2 rows")


def test_proposed_product(tmp_path: Path) -> None:
    """UT-MKT-011.005.M04.T01: a good recipe is saved as one proposed product."""
    rid = da.ask_data(tmp_path, "Tech longs", NOW)
    skill = _skill()
    assert skill.act(_Ctx(tmp_path, {"recipe": GOOD}), skill.facts(tmp_path)) == []
    [(req, state, title, recipe)] = _q(tmp_path, "SELECT request_id, state, title, recipe "
                                                 "FROM asked_products")
    assert (req, state, title) == (rid, "proposed", "Tech longs")
    assert DataRecipe.model_validate_json(recipe) == _recipe()


def test_failed_product(tmp_path: Path) -> None:
    """UT-MKT-011.005.M04.T02: no answer, no recipe, or a recipe that fails the check fails."""
    skill = _skill()
    answers: list[dict[str, Any] | None] = [
        None, {"recipe": None, "reason": "No volume data in the menu"},
        {"recipe": {**GOOD, "columns": ["price"]}}]
    for answer in answers:
        da.ask_data(tmp_path, "Something", NOW)
        skill.act(_Ctx(tmp_path, answer), skill.facts(tmp_path))
    assert _q(tmp_path, "SELECT state, reason FROM asked_products ORDER BY id") == [
        ("failed", dr.NO_ANSWER), ("failed", "No volume data in the menu"),
        ("failed", "The recipe did not pass the check: unknown column price")]


def test_one_answer_per_request(tmp_path: Path) -> None:
    """UT-MKT-011.005.M01.T01: a second asked product for the same request is refused."""
    rid = da.ask_data(tmp_path, "Once", NOW)
    da.add_asked(tmp_path, rid, None, "no", NOW)
    with pytest.raises(sqlite3.IntegrityError):
        da.add_asked(tmp_path, rid, _recipe(), "", NOW)


def test_decision_saved(tmp_path: Path) -> None:
    """UT-MKT-011.006.M01.T01: approve adds a data_product approval and lists the product."""
    pid = _proposed(tmp_path)
    assert [p.id for p in da.waiting_products(tmp_path)] == [pid]
    assert da.decide_product(tmp_path, pid, "approve", NOW) == ""
    assert _q(tmp_path, "SELECT kind, subject, decision FROM approvals") == [
        ("data_product", str(pid), "approve")]
    assert da.waiting_products(tmp_path) == []
    assert [p.id for p in da.approved_products(tmp_path)] == [pid]


def test_decision_refused(tmp_path: Path) -> None:
    """UT-MKT-011.006.M01.T02: second, unknown and not-proposed decisions are refused."""
    pid = _proposed(tmp_path)
    da.decide_product(tmp_path, pid, "reject", NOW)
    assert da.decide_product(tmp_path, pid, "approve", NOW) == "already decided"
    assert da.decide_product(tmp_path, pid, "maybe", NOW) == "unknown decision"
    assert da.decide_product(tmp_path, 999, "approve", NOW) == "not found"
    failed = da.add_asked(tmp_path, da.ask_data(tmp_path, "x", NOW), None, "no", NOW)
    assert da.decide_product(tmp_path, failed, "approve", NOW) == "not found"
    assert _q(tmp_path, "SELECT COUNT(*) FROM approvals") == [(1,)]


def _floor(home: Path) -> DeskFloorData:
    return DeskFloorData(SampleFloorData(), home)


def test_asked_panel_in_catalog(tmp_path: Path) -> None:
    """UT-MKT-011.007.M05.T01: an approved product is listed and its rows come from the recipe."""
    _market(tmp_path)
    pid = _proposed(tmp_path)
    da.decide_product(tmp_path, pid, "approve", NOW)
    [product] = [p for p in _floor(tmp_path).products() if p.id == f"asked.{pid}"]
    assert (product.title, product.kind, product.columns) == (
        "Tech longs (asked)", "table", ("symbol", "score", "sector"))
    assert _floor(tmp_path).rows(product.id, {}) == run_recipe(tmp_path, _recipe())


def test_new_day_without_rebuild(tmp_path: Path) -> None:
    """UT-MKT-011.007.M05.T02: after a new data day the panel shows the new day's rows."""
    _market(tmp_path)
    pid = _proposed(tmp_path)
    da.decide_product(tmp_path, pid, "approve", NOW)
    con = sqlite3.connect(tmp_path / DB_NAME)
    with con:
        con.execute("INSERT INTO stock_score (date, symbol, side, score) "
                    "VALUES ('2026-11-10', 'NEW', 'long', 88.0)")
        con.execute("INSERT INTO stock_rs (date, symbol, sector) "
                    "VALUES ('2026-11-10', 'NEW', 'Technology')")
    con.close()
    assert _floor(tmp_path).rows(f"asked.{pid}", {}) == [
        {"symbol": "NEW", "score": 88.0, "sector": "Technology"}]


def test_not_listed(tmp_path: Path) -> None:
    """UT-MKT-011.007.M05.T03: waiting, rejected, failed and broken products are not listed."""
    _proposed(tmp_path)
    da.decide_product(tmp_path, _proposed(tmp_path), "reject", NOW)
    da.add_asked(tmp_path, da.ask_data(tmp_path, "x", NOW), None, "no", NOW)
    rid = da.ask_data(tmp_path, "broken", NOW)
    con = sqlite3.connect(tmp_path / DB_NAME)
    with con:
        con.execute("INSERT INTO asked_products (created, request_id, state, title, recipe, "
                    "reason) VALUES (?, ?, 'proposed', 'Broken', '{\"bad\": 1}', '')",
                    (NOW.isoformat(), rid))
        broken = int(con.execute("SELECT MAX(id) FROM asked_products").fetchone()[0])
    con.close()
    da.decide_product(tmp_path, broken, "approve", NOW)
    assert [p for p in _floor(tmp_path).products() if p.id.startswith("asked.")] == []
    assert _floor(tmp_path).rows("asked.999", {}) == []


def test_default_data_employee() -> None:
    """UT-MKT-011.008.M06.T01: emp-009 is an expert data employee and the skill loads."""
    spec = yaml.safe_load((EMP / "job.yaml").read_text(encoding="utf-8"))
    assert (spec["id"], spec["level"], spec["skill"], spec["trigger"], spec["calls_per_day"],
            spec["monthly_cost_usd"]) == ("emp-009", "expert", "data_recipe", "data_request",
                                          20, 3.0)
    module, _, cls = SKILL_PATHS["data_recipe"].partition(":")
    assert getattr(importlib.import_module(module), cls)().key == "data_recipe"


def test_no_real_names() -> None:
    """UT-MKT-011.008.M06.T02: generic name only, and market does not import desk."""
    assert yaml.safe_load((EMP / "job.yaml").read_text(encoding="utf-8"))["name"] == "Expert 7"
    assert "{name}" in (EMP / "soul.md").read_text(encoding="utf-8")
    src = Path(dr.__file__).read_text(encoding="utf-8")
    assert not re.search(r"^\s*(from|import) us_swing\.desk\b", src, re.M)


def test_logs(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-011.009.M04.T01: proposed and failed log lines carry the request numbers."""
    one = da.ask_data(tmp_path, "One", NOW)
    two = da.ask_data(tmp_path, "Two", NOW)
    skill = _skill()
    with caplog.at_level(logging.INFO, logger="us_swing.market.data_recipe"):
        skill.act(_Ctx(tmp_path, {"recipe": GOOD}), skill.facts(tmp_path))
        skill.act(_Ctx(tmp_path, None), skill.facts(tmp_path))
    assert f"[Data] Request {one} proposed: Tech longs" in caplog.text
    assert f"[Data] Request {two} failed:" in caplog.text
