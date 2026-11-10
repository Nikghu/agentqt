"""Tests for MD-DSK-008.001.M22 — core/desk_employee.py, and the employee.md changes in
MD-DSK-002.002.M09 (registry), MD-DSK-006.001.M18 (hiring) and MD-DSK-005.005.M17 (replay).
Employee names here are made up."""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from tests.desk import test_harness as th
from tests.desk.test_harness import _reset_state  # noqa: F401 - autouse fixture
import us_swing
from us_swing.core import desk_employee as de
from us_swing.core.desk_ai_settings import DeskAiSettings, save_settings
from us_swing.core.desk_hiring import start_hire
from us_swing.core.desk_steps import DEFAULT_EMPLOYEE_PACKAGES, SKILL_PATHS
from us_swing.desk import registry
from us_swing.desk.recorder import Attempt, Recorder
from us_swing.desk.replay import replay

TODAY = date(2026, 11, 10)


@pytest.fixture()
def home(tmp_path: Path) -> Path:
    return tmp_path / "desk"


def _md(home: Path, emp_id: str = "t-1", level: str = "junior", prompt: str = th.SOUL) -> Path:
    """Write one employee.md (made from the test job text) and return its folder."""
    folder = home / "employees" / emp_id
    spec = de.check(__import__("yaml").safe_load(th.job(emp_id, f"Tester {emp_id}", level)))
    de.write_new(folder, spec, prompt)
    return folder


def test_read_employee_md(home: Path) -> None:
    """UT-DSK-008.001.M22.T01: employee.md gives the spec and prompt; render then parse agrees."""
    folder = _md(home)
    found = de.read_employee(folder)
    assert found is not None
    assert (found.spec.id, found.spec.name, found.spec.level) == ("t-1", "Tester t-1", "junior")
    assert found.prompt == th.SOUL
    again = de.parse(de.render(found.spec, found.prompt))
    assert again.spec == found.spec and again.prompt == found.prompt


@pytest.mark.parametrize(("text", "why"), [
    ("You are {name}.\n", "no settings block"),
    ("---\n" + th.job().replace("source: openrouter", "source: elsewhere") + "---\nHi\n",
     "models primary source"),
    ("---\n" + th.job() + "---\n\n", "the prompt is empty"),
])
def test_wrong_file(text: str, why: str) -> None:
    """UT-DSK-008.001.M22.T02: a wrong file raises ValueError with a plain reason."""
    with pytest.raises(ValueError, match=why):
        de.parse(text)


def test_registry_uses_core_rules(home: Path) -> None:
    """UT-DSK-008.002.M22.T01: the registry uses the core JobSpec, and loads employee.md."""
    assert registry.JobSpec is de.JobSpec
    _md(home)
    hires = registry.load_employees(home, th.SKILLS)
    assert [h.spec.id for h in hires] == ["t-1"] and hires[0].soul.startswith("You are Tester")


def test_core_has_no_desk_import() -> None:
    """UT-DSK-008.002.M22.T02: importing the core module loads no ``us_swing.desk`` module."""
    code = ("import sys, us_swing.core.desk_employee; "
            "print(any(m.startswith('us_swing.desk.') or m == 'us_swing.desk' "
            "for m in sys.modules))")
    env = {**os.environ, "PYTHONPATH": str(Path(us_swing.__file__).parents[1])}
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         check=True, env=env)
    assert out.stdout.strip() == "False"


def test_move_old_pair(home: Path) -> None:
    """UT-DSK-008.003.M22.T01: job.yaml + soul.md become employee.md; old files go to history."""
    folder = th.employee(home, "t-1", th.job("t-1", "Tester A"))
    assert de.migrate_all(home) == 1
    found = de.read_employee(folder)
    assert found is not None and found.spec.name == "Tester A" and found.prompt == th.SOUL
    assert found.spec.version == 1
    assert not (folder / "job.yaml").exists() and not (folder / "soul.md").exists()
    assert {p.name for p in (folder / "history").iterdir()} == {"v1-job.yaml", "v1-soul.md"}


def test_broken_old_pair_not_moved(home: Path) -> None:
    """UT-DSK-008.003.M22.T02: a broken job.yaml is not moved and the employee stays asleep."""
    folder = th.employee(home, "t-1", th.job().replace("source: openrouter", "source: x"))
    assert de.migrate_all(home) == 0
    assert (folder / "job.yaml").exists() and not (folder / "employee.md").exists()
    assert registry.load_employees(home, th.SKILLS) == []


def test_already_moved(home: Path) -> None:
    """UT-DSK-008.003.M22.T03: a folder with employee.md is left as it is."""
    folder = _md(home)
    before = (folder / "employee.md").read_bytes()
    assert de.migrate_all(home) == 0
    assert (folder / "employee.md").read_bytes() == before


def test_defaults_load(home: Path) -> None:
    """UT-DSK-008.004.M09.T01: every shipped employee seeds as employee.md and loads."""
    defaults = registry.default_folders(DEFAULT_EMPLOYEE_PACKAGES)
    assert defaults and all((f / "employee.md").exists() for f in defaults)
    registry.seed_employees(home, defaults)
    hires = registry.load_employees(home, SKILL_PATHS)
    assert len(hires) == len(defaults)
    assert all("{name}" not in h.soul for h in hires)


def test_seed_keeps_edits(home: Path) -> None:
    """UT-DSK-008.004.M09.T02: an edited employee.md is not overwritten by seeding again."""
    defaults = registry.default_folders(DEFAULT_EMPLOYEE_PACKAGES)
    registry.seed_employees(home, defaults)
    path = home / "employees" / defaults[0].name / "employee.md"
    edited = path.read_text(encoding="utf-8").replace("\n---\n", "\n---\nEdited line.\n", 1)
    path.write_text(edited, encoding="utf-8")
    assert registry.seed_employees(home, defaults) == 0
    assert path.read_text(encoding="utf-8") == edited


def test_save(home: Path) -> None:
    """UT-DSK-008.005.M22.T01: save raises the version and keeps the old file."""
    folder = _md(home)
    assert de.save_employee(home, "t-1", {"name": "Tester New"}, "You are {name}. New text.") == ""
    found = de.read_employee(folder)
    assert found is not None and found.spec.version == 2 and found.spec.name == "Tester New"
    old = de.parse((folder / "history" / "v1.md").read_text(encoding="utf-8"))
    assert old.spec.version == 1 and old.prompt == th.SOUL
    hire = registry.load_employees(home, th.SKILLS)[0]
    assert hire.soul == "You are Tester New. New text."


def test_refused_save(home: Path) -> None:
    """UT-DSK-008.005.M22.T02: a wrong value is refused; file and history are unchanged."""
    folder = _md(home)
    before = (folder / "employee.md").read_bytes()
    why = de.save_employee(home, "t-1", {"calls_per_day": 0}, th.SOUL)
    assert "calls per day" in why
    assert de.save_employee(home, "t-1", {"name": "  "}, th.SOUL) == "name: may not be empty"
    assert de.save_employee(home, "t-1", {}, "  ") == "the prompt is empty"
    assert (folder / "employee.md").read_bytes() == before
    assert not (folder / "history").exists()


def test_restore(home: Path) -> None:
    """UT-DSK-008.006.M22.T01: restoring v1 after two saves gives v4 with the v1 prompt."""
    folder = _md(home)
    de.save_employee(home, "t-1", {}, "Second {name}")
    de.save_employee(home, "t-1", {}, "Third {name}")
    assert [v.number for v in de.versions(folder)] == [3, 2, 1]
    assert de.restore(home, "t-1", 1) == ""
    found = de.read_employee(folder)
    assert found is not None and found.spec.version == 4 and found.prompt == th.SOUL
    assert [v.number for v in de.versions(folder)] == [4, 3, 2, 1]
    assert de.versions(folder)[0].current and de.restore(home, "t-1", 9) != ""


def test_hire_writes_employee_md(home: Path) -> None:
    """UT-DSK-008.007.M18.T01: a hire's folder holds employee.md, shadow, version 1."""
    new_id, reason = start_hire(home, "setup_review", "expert", "Made Up One", "claude",
                                "default", TODAY)
    assert reason == "" and new_id is not None
    folder = home / "employees" / new_id
    assert {p.name for p in folder.iterdir()} == {"employee.md"}
    found = de.read_employee(folder)
    assert found is not None and found.spec.status == "shadow" and found.spec.version == 1
    assert "{name}" in found.prompt


def test_refused_hire(home: Path) -> None:
    """UT-DSK-008.007.M18.T02: with the seats full no folder is made."""
    save_settings(DeskAiSettings(expert_cap=1), home)
    _md(home, "t-1", "expert")
    new_id, reason = start_hire(home, "setup_review", "expert", "Made Up Two", "claude",
                                "default", TODAY)
    assert new_id is None and "seats" in reason
    assert [p.name for p in (home / "employees").iterdir()] == ["t-1"]


def test_draft_replay(home: Path) -> None:
    """UT-DSK-008.008.M17.T01: the draft prompt goes out as the system text; marked replay."""
    _md(home, "t-1", prompt="You are {name}. Old words.")
    rec = Recorder(home)
    try:
        rec.add(Attempt(1, "t-1", "Tester t-1", 1, "2026-11-09", "2026-11-09T17:00:00-05:00",
                        "openrouter", "or-model", 1, "Old system\n\n---\n\nfacts text",
                        '{"word": "old"}', True, "", 10, 5, 0.001, 1.0))
    finally:
        rec.close()
    found = de.read_employee(home / "employees" / "t-1")
    assert found is not None
    draft = de.parse(de.render(found.spec, "You are {name}. Draft words."))
    caller = th.FakeCaller(th.GOOD)
    lines = replay(home, 1, "t-1", settings=th.ON, key=lambda: "key", caller=caller,
                   skills=lambda: th.SKILLS, draft=draft)
    assert lines is not None and lines[0].new_valid and '"calm"' in lines[0].answer
    assert caller.calls[0][2].startswith("You are Tester t-1. Draft words.")
    assert caller.calls[0][3] == "facts text"
    assert th._rows(home, "SELECT replay FROM activity ORDER BY id") == [(0,), (1,)]
    assert de.read_employee(home / "employees" / "t-1") == found


def test_seats_full(home: Path) -> None:
    """UT-DSK-008.009.M22.T01: junior to expert is refused when the expert seats are full."""
    save_settings(DeskAiSettings(expert_cap=1), home)
    _md(home, "t-1", "expert")
    folder = _md(home, "t-2", "junior")
    before = (folder / "employee.md").read_bytes()
    assert de.save_employee(home, "t-2", {"level": "expert"}, th.SOUL) == (
        "all 1 expert seats are taken")
    assert (folder / "employee.md").read_bytes() == before


def test_free_seat(home: Path) -> None:
    """UT-DSK-008.009.M22.T02: junior to expert is saved when an expert seat is free."""
    save_settings(DeskAiSettings(expert_cap=2), home)
    _md(home, "t-1", "expert")
    folder = _md(home, "t-2", "junior")
    assert de.save_employee(home, "t-2", {"level": "expert"}, th.SOUL) == ""
    found = de.read_employee(folder)
    assert found is not None and found.spec.level == "expert"
