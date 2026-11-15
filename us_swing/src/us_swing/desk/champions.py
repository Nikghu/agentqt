"""
Module: MD-DSK-012.021.M33 — desk/champions.py
Parent SRD: SRD-DSK-012.021
Also: SRD-DSK-012.022 (a wave on up to 4 code workers), .023 (one retry, time limit)
Also: SRD-DSK-013.020 (a tool may be given as a function, such as a built tool's sandbox run)

Tool groups (AI Desk v3 M6). A tool group runs the registered tools of one task-card part
and keeps only that part's columns. This module is the only caller of tool functions; they
are loaded by import path, so ``desk`` never imports the tools' own packages. The parts of
one wave run together on a small thread pool, each with a time limit. No AI call is made
here. Design: DD-DSK-012.012.D01 §5.
"""
from __future__ import annotations

import importlib
import logging
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from us_swing.core.desk_registry import ToolResult
from us_swing.core.desk_tasks import PartStatus, PlanPart

log = logging.getLogger(__name__)

WORKERS = 4
DEFAULT_SECS = 30
OK: Final = "ok"
FAILED: Final = "failed"
SKIPPED: Final = "skipped"
ToolFn = Callable[[Path, Sequence[str]], ToolResult]
ToolRef = str | ToolFn


@dataclass(frozen=True)
class PartResult:
    """What one part gave: values by key and column, reasons, flags, and how it ended.

    ``missing`` maps ``<key>.<column>`` to the reason that value is empty. A tool's reason for
    a whole key is copied to each of that tool's columns, so two tools of one part never
    overwrite each other's reasons.
    """

    id: str
    status: PartStatus
    rows: dict[str, dict[str, Any]] = field(default_factory=dict)
    missing: dict[str, str] = field(default_factory=dict)
    flags: dict[str, str] = field(default_factory=dict)
    secs: float = 0.0
    reason: str = ""


def _load(path: ToolRef) -> ToolFn:
    if callable(path):
        return path
    module, _, name = path.partition(":")
    fn: ToolFn = getattr(importlib.import_module(module), name)
    return fn


def _call(fn: ToolFn, home: Path, keys: Sequence[str]) -> ToolResult:
    """Call a tool; a call that raises is tried once more (SRD-DSK-012.023)."""
    try:
        return fn(home, keys)
    except Exception:  # noqa: BLE001 — the second try decides
        log.debug("[Task cards] A tool call failed; trying it once more", exc_info=True)
        return fn(home, keys)


def _failed(part: PlanPart, started: float, reason: str) -> PartResult:
    return PartResult(part.id, FAILED, secs=time.monotonic() - started, reason=reason[:150])


def run_part(home: Path, part: PlanPart, keys: Sequence[str], paths: Mapping[str, ToolRef],
             key: str) -> PartResult:
    """Run the tools of one part for ``keys`` and keep only the part's columns.

    Args:
        home: Desk folder.
        part: The part: its tools and the columns each one fills.
        keys: Key values (symbols) to work.
        paths: Import path, or the function itself, of each tool by tool name.
        key: Name of the key column in the tool rows.

    Returns:
        The part's values, or a failed result with the reason.
    """
    started = time.monotonic()
    wanted = set(keys)
    rows: dict[str, dict[str, Any]] = {}
    missing: dict[str, str] = {}
    flags: dict[str, str] = {}
    for tool in sorted(part.tools):
        cols = part.tools[tool]
        path = paths.get(tool)
        try:
            fn = _load(path) if path else None
        except Exception:  # noqa: BLE001 — code that cannot be loaded is no code
            fn = None
        if fn is None:
            return _failed(part, started, f"no code for {tool}")
        try:
            result = _call(fn, home, keys)
            if result.is_error:
                return _failed(part, started, result.error.strip() or "the tool gave an error")
            for row in result.rows:
                name = str(row.get(key, ""))
                if name in wanted:
                    rows.setdefault(name, {}).update({c: row.get(c) for c in cols if c != key})
            for where, why in result.missing.items():
                if where in wanted:
                    missing.update(dict.fromkeys((f"{where}.{c}" for c in cols), why))
            missing.update({w: y for w, y in result.missing.items() if w not in wanted})
            flags.update({k: note for k, note in result.flags.items() if k in wanted})
        except Exception as exc:  # noqa: BLE001 — any tool error only fails its part
            return _failed(part, started, str(exc).strip() or "the tool hit an error")
    return PartResult(part.id, OK, rows, missing, flags, time.monotonic() - started)


def run_wave(home: Path, parts: Sequence[PlanPart], keys: Sequence[str],
             paths: Mapping[str, ToolRef], limits: Mapping[str, int],
             key: str) -> list[PartResult]:
    """Run the parts of one wave together on at most 4 workers (SRD-DSK-012.022).

    Each part may take the sum of its tools' time limits, counted from the start of the
    wave; a part that takes longer ends failed and its thread is left to end by itself.

    Returns:
        One result per part, in the order of ``parts``.
    """
    if not parts:
        return []
    started = time.monotonic()
    pool = ThreadPoolExecutor(max_workers=min(WORKERS, len(parts)),
                              thread_name_prefix="desk-tool")
    try:
        jobs = [pool.submit(run_part, home, part, keys, paths, key) for part in parts]
        out: list[PartResult] = []
        for part, job in zip(parts, jobs, strict=True):
            limit = sum(limits.get(tool, DEFAULT_SECS) for tool in part.tools)
            try:
                out.append(job.result(timeout=max(0.0, started + limit - time.monotonic())))
            except FutureTimeout:
                out.append(PartResult(part.id, FAILED, secs=float(limit),
                                      reason=f"took longer than {limit} s"))
        return out
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
