"""
Module: MD-GUI-000.007.M01 — tests
Parent SRD: SRD-GUI-000.007

The Windows-version check must not start cmd.exe, which flashes a console window.
"""
from __future__ import annotations

import platform
import subprocess
import sys
from collections.abc import Iterator
from typing import Any

import pytest

from us_swing.gui import quiet_platform

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


@pytest.fixture(autouse=True)
def restore_platform() -> Iterator[None]:
    original = platform._syscmd_ver  # type: ignore[attr-defined]
    yield
    platform._syscmd_ver = original  # type: ignore[attr-defined]
    platform._uname_cache = None  # type: ignore[attr-defined]


def _block_processes(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    started: list[Any] = []

    def _fail(*args: Any, **_kwargs: Any) -> Any:
        started.append(args)
        raise AssertionError("a process was started")

    monkeypatch.setattr(subprocess, "Popen", _fail)
    return started


@windows_only
def test_version_check_starts_no_process(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-GUI-000.007.M01.T01: win32_ver, uname and machine start no process once installed."""
    assert quiet_platform.install() is True
    platform._uname_cache = None  # type: ignore[attr-defined]
    started = _block_processes(monkeypatch)

    platform.win32_ver()
    platform.uname()
    platform.machine()

    assert started == []


@windows_only
def test_version_values_unchanged() -> None:
    """UT-GUI-000.007.M01.T02: the reported Windows version matches the cmd.exe answer."""
    platform._uname_cache = None  # type: ignore[attr-defined]
    real_ver, real_win32, real_uname = (
        platform._syscmd_ver(), platform.win32_ver(), platform.uname(),  # type: ignore[attr-defined]
    )

    quiet_platform.install()
    platform._uname_cache = None  # type: ignore[attr-defined]

    assert platform._syscmd_ver() == real_ver  # type: ignore[attr-defined]
    assert platform.win32_ver() == real_win32
    assert platform.uname() == real_uname


def test_other_platforms_left_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-GUI-000.007.M01.T03: off Windows nothing is replaced."""
    original = platform._syscmd_ver  # type: ignore[attr-defined]
    monkeypatch.setattr(sys, "platform", "linux")

    assert quiet_platform.install() is False
    assert platform._syscmd_ver is original  # type: ignore[attr-defined]
