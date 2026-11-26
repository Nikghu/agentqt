"""
Module: MD-EXE-022.005.M02 — custom indicator check
Parent SRD: SRD-EXE-022.005

Reads, loads and dry-runs one indicator file before the tool uses it
(SRD-EXE-022.005–.007). Every problem is reported in plain words.
"""
from __future__ import annotations

import ast
import difflib
import re
import sys
import time
import traceback
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np
import pandas as pd

from usswing import Input, Number, USSwingIndicator
from usswing._indicator import Result, compute
from usswing._parameters import Parameter

from us_swing.core.indicator_plugins._guard import (
    DeadlineExceeded,
    PluginExit,
    call_with_deadline,
)

NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{1,31}$")
TIME_LIMIT_S = 2.0
FUTURE_CANDLES = 5
OUTPUT_TYPES = ("value", "signal")
REQUIRED_FIELDS = ("indicator_name", "description", "version", "output_type", "parameters")
LOAD_LIMIT_S = 5.0
DEV_REASON = "uses testing tools (usswing.dev); move plotting to a separate script"
FUTURE_REASON = "uses future candles (values change when newer candles arrive)"
NOT_CHECKED_NOTE = "not checked on candles (no candle data yet)"
FEW_CANDLES_NOTE = "future-candle check skipped (too few candles)"

StockFrames = tuple[str, Mapping[str, pd.DataFrame]]
CandleProbe = Callable[[], Sequence[StockFrames]]
Clock = Callable[[], float]


@dataclass(frozen=True)
class PluginSpec:
    """A custom indicator that passed the check."""

    name: str
    description: str
    version: str
    output_type: str
    parameters: tuple[Parameter, ...]
    indicator_class: type[USSwingIndicator]
    path: Path


@dataclass(frozen=True)
class CheckReport:
    """Result of checking one file: the spec when it passed, else the reasons.

    ``notes`` lists checks that could not run (for example no candle data); the file
    still loads, and the live guard protects trading.
    """

    reasons: tuple[str, ...]
    spec: PluginSpec | None = None
    notes: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.spec is not None and not self.reasons


def check_file(
    path: Path,
    *,
    builtin_names: Iterable[str] = (),
    taken_names: Iterable[str] = (),
    candle_probe: CandleProbe | None = None,
    clock: Clock = time.perf_counter,
) -> CheckReport:
    """Check one indicator file (SRD-EXE-022.005–.007).

    Args:
        path: The ``.py`` file.
        builtin_names: Names of the tool's own indicators.
        taken_names: Names of the user's other custom indicators.
        candle_probe: Gives a few stocks' candle frames for the dry run; None skips it.
        clock: Seconds counter used to time the dry run.
    """
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        return CheckReport((f"cannot read the file: {exc.strerror or exc}",))
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return CheckReport((f"syntax error on line {exc.lineno}: {exc.msg}",))

    reasons = [DEV_REASON] if _imports_dev(tree) else []
    module, load_error = _load(path, source)
    if module is None:
        return CheckReport((*reasons, load_error))
    classes = _indicator_classes(module)
    if not classes:
        return CheckReport((*reasons, "no USSwingIndicator class found"))
    if len(classes) > 1:
        names = ", ".join(cls.__name__ for cls in classes)
        return CheckReport((*reasons, f"one indicator per file — found {names}"))

    cls = classes[0]
    field_reasons = _field_problems(cls)
    reasons += field_reasons
    if not field_reasons:
        reasons += _name_problems(cls.indicator_name, builtin_names, taken_names)
        reasons += _label_problems(_labels_read(tree), cls.parameters)
    notes: list[str] = []
    if not reasons and candle_probe is not None:
        stocks = candle_probe()
        if stocks:
            dry_reasons, notes = _dry_run(cls, path, stocks, clock)
            reasons += dry_reasons
        else:
            notes.append(NOT_CHECKED_NOTE)
    if reasons:
        return CheckReport(tuple(reasons))
    return CheckReport((), PluginSpec(
        name=cls.indicator_name, description=cls.description, version=cls.version,
        output_type=cls.output_type, parameters=tuple(cls.parameters),
        indicator_class=cls, path=path), tuple(notes))


# ── Reading the code ──────────────────────────────────────────────────────────

def _imports_dev(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(a.name == "usswing.dev" or a.name.startswith("usswing.dev.")
                   for a in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "usswing.dev" or module.startswith("usswing.dev."):
                return True
            if module == "usswing" and any(a.name == "dev" for a in node.names):
                return True
    return False


def _labels_read(tree: ast.Module) -> list[str]:
    """Literal labels in ``self.parameter("...")`` calls, in order, without repeats."""
    labels: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        owner = node.func.value
        if (node.func.attr == "parameter" and isinstance(owner, ast.Name)
                and owner.id == "self" and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
                and node.args[0].value not in labels):
            labels.append(node.args[0].value)
    return labels


# ── Loading ───────────────────────────────────────────────────────────────────

def _load(path: Path, source: str) -> tuple[ModuleType | None, str]:
    """Run the file's code as a fresh module (no cached bytecode), with a time limit."""
    stem = re.sub(r"\W", "_", path.stem)
    name = f"usswing_plugin_{stem}_{abs(hash(str(path.resolve()))):x}"
    module = ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    try:
        code = compile(source, str(path), "exec")
        call_with_deadline(lambda: exec(code, module.__dict__), LOAD_LIMIT_S)  # noqa: S102
    except DeadlineExceeded:
        sys.modules.pop(name, None)
        return None, f"did not finish loading in {LOAD_LIMIT_S:g} s"
    except PluginExit:
        sys.modules.pop(name, None)
        return None, "stopped while loading (sys.exit was called)"
    except Exception as exc:  # noqa: BLE001 — any error in user code becomes a reason
        sys.modules.pop(name, None)
        return None, f"failed to load: {exc}{_line_of(exc, path)}"
    return module, ""


def _indicator_classes(module: ModuleType) -> list[type[USSwingIndicator]]:
    return [obj for obj in vars(module).values()
            if isinstance(obj, type) and issubclass(obj, USSwingIndicator)
            and obj is not USSwingIndicator and obj.__module__ == module.__name__]


def _line_of(exc: BaseException, path: Path) -> str:
    target = str(path.resolve()).lower()
    lines = [frame.lineno for frame in traceback.extract_tb(exc.__traceback__)
             if frame.filename and str(Path(frame.filename).resolve()).lower() == target]
    return f" (line {lines[-1]})" if lines else ""


# ── Fields ────────────────────────────────────────────────────────────────────

def _declared(cls: type[USSwingIndicator], field: str) -> bool:
    return any(field in vars(k) for k in cls.__mro__
               if k is not USSwingIndicator and issubclass(k, USSwingIndicator))


def _field_problems(cls: type[USSwingIndicator]) -> list[str]:
    reasons: list[str] = []
    own = [k for k in vars(cls) if not k.startswith("_") and k not in REQUIRED_FIELDS]
    for field in REQUIRED_FIELDS:
        if not _declared(cls, field):
            reasons.append(_missing(field, own))
    if reasons:
        return reasons
    name = cls.indicator_name
    if not isinstance(name, str) or not NAME_PATTERN.match(name):
        reasons.append('"indicator_name" must be capital letters, digits and _ '
                       f"(2 to 32 long, starting with a letter), got {name!r}")
    for field in ("description", "version"):
        value = getattr(cls, field)
        if not isinstance(value, str) or not value.strip():
            reasons.append(f'"{field}" must not be empty')
    if cls.output_type not in OUTPUT_TYPES:
        reasons.append(f'"output_type" must be "value" or "signal", got {cls.output_type!r}')
    reasons += _parameter_problems(cls.parameters)
    if cls.calculate is USSwingIndicator.calculate:
        reasons.append("calculate() is not written")
    return reasons


def _missing(field: str, own: list[str]) -> str:
    hint = difflib.get_close_matches(field, own, n=1, cutoff=0.4)
    if hint:
        return f'"{field}" is not set (found "{hint[0]}" — did you mean "{field}"?)'
    return f'"{field}" is not set'


def _parameter_problems(parameters: Any) -> list[str]:
    if not isinstance(parameters, (list, tuple)) or not all(
            isinstance(p, (Number, Input)) for p in parameters):
        return ['"parameters" must be a list of Number and Input']
    if not parameters:
        return ['"parameters" is empty']
    seen: set[str] = set()
    reasons: list[str] = []
    for parameter in parameters:
        if parameter.label in seen:
            reasons.append(f'two parameters are labelled "{parameter.label}"')
        seen.add(parameter.label)
    return reasons


def _name_problems(name: str, builtin_names: Iterable[str],
                   taken_names: Iterable[str]) -> list[str]:
    if name.upper() in {n.upper() for n in builtin_names}:
        return [f'name "{name}" is already used by a built-in indicator']
    if name.upper() in {n.upper() for n in taken_names}:
        return [f'name "{name}" is already used by another of your indicators']
    return []


def _label_problems(labels_read: list[str], parameters: Sequence[Parameter]) -> list[str]:
    declared = {p.label for p in parameters}
    return [f'calculate() reads parameter "{label}", but it is not in parameters'
            for label in labels_read if label not in declared]


# ── Dry run ───────────────────────────────────────────────────────────────────

def frame_source(frames: Mapping[str, pd.DataFrame]) -> Callable[[str, str], pd.DataFrame]:
    """Candle source over fixed frames; a missing timeframe raises a plain error."""
    def source(_symbol_type: str, timeframe: str) -> pd.DataFrame:
        frame = frames.get(timeframe)
        if frame is None or frame.empty:
            raise ValueError(f"No candle data for timeframe {timeframe!r}")
        return frame
    return source


def _run_once(cls: type[USSwingIndicator], frames: Mapping[str, pd.DataFrame]) -> Result:
    return call_with_deadline(lambda: compute(cls(frame_source(frames), {})), TIME_LIMIT_S)


def _dry_run(cls: type[USSwingIndicator], path: Path, stocks: Sequence[StockFrames],
             clock: Clock) -> tuple[list[str], list[str]]:
    """Reasons to refuse, and notes about checks that could not run."""
    notes: list[str] = []
    for symbol, frames in stocks:
        start = clock()
        try:
            result = _run_once(cls, frames)
        except DeadlineExceeded:
            return [f"did not finish in {TIME_LIMIT_S:g} s on {symbol}"], notes
        except Exception as exc:  # noqa: BLE001 — any error in user code becomes a reason
            return [f"failed on {symbol}: {exc}{_line_of(exc, path)}"], notes
        took = clock() - start
        if took > TIME_LIMIT_S:
            return [f"took {took:.1f} s on {symbol} (limit {TIME_LIMIT_S:g} s)"], notes
        future = _future_problem(cls, path, frames, result)
        if future == FEW_CANDLES_NOTE:
            notes.append(f"{FEW_CANDLES_NOTE} on {symbol}")
        elif future:
            return [future], notes
    return [], notes


def _future_problem(cls: type[USSwingIndicator], path: Path,
                    frames: Mapping[str, pd.DataFrame], full: Result) -> str:
    """A reason when dropping the newest candles changes older values; "" when fine."""
    main = frames[full.main_timeframe]
    if len(main) <= 2 * FUTURE_CANDLES:
        return FEW_CANDLES_NOTE
    time_col = next((c for c in ("ts", "datetime") if c in main), None)
    if time_col is not None:
        cutoff = main[time_col].iloc[-FUTURE_CANDLES]
        trimmed = {tf: (f[f[time_col] < cutoff] if time_col in f else f.iloc[:-FUTURE_CANDLES])
                   for tf, f in frames.items()}
    else:
        trimmed = {tf: f.iloc[:-FUTURE_CANDLES] for tf, f in frames.items()}
    try:
        part = _run_once(cls, trimmed)
    except Exception as exc:  # noqa: BLE001 — must also work while candles are still arriving
        return f"fails with fewer candles: {exc}{_line_of(exc, path)}"
    shared = len(part.values)
    if not np.allclose(full.values.to_numpy()[:shared], part.values.to_numpy(),
                       rtol=0.0, atol=1e-9, equal_nan=True):
        return FUTURE_REASON
    return ""
