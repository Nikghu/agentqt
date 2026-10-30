"""Tests for SRD-MCP-007.004–.006 — MD-MCP-007.004.M02 (backtest MCP jobs)."""
from __future__ import annotations

import threading
from datetime import date
from typing import Any

import pytest

from us_swing.backtest.spec import Period, RunPlan
from us_swing.backtest.steps.stocks import StepCancelled
from us_swing.mcp.jobs import JobManager

_PLAN = RunPlan(name="t", period=Period(date(2025, 3, 3), date(2025, 3, 7)))


class _FakeService:
    """Steps 1–3 stand-in; Step 1 waits on ``gate`` and checks ``cancel`` while waiting."""

    def __init__(self, fail: str = "") -> None:
        self.gate = threading.Event()
        self.fail = fail

    def run_stocks(self, plan: RunPlan, user_id: str, *, cancel: Any, progress: Any,
                   **_: Any) -> str:
        progress(1, 4)
        while not self.gate.wait(0.01):
            if cancel():
                raise StepCancelled
        return "daily"

    def run_signals(self, plan: RunPlan, daily: str, **_: Any) -> str:
        if self.fail:
            raise ValueError(self.fail)
        return "found"

    def run_portfolio(self, plan: RunPlan, daily: str, found: str, *, started: Any,
                      progress: Any, **_: Any) -> list[Any]:
        started("run-1")
        progress(4, 4)
        return []


def _finish(jobs: JobManager, job_id: str) -> dict[str, object]:
    thread = jobs.get(job_id).thread
    assert thread is not None
    thread.join(5)
    return jobs.get(job_id).as_dict()


def test_job_runs_to_done() -> None:
    """UT-MCP-007.004.M02.T01: A job runs Steps 1–3, shows progress and gets the run id."""
    svc = _FakeService()
    jobs = JobManager(svc, workers=0)  # type: ignore[arg-type]
    job = jobs.start(_PLAN, "admin")
    assert job.as_dict()["state"] == "running"
    svc.gate.set()

    status = _finish(jobs, job.job_id)

    assert status["state"] == "done"
    assert status["run_id"] == "run-1"
    assert (status["step"], status["done"], status["total"]) == ("Portfolio", 4, 4)


def test_cancel_and_failure() -> None:
    """UT-MCP-007.006.M02.T01: Cancel stops a job; a failed step gives its message."""
    jobs = JobManager(_FakeService(), workers=0)  # type: ignore[arg-type]
    job = jobs.start(_PLAN, "admin")
    jobs.cancel(job.job_id)
    status = _finish(jobs, job.job_id)
    assert (status["state"], status["message"]) == ("cancelled", "Cancelled by request")

    svc = _FakeService(fail="Strategy X is not in the strategy list")
    svc.gate.set()
    jobs = JobManager(svc, workers=0)  # type: ignore[arg-type]
    status = _finish(jobs, jobs.start(_PLAN, "admin").job_id)
    assert (status["state"], status["message"]) == ("failed",
                                                    "Strategy X is not in the strategy list")
    with pytest.raises(ValueError, match="No backtest job"):
        jobs.get("nope")


def test_time_limit_and_job_limit() -> None:
    """UT-MCP-007.005.M02.T01: A job over the time limit is stopped; a third job is refused."""
    now = [0.0]
    jobs = JobManager(_FakeService(), workers=0, max_seconds=60,  # type: ignore[arg-type]
                      clock=lambda: now[0])
    first = jobs.start(_PLAN, "admin")
    second = jobs.start(_PLAN, "admin")
    with pytest.raises(ValueError, match="2 backtests are already running"):
        jobs.start(_PLAN, "admin")

    now[0] = 61.0
    assert _finish(jobs, first.job_id)["message"] == "Stopped at the 1 minute limit"
    assert _finish(jobs, second.job_id)["state"] == "cancelled"
