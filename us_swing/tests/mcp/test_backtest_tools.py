"""Tests for SRD-MCP-007.001–.010 — MD-MCP-007.001.M01 (backtest MCP tools)."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from us_swing.backtest.results import ResultsStore
from us_swing.backtest.service import BacktestService
from us_swing.backtest.store import BacktestStore
from us_swing.core.backtest_bridge import PresetInfo
from us_swing.mcp.backtest_tools import TOOL_NAMES, BacktestTools, build_server
from us_swing.mcp.jobs import JobManager
from tests.backtest.conftest import Record
from tests.backtest.test_saved_reports import _saved_run
from tests.backtest.test_service import _service as _rsi_service

_SRC = Path(__file__).resolve().parents[2] / "src"
_PLAN: dict[str, Any] = {
    "name": "mcp", "period": {"from": "2025-03-03", "to": "2025-03-07"},
    "universe": {"mode": "names", "names": ["AAPL", "MSFT", "NVDA"]},
    "screener": {"preset_id": "p1"},
    "strategies": [{"id": "S1"}],
}


def _tools(store: BacktestStore, tmp_path: Path) -> tuple[BacktestTools, ResultsStore]:
    svc, results = _rsi_service(store, tmp_path)
    return _make(svc), results


def _make(svc: BacktestService) -> BacktestTools:
    return BacktestTools(
        svc, JobManager(svc, workers=0),
        lambda user: [PresetInfo("p1", "RSI", "1d", False)] if user == "7" else [],
        lambda: [{"name": "S2"}, {"name": "S1"}],
        lambda: [Record("AAPL", "Information Technology"), Record("XOM", "Energy"),
                 Record("CVX", "")],
        lambda: "7",
    )


def test_server_lists_tools() -> None:
    """UT-MCP-007.001.M01.T01: The server lists the 8 backtest tools."""
    server = build_server(BacktestTools.__new__(BacktestTools))
    names = [t.name for t in asyncio.run(server.list_tools())]
    assert names == list(TOOL_NAMES)


def test_catalog_and_estimate(store: BacktestStore, tmp_path: Path) -> None:
    """UT-MCP-007.002.M01.T01: Catalog (app's first user by default) and estimate."""
    tools, _ = _tools(store, tmp_path)

    assert tools.bt_catalog() == {
        "presets": [{"id": "p1", "name": "RSI", "timeframe": "1d"}],
        "strategies": ["S1", "S2"], "sectors": ["Energy", "Information Technology"],
    }
    assert tools.bt_catalog("other")["presets"] == []
    est = tools.bt_estimate(_PLAN)
    assert est["stocks"] == 3
    assert est["missing_3m"] == ["AAPL", "MSFT", "NVDA"]
    assert est["errors"] == []
    assert "Run plan is not valid" in tools.bt_estimate({"name": "x"})["error"]


def test_run_refusals(store: BacktestStore, tmp_path: Path) -> None:
    """UT-MCP-007.004.M01.T01: bt_run refuses no strategy, too many variants, plan errors."""
    tools, _ = _tools(store, tmp_path)

    assert tools.bt_run({**_PLAN, "strategies": []})["error"] == "Pick at least one strategy"
    many = {**_PLAN, "account": {"capital": list(range(1000, 66000, 1000))}}
    assert "65 variants; the limit is 64" in tools.bt_run(many)["error"]
    empty = {**_PLAN, "universe": {"mode": "names", "names": []}}
    assert "Type at least one stock name" in tools.bt_run(empty)["error"]
    assert tools.bt_status("nope") == {"error": "No backtest job nope"}
    assert tools.bt_cancel("nope") == {"error": "No backtest job nope"}


def test_summary_trades_compare(store: BacktestStore, tmp_path: Path) -> None:
    """UT-MCP-007.007.M01.T01: Summary, trades and compare read a saved run."""
    tools, results = _tools(store, tmp_path)
    run_id = _saved_run(results, "Mine")

    summary = tools.bt_summary(run_id)
    assert (summary["name"], summary["status"]) == ("Mine", "done")
    assert summary["plan"]["universe"]["names"] == ["AAPL", "MSFT", "NVDA"]
    (variant,) = summary["variants"]
    assert variant["label"] == "$1,000 · S1 100%/50%"
    assert variant["stats"]["Trades"] == 4

    trades = tools.bt_trades(run_id, limit=2)
    assert trades["total"] == 4
    assert [t["symbol"] for t in trades["trades"]] == ["AAPL", "NVDA"]
    assert "Variant must be 0 to 0" in tools.bt_trades(run_id, variant=3)["error"]

    compared = tools.bt_compare([run_id, "nope"])
    assert [r["run_id"] for r in compared["rows"]] == [run_id]
    assert compared["rows"][0]["Trades"] == 4
    assert compared["errors"] == ["No saved run nope"]
    assert tools.bt_compare([])["error"] == "Give 1 to 10 run ids"
    assert tools.bt_summary("nope") == {"error": "No saved run nope"}


def test_stdio_session(tmp_path: Path) -> None:
    """UT-MCP-007.001.M01.T02: A real stdio session lists the tools and gets a plain error."""
    env = {**os.environ, "PYTHONPATH": str(_SRC), "USERPROFILE": str(tmp_path),
           "HOME": str(tmp_path)}
    params = StdioServerParameters(command=sys.executable, args=["-m", "us_swing.mcp"],
                                   env=env)

    async def session() -> tuple[list[str], str]:
        async with stdio_client(params) as (read, write), ClientSession(read, write) as client:
            await client.initialize()
            listed = await client.list_tools()
            answer = await client.call_tool("bt_status", {"job_id": "nope"})
            first = answer.content[0]
            return [t.name for t in listed.tools], getattr(first, "text", "")

    names, text = asyncio.run(asyncio.wait_for(session(), 60))

    assert names == list(TOOL_NAMES)
    assert "No backtest job nope" in text
