"""
Module: MD-DSK-013.010.M38 — desk/sandbox.py
Parent SRD: SRD-DSK-013.010
Also: SRD-DSK-013.013 (a changed file never runs), .020 (tool functions for the planner),
.024 (a stopped run is logged)

Runs a built tool's code in a separate process (AI Desk v3 M7b). The child is started the way
the backtest workers start (``multiprocessing`` spawn; in the built app ``run_gui.py`` calls
``freeze_support()`` first), gets 60 seconds and a 512 MB memory cap, and sends back JSON
bytes only: the desk never unpickles what the child sends. ``built_fns()`` gives the planner one
tool function per enabled built tool. Design: DD-DSK-013.001.D01 §8, §12.
"""
from __future__ import annotations

import json
import logging
import multiprocessing
import sqlite3
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from pathlib import Path
from typing import Any, Protocol

from us_swing.core.desk_built_tools import (
    CHANGED,
    SECS,
    BuiltTool,
    ToolColumn,
    checked_code,
    enabled_tools,
)
from us_swing.core.desk_registry import ToolResult
from us_swing.desk.champions import ToolFn
from us_swing.desk.sandbox_child import child_main

log = logging.getLogger(__name__)

MAX_OUT = 1_000_000
BROKEN = "the tool gave a broken answer"
TOO_MUCH = "the tool gave too much output"
Target = Callable[[Connection, bytes], None]


class _Receiver(Protocol):
    """The receiving end of the pipe: a ``Connection``, or a ``PipeConnection`` on Windows."""

    def poll(self, timeout: float | None = ...) -> bool: ...

    def recv_bytes(self, maxlength: int | None = ...) -> bytes: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class RunResult:
    """What one sandbox run gave: rows, reasons, the crashed stocks and wrong values, or the
    error that ended the whole run."""

    rows: tuple[dict[str, Any], ...] = ()
    missing: dict[str, str] = field(default_factory=dict)
    crashed: tuple[str, ...] = ()
    wrong: tuple[str, ...] = ()
    secs: float = 0.0
    error: str = ""
    pid: int = 0
    cut: tuple[str, ...] = ()
    capped: bool = True


def _texts(value: object) -> tuple[str, ...]:
    return tuple(v for v in value if isinstance(v, str)) if isinstance(value, list) else ()


def _parse(data: bytes, secs: float) -> RunResult:
    """Check the child's JSON answer; anything else is a broken answer."""
    try:
        out = json.loads(data)
    except (ValueError, UnicodeDecodeError):
        return RunResult(secs=secs, error=BROKEN)
    if not isinstance(out, dict):
        return RunResult(secs=secs, error=BROKEN)
    if out.get("error"):
        return RunResult(secs=secs, error=str(out["error"])[:200])
    rows, missing = out.get("rows"), out.get("missing", {})
    if not isinstance(rows, list) or not all(
            isinstance(r, dict) and isinstance(r.get("symbol"), str) for r in rows):
        return RunResult(secs=secs, error=BROKEN)
    if not isinstance(missing, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in missing.items()):
        return RunResult(secs=secs, error=BROKEN)
    pid = out.get("pid")
    capped = out.get("capped") is not False
    if not capped:
        log.warning("[Tool builder] A tool ran without a memory cap")
    return RunResult(tuple(rows), dict(missing), _texts(out.get("crashed")),
                     _texts(out.get("wrong")), secs, "", pid if isinstance(pid, int) else 0,
                     _texts(out.get("cut")), capped)


def _ended(proc: BaseProcess) -> RunResult:
    proc.join(2)
    return RunResult(error=f"the tool process ended without an answer (exit code "
                           f"{proc.exitcode})")


def _answer(recv: _Receiver, proc: BaseProcess, secs: int, started: float) -> RunResult:
    if not recv.poll(secs):
        log.warning("[Tool builder] A tool run was stopped: took longer than %d s", secs)
        return RunResult(secs=float(secs), error=f"took longer than {secs} s")
    try:
        data = recv.recv_bytes(MAX_OUT)
    except OSError as exc:
        if "bad message length" in str(exc):
            return RunResult(error=TOO_MUCH)
        return _ended(proc)
    except EOFError:
        return _ended(proc)
    return _parse(data, round(time.monotonic() - started, 3))


def run_code(home: Path, code: str, columns: Sequence[ToolColumn], symbols: Sequence[str],
             secs: int = SECS, backtest: Path | None = None,
             target: Target = child_main) -> RunResult:
    """Run tool code for ``symbols`` in a separate process (SRD-DSK-013.010).

    Args:
        home: Desk folder, for the desk rows read function.
        code: The tool's code; the child checks it against the rules again.
        columns: The tool's columns, to check each value.
        symbols: Stocks to work.
        secs: Time limit; the process is killed after it.
        backtest: Backtest Data folder; the app's folder when ``None``.
        target: The child entry; tests pass a stand-in.

    Returns:
        The rows and reasons, or the error that ended the run.
    """
    job = json.dumps({"code": code, "columns": [{"name": c.name, "type": c.type} for c in columns],
                      "symbols": list(symbols), "home": str(home),
                      "backtest": str(backtest) if backtest else None,
                      "secs": secs}).encode("utf-8")
    ctx = multiprocessing.get_context("spawn")
    recv, send = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=target, args=(send, job), name="desk-tool", daemon=True)
    started = time.monotonic()
    proc.start()
    send.close()
    try:
        return _answer(recv, proc, secs, started)
    finally:
        recv.close()
        proc.join(2)
        if proc.is_alive():
            proc.kill()
            proc.join(2)


def _tool_fn(tool: BuiltTool, backtest: Path | None) -> ToolFn:
    def run(home: Path, symbols: Sequence[str]) -> ToolResult:
        code = checked_code(home, tool)
        if code is None:
            log.warning("[Tool builder] Tool %s v%d did not run: %s", tool.name, tool.version,
                        CHANGED)
            return ToolResult(isError=True, error=CHANGED)
        result = run_code(home, code, tool.columns, symbols, backtest=backtest)
        if result.error:
            return ToolResult(isError=True, error=result.error)
        return ToolResult(rows=list(result.rows), missing=result.missing)

    return run


def built_fns(home: Path, backtest: Path | None = None) -> dict[str, ToolFn]:
    """One tool function per enabled built tool, by registry name (SRD-DSK-013.020).

    A function never raises: a changed file or a failed run comes back as ``isError``, so the
    tool group does not try it a second time. A read error gives no built tools, so the other
    tools of a table still run.
    """
    try:
        tools = enabled_tools(home)
    except (sqlite3.Error, OSError):
        log.warning("[Tool builder] The enabled tools could not be read; they are left out")
        return {}
    return {tool.tool_name: _tool_fn(tool, backtest) for tool in tools}
