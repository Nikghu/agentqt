"""Tests for MD-DSK-012.021.M33 (desk/champions.py): tool groups, waves, retry, time limit."""
from __future__ import annotations

import threading
import time
from collections.abc import Sequence
from pathlib import Path

import pytest

from us_swing.core.desk_registry import ToolResult
from us_swing.core.desk_tasks import PlanPart
from us_swing.desk.champions import run_part, run_wave

_HERE = "tests.desk.test_champions"
CALLS: list[str] = []
LEFT = {"flaky": 0, "broken": 0}
GATE = threading.Barrier(2)
LOCK = threading.Lock()
RUNNING = {"now": 0, "most": 0}


@pytest.fixture(autouse=True)
def _reset() -> None:
    CALLS.clear()
    LEFT.update(flaky=0, broken=0)
    RUNNING.update(now=0, most=0)
    GATE.reset()


def two_columns(home: Path, keys: Sequence[str]) -> ToolResult:
    CALLS.append("two")
    return ToolResult(rows=[{"symbol": k, "a": 1, "b": 2} for k in keys] + [
        {"symbol": "OTHER", "a": 9, "b": 9}], flags={"OTHER": "not asked"})


def other(home: Path, keys: Sequence[str]) -> ToolResult:
    CALLS.append("other")
    return ToolResult()


def meets_partner(home: Path, keys: Sequence[str]) -> ToolResult:
    GATE.wait(timeout=5)
    return ToolResult(rows=[{"symbol": k, "a": 1} for k in keys])


def counted(home: Path, keys: Sequence[str]) -> ToolResult:
    with LOCK:
        RUNNING["now"] += 1
        RUNNING["most"] = max(RUNNING["most"], RUNNING["now"])
    time.sleep(0.05)
    with LOCK:
        RUNNING["now"] -= 1
    return ToolResult(rows=[{"symbol": k, "a": 1} for k in keys])


def flaky(home: Path, keys: Sequence[str]) -> ToolResult:
    CALLS.append("flaky")
    if LEFT["flaky"]:
        LEFT["flaky"] -= 1
        raise RuntimeError("boom")
    return ToolResult(rows=[{"symbol": k, "a": 1} for k in keys])


def slow(home: Path, keys: Sequence[str]) -> ToolResult:
    time.sleep(1.5)
    return ToolResult()


def error_result(home: Path, keys: Sequence[str]) -> ToolResult:
    CALLS.append("error")
    return ToolResult(isError=True, error="feed is down")


PATHS = {f"technical.{name}": f"{_HERE}:{name}"
         for name in ("two_columns", "other", "meets_partner", "counted", "flaky", "slow",
                      "error_result")}


def _part(tool: str, cols: list[str], part_id: str = "B") -> PlanPart:
    return PlanPart(id=part_id, wave=2, group="technical", tools={f"technical.{tool}": cols})


def test_part_runs_only_its_tools_and_columns(tmp_path: Path) -> None:
    """UT-DSK-012.021.M33.T01: Part runs only its tools and columns."""
    result = run_part(tmp_path, _part("two_columns", ["a"]), ["X", "Y"], PATHS, "symbol")
    assert result.status == "ok" and result.reason == ""
    assert result.rows == {"X": {"a": 1}, "Y": {"a": 1}}
    assert result.flags == {} and CALLS == ["two"]


def test_tool_with_no_code(tmp_path: Path) -> None:
    """UT-DSK-012.021.M33.T02: Tool with no code."""
    for tool in ("none", "gone"):
        paths = {**PATHS, "technical.gone": f"{_HERE}:not_there"}
        result = run_part(tmp_path, _part(tool, ["a"]), ["X"], paths, "symbol")
        assert result.status == "failed" and result.reason == f"no code for technical.{tool}"


def test_parts_run_together(tmp_path: Path) -> None:
    """UT-DSK-012.022.M33.T01: Parts run together."""
    parts = [_part("meets_partner", ["a"], "B"), _part("meets_partner", ["a"], "C")]
    results = run_wave(tmp_path, parts, ["X"], PATHS, {}, "symbol")
    assert [(r.id, r.status) for r in results] == [("B", "ok"), ("C", "ok")]


def test_at_most_four_at_once(tmp_path: Path) -> None:
    """UT-DSK-012.022.M33.T02: At most 4 at once."""
    parts = [_part("counted", ["a"], f"P{n}") for n in range(6)]
    results = run_wave(tmp_path, parts, ["X"], PATHS, {}, "symbol")
    assert [r.status for r in results] == ["ok"] * 6
    assert 2 <= RUNNING["most"] <= 4
    assert run_wave(tmp_path, [], ["X"], PATHS, {}, "symbol") == []


def test_one_retry(tmp_path: Path) -> None:
    """UT-DSK-012.023.M33.T01: One retry."""
    LEFT["flaky"] = 1
    result = run_part(tmp_path, _part("flaky", ["a"]), ["X"], PATHS, "symbol")
    assert result.status == "ok" and result.rows == {"X": {"a": 1}}
    assert CALLS == ["flaky", "flaky"]


def test_fails_twice(tmp_path: Path) -> None:
    """UT-DSK-012.023.M33.T02: Fails twice."""
    LEFT["flaky"] = 2
    result = run_part(tmp_path, _part("flaky", ["a"]), ["X"], PATHS, "symbol")
    assert result.status == "failed" and result.reason == "boom" and result.rows == {}
    assert CALLS == ["flaky", "flaky"]


def test_time_limit(tmp_path: Path) -> None:
    """UT-DSK-012.023.M33.T03: Time limit."""
    started = time.monotonic()
    results = run_wave(tmp_path, [_part("slow", ["a"])], ["X"], PATHS, {"technical.slow": 1},
                       "symbol")
    assert time.monotonic() - started < 1.4
    assert results[0].status == "failed" and results[0].reason == "took longer than 1 s"


def reason_a(home: Path, keys: Sequence[str]) -> ToolResult:
    return ToolResult(missing=dict.fromkeys(keys, "fewer than 15 daily bars"))


def reason_b(home: Path, keys: Sequence[str]) -> ToolResult:
    return ToolResult(missing={"X.c": "no setup", **dict.fromkeys(keys, "not scored")})


def test_each_tool_keeps_its_reasons(tmp_path: Path) -> None:
    """UT-DSK-012.021.M33.T03: Each tool keeps its reasons."""
    part = PlanPart(id="C", wave=2, group="technical",
                    tools={"technical.reason_a": ["a"], "technical.reason_b": ["b", "c"]})
    paths = {f"technical.{n}": f"{_HERE}:{n}" for n in ("reason_a", "reason_b")}
    result = run_part(tmp_path, part, ["X", "Y"], paths, "symbol")
    assert result.status == "ok" and result.rows == {}
    assert result.missing == {
        "X.a": "fewer than 15 daily bars", "Y.a": "fewer than 15 daily bars",
        "X.b": "not scored", "X.c": "no setup", "Y.b": "not scored", "Y.c": "not scored"}


def test_error_result(tmp_path: Path) -> None:
    """UT-DSK-012.023.M33.T04: Error result."""
    result = run_part(tmp_path, _part("error_result", ["a"]), ["X"], PATHS, "symbol")
    assert result.status == "failed" and result.reason == "feed is down"
    assert CALLS == ["error"]
