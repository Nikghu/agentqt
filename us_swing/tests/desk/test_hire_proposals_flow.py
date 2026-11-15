"""Flow tests for hire proposals through the desk (AI Desk v3 M7a): the weekly event, the
secretary's turn, the boss's short reply-only turn, gate 1 and the default employee.

Modules: MD-DSK-006.009.M20 (weekly event), MD-DSK-003.001.M10 (boss turn),
MD-DSK-006.016.M36 (flow) and MD-DSK-001.021.M07 (default employee). Names are made up.
"""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

import us_swing
from tests.desk import proposal_support as ps
from us_swing.core.desk_agents import AgentContext, Facts, FeedItem
from us_swing.core.desk_ai_settings import DeskAiSettings, save_settings
from us_swing.core.desk_contract import StepContext
from us_swing.core.desk_employee import read_employee
from us_swing.core.desk_hiring import employees
from us_swing.core.desk_messages import Person, accept
from us_swing.core.desk_msg import Draft
from us_swing.core.desk_proposals import AGREE, APPROVED, DISAGREE, decide_proposal, proposal_rows
from us_swing.core.desk_steps import DEFAULT_EMPLOYEE_PACKAGES, SKILL_PATHS
from us_swing.desk.employees_step import EmployeesStep
from us_swing.desk.gateway import Reply
from us_swing.desk.registry import default_folders, load_skill, seed_employees
from us_swing.desk.secretary import HireReviewSkill
from us_swing.desk.weekly_report import WeeklyReportStep

_HERE = "tests.desk.test_hire_proposals_flow"
SKILLS = {"boss_desk": f"{_HERE}:BossSkill", "hire_review": f"{_HERE}:Secretary"}
ROSTER = [Person(ps.BOSS, "Helm", "boss_desk"), Person(ps.SEC, "Ledger", "hire_review", ps.BOSS)]
CALLS: list[str] = []
ACTED: list[tuple[int, ...]] = []
VIEWS: dict[str, tuple[str, str]] = {}


class BossSkill:
    """Stands in for the boss's own skill; it only notes the inbox it is woken with."""

    key = "boss_desk"
    needs: tuple[str, ...] = ()
    answer = DeskAiSettings
    talks = True

    def facts(self, home: Path) -> Facts:
        return Facts("facts of the boss", ps.DAY, True)

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        ACTED.append(facts.inbox)
        return []


class Secretary(HireReviewSkill):
    """The real secretary with the test clock."""

    def __init__(self) -> None:
        super().__init__(clock=lambda: ps.NOW)


def _replies(user: str, verdicts: list[tuple[str, str]]) -> Reply:
    parents = sorted(int(p) for p in re.findall(r"parent (\d+)", user))
    messages = [{"type": "reply", "parent": p, "text": text, "verdict": {"result": result}}
                if result == "done" else
                {"type": "reply", "parent": p, "verdict": {"result": result, "reason": text}}
                for p, (result, text) in zip(parents, verdicts, strict=False)]
    return Reply(json.dumps({"messages": messages}), 10, 10, 0.0)


def _caller(source: str, model: str, system: str, user: str, key: str) -> Reply:
    CALLS.append(user)
    if "Hire needs found by code" in user:
        picks = [{"candidate": "C1", "source": "openrouter", "model": "m",
                  "why": "Setup review fails most mornings."}]
        return Reply(json.dumps({"picks": picks}), 10, 10, 0.0)
    if "Hire proposals from people who report to you" in user:
        return _replies(user, [VIEWS.get("first", ("done", "fits the plan")),
                               VIEWS.get("second", ("refused", "costs too much"))])
    if "Problems raised to you" in user:
        return _replies(user, [("done", "Fixed the stop.")])
    return Reply("{}", 10, 10, 0.0)


@pytest.fixture(autouse=True)
def _fresh() -> None:
    CALLS.clear()
    ACTED.clear()
    VIEWS.clear()


def _rows(home: Path, sql: str) -> list[Any]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute(sql).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        con.close()


def _step(settings: DeskAiSettings = ps.SETTINGS) -> EmployeesStep:
    return EmployeesStep(lambda: SKILLS, lambda: [], lambda: settings, lambda: "key", _caller,
                         lambda: ps.NOW)


def _run(home: Path, settings: DeskAiSettings = ps.SETTINGS) -> None:
    WeeklyReportStep(clock=lambda: ps.NOW)(StepContext(1, "manual", ps.NOW, home))
    _step(settings).handle_events(StepContext(1, "manual", ps.NOW, home))


def _asks(home: Path, count: int) -> list[int]:
    """Store ``count`` proposal asks from the secretary to the boss; return their ids."""
    if count == 2:
        ps.hire(home, "emp-g", "Gale", "skill_y")
        ps.failing(home, "emp-g")
    ps.failing(home)
    ctx = ps.Ctx(home, Secretary.answer.model_validate({"picks": [
        {"candidate": f"C{n + 1}", "source": "openrouter", "model": "m", "why": "w"}
        for n in range(count)]}))
    Secretary().act(ctx, Facts("facts", ps.DAY, True))
    out = accept(home, ctx.drafts, ps.SEC, ROSTER, ps.NOW, ps.DAY)
    return [int(o.split("#")[1]) for o in out]


# ── weekly event (SRD-DSK-006.011) ──────────────────────────────────────────


def test_weekly_event(home: Path) -> None:
    """UT-DSK-006.011.M20.T01: A new weekly report posts one ``weekly_report`` event."""
    ps.team(home)
    WeeklyReportStep(clock=lambda: ps.NOW)(StepContext(1, "manual", ps.NOW, home))
    assert _rows(home, "SELECT kind, data_day FROM events") == [("weekly_report", ps.DAY)]


def test_no_weekly_event(home: Path) -> None:
    """UT-DSK-006.011.M20.T02: No event while proposals are off, or when the week's report is
    already written."""
    ps.team(home)
    save_settings(DeskAiSettings(messages_on=True), home)
    step = WeeklyReportStep(clock=lambda: ps.NOW)
    step(StepContext(1, "manual", ps.NOW, home))
    assert _rows(home, "SELECT kind FROM events") == []
    save_settings(ps.SETTINGS, home)
    step(StepContext(2, "manual", ps.NOW, home))
    assert _rows(home, "SELECT kind FROM events") == []
    assert _rows(home, "SELECT COUNT(*) FROM desk_reports") == [(1,)]


# ── the whole flow (SRD-DSK-006.018, .024) ──────────────────────────────────


def test_flow_on_a_desk_copy(home: Path) -> None:
    """UT-DSK-006.018.M36.T03: A failing holder and a Friday run give one proposal with the
    boss's view after 2 AI calls; Approve starts the trial hire in shadow."""
    ps.team(home)
    ps.failing(home)
    _run(home)
    assert len(CALLS) == 2 and ACTED == []
    found = proposal_rows(home)
    assert [(p.skill, p.view, p.view_by, p.view_note) for p in found] == [
        ("setup_review", AGREE, ps.BOSS, "fits the plan")]
    assert [r[0:2] for r in _rows(home, "SELECT type, receiver FROM messages ORDER BY id")] == [
        ("ask", ps.BOSS), ("reply", ps.SEC)]
    assert _rows(home, "SELECT COUNT(*) FROM briefs") in ([], [(0,)])
    assert decide_proposal(home, found[0].id, "approve", ps.NOW) == ""
    trial = [e for e in employees(home) if e.status == "shadow"]
    assert [(e.skill, e.name) for e in trial] == [("setup_review", "Expert 1")]
    assert proposal_rows(home)[0].state == APPROVED


def test_off_flow(home: Path) -> None:
    """UT-DSK-006.024.M36.T02: With hire proposals off the same run posts no event, makes no
    proposal and no AI call."""
    ps.team(home)
    ps.failing(home)
    off = replace(ps.SETTINGS, hire_proposals_on=False)
    save_settings(off, home)
    _run(home, off)
    assert CALLS == [] and proposal_rows(home) == []
    assert _rows(home, "SELECT kind FROM events") == []


# ── the boss's short turn (SRD-DSK-006.020, .021) ───────────────────────────


def test_short_turn_for_proposals(home: Path) -> None:
    """UT-DSK-006.020.M10.T01: Two proposal asks take one AI call; the boss's skill does not act;
    2 replies are stored and no feed note is added."""
    ps.team(home)
    _asks(home, 2)
    _step().handle_events(StepContext(1, "manual", ps.NOW, home))
    assert len(CALLS) == 1 and ACTED == []
    assert _rows(home, "SELECT COUNT(*) FROM messages WHERE type = 'reply'") == [(2,)]
    assert _rows(home, "SELECT COUNT(*) FROM briefs") in ([], [(0,)])


def test_other_messages_as_before(home: Path) -> None:
    """UT-DSK-006.020.M10.T02: An escalation reply still gets a feed note and a plain ask still
    runs the boss's skill turn."""
    ps.team(home)
    settings = replace(ps.SETTINGS, escalation_on=True)
    save_settings(settings, home)
    accept(home, [Draft(type="escalate", to="boss", subject="Plan broken",
                        text="The stop is above the entry.")],
           ps.SEC, ROSTER, ps.NOW, ps.DAY, True)
    out = accept(home, [Draft(type="ask", to=ps.BOSS, subject="Quick check",
                              text="Is the plan fine?")], ps.SEC, ROSTER, ps.NOW, ps.DAY)
    ask_id = int(out[0].split("#")[1])
    _step(settings).handle_events(StepContext(1, "manual", ps.NOW, home))
    assert _rows(home, "SELECT COUNT(*) FROM briefs") == [(1,)]
    assert ACTED == [(ask_id,)]


def test_view_recorded(home: Path) -> None:
    """UT-DSK-006.021.M10.T01: The boss's done reply agrees and its refused reply does not, each
    with its note."""
    ps.team(home)
    _asks(home, 2)
    _step().handle_events(StepContext(1, "manual", ps.NOW, home))
    views = {p.skill: (p.view, p.view_note) for p in proposal_rows(home)}
    assert views == {"setup_review": (AGREE, "fits the plan"),
                     "skill_y": (DISAGREE, "costs too much")}


def test_boss_turn_off(home: Path) -> None:
    """UT-DSK-006.024.M10.T01: With hire proposals turned off a waiting proposal ask is refused
    by code; there is no AI call and the boss's skill does not run."""
    ps.team(home)
    _asks(home, 1)
    off = replace(ps.SETTINGS, hire_proposals_on=False)
    save_settings(off, home)
    _step(off).handle_events(StepContext(1, "manual", ps.NOW, home))
    assert CALLS == [] and ACTED == []
    bodies = [json.loads(r[0]) for r in _rows(
        home, "SELECT body FROM messages WHERE type = 'reply'")]
    assert [b["verdict"] for b in bodies] == [{"result": "refused",
                                               "reason": "hire proposals are off"}]


# ── default employee (SRD-DSK-006.025) ──────────────────────────────────────


def _shipped() -> Path:
    return Path(str(us_swing.__file__)).parent / "market" / "employees" / "emp-020"


def test_default_secretary() -> None:
    """UT-DSK-006.025.M07.T01: The shipped secretary holds hire_review and its skill loads."""
    found = read_employee(_shipped())
    assert found is not None
    s = found.spec
    assert (s.name, s.title, s.level, s.skill, s.reports_to, s.status) == (
        "Expert 15", "Desk secretary", "expert", "hire_review", "emp-005", "active")
    assert tuple(s.trigger) == ("weekly_report",)
    assert isinstance(load_skill("hire_review", SKILL_PATHS), HireReviewSkill)


def test_app_build_list() -> None:
    """UT-DSK-006.025.M07.T02: The app build list names the secretary module."""
    spec = (Path(us_swing.__file__).parents[2] / "USSwing.spec").read_text(encoding="utf-8")
    assert "'us_swing.desk.secretary'" in spec


def test_own_file_kept(tmp_path: Path) -> None:
    """UT-DSK-006.025.M07.T03: A start keeps a secretary file the Master user renamed and copies
    the default into a desk without one."""
    mine, fresh = tmp_path / "mine", tmp_path / "fresh"
    folder = mine / "employees" / "emp-020"
    shutil.copytree(_shipped(), folder)
    text = (folder / "employee.md").read_text(encoding="utf-8")
    (folder / "employee.md").write_text(text.replace("name: Expert 15", "name: Scribe"),
                                        encoding="utf-8")
    defaults = default_folders(DEFAULT_EMPLOYEE_PACKAGES)
    seed_employees(mine, defaults)
    seed_employees(fresh, defaults)
    kept = read_employee(folder)
    copied = read_employee(fresh / "employees" / "emp-020")
    assert kept is not None and kept.spec.name == "Scribe"
    assert copied is not None and copied.spec.name == "Expert 15"
