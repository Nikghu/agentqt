"""
Module: MD-EXE-022.005.M02 — custom indicator check
Parent SRD: SRD-EXE-022.005

Reads, loads and dry-runs one indicator file before the tool uses it
(SRD-EXE-022.005–.007). Every problem is reported in plain words.
"""
from __future__ import annotations

import ast
import difflib
import importlib.util
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

NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{1,31}$")
TIME_LIMIT_S = 2.0
FUTURE_CANDLES = 5
OUTPUT_TYPES = ("value", "signal")
REQUIRED_FIELDS = ("indicator_name", "description", "version", "output_type", "parameters")
DEV_REASON = "uses testing tools (usswing.dev); move plotting to a separate script"
FUTURE_REASON = "uses future candles (values change when newer candles arrive)"

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
    """Result of checking one file: the spec when it passed, else the reasons."""

    reasons: tuple[str, ...]
    spec: PluginSpec | None = None

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
    module, load_error = _load(path)
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
    if not reasons and candle_probe is not None:
        reasons += _dry_run(cls, path, candle_probe(), clock)
    if reasons:
        return CheckReport(tuple(reasons))
    return CheckReport((), PluginSpec(
        name=cls.indicator_name, description=cls.description, version=cls.version,
        output_type=cls.output_type, parameters=tuple(cls.parameters),
        indicator_class=cls, path=path))


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

def _load(path: Path) -> tuple[ModuleType | None, str]:
    stem = re.sub(r"\W", "_", path.stem)
    name = f"usswing_plugin_{stem}_{abs(hash(str(path.resolve()))):x}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        return None, "cannot be loaded as a Python file"
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except SystemExit:
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


def _dry_run(cls: type[USSwingIndicator], path: Path, stocks: Sequence[StockFrames],
             clock: Clock) -> list[str]:
    for symbol, frames in stocks:
        start = clock()
        try:
            result = compute(cls(frame_source(frames), {}))
        except Exception as exc:  # noqa: BLE001 — any error in user code becomes a reason
            return [f"failed on {symbol}: {exc}{_line_of(exc, path)}"]
        took = clock() - start
        if took > TIME_LIMIT_S:
            return [f"took {took:.1f} s on {symbol} (limit {TIME_LIMIT_S:g} s)"]
        if _uses_future(cls, frames, result):
            return [FUTURE_REASON]
    return []


def _uses_future(cls: type[USSwingIndicator], frames: Mapping[str, pd.DataFrame],
                 full: Result) -> bool:
    """True when dropping the newest candles changes values of older candles."""
    main = frames[full.main_timeframe]
    if len(main) <= 2 * FUTURE_CANDLES or "ts" not in main:
        return False
    cutoff = main["ts"].iloc[-FUTURE_CANDLES]
    trimmed = {tf: (f[f["ts"] < cutoff] if "ts" in f else f.iloc[:-FUTURE_CANDLES])
               for tf, f in frames.items()}
    try:
        part = compute(cls(frame_source(trimmed), {}))
    except Exception:  # noqa: BLE001 — not a future-candle problem
        return False
    shared = len(part.values)
    return not np.allclose(full.values.to_numpy()[:shared], part.values.to_numpy(),
                           rtol=0.0, atol=1e-9, equal_nan=True)
