"""Tests for the tool builder through the desk (AI Desk v3 M7b): tool groups and the planner
running a built tool in the sandbox, the switch off through a real message wake, and the
default builder employee.

Stock and employee names here are made up.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

import us_swing
from tests.desk import builder_support as bs
from tests.desk import task_support as ts
from us_swing.core.desk_ai_settings import load_settings, save_settings
from us_swing.core.desk_built_tools import CHANGED, ToolColumn, enable_tool, tool_requests
from us_swing.core.desk_contract import StepContext
from us_swing.core.desk_employee import read_employee
from us_swing.core.desk_registry import ToolResult
from us_swing.core.desk_steps import DEFAULT_EMPLOYEE_PACKAGES, SKILL_PATHS, TOOL_READS_PATH
from us_swing.core.desk_tasks import PlanPart, card_rows
from us_swing.desk import sandbox
from us_swing.desk.champions import run_part
from us_swing.desk.employees_step import EmployeesStep
from us_swing.desk.gateway import Reply
from us_swing.desk.registry import default_folders, load_skill, seed_employees
from us_swing.desk.tool_builder import ToolBuilderSkill

LENGTH = [ToolColumn(name="length", type="number", meaning="letters in the name")]
LENGTH_CODE = "def tool(symbol):\n    return {'length': len(symbol)}\n"
FORMAT = "length_tool.v1"
CALLS: list[str] = []


def _caller(source: str, model: str, system: str, user: str, key: str) -> Reply:
    CALLS.append(system)
    return Reply(json.dumps({}), 10, 10, 0.0)


def _length_tool(home: Path) -> int:
    tool = bs.version(home, name="length_tool", code=LENGTH_CODE, columns=LENGTH)
    assert enable_tool(home, tool.id, bs.NOW) == ""
    return tool.id


# ── tool groups and the planner (SRD-DSK-013.020, .021) ─────────────────────


def _close(home: Path, symbols: list[str]) -> ToolResult:
    return ToolResult(rows=[{"symbol": s, "close": 10.0} for s in symbols])


def test_function_tools(tmp_path: Path) -> None:
    """UT-DSK-013.020.M33.T01: A part with one tool given as a function and one as a path fills
    both tools' columns."""
    part = PlanPart(id="A", wave=1, group="data",
                    tools={"data.fn": ["symbol", "close"], "data.path": ["rs_rank"]})
    paths: dict[str, Any] = {"data.fn": _close,
                             "data.path": "tests.desk.task_support:fake_rs"}
    ts.W = ts.World()
    result = run_part(tmp_path, part, ["ZZA", "ZZB"], paths, "symbol")
    assert result.status == "ok"
    assert result.rows == {"ZZA": {"close": 10.0, "rs_rank": 80},
                           "ZZB": {"close": 10.0, "rs_rank": 81}}


def test_planner_runs_built_tool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-DSK-013.020.M34.T01: A table ask for an enabled built tool's format gets a done reply
    with a row per stock; the card's part is the built tool group."""
    ts.prepare(tmp_path, monkeypatch)
    save_settings(replace(ts.SETTINGS, tool_builder_on=True), tmp_path)
    _length_tool(tmp_path)
    reply = ts.answer(tmp_path, symbols=["ZZA", "ZZBB"], schema=FORMAT)
    assert reply.verdict is not None and reply.verdict.result == "done"
    assert reply.data is not None and reply.data.rows == [["ZZA", 3], ["ZZBB", 4]]
    (card,) = card_rows(tmp_path)
    assert card.status == "done" and [p.group for p in card.parts] == ["built"]


def test_run_error_fails_its_part(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-DSK-013.020.M34.T02: A built tool whose file changed after Enable fails its part with
    the reason, the reply is failed, and the tool is called once."""
    ts.prepare(tmp_path, monkeypatch)
    tid = _length_tool(tmp_path)
    tool_file = tmp_path / "tools" / "length_tool" / "v1.py"
    tool_file.write_text(LENGTH_CODE + "# edited\n", encoding="utf-8")
    seen: list[int] = []
    real = sandbox.checked_code

    def counted(home: Path, tool: Any) -> str | None:
        seen.append(tool.id)
        return real(home, tool)

    monkeypatch.setattr(sandbox, "checked_code", counted)
    reply = ts.answer(tmp_path, symbols=["ZZA"], schema=FORMAT)
    assert reply.verdict is not None and reply.verdict.result == "failed"
    assert reply.verdict.reason == f"Built tools failed: {CHANGED}"
    assert seen == [tid]


def test_enabled_tools_keep_working(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-DSK-013.021.M34.T01: With the tool builder off, an enabled tool still fills a table."""
    ts.prepare(tmp_path, monkeypatch)
    _length_tool(tmp_path)
    assert load_settings(tmp_path).tool_builder_on is False
    reply = ts.answer(tmp_path, symbols=["ZZA"], schema=FORMAT)
    assert reply.data is not None and reply.data.rows == [["ZZA", 3]]


# ── the switch off through a real message wake (SRD-DSK-013.021) ────────────


class Builder(ToolBuilderSkill):
    """The real builder with the test clock."""

    def __init__(self) -> None:
        super().__init__(clock=lambda: bs.NOW)


def test_builder_off(tmp_path: Path) -> None:
    """UT-DSK-013.021.M40.T01: With the tool builder off, an ask gets a refused reply naming the
    switch; no request is saved and no model is asked."""
    CALLS.clear()
    bs.on(tmp_path, tool_builder_on=False)
    bs.team(tmp_path)
    ask_id = bs.ask(tmp_path, {"request": "Percent below the 52-week high"})
    skills = {"lead_chat": "us_swing.market.lead_chat:LeadChatSkill",
              "tool_builder": "tests.desk.test_tool_builder_flow:Builder"}
    step = EmployeesStep(lambda: skills, lambda: [], lambda: load_settings(tmp_path),
                         lambda: "key", _caller, lambda: bs.NOW)
    step.handle_events(StepContext(1, "manual", bs.NOW, tmp_path))
    rows = bs.rows(tmp_path, "SELECT type, parent, body FROM messages ORDER BY id")
    reply = next(r for r in rows if r[0] == "reply" and r[1] == ask_id)
    verdict = json.loads(reply[2])["verdict"]
    assert verdict["result"] == "refused" and "the tool builder is off" in verdict["reason"]
    assert tool_requests(tmp_path) == [] and CALLS == []


# ── default builder (SRD-DSK-013.022) ───────────────────────────────────────


def _shipped() -> Path:
    return next(f for f in default_folders(DEFAULT_EMPLOYEE_PACKAGES) if f.name == "emp-021")


def test_default_builder() -> None:
    """UT-DSK-013.022.M07.T01: The shipped builder holds tool_builder at champion level, reports
    to the planner and wakes on tool requests and messages; its skill, the read functions and
    the app build list are set."""
    found = read_employee(_shipped())
    assert found is not None
    s = found.spec
    assert (s.title, s.level, s.skill, s.reports_to, s.status) == (
        "Tool builder", "champion", "tool_builder", "emp-019", "active")
    assert tuple(s.trigger) == ("tool_request", "message")
    assert s.name.startswith("Champion ") and "{name}" in found.prompt
    assert isinstance(load_skill("tool_builder", SKILL_PATHS), ToolBuilderSkill)
    assert TOOL_READS_PATH == "us_swing.market.tool_reads:reads"
    spec = (Path(us_swing.__file__).parents[2] / "USSwing.spec").read_text(encoding="utf-8")
    for module in ("us_swing.desk.tool_builder", "us_swing.desk.sandbox",
                   "us_swing.desk.sandbox_child", "us_swing.market.tool_reads"):
        assert f"'{module}'" in spec


def test_builder_added_once(tmp_path: Path) -> None:
    """UT-DSK-013.022.M07.T02: A desk without emp-021 gets it at the first seeding and nothing
    at the second; a renamed copy is kept."""
    shipped = [_shipped()]
    assert seed_employees(tmp_path, shipped) == 1
    assert seed_employees(tmp_path, shipped) == 0
    found = read_employee(shipped[0])
    assert found is not None
    file = tmp_path / "employees" / "emp-021" / "employee.md"
    text = file.read_text(encoding="utf-8")
    file.write_text(text.replace(f"name: {found.spec.name}", "name: Smith Tool"),
                    encoding="utf-8")
    seed_employees(tmp_path, shipped)
    kept = read_employee(tmp_path / "employees" / "emp-021")
    assert kept is not None and kept.spec.name == "Smith Tool"

