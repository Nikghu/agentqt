"""Tests for MD-DSK-005.005.M17 — desk/replay.py and the replay command."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tests.desk import test_harness as th
from tests.desk.test_harness import _reset_state  # noqa: F401 - autouse fixture
from us_swing.desk.cli import main
from us_swing.desk.recorder import Attempt, Recorder, ny_now
from us_swing.desk.replay import ReplayLine, replay, report
from us_swing.desk.gateway import Reply


def _recorded(home: Path, *emp_ids: str) -> th.FakeCaller:
    """Run the desk once (run id 1) with the given employees; return the recorded caller."""
    for emp_id in emp_ids:
        th.employee(home, emp_id, th.job(emp_id, f"Tester {emp_id}"))
    caller = th.FakeCaller(*[th.GOOD] * len(emp_ids))
    th._run(th._step(caller), home)
    return caller


def _replay(home: Path, caller: th.FakeCaller, **kw: object) -> list[ReplayLine] | None:
    return replay(home, 1, settings=kw.pop("settings", th.ON),  # type: ignore[arg-type]
                  key=lambda: "key", caller=caller, skills=lambda: th.SKILLS,
                  **kw)  # type: ignore[arg-type]


def _count(home: Path, table: str) -> int:
    return int(th._rows(home, f"SELECT COUNT(*) FROM {table}")[0][0])  # noqa: S608


def test_replay_resends(home: Path) -> None:
    """UT-DSK-005.005.M17.T01: The same system and user text go out, to the recorded model."""
    first = _recorded(home, "t-1")
    second = th.FakeCaller(th.GOOD)
    lines = _replay(home, second)
    assert lines is not None and lines[0].new_valid and lines[0].old_valid
    assert second.calls == first.calls and second.calls[0][1] == "or-model"


def test_replay_options(home: Path) -> None:
    """UT-DSK-005.005.M17.T02: Employee and model options pick one employee and the model."""
    _recorded(home, "t-1", "t-2")
    second = th.FakeCaller(th.GOOD)
    lines = _replay(home, second, employee="t-2", model="other-model")
    assert lines is not None and [x.name for x in lines] == ["Tester t-2"]
    assert len(second.calls) == 1 and second.calls[0][1] == "other-model"


def test_replay_budget_applies(home: Path) -> None:
    """UT-DSK-005.005.M17.T03: With the budget used up no call is made; the report says so."""
    _recorded(home, "t-1")
    rec = Recorder(home)
    rec.add(Attempt(9, "t-9", "Tester Z", 1, "2026-11-05", ny_now().isoformat(timespec="seconds"),
                    "openrouter", "m", 1, "p", "a", True, "", 1, 1, 10.0, 1.0))
    rec.close()
    second = th.FakeCaller(th.GOOD)
    lines = _replay(home, second)
    assert lines is not None and not lines[0].new_valid and second.calls == []
    assert "not asked" in report(1, lines)


def test_replay_tries_marked(home: Path) -> None:
    """UT-DSK-005.006.M17.T01: Replay tries are stored with replay 1; the originals stay 0."""
    _recorded(home, "t-1")
    _replay(home, th.FakeCaller(th.GOOD), employee="t-1")
    assert th._rows(home, "SELECT employee, replay FROM activity ORDER BY id") == [
        ("t-1", 0), ("t-1", 1)]


def test_replay_writes_nothing_else(home: Path) -> None:
    """UT-DSK-005.006.M17.T02: Briefs, events and roster are unchanged; act is not called."""
    _recorded(home, "t-1")
    before = {t: _count(home, t) for t in ("briefs", "events", "roster")}
    acts = len(th.STATE.seen)
    _replay(home, th.FakeCaller(th.GOOD))
    assert {t: _count(home, t) for t in before} == before
    assert len(th.STATE.seen) == acts


def test_report_lines(home: Path) -> None:
    """UT-DSK-005.007.M17.T01: The ASCII report names the employee, both checks and the field."""
    _recorded(home, "t-1")
    lines = _replay(home, th.FakeCaller(Reply('{"word": "other"}', 5, 5, 0.001)))
    assert lines is not None and lines[0].changed == ("word",)
    text = report(1, lines)
    assert text.isascii() and "Tester t-1" in text
    assert "recorded valid, replay valid; changed: word" in text


def test_unknown_run(home: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """UT-DSK-005.007.M17.T02: A run with no tries gives exit code 1 and a message."""
    assert main(["replay", "99"], home) == 1
    assert "no recorded AI tries" in capsys.readouterr().out


def test_employee_gone(home: Path) -> None:
    """UT-DSK-005.007.M17.T03: A removed employee folder gives 'employee not found'; no call."""
    _recorded(home, "t-1")
    shutil.rmtree(home / "employees" / "t-1")
    second = th.FakeCaller(th.GOOD)
    lines = _replay(home, second)
    assert lines is not None and lines[0].note == "employee not found"
    assert second.calls == [] and "employee not found" in report(1, lines)


def test_replay_soul_with_rule_lines(home: Path) -> None:
    """UT-DSK-005.005.M17.T04: A soul with --- lines is split at the last separator."""
    th.employee(home, "t-1", soul="Top.\n\n---\n\nMore rules.")
    first = th.FakeCaller(th.GOOD)
    th._run(th._step(first), home)
    second = th.FakeCaller(th.GOOD)
    assert _replay(home, second) is not None
    assert second.calls == first.calls
