"""Tests for MD-GUI-034.003.M09 — desk launch helper in core/desk_contract.py."""
from __future__ import annotations

import subprocess
from typing import Any

import pytest

from us_swing.core import desk_contract


def test_launch_is_detached(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-GUI-034.003.M09.T01: Launch is detached."""
    seen: dict[str, Any] = {}

    def fake_popen(cmd: list[str], **kw: Any) -> None:
        seen["cmd"], seen["kw"] = cmd, kw

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    desk_contract.launch_desk(resume=True)
    assert seen["cmd"][-2:] == ["desk", "--resume"]
    flags = seen["kw"]["creationflags"]
    assert flags & getattr(subprocess, "CREATE_NO_WINDOW", 0)
    assert flags & getattr(subprocess, "DETACHED_PROCESS", 0)
