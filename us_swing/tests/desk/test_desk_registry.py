"""Tests for MD-DSK-012.001.M28 — core/desk_registry.py (and its desk start call in M04)."""
from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from pydantic import ValidationError

from tests.desk.conftest import THU_1500_ET, FakeClock
from us_swing.core import desk_registry
from us_swing.core.desk_recipes import MENU
from us_swing.core.desk_registry import (
    SCHEMA_ID,
    TOOL_NAME,
    TOOL_REF,
    Column,
    TableFormat,
    Tool,
    fill_registry,
    get_format,
    get_tool,
    list_formats,
    list_tools,
    seed_formats,
    seed_tools,
)
from us_swing.core.desk_research import KINDS, TicketAsk
from us_swing.core.desk_steps import SKILL_PATHS, STEP_PATHS
from us_swing.desk.process import DeskProcess

NOW = THU_1500_ET
_SEED: list[Tool] = []


@pytest.fixture
def seeds() -> list[Tool]:
    if not _SEED:
        _SEED.extend(seed_tools())
    return _SEED


def _tool(**change: Any) -> Tool:
    data: dict[str, Any] = {"name": "step.regime", "kind": "code", "version": 1,
                            "description": "Market regime", "inputSchema": {"type": "object"}}
    return Tool.model_validate({**data, **change})


def _rows(home: Path, sql: str) -> list[tuple[Any, ...]]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def test_tool_in_mcp_shape() -> None:
    """UT-DSK-012.001.M28.T01: Tool row in MCP shape."""
    for tool in (_tool(), _tool(name="mcp:backtest/bt_run", kind="mcp", outputSchema="scores.v1")):
        out = tool.model_dump(by_alias=True)
        assert "inputSchema" in out and "outputSchema" in out
        assert Tool.model_validate_json(tool.model_dump_json(by_alias=True)) == tool


def test_kind_and_name_disagree() -> None:
    """UT-DSK-012.001.M28.T02: Kind and name disagree."""
    for change in ({"kind": "mcp"}, {"name": "mcp:a/b"}, {"status": "paused"}):
        with pytest.raises(ValidationError):
            _tool(**change)


def test_good_names() -> None:
    """UT-DSK-012.002.M28.T01: Good names."""
    assert re.match(TOOL_NAME, "step.regime")
    assert re.match(TOOL_NAME, "mcp:backtest/bt_run")
    assert re.match(TOOL_REF, "step.regime@1")


def test_bad_names() -> None:
    """UT-DSK-012.002.M28.T02: Bad names."""
    for name in ("Step.Regime", "regime", "mcp:backtest"):
        with pytest.raises(ValidationError):
            _tool(name=name)
    assert not re.match(TOOL_REF, "step.regime@x")


def test_format_row() -> None:
    """UT-DSK-012.003.M28.T01: Format row."""
    fmt = TableFormat(id="setup_table.v1", title="Setup table", columns=[
        Column(name="symbol", type="text", meaning="ticker"),
        Column(name="rs_rank", type="number", meaning="rs rank"),
        Column(name="atr_pct", type="number", meaning="atr in percent")])
    assert (fmt.name, fmt.version) == ("setup_table", 1)
    assert TableFormat.model_validate_json(fmt.model_dump_json()) == fmt


def test_bad_format() -> None:
    """UT-DSK-012.003.M28.T02: Bad format."""
    col = {"name": "symbol", "type": "text", "meaning": "ticker"}
    for data in ({"id": "setup_table", "title": "t", "columns": [col]},
                 {"id": "setup_table.v1", "title": "t", "columns": []},
                 {"id": "setup_table.v1", "title": "t", "columns": [col, col]}):
        with pytest.raises(ValidationError):
            TableFormat.model_validate(data)


def test_tables_made(home: Path) -> None:
    """UT-DSK-012.004.M28.T01: Tables made."""
    fill_registry(home, NOW)
    assert _rows(home, "SELECT COUNT(*) FROM tools")[0][0] > 0
    assert _rows(home, "SELECT COUNT(*) FROM schemas")[0][0] > 0
    keys = _rows(home, "SELECT name, pk FROM pragma_table_info('tools') WHERE pk > 0")
    assert sorted(keys, key=lambda r: r[1]) == [("name", 1), ("version", 2)]


def test_same_key_twice(home: Path) -> None:
    """UT-DSK-012.004.M28.T02: Same key twice."""
    fill_registry(home, NOW)
    con = sqlite3.connect(home / "desk.db")
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO tools VALUES ('step.regime', 1, 'code', 'active', '{}', '')")
    con.close()
    assert _rows(home, "SELECT COUNT(*) FROM tools WHERE name = 'step.regime'")[0][0] == 1


def test_tables_made_twice(home: Path) -> None:
    """UT-DSK-012.004.M28.T03: Tables made twice."""
    fill_registry(home, NOW)
    before = len(list_tools(home))
    desk_registry._connect(home).close()
    assert len(list_tools(home)) == before


def test_steps_seeded(seeds: list[Tool]) -> None:
    """UT-DSK-012.005.M28.T01: Steps seeded."""
    steps = [t for t in seeds if t.name.startswith("step.")]
    assert len(steps) == len(STEP_PATHS)
    names = {t.name: t for t in steps}
    assert names["step.candle_check"].description == "Candle check"
    assert "step.weekly_report" in names
    assert all(t.kind == "code" and not t.ai for t in steps)


def test_bad_step_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-DSK-012.005.M28.T02: Bad step path."""
    monkeypatch.setattr(desk_registry, "STEP_PATHS", ("us_swing.market.no_such:NoStep",))
    with pytest.raises(ModuleNotFoundError, match="no_such"):
        seed_tools()


def test_research_skills_seeded(seeds: list[Tool]) -> None:
    """UT-DSK-012.006.M28.T01: Research skills seeded."""
    research = {t.name: t for t in seeds if t.name.startswith("research.")}
    assert set(research) == {f"research.{k}" for k in SKILL_PATHS if k in KINDS}
    assert all(t.ai and t.input_schema == TicketAsk.model_json_schema()
               for t in research.values())


def test_kind_with_no_skill(seeds: list[Tool]) -> None:
    """UT-DSK-012.006.M28.T02: Kind with no skill."""
    assert "stock_study" in KINDS and "stock_study" not in SKILL_PATHS
    assert "research.stock_study" not in {t.name for t in seeds}


def test_recipe_and_formats_seeded(seeds: list[Tool]) -> None:
    """UT-DSK-012.007.M28.T01: Recipe and formats seeded."""
    recipe = next(t for t in seeds if t.name == "data.recipe")
    assert "source" in recipe.input_schema["properties"]
    formats = {f.id: f for f in seed_formats()}
    assert set(formats) == {f"{k}.v1" for k in MENU}
    for key, source in MENU.items():
        assert [c.name for c in formats[f"{key}.v1"].columns] == list(source.columns)


def test_recipe_input_refuses_unknown_source(seeds: list[Tool]) -> None:
    """UT-DSK-012.007.M28.T02: Recipe input refuses unknown source."""
    recipe = next(t for t in seeds if t.name == "data.recipe")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"source": "orders", "columns": ["x"]}, recipe.input_schema)


def test_backtest_mcp_seeded(seeds: list[Tool]) -> None:
    """UT-DSK-012.008.M28.T01: Backtest MCP seeded."""
    from us_swing.mcp.backtest_tools import TOOL_NAMES

    mcp = {t.name: t for t in seeds if t.kind == "mcp"}
    assert set(mcp) == {f"mcp:backtest/{n}" for n in TOOL_NAMES}
    assert mcp["mcp:backtest/bt_status"].input_schema["required"] == ["job_id"]


def test_mcp_input_refuses_missing_args(seeds: list[Tool]) -> None:
    """UT-DSK-012.008.M28.T02: MCP input refuses missing args."""
    status = next(t for t in seeds if t.name == "mcp:backtest/bt_status")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({}, status.input_schema)


def test_fill_twice_no_copies(home: Path) -> None:
    """UT-DSK-012.009.M28.T01: Fill twice, no copies."""
    first = fill_registry(home, NOW)
    rows = _rows(home, "SELECT name, version, kind, status, body FROM tools ORDER BY name")
    assert fill_registry(home, NOW) == first
    assert _rows(home, "SELECT name, version, kind, status, body FROM tools ORDER BY name") == rows
    assert len(rows) == first[0]


def test_removed_tool_set_off(home: Path) -> None:
    """UT-DSK-012.009.M28.T02: Removed tool set off."""
    fill_registry(home, NOW)
    old = _tool(name="step.old")
    con = sqlite3.connect(home / "desk.db")
    with con:
        con.execute("INSERT INTO tools VALUES (?, 1, 'code', 'active', ?, '')",
                    (old.name, old.model_dump_json(by_alias=True)))
    con.close()
    fill_registry(home, NOW)
    gone = get_tool(home, "step.old")
    assert gone is not None and gone.status == "off"


def test_desk_start_fills_registry(home: Path, clock: FakeClock, seeds: list[Tool]) -> None:
    """UT-DSK-001.010.M04.T32: Desk start fills the registry."""
    desk = DeskProcess(home, clock=clock, sleep=lambda _s: None)
    assert desk.start()
    desk.close()
    assert {t.name for t in list_tools(home)} == {t.name for t in seeds}


def test_registry_error_does_not_stop_desk(home: Path, clock: FakeClock,
                                           monkeypatch: pytest.MonkeyPatch,
                                           caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-001.010.M04.T33: Registry error does not stop the desk."""
    def broken(_home: Path, _now: object) -> tuple[int, int]:
        raise RuntimeError("bad seed")

    monkeypatch.setattr("us_swing.desk.process.fill_registry", broken)
    desk = DeskProcess(home, clock=clock, sleep=lambda _s: None)
    with caplog.at_level(logging.ERROR):
        assert desk.start()
    desk.close()
    assert any(r.getMessage().startswith("[Tools]") for r in caplog.records)


def test_read_functions(home: Path) -> None:
    """UT-DSK-012.010.M28.T01: Read functions."""
    fill_registry(home, NOW)
    con = sqlite3.connect(home / "desk.db")
    with con:
        for version in (1, 2):
            tool = _tool(name="x.y", version=version)
            con.execute("INSERT INTO tools VALUES ('x.y', ?, 'code', 'active', ?, '')",
                        (version, tool.model_dump_json(by_alias=True)))
    con.close()
    names = [(t.name, t.version) for t in list_tools(home)]
    assert names == sorted(names)
    newest = get_tool(home, "x.y")
    first = get_tool(home, "x.y", 1)
    assert newest is not None and newest.version == 2
    assert first is not None and first.version == 1
    scores = get_format(home, "scores.v1")
    assert scores is not None and scores.title == MENU["scores"].label
    assert [f.id for f in list_formats(home)] == sorted(f.id for f in list_formats(home))
    assert re.match(SCHEMA_ID, "scores.v1")


def test_no_database_yet(home: Path) -> None:
    """UT-DSK-012.010.M28.T02: No database yet."""
    assert list_tools(home) == [] and list_formats(home) == []
    assert get_tool(home, "step.regime") is None and get_format(home, "scores.v1") is None
    assert not (home / "desk.db").exists()
    fill_registry(home, NOW)
    assert get_tool(home, "step.nothing") is None and get_format(home, "nothing") is None


def test_fill_is_logged(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-012.011.M28.T01: Fill is logged."""
    with caplog.at_level(logging.INFO, logger="us_swing.core.desk_registry"):
        tools, formats = fill_registry(home, NOW)
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("[Tools]")]
    assert lines == [f"[Tools] Registry ready: {tools} tool(s), {formats} table format(s)"]
