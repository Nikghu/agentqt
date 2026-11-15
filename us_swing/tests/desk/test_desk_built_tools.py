"""Tests for MD-DSK-013.001.M37 — core/desk_built_tools.py (AI Desk v3 M7b): tool requests,
the answer and code rules, versions, sample stocks, Enable and Disable, and reads; plus the M7b
parts of the registry (M28), the plans (M32) and the settings (M13).

Stock and employee names here are made up.
"""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.desk import builder_support as bs
from us_swing.core.desk_ai_settings import DeskAiSettings, load_settings, save_settings
from us_swing.core.desk_built_tools import (
    CHANGED,
    DISABLED,
    ENABLED,
    FAILED,
    OFF,
    REVIEW,
    TOO_DEEP,
    ToolAnswer,
    ask_tool,
    built_tool_rows,
    check_answer,
    check_code,
    code_of,
    disable_tool,
    enable_tool,
    get_built,
    sample_symbols,
    save_version,
    tool_requests,
)
from us_swing.core.desk_registry import (
    Tool,
    fill_registry,
    get_format,
    get_tool,
    list_tools,
    save_tool,
)
from us_swing.core.desk_tasks import RETIRED, fill_plans, get_plan, note_result

NOW = bs.NOW


def _events(home: Path) -> list[tuple[str, ...]]:
    return bs.rows(home, "SELECT kind, key FROM events WHERE kind = 'tool_request'")


# ── requests (SRD-DSK-013.001) ──────────────────────────────────────────────


def test_save_request(tmp_path: Path) -> None:
    """UT-DSK-013.001.M37.T01: A typed request is one new row from the Master user, and one
    tool_request event is posted for it."""
    bs.on(tmp_path)
    rid = ask_tool(tmp_path, "  Percent below the 52-week high ", NOW)
    (req,) = tool_requests(tmp_path)
    assert (req.id, req.source, req.asker, req.text, req.state, req.message) == (
        rid, "tools", "master", "Percent below the 52-week high", "new", None)
    assert _events(tmp_path) == [("tool_request", f"tool_request|{bs.DAY}|{rid}")]


@pytest.mark.parametrize(("text", "on", "why"), [
    ("   ", True, "a request needs 1 to 300 characters"),
    ("x" * 301, True, "a request needs 1 to 300 characters"),
    ("Percent below the 52-week high", False, OFF),
])
def test_request_refused(tmp_path: Path, text: str, on: bool, why: str) -> None:
    """UT-DSK-013.001.M37.T02: An empty or long text, or the tool builder off, is refused with
    the reason; no row and no event."""
    bs.on(tmp_path, tool_builder_on=on)
    with pytest.raises(ValueError, match=why):
        ask_tool(tmp_path, text, NOW)
    assert tool_requests(tmp_path) == []
    assert not (tmp_path / "desk.db").exists() or _events(tmp_path) == []


# ── answer model and checks (SRD-DSK-013.005, .006) ─────────────────────────


def test_answer_model() -> None:
    """UT-DSK-013.005.M37.T01: A JSON answer with name, title, about, 2 columns and code."""
    found = ToolAnswer.model_validate_json(
        '{"name": "gap_pct", "title": "Gap", "about": "Open against the last close.", '
        '"columns": [{"name": "gap", "type": "number", "meaning": "gap in percent"}, '
        '{"name": "side", "type": "text", "meaning": "up or down"}], '
        '"code": "def tool(symbol):\\n    return {}\\n"}')
    assert [c.name for c in found.columns] == ["gap", "side"] and found.refuse == ""


@pytest.mark.parametrize("change", [
    {"columns": [{"name": f"c{n}", "type": "number", "meaning": "m"} for n in range(6)]},
    {"code": "x" * 6001},
    {"columns": [{"name": "day", "type": "date", "meaning": "m"}]},
    {"author": "someone"},
])
def test_answer_limits(change: dict[str, object]) -> None:
    """UT-DSK-013.005.M37.T02: 6 columns, 6001 characters of code, a column of type date or an
    extra key fail validation."""
    with pytest.raises(ValidationError):
        ToolAnswer.model_validate({"name": "gap_pct", "title": "Gap", "about": "a", **change})


def test_good_answer(tmp_path: Path) -> None:
    """UT-DSK-013.006.M37.T01: A new name and the name of a built tool both pass; the second
    save of a name is version 2."""
    assert check_answer(tmp_path, bs.answer()) == []
    first = save_version(tmp_path, None, bs.answer(), NOW)
    assert check_answer(tmp_path, bs.answer()) == []
    second = save_version(tmp_path, None, bs.answer(), NOW)
    assert (first.version, second.version) == (1, 2)


@pytest.mark.parametrize(("change", "why"), [
    ({"name": "setup_table"}, "the name setup_table is taken by a table format"),
    ({"name": "x"}, "the tool name must be lower_case, 3 to 30 characters"),
    ({"title": " "}, "the title is empty"),
    ({"columns": [bs.COLUMNS[0].model_copy(update={"name": "symbol"})]},
     "the desk adds the symbol column itself; name your columns otherwise"),
    ({"columns": [bs.COLUMNS[0], bs.COLUMNS[0]]}, "each column name may be used once"),
])
def test_bad_answer(tmp_path: Path, change: dict[str, object], why: str) -> None:
    """UT-DSK-013.006.M37.T02: A taken or bad name, an empty title, a column named symbol or the
    same column twice give one problem each."""
    data = {**bs.answer().model_dump(), **change}
    assert check_answer(tmp_path, ToolAnswer.model_validate(data)) == [why]


# ── code rules (SRD-DSK-013.007) ────────────────────────────────────────────

GOOD = '''"""A tool with every allowed kind of statement."""
LIMIT = 20
NAMES = ("a", "b")


def last_close(bars):
    return bars[-1]["close"]


def tool(symbol):
    bars = daily_bars(symbol, 60)
    rows = desk_rows("stock_rs", symbol, 2)
    if len(bars) < LIMIT:
        raise ValueError("too few bars")
    closes = [b["close"] for b in bars]
    total = 0.0
    for value in closes:
        total += value
    try:
        spread = math.sqrt(abs(closes[-1] - mean(closes)))
    except ValueError as exc:
        raise ValueError("no spread") from exc
    seen = {}
    seen.setdefault("n", len(rows))
    while total > 1e9:
        total = total / 2
    best = sorted(closes, key=lambda c: -c)[:3]
    return {"close": last_close(bars), "spread": round(spread, 2), "top": sum(best),
            "name": symbol.lower().strip()}
'''


def test_good_code() -> None:
    """UT-DSK-013.007.M37.T01: Helpers, constants, loops, a comprehension, try and except, math,
    mean and the read functions pass."""
    assert check_code(GOOD) == []
    assert check_code(bs.GOOD_CODE) == []


def _tool(body: str) -> str:
    return f"def tool(symbol):\n{body}\n    return {{}}\n"


@pytest.mark.parametrize(("code", "why"), [
    ("import os\n" + _tool("    pass"), "line 1: import is not allowed"),
    ("from math import sqrt\n" + _tool("    pass"), "line 1: import is not allowed"),
    (_tool("    class A:\n        pass"), "line 2: class is not allowed"),
    (_tool("    with x as y:\n        pass"), "line 2: with is not allowed"),
    (_tool("    yield 1"), "line 2: yield is not allowed"),
    (_tool("    global LIMIT"), "line 2: global is not allowed"),
    ("def deco(f):\n    return f\n\n@deco\n" + _tool("    pass"),
     "line 5: decorators are not allowed"),
    ("async def helper():\n    pass\n" + _tool("    pass"), "line 1: async def is not allowed"),
    (_tool("    match symbol:\n        case str():\n            pass"),
     "line 2: match is not allowed"),
])
def test_banned_statements(code: str, why: str) -> None:
    """UT-DSK-013.007.M37.T02: import, from-import, class, with, yield, global, a decorator,
    async def and match each give a problem with its line."""
    assert why in check_code(code)


@pytest.mark.parametrize(("body", "why"), [
    ("    open('x')", "line 2: unknown name open"),
    ("    __import__('os')", "line 2: the name __import__ starts with _"),
    ("    symbol.__class__", "line 2: the attribute __class__ is not allowed"),
    ("    g = (b for b in [1])\n    g.gi_frame", "line 3: the attribute gi_frame is not allowed"),
    ("    x = 'a__b'", "line 2: a text with __ in it is not allowed"),
    ("    eval('1')", "line 2: unknown name eval"),
    ("    getattr(symbol, 'upper')", "line 2: unknown name getattr"),
    ("    foo()", "line 2: unknown name foo"),
    ("    'x{0}'.format(symbol)", "line 2: the attribute format is not allowed"),
])
def test_banned_names(body: str, why: str) -> None:
    """UT-DSK-013.007.M37.T03: open, __import__, __class__, gi_frame, a text with __, eval,
    getattr, an unknown name and str.format each give a problem."""
    assert why in check_code(_tool(body))


@pytest.mark.parametrize(("code", "why"), [
    ("def helper(symbol):\n    return {}\n", "line 1: the code has no def tool(symbol)"),
    ("def tool(a, b):\n    return {}\n", "line 1: tool must take one parameter, symbol, with "
                                          "no default"),
    ("def tool(symbol=1):\n    return {}\n", "line 1: tool must take one parameter, symbol, "
                                             "with no default"),
    ("X = len('ab')\n" + _tool("    pass"), "line 1: only def statements and constants may "
                                             "stand at the top"),
    ("#" * 6001, "line 1: the code is longer than 6000 characters"),
    ("def tool(symbol)\n    return {}\n", "line 1: expected ':'"),
])
def test_code_shape(code: str, why: str) -> None:
    """UT-DSK-013.007.M37.T04: no tool, a tool with two or default parameters, a top-level call,
    over 6000 characters and a syntax error each give a problem."""
    assert why in check_code(code)


# ── versions (SRD-DSK-013.009) ──────────────────────────────────────────────


def test_save_versions(tmp_path: Path) -> None:
    """UT-DSK-013.009.M37.T01: The same name saved twice gives v1.py and v2.py with their code
    and SHA-256; v1 stays as it was."""
    first = save_version(tmp_path, None, bs.answer(), NOW)
    v1 = (tmp_path / first.file).read_bytes()
    second = save_version(tmp_path, None, bs.answer(code=bs.GOOD_CODE + "# two\n"), NOW)
    assert (first.file, second.file) == (f"tools/{bs.NAME}/v1.py", f"tools/{bs.NAME}/v2.py")
    assert (tmp_path / first.file).read_bytes() == v1 == bs.GOOD_CODE.encode()
    assert second.sha256 == hashlib.sha256((bs.GOOD_CODE + "# two\n").encode()).hexdigest()
    assert first.sha256 == hashlib.sha256(v1).hexdigest()


def test_file_left_by_a_crash(tmp_path: Path) -> None:
    """UT-DSK-013.009.M37.T02: A v1.py with no row is never overwritten; the new version is v2."""
    stray = tmp_path / "tools" / bs.NAME / "v1.py"
    stray.parent.mkdir(parents=True)
    stray.write_bytes(b"left over")
    saved = save_version(tmp_path, None, bs.answer(), NOW)
    assert saved.version == 2 and stray.read_bytes() == b"left over"


# ── sample stocks (SRD-DSK-013.014) ─────────────────────────────────────────


def test_sample_stocks(tmp_path: Path) -> None:
    """UT-DSK-013.014.M37.T01: The request's stocks; else the best-ranked ideas; else the top
    RS stocks; else none."""
    assert sample_symbols(tmp_path, ["zzb", "ZZA", "zzb"]) == ["ZZB", "ZZA"]
    assert sample_symbols(tmp_path, []) == []
    bs.rows(tmp_path, "CREATE TABLE stock_rs (date TEXT, symbol TEXT, rs_rating INTEGER)")
    for n in range(7):
        bs.rows(tmp_path, "INSERT INTO stock_rs VALUES ('2026-11-13', ?, ?)", (f"ZR{n}", n))
    bs.rows(tmp_path, "INSERT INTO stock_rs VALUES ('2026-11-12', 'OLD', 99)")
    assert sample_symbols(tmp_path, []) == ["ZR6", "ZR5", "ZR4", "ZR3", "ZR2"]
    bs.rows(tmp_path, "CREATE TABLE ideas (date TEXT, symbol TEXT, rank INTEGER)")
    for n, sym in enumerate(("ZI1", "ZI1", "ZI2", "ZI3", "ZI4", "ZI5", "ZI6")):
        bs.rows(tmp_path, "INSERT INTO ideas VALUES ('2026-11-13', ?, ?)", (sym, n))
    assert sample_symbols(tmp_path, []) == ["ZI1", "ZI2", "ZI3", "ZI4", "ZI5"]


# ── Enable and Disable (SRD-DSK-013.017, .018) ──────────────────────────────


def _built_rows(home: Path) -> list[tuple[str, int, str]]:
    return [(t.name, t.version, t.status) for t in list_tools(home)
            if t.name.startswith("built.")]


def test_enable(tmp_path: Path) -> None:
    """UT-DSK-013.017.M37.T01: Enable writes the active tool with 60 s, the format with symbol
    first and every column made by the tool, and an active plan."""
    tool = bs.version(tmp_path)
    assert tool.state == REVIEW
    assert enable_tool(tmp_path, tool.id, NOW) == ""
    reg = get_tool(tmp_path, f"built.{bs.NAME}")
    assert reg is not None and (reg.status, reg.secs, reg.output_schema) == (
        "active", 60, f"{bs.NAME}.v1")
    fmt = get_format(tmp_path, f"{bs.NAME}.v1")
    assert fmt is not None and [c.name for c in fmt.columns] == ["symbol", "below_high"]
    assert {c.by for c in fmt.columns} == {f"built.{bs.NAME}"}
    plan = get_plan(tmp_path, f"{bs.NAME}.v1")
    assert plan is not None and plan.status == "active" and plan.unmade == ()
    found = get_built(tmp_path, tool.id)
    assert found is not None and found.state == ENABLED and found.decided


def test_new_version_replaces(tmp_path: Path) -> None:
    """UT-DSK-013.017.M37.T02: Enabling v2 turns v1 off: disabled, registry row off, format gone."""
    first = bs.version(tmp_path)
    assert enable_tool(tmp_path, first.id, NOW) == ""
    second = bs.version(tmp_path, code=bs.GOOD_CODE + "# v2\n")
    assert enable_tool(tmp_path, second.id, NOW) == ""
    assert _built_rows(tmp_path) == [(f"built.{bs.NAME}", 1, "off"),
                                     (f"built.{bs.NAME}", 2, "active")]
    assert get_format(tmp_path, f"{bs.NAME}.v1") is None
    assert get_plan(tmp_path, f"{bs.NAME}.v1") is None
    assert get_format(tmp_path, f"{bs.NAME}.v2") is not None
    states = {t.version: t.state for t in built_tool_rows(tmp_path)}
    assert states == {1: DISABLED, 2: ENABLED}


def test_enable_refused(tmp_path: Path) -> None:
    """UT-DSK-013.017.M37.T03: A failed version, a changed file, an unknown id and an enabled
    one are refused with the reason, and nothing is written."""
    failed = bs.version(tmp_path, name="gap_one", ok=False)
    edited = bs.version(tmp_path, name="gap_two")
    (tmp_path / edited.file).write_text(bs.GOOD_CODE + "# edited\n", encoding="utf-8")
    assert enable_tool(tmp_path, failed.id, NOW) == "this version failed its checks"
    assert enable_tool(tmp_path, edited.id, NOW) == CHANGED
    assert enable_tool(tmp_path, 999, NOW) == "no such tool"
    assert _built_rows(tmp_path) == []
    good = bs.version(tmp_path, name="gap_three")
    assert enable_tool(tmp_path, good.id, NOW) == ""
    before = _built_rows(tmp_path)
    assert enable_tool(tmp_path, good.id, NOW) == ("only a tool in review or disabled can be "
                                                  "enabled")
    assert _built_rows(tmp_path) == before


def test_one_plan_only(tmp_path: Path) -> None:
    """UT-DSK-013.017.M32.T01: Enable makes only its own plan; a retired plan of another
    format stays retired."""
    other = bs.version(tmp_path, name="other_tool")
    assert enable_tool(tmp_path, other.id, NOW) == ""
    for _ in range(3):
        note_result(tmp_path, f"other_tool.v{other.version}", True, "broken", NOW)
    tool = bs.version(tmp_path)
    assert enable_tool(tmp_path, tool.id, NOW) == ""
    kept = get_plan(tmp_path, "other_tool.v1")
    assert kept is not None and kept.status == RETIRED


def test_disable(tmp_path: Path) -> None:
    """UT-DSK-013.018.M37.T01: Disable sets the version disabled, its registry row off and
    removes its format and plan; Enable works again."""
    tool = bs.version(tmp_path)
    enable_tool(tmp_path, tool.id, NOW)
    assert disable_tool(tmp_path, tool.id, NOW) == ""
    found = get_built(tmp_path, tool.id)
    assert found is not None and found.state == DISABLED
    assert _built_rows(tmp_path) == [(f"built.{bs.NAME}", 1, "off")]
    assert get_format(tmp_path, f"{bs.NAME}.v1") is None
    assert get_plan(tmp_path, f"{bs.NAME}.v1") is None
    assert enable_tool(tmp_path, tool.id, NOW) == ""
    assert _built_rows(tmp_path) == [(f"built.{bs.NAME}", 1, "active")]


def test_disable_refused(tmp_path: Path) -> None:
    """UT-DSK-013.018.M37.T02: A version in review cannot be disabled."""
    tool = bs.version(tmp_path)
    assert disable_tool(tmp_path, tool.id, NOW) == "only an enabled tool can be disabled"
    assert disable_tool(tmp_path, 999, NOW) == "no such tool"


# ── registry on a desk start (SRD-DSK-013.019) ──────────────────────────────


def test_built_rows_kept(tmp_path: Path) -> None:
    """UT-DSK-013.019.M28.T01: A desk start keeps an enabled built tool active."""
    tool = bs.version(tmp_path)
    enable_tool(tmp_path, tool.id, NOW)
    fill_registry(tmp_path, NOW + timedelta(days=1))
    fill_plans(tmp_path, NOW + timedelta(days=1))
    assert _built_rows(tmp_path) == [(f"built.{bs.NAME}", 1, "active")]
    plan = get_plan(tmp_path, f"{bs.NAME}.v1")
    assert plan is not None and plan.status == "active"


def test_other_gone_tools_off(tmp_path: Path) -> None:
    """UT-DSK-013.019.M28.T02: A code tool that is not in the seed is still set off."""
    save_tool(tmp_path, Tool(name="zz.gone", kind="code", version=1, description="gone",
                             inputSchema={"type": "object"}), NOW)
    fill_registry(tmp_path, NOW)
    gone = get_tool(tmp_path, "zz.gone")
    assert gone is not None and gone.status == "off"


# ── switch (SRD-DSK-013.021) ────────────────────────────────────────────────


def test_switch_setting(tmp_path: Path) -> None:
    """UT-DSK-013.021.M13.T01: tool_builder_on is false by default; true is kept."""
    assert DeskAiSettings().tool_builder_on is False
    assert load_settings(tmp_path).tool_builder_on is False
    save_settings(DeskAiSettings(tool_builder_on=True), tmp_path)
    assert load_settings(tmp_path).tool_builder_on is True


# ── reads (SRD-DSK-013.023) ─────────────────────────────────────────────────


def test_reads(tmp_path: Path) -> None:
    """UT-DSK-013.023.M37.T01: Requests and versions come newest first; the code is the file's
    text."""
    bs.on(tmp_path)
    ids = [ask_tool(tmp_path, f"Request {n}", NOW + timedelta(minutes=n)) for n in range(3)]
    assert [r.id for r in tool_requests(tmp_path)] == ids[::-1]
    first, second = bs.version(tmp_path), bs.version(tmp_path, name="gap_two", ok=False)
    assert [t.id for t in built_tool_rows(tmp_path)] == [second.id, first.id]
    assert second.state == FAILED and second.passed == 4
    assert code_of(tmp_path, first) == bs.GOOD_CODE


def test_reads_without_database(tmp_path: Path) -> None:
    """UT-DSK-013.023.M37.T02: With no desk database the reads are empty; a missing file gives
    no code."""
    assert tool_requests(tmp_path) == [] and built_tool_rows(tmp_path) == []
    tool = bs.version(tmp_path)
    (tmp_path / tool.file).unlink()
    assert code_of(tmp_path, tool) == ""


# ── code review fixes (2026-11-15) ──────────────────────────────────────────


def test_deep_code_never_raises() -> None:
    """UT-DSK-013.007.M37.T05: A very long top-level sum and deeply nested brackets give
    problems or none, but never raise."""
    long_sum = "X = " + "1+" * 2900 + "1\n" + _tool("    pass")
    assert len(long_sum) <= 6000
    assert check_code(long_sum) in ([], [f"line 1: {TOO_DEEP}"])
    nested = _tool("    x = " + "(" * 300 + "1" + ")" * 300)
    problems = check_code(nested)
    assert problems and problems[0].startswith("line ")


def test_enable_rolls_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-DSK-013.017.M37.T04: An Enable that fails half way leaves no active registry row,
    format or plan, and the version stays in review."""
    from us_swing.core import desk_built_tools as dbt  # noqa: PLC0415

    tool = bs.version(tmp_path)

    def broken(*_args: object) -> bool:
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(dbt, "save_plan", broken)
    assert enable_tool(tmp_path, tool.id, NOW) == dbt.NOT_SAVED
    assert [s for _n, _v, s in _built_rows(tmp_path)] in ([], ["off"])
    assert get_format(tmp_path, f"{bs.NAME}.v1") is None
    found = get_built(tmp_path, tool.id)
    assert found is not None and found.state == REVIEW


def test_broken_row_skipped(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-013.023.M37.T03: A built tool row that cannot be read is skipped with a warning;
    the other rows and the planner's tool functions still work."""
    from us_swing.desk.sandbox import built_fns  # noqa: PLC0415

    good = bs.version(tmp_path)
    assert enable_tool(tmp_path, good.id, NOW) == ""
    bad = bs.version(tmp_path, name="bad_tool")
    bs.rows(tmp_path, "UPDATE built_tools SET columns = 'not json', state = 'enabled' "
                      "WHERE id = ?", (bad.id,))
    assert [t.id for t in built_tool_rows(tmp_path)] == [good.id]
    assert "could not be read" in caplog.text
    assert set(built_fns(tmp_path)) == {f"built.{bs.NAME}"}
