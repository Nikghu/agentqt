"""Tests for the daily token split (SRD-DSK-004.006–.010, Autonomous desk step E)."""
from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from us_swing.core.desk_employee import check
from us_swing.core.desk_events import Event
from us_swing.desk.budget import Budget, Part, part_cap
from us_swing.desk.employees_step import EmployeesStep
from us_swing.desk.gateway import Gateway, Reply
from us_swing.desk.recorder import Recorder
from us_swing.desk.registry import load_employees
from tests.desk.research_support import DAY, NOW, ON, SKILLS, add_try, employee, execute, job
from tests.desk.test_harness import FakeCaller


@pytest.fixture
def home(tmp_path: Path) -> Path:
    return tmp_path / "desk"


@pytest.fixture
def rec(home: Path) -> Iterator[Recorder]:
    recorder = Recorder(home)
    yield recorder
    recorder.close()


def _budget(rec: Recorder) -> Budget:
    return Budget(rec, ON, lambda: NOW)


def _refusal(rec: Recorder, part: Part) -> str | None:
    return _budget(rec).refusal("t-1", "Tester", 50.0, 40, "claude", part)


def test_default_daily_tokens() -> None:
    """UT-DSK-004.006.M22.T01: A job without tokens_per_day gets 60,000."""
    spec = check(yaml.safe_load(job("t-1", "Tester", "junior", "fake_lead")))
    assert spec.tokens_per_day == 60_000


def test_too_small_budget() -> None:
    """UT-DSK-004.006.M22.T02: tokens_per_day 500 is refused and the field is named."""
    with pytest.raises(ValueError, match="tokens per day"):
        check(yaml.safe_load(job("t-1", "Tester", "junior", "fake_lead",
                                 extra="tokens_per_day: 500")))


def test_split() -> None:
    """UT-DSK-004.007.M12.T01: 60,000 a day splits 30,000 / 12,000 / 18,000."""
    assert [part_cap(Part(n, "t-1", "T", 60_000)) for n in ("plan", "market", "research")] == [
        30_000, 12_000, 18_000]


def test_split_odd_budget() -> None:
    """UT-DSK-004.007.M12.T02: An odd budget never splits to more than the budget."""
    caps = [part_cap(Part(n, "t-1", "T", 1_001)) for n in ("plan", "market", "research")]
    assert caps == [500, 200, 300] and sum(caps) <= 1_001


def test_part_by_event(home: Path) -> None:
    """UT-DSK-004.008.M10.T01: Watch flag and check-in wakes use the market part; others plan."""
    employee(home, "t-1", "Tester", "junior", "fake_lead")
    (hire,) = load_employees(home, SKILLS)
    step = EmployeesStep(lambda: SKILLS, lambda: [], lambda: ON, lambda: "key", FakeCaller(),
                         lambda: NOW)
    for i, kind in enumerate(("after_run", "watch_flag", "market_checkin"), start=1):
        event = Event(i, kind, 0, DAY, NOW.isoformat(), None,
                      (NOW + timedelta(hours=1)).isoformat())
        assert step._wake(hire, event, 1, home, ON) == "ok"
    con_rows = Recorder(home)
    try:
        parts = con_rows._con.execute("SELECT part, payer FROM activity ORDER BY id").fetchall()
    finally:
        con_rows.close()
    assert parts == [("plan", "t-1"), ("market", "t-1"), ("market", "t-1")]


def test_old_rows_count_as_plan(home: Path, rec: Recorder) -> None:
    """UT-DSK-004.008.M14.T01: Rows with no part or payer count in the employee's plan part."""
    execute(home, "INSERT INTO activity (employee, started, tokens_in, tokens_out, replay) "
                  "VALUES ('t-1', ?, 700, 0, 0)", (f"{DAY}T10:00:00-05:00",))
    assert rec.part_tokens(DAY, "t-1", "plan") == 700
    assert rec.part_tokens(DAY, "t-1", "market") == 0


def test_used_up_part_refuses(home: Path, rec: Recorder) -> None:
    """UT-DSK-004.009.M12.T01: A used-up market part refuses market calls, not plan calls."""
    add_try(home, "t-1", 12_000, part="market")
    assert _refusal(rec, Part("market", "t-1", "Tester", 60_000)) == (
        "Tester market-hours tokens for today used up")
    assert _refusal(rec, Part("plan", "t-1", "Tester", 60_000)) is None


def test_ticket_paid_by_raiser(home: Path, rec: Recorder) -> None:
    """UT-DSK-004.009.M12.T02: A ticket call uses the raiser's research part, not the doer's."""
    add_try(home, "t-1", 18_000, part="research", payer="t-1")
    part = Part("research", "l-1", "Lead A", 60_000, 1, 10_000)
    assert _refusal(rec, part) is None
    add_try(home, "t-1", 18_000, part="research", payer="l-1")
    assert _refusal(rec, part) == "Lead A research tokens for today used up"


def test_ticket_cap_between_tries(home: Path, rec: Recorder) -> None:
    """UT-DSK-004.009.M11.T01: A try that reaches the ticket cap stops the next try."""
    employee(home, "t-1", "Tester", "junior", "fake_lead")
    (hire,) = load_employees(home, SKILLS)
    caller = FakeCaller(Reply("not json", 900, 200, 0.0))
    part = Part("research", "l-1", "Lead A", 60_000, 5, 1_000)
    gateway = Gateway(home, hire, rec, ON, "key", 1, DAY, caller, lambda: NOW, part=part)
    from tests.desk.research_support import View

    assert gateway.ask("facts", View) is None
    assert len(caller.calls) == 1
    assert gateway.refused == "ticket 5 reached its cap of 1,000 tokens"


def test_part_refusal_log(home: Path, rec: Recorder, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-004.010.M11.T01: A used-up plan part is logged with name, part and tokens."""
    add_try(home, "t-1", 30_000)
    _refusal(rec, Part("plan", "t-1", "Tester", 60_000))
    assert "[Budget] Tester: plan tokens for today used up (30,000 of 30,000)" in caplog.text
