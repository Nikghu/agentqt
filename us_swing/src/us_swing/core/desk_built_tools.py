"""
Module: MD-DSK-013.001.M37 — core/desk_built_tools.py
Parent SRD: SRD-DSK-013.001
Also: SRD-DSK-013.005 (answer model), .006 (answer checks), .007 (code rules), .009 (versions
with SHA-256), .013 (changed code), .014 (sample stocks), .015 (version states), .017 (Enable),
.018 (Disable), .021 (switch), .023 (reads), .024 (log lines)

Tool requests and built tools in ``desk.db`` (AI Desk v3 M7b). The Master user asks for a tool
in AI Desk → Tools (``ask_tool``) or through the chat lead, and the builder employee writes one
small Python function per request. This module keeps the requests and the versions, checks an
answer and its code against fixed rules, binds each version's file to its SHA-256, and switches
a version on or off: only ``enable_tool`` writes a built tool, its table format and its plan.
Shared by the desk and the GUI; it imports neither ``desk``, ``market`` nor ``gui``.
Design: DD-DSK-013.001.D01.
"""
from __future__ import annotations

import ast
import hashlib
import json
import logging
import re
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Final, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from us_swing.core.desk_ai_settings import load_settings
from us_swing.core.desk_contract import DB_NAME
from us_swing.core.desk_events import post_event
from us_swing.core.desk_registry import (
    Column,
    TableFormat,
    Tool,
    drop_format,
    list_formats,
    save_format,
    save_tool,
    seed_formats,
    set_tool_status,
)
from us_swing.core.desk_tasks import drop_plan, save_plan

log = logging.getLogger(__name__)

NY = ZoneInfo("America/New_York")
GROUP: Final = "built"
SECS: Final = 60
MAX_REQUEST: Final = 300
MAX_CODE: Final = 6000
MAX_LINES: Final = 200
MAX_COLUMNS: Final = 5
SAMPLES: Final = 5
MADE_UP: Final = "ZZZZZ"
OPEN_FOR: Final = timedelta(days=1)
OFF: Final = "the tool builder is off"
CHANGED: Final = "the code changed after review"
NOT_SAVED: Final = "the change could not be saved; see the desk log"
EXPIRED: Final = "not picked up within a day"
STOPPED: Final = "the desk stopped while it was building"
TOO_DEEP: Final = "the code is too deeply nested"
REVIEW: Final = "review"
FAILED: Final = "failed"
ENABLED: Final = "enabled"
DISABLED: Final = "disabled"
CHECKS: Final = ("Code rules", "Time and memory", "Full row", "Value types", "No data")

ALLOWED_BUILTINS: Final = (
    "abs", "all", "any", "bool", "dict", "divmod", "enumerate", "filter", "float", "int",
    "isinstance", "len", "list", "map", "max", "min", "pow", "range", "reversed", "round", "set",
    "sorted", "str", "sum", "tuple", "zip", "ValueError", "ZeroDivisionError", "KeyError",
    "IndexError", "TypeError", "Exception")
STATS_NAMES: Final = ("mean", "median", "stdev", "pstdev", "fmean")
READ_NAMES: Final = ("daily_bars", "intraday_bars", "desk_rows")
MATH_ATTRS: Final = ("sqrt", "log", "log10", "exp", "floor", "ceil", "fabs", "isnan",
                     "isfinite", "inf", "nan", "pi", "hypot", "copysign")
ALLOWED_NAMES: Final = frozenset((*ALLOWED_BUILTINS, "math", *STATS_NAMES, *READ_NAMES))
ALLOWED_ATTRS: Final = frozenset((
    "get", "items", "keys", "values", "append", "extend", "insert", "pop", "index", "count",
    "sort", "reverse", "copy", "update", "setdefault", "lower", "upper", "strip", "lstrip",
    "rstrip", "split", "join", "replace", "startswith", "endswith", "isdigit", "add", "discard",
    *MATH_ATTRS))
_BANNED: Final[dict[type[ast.AST], str]] = {
    ast.Import: "import", ast.ImportFrom: "import", ast.ClassDef: "class",
    ast.AsyncFunctionDef: "async def", ast.Await: "await", ast.AsyncFor: "async for",
    ast.AsyncWith: "async with", ast.With: "with", ast.Yield: "yield",
    ast.YieldFrom: "yield from", ast.Global: "global", ast.Nonlocal: "nonlocal",
    ast.Match: "match"}
_TOOL_NAME = re.compile(r"^[a-z][a-z0-9_]{2,29}$")
_SYMBOLS: Final[dict[str, Any]] = {
    "type": "object", "required": ["symbols"],
    "properties": {"symbols": {"type": "array", "items": {"type": "string"}}}}

SCHEMA = """
CREATE TABLE IF NOT EXISTS tool_requests (
    id INTEGER PRIMARY KEY, made TEXT, source TEXT, message INTEGER, asker TEXT, text TEXT,
    symbols TEXT, state TEXT, reason TEXT, tool INTEGER, ended TEXT
);
CREATE TABLE IF NOT EXISTS built_tools (
    id INTEGER PRIMARY KEY, name TEXT, version INTEGER, request INTEGER, title TEXT, about TEXT,
    columns TEXT, file TEXT, sha256 TEXT, state TEXT, checks TEXT, sample TEXT, made TEXT,
    decided TEXT, UNIQUE (name, version)
);
"""
_REQ_COLS = "id, made, source, message, asker, text, symbols, state, reason, tool, ended"
_TOOL_COLS = ("id, name, version, request, title, about, columns, file, sha256, state, checks, "
              "sample, made, decided")


class ToolColumn(BaseModel):
    """One column a built tool fills."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,29}$", description="Column name in lower_case")
    type: Literal["number", "text"]
    meaning: str = Field(min_length=1, max_length=120,
                         description="What the value means, in a few words")


class ToolAnswer(BaseModel):
    """The builder's answer: one tool, or only a refusal reason (SRD-DSK-013.005)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(default="", max_length=30,
                      description="Tool name in lower_case, 3 to 30 characters")
    title: str = Field(default="", max_length=60, description="Short title for the Master user")
    about: str = Field(default="", max_length=300,
                       description="What the tool gives, in one or two short sentences")
    columns: list[ToolColumn] = Field(default_factory=list, max_length=MAX_COLUMNS,
                                      description="1 to 5 columns; never symbol")
    code: str = Field(default="", max_length=MAX_CODE,
                      description="Python code with def tool(symbol)")
    refuse: str = Field(default="", max_length=200,
                        description="Why the tool cannot be built; leave the rest empty then")


class Check(BaseModel):
    """One check of a version: its name, whether it passed and a short note."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    check: str
    ok: bool
    note: str = ""


@dataclass(frozen=True)
class ToolRequest:
    """One request for a tool; times are New York ISO text."""

    id: int
    made: str
    source: str
    message: int | None
    asker: str
    text: str
    symbols: tuple[str, ...]
    state: str
    reason: str
    tool: int | None
    ended: str | None


@dataclass(frozen=True)
class BuiltTool:
    """One saved version of a built tool."""

    id: int
    name: str
    version: int
    request: int | None
    title: str
    about: str
    columns: tuple[ToolColumn, ...]
    file: str
    sha256: str
    state: str
    checks: tuple[Check, ...]
    sample: tuple[str, ...]
    made: str
    decided: str | None

    @property
    def tool_name(self) -> str:
        """Registry name, such as ``built.gap_pct``."""
        return f"{GROUP}.{self.name}"

    @property
    def format_id(self) -> str:
        """Table format id, such as ``gap_pct.v2``."""
        return f"{self.name}.v{self.version}"

    @property
    def passed(self) -> int:
        """How many checks passed."""
        return sum(c.ok for c in self.checks)


# ── store ────────────────────────────────────────────────────────────────────


def _connect(home: Path) -> sqlite3.Connection:
    home.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(home / DB_NAME, timeout=5)
    con.execute("PRAGMA busy_timeout=5000")
    con.executescript(SCHEMA)
    return con


def _stamp(moment: datetime) -> str:
    return moment.astimezone(NY).isoformat(timespec="seconds")


def _read(home: Path, sql: str, args: tuple[object, ...] = (),
          strict: bool = False) -> list[tuple[Any, ...]]:
    """Rows of a read-only query; empty with no database or table. With ``strict`` any other
    database error rises, so a lock is never taken for "no such row"."""
    path = home / DB_NAME
    if not path.exists():
        return []
    con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=2)
    try:
        return con.execute(sql, args).fetchall()
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc):
            return []
        if strict:
            raise
        log.warning("[Tool builder] Could not read the built tools: %s", exc)
        return []
    finally:
        con.close()


def _request(row: Sequence[Any]) -> ToolRequest:
    return ToolRequest(int(row[0]), str(row[1]), str(row[2]),
                       None if row[3] is None else int(row[3]), str(row[4]), str(row[5]),
                       tuple(json.loads(row[6] or "[]")), str(row[7]), str(row[8] or ""),
                       None if row[9] is None else int(row[9]), row[10])


def _built(row: Sequence[Any]) -> BuiltTool:
    return BuiltTool(int(row[0]), str(row[1]), int(row[2]),
                     None if row[3] is None else int(row[3]), str(row[4]), str(row[5]),
                     tuple(ToolColumn.model_validate(c) for c in json.loads(row[6] or "[]")),
                     str(row[7]), str(row[8]), str(row[9]),
                     tuple(Check.model_validate(c) for c in json.loads(row[10] or "[]")),
                     tuple(str(s) for s in json.loads(row[11] or "[]")), str(row[12]), row[13])


# ── requests (SRD-DSK-013.001–.003) ──────────────────────────────────────────


def ask_tool(home: Path, text: str, now: datetime) -> int:
    """Save a tool request typed by the Master user and post its event (SRD-DSK-013.001).

    Args:
        home: Desk folder.
        text: What the tool should give, 1 to 300 characters.
        now: Time-zone aware time.

    Returns:
        The request id.

    Raises:
        ValueError: When the text is empty or too long, or the tool builder is off.
    """
    text = text.strip()
    if not text or len(text) > MAX_REQUEST:
        raise ValueError(f"a request needs 1 to {MAX_REQUEST} characters")
    if not load_settings(home).tool_builder_on:
        raise ValueError(OFF)
    rid = add_request(home, "tools", None, "master", text, (), now)
    post_event(home, "tool_request", now.date().isoformat(), now, run_id=rid)
    log.info("[Tool builder] Request #%d saved", rid)
    return rid


def add_request(home: Path, source: str, message: int | None, asker: str, text: str,
                symbols: Sequence[str], now: datetime) -> int:
    """Save one new request; ``source`` is tools or chat (SRD-DSK-013.001, .002)."""
    con = _connect(home)
    try:
        with con:
            cur = con.execute(
                "INSERT INTO tool_requests (made, source, message, asker, text, symbols, state, "
                "reason) VALUES (?, ?, ?, ?, ?, ?, 'new', '')",
                (_stamp(now), source, message, asker, text[:MAX_REQUEST],
                 json.dumps(list(symbols)[:SAMPLES])))
        return int(cur.lastrowid or 0)
    finally:
        con.close()


def _open(home: Path, states: tuple[str, ...]) -> list[ToolRequest]:
    marks = ",".join("?" * len(states))
    return [_request(r) for r in _read(
        home, f"SELECT {_REQ_COLS} FROM tool_requests WHERE state IN ({marks}) "  # noqa: S608
              "ORDER BY id", states)]


def new_requests(home: Path, now: datetime) -> list[ToolRequest]:
    """New requests of the last day, oldest first (SRD-DSK-013.003)."""
    return [r for r in _open(home, ("new",))
            if now - datetime.fromisoformat(r.made) <= OPEN_FOR]


def stale_requests(home: Path, now: datetime) -> list[ToolRequest]:
    """New or building requests made more than a day ago: not picked up, or left by a desk
    that stopped while it was building (SRD-DSK-013.003)."""
    return [r for r in _open(home, ("new", "building"))
            if now - datetime.fromisoformat(r.made) > OPEN_FOR]


def expire_requests(home: Path, now: datetime) -> int:
    """End the stale requests: a new one expired, a building one failed; return how many."""
    old = stale_requests(home, now)
    for r in old:
        if r.state == "new":
            set_request(home, r.id, "expired", EXPIRED, now)
            log.info("[Tool builder] Request #%d expired", r.id)
        else:
            set_request(home, r.id, "failed", STOPPED, now)
            log.info("[Tool builder] Request #%d failed: %s", r.id, STOPPED)
    return len(old)


def set_request(home: Path, rid: int, state: str, reason: str, now: datetime,
                tool: int | None = None) -> None:
    """Set a request's state and reason; the end time is set for a final state."""
    ended = None if state in ("new", "building") else _stamp(now)
    con = _connect(home)
    try:
        with con:
            con.execute("UPDATE tool_requests SET state = ?, reason = ?, tool = COALESCE(?, tool), "
                        "ended = ? WHERE id = ?", (state, reason[:300], tool, ended, rid))
    finally:
        con.close()


# ── answer and code rules (SRD-DSK-013.006, .007) ────────────────────────────


def taken_names(home: Path) -> set[str]:
    """Table format names a new tool may not take: every library name but the built tools'."""
    own = {str(r[0]) for r in _read(home, "SELECT DISTINCT name FROM built_tools")}
    return ({f.name for f in seed_formats()} | {f.name for f in list_formats(home)}) - own


def check_answer(home: Path, answer: ToolAnswer) -> list[str]:
    """Shape problems of an answer: its name, title, about and columns (SRD-DSK-013.006)."""
    problems = []
    if not _TOOL_NAME.match(answer.name):
        problems.append("the tool name must be lower_case, 3 to 30 characters")
    elif answer.name in taken_names(home):
        problems.append(f"the name {answer.name} is taken by a table format")
    if not answer.title.strip():
        problems.append("the title is empty")
    if not answer.about.strip():
        problems.append("about is empty")
    names = [c.name for c in answer.columns]
    if not names:
        problems.append(f"give 1 to {MAX_COLUMNS} columns")
    if "symbol" in names:
        problems.append("the desk adds the symbol column itself; name your columns otherwise")
    if len(names) != len(set(names)):
        problems.append("each column name may be used once")
    return problems


def _constant(node: ast.AST | None) -> bool:
    """A literal, or a tuple, list, set, dict, sign or sum of literals; checked without
    recursion, so a very long sum cannot exhaust the stack."""
    todo: list[ast.AST | None] = [node]
    while todo:
        item = todo.pop()
        if isinstance(item, ast.Constant):
            continue
        if isinstance(item, ast.Tuple | ast.List | ast.Set):
            todo.extend(item.elts)
        elif isinstance(item, ast.Dict) and None not in item.keys:
            todo.extend([*item.keys, *item.values])
        elif isinstance(item, ast.UnaryOp):
            todo.append(item.operand)
        elif isinstance(item, ast.BinOp):
            todo.extend([item.left, item.right])
        else:
            return False
    return True


def _allowed_at_top(node: ast.stmt, first: bool) -> bool:
    """A def, a constant or the docstring; banned statements are named by their own rule."""
    if isinstance(node, ast.FunctionDef) or type(node) in _BANNED:
        return True
    if isinstance(node, ast.Assign):
        return all(isinstance(t, ast.Name) for t in node.targets) and _constant(node.value)
    if isinstance(node, ast.AnnAssign):
        return isinstance(node.target, ast.Name) and _constant(node.value)
    return (first and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str))


def _top_level(tree: ast.Module) -> list[tuple[int, str]]:
    """Only defs, constants and a docstring at the top, and one plain ``def tool(symbol)``;
    each problem with its line."""
    problems = [(node.lineno, "only def statements and constants may stand at the top")
                for i, node in enumerate(tree.body) if not _allowed_at_top(node, i == 0)]
    tool = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "tool"),
                None)
    if tool is None:
        return [*problems, (1, "the code has no def tool(symbol)")]
    a = tool.args
    if (len(a.args) != 1 or a.posonlyargs or a.kwonlyargs or a.vararg or a.kwarg
            or a.defaults):
        problems.append((tool.lineno, "tool must take one parameter, symbol, with no default"))
    return problems


def _bound(tree: ast.AST) -> set[str]:
    """Every name the code binds: assigned names, parameters, defs and except names."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store | ast.Del):
            names.add(node.id)
        elif isinstance(node, ast.FunctionDef):
            names.add(node.name)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
    return names


def _node_problem(node: ast.AST, bound: set[str]) -> str:
    """The rule one node breaks, or ``""``."""
    kind = _BANNED.get(type(node))
    if kind is not None:
        return f"{kind} is not allowed"
    if isinstance(node, ast.FunctionDef):
        if node.decorator_list:
            return "decorators are not allowed"
        if node.name.startswith("_"):
            return f"the name {node.name} starts with _"
    elif isinstance(node, ast.arg) and node.arg.startswith("_"):
        return f"the name {node.arg} starts with _"
    elif isinstance(node, ast.ExceptHandler) and node.name and node.name.startswith("_"):
        return f"the name {node.name} starts with _"
    elif isinstance(node, ast.Name):
        if node.id.startswith("_"):
            return f"the name {node.id} starts with _"
        if isinstance(node.ctx, ast.Load) and node.id not in bound and node.id not in ALLOWED_NAMES:
            return f"unknown name {node.id}"
    elif isinstance(node, ast.Attribute) and node.attr not in ALLOWED_ATTRS:
        return f"the attribute {node.attr} is not allowed"
    elif isinstance(node, ast.Constant) and isinstance(node.value, str) and "__" in node.value:
        return "a text with __ in it is not allowed"
    return ""


def check_code(code: str) -> list[str]:
    """Problems of tool code against the fixed rules; empty when it may run (SRD-DSK-013.007).

    Each problem reads ``line <n>: <what>``. The rules allow only listed names and attribute
    names, so the code cannot reach a module, a frame, a file or ``__builtins__``.
    """
    if len(code) > MAX_CODE:
        return [f"line 1: the code is longer than {MAX_CODE} characters"]
    if len(code.splitlines()) > MAX_LINES:
        return [f"line {MAX_LINES + 1}: the code is longer than {MAX_LINES} lines"]
    try:
        tree = ast.parse(code)
        bound = _bound(tree)
        found = _top_level(tree)
        for node in ast.walk(tree):
            why = _node_problem(node, bound)
            if why:
                found.append((int(getattr(node, "lineno", 1)), why))
    except SyntaxError as exc:
        return [f"line {exc.lineno or 1}: {exc.msg}"]
    except (RecursionError, MemoryError):
        return [f"line 1: {TOO_DEEP}"]
    return [f"line {line}: {why}" for line, why in sorted(found, key=lambda pair: pair[0])]


# ── versions (SRD-DSK-013.009, .013, .015) ───────────────────────────────────


def _next_version(home: Path, name: str) -> int:
    rows = _read(home, "SELECT MAX(version) FROM built_tools WHERE name = ?", (name,),
                 strict=True)
    files = [int(m.group(1)) for p in (home / "tools" / name).glob("v*.py")
             if (m := re.fullmatch(r"v(\d+)\.py", p.name))]
    return max([int(rows[0][0] or 0) if rows else 0, *files]) + 1


def save_version(home: Path, request: int | None, answer: ToolAnswer,
                 now: datetime) -> BuiltTool:
    """Write the answer's code once as ``tools/<name>/v<N>.py`` and add its row (.009).

    The file is opened with mode ``x``, so it is never overwritten; the row starts failed with
    no checks until ``set_checks()`` sets its state.
    """
    version = _next_version(home, answer.name)
    rel = f"tools/{answer.name}/v{version}.py"
    path = home / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    data = answer.code.encode("utf-8")
    with path.open("xb") as fh:
        fh.write(data)
    con = _connect(home)
    try:
        with con:
            cur = con.execute(
                "INSERT INTO built_tools (name, version, request, title, about, columns, file, "
                "sha256, state, checks, sample, made) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', "
                "'[]', ?)",
                (answer.name, version, request, answer.title.strip(), answer.about.strip(),
                 json.dumps([c.model_dump() for c in answer.columns]), rel,
                 hashlib.sha256(data).hexdigest(), FAILED, _stamp(now)))
        tool_id = int(cur.lastrowid or 0)
    finally:
        con.close()
    saved = get_built(home, tool_id)
    if saved is None:
        raise sqlite3.OperationalError("the saved tool could not be read back")
    return saved


def set_checks(home: Path, tool_id: int, checks: Sequence[Check],
               sample: Sequence[str]) -> str:
    """Keep a version's checks and sample lines; return its state, review only when all 5
    checks passed (SRD-DSK-013.015)."""
    state = REVIEW if len(checks) == len(CHECKS) and all(c.ok for c in checks) else FAILED
    con = _connect(home)
    try:
        with con:
            con.execute("UPDATE built_tools SET checks = ?, sample = ?, state = ? WHERE id = ?",
                        (json.dumps([c.model_dump() for c in checks]), json.dumps(list(sample)),
                         state, tool_id))
    finally:
        con.close()
    return state


def code_of(home: Path, tool: BuiltTool) -> str:
    """The version's code as saved on disk, or ``""`` when its file is missing."""
    try:
        return (home / tool.file).read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def checked_code(home: Path, tool: BuiltTool) -> str | None:
    """The version's code when its file still matches its SHA-256, else ``None`` (.013)."""
    try:
        data = (home / tool.file).read_bytes()
    except OSError:
        return None
    if hashlib.sha256(data).hexdigest() != tool.sha256:
        return None
    return data.decode("utf-8", errors="replace")


def changed(home: Path, tool: BuiltTool) -> bool:
    """True when the version's file is missing or no longer matches its SHA-256 (.013)."""
    return checked_code(home, tool) is None


def sample_symbols(home: Path, given: Sequence[str]) -> list[str]:
    """Up to 5 stocks to test a tool on: the request's, else the best-ranked ideas of the
    latest date, else the top RS stocks of the latest day (SRD-DSK-013.014)."""
    if given:
        return list(dict.fromkeys(s.strip().upper() for s in given if s.strip()))[:SAMPLES]
    for sql in ("SELECT symbol FROM ideas WHERE date = (SELECT MAX(date) FROM ideas) "
                "ORDER BY rank LIMIT ?",
                "SELECT symbol FROM stock_rs WHERE date = (SELECT MAX(date) FROM stock_rs) "
                "ORDER BY rs_rating DESC LIMIT ?"):
        found = list(dict.fromkeys(str(r[0]) for r in _read(home, sql, (SAMPLES * 2,))))
        if found:
            return found[:SAMPLES]
    return []


# ── Enable and Disable (SRD-DSK-013.017, .018) ───────────────────────────────


def tool_format(tool: BuiltTool) -> TableFormat:
    """The table format of a version: ``symbol``, then the tool's columns, all made by it."""
    return TableFormat(id=tool.format_id, title=(tool.title or tool.name)[:80], columns=[
        Column(name="symbol", type="text", meaning="stock", by=tool.tool_name),
        *(Column(name=c.name, type=c.type, meaning=c.meaning, by=tool.tool_name)
          for c in tool.columns)])


def _registry_tool(tool: BuiltTool) -> Tool:
    return Tool(name=tool.tool_name, kind="code", version=tool.version,
                description=(tool.title or tool.name)[:300], inputSchema=_SYMBOLS,
                outputSchema=tool.format_id, secs=SECS)


def _set_state(home: Path, tool_id: int, state: str, now: datetime) -> None:
    con = _connect(home)
    try:
        with con:
            con.execute("UPDATE built_tools SET state = ?, decided = ? WHERE id = ?",
                        (state, _stamp(now), tool_id))
    finally:
        con.close()


def _switch_off(home: Path, tool: BuiltTool, now: datetime) -> None:
    """The row first, so a half-done Disable never leaves an enabled row without its parts."""
    _set_state(home, tool.id, DISABLED, now)
    drop_plan(home, tool.format_id)
    drop_format(home, tool.format_id)
    set_tool_status(home, tool.tool_name, tool.version, "off", now)


def may_enable(tool: BuiltTool | None) -> bool:
    """A version may be enabled when it waits in review or is disabled and passed all checks;
    the GUI offers Enable by this rule (SRD-DSK-013.017)."""
    return (tool is not None and tool.state in (REVIEW, DISABLED)
            and tool.passed == len(CHECKS))


def may_disable(tool: BuiltTool | None) -> bool:
    """A version may be disabled while it is enabled (SRD-DSK-013.018)."""
    return tool is not None and tool.state == ENABLED


def _refusal(home: Path, tool: BuiltTool | None) -> str:
    if tool is None:
        return "no such tool"
    if tool.state == FAILED or tool.passed < len(CHECKS):
        return "this version failed its checks"
    if not may_enable(tool):
        return "only a tool in review or disabled can be enabled"
    if changed(home, tool):
        return CHANGED
    return ""


def _undo_enable(home: Path, tool: BuiltTool, now: datetime) -> None:
    """Take back a half-done Enable, so no active registry row, format or plan is left for
    a version that is not enabled; the version keeps its state."""
    try:
        drop_plan(home, tool.format_id)
        drop_format(home, tool.format_id)
        set_tool_status(home, tool.tool_name, tool.version, "off", now)
    except (sqlite3.Error, OSError):
        log.exception("[Tool builder] Tool %s v%d could not be set back", tool.name,
                      tool.version)


def enable_tool(home: Path, tool_id: int, now: datetime) -> str:
    """Switch one version on: its registry tool, table format and plan; any other enabled
    version of the same tool goes off (SRD-DSK-013.017).

    Returns:
        ``""`` when done, else why it was refused.
    """
    try:
        tool = get_built(home, tool_id)
        why = _refusal(home, tool)
        if why or tool is None:
            return why
        for other in _versions(home, tool.name):
            if other.id != tool.id and other.state == ENABLED:
                _switch_off(home, other, now)
        fmt = tool_format(tool)
        try:
            save_tool(home, _registry_tool(tool), now)
            save_format(home, fmt, now)
            save_plan(home, fmt, now)
            _set_state(home, tool.id, ENABLED, now)
        except (sqlite3.Error, OSError):
            _undo_enable(home, tool, now)
            raise
    except (sqlite3.Error, OSError):
        log.exception("[Tool builder] Tool #%d could not be enabled", tool_id)
        return NOT_SAVED
    log.info("[Tool builder] Tool %s v%d enabled", tool.name, tool.version)
    return ""


def disable_tool(home: Path, tool_id: int, now: datetime) -> str:
    """Switch an enabled version off: its registry tool off, its format and plan removed
    (SRD-DSK-013.018).

    Returns:
        ``""`` when done, else why it was refused.
    """
    try:
        tool = get_built(home, tool_id)
        if tool is None:
            return "no such tool"
        if not may_disable(tool):
            return "only an enabled tool can be disabled"
        _switch_off(home, tool, now)
    except (sqlite3.Error, OSError):
        log.exception("[Tool builder] Tool #%d could not be disabled", tool_id)
        return NOT_SAVED
    log.info("[Tool builder] Tool %s v%d disabled", tool.name, tool.version)
    return ""


# ── reads (SRD-DSK-013.023) ──────────────────────────────────────────────────


def get_built(home: Path, tool_id: int) -> BuiltTool | None:
    """One version by id; a database error other than a missing table rises."""
    rows = _read(home, f"SELECT {_TOOL_COLS} FROM built_tools WHERE id = ?",  # noqa: S608
                 (tool_id,), strict=True)
    return _built(rows[0]) if rows else None


def _versions(home: Path, name: str) -> list[BuiltTool]:
    return [_built(r) for r in _read(
        home, f"SELECT {_TOOL_COLS} FROM built_tools WHERE name = ? ORDER BY version",  # noqa: S608
        (name,), strict=True)]


def _good(rows: Sequence[Sequence[Any]]) -> list[BuiltTool]:
    """The rows that read back; a broken row is skipped with a warning, so one bad row never
    stops the other tools."""
    out: list[BuiltTool] = []
    for row in rows:
        try:
            out.append(_built(row))
        except (ValueError, TypeError):
            log.warning("[Tool builder] Built tool #%s could not be read; it is skipped", row[0])
    return out


def built_tool_rows(home: Path, limit: int = 50) -> list[BuiltTool]:
    """The latest ``limit`` versions, newest first."""
    return _good(_read(
        home, f"SELECT {_TOOL_COLS} FROM built_tools ORDER BY id DESC LIMIT ?",  # noqa: S608
        (limit,)))


def enabled_tools(home: Path) -> list[BuiltTool]:
    """The enabled versions, by name."""
    return _good(_read(
        home, f"SELECT {_TOOL_COLS} FROM built_tools WHERE state = ? ORDER BY name",  # noqa: S608
        (ENABLED,)))


def tool_requests(home: Path, limit: int = 20) -> list[ToolRequest]:
    """The latest ``limit`` requests, newest first."""
    return [_request(r) for r in _read(
        home, f"SELECT {_REQ_COLS} FROM tool_requests ORDER BY id DESC LIMIT ?",  # noqa: S608
        (limit,))]


def get_request(home: Path, rid: int) -> ToolRequest | None:
    """One request by id."""
    rows = _read(home, f"SELECT {_REQ_COLS} FROM tool_requests WHERE id = ?",  # noqa: S608
                 (rid,))
    return _request(rows[0]) if rows else None
