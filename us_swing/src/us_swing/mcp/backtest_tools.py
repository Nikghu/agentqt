"""
Module: MD-MCP-007.001.M01 — Backtest MCP tools
Parent SRD: SRD-MCP-007.001 – SRD-MCP-007.010

The 8 backtest tools and the stdio server that lists them. Every tool calls
``BacktestService``; results go to the same ``results.db`` as the app.
"""
from __future__ import annotations

import functools
import json
import logging
import math
from collections.abc import Callable, Sequence
from typing import Any

import pandas as pd
from mcp.server.fastmcp import FastMCP

from us_swing.backtest.service import BacktestService
from us_swing.backtest.spec import RunPlan
from us_swing.backtest.steps import report
from us_swing.backtest.universe import UniverseRecord
from us_swing.core.backtest_bridge import PresetInfo
from us_swing.mcp.jobs import JobManager

_log = logging.getLogger(__name__)

SERVER_NAME = "us_swing_backtest"
MAX_VARIANTS = 64
MAX_TRADES = 500
MAX_COMPARE = 10

Result = dict[str, Any]


def _num(value: float) -> float | None:
    return None if math.isnan(value) else value


def _rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Frame rows as JSON-safe dicts: dates as ISO text, NaN as null."""
    rows: list[dict[str, Any]] = json.loads(frame.to_json(orient="records", date_format="iso"))
    return rows


def _safe(tool: Callable[..., Result]) -> Callable[..., Result]:
    """Return ``{"error": ...}`` instead of raising (SRD-MCP-007.010)."""
    @functools.wraps(tool)
    def wrapper(*args: Any, **kwargs: Any) -> Result:
        try:
            return tool(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 — sent back to the agent as a message
            _log.warning("[Backtest MCP] %s failed: %s", tool.__name__, exc)
            return {"error": str(exc) or type(exc).__name__}
    return wrapper


def _plan(data: dict[str, Any]) -> RunPlan:
    try:
        return RunPlan.from_dict(data)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Run plan is not valid: {exc}") from exc


class BacktestTools:
    """The tool bodies, kept apart from the server so tests can call them directly."""

    def __init__(self, service: BacktestService, jobs: JobManager,
                 presets: Callable[[str], Sequence[PresetInfo]],
                 strategies: Callable[[], Sequence[dict[str, Any]]],
                 records: Callable[[], Sequence[UniverseRecord]],
                 default_user: Callable[[], str] = lambda: "1") -> None:
        self._service = service
        self._default_user = default_user
        self._jobs = jobs
        self._presets = presets
        self._strategies = strategies
        self._records = records

    def _user(self, user_id: str) -> str:
        return user_id or self._default_user()

    @_safe
    def bt_catalog(self, user_id: str = "") -> Result:
        """Screener presets, live strategy names and S&P 500 sectors for a run plan.

        An empty ``user_id`` means the app's first user, as in the app.
        """
        return {
            "presets": [{"id": p.id, "name": p.name, "timeframe": p.timeframe}
                        for p in self._presets(self._user(user_id))],
            "strategies": sorted(str(s["name"]) for s in self._strategies()),
            "sectors": sorted({r.sector for r in self._records() if r.sector}),
        }

    @_safe
    def bt_estimate(self, plan: dict[str, Any], user_id: str = "") -> Result:
        """Data check for a run plan: stocks, missing candles, cached days and errors."""
        est = self._service.estimate(_plan(plan), self._user(user_id))
        return {"stocks": len(est.symbols), "missing_1d": est.missing_1d,
                "missing_3m": est.missing_3m, "days_total": est.days_total,
                "days_cached": est.days_cached, "errors": est.errors}

    @_safe
    def bt_run(self, plan: dict[str, Any], user_id: str = "") -> Result:
        """Start Steps 1–3 in the background; poll ``bt_status`` with the job id."""
        run_plan = _plan(plan)
        if not run_plan.strategies:
            raise ValueError("Pick at least one strategy")
        count = len(run_plan.variants())
        if count > MAX_VARIANTS:
            raise ValueError(f"The plan has {count} variants; the limit is {MAX_VARIANTS}")
        user = self._user(user_id)
        errors = self._service.estimate(run_plan, user).errors
        if errors:
            raise ValueError("; ".join(errors))
        return self._jobs.start(run_plan, user).as_dict()

    @_safe
    def bt_status(self, job_id: str) -> Result:
        """State, step and progress of a job; ``run_id`` is set once results are saved."""
        return self._jobs.get(job_id).as_dict()

    @_safe
    def bt_cancel(self, job_id: str) -> Result:
        """Ask a running job to stop."""
        return self._jobs.cancel(job_id).as_dict()

    @_safe
    def bt_summary(self, run_id: str) -> Result:
        """A saved run's plan and every Step 4 stat for each variant."""
        run = self._service.get_run(run_id)
        if run is None:
            raise ValueError(f"No saved run {run_id}")
        return {
            "run_id": run.run_id, "name": run.name, "status": run.status,
            "plan": json.loads(run.plan_json),
            "variants": [{"label": rep.label,
                          "stats": {s.name: _num(s.value) for s in rep.stats}}
                         for rep in self._service.report_for_run(run_id)],
        }

    @_safe
    def bt_trades(self, run_id: str, variant: int = 0, limit: int = 100) -> Result:
        """One variant's trades, newest last; ``limit`` up to 500."""
        if self._service.get_run(run_id) is None:
            raise ValueError(f"No saved run {run_id}")
        results = self._service.saved_results(run_id)
        if not 0 <= variant < len(results):
            raise ValueError(f"Variant must be 0 to {len(results) - 1}")
        trades = results[variant].trades
        limit = max(1, min(limit, MAX_TRADES))
        return {"total": len(trades), "trades": _rows(trades.tail(limit))}

    @_safe
    def bt_compare(self, run_ids: list[str]) -> Result:
        """Key stats for every variant of 1 to 10 saved runs."""
        if not 1 <= len(run_ids) <= MAX_COMPARE:
            raise ValueError(f"Give 1 to {MAX_COMPARE} run ids")
        rows: list[dict[str, Any]] = []
        errors = []
        for run_id in run_ids:
            if self._service.get_run(run_id) is None:
                errors.append(f"No saved run {run_id}")
                continue
            table = report.compare(self._service.report_for_run(run_id))
            rows += [{"run_id": run_id, **row} for row in _rows(table)]
        return {"rows": rows, "errors": errors}


TOOL_NAMES = ("bt_catalog", "bt_estimate", "bt_run", "bt_status", "bt_cancel", "bt_summary",
              "bt_trades", "bt_compare")


def build_server(tools: BacktestTools) -> FastMCP:
    """Register the tools on a FastMCP server (SRD-MCP-007.001)."""
    server = FastMCP(SERVER_NAME)
    for name in TOOL_NAMES:
        server.add_tool(getattr(tools, name), name=name)
    return server


def default_tools() -> BacktestTools:
    """Tools on the app's real store, cache, results and live strategies."""
    from us_swing.backtest.cache import StepCache  # noqa: PLC0415 — heavy, server start only
    from us_swing.backtest.results import ResultsStore  # noqa: PLC0415
    from us_swing.backtest.store import BacktestStore  # noqa: PLC0415
    from us_swing.core.backtest_bridge import (  # noqa: PLC0415
        default_user_id,
        list_presets,
        load_preset_dict,
        load_strategies,
        load_universe,
    )

    service = BacktestService(BacktestStore(), StepCache(), ResultsStore(),
                              load_universe, load_preset_dict, load_strategies)
    return BacktestTools(service, JobManager(service), list_presets, load_strategies,
                         load_universe, default_user_id)
