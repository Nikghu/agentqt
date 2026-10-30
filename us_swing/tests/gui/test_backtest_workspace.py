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
from PyQt6.QtCore import QObject, QSettings, Qt, pyqtSignal

from us_swing.backtest.service import DailyList, Estimate, OpenedRun, SavedReport
from us_swing.backtest.spec import Variant
from us_swing.backtest.steps.portfolio import VariantResult
from us_swing.backtest.steps.report import Report, build_report
from us_swing.core.backtest_bridge import PresetInfo
from us_swing.data.models import ConnectionStatus
from us_swing.gui import backtest_workspace as mod
from us_swing.gui.backtest_builder import BacktestBuilder
from us_swing.gui.backtest_workspace import BacktestWorkspace, data_check_text, trades_summary

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
        self.bar_reads: list[tuple[str, str, date, date]] = []

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
        return DailyList("k", days, frame, {days[0]: date(2026, 2, 27), days[1]: days[0]})

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

    def run_portfolio(self, _plan: Any, _daily: DailyList, _found: Any, **kw: Any) -> list[Any]:
        kw["progress"](1, 1)
        ts = pd.Timestamp("2026-03-03 15:00", tz="UTC")
        trades = pd.DataFrame({
            "strategy": ["ST_A", "ST_A"], "symbol": ["AAPL", "MSFT"], "direction": ["LONG"] * 2,
            "entry_ts": [ts, ts + pd.Timedelta(hours=1)], "entry_px": [10.0, 20.0], "qty": [3, 1],
            "exit_ts": [ts + pd.Timedelta(hours=2)] * 2, "exit_px": [20.0, 10.0],
            "exit_reason": ["strategy", "end_time"], "costs": [0.0, 0.0],
            "net_pnl": [30.0, -10.0], "mae": [0.0, 0.0], "mfe": [0.0, 0.0],
            "score": [1.0, 1.0], "rank": [1, 2],
        })
        log = pd.DataFrame({"ts": [ts] * 3, "symbol": ["AAPL", "MSFT", "NVDA"],
                            "strategy": ["ST_A"] * 3,
                            "decision": ["entered", "entered", "no_margin"],
                            "margin_available": [1.0] * 3, "strategy_deployed": [1.0] * 3})
        money = pd.DataFrame({"date": [date(2026, 3, 2), date(2026, 3, 3)],
                              "start_capital": [100.0] * 2, "deployed": [0.0] * 2,
                              "margin_min": [50.0] * 2, "margin_close": [100.0] * 2,
                              "open_value": [0.0] * 2, "equity": [100.0, 120.0]})
        return [VariantResult(Variant(100.0, ()), trades, log, money),
                VariantResult(Variant(200.0, ()), trades.iloc[:1], log, money.assign(equity=230.0))]

    def bars(self, symbol: str, tf: str, start: date, end: date) -> pd.DataFrame:
        self.bar_reads.append((symbol, tf, start, end))
        ts = pd.date_range("2026-03-03 14:30", periods=8, freq="15min", tz="UTC")
        return pd.DataFrame({"ts": ts, "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.5,
                             "volume": 1})

    def saved_reports(self) -> list[SavedReport]:
        return []

    def open_run(self, _run_id: str, _user: str, **kw: Any) -> OpenedRun:
        kw["progress"](1, 1)
        daily = self.run_stocks(None, "", progress=lambda *_: None)
        found = self.run_signals(None, daily, progress=lambda *_: None)
        results = self.run_portfolio(None, daily, found, progress=lambda *_: None)
        return OpenedRun(None, daily, found, results,  # type: ignore[arg-type]
                         self.build_reports(None, results))

    def build_reports(self, _plan: Any, results: list[VariantResult]) -> list[Report]:
        return [build_report(f"${r.variant.capital:,.0f}", r.variant.capital, r.trades, r.money,
                             r.day_log, {"AAPL": "Information Technology"}) for r in results]


_STRATEGIES = [
    {"name": "ST_A", "capital_max": 50, "per_trade_pct": 100},
    {"name": "ST_B", "capital_max": 25, "per_trade_pct": 50},
]


@pytest.fixture()
def workspace(qtbot: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> BacktestWorkspace:
    monkeypatch.setattr(mod, "list_presets", lambda _user: _PRESETS)
    monkeypatch.setattr(mod, "load_strategies", lambda: _STRATEGIES)
    settings = QSettings(str(tmp_path / "dock.ini"), QSettings.Format.IniFormat)
    ws = BacktestWorkspace(_FakeSvc(), service=_FakeService(),  # type: ignore[arg-type]
                           settings=settings)
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
    assert data_check_text(_EST) == "75 stocks · 0 missing 1d · 1 missing 3m candles"

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
    assert workspace.days_table.rowCount() == 3
    assert workspace.days_table.item(1, 0).text() == "2026-03-03"  # type: ignore[union-attr]
    assert workspace.days_table.item(1, 2).text() == "1"  # type: ignore[union-attr]
    assert workspace.stocks_table.rowCount() == 1
    assert workspace.stocks_table.item(0, 1).text() == "MSFT"  # type: ignore[union-attr]


def test_session_and_data_day_shown(workspace: BacktestWorkspace, qtbot: Any) -> None:
    """UT-GUI-031.013.M03.T01: Each session row shows the day its list was made from."""
    workspace._start_estimate()
    qtbot.waitUntil(lambda: workspace._estimate is not None)

    workspace.run_btn.click()
    qtbot.waitUntil(lambda: workspace._runner is None)

    assert workspace.days_table.item(2, 0).text() == "2026-03-02"  # type: ignore[union-attr]
    assert workspace.days_table.item(2, 1).text() == "2026-02-27"  # type: ignore[union-attr]
    assert workspace.stocks_head.text().startswith(
        "SESSION 2026-03-03 · DATA UP TO 2026-03-02 CLOSE")


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


def test_account_fields(qtbot: Any) -> None:
    """UT-GUI-031.030.M02.T01: Account fields and user defaults go into the plan."""
    builder = BacktestBuilder()
    qtbot.addWidget(builder)
    builder.set_account_defaults(5000.0, 2.0)
    builder._slippage.setValue(10)
    builder._when.setCurrentIndex(1)

    plan = builder.plan()

    assert plan.account.capital == (5000.0,)
    assert plan.account.max_daily_loss_pct == 2.0
    assert plan.account.when_full == "highest_score"
    assert plan.costs.slippage_bps == 10.0


def test_run_does_step_3(workspace: BacktestWorkspace, qtbot: Any) -> None:
    """UT-GUI-031.031.M03.T01: Run does Step 3 and shows the Trades tab."""
    _run_both(workspace, qtbot)

    assert workspace.pills[2].text() == "3 Portfolio · Done"
    assert workspace.trades_table.rowCount() == 2


def test_trades_tab(workspace: BacktestWorkspace, qtbot: Any) -> None:
    """UT-GUI-031.032.M03.T01: Summary line and one row per trade."""
    _run_both(workspace, qtbot)

    assert workspace.trades_head.text() == "TRADES · 2 trades · net P&L $20.00 · win rate 50%"
    assert workspace.trades_table.rowCount() == 2
    assert trades_summary(pd.DataFrame(columns=["net_pnl"])) == "TRADES · none"


def test_day_log_and_money_tabs(workspace: BacktestWorkspace, qtbot: Any) -> None:
    """UT-GUI-031.033.M03.T01: Day log and Money panels list the day's rows, or all."""
    _run_both(workspace, qtbot)

    assert workspace.log_table.rowCount() == 3
    assert workspace.money_table.rowCount() == 1
    assert workspace.money_table.item(0, 5).text() == "120.00"  # type: ignore[union-attr]
    workspace.days_table.selectRow(0)
    assert workspace.money_table.rowCount() == 2


def test_run_does_step_4(workspace: BacktestWorkspace, qtbot: Any) -> None:
    """UT-GUI-031.040.M03.T01: Run ends with the Report tab and its KPI row filled."""
    _run_both(workspace, qtbot)

    assert workspace.pills[3].text() == "4 Report · Done"
    assert workspace.tabs.tabText(workspace.tabs.currentIndex()) == "Detail Report"
    assert workspace.report_view.kpi_values["Trades"].text() == "2"
    assert workspace.report_view.kpi_values["Net P&L"].text() == "$20.00"


def test_variant_picker_switches_tabs(workspace: BacktestWorkspace, qtbot: Any) -> None:
    """UT-GUI-031.044.M03.T01: Picking the second variant shows its trades and report."""
    _run_both(workspace, qtbot)
    view = workspace.report_view

    assert not view.variant.isHidden()
    assert view.compare_table.rowCount() == 2
    view.variant.setCurrentIndex(1)

    assert workspace.trades_table.rowCount() == 1
    assert view.kpi_values["Net P&L"].text() == "$30.00"


def test_sections_and_variant_corner(workspace: BacktestWorkspace) -> None:
    """UT-GUI-031.050.M03.T01: Three section tabs; the variant picker sits by the tabs."""
    tabs = workspace.tabs

    assert [tabs.tabText(i) for i in range(tabs.count())] == [
        "Trade Inspector", "Detail Report", "Reports"]
    assert tabs.cornerWidget() is workspace.report_view.variant


def test_picking_a_day_filters_panels(workspace: BacktestWorkspace, qtbot: Any) -> None:
    """UT-GUI-031.051.M03.T01: A day with no trades empties Trades, Signals and Decisions."""
    _run_both(workspace, qtbot)

    workspace.days_table.selectRow(2)  # 2026-03-02

    assert workspace.trades_table.rowCount() == 0
    assert workspace.signals_table.rowCount() == 0
    assert workspace.log_table.rowCount() == 0
    assert workspace.money_table.item(0, 0).text() == "2026-03-02"  # type: ignore[union-attr]
    assert workspace.chart.message == "No trade on this session"


def test_all_sessions_row_totals(workspace: BacktestWorkspace, qtbot: Any) -> None:
    """UT-GUI-031.051.M03.T02: The All sessions row shows totals; a day with no trade shows —."""
    _run_both(workspace, qtbot)
    table = workspace.days_table

    assert table.item(0, 0).text() == "All sessions"  # type: ignore[union-attr]
    assert table.item(0, 3).text() == "2"  # type: ignore[union-attr]
    assert table.item(0, 4).text() == "$20.00"  # type: ignore[union-attr]
    assert table.item(2, 4).text() == "—"  # type: ignore[union-attr]


def test_chart_shows_selected_trade(workspace: BacktestWorkspace, qtbot: Any) -> None:
    """UT-GUI-031.052.M03.T01: The chart reads the trade's stock for its day, 15m first."""
    _run_both(workspace, qtbot)
    reads = workspace._service.bar_reads  # type: ignore[attr-defined]

    workspace.trades_table.selectRow(1)  # newest first: row 0 MSFT, row 1 AAPL

    assert reads[-1] == ("AAPL", "15m", date(2026, 3, 3), date(2026, 3, 3))
    assert list(workspace.chart.trades["symbol"]) == ["AAPL"]
    assert workspace.chart_head.text() == "AAPL · ST_A · 2026-03-03"
    workspace.chart_tf.setCurrentText("1d")
    assert reads[-1][1:3] == ("1d", date(2025, 12, 3))


def test_trade_list_opens_day(workspace: BacktestWorkspace, qtbot: Any) -> None:
    """UT-GUI-031.053.M03.T01: Clicking a Trade list row opens its day with that trade picked."""
    _run_both(workspace, qtbot)
    workspace.days_table.selectRow(2)  # start on another day

    workspace.trade_list.table.cellClicked.emit(1, 0)  # trade #2, MSFT

    assert workspace.tabs.currentWidget() is workspace.inspector
    assert workspace._selected_day() == date(2026, 3, 3)
    assert workspace.chart_head.text().startswith("MSFT")


def test_detail_panels_filled(workspace: BacktestWorkspace, qtbot: Any) -> None:
    """UT-GUI-031.054.M03.T01: Detail Report has Trade list, Screener use and Margin use filled."""
    _run_both(workspace, qtbot)

    assert set(workspace.detail.panels) == {"report", "tradelist", "screener_use", "margin_use",
                                            "risk"}
    assert workspace.trade_list.table.rowCount() == 2
    assert workspace.screener_use.chart.use.days == ["2026-03-02", "2026-03-03"]
    assert workspace.margin_use.facts.text().startswith("Money deployed on 2 of 2 days")


def test_open_saved_run(workspace: BacktestWorkspace, qtbot: Any) -> None:
    """UT-GUI-031.055.M03.T01: Opening a saved run fills the panels with its Stocks per day."""
    from tests.gui.test_backtest_reports import saved_report

    saved = saved_report()
    workspace.builder._top_n.setValue(1)  # the saved plan says All

    workspace.reports.open_requested.emit(saved)
    qtbot.waitUntil(lambda: workspace._runner is None)

    assert [p.text().split(" · ")[1] for p in workspace.pills] == ["Done"] * 4
    assert workspace.tabs.currentWidget() is workspace.detail
    assert workspace.trade_list.table.rowCount() == 2
    assert workspace.days_table.item(0, 2).text() == "3"  # type: ignore[union-attr]


def test_reports_tab_refreshes(workspace: BacktestWorkspace, qtbot: Any) -> None:
    """UT-GUI-031.055.M03.T02: Showing the Reports tab reloads the saved runs."""
    workspace.tabs.setCurrentWidget(workspace.saved)

    qtbot.waitUntil(lambda: not workspace.reports._workers)
    assert workspace.reports.count.text().startswith("0 saved run(s)")
