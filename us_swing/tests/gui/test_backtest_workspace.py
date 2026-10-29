"""
Module: MD-GUI-031.002.M02 / MD-GUI-031.003.M03 — tests
Parent SRD: SRD-GUI-031.002

Backtest workspace: builder plan, screener fields, step strip, data check,
Step 1 run and view.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd
import pytest
from PyQt6.QtCore import QObject, Qt, pyqtSignal

from us_swing.backtest.service import DailyList, Estimate
from us_swing.core.backtest_bridge import PresetInfo
from us_swing.data.models import ConnectionStatus
from us_swing.gui import backtest_workspace as mod
from us_swing.gui.backtest_builder import BacktestBuilder
from us_swing.gui.backtest_workspace import BacktestWorkspace, data_check_text

_PRESETS = [PresetInfo("p1", "Momentum", "1d", False), PresetInfo("p2", "Weekly", "1w", False)]


@dataclass(frozen=True)
class _Record:
    symbol: str
    sector: str
    market_cap: float | None = None


@dataclass(frozen=True)
class _User:
    user_id: str = "1"


_RECORDS = [_Record("AAPL", "Information Technology"), _Record("XOM", "Energy"),
            _Record("CVX", "Energy")]


class _FakeSvc(QObject):
    sp500_updated = pyqtSignal()
    backtest_finished = pyqtSignal(bool, str)
    feed_status_changed = pyqtSignal(str)

    def __init__(self, connected: bool = True) -> None:
        super().__init__()
        self.connection_status = (
            ConnectionStatus.CONNECTED if connected else ConnectionStatus.DISCONNECTED
        )
        self.started = 0

    def get_sp500_universe(self) -> list[_Record]:
        return _RECORDS

    def get_active_user(self) -> _User:
        return _User()

    def is_backtest_running(self) -> bool:
        return False

    def start_backtest_download(self) -> bool:
        self.started += 1
        return True


_EST = Estimate(symbols=["A"] * 75, missing_1d=[], missing_3m=["X"], benchmark_ok=False,
                days_total=0, days_cached=0, errors=[])


class _FakeService:
    def __init__(self, est: Estimate = _EST) -> None:
        self.est = est
        self.runs = 0

    def estimate(self, _plan: Any, _user: str) -> Estimate:
        return self.est

    def run_stocks(self, _plan: Any, _user: str, **kw: Any) -> DailyList:
        self.runs += 1
        kw["progress"](1, 2)
        kw["progress"](2, 2)
        days = [date(2026, 3, 2), date(2026, 3, 3)]
        frame = pd.DataFrame({"date": [days[0], days[1], days[1]],
                              "symbol": ["AAPL", "MSFT", "NVDA"],
                              "score": [0.9, 0.8, 0.7], "rank": [1, 1, 2]})
        return DailyList("k", days, frame)

    def run_signals(self, _plan: Any, _daily: DailyList, **kw: Any) -> pd.DataFrame:
        kw["progress"](1, 1)
        start = pd.Timestamp("2026-03-03 14:33", tz="UTC")
        return pd.DataFrame({
            "strategy": ["ST_A", "ST_B", "ST_A"], "symbol": ["AAPL", "MSFT", "AAPL"],
            "kind": ["entry", "entry", "exit"],
            "start": [start, start, start + pd.Timedelta(minutes=30)],
            "end": [start, start, start + pd.Timedelta(minutes=33)],
            "close_at_start": [10.0, 20.0, 11.0], "values": ["{}"] * 3, "pnl": [False] * 3,
        })


_STRATEGIES = [
    {"name": "ST_A", "capital_max": 50, "per_trade_pct": 100},
    {"name": "ST_B", "capital_max": 25, "per_trade_pct": 50},
]


@pytest.fixture()
def workspace(qtbot: Any, monkeypatch: pytest.MonkeyPatch) -> BacktestWorkspace:
    monkeypatch.setattr(mod, "list_presets", lambda _user: _PRESETS)
    monkeypatch.setattr(mod, "load_strategies", lambda: _STRATEGIES)
    ws = BacktestWorkspace(_FakeSvc(), service=_FakeService())  # type: ignore[arg-type]
    qtbot.addWidget(ws)
    return ws


def _tick(builder: BacktestBuilder, *sectors: str) -> None:
    lst = builder._sectors
    for i in range(lst.count()):
        item = lst.item(i)
        if item is not None and item.text() in sectors:
            item.setCheckState(Qt.CheckState.Checked)


def test_backtest_item_after_charts() -> None:
    """UT-GUI-031.001.M01.T01: Backtest is the fifth sidebar item and a wide page."""
    from us_swing.gui.main_window import _NAV_ITEMS, _WIDE_PAGES

    assert _NAV_ITEMS[4] == ("history", "Backtest")
    assert 4 in _WIDE_PAGES


def test_plan_from_fields(qtbot: Any) -> None:
    """UT-GUI-031.002.M02.T01: Sectors, add and remove fields go into the plan."""
    builder = BacktestBuilder()
    qtbot.addWidget(builder)
    builder.set_universe(_RECORDS)
    builder._mode.buttons[1].click()
    _tick(builder, "Energy", "Information Technology")
    builder._add.setText("pltr, amd")
    builder._remove.setText("INTC")

    plan = builder.plan()

    assert plan.universe.mode == "sector"
    assert plan.universe.sectors == ("Energy", "Information Technology")
    assert plan.universe.add == ("PLTR", "AMD")
    assert plan.universe.remove == ("INTC",)


def test_names_mode_with_no_names(qtbot: Any) -> None:
    """UT-GUI-031.002.M02.T02: Names mode with an empty field fails validation."""
    builder = BacktestBuilder()
    qtbot.addWidget(builder)
    builder.set_presets(_PRESETS)
    builder._mode.buttons[2].click()

    assert "Type at least one stock name" in builder.plan().validate()


def test_screener_fields(qtbot: Any) -> None:
    """UT-GUI-031.010.M02.T01: Preset picker, Stocks per day and the disabled AI tick."""
    builder = BacktestBuilder()
    qtbot.addWidget(builder)
    builder.set_presets(_PRESETS)

    assert [builder._preset.itemText(i) for i in range(2)] == ["Momentum", "Weekly (weekly)"]
    assert builder._top_n.text() == "All"
    builder._top_n.setValue(5)
    assert builder.plan().screener.top_n == 5
    assert builder.plan().screener.preset_id == "p1"
    assert not builder._ai.isEnabled()


def test_step_strip_states(workspace: BacktestWorkspace) -> None:
    """UT-GUI-031.003.M03.T01: Pills read Waiting, n of m, Done and Cached."""
    cases = [("waiting", "Waiting", ""), ("running", "3 of 10", "downloading"),
             ("done", "Done", "complete"), ("cached", "Cached", "complete")]
    for state, text, qss in cases:
        workspace.set_step(0, state, 3, 10)
        assert workspace.pills[0].text() == f"1 Stocks · {text}"
        assert workspace.pills[0].property("state") == qss


def test_data_check_text(workspace: BacktestWorkspace, qtbot: Any) -> None:
    """UT-GUI-031.004.M03.T01: Counts line from the estimate; Run enabled."""
    assert data_check_text(_EST) == "75 stocks · 0 missing 1d · 1 missing 3m candles · SPY missing"

    workspace._start_estimate()
    qtbot.waitUntil(lambda: workspace._estimate is not None)

    assert workspace.check_label.text() == data_check_text(_EST)
    assert workspace.run_btn.isEnabled()
    assert workspace.download_btn.isEnabled()


def test_errors_block_run_and_download_needs_tws(qtbot: Any,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-GUI-031.004.M03.T02: Plan errors disable Run; no TWS disables Download."""
    monkeypatch.setattr(mod, "list_presets", lambda _user: _PRESETS)
    bad = Estimate(["A"], [], ["A"], True, 0, 0, ["Start date is after the end date"])
    ws = BacktestWorkspace(_FakeSvc(connected=False),  # type: ignore[arg-type]
                           service=_FakeService(bad))  # type: ignore[arg-type]
    qtbot.addWidget(ws)

    ws._start_estimate()
    qtbot.waitUntil(lambda: ws._estimate is not None)

    assert "Start date is after the end date" in ws.check_label.text()
    assert not ws.run_btn.isEnabled()
    assert not ws.download_btn.isEnabled()


def test_run_and_view(workspace: BacktestWorkspace, qtbot: Any) -> None:
    """UT-GUI-031.011.M03.T01 / UT-GUI-031.012.M03.T01: Run shows Cancel, then the days."""
    workspace._start_estimate()
    qtbot.waitUntil(lambda: workspace._estimate is not None)
    workspace.builder._top_n.setValue(1)

    workspace.run_btn.click()
    assert workspace.run_btn.text() == "Cancel"
    qtbot.waitUntil(lambda: workspace._runner is None)

    assert workspace.run_btn.text() == "Run"
    assert workspace.pills[0].text() == "1 Stocks · Done"
    assert workspace.days_table.rowCount() == 2
    assert workspace.days_table.item(0, 0).text() == "2026-03-03"  # type: ignore[union-attr]
    assert workspace.days_table.item(0, 1).text() == "1"  # type: ignore[union-attr]
    assert workspace.stocks_table.rowCount() == 1
    assert workspace.stocks_table.item(0, 1).text() == "MSFT"  # type: ignore[union-attr]


def _tick_strategy(ws: BacktestWorkspace, index: int) -> None:
    ws.refresh_strategies()
    item = ws.builder._strategies.item(index)
    assert item is not None
    item.setCheckState(Qt.CheckState.Checked)


def test_strategies_list(workspace: BacktestWorkspace) -> None:
    """UT-GUI-031.020.M02.T01: Strategy rows show money split; ticked ones go in the plan."""
    _tick_strategy(workspace, 0)
    lst = workspace.builder._strategies

    assert lst.item(0).text() == "ST_A · 50% · 100% per trade"  # type: ignore[union-attr]
    specs = workspace.builder.plan().strategies
    assert [(s.id, s.allocation_pct, s.per_trade_pct) for s in specs] == [
        ("ST_A", (50.0,), (100.0,))]


def _run_both(ws: BacktestWorkspace, qtbot: Any) -> None:
    ws._start_estimate()
    qtbot.waitUntil(lambda: ws._estimate is not None)
    _tick_strategy(ws, 0)
    ws.run_btn.click()
    qtbot.waitUntil(lambda: ws._runner is None)


def test_run_does_both_steps(workspace: BacktestWorkspace, qtbot: Any) -> None:
    """UT-GUI-031.021.M03.T01: Run does Step 1 and Step 2; both pills Done; table filled."""
    _run_both(workspace, qtbot)

    assert workspace.pills[0].text() == "1 Stocks · Done"
    assert workspace.pills[1].text() == "2 Signals · Done"
    assert workspace.signals_table.rowCount() == 3
    assert workspace.signals_table.item(0, 2).text() == "exit"  # type: ignore[union-attr]
    assert workspace.signals_table.item(0, 3).text() == "2026-03-03 10:03"  # type: ignore[union-attr]


def test_strategy_filter(workspace: BacktestWorkspace, qtbot: Any) -> None:
    """UT-GUI-031.022.M03.T01: Picking a strategy shows only its rows."""
    _run_both(workspace, qtbot)

    workspace.strategy_filter.setCurrentText("ST_B")

    assert workspace.signals_table.rowCount() == 1
    assert workspace.signals_table.item(0, 1).text() == "MSFT"  # type: ignore[union-attr]


def test_double_click_opens_charts(workspace: BacktestWorkspace, qtbot: Any) -> None:
    """UT-GUI-031.023.M03.T01: Double-clicking a row asks for that stock's chart."""
    _run_both(workspace, qtbot)
    seen: list[tuple[str, str]] = []
    workspace.chart_requested.connect(lambda s, tf: seen.append((s, tf)))

    workspace.signals_table.cellDoubleClicked.emit(0, 0)

    assert seen == [("AAPL", "1d")]
