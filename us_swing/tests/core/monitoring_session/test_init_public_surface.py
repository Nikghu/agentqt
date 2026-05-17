"""Tests for MD-EXE-009.002.M03 — core/monitoring_session/__init__.py public surface."""
from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import Engine

import us_swing.core.monitoring_session as _pkg
from us_swing.core.monitoring_session import (
    MonitoringCommand,
    MonitoringEventBus,
    MonitoringQuery,
    build_default_service,
)

_PKG_DIR = Path(_pkg.__file__).parent
_SRC_ROOT = _PKG_DIR.parent.parent  # us_swing/src/us_swing/


# ── UT-EXE-009.002.M03.T01 ──────────────────────────────────────────────────


def test_no_pyqt6_in_monitoring_session_package() -> None:
    """UT-EXE-009.002.M03.T01: Qt-free guarantee — no module imports PyQt6."""
    violations: list[str] = []
    for py_file in _PKG_DIR.rglob("*.py"):
        src = py_file.read_text(encoding="utf-8")
        if "PyQt6" in src or "pyqtSignal" in src:
            violations.append(str(py_file.relative_to(_PKG_DIR)))

    assert violations == [], (
        f"monitoring_session package imports PyQt6 in: {violations}"
    )


# ── UT-EXE-009.002.M03.T02 ──────────────────────────────────────────────────


def test_underscore_modules_not_imported_outside_package() -> None:
    """UT-EXE-009.002.M03.T02: Underscore-prefixed modules are not imported outside the package."""
    pattern = re.compile(r"from\s+us_swing\.core\.monitoring_session\._")
    violations: list[str] = []

    for py_file in _SRC_ROOT.rglob("*.py"):
        # Skip files that are part of the monitoring_session package itself.
        try:
            py_file.relative_to(_PKG_DIR)
            continue
        except ValueError:
            pass

        src = py_file.read_text(encoding="utf-8")
        if pattern.search(src):
            violations.append(str(py_file.relative_to(_SRC_ROOT)))

    assert violations == [], (
        f"Files outside the package import underscore modules: {violations}"
    )


# ── UT-EXE-009.002.M03.T03 ──────────────────────────────────────────────────


def test_build_default_service_returns_protocol_instances(engine: Engine) -> None:
    """UT-EXE-009.002.M03.T03: build_default_service(engine) returns three Protocol refs."""
    query, cmd, bus = build_default_service(engine)

    assert isinstance(query, MonitoringQuery)
    assert isinstance(cmd, MonitoringCommand)
    assert isinstance(bus, MonitoringEventBus)
    # query and command share the same concrete object.
    assert query is cmd


# ── UT-EXE-009.002.M03.T04 ──────────────────────────────────────────────────


def test_all_does_not_expose_underscore_names() -> None:
    """UT-EXE-009.002.M03.T04: Public __all__ does not expose any underscore-prefixed name."""
    all_exports = _pkg.__all__

    underscore_names = [name for name in all_exports if name.startswith("_")]
    assert underscore_names == [], (
        f"__all__ exposes private names: {underscore_names}"
    )

    # The concrete service class must not appear in __all__.
    assert "MonitoringSessionService" not in all_exports
