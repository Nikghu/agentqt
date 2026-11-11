"""Tests for MD-DSK-003.006.M16 — desk/router.py (events, order, baton chain)."""
from __future__ import annotations

import logging
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from tests.desk.test_harness import employee, job
from us_swing.core.desk_agents import AgentContext, Facts, FeedItem
from us_swing.core.desk_events import Event, open_events, post_event, waiting_count
from us_swing.desk.recorder import NY, Attempt, Recorder
from us_swing.desk.registry import Hire, load_employees
from us_swing.desk.router import Router, run_order
from us_swing.market.risk_check import views_text
from us_swing.market.store import MarketStore

NOW = datetime(2026, 11, 6, 12, 0, tzinfo=NY)


class _Answer(BaseModel):
    word: str


def _make(key: str, needs: tuple[str, ...]) -> type:
    class _Skill:
        def facts(self, home: Path) -> Facts:
            return Facts("", "2026-11-05", True)

        def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
            return []

    _Skill.key, _Skill.needs, _Skill.answer = key, needs, _Answer  # type: ignore[attr-defined]
    return _Skill


_NEEDS: dict[str, tuple[str, ...]] = {
    "a": (), "selfy": ("selfy",), "b": ("a",), "c": ("a", "b"), "ghost_user": ("ghost",),
    "loop_a": ("loop_b",), "loop_b": ("loop_a",),
    "regime_view": (), "sector_flow_view": (), "setup_review": (),
    "risk_check": ("regime_view", "sector_flow_view", "setup_review"),
    "lead_brief": ("regime_view", "sector_flow_view", "setup_review", "risk_check"),
    "lead_ab": ("a", "b"),
}
for _key, _needs in _NEEDS.items():
    globals()[f"Skill_{_key}"] = _make(_key, _needs)
PATHS = {k: f"tests.desk.test_router:Skill_{k}" for k in _NEEDS}


def _hires(home: Path, *rows: tuple[str, str, str], lead: str = "") -> list[Hire]:
    """Write employees as (id, skill key, trigger text) and load them; ``lead`` is a lead."""
    for emp_id, skill, trigger in rows:
        level = "lead" if emp_id == lead else "junior"
        text = job(emp_id, f"Tester {emp_id}", level=level, skill=skill).replace(
            "trigger: after_run", f"trigger: {trigger}")
        employee(home, emp_id, text)
    return load_employees(home, PATHS)


class _Wakes:
    """A wake function that records (employee id, event kind) and can fail for some ids.

    ``fail`` ids raise; ``bad`` maps an id to how many tries give ``failed`` before ``ok``.
    """

    def __init__(self, fail: set[str] | None = None, bad: dict[str, int] | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self.fail = fail or set()
        self.bad = dict(bad or {})
        self.retries: list[tuple[str, bool]] = []
        self.missing: dict[str, tuple[str, ...]] = {}

    def __call__(self, hire: Hire, event: Event, retry: bool, missing: tuple[str, ...]) -> str:
        emp = hire.spec.id
        self.retries.append((emp, retry))
        self.missing[emp] = missing
        if emp in self.fail:
            raise RuntimeError("boom")
        if self.bad.get(emp, 0) > 0:
            self.bad[emp] -= 1
            return "failed"
        self.calls.append((emp, event.kind))
        return "ok"


class _Clock:
    """A clock the test can move on."""

    def __init__(self, now: datetime = NOW) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def add(self, minutes: int) -> None:
        self.now += timedelta(minutes=minutes)


def _router(home: Path, hires: list[Hire], wake: Any, clock: Any = None,
            alert: Any = None) -> Router:
    return Router(home, hires, wake, set(PATHS), clock or (lambda: NOW), alert)


def _states(home: Path) -> list[tuple[str, str]]:
    """Kind and state of the trigger events (not ``step_done``)."""
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute("SELECT kind, state FROM events WHERE kind != 'step_done' "
                           "ORDER BY id").fetchall()
    finally:
        con.close()


def _steps(home: Path) -> dict[str, tuple[int, str]]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return {e: (n, r) for e, n, r in
                con.execute("SELECT employee, tries, result FROM steps").fetchall()}
    finally:
        con.close()


def _try(emp: str, started: datetime) -> Attempt:
    return Attempt(1, emp, "Tester", 1, "2026-11-05", started.isoformat(timespec="seconds"),
                   "openrouter", "m", 1, "p", "a", True, "", 1, 1, 0.0, 1.0)


# ---------------- run order from needs ----------------

def test_needs_set_order(home: Path) -> None:
    """UT-DSK-002.008.M16.T01: A comes before B (needs A), and C (needs A and B) is last."""
    hires = _hires(home, ("e-c", "c", "after_run"), ("e-b", "b", "after_run"),
                   ("e-a", "a", "after_run"))
    assert run_order(hires, set(PATHS)) == ["e-a", "e-b", "e-c"]


def test_unknown_need_key(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-002.008.M16.T02: A need nobody has is left out with a warning; the skill runs."""
    hires = _hires(home, ("e-g", "ghost_user", "after_run"))
    with caplog.at_level(logging.WARNING):
        assert run_order(hires, set(PATHS) - {"ghost"}) == ["e-g"]
    assert "needs unknown skill ghost" in caplog.text
    post_event(home, "after_run", "2026-11-05", NOW, 1)
    wake = _Wakes()
    _router(home, hires, wake).handle()
    assert wake.calls == [("e-g", "after_run")]


def test_reports_to_is_not_order(home: Path) -> None:
    """UT-DSK-002.008.M16.T03: A lead reporting to an expert still runs after that expert."""
    hires = _hires(home, ("e-lead", "b", "after_run"), ("e-exp", "a", "after_run"))
    lead_file = home / "employees" / "e-lead" / "job.yaml"
    lead_file.write_text(lead_file.read_text(encoding="utf-8").replace(
        "reports_to: null", "reports_to: e-exp"), encoding="utf-8")
    hires = load_employees(home, PATHS)
    assert {h.spec.id: h.spec.reports_to for h in hires}["e-lead"] == "e-exp"
    assert run_order(hires, set(PATHS)) == ["e-exp", "e-lead"]


# ---------------- priority, listeners, expiry ----------------

def test_priority_order(home: Path) -> None:
    """UT-DSK-003.006.M16.T01: Events posted P2, P1, P0 are handled P0, P1, P2."""
    hires = _hires(home, ("e-1", "a", "[regime_change, after_run, market_close]"))
    post_event(home, "market_close", "2026-11-06", NOW - timedelta(minutes=3))
    post_event(home, "after_run", "2026-11-06", NOW - timedelta(minutes=2), 1)
    post_event(home, "regime_change", "2026-11-06", NOW - timedelta(minutes=1))
    wake = _Wakes()
    _router(home, hires, wake).handle()
    assert [kind for _, kind in wake.calls] == ["regime_change", "after_run", "market_close"]


def test_same_priority_by_time(home: Path) -> None:
    """UT-DSK-003.006.M16.T02: Two P2 events are handled oldest first, not by row order."""
    hires = _hires(home, ("e-1", "a", "[market_open, market_close]"))
    post_event(home, "market_close", "2026-11-06", NOW - timedelta(minutes=5))
    post_event(home, "market_open", "2026-11-06", NOW - timedelta(minutes=10))
    wake = _Wakes()
    _router(home, hires, wake).handle()
    assert [kind for _, kind in wake.calls] == ["market_open", "market_close"]


def test_no_listener(home: Path) -> None:
    """UT-DSK-003.006.M16.T03: An event nobody listens to is closed; nobody is woken."""
    hires = _hires(home, ("e-1", "a", "after_run"))
    post_event(home, "market_close", "2026-11-06", NOW)
    wake = _Wakes()
    router = _router(home, hires, wake)
    assert not router.has_work()
    router.handle()
    assert wake.calls == [] and _states(home) == [("market_close", "done")]


def test_expired_event(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-003.007.M16.T01: A P2 event 31 minutes old is expired, not handled, and logged."""
    hires = _hires(home, ("e-1", "a", "market_close"))
    post_event(home, "market_close", "2026-11-06", NOW - timedelta(minutes=31))
    wake = _Wakes()
    with caplog.at_level(logging.INFO):
        _router(home, hires, wake).handle()
    assert wake.calls == [] and _states(home) == [("market_close", "expired")]
    assert "expired" in caplog.text


def test_late_event(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-003.007.M16.T02: A P0 event handled 20 minutes after posting is late and logged."""
    hires = _hires(home, ("e-1", "a", "regime_change"))
    post_event(home, "regime_change", "2026-11-06", NOW - timedelta(minutes=20))
    wake = _Wakes()
    with caplog.at_level(logging.WARNING):
        _router(home, hires, wake).handle()
    assert wake.calls == [("e-1", "regime_change")]
    assert _states(home) == [("regime_change", "late")]
    assert "handled late" in caplog.text


def test_on_time_event(home: Path) -> None:
    """UT-DSK-003.007.M16.T03: A P1 event handled after 10 minutes is done."""
    hires = _hires(home, ("e-1", "a", "after_run"))
    post_event(home, "after_run", "2026-11-06", NOW - timedelta(minutes=10), 1)
    _router(home, hires, _Wakes()).handle()
    assert _states(home) == [("after_run", "done")]


# ---------------- 30-minute rule ----------------

def test_no_wake_within_30_minutes(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-003.009.M16.T01: Woken 12 minutes ago, a P2 event does not wake it again."""
    hires = _hires(home, ("e-1", "a", "market_close"))
    rec = Recorder(home)
    rec.add(_try("e-1", NOW - timedelta(minutes=12)))
    rec.close()
    post_event(home, "market_close", "2026-11-06", NOW)
    wake = _Wakes()
    with caplog.at_level(logging.INFO):
        _router(home, hires, wake).handle()
    assert wake.calls == []
    assert "woke 12 minutes ago" in caplog.text


def test_p0_passes_30_minute_rule(home: Path) -> None:
    """UT-DSK-003.009.M16.T02: A P0 event wakes an employee woken 12 minutes ago."""
    hires = _hires(home, ("e-1", "a", "regime_change"))
    rec = Recorder(home)
    rec.add(_try("e-1", NOW - timedelta(minutes=12)))
    rec.close()
    post_event(home, "regime_change", "2026-11-06", NOW)
    wake = _Wakes()
    _router(home, hires, wake).handle()
    assert wake.calls == [("e-1", "regime_change")]


# ---------------- chain run order ----------------

def _five(home: Path) -> list[Hire]:
    return _hires(home, ("e-lead", "lead_brief", "after_run"),
                  ("e-risk", "risk_check", "after_run"),
                  ("e-set", "setup_review", "after_run"),
                  ("e-sec", "sector_flow_view", "after_run"),
                  ("e-reg", "regime_view", "after_run"), lead="e-lead")


def test_chain_run_order(home: Path) -> None:
    """UT-DSK-003.010.M16.T01: Three experts, risk, lead: lead last, risk after setup review."""
    hires = _five(home)
    post_event(home, "after_run", "2026-11-05", NOW, 1)
    wake = _Wakes()
    _router(home, hires, wake).handle()
    order = [emp for emp, _ in wake.calls]
    assert sorted(order) == sorted(h.spec.id for h in hires) and len(order) == 5
    assert order[-1] == "e-lead" and order.index("e-risk") > order.index("e-set")
    assert order.index("e-risk") == 3


def test_loop_in_needs(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-003.010.M16.T02: A needs B and B needs A: nobody is woken; one warning."""
    hires = _hires(home, ("e-a", "loop_a", "after_run"), ("e-b", "loop_b", "after_run"))
    post_event(home, "after_run", "2026-11-05", NOW, 1)
    wake = _Wakes()
    with caplog.at_level(logging.WARNING):
        _router(home, hires, wake).handle()
    assert wake.calls == []
    assert caplog.text.count("need each other in a loop") == 1


def test_whole_chain_in_one_pass(home: Path) -> None:
    """UT-DSK-003.010.M16.T03: With no failure one handle() runs the chain; all events done."""
    hires = _five(home)
    post_event(home, "after_run", "2026-11-05", NOW, 1)
    router = _router(home, hires, _Wakes())
    router.handle()
    con = sqlite3.connect(home / "desk.db")
    try:
        states = {s for (s,) in con.execute("SELECT state FROM events").fetchall()}
    finally:
        con.close()
    assert states == {"done"} and not router.has_work()
    assert {r for _, r in _steps(home).values()} == {"ok"}


def test_loop_event_closed(home: Path) -> None:
    """UT-DSK-003.010.M16.T04: An event skipped for a loop in needs is closed with that note."""
    hires = _hires(home, ("e-a", "loop_a", "after_run"), ("e-b", "loop_b", "after_run"))
    post_event(home, "after_run", "2026-11-05", NOW, 1)
    _router(home, hires, _Wakes()).handle()
    assert _notes(home) == [("done", "loop in needs")]


def test_failed_step_others_run(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-003.011.M16.T01: One expert fails 3 times: the others run; the lead runs partial."""
    hires = _five(home)
    post_event(home, "after_run", "2026-11-05", NOW, 1)
    clock = _Clock()
    wake = _Wakes(fail={"e-sec"})
    router = _router(home, hires, wake, clock)
    with caplog.at_level(logging.ERROR):
        for _ in range(3):
            router.handle()
            clock.add(5)
    ran = [emp for emp, _ in wake.calls]
    assert "e-reg" in ran and "e-set" in ran and "e-lead" in ran and "e-risk" not in ran
    assert wake.missing["e-lead"] == ("Tester e-sec", "Tester e-risk")
    assert "Tester e-sec failed" in caplog.text


def test_missing_view_noted(home: Path) -> None:
    """UT-DSK-003.011.M16.T02: A stale expert stays asleep; the dependent still runs and notes it."""
    hires = _hires(home, ("e-a", "regime_view", "after_run"),
                   ("e-b", "risk_check", "after_run"))
    post_event(home, "after_run", "2026-11-05", NOW, 1)
    facts: list[str] = []

    def wake(hire: Hire, event: Event, retry: bool, missing: tuple[str, ...]) -> str:
        if hire.spec.id == "e-a":
            return "slept"
        store = MarketStore(home)
        try:
            facts.append(views_text(store, "2026-11-05", hire.skill.needs))
        finally:
            store.close()
        return "ok"

    _router(home, hires, wake).handle()
    assert len(facts) == 1 and "Regime view: not available today" in facts[0]


def test_pass_error_closes_event(home: Path, caplog: pytest.LogCaptureFixture,
                                 monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-DSK-003.011.M16.T03: A router error outside a wake is logged; event closed as failed."""
    hires = _hires(home, ("e-1", "a", "after_run"))
    post_event(home, "after_run", "2026-11-05", NOW, 1)

    def broken(self: Router, *args: Any) -> str:
        raise RuntimeError("pass broke")

    monkeypatch.setattr(Router, "_advance", broken)
    with caplog.at_level(logging.ERROR):
        _router(home, hires, _Wakes()).handle()
    assert "pass broke" in caplog.text
    assert _notes(home) == [("done", "failed")]


# ---------------- no LangGraph ----------------

def test_no_langgraph_import() -> None:
    """UT-DSK-003.012.M16.T01: No us_swing source file imports langgraph."""
    src = Path(__file__).resolve().parents[2] / "src" / "us_swing"
    pattern = re.compile(r"^\s*(import|from)\s+langgraph", re.MULTILINE)
    found = [str(p.relative_to(src)) for p in src.rglob("*.py")
             if pattern.search(p.read_text(encoding="utf-8"))]
    assert found == []


def test_langgraph_dependency_removed() -> None:
    """UT-DSK-003.012.M16.T02: pyproject.toml and USSwing.spec name no langgraph packages."""
    root = Path(__file__).resolve().parents[3]
    for path in (root / "pyproject.toml", root / "us_swing" / "USSwing.spec"):
        text = path.read_text(encoding="utf-8")
        assert "langgraph" not in text and "langchain_core" not in text


def test_same_skill_no_edge(home: Path) -> None:
    """UT-DSK-002.008.M16.T04: Two employees with one skill do not wait for each other."""
    hires = _hires(home, ("e-1", "selfy", "after_run"), ("e-2", "selfy", "after_run"))
    assert run_order(hires, set(PATHS)) is not None


# ---------------- baton (step B) ----------------

def test_one_step_done_per_step(home: Path) -> None:
    """UT-DSK-003.014.M16.T01: A chain of 3 that all answer gives 3 step_done rows, result ok."""
    hires = _hires(home, ("e-a", "a", "after_run"), ("e-b", "b", "after_run"),
                   ("e-c", "c", "after_run"))
    post_event(home, "after_run", "2026-11-05", NOW, 1)
    _router(home, hires, _Wakes()).handle()
    con = sqlite3.connect(home / "desk.db")
    try:
        rows = con.execute("SELECT key FROM events WHERE kind = 'step_done'").fetchall()
    finally:
        con.close()
    assert len(rows) == 3
    assert _steps(home) == {"e-a": (1, "ok"), "e-b": (1, "ok"), "e-c": (1, "ok")}


def test_wake_when_need_done(home: Path) -> None:
    """UT-DSK-003.015.M16.T01: B needs A, so B is woken only after A's step is ok."""
    hires = _hires(home, ("e-b", "b", "after_run"), ("e-a", "a", "after_run"))
    post_event(home, "after_run", "2026-11-05", NOW, 1)
    wake = _Wakes()
    _router(home, hires, wake).handle()
    assert [emp for emp, _ in wake.calls] == ["e-a", "e-b"]


def test_wait_for_all_needs(home: Path) -> None:
    """UT-DSK-003.015.M16.T02: C needs A and B: woken once, after both."""
    hires = _hires(home, ("e-c", "c", "after_run"), ("e-b", "b", "after_run"),
                   ("e-a", "a", "after_run"))
    post_event(home, "after_run", "2026-11-05", NOW, 1)
    wake = _Wakes()
    _router(home, hires, wake).handle()
    assert [emp for emp, _ in wake.calls] == ["e-a", "e-b", "e-c"]


def test_need_outside_chain(home: Path) -> None:
    """UT-DSK-003.015.M16.T03: B needs a skill nobody in the chain has, so B runs at once."""
    hires = _hires(home, ("e-b", "b", "after_run"), ("e-a", "a", "market_close"))
    post_event(home, "after_run", "2026-11-05", NOW, 1)
    wake = _Wakes()
    _router(home, hires, wake).handle()
    assert wake.calls == [("e-b", "after_run")]


def test_need_not_done_yet(home: Path) -> None:
    """UT-DSK-003.015.M16.T04: A failed once and waits for its retry, so B is not woken."""
    hires = _hires(home, ("e-a", "a", "after_run"), ("e-b", "b", "after_run"))
    post_event(home, "after_run", "2026-11-05", NOW, 1)
    wake = _Wakes(bad={"e-a": 1})
    _router(home, hires, wake).handle()
    assert wake.calls == [] and _steps(home) == {"e-a": (1, "failed")}


def test_retry_after_5_minutes(home: Path) -> None:
    """UT-DSK-003.016.M16.T01: A fails once: not retried at +4 min, retried at +5; B follows."""
    hires = _hires(home, ("e-a", "a", "after_run"), ("e-b", "b", "after_run"))
    post_event(home, "after_run", "2026-11-05", NOW, 1)
    clock = _Clock()
    wake = _Wakes(bad={"e-a": 1})
    router = _router(home, hires, wake, clock)
    router.handle()
    clock.add(4)
    router.handle()
    assert len(wake.retries) == 1
    clock.add(1)
    router.handle()
    assert wake.retries == [("e-a", False), ("e-a", True), ("e-b", False)]
    assert [emp for emp, _ in wake.calls] == ["e-a", "e-b"]


def test_at_most_two_retries(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-003.016.M16.T02: A always fails: 3 wakes, the step is failed, no 4th wake."""
    hires = _hires(home, ("e-a", "a", "after_run"))
    post_event(home, "after_run", "2026-11-05", NOW, 1)
    clock = _Clock()
    wake = _Wakes(bad={"e-a": 99})
    router = _router(home, hires, wake, clock)
    with caplog.at_level(logging.WARNING):
        for _ in range(5):
            router.handle()
            clock.add(5)
    assert len(wake.retries) == 3 and _steps(home) == {"e-a": (3, "failed")}
    assert "trying again in 5 minutes (try 2 of 3)" in caplog.text
    assert "failed 3 times" in caplog.text


def test_retry_skips_wake_rules(home: Path) -> None:
    """UT-DSK-003.016.M16.T03: A retry 5 minutes after a wake passes the 30-minute rule."""
    hires = _hires(home, ("e-a", "a", "market_close"))
    post_event(home, "market_close", "2026-11-06", NOW)
    clock = _Clock()

    class _Records(_Wakes):
        def __call__(self, hire: Hire, event: Event, retry: bool,
                     missing: tuple[str, ...]) -> str:
            rec = Recorder(home)
            try:
                rec.add(_try(hire.spec.id, clock()))
            finally:
                rec.close()
            return super().__call__(hire, event, retry, missing)

    wake = _Records(bad={"e-a": 1})
    router = _router(home, hires, wake, clock)
    router.handle()
    clock.add(5)
    router.handle()
    assert wake.retries == [("e-a", False), ("e-a", True)]
    assert wake.calls == [("e-a", "market_close")]


def test_retry_wakes_the_desk(home: Path) -> None:
    """UT-DSK-003.016.M16.T04: has_work is False before the retry is due and True at due."""
    hires = _hires(home, ("e-a", "a", "after_run"))
    post_event(home, "after_run", "2026-11-05", NOW, 1)
    clock = _Clock()
    router = _router(home, hires, _Wakes(bad={"e-a": 1}), clock)
    router.handle()
    clock.add(4)
    assert not router.has_work() and waiting_count(home, clock()) == 0
    clock.add(1)
    assert router.has_work() and waiting_count(home, clock()) == 1


def test_chain_stops(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-003.017.M16.T01: A fails 3 times: B (needs A) and C (needs B) are skipped."""
    hires = _hires(home, ("e-a", "a", "after_run"), ("e-b", "b", "after_run"),
                   ("e-c", "c", "after_run"))
    post_event(home, "after_run", "2026-11-05", NOW, 1)
    clock = _Clock()
    wake = _Wakes(bad={"e-a": 99})
    router = _router(home, hires, wake, clock)
    with caplog.at_level(logging.INFO):
        for _ in range(4):
            router.handle()
            clock.add(5)
    assert wake.calls == [] and {e for e, _ in wake.retries} == {"e-a"}
    assert _steps(home)["e-b"][1] == "skipped" and _steps(home)["e-c"][1] == "skipped"
    assert caplog.text.count("Tester e-b will not run") == 1
    assert caplog.text.count("Tester e-c will not run") == 1
    assert _notes(home)[0] == ("done", "chain partial")


def test_other_branch_goes_on(home: Path) -> None:
    """UT-DSK-003.017.M16.T02: A fails 3 times; D needs nothing and still runs."""
    hires = _hires(home, ("e-a", "a", "after_run"), ("e-d", "selfy", "after_run"))
    post_event(home, "after_run", "2026-11-05", NOW, 1)
    wake = _Wakes(bad={"e-a": 99})
    _router(home, hires, wake).handle()
    assert wake.calls == [("e-d", "after_run")]


def test_lead_runs_partial(home: Path) -> None:
    """UT-DSK-003.018.M16.T01: The lead needs A and B; A fails 3 times; the lead runs after B."""
    hires = _hires(home, ("e-l", "lead_ab", "after_run"), ("e-a", "a", "after_run"),
                   ("e-b", "b", "after_run"), lead="e-l")
    post_event(home, "after_run", "2026-11-05", NOW, 1)
    clock = _Clock()
    alerts: list[str] = []
    wake = _Wakes(bad={"e-a": 99})
    router = _router(home, hires, wake, clock, lambda h, e: alerts.append(h.spec.id))
    for _ in range(4):
        router.handle()
        clock.add(5)
    assert wake.calls == [("e-l", "after_run")]
    assert wake.missing["e-l"] == ("Tester e-a", "Tester e-b")
    assert alerts == ["e-a"]


def test_lead_fails(home: Path) -> None:
    """UT-DSK-003.018.M16.T02: The lead fails 3 times: no plan; an alert for the lead."""
    hires = _hires(home, ("e-l", "lead_ab", "after_run"), ("e-a", "a", "after_run"),
                   lead="e-l")
    post_event(home, "after_run", "2026-11-05", NOW, 1)
    clock = _Clock()
    alerts: list[str] = []
    wake = _Wakes(bad={"e-l": 99})
    router = _router(home, hires, wake, clock, lambda h, e: alerts.append(h.spec.id))
    for _ in range(4):
        router.handle()
        clock.add(5)
    assert wake.calls == [("e-a", "after_run")] and alerts == ["e-l"]
    assert _steps(home)["e-l"] == (3, "failed")


def test_full_chain(home: Path) -> None:
    """UT-DSK-003.018.M16.T03: Nothing fails: the lead gets no missing names; note chain full."""
    hires = _five(home)
    post_event(home, "after_run", "2026-11-05", NOW, 1)
    wake = _Wakes()
    _router(home, hires, wake).handle()
    assert wake.missing["e-lead"] == ()
    assert _notes(home)[0] == ("done", "chain full")


def test_carry_on_after_restart(home: Path) -> None:
    """UT-DSK-003.019.M16.T01: A new router carries the chain on; finished steps are not rerun."""
    hires = _hires(home, ("e-a", "a", "after_run"), ("e-b", "b", "after_run"))
    post_event(home, "after_run", "2026-11-05", NOW, 1)
    clock = _Clock()
    first = _Wakes(bad={"e-b": 1})
    _router(home, hires, first, clock).handle()
    clock.add(5)
    second = _Wakes()
    _router(home, load_employees(home, PATHS), second, clock).handle()
    assert second.retries == [("e-b", True)] and second.calls == [("e-b", "after_run")]


def test_cut_wake(home: Path) -> None:
    """UT-DSK-003.019.M16.T02: A step left running at restart is a failed try 1, retried later."""
    hires = _hires(home, ("e-a", "a", "after_run"))
    post_event(home, "after_run", "2026-11-05", NOW, 1)
    con = open_events(home)
    try:
        with con:
            con.execute("INSERT INTO steps VALUES (1, 'e-a', 1, 'running', ?)",
                        (NOW.isoformat(timespec="seconds"),))
    finally:
        con.close()
    clock = _Clock()
    wake = _Wakes()
    router = _router(home, hires, wake, clock)
    router.handle()
    assert wake.retries == []
    clock.add(5)
    router.handle()
    assert wake.retries == [("e-a", True)] and _steps(home) == {"e-a": (2, "ok")}


def test_expired_chain(home: Path) -> None:
    """UT-DSK-003.019.M16.T03: After the trigger expired, the step_done expires; nobody wakes."""
    hires = _hires(home, ("e-a", "a", "after_run"), ("e-b", "b", "after_run"))
    post_event(home, "after_run", "2026-11-05", NOW, 1)
    clock = _Clock()
    _router(home, hires, _Wakes(bad={"e-a": 1}), clock).handle()
    clock.add(7 * 60)
    wake = _Wakes()
    alerts: list[str] = []
    _router(home, hires, wake, clock, lambda h, e: alerts.append(h.spec.id)).handle()
    assert wake.retries == [] and alerts == ["e-a"]
    con = sqlite3.connect(home / "desk.db")
    try:
        states = con.execute("SELECT state FROM events WHERE kind = 'step_done'").fetchall()
    finally:
        con.close()
    assert states == [("expired",)]


def _notes(home: Path) -> list[tuple[str, str]]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute("SELECT state, note FROM events WHERE kind != 'step_done' "
                           "ORDER BY id").fetchall()
    finally:
        con.close()
