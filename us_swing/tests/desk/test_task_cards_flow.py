"""Tests for the task card flow through the desk (AI Desk v3 M6): the planner woken by a
message, the desk start, the setting, the failure log, the alert kind and the default planner.

Employee names here are made up: code must never depend on them.
"""
from __future__ import annotations

import importlib
import json
import logging
import shutil
import sqlite3
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

import us_swing
from tests.desk import task_support as ts
from tests.desk.conftest import FakeClock
from us_swing.core.desk_agents import AgentContext, Facts, FeedItem
from us_swing.core.desk_ai_settings import DeskAiSettings, load_settings, save_settings
from us_swing.core.desk_alerts import open_alerts, raise_alert
from us_swing.core.desk_contract import StepContext
from us_swing.core.desk_memory import core_block, failure_rows, log_failure, memory_rows, recall
from us_swing.core.desk_registry import fill_registry
from us_swing.core.desk_steps import DEFAULT_EMPLOYEE_PACKAGES, SKILL_PATHS, TOOL_PATHS
from us_swing.core.desk_tasks import card_rows, fill_plans, get_plan, note_result, open_card
from us_swing.desk.employees_step import EmployeesStep
from us_swing.desk.gateway import Reply
from us_swing.desk.planner import TaskPlannerSkill
from us_swing.desk.process import DeskProcess
from us_swing.desk.registry import default_folders, load_employee, load_skill, seed_employees

_HERE = "tests.desk.test_task_cards_flow"
SKILLS = {"asker": f"{_HERE}:AskerSkill", "task_planner": f"{_HERE}:Planner"}
WOKE: list[tuple[int, ...]] = []
CALLS: list[str] = []


class AskerSkill:
    """Stands in for the employee that asked; it only notes the inbox it is woken with."""

    key = "asker"
    needs: tuple[str, ...] = ()
    answer = DeskAiSettings
    talks = True

    def facts(self, home: Path) -> Facts:
        return Facts("facts of the asker", ts.DAY, True)

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        WOKE.append(facts.inbox)
        return []


class Planner(TaskPlannerSkill):
    """The real planner with the test clock and no Telegram."""

    def __init__(self) -> None:
        super().__init__(clock=lambda: ts.NOW, send=lambda _text: True)


def _caller(source: str, model: str, system: str, user: str, key: str) -> Reply:
    CALLS.append(system)
    return Reply(json.dumps({}), 10, 10, 0.0)


def _rows(home: Path, sql: str) -> list[Any]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute(sql).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        con.close()


# ── the planner woken by a message (SRD-DSK-012.018) ─────────────────────────


def test_ask_to_reply_through_the_desk(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-DSK-012.018.M34.T04: Ask to reply through the desk."""
    WOKE.clear()
    CALLS.clear()
    ts.prepare(home, monkeypatch)
    ask_id = ts.ask(home)
    step = EmployeesStep(lambda: SKILLS, lambda: [], lambda: ts.SETTINGS, lambda: "key", _caller,
                         lambda: ts.NOW)
    step.handle_events(StepContext(1, "manual", ts.NOW, home))
    rows = _rows(home, "SELECT id, type, sender, receiver, state, body FROM messages ORDER BY id")
    assert [r[1:5] for r in rows] == [("ask", ts.ASKER, ts.PLANNER, "completed"),
                                      ("reply", ts.PLANNER, ts.ASKER, "completed")]
    body = json.loads(rows[1][5])
    assert body["verdict"]["result"] == "done" and body["data"]["schema"] == ts.FORMAT
    assert [row[0] for row in body["data"]["rows"]] == ts.SIX
    assert WOKE == [(rows[1][0],)]
    assert CALLS == []
    assert _rows(home, f"SELECT COUNT(*) FROM activity WHERE employee = '{ts.PLANNER}'") in (
        [], [(0,)])
    card = card_rows(home)[0]
    assert (card.message, card.asker, card.planner, card.status, card.rows) == (
        ask_id, ts.ASKER, ts.PLANNER, "done", 6)


# ── desk start (SRD-DSK-012.016) ─────────────────────────────────────────────


def test_desk_start_makes_the_plans(home: Path, clock: FakeClock) -> None:
    """UT-DSK-012.016.M04.T01: Desk start makes the plans."""
    desk = DeskProcess(home, clock=clock, sleep=lambda _s: None)
    assert desk.start()
    desk.close()
    plan = get_plan(home, ts.FORMAT)
    assert plan is not None and plan.status == "active"


def test_desk_start_closes_cards_left_working(home: Path, clock: FakeClock) -> None:
    """UT-DSK-012.017.M04.T01: Desk start closes cards left working."""
    open_card(home, 7, ts.ASKER, ts.PLANNER, ts.FORMAT, ["symbol"], ["AVGO"], ts.NOW)
    desk = DeskProcess(home, clock=clock, sleep=lambda _s: None)
    assert desk.start()
    desk.close()
    assert [c.status for c in card_rows(home)] == ["failed"]


def test_plan_error_does_not_stop_desk(home: Path, clock: FakeClock,
                                       monkeypatch: pytest.MonkeyPatch,
                                       caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-012.016.M04.T02: Plan error does not stop the desk."""
    def broken(_home: Path, _now: object) -> int:
        raise RuntimeError("bad plan")

    monkeypatch.setattr("us_swing.desk.process.fill_plans", broken)
    desk = DeskProcess(home, clock=clock, sleep=lambda _s: None)
    with caplog.at_level(logging.ERROR):
        assert desk.start()
    desk.close()
    assert any(r.getMessage().startswith("[Task cards]") for r in caplog.records)


# ── setting (SRD-DSK-012.028) ────────────────────────────────────────────────


def test_setting(home: Path) -> None:
    """UT-DSK-012.028.M13.T01: Setting."""
    assert DeskAiSettings().task_cards_on is False
    assert load_settings(home).task_cards_on is False
    save_settings(replace(DeskAiSettings(), task_cards_on=True), home)
    assert load_settings(home).task_cards_on is True


# ── failure log (SRD-DSK-012.026) ────────────────────────────────────────────


def test_failure_row(home: Path) -> None:
    """UT-DSK-012.026.M30.T01: Failure row."""
    log_failure(home, ts.PLANNER, "Ask refused: no ready plan for scores.v1", ts.DAY, ts.NOW)
    log_failure(home, ts.PLANNER, "setup_table.v1: Calendar tools failed: timed out", ts.DAY,
                ts.NOW + timedelta(minutes=1))
    rows = failure_rows(home)
    assert [(m.owner, m.kind, m.made, m.status) for m in rows] == [
        (ts.PLANNER, "failure", ts.DAY, "active")] * 2
    assert [m.text for m in rows] == ["setup_table.v1: Calendar tools failed: timed out",
                                      "Ask refused: no ready plan for scores.v1"]
    assert len(failure_rows(home, limit=1)) == 1
    assert failure_rows(home / "nothing") == []


def test_failure_rows_stay_out_of_prompts(home: Path) -> None:
    """UT-DSK-012.026.M30.T02: Failure rows stay out of prompts."""
    log_failure(home, ts.PLANNER, "setup_table.v1: Calendar tools failed: timed out", ts.DAY,
                ts.NOW)
    assert core_block(home, ts.PLANNER, ts.DAY) == ""
    assert recall(home, ts.PLANNER, "Calendar tools failed: timed out", ts.DAY) == ""
    assert memory_rows(home, "note", "active", ts.PLANNER) == []
    assert memory_rows(home, "view", "open", ts.PLANNER) == []


# ── alert kind (SRD-DSK-012.027) ─────────────────────────────────────────────


def test_alert_kind(home: Path) -> None:
    """UT-DSK-012.027.M21.T01: Alert kind."""
    sent: list[str] = []
    alert = raise_alert(home, "plan_retired", ts.FORMAT, 0, "failed 3 times", ts.NOW,
                        lambda text: sent.append(text) is None)
    assert alert is not None and alert.title == "Table plan retired"
    assert "Restart the desk" in alert.fix and "AI Desk → Tools" in alert.fix
    assert len(sent) == 1 and "failed 3 times" in sent[0]


def test_alert_closes_when_the_plan_is_active_again(home: Path) -> None:
    """UT-DSK-012.027.M21.T02: Alert closes when the plan is active again."""
    fill_registry(home, ts.NOW)
    fill_plans(home, ts.NOW)
    for _ in range(3):
        note_result(home, ts.FORMAT, True, "feed is down", ts.NOW)
    raise_alert(home, "plan_retired", ts.FORMAT, 0, "failed 3 times", ts.NOW, lambda _t: True)
    assert [a.kind for a in open_alerts(home, ts.NOW)] == ["plan_retired"]
    fill_plans(home, ts.NOW)
    assert open_alerts(home, ts.NOW) == []


# ── default planner employee and app build (SRD-DSK-012.029) ─────────────────


def _default_planner() -> Path:
    return next(f for f in default_folders(DEFAULT_EMPLOYEE_PACKAGES) if f.name == "emp-019")


def test_default_planner_employee() -> None:
    """UT-DSK-012.029.M07.T01: Default planner employee."""
    hire = load_employee(_default_planner(), SKILL_PATHS)
    assert hire is not None
    spec = hire.spec
    assert (spec.level, spec.skill, spec.trigger, spec.status) == (
        "champion", "task_planner", ("message",), "active")
    skill = load_skill("task_planner", SKILL_PATHS)
    assert skill is not None and skill.key == "task_planner"
    for path, secs in TOOL_PATHS.values():
        module, _, name = path.partition(":")
        assert callable(getattr(importlib.import_module(module), name)) and secs >= 1


def test_user_copy_kept(home: Path) -> None:
    """UT-DSK-012.029.M07.T02: User copy kept."""
    target = home / "employees" / "emp-019"
    shutil.copytree(_default_planner(), target)
    file = target / "employee.md"
    changed = file.read_text(encoding="utf-8").replace("name: Champion 1", "name: Table Maker")
    assert "name: Table Maker" in changed
    file.write_text(changed, encoding="utf-8")
    seed_employees(home, default_folders(DEFAULT_EMPLOYEE_PACKAGES))
    assert file.read_text(encoding="utf-8") == changed


def test_app_build_holds_the_modules() -> None:
    """UT-DSK-012.029.M07.T03: App build holds the modules."""
    spec = (Path(us_swing.__file__).parents[2] / "USSwing.spec").read_text(encoding="utf-8")
    assert "'us_swing.desk.planner'" in spec and "'us_swing.market.table_tools'" in spec
