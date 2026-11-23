"""
Module: MD-EXE-022.008.M03 — custom indicator registry
Parent SRD: SRD-EXE-022.008

Loads the indicator files of this PC (one folder shared by all users) and keeps the
ones that pass the check (SRD-EXE-022.008–.009). A broken file is skipped and logged;
it never stops the app. Files in the old per-user folders are moved once.
"""
from __future__ import annotations

import logging
import shutil
import threading
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from us_swing.core.indicator_plugins._check import (
    CandleProbe,
    PluginSpec,
    StockFrames,
    check_file,
)

_log = logging.getLogger(__name__)

PLUGINS_ROOT = Path.home() / ".usswing" / "plugins"


def plugin_dir(root: Path | None = None) -> Path:
    """Folder of the indicator files, shared by all users (not created here)."""
    return (root or PLUGINS_ROOT) / "indicators"


def move_user_folders(root: Path | None = None) -> list[str]:
    """Move files from the old per-user folders (``<root>/<user id>/``) to the shared ones.

    A file or project whose name already exists in the shared folder is left where it is.

    Returns:
        The names that were moved.
    """
    base = root or PLUGINS_ROOT
    moved: list[str] = []
    old_folders = sorted(p for p in base.glob("*") if p.is_dir() and p.name.isdigit()) \
        if base.is_dir() else []
    for old in old_folders:
        for part in ("indicators", "projects"):
            source = old / part
            if not source.is_dir():
                continue
            target = base / part
            target.mkdir(parents=True, exist_ok=True)
            for item in sorted(source.iterdir()):
                if (target / item.name).exists():
                    _log.warning("[Indicators] %s was not moved to %s: a file with that name "
                                 "is already there", item, target)
                    continue
                try:
                    shutil.move(str(item), str(target / item.name))
                except OSError as exc:
                    _log.warning("[Indicators] %s was not moved to %s (it may be open in "
                                 "another program); trying again on the next start: %s",
                                 item, target, exc)
                    continue
                moved.append(item.name)
            _remove_if_empty(source)
        _remove_if_empty(old)
    if moved:
        _log.info("[Indicators] Moved %d item(s) to the shared indicator folders", len(moved))
    return moved


def _remove_if_empty(folder: Path) -> None:
    try:
        folder.rmdir()
    except OSError:
        pass


def builtin_names() -> frozenset[str]:
    """Names of the tool's own indicators, which a custom indicator may not reuse."""
    from us_swing.execution.strategy_engine._evaluator import ConditionEvaluator

    return frozenset(ConditionEvaluator.FUNCTION_MAP) | {"Number", "PNL"}


@dataclass(frozen=True)
class PluginStatus:
    """One file in the user's folder and whether it loaded."""

    file: str
    name: str
    version: str
    ok: bool
    reasons: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


class IndicatorRegistry:
    """The custom indicators of this PC (shared by all users), by ``indicator_name``."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or PLUGINS_ROOT
        self._lock = threading.Lock()
        self._specs: dict[str, PluginSpec] = {}
        self._statuses: tuple[PluginStatus, ...] = ()
        self._listeners: list[Callable[[], None]] = []

    def load(self, *, candle_probe: CandleProbe | None = None,
             builtins: Iterable[str] | None = None) -> None:
        """Check every ``*.py`` file of the indicator folder and keep the ones that pass."""
        move_user_folders(self.root)
        folder = plugin_dir(self.root)
        files = sorted(p for p in folder.glob("*.py") if not p.name.startswith("_")) \
            if folder.is_dir() else []
        taken_builtins = frozenset(builtins) if builtins is not None else builtin_names()
        probe = _cached(candle_probe) if candle_probe is not None else None
        specs: dict[str, PluginSpec] = {}
        statuses: list[PluginStatus] = []
        for path in files:
            report = check_file(path, builtin_names=taken_builtins, taken_names=specs,
                                candle_probe=probe)
            if report.ok and report.spec is not None:
                spec = report.spec
                specs[spec.name] = spec
                statuses.append(PluginStatus(path.name, spec.name, spec.version, True,
                                             notes=report.notes))
                for note in report.notes:
                    _log.warning("[Indicators] %s loaded, %s", path.name, note)
                continue
            statuses.append(PluginStatus(path.name, path.stem, "", False, report.reasons))
            _log.warning("[Indicators] %s was not loaded: %s", path.name, report.reasons[0])
            for reason in report.reasons[1:]:
                _log.debug("[Indicators] %s: %s", path.name, reason)
        with self._lock:
            self._specs = specs
            self._statuses = tuple(statuses)
            listeners = list(self._listeners)
        if files:
            _log.info("[Indicators] Loaded %d of %d custom indicator(s)", len(specs), len(files))
        for listener in listeners:
            listener()

    def get(self, name: str) -> PluginSpec | None:
        with self._lock:
            return self._specs.get(name)

    def names(self) -> frozenset[str]:
        with self._lock:
            return frozenset(self._specs)

    def statuses(self) -> tuple[PluginStatus, ...]:
        with self._lock:
            return self._statuses

    def add_listener(self, listener: Callable[[], None]) -> None:
        """Call ``listener`` after every load."""
        with self._lock:
            self._listeners.append(listener)

    def clear(self) -> None:
        with self._lock:
            self._specs = {}
            self._statuses = ()


def _cached(probe: CandleProbe) -> CandleProbe:
    """Read the probe stocks once per load, not once per file."""
    cache: list[Sequence[StockFrames]] = []

    def cached() -> Sequence[StockFrames]:
        if not cache:
            try:
                cache.append(list(probe()))
            except Exception:
                _log.warning("[Indicators] Could not read candles for the indicator check",
                             exc_info=True)
                cache.append([])
        return cache[0]

    return cached


REGISTRY = IndicatorRegistry()
