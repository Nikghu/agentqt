"""
Module: MD-DSK-012.001.M28 — core/desk_registry.py
Parent SRD: SRD-DSK-012.001
Also: SRD-DSK-011.019 (format ``idea_fix.v1`` for fix replies)
Also: SRD-DSK-012.012 (``Tool.secs``), .013 (``ToolResult``), .014 (``Column.by``, the key
column), .015 (table tools and ``setup_table.v1`` seeded) — AI Desk v3 M6

Tool registry (``desk.tool/1``) and schema library (``desk.schema/1``) in ``desk.db``. Tool
rows use the MCP tool shape so code tools and MCP tools look the same. The registry is filled
from the desk steps, research skills, the data recipe menu and the Backtest MCP tools; seed
sources are loaded by import path, so this module imports no ``desk``, ``market``, ``mcp`` or
``gui`` code at module level. Design: DD-DSK-012.001.D01.
"""
from __future__ import annotations

import importlib
import json
import logging
import re
import sqlite3
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from us_swing.core import desk_steps
from us_swing.core.desk_contract import DB_NAME, utc_text
from us_swing.core.desk_steps import SKILL_PATHS, STEP_PATHS

log = logging.getLogger(__name__)

TOOL_SCHEMA = "desk.tool/1"
FORMAT_SCHEMA = "desk.schema/1"
TOOL_NAME = r"^(?:[a-z0-9_]+\.[a-z0-9_]+|mcp:[a-z0-9_]+/[a-z0-9_]+)$"
TOOL_REF = TOOL_NAME[:-1] + r"@[0-9]+$"
SCHEMA_ID = r"^[a-z0-9_]+\.v[0-9]+$"
BACKTEST_MCP = "us_swing.mcp.backtest_tools"
_EMPTY_INPUT: dict[str, Any] = {"type": "object", "properties": {}}
_SYMBOLS_INPUT: dict[str, Any] = {
    "type": "object", "required": ["symbols"],
    "properties": {"symbols": {"type": "array", "items": {"type": "string"}}}}

SCHEMA = """
CREATE TABLE IF NOT EXISTS tools (
    name TEXT, version INTEGER, kind TEXT, status TEXT, body TEXT, updated TEXT,
    PRIMARY KEY (name, version)
);
CREATE TABLE IF NOT EXISTS schemas (
    name TEXT, version INTEGER, body TEXT, updated TEXT, PRIMARY KEY (name, version)
);
"""


class Tool(BaseModel):
    """One registry tool in MCP tool shape (SRD-DSK-012.001)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str = Field(pattern=TOOL_NAME)
    kind: Literal["code", "mcp"]
    version: int = Field(ge=1)
    description: str = Field(max_length=300)
    input_schema: dict[str, Any] = Field(alias="inputSchema")
    output_schema: dict[str, Any] | str | None = Field(default=None, alias="outputSchema")
    ai: bool = False
    status: Literal["active", "off"] = "active"
    secs: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _kind_matches_name(self) -> Tool:
        if (self.kind == "mcp") != self.name.startswith("mcp:"):
            raise ValueError("an mcp tool is named mcp:server/tool and a code tool group.tool")
        if isinstance(self.output_schema, str) and not re.match(SCHEMA_ID, self.output_schema):
            raise ValueError("output schema must be a table format id like scores.v1")
        return self


class Column(BaseModel):
    """One column of a table format."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^[a-z0-9_]+$")
    type: Literal["text", "number"]
    meaning: str = Field(min_length=1, max_length=120)
    by: str | None = Field(default=None, pattern=TOOL_NAME)


class ToolResult(BaseModel):
    """What a table tool returns; the error flag is named ``isError`` as in MCP (SRD-DSK-012.013).

    ``rows`` holds one dict per key with the key column and the tool's columns. ``missing``
    maps ``<key>`` (nothing for that key) or ``<key>.<column>`` (one empty value) to a reason.
    ``flags`` maps a key to one short fact.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    rows: list[dict[str, Any]] = Field(default_factory=list)
    missing: dict[str, str] = Field(default_factory=dict)
    flags: dict[str, str] = Field(default_factory=dict)
    is_error: bool = Field(default=False, alias="isError")
    error: str = ""


class TableFormat(BaseModel):
    """One versioned table format of the schema library (SRD-DSK-012.003)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=SCHEMA_ID)
    title: str = Field(min_length=1, max_length=80)
    columns: list[Column] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_columns(self) -> TableFormat:
        names = [c.name for c in self.columns]
        if len(names) != len(set(names)):
            raise ValueError("column names must be unique")
        return self

    @property
    def key(self) -> str:
        """Name of the key column: the first one (SRD-DSK-012.014)."""
        return self.columns[0].name

    @property
    def name(self) -> str:
        """Format name without its version."""
        return self.id.rsplit(".v", 1)[0]

    @property
    def version(self) -> int:
        """Format version number."""
        return int(self.id.rsplit(".v", 1)[1])


# ── seed (pure, no database) ─────────────────────────────────────────────────


def _load(path: str) -> Any:
    module, _, attr = path.partition(":")
    return getattr(importlib.import_module(module), attr)


def _first_line(obj: object) -> str:
    return obj.__doc__.strip().splitlines()[0][:300] if obj.__doc__ else ""


def _step_key(class_name: str) -> str:
    base = class_name.removesuffix("Step")
    return re.sub(r"(?<!^)(?=[A-Z])", "_", base).lower()


def _step_tools() -> list[Tool]:
    tools = []
    for path in STEP_PATHS:
        cls = _load(path)
        tools.append(Tool(name=f"step.{_step_key(cls.__name__)}", kind="code", version=1,
                          description=str(getattr(cls, "name", cls.__name__)),
                          inputSchema=_EMPTY_INPUT))
    return tools


def _research_tools() -> list[Tool]:
    from us_swing.core.desk_research import KINDS, TicketAsk  # noqa: PLC0415 — avoids a cycle

    ask = TicketAsk.model_json_schema()
    return [Tool(name=f"research.{key}", kind="code", version=1,
                 description=_first_line(_load(path)), inputSchema=ask, ai=True)
            for key, path in SKILL_PATHS.items() if key in KINDS]


def _recipe_tool() -> Tool:
    from us_swing.core.desk_recipes import DataRecipe  # noqa: PLC0415 — avoids a cycle

    return Tool(name="data.recipe", kind="code", version=1, description=_first_line(DataRecipe),
                inputSchema=DataRecipe.model_json_schema())


def _mcp_tools() -> list[Tool]:
    from mcp.server.fastmcp.utilities.func_metadata import func_metadata  # noqa: PLC0415

    module = importlib.import_module(BACKTEST_MCP)
    tools = []
    for name in module.TOOL_NAMES:
        fn: Callable[..., Any] = getattr(module.BacktestTools, name)
        schema = func_metadata(fn, skip_names=["self"]).arg_model.model_json_schema()
        tools.append(Tool(name=f"mcp:backtest/{name}", kind="mcp", version=1,
                          description=_first_line(fn), inputSchema=schema))
    return tools


def _table_tools() -> list[Tool]:
    return [Tool(name=name, kind="code", version=1, description=_first_line(_load(path)),
                 inputSchema=_SYMBOLS_INPUT, secs=secs)
            for name, (path, secs) in desk_steps.TOOL_PATHS.items()]


def seed_tools() -> list[Tool]:
    """Every tool the desk has today: steps, research skills, data recipe, table tools and
    Backtest MCP."""
    try:
        mcp = _mcp_tools()
    except Exception:  # noqa: BLE001 — Backtest tools missing must not block the other tools
        log.warning("[Tools] Backtest tools could not be read; they are set off")
        mcp = []
    return [*_step_tools(), *_research_tools(), _recipe_tool(), *_table_tools(), *mcp]


def seed_formats() -> list[TableFormat]:
    """One ``<source>.v1`` format per data recipe menu source (SRD-DSK-012.007)."""
    from us_swing.core.desk_recipes import MENU  # noqa: PLC0415 — avoids a cycle

    return [TableFormat(id=f"{key}.v1", title=source.label,
                        columns=[Column(name=col, type="number" if kind == "number" else "text",
                                        meaning=col.replace("_", " "))
                                 for col, (_, kind) in source.columns.items()])
            for key, source in MENU.items()] + [_IDEA_FIX, _SETUP_TABLE]


_IDEA_FIX = TableFormat(id="idea_fix.v1", title="Idea fix", columns=[
    Column(name="side", type="text", meaning="long or short"),
    Column(name="symbol", type="text", meaning="stock"),
    Column(name="trigger", type="number", meaning="new entry trigger price"),
    Column(name="stop", type="number", meaning="new stop price")])
_SETUP_TABLE = TableFormat(id="setup_table.v1", title="Setup table", columns=[
    Column(name="symbol", type="text", meaning="stock", by="data.daily_close"),
    Column(name="close", type="number", meaning="last daily close", by="data.daily_close"),
    Column(name="rs_rank", type="number", meaning="RS rating 1 to 99 of the latest data day",
           by="technical.rs_rank"),
    Column(name="atr_pct", type="number", meaning="14-day average true range as a percent of "
           "the close", by="technical.atr_pct"),
    Column(name="side", type="text", meaning="long or short, the better-scored side",
           by="technical.setup"),
    Column(name="setup", type="text", meaning="setup name, or none", by="technical.setup"),
    Column(name="trigger", type="number", meaning="price that confirms the setup",
           by="technical.setup"),
    Column(name="stop", type="number", meaning="price that cancels the setup",
           by="technical.setup"),
    Column(name="earn_days", type="number", meaning="trading days to the next earnings date",
           by="calendar.earnings")])


# ── store ────────────────────────────────────────────────────────────────────


def _connect(home: Path) -> sqlite3.Connection:
    home.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(home / DB_NAME, timeout=5)
    con.execute("PRAGMA busy_timeout=5000")
    con.executescript(SCHEMA)
    return con


def _tool_json(tool: Tool) -> str:
    return tool.model_dump_json(by_alias=True)


def fill_registry(home: Path, now: datetime) -> tuple[int, int]:
    """Write the seed tools and formats without copies; set gone tools off (SRD-DSK-012.009).

    Args:
        home: Desk folder holding ``desk.db``.
        now: Time written as ``updated``.

    Returns:
        Number of seed tools and seed formats.
    """
    tools, formats = seed_tools(), seed_formats()
    stamp = utc_text(now)
    con = _connect(home)
    try:
        with con:
            for tool in tools:
                con.execute(
                    "INSERT INTO tools VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(name, version) DO "
                    "UPDATE SET kind = excluded.kind, status = excluded.status, "
                    "body = excluded.body, updated = excluded.updated",
                    (tool.name, tool.version, tool.kind, tool.status, _tool_json(tool), stamp))
            for fmt in formats:
                con.execute(
                    "INSERT INTO schemas VALUES (?, ?, ?, ?) ON CONFLICT(name, version) DO "
                    "UPDATE SET body = excluded.body, updated = excluded.updated",
                    (fmt.name, fmt.version, fmt.model_dump_json(), stamp))
            seeded = {(t.name, t.version) for t in tools}
            for name, version, body in con.execute(
                    "SELECT name, version, body FROM tools WHERE status = 'active'").fetchall():
                if (name, version) not in seeded:
                    gone = {**json.loads(body), "status": "off"}
                    con.execute("UPDATE tools SET status = 'off', body = ?, updated = ? "
                                "WHERE name = ? AND version = ?",
                                (json.dumps(gone), stamp, name, version))
    finally:
        con.close()
    log.info("[Tools] Registry ready: %d tool(s), %d table format(s)", len(tools), len(formats))
    return len(tools), len(formats)


def _read(home: Path, sql: str, args: tuple[object, ...] = ()) -> list[tuple[Any, ...]]:
    path = home / DB_NAME
    if not path.exists():
        return []
    con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=2)
    try:
        return con.execute(sql, args).fetchall()
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc):
            log.warning("[Tools] Could not read the tool registry: %s", exc)
        return []
    finally:
        con.close()


def list_tools(home: Path, status: str | None = None) -> list[Tool]:
    """Registry tools by name, then version; all of them when ``status`` is None."""
    rows = (_read(home, "SELECT body FROM tools ORDER BY name, version") if status is None else
            _read(home, "SELECT body FROM tools WHERE status = ? ORDER BY name, version",
                  (status,)))
    return [Tool.model_validate_json(body) for (body,) in rows]


def get_tool(home: Path, name: str, version: int | None = None) -> Tool | None:
    """One tool by name; the newest version when ``version`` is None."""
    rows = (_read(home, "SELECT body FROM tools WHERE name = ? ORDER BY version DESC LIMIT 1",
                  (name,)) if version is None else
            _read(home, "SELECT body FROM tools WHERE name = ? AND version = ?", (name, version)))
    return Tool.model_validate_json(rows[0][0]) if rows else None


def list_formats(home: Path) -> list[TableFormat]:
    """Schema library formats by name, then version."""
    rows = _read(home, "SELECT body FROM schemas ORDER BY name, version")
    return [TableFormat.model_validate_json(body) for (body,) in rows]


def get_format(home: Path, schema_id: str) -> TableFormat | None:
    """One format by id such as ``scores.v1``; None when unknown or not an id."""
    if not re.match(SCHEMA_ID, schema_id):
        return None
    name, version = schema_id.rsplit(".v", 1)
    rows = _read(home, "SELECT body FROM schemas WHERE name = ? AND version = ?",
                 (name, int(version)))
    return TableFormat.model_validate_json(rows[0][0]) if rows else None

