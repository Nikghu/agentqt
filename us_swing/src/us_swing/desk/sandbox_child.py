"""
Module: MD-DSK-013.011.M39 — desk/sandbox_child.py
Parent SRD: SRD-DSK-013.011
Also: SRD-DSK-013.012 (one call per stock, a reason instead of a stop), .010 (memory cap,
watchdog, and a deadline so the rows already made reach the desk)

The sandbox child (AI Desk v3 M7b). It runs in its own process, started by
``desk/sandbox.run_code()``: it caps its own memory, starts a watchdog, checks the code
against the rules again, runs it with only the safe built-ins, ``math``, a few statistics
functions and the read functions, calls ``tool(symbol)`` once per stock and sends back JSON
bytes only. The read functions are loaded by import path, so ``desk`` imports no ``market``
code. Design: DD-DSK-013.001.D01 §8.
"""
from __future__ import annotations

import builtins
import importlib
import json
import logging
import math
import os
import statistics
import sys
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Any

from us_swing.core.desk_built_tools import ALLOWED_BUILTINS, STATS_NAMES, check_code
from us_swing.core.desk_steps import TOOL_READS_PATH

log = logging.getLogger(__name__)

MEMORY_MB = 512
WATCHDOG_SLACK = 5
MAX_TEXT = 200
MAX_REASON = 120
NO_MEMORY = "the tool ran out of memory"
TOO_DEEP = "the tool went too deep"
NO_ROW = "the tool gave no row"
NO_VALUE = "no value"
WRONG = "wrong value"
CUT = "not run: the time limit was reached"
DEADLINE_SLACK = 10
MAX_INT = 2**53
_JOB_LIMIT_PROCESS_MEMORY = 0x100
_JOB_EXTENDED_LIMITS = 9


def child_env(read: Mapping[str, Callable[..., Any]]) -> dict[str, Any]:
    """The only names tool code sees: the safe built-ins, ``math``, the statistics functions
    and the read functions (SRD-DSK-013.011)."""
    safe = {name: getattr(builtins, name) for name in ALLOWED_BUILTINS}
    stats = {name: getattr(statistics, name) for name in STATS_NAMES}
    return {"__builtins__": safe, "math": math, **stats, **read}


def _limit_memory(mb: int) -> bool:
    """Put this process in a Windows job object that caps its memory; ``False`` elsewhere."""
    if sys.platform != "win32":
        log.debug("[Tool builder] No memory cap on this system")
        return False
    import ctypes  # noqa: PLC0415 — Windows only
    from ctypes import wintypes  # noqa: PLC0415

    class _Io(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in ("r", "w", "o", "rb", "wb", "ob")]

    class _Basic(ctypes.Structure):
        _fields_ = [("user_process", ctypes.c_int64), ("user_job", ctypes.c_int64),
                    ("flags", wintypes.DWORD), ("min_set", ctypes.c_size_t),
                    ("max_set", ctypes.c_size_t), ("processes", wintypes.DWORD),
                    ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD),
                    ("scheduling", wintypes.DWORD)]

    class _Extended(ctypes.Structure):
        _fields_ = [("basic", _Basic), ("io", _Io), ("process_memory", ctypes.c_size_t),
                    ("job_memory", ctypes.c_size_t), ("peak_process", ctypes.c_size_t),
                    ("peak_job", ctypes.c_size_t)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                               wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        return False
    info = _Extended()
    info.basic.flags = _JOB_LIMIT_PROCESS_MEMORY
    info.process_memory = mb * 1024 * 1024
    if not kernel.SetInformationJobObject(job, _JOB_EXTENDED_LIMITS, ctypes.byref(info),
                                          ctypes.sizeof(info)):
        return False
    return bool(kernel.AssignProcessToJobObject(job, kernel.GetCurrentProcess()))


def _watchdog(secs: float) -> None:
    """End this process after ``secs``, so a child never outlives a stopped desk."""
    def stop() -> None:
        time.sleep(secs)
        os._exit(3)

    threading.Thread(target=stop, name="tool-watchdog", daemon=True).start()


def _fits(value: object, kind: str) -> bool:
    """A number column takes a finite float or an int a float can hold exactly; a text column
    takes text up to 200 characters. A huge int never reaches ``math.isfinite``."""
    if kind == "number":
        if isinstance(value, bool):
            return False
        if isinstance(value, int):
            return abs(value) <= MAX_INT
        return isinstance(value, float) and math.isfinite(value)
    return isinstance(value, str) and len(value) <= MAX_TEXT


def _crash(exc: BaseException) -> str:
    if isinstance(exc, MemoryError):
        return NO_MEMORY
    if isinstance(exc, RecursionError):
        return TOO_DEEP
    return f"error: {type(exc).__name__}: {exc}"[:MAX_REASON]


def _row(symbol: str, out: object, columns: Sequence[Mapping[str, str]],
         missing: dict[str, str], wrong: list[str]) -> dict[str, Any] | None:
    """The stock's row of checked values, or ``None`` with its reasons in ``missing``."""
    if not isinstance(out, dict):
        missing[symbol] = NO_ROW
        return None
    kept: dict[str, Any] = {}
    for col in columns:
        name, value = col["name"], out.get(col["name"])
        where = f"{symbol}.{name}"
        if value is None:
            missing[where] = NO_VALUE
        elif not _fits(value, col["type"]):
            missing[where] = WRONG
            wrong.append(where)
        else:
            kept[name] = value
    if not kept:
        missing[symbol] = missing.get(f"{symbol}.{columns[0]['name']}", NO_VALUE)
        return None
    return {"symbol": symbol, **kept}


def run_tool(tool: Callable[[str], object], symbols: Sequence[str],
             columns: Sequence[Mapping[str, str]],
             deadline: float | None = None) -> dict[str, Any]:
    """Call ``tool`` once per stock and check each value (SRD-DSK-013.012).

    Args:
        tool: The checked ``tool`` function.
        symbols: Stocks to work, in order.
        columns: Name and type of each column.
        deadline: ``time.monotonic()`` after which no new stock starts, so the rows already
            made still reach the desk before its time limit.

    Returns:
        ``rows`` (symbol and the kept values), ``missing`` (a reason per stock or per stock
        and column), ``crashed`` (stocks whose call failed other than by a ValueError or gave
        no dict), ``wrong`` (``<symbol>.<column>`` with a value of the wrong kind) and ``cut``
        (stocks not started because the deadline passed).
    """
    rows: list[dict[str, Any]] = []
    missing: dict[str, str] = {}
    crashed: list[str] = []
    wrong: list[str] = []
    cut: list[str] = []
    for symbol in symbols:
        if deadline is not None and time.monotonic() > deadline:
            missing[symbol] = CUT
            cut.append(symbol)
            continue
        try:
            row = _row(symbol, tool(symbol), columns, missing, wrong)
        except ValueError as exc:
            missing[symbol] = str(exc)[:MAX_REASON] or "no data"
            continue
        except Exception as exc:  # noqa: BLE001 — any error only costs this stock its row
            missing[symbol] = _crash(exc)
            crashed.append(symbol)
            continue
        if row is not None:
            rows.append(row)
        elif missing.get(symbol) == NO_ROW:
            crashed.append(symbol)
    return {"rows": rows, "missing": missing, "crashed": crashed, "wrong": wrong, "cut": cut}


def _deadline(secs: float) -> float:
    """When the child stops starting new stocks, counted from the first stock: before the
    desk's limit, leaving time for the start of the process and the answer."""
    return time.monotonic() + max(secs - DEADLINE_SLACK, secs / 2)


def _run_job(spec: Mapping[str, Any], started: float) -> dict[str, Any]:
    problems = check_code(str(spec["code"]))
    if problems:
        return {"error": f"code rules: {problems[0]}"}
    module, _, attr = TOOL_READS_PATH.partition(":")
    reads = getattr(importlib.import_module(module), attr)
    backtest = Path(spec["backtest"]) if spec.get("backtest") else None
    env = child_env(reads(Path(spec["home"]), backtest))
    exec(compile(str(spec["code"]), "<tool>", "exec"), env)  # noqa: S102 — checked code, safe names only
    tool = env.get("tool")
    if not callable(tool):
        return {"error": "code rules: the code has no def tool(symbol)"}
    result = run_tool(tool, [str(s) for s in spec["symbols"]], spec["columns"],
                      _deadline(float(spec["secs"])))
    return {**result, "secs": round(time.monotonic() - started, 3), "pid": os.getpid()}


def child_main(conn: Connection, job: bytes) -> None:
    """Entry of the sandbox process: run one job and send one JSON answer (SRD-DSK-013.011).

    Args:
        conn: Sending end of the pipe to the desk.
        job: JSON bytes with code, columns, symbols, home, backtest and secs.
    """
    started = time.monotonic()
    capped = False
    try:
        spec = json.loads(job)
        capped = _limit_memory(MEMORY_MB)
        _watchdog(float(spec["secs"]) + WATCHDOG_SLACK)
        out = _run_job(spec, started)
    except Exception as exc:  # noqa: BLE001 — the desk gets the reason, not a stack
        out = {"error": f"the tool could not start: {type(exc).__name__}: {exc}"[:200]}
    out["capped"] = capped
    try:
        conn.send_bytes(json.dumps(out).encode("utf-8"))
    finally:
        conn.close()
