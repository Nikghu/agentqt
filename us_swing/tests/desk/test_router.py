"""Tests for MD-DSK-003.006.M16 — desk/router.py (events, order, LangGraph run)."""
from __future__ import annotations

import logging
import os
import re
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from tests.desk.test_harness import employee, job
from us_swing.core.desk_agents import AgentContext, Facts, FeedItem
from us_swing.core.desk_events import Event, post_event
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
}
for _key, _needs in _NEEDS.items():
    globals()[f"Skill_{_key}"] = _make(_key, _needs)
PATHS = {k: f"tests.desk.test_router:Skill_{k}" for k in _NEEDS}


def _hires(home: Path, *rows: tuple[str, str, str]) -> list[Hire]:
    """Write employees as (id, skill key, trigger text) and load them."""
    for emp_id, skill, trigger in rows:
        text = job(emp_id, f"Tester {emp_id}", skill=skill).replace(
            "trigger: after_run", f"trigger: {trigger}")
        employee(home, emp_id, text)
    return load_employees(home, PATHS)


class _Wakes:
    """A wake function that records (employee id, event kind) and can fail for some ids."""

    def __init__(self, fail: set[str] | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self.fail = fail or set()

    def __call__(self, hire: Hire, event: Event) -> None:
        if hire.spec.id in self.fail:
            raise RuntimeError("boom")
        self.calls.append((hire.spec.id, event.kind))


def _router(home: Path, hires: list[Hire], wake: Any) -> Router:
    return Router(home, hires, wake, set(PATHS), lambda: NOW)


def _states(home: Path) -> list[tuple[str, str]]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute("SELECT kind, state FROM events ORDER BY id").fetchall()
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


# ---------------- LangGraph run ----------------

def test_graph_run_order(home: Path) -> None:
    """UT-DSK-003.010.M16.T01: Three experts, risk, lead: lead last, risk after setup review."""
    hires = _hires(home, ("e-lead", "lead_brief", "after_run"),
                   ("e-risk", "risk_check", "after_run"),
                   ("e-set", "setup_review", "after_run"),
                   ("e-sec", "sector_flow_view", "after_run"),
                   ("e-reg", "regime_view", "after_run"))
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


def test_own_connection_per_node(home: Path) -> None:
    """UT-DSK-003.010.M16.T03: A node on a worker thread opens its own connection; no error."""
    hires = _hires(home, ("e-1", "a", "after_run"))
    post_event(home, "after_run", "2026-11-05", NOW, 1)
    threads: list[int] = []

    def wake(hire: Hire, event: Event) -> None:
        threads.append(threading.get_ident())
        rec = Recorder(home)
        try:
            rec.add(_try(hire.spec.id, NOW))
        finally:
            rec.close()

    router = _router(home, hires, wake)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(router.handle).result()
    assert len(threads) == 1 and threads[0] != threading.main_thread().ident
    con = sqlite3.connect(home / "desk.db")
    try:
        assert con.execute("SELECT COUNT(*) FROM activity").fetchone() == (1,)
    finally:
        con.close()


def test_failed_node(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-003.011.M16.T01: One failing expert is logged; the others and the lead run."""
    hires = _hires(home, ("e-a", "a", "after_run"), ("e-b", "b", "after_run"),
                   ("e-c", "c", "after_run"))
    post_event(home, "after_run", "2026-11-05", NOW, 1)
    wake = _Wakes(fail={"e-b"})
    with caplog.at_level(logging.ERROR):
        _router(home, hires, wake).handle()
    assert [emp for emp, _ in wake.calls] == ["e-a", "e-c"]
    assert "Tester e-b failed" in caplog.text
    assert _states(home) == [("after_run", "done")]


def test_missing_view_noted(home: Path) -> None:
    """UT-DSK-003.011.M16.T02: A stale expert stays asleep; the dependent still runs and notes it."""
    hires = _hires(home, ("e-a", "regime_view", "after_run"),
                   ("e-b", "risk_check", "after_run"))
    post_event(home, "after_run", "2026-11-05", NOW, 1)
    facts: list[str] = []

    def wake(hire: Hire, event: Event) -> None:
        if hire.spec.id == "e-a":
            return
        store = MarketStore(home)
        try:
            facts.append(views_text(store, "2026-11-05", hire.skill.needs))
        finally:
            store.close()

    _router(home, hires, wake).handle()
    assert len(facts) == 1 and "Regime view: not available today" in facts[0]


# ---------------- LangGraph only in desk ----------------

def test_langgraph_available(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-DSK-003.012.M16.T01: langgraph imports and the router switches tracing off."""
    import langgraph.graph  # noqa: F401, PLC0415

    monkeypatch.setenv("LANGSMITH_TRACING", "x")
    monkeypatch.delenv("LANGSMITH_TRACING")
    hires = _hires(home, ("e-1", "a", "after_run"))
    post_event(home, "after_run", "2026-11-05", NOW, 1)
    wake = _Wakes()
    _router(home, hires, wake).handle()
    assert wake.calls and os.environ["LANGSMITH_TRACING"] == "false"


def test_only_desk_imports_langgraph() -> None:
    """UT-DSK-003.012.M16.T02: No source file outside desk/ imports langgraph."""
    src = Path(__file__).resolve().parents[2] / "src" / "us_swing"
    pattern = re.compile(r"^\s*(import|from)\s+langgraph", re.MULTILINE)
    found = [str(p.relative_to(src)) for p in src.rglob("*.py")
             if p.relative_to(src).parts[0] != "desk"
             and pattern.search(p.read_text(encoding="utf-8"))]
    assert found == []


def test_same_skill_no_edge(home: Path) -> None:
    """UT-DSK-002.008.M16.T04: Two employees with one skill do not wait for each other."""
    hires = _hires(home, ("e-1", "selfy", "after_run"), ("e-2", "selfy", "after_run"))
    assert run_order(hires, set(PATHS)) is not None


def test_graph_error_closes_event(home: Path, caplog: pytest.LogCaptureFixture,
                                  monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-DSK-003.011.M16.T03: A graph that raises is logged; the event is closed as failed."""
    hires = _hires(home, ("e-1", "a", "after_run"))
    post_event(home, "after_run", "2026-11-05", NOW, 1)

    def broken(self: Router, event: Event, woken: list[Hire]) -> None:
        raise RuntimeError("graph broke")

    monkeypatch.setattr(Router, "_run_graph", broken)
    with caplog.at_level(logging.ERROR):
        _router(home, hires, _Wakes()).handle()
    assert "graph broke" in caplog.text
    assert _notes(home) == [("done", "failed")]


def test_loop_event_closed(home: Path) -> None:
    """UT-DSK-003.010.M16.T04: An event skipped for a loop in needs is closed with that note."""
    hires = _hires(home, ("e-a", "loop_a", "after_run"), ("e-b", "loop_b", "after_run"))
    post_event(home, "after_run", "2026-11-05", NOW, 1)
    _router(home, hires, _Wakes()).handle()
    assert _notes(home) == [("done", "loop in needs")]


def _notes(home: Path) -> list[tuple[str, str]]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute("SELECT state, note FROM events").fetchall()
    finally:
        con.close()
