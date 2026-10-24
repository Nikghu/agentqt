"""Tests for the tiled Dashboard (FO-GUI-025, Phase 1)."""
from __future__ import annotations

import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QLabel

from us_swing.data.models import AccountState
from us_swing.execution.trade_cycle import StrategyPnlSummary
from us_swing.gui._types import OpenPosition
from us_swing.gui.dashboard_tiles import ROW_H, TILES, KpiStrip, StrategyPnlList, Tile, TileGrid


def _pos(symbol: str, avg: float, cur: float, qty: int = 10, side: str = "LONG") -> OpenPosition:
    return OpenPosition(
        symbol=symbol, user_id=1, quantity=qty, average_price=avg, stop_loss=0.0,
        target_price=0.0, mode="paper", trailing_stop=False, filled_quantity=qty,
        total_quantity=qty, current_price=cur, strategy_id="", trade_id="",
        entry_time=datetime.datetime(2026, 10, 24, 9, 35), direction=side,
    )


@pytest.fixture()
def grid(qtbot):
    tiles = {name: Tile(name, QLabel(name)) for name in TILES}
    widget = TileGrid(tiles)
    qtbot.addWidget(widget)
    return widget, tiles


def test_maximise_hides_other_tiles(grid):
    """UT-GUI-025.004.M01.T01: Maximise shows only that tile and flips its button."""
    widget, tiles = grid
    tiles["history"].max_btn.click()
    assert widget.maximised == "history"
    assert [n for n in TILES if widget.is_shown(n)] == ["history"]
    assert tiles["history"].max_btn.toolTip() == "Restore"


def test_second_click_restores_grid(grid):
    """UT-GUI-025.004.M01.T02: Clicking Maximise again restores all four tiles."""
    widget, tiles = grid
    seen: list[str] = []
    widget.changed.connect(seen.append)
    tiles["watch"].max_btn.click()
    tiles["watch"].max_btn.click()
    assert widget.maximised == ""
    assert all(widget.is_shown(n) for n in TILES)
    assert tiles["watch"].max_btn.toolTip() == "Maximise"
    assert seen == ["watch", ""]


def test_unknown_tile_name_restores(grid):
    """UT-GUI-025.004.M01.T03: An unknown saved tile name falls back to the full grid."""
    widget, _tiles = grid
    widget.set_maximised("positions")
    widget.set_maximised("no-such-tile")
    assert widget.maximised == ""
    assert all(widget.is_shown(n) for n in TILES)


def test_kpi_strip_values(qtbot):
    """UT-GUI-025.001.M01.T01: KPI strip shows a value and its optional note."""
    strip = KpiStrip()
    qtbot.addWidget(strip)
    strip.set_value("cap", "45.8%", sub="of 95%")
    strip.set_value("pos", "5")
    assert strip.value("cap") == "45.8%"
    assert not strip._subs["cap"].isHidden()
    assert strip._subs["pos"].isHidden()


def test_strategy_bars_scale_to_largest(qtbot):
    """UT-GUI-025.005.M01.T01: Bars scale to the largest P&L; total sums the rows."""
    bars = StrategyPnlList()
    qtbot.addWidget(bars)
    bars.set_rows([("Pullback", "2 open", 49.5), ("Breakout", "1 open", -16.3)])
    assert bars.bars[0].fraction == pytest.approx(1.0)
    assert bars.bars[1].fraction == pytest.approx(-16.3 / 49.5)
    assert bars.total_lbl.text() == "+$33.20"
    assert bars.empty_lbl.isHidden()


def test_strategy_bars_empty(qtbot):
    """UT-GUI-025.005.M01.T02: No strategies shows the empty text and a zero total."""
    bars = StrategyPnlList()
    qtbot.addWidget(bars)
    bars.set_rows([])
    assert not bars.empty_lbl.isHidden()
    assert bars.total_lbl.text() == "$0.00"


# ── DashboardPanel wiring (SRD-GUI-025.001/.002/.006) ─────────────────────────

def _service(positions: list[OpenPosition]) -> MagicMock:
    svc = MagicMock()
    svc.get_users.return_value = [SimpleNamespace(user_id=1, username="trader")]
    svc.get_viewing_uid.return_value = None
    svc.get_positions.return_value = positions
    svc.get_account_state.return_value = AccountState(
        user_id=1, equity=25_000.0, start_of_day_equity=25_000.0,
        open_position_value=0.0, daily_pnl=41.75, total_cash_value=13_579.48,
    )
    svc.get_all_trades.return_value = []
    svc.get_system_config.return_value = SimpleNamespace(market_timezone="US/Eastern")
    svc.get_watchlist_items.return_value = []
    svc.get_strategy_pnl.return_value = StrategyPnlSummary(today=8.55)
    svc.get_open_symbols_for_strategy.return_value = ["NDAQ"]
    return svc


@pytest.fixture()
def settings(tmp_path):
    store = QSettings(str(tmp_path / "dash.ini"), QSettings.Format.IniFormat)
    yield store
    store.clear()


def _panel(qtbot, svc, settings):
    from us_swing.gui.dashboard_panel import DashboardPanel
    strategies = [SimpleNamespace(name="Acc/Dist")]
    with patch("us_swing.gui.dashboard_panel.load_strategies", return_value=strategies), \
         patch("us_swing.universe.store.load_sp500", return_value=[]):
        panel = DashboardPanel(svc, settings=settings)
    qtbot.addWidget(panel)
    return panel


def test_panel_kpis_from_positions(qtbot, settings):
    """UT-GUI-025.001.M02.T01: Strip shows unrealised P&L, positions, P&L today and capital."""
    svc = _service([_pos("NDAQ", 102.78, 103.23, qty=19), _pos("MSFT", 431.2, 427.9, 5, "SHORT")])
    panel = _panel(qtbot, svc, settings)
    assert panel._kpi.value("pos") == "2"
    assert panel._kpi.value("unreal") == "+$25.05"
    assert panel._kpi.value("pnl") == "+$41.75"
    assert panel._kpi.value("cash") == "$13,579.48"
    assert panel._strategy_list.total_lbl.text() == "+$8.55"


def test_view_switch_sets_scope(qtbot, settings):
    """UT-GUI-025.002.M02.T01: Clicking a user in the view switch scopes the dashboard."""
    svc = _service([])
    panel = _panel(qtbot, svc, settings)
    panel._view_chips.buttons[1].click()
    svc.set_viewing_uid.assert_called_with(1)
    assert settings.value("view_uid") == "1"


def test_density_and_maximised_remembered(qtbot, settings):
    """UT-GUI-025.006.M02.T01: Density and maximised tile come back after a restart."""
    panel = _panel(qtbot, _service([]), settings)
    panel._density_chips.buttons[0].click()          # Comfort
    panel._strategy_tile.max_btn.click()
    again = _panel(qtbot, _service([]), settings)
    assert again._density_chips.value == "comfort"
    assert again._pos_view.verticalHeader().defaultSectionSize() == ROW_H["comfort"]
    assert again._grid.maximised == "strategy"


def test_defaults_without_saved_settings(qtbot, settings):
    """UT-GUI-025.006.M02.T02: First start is Compact, full grid, no scope change."""
    svc = _service([])
    panel = _panel(qtbot, svc, settings)
    assert panel._density_chips.value == "compact"
    assert panel._grid.maximised == ""
    svc.set_viewing_uid.assert_not_called()
