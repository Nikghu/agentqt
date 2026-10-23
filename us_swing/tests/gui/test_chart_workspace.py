"""Tests for the Charts workspace (FO-GUI-020)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from us_swing.gui import screener_panel
from us_swing.gui.chart_workspace import MAX_CHARTS, ChartWorkspace

_CANDLES = [
    {"time": 1_760_000_000 + i * 86_400, "open": 100.0 + i, "high": 102.0 + i,
     "low": 99.0 + i, "close": 101.0 + i, "volume": 1_000 + i}
    for i in range(5)
]


class _StubService:
    def get_candle_symbols(self, *_a, **_k) -> list[str]:
        return ["AAPL", "MSFT", "NVDA", "TSLA"]

    def get_candles_for_symbol(self, *_a, **_k) -> list[dict]:
        return list(_CANDLES)

    def get_system_config(self) -> SimpleNamespace:
        return SimpleNamespace(market_timezone="US/Eastern")

    def __getattr__(self, name: str):
        return lambda *_a, **_k: []


@pytest.fixture()
def workspace(qtbot):
    widget = ChartWorkspace(_StubService())  # type: ignore[arg-type]
    qtbot.addWidget(widget)
    widget.resize(1000, 700)
    return widget


def test_new_chart_up_to_six(workspace):
    """UT-GUI-020.001.M01.T01: New Chart adds windows up to six."""
    while workspace._new_btn.isEnabled():
        workspace._new_btn.click()
    assert workspace.window_count == MAX_CHARTS
    assert workspace._count_lbl.text() == "6 of 6 charts"


def test_closing_window_frees_slot(qtbot, workspace):
    """UT-GUI-020.001.M01.T02: Closing a window frees a slot."""
    while workspace._new_btn.isEnabled():
        workspace._new_btn.click()
    workspace._mdi.subWindowList()[0].close()
    qtbot.waitUntil(lambda: workspace.window_count == MAX_CHARTS - 1, timeout=2000)
    qtbot.waitUntil(workspace._new_btn.isEnabled, timeout=2000)


def test_tabs_mode_switches_view(workspace):
    """UT-GUI-020.002.M01.T01: Tabs mode switches view mode."""
    from PyQt6.QtWidgets import QMdiArea
    workspace._mode_buttons["tabs"].click()
    assert workspace._mdi.viewMode() == QMdiArea.ViewMode.TabbedView
    workspace._mode_buttons["tile"].click()
    assert workspace._mdi.viewMode() == QMdiArea.ViewMode.SubWindowView


def test_same_symbol_focuses_window(workspace):
    """UT-GUI-020.003.M01.T01: Same symbol focuses its window."""
    workspace.open_symbol("AAPL")
    count = workspace.window_count
    workspace.open_symbol("aapl")
    assert workspace.window_count == count
    active = workspace._mdi.activeSubWindow()
    assert active is not None and active.widget().current_symbol == "AAPL"
    assert active.windowTitle().startswith("AAPL")


def test_seventh_symbol_reuses_active(workspace):
    """UT-GUI-020.003.M01.T02: Seventh symbol loads into the active window."""
    while workspace._new_btn.isEnabled():
        workspace._new_btn.click()
    workspace.open_symbol("TSLA")
    assert workspace.window_count == MAX_CHARTS
    active = workspace._mdi.activeSubWindow()
    assert active is not None and active.widget().current_symbol == "TSLA"


def test_quick_chart_viewer_removed():
    """UT-GUI-020.004.M01.T01: Quick Chart Viewer is gone."""
    assert not hasattr(screener_panel, "QuickChartWindow")
    assert hasattr(screener_panel.ScreenerPanel, "chart_requested")
