"""Tests for the Charts workspace, Focus + Inspector (FO-GUI-026, MD-GUI-026.001.M01)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from PyQt6.QtCore import QObject, QSettings, pyqtSignal
from PyQt6.QtWidgets import QMdiArea

from us_swing.gui import screener_panel
from us_swing.gui.chart_drawings import Drawing, DrawingStore
from us_swing.gui.chart_inspector import TradePlan
from us_swing.gui.chart_workspace import ChartWorkspace, parse_overlays

_CANDLES = [
    {"time": 1_760_000_000 + i * 86_400, "open": 100.0 + i, "high": 102.0 + i,
     "low": 99.0 + i, "close": 101.0 + i, "volume": 1_000 + i}
    for i in range(30)
]


class _Svc(QObject):
    watchlist_updated = pyqtSignal()
    positions_updated = pyqtSignal()
    screener_results_updated = pyqtSignal(list)
    sp500_updated = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.screener: list[SimpleNamespace] = []
        self.positions: list[SimpleNamespace] = []
        self.drawings = DrawingStore(sa.create_engine("sqlite://"))

    def get_candle_symbols(self, *_a, **_k) -> list[str]:
        return ["AAPL", "NVDA"]

    def get_candles_for_symbol(self, symbol: str, *_a, **_k) -> list[dict]:
        return [] if symbol == "ZZZ" else list(_CANDLES)

    def get_system_config(self) -> SimpleNamespace:
        return SimpleNamespace(market_timezone="US/Eastern")

    def get_watchlist_items(self) -> list[SimpleNamespace]:
        return [SimpleNamespace(symbol="NVDA", ltp=130.0, change_pct=1.2)]

    def get_latest_screener_results(self) -> list[SimpleNamespace]:
        return self.screener

    def get_positions(self) -> list[SimpleNamespace]:
        return self.positions

    def get_sp500_universe(self) -> list[SimpleNamespace]:
        return [SimpleNamespace(symbol="NVDA", name="NVIDIA Corp")]

    def get_active_user(self) -> SimpleNamespace:
        return SimpleNamespace(user_id=1,
                               risk_config=SimpleNamespace(risk_per_trade_pct=1.0))

    def get_account_state(self) -> SimpleNamespace:
        return SimpleNamespace(equity=40_000.0)

    def get_drawing_store(self) -> DrawingStore:
        return self.drawings


def _screener_entry(symbol: str, entry=None, stop=None, target=None) -> SimpleNamespace:
    return SimpleNamespace(symbol=symbol, score=0.9, screener_name="Momentum",
                           run_type="manual", plan_entry=entry, plan_stop=stop,
                           plan_target=target)


@pytest.fixture()
def settings(tmp_path) -> QSettings:
    return QSettings(str(tmp_path / "charts.ini"), QSettings.Format.IniFormat)


@pytest.fixture()
def svc() -> _Svc:
    return _Svc()


@pytest.fixture()
def workspace(qtbot, svc, settings):
    widget = ChartWorkspace(svc, settings=settings)  # type: ignore[arg-type]
    qtbot.addWidget(widget)
    widget.resize(1300, 800)
    plans: list[object] = []
    widget.chart.set_plan = plans.append  # type: ignore[method-assign]
    widget.plans = plans  # type: ignore[attr-defined]
    return widget


def test_three_cards_no_mdi(workspace):
    """UT-GUI-026.001.M01.T01: Three cards, no MDI."""
    assert workspace.findChild(QMdiArea) is None
    cards = [workspace.source.parent(), workspace.chart.parent().parent(),
             workspace.inspector.parent()]
    assert workspace.chart.parent().parent().objectName() == "shell_card"
    assert [c.objectName() for c in cards] == ["shell_card"] * 3


def test_open_symbol_loads_chart_and_selects_row(workspace):
    """UT-GUI-026.001.M01.T02: open_symbol loads chart and selects row."""
    workspace.open_symbol("nvda", "1w")
    assert workspace.chart.current_symbol == "NVDA"
    assert workspace.chart.current_timeframe == "1w"
    assert workspace.timeframe == "1w"
    current = workspace.source.list.currentItem()
    assert current is not None and current.data(256) == "NVDA"
    assert workspace.symbol_lbl.text() == "NVDA"
    assert workspace.company_lbl.text() == "NVIDIA Corp"
    assert workspace.price_lbl.text() == "130.00"


def test_symbol_not_in_list_still_loads(workspace):
    """UT-GUI-026.001.M01.T03: Symbol not in list still loads."""
    workspace.open_symbol("AAPL")
    assert workspace.chart.current_symbol == "AAPL"
    assert workspace.source.list.currentItem() is None
    workspace.open_symbol("ZZZ")
    assert workspace.symbol_lbl.text() == "ZZZ"
    assert workspace.change_lbl.text() == "No data"


def test_overlays_add_remove_remember(qtbot, svc, settings, workspace):
    """UT-GUI-026.003.M01.T01: Overlay add, remove and remember."""
    assert workspace.overlays == [("sma", 20), ("sma", 50)]
    sent: list[list[tuple[str, int]]] = []
    workspace.chart.set_overlays = sent.append  # type: ignore[method-assign]
    workspace.add_overlay(("ema", 9))
    workspace.remove_overlay(("sma", 50))
    assert sent[-1] == [("sma", 20), ("ema", 9)]
    again = ChartWorkspace(svc, settings=settings)  # type: ignore[arg-type]
    qtbot.addWidget(again)
    assert again.overlays == [("sma", 20), ("ema", 9)]


def test_bad_saved_overlays_dropped():
    """UT-GUI-026.003.M01.T02: Bad saved overlay is dropped."""
    assert parse_overlays("sma:x,foo:5,sma:20,sma:20,ema:0") == [("sma", 20)]
    assert parse_overlays("") == []


def test_plan_sent_to_chart(svc, workspace):
    """UT-GUI-026.004.M01.T01: Plan sent to the chart."""
    svc.screener = [_screener_entry("NVDA", 129.8, 124.5, 141.0)]
    workspace.open_symbol("NVDA")
    assert workspace.plans[-1] == (129.8, 124.5, 141.0)


def test_no_plan_clears_lines(workspace):
    """UT-GUI-026.004.M01.T02: No plan clears lines."""
    workspace.open_symbol("AAPL")
    assert workspace.plans[-1] is None


def test_hidden_inspector_stays_hidden(qtbot, svc, settings, workspace):
    """UT-GUI-026.005.M01.T04: Hidden Inspector stays hidden."""
    workspace.inspector_btn.click()
    assert workspace._inspector_card.isHidden()
    again = ChartWorkspace(svc, settings=settings)  # type: ignore[arg-type]
    qtbot.addWidget(again)
    assert again._inspector_card.isHidden()
    assert not again.inspector_btn.isChecked()


def test_plan_source_order(svc, workspace):
    """UT-GUI-026.006.M01.T05: Plan source order."""
    svc.screener = [_screener_entry("NVDA", 129.8, 124.5, 141.0)]
    svc.positions = [SimpleNamespace(symbol="NVDA", quantity=10, average_price=120.0,
                                     stop_loss=115.0, target_price=150.0)]
    assert workspace._plan_for("NVDA") == TradePlan(129.8, 124.5, 141.0)
    svc.screener = [_screener_entry("NVDA")]
    assert workspace._plan_for("NVDA") == TradePlan(120.0, 115.0, 150.0)
    svc.positions[0].stop_loss = 0.0
    assert workspace._plan_for("NVDA") is None


def test_edited_plan_wins_and_redraws(workspace):
    """UT-GUI-026.006.M01.T06: Edited plan is kept for the session and redrawn."""
    workspace.open_symbol("NVDA")
    workspace.inspector.plan_changed.emit(TradePlan(130.0, 125.0, 140.0))
    assert workspace.plans[-1] == (130.0, 125.0, 140.0)
    workspace.open_symbol("AAPL")
    workspace.open_symbol("NVDA")
    assert workspace.plans[-1] == (130.0, 125.0, 140.0)
    workspace.inspector.plan_changed.emit(TradePlan(130.0, 131.0, 140.0))
    assert workspace.plans[-1] is None


def test_theme_refresh_recolours_change(workspace):
    """UT-GUI-026.001.M01.T04: Theme change keeps symbol and recolours the change."""
    workspace.open_symbol("NVDA")
    workspace.change_lbl.setStyleSheet("")
    workspace.refresh_theme("carbon")
    assert workspace.symbol_lbl.text() == "NVDA"
    assert "color" in workspace.change_lbl.styleSheet()


def test_inspector_gets_context(workspace):
    """UT-GUI-026.007.M01.T03: Indicators get the loaded bars."""
    workspace.open_symbol("NVDA")
    section = next(s for s in workspace.inspector.sections if s.key == "indicators")
    assert section.rows.values["rsi"].text() != "—"


def test_send_to_execution_adds_pick(qtbot, svc, workspace):
    """UT-GUI-026.010.M01.T01: Send to Execution adds pick."""
    picks: list[str] = []
    svc.add_manual_pick = lambda s: picks.append(s)  # type: ignore[attr-defined]
    workspace.open_symbol("NVDA")
    plan = next(s for s in workspace.inspector.sections if s.key == "plan")
    with qtbot.waitSignal(workspace.execution_requested) as blocker:
        plan.send_btn.click()
    assert picks == ["NVDA"] and blocker.args == ["NVDA"]
    assert plan.message_lbl.isHidden()


def test_existing_pick_shows_message(qtbot, svc, workspace):
    """UT-GUI-026.010.M01.T02: Existing pick shows message."""
    svc.add_manual_pick = lambda s: f"{s} is already in your picks"  # type: ignore[attr-defined]
    workspace.open_symbol("NVDA")
    plan = next(s for s in workspace.inspector.sections if s.key == "plan")
    with qtbot.assertNotEmitted(workspace.execution_requested):
        plan.send_btn.click()
    assert not plan.message_lbl.isHidden()
    assert plan.message_lbl.text() == "NVDA is already in your picks"


def test_markers_and_levels_reach_chart(workspace):
    """UT-GUI-026.008.M01.T03: Inspector markers and levels reach the chart."""
    workspace.inspector.markers_changed.emit([{"time": 1, "text": "x"}])
    workspace.inspector.levels_changed.emit([1.0])
    studies = workspace.chart._studies()
    assert studies["markers"] == [{"time": 1, "text": "x"}] and studies["levels"] == [1.0]


def test_drawing_saved_and_reloaded(svc, workspace):
    """UT-GUI-026.011.M01.T01: Finished drawing is saved, tool resets, drawing comes back."""
    workspace.open_symbol("NVDA")
    workspace.tool_buttons["trend"].click()
    assert workspace.chart._tool == "trend"
    workspace.chart.drawing_added.emit(Drawing("trend", ((1.0, 100.0), (2.0, 110.0))))
    assert workspace.chart._tool == "" and workspace.tool_buttons[""].isChecked()
    saved = svc.drawings.load(1, "NVDA", "1d")
    assert len(saved) == 1 and saved[0].colour
    workspace.open_symbol("AAPL")
    assert workspace.chart._drawings == []
    workspace.open_symbol("NVDA")
    assert workspace.chart._drawings == [saved[0].to_js()]


def test_clear_drawings(svc, workspace):
    """UT-GUI-026.011.M01.T02: Delete all clears the chart and the database."""
    workspace.open_symbol("NVDA")
    workspace.chart.drawing_added.emit(Drawing("hline", ((1.0, 100.0),)))
    workspace.clear_drawings()
    assert workspace.chart._drawings == []
    assert svc.drawings.load(1, "NVDA", "1d") == []


def test_eraser_deletes_one_drawing(svc, workspace):
    """UT-GUI-026.011.M01.T03: Eraser deletes only the clicked drawing."""
    workspace.open_symbol("NVDA")
    workspace.chart.drawing_added.emit(Drawing("hline", ((1.0, 100.0),)))
    workspace.chart.drawing_added.emit(Drawing("trend", ((1.0, 100.0), (2.0, 110.0))))
    first, second = svc.drawings.load(1, "NVDA", "1d")
    workspace.tool_buttons["erase"].click()
    workspace.chart._bridge.delete_drawing(first.id)
    assert workspace.chart._drawings == [second.to_js()]
    assert svc.drawings.load(1, "NVDA", "1d") == [second]
    assert workspace.chart._tool == "erase"   # stays on to erase more


def test_save_failure_keeps_drawing(svc, workspace, caplog):
    """UT-GUI-026.012.M01.T05: Save failure logs and keeps the drawing on screen."""
    workspace.open_symbol("NVDA")
    with svc.drawings._engine.begin() as conn:
        conn.execute(sa.text("DROP TABLE chart_drawings"))
    workspace.chart.drawing_added.emit(Drawing("hline", ((1.0, 100.0),)))
    assert len(workspace.chart._drawings) == 1
    assert "[Charts] Could not save drawing" in caplog.text


def test_quick_chart_viewer_removed():
    """UT-GUI-020.004.M01.T01: Quick Chart Viewer is gone."""
    assert not hasattr(screener_panel, "QuickChartWindow")
    assert hasattr(screener_panel.ScreenerPanel, "chart_requested")


# ── Default stock on open (SRD-GUI-026.013) ───────────────────────────────────

def _trade(symbol: str) -> SimpleNamespace:
    return SimpleNamespace(symbol=symbol, quantity=5, direction="LONG", current_price=50.0,
                           pnl_pct=1.0, average_price=48.0, stop_loss=0.0, target_price=0.0)


def test_opens_first_trade_when_shown(qtbot, svc, workspace):
    """UT-GUI-026.013.M01.T01: Opening Charts loads the first open trade, ahead of the watchlist."""
    svc.positions = [_trade("KVUE")]
    workspace.show()
    qtbot.waitUntil(lambda: workspace.chart.current_symbol == "KVUE")
    assert workspace.source.tab == "trades"


def test_late_trades_take_over_auto_pick(qtbot, svc, workspace):
    """UT-GUI-026.013.M01.T02: Trades that arrive after open replace the automatic watchlist pick."""
    workspace.show()
    qtbot.waitUntil(lambda: workspace.chart.current_symbol == "NVDA")
    svc.positions = [_trade("KVUE")]
    svc.positions_updated.emit()
    assert workspace.chart.current_symbol == "KVUE" and workspace.source.tab == "trades"


def test_user_choice_not_overridden(qtbot, svc, workspace):
    """UT-GUI-026.013.M01.T03: A stock the user asked for stays, even when trades arrive."""
    workspace.show()
    workspace.open_symbol("AAPL")
    qtbot.wait(20)
    svc.positions = [_trade("KVUE")]
    svc.positions_updated.emit()
    assert workspace.chart.current_symbol == "AAPL"


def test_hidden_workspace_does_not_load(svc, workspace):
    """UT-GUI-026.013.M01.T04: Data updates while Charts is hidden load nothing."""
    svc.positions = [_trade("KVUE")]
    svc.positions_updated.emit()
    assert workspace.chart.current_symbol == ""
