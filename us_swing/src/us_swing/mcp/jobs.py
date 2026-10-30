"""
Module: MD-MCP-007.004.M02 — Backtest MCP jobs
Parent SRD: SRD-MCP-007.004, SRD-MCP-007.005, SRD-MCP-007.006

Runs Steps 1–3 of one plan in a background thread and keeps its state for polling.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from us_swing.backtest.service import BacktestService
from us_swing.backtest.spec import RunPlan
from us_swing.backtest.steps.stocks import StepCancelled

_log = logging.getLogger(__name__)

MAX_JOBS = 2
MAX_SECONDS = 30 * 60
STEPS = ("Stocks", "Signals", "Portfolio")


@dataclass
class Job:
    """One background run; ``state`` is running, done, failed or cancelled."""

    job_id: str
    plan: RunPlan
    started: float
    state: str = "running"
    step: str = STEPS[0]
    done: int = 0
    total: int = 0
    run_id: str = ""
    message: str = ""
    cancel_asked: bool = False
    timed_out: bool = False
    thread: threading.Thread | None = field(default=None, repr=False)

    def as_dict(self) -> dict[str, object]:
        """Status shown by ``bt_status`` (SRD-MCP-007.005)."""
        return {"job_id": self.job_id, "state": self.state, "step": self.step,
                "done": self.done, "total": self.total, "run_id": self.run_id,
                "message": self.message}


class JobManager:
    """At most ``MAX_JOBS`` running jobs; a job over ``max_seconds`` is cancelled."""

    def __init__(self, service: BacktestService, *, workers: int = 4,
                 max_seconds: float = MAX_SECONDS,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._service = service
        self._workers = workers
        self._max_seconds = max_seconds
        self._clock = clock
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def start(self, plan: RunPlan, user_id: str) -> Job:
        """Start a job in a background thread.

        Raises:
            ValueError: ``MAX_JOBS`` jobs are already running.
        """
        with self._lock:
            if sum(j.state == "running" for j in self._jobs.values()) >= MAX_JOBS:
                raise ValueError(f"{MAX_JOBS} backtests are already running; wait or cancel one")
            job = Job(uuid.uuid4().hex[:12], plan, self._clock())
            self._jobs[job.job_id] = job
        job.thread = threading.Thread(target=self._run, args=(job, user_id), daemon=True)
        job.thread.start()
        _log.info("[Backtest MCP] Backtest %s started", plan.name)
        return job

    def get(self, job_id: str) -> Job:
        """Return a job.

        Raises:
            ValueError: the job id is unknown.
        """
        job = self._jobs.get(job_id)
        if job is None:
            raise ValueError(f"No backtest job {job_id}")
        return job

    def cancel(self, job_id: str) -> Job:
        """Ask a running job to stop at its next progress step."""
        job = self.get(job_id)
        job.cancel_asked = True
        return job

    def _stop(self, job: Job) -> bool:
        if self._clock() - job.started > self._max_seconds:
            job.timed_out = True
        return job.cancel_asked or job.timed_out

    def _progress(self, job: Job, step: int) -> Callable[[int, int], None]:
        def show(done: int, total: int) -> None:
            job.step, job.done, job.total = STEPS[step], done, total
        return show

    def _run(self, job: Job, user_id: str) -> None:
        svc, plan = self._service, job.plan

        def stop() -> bool:
            return self._stop(job)

        def got_run_id(run_id: str) -> None:
            job.run_id = run_id

        try:
            daily = svc.run_stocks(plan, user_id, workers=self._workers, cancel=stop,
                                   progress=self._progress(job, 0))
            found = svc.run_signals(plan, daily, workers=self._workers, cancel=stop,
                                    progress=self._progress(job, 1))
            svc.run_portfolio(plan, daily, found, cancel=stop, started=got_run_id,
                              progress=self._progress(job, 2))
            job.state = "done"
        except StepCancelled:
            job.state = "cancelled"
            job.message = (f"Stopped at the {self._max_seconds / 60:g} minute limit"
                           if job.timed_out else "Cancelled by request")
        except Exception as exc:  # noqa: BLE001 — returned to the agent as a message
            job.state, job.message = "failed", str(exc)
            _log.warning("[Backtest MCP] Backtest %s failed: %s", plan.name, exc)
        else:
            _log.info("[Backtest MCP] Backtest %s finished", plan.name)
