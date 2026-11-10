"""Tests for core/desk_team.py (MD-GUI-035.002.M02). Employee names are made up."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from tests.gui.team_fixtures import NEEDS, NOW, desk
from us_swing.core.desk_team import (
    day_events,
    history,
    levels,
    run_view,
    runs,
    scorecard,
    team,
)


def test_team_order_and_needs(tmp_path: Path) -> None:
    """UT-GUI-035.002.M02.T01: team in run order, needs as employee ids, columns by level."""
    desk(tmp_path, finished=True)
    members = team(tmp_path, NEEDS)
    assert [m.id for m in members] == ["emp-a", "emp-b", "emp-c", "emp-d"]
    assert members[2].needs == ("emp-a", "emp-b")
    assert members[3].on_demand and not members[0].on_demand
    assert [[m.id for m in col] for col in levels(members)] == [["emp-a", "emp-b"], ["emp-c"]]


def test_run_view_running(tmp_path: Path) -> None:
    """UT-GUI-035.004.M02.T01: running run: done, working on try 2, waiting, asleep."""
    desk(tmp_path, finished=False)
    members = team(tmp_path, NEEDS)
    run = runs(tmp_path)[0]
    assert run.ended is None
    view = run_view(tmp_path, run, members)
    assert view.ai_started is not None
    labels = {k: (s.key, s.label) for k, s in view.states.items()}
    assert labels["emp-a"] == ("done", "Done")
    assert labels["emp-b"] == ("working", "Working · try 2")
    assert labels["emp-c"] == ("waiting", "Waiting")
    assert labels["emp-d"] == ("asleep", "Asleep")


def test_run_view_finished(tmp_path: Path) -> None:
    """UT-GUI-035.004.M02.T02: finished run: backup used, no call for the one that never ran."""
    desk(tmp_path, finished=True)
    members = team(tmp_path, NEEDS)
    view = run_view(tmp_path, runs(tmp_path)[0], members)
    assert view.states["emp-b"].label == "Done · backup used"
    assert len(view.states["emp-b"].calls) == 2
    assert view.states["emp-c"].key == "skipped"


def test_events_and_scorecard(tmp_path: Path) -> None:
    """UT-GUI-035.006.M02.T01: events link their calls; scorecard sums the 30 days."""
    run_id = desk(tmp_path, finished=True)
    members = team(tmp_path, NEEDS)
    events = day_events(tmp_path, date(2026, 11, 9), members, NOW)
    by_kind = {e.kind: e for e in events}
    assert [c.run_id for c in by_kind["after_run"].calls] == [run_id] * 3
    assert [c.employee for c in by_kind["chat_question"].calls] == ["emp-d"]
    scores = scorecard(tmp_path, members, NOW)
    beta = scores[1]
    assert (beta.calls, beta.valid, beta.retries, beta.backup_calls) == (2, 1, 1, 1)
    assert beta.valid_share == 0.5 and beta.last_error == "answer missing a field"
    total = scores[-1]
    assert total.employee == "" and total.calls == 4
    assert round(total.cost_usd, 3) == 0.032
    assert [d.calls for d in history(tmp_path, "emp-b")] == [2]


def test_empty_desk(tmp_path: Path) -> None:
    """UT-GUI-035.009.M02.T01: no desk folder: everything is empty and nothing fails."""
    members = team(tmp_path, NEEDS)
    assert members == [] and runs(tmp_path) == []
    assert day_events(tmp_path, date(2026, 11, 9), members, NOW) == []
    total = scorecard(tmp_path, members, NOW)[-1]
    assert total.calls == 0 and total.valid_share is None and total.cost_per_answer is None
