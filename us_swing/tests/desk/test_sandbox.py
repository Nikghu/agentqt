"""Tests for MD-DSK-013.010.M38 (desk/sandbox.py) and MD-DSK-013.011.M39
(desk/sandbox_child.py): tool code runs in a real child process with a time limit, a memory
cap, safe names only, and JSON back (AI Desk v3 M7b).

Stock names here are made up.
"""
from __future__ import annotations

import json
import logging
import multiprocessing
import os
import sys
import time
from pathlib import Path

import pytest

from tests.desk import builder_support as bs
from us_swing.core.desk_built_tools import ALLOWED_BUILTINS, CHANGED, ToolColumn, enable_tool
from us_swing.desk import sandbox
from us_swing.desk.sandbox import BROKEN, TOO_MUCH, built_fns, run_code
from us_swing.desk.sandbox_child import CUT, NO_MEMORY, NO_ROW, WRONG, child_env, run_tool

LENGTH = [ToolColumn(name="length", type="number", meaning="letters in the name")]
LENGTH_CODE = "def tool(symbol):\n    return {'length': len(symbol)}\n"


def test_child_run(tmp_path: Path) -> None:
    """UT-DSK-013.010.M38.T01: The code runs in another process and gives one row per stock."""
    result = run_code(tmp_path, LENGTH_CODE, LENGTH, ["ZZA", "ZZBB"], secs=60)
    assert result.error == ""
    assert list(result.rows) == [{"symbol": "ZZA", "length": 3}, {"symbol": "ZZBB", "length": 4}]
    assert result.pid not in (0, os.getpid())


def test_time_limit(tmp_path: Path) -> None:
    """UT-DSK-013.010.M38.T02: A tool that loops for ever is stopped at its limit, and the
    child is gone."""
    code = "def tool(symbol):\n    while True:\n        pass\n"
    result = run_code(tmp_path, code, LENGTH, ["ZZA"], secs=3)
    assert result.error == "took longer than 3 s" and result.rows == ()
    assert multiprocessing.active_children() == []


@pytest.mark.skipif(sys.platform != "win32", reason="the memory cap is a Windows job object")
def test_memory_cap(tmp_path: Path) -> None:
    """UT-DSK-013.010.M38.T03: A list of 100 million items passes the 512 MB cap: the stock gets
    "the tool ran out of memory" and the run still ends."""
    code = "def tool(symbol):\n    items = [0] * 100000000\n    return {'length': len(items)}\n"
    result = run_code(tmp_path, code, LENGTH, ["ZZA"], secs=60)
    assert result.error == ""
    assert result.missing == {"ZZA": NO_MEMORY} and result.crashed == ("ZZA",)


@pytest.mark.parametrize(("target", "why"), [
    (bs.child_big, TOO_MUCH),
    (bs.child_silent, "the tool process ended without an answer"),
    (bs.child_pickle, BROKEN),
])
def test_bad_child_answers(tmp_path: Path, target: sandbox.Target, why: str) -> None:
    """UT-DSK-013.010.M38.T04: Too much output, no answer and a pickled answer each end the run
    with a reason; nothing is unpickled."""
    result = run_code(tmp_path, LENGTH_CODE, LENGTH, ["ZZA"], secs=60, target=target)
    assert result.error.startswith(why) and result.rows == ()


def test_safe_names(tmp_path: Path) -> None:
    """UT-DSK-013.011.M39.T01: len, sorted, math.sqrt, mean and daily_bars work in the child."""
    bs.daily_file(tmp_path / "bt", "ZZA", 60)
    code = ("def tool(symbol):\n"
            "    closes = [b['close'] for b in daily_bars(symbol, 10)]\n"
            "    top = sorted(closes)[-1]\n"
            "    return {'top': top, 'root': round(math.sqrt(16), 1), 'avg': mean(closes),\n"
            "            'days': len(closes)}\n")
    cols = [ToolColumn(name=n, type="number", meaning=n) for n in ("top", "root", "avg", "days")]
    result = run_code(tmp_path, code, cols, ["ZZA"], secs=60, backtest=tmp_path / "bt")
    assert result.error == ""
    assert list(result.rows) == [{"symbol": "ZZA", "top": 159.5, "root": 4.0, "avg": 155.0,
                                  "days": 10}]


def test_rules_again_in_the_child(tmp_path: Path) -> None:
    """UT-DSK-013.011.M39.T02: Code that breaks the rules is refused by the child before it
    runs."""
    code = "import os\n" + LENGTH_CODE
    result = run_code(tmp_path, code, LENGTH, ["ZZA"], secs=60)
    assert result.error == "code rules: line 1: import is not allowed"


def test_only_listed_builtins() -> None:
    """UT-DSK-013.011.M39.T03: The code's built-ins are only the listed names."""
    env = child_env({"daily_bars": len})
    names = set(env["__builtins__"])
    assert names == set(ALLOWED_BUILTINS)
    assert not names & {"open", "__import__", "getattr", "eval", "exec", "compile", "type"}
    assert set(env) == {"__builtins__", "math", "mean", "median", "stdev", "pstdev", "fmean",
                        "daily_bars"}


def _tool(symbol: str) -> object:
    if symbol == "ZZA":
        raise ValueError("fewer than 252 bars")
    return {"n": 1.5, "t": "up"}


COLS = [{"name": "n", "type": "number"}, {"name": "t", "type": "text"}]


def test_rows_and_reasons() -> None:
    """UT-DSK-013.012.M39.T01: A ValueError gives that stock its reason; the other stock gets
    its row."""
    out = run_tool(_tool, ["ZZA", "ZZB"], COLS)
    assert out["rows"] == [{"symbol": "ZZB", "n": 1.5, "t": "up"}]
    assert out["missing"] == {"ZZA": "fewer than 252 bars"} and out["crashed"] == []


def _bad(symbol: str) -> object:
    values: dict[str, object] = {
        "ZS2": {"n": [1], "t": "ok"}, "ZS3": {"n": float("nan"), "t": "ok"},
        "ZS4": {"n": 1, "t": "x" * 300}}
    if symbol == "ZS1":
        return [][1]
    return values.get(symbol, "not a dict")


def test_errors_and_wrong_values() -> None:
    """UT-DSK-013.012.M39.T02: An IndexError, a list for a number, NaN, a long text and a
    non-dict each give a reason, and the run still ends."""
    out = run_tool(_bad, ["ZS1", "ZS2", "ZS3", "ZS4", "ZS5"], COLS)
    missing = out["missing"]
    assert missing["ZS1"].startswith("error: IndexError")
    assert (missing["ZS2.n"], missing["ZS3.n"], missing["ZS4.t"]) == (WRONG, WRONG, WRONG)
    assert missing["ZS5"] == NO_ROW
    assert out["crashed"] == ["ZS1", "ZS5"]
    assert out["wrong"] == ["ZS2.n", "ZS3.n", "ZS4.t"]
    assert [r["symbol"] for r in out["rows"]] == ["ZS2", "ZS3", "ZS4"]


def test_changed_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-DSK-013.013.M38.T01: An enabled tool whose file was edited does not run, and no child
    starts."""
    tool = bs.version(tmp_path)
    assert enable_tool(tmp_path, tool.id, bs.NOW) == ""
    (tmp_path / tool.file).write_text(bs.GOOD_CODE + "# edited\n", encoding="utf-8")
    started: list[str] = []
    monkeypatch.setattr(sandbox, "run_code", lambda *a, **k: started.append("run"))
    result = built_fns(tmp_path)[tool.tool_name](tmp_path, ["ZZA"])
    assert (result.is_error, result.error) == (True, CHANGED) and started == []


def test_unchanged_file(tmp_path: Path) -> None:
    """UT-DSK-013.013.M38.T02: The same tool with its file as saved runs in the child."""
    bs.daily_file(tmp_path / "bt", "ZZA", 60)
    tool = bs.version(tmp_path)
    assert enable_tool(tmp_path, tool.id, bs.NOW) == ""
    result = built_fns(tmp_path, tmp_path / "bt")[tool.tool_name](tmp_path, ["ZZA", "ZZB"])
    assert result.is_error is False
    assert result.rows == [{"symbol": "ZZA", "below_high": 0.31}]
    assert result.missing == {"ZZB": "fewer than 20 daily bars"}


# ── code review fixes (2026-11-16) ──────────────────────────────────────────


def test_huge_number(tmp_path: Path) -> None:
    """UT-DSK-013.012.M39.T03: A huge int is a wrong value for its stock only; the other stock
    keeps its row."""
    def tool(symbol: str) -> object:
        return {"n": 10**400 if symbol == "ZS1" else 2.0, "t": "ok"}

    out = run_tool(tool, ["ZS1", "ZS2"], COLS)
    assert out["missing"]["ZS1.n"] == WRONG and out["wrong"] == ["ZS1.n"]
    assert out["rows"] == [{"symbol": "ZS1", "t": "ok"}, {"symbol": "ZS2", "n": 2.0, "t": "ok"}]


def test_rows_up_to_the_deadline() -> None:
    """UT-DSK-013.010.M39.T01: After the deadline no new stock starts; the rows made so far are
    kept and the rest are cut with the reason."""
    def slow(symbol: str) -> object:
        time.sleep(0.3)
        return {"n": 1.0, "t": "x"}

    symbols = ["ZS1", "ZS2", "ZS3", "ZS4", "ZS5"]
    out = run_tool(slow, symbols, COLS, deadline=time.monotonic() + 0.45)
    done = [r["symbol"] for r in out["rows"]]
    assert done and out["cut"] and done + out["cut"] == symbols
    assert all(out["missing"][s] == CUT for s in out["cut"])


class _Proc:
    exitcode = 1

    def join(self, _timeout: float | None = None) -> None:
        return None


class _Pipe:
    def __init__(self, error: BaseException) -> None:
        self.error = error

    def poll(self, timeout: float | None = None) -> bool:
        return True

    def recv_bytes(self, maxlength: int | None = None) -> bytes:
        raise self.error

    def close(self) -> None:
        return None


def test_pipe_errors() -> None:
    """UT-DSK-013.010.M38.T05: A broken pipe ends the run as a process with no answer; only a
    too long message is "too much output"."""
    proc = _Proc()
    reset = sandbox._answer(_Pipe(ConnectionResetError("reset")), proc, 5, 0.0)  # type: ignore[arg-type]
    assert reset.error == "the tool process ended without an answer (exit code 1)"
    long = sandbox._answer(_Pipe(OSError("bad message length")), proc, 5, 0.0)  # type: ignore[arg-type]
    assert long.error == TOO_MUCH


def test_no_memory_cap_logged(caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-013.010.M38.T06: An answer from a child that could not cap its memory is kept and
    logged."""
    data = json.dumps({"rows": [], "missing": {}, "capped": False}).encode()
    with caplog.at_level(logging.WARNING):
        result = sandbox._parse(data, 1.0)
    assert result.error == "" and result.capped is False
    assert "[Tool builder] A tool ran without a memory cap" in caplog.text
