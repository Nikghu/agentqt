"""Tests for MD-DSK-001.020.M06 — desk/cli.py."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from us_swing.core.desk_contract import DeskState
from us_swing.desk.cli import main
from us_swing.desk.store import DeskStore


def _live(home: Path) -> DeskStore:
    s = DeskStore(home)
    s.set_state(DeskState.SLEEPING, datetime.now(UTC))
    return s


def test_status_prints_state(home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """UT-DSK-001.020.M06.T01: Status prints state."""
    s = _live(home)
    code = main(["status"], home)
    s.close()
    assert code == 0
    assert "Sleeping" in capsys.readouterr().out


def test_pause_sends_command(home: Path) -> None:
    """UT-DSK-001.020.M06.T02: Pause sends command."""
    s = _live(home)
    code = main(["pause"], home)
    cmds = s.pending_commands()
    s.close()
    assert code == 0
    assert [c.kind for c in cmds] == ["pause"]


def test_unknown_sub_command(home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """UT-DSK-001.020.M06.T03: Unknown sub-command."""
    assert main(["fly"], home) == 2
    assert "usage" in capsys.readouterr().out


def test_command_with_no_desk(home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """UT-DSK-001.020.M06.T04: Command with no desk."""
    assert main(["stop"], home) == 1
    assert "Desk is off" in capsys.readouterr().out


def test_proof_prints_report(home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """UT-DSK-001.022.M06.T01: `desk proof` prints the runner's report and exits 0."""
    seen: list[Path] = []

    def runner(where: Path) -> str:
        seen.append(where)
        return "Score proof report"

    assert main(["proof"], home, proof=lambda: runner) == 0
    assert seen == [home]
    assert "Score proof report" in capsys.readouterr().out


def test_proof_without_data(home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """UT-DSK-001.022.M06.T02: With no data `desk proof` prints a message and exits 1."""
    assert main(["proof"], home, proof=lambda: lambda _home: None) == 1
    assert "Backtest Data" in capsys.readouterr().out


def test_parent_option_gives_parent_watch(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-DSK-001.020.M06.T05: ``--parent PID`` gives the loop a parent watch (SRD-DSK-001.020)."""
    built: dict[str, Any] = {}
    seen: list[int] = []

    class FakeProcess:
        def __init__(self, *_a: Any, **kw: Any) -> None:
            built.update(kw)

        def run(self) -> int:
            return 0

    monkeypatch.setattr("us_swing.desk.cli.load_steps", lambda: [])
    monkeypatch.setattr("us_swing.desk.cli.pid_alive", lambda pid: seen.append(pid) or True)
    assert main(["--resume", "--parent", "1234"], home, process=FakeProcess) == 0
    assert built["resume"] is True
    assert built["parent_alive"]() is True and seen == [1234]
    assert main([], home, process=FakeProcess) == 0
    assert built["resume"] is False and built["parent_alive"] is None


def test_install_is_gone(home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """UT-DSK-001.020.M06.T06: ``install`` is gone (SRD-DSK-001.020)."""
    assert main(["install"], home) == 2
    out = capsys.readouterr().out
    assert "usage" in out and "install" not in out
    assert main(["--parent", "x"], home) == 2
