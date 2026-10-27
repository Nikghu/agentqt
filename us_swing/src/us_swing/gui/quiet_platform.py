"""
Module: MD-GUI-000.007.M01 — gui/quiet_platform.py
Parent SRD: SRD-GUI-000.007

Stops Python 3.11 flashing a console window at start-up on Windows.

``platform.win32_ver()`` runs ``cmd /c ver`` to read the Windows version. In the
windowed (no console) app every such call flashes a console window; pandas and
keyring both trigger it at start-up. ``install()`` answers the same question from
``sys.getwindowsversion()`` instead. Call it before pandas or keyring is imported.
"""
from __future__ import annotations

import platform
import sys


def _syscmd_ver(
    system: str = "", release: str = "", version: str = "",
    supported_platforms: tuple[str, ...] = ("win32", "win16", "dos"),
) -> tuple[str, str, str]:
    major, minor, build = sys.getwindowsversion()[:3]
    return "Microsoft", "Windows", f"{major}.{minor}.{build}"


def install() -> bool:
    """Replace ``platform._syscmd_ver`` on Windows; return whether it was replaced."""
    if sys.platform != "win32":
        return False
    platform._syscmd_ver = _syscmd_ver  # type: ignore[attr-defined]
    return True
