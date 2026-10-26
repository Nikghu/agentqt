"""Tests for the tiled Dashboard (FO-GUI-025, Phase 1)."""
from __future__ import annotations

import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QLabel

from us_swing.data.models import AccountState
from us_swing.execution.equity_snapshot import CurvePoint
from us_swing.execution.trade_cycle import StrategyPnlSummary
from us_swing.gui._types import OpenPosition
from us_swing.gui.dashboard_tiles import ROW_H, TILES, KpiStrip, StrategyPnlList, Tile, TileGrid
from us_swing.gui.performance_band import (
    ExposureView,
    PerformanceBand,
    change_text,
    exposure_bars,
    MAX_BARS,
)


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
        user_id=1, equity=25_000.0, start_of_day_equity=24_958.25,
        open_position_value=0.0, daily_pnl=12.0, total_cash_value=13_579.48,
    )
    svc.get_all_trades.return_value = []
    svc.get_system_config.return_value = SimpleNamespace(market_timezone="US/Eastern")
    svc.get_watchlist_items.return_value = []
    svc.get_strategy_pnl.return_value = StrategyPnlSummary(today=8.55)
    svc.get_open_symbols_for_strategy.return_value = ["NDAQ"]
    svc.get_equity_curve.return_value = ()
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


# ── Phase 2: tile buttons (SRD-GUI-025.008–.012) ──────────────────────────────

_ET = datetime.timezone(datetime.timedelta(hours=-4))


def _trade(symbol: str, days_ago: int, state: str) -> SimpleNamespace:
    when = datetime.datetime.now(_ET) - datetime.timedelta(days=days_ago)
    return SimpleNamespace(
        user_id=1, symbol=symbol, side="BUY", quantity=5, filled_quantity=5,
        entry_price=100.0, order_state=state, strategy_id="Breakout", mode="paper",
        entry_time=when,
    )


def _watch_item(symbol: str) -> SimpleNamespace:
    return SimpleNamespace(
        symbol=symbol, ltp=100.0, change=1.0, change_pct=1.0, day_open=99.0,
        day_high=101.0, day_low=98.0, volume=1_000, year_high=120.0, year_low=80.0,
        market_cap=1e9,
    )


def test_filter_hides_other_symbols(qtbot, settings):
    """UT-GUI-025.008.M02.T01: Filter text hides rows whose symbol does not match."""
    panel = _panel(qtbot, _service([_pos("NDAQ", 100, 101), _pos("MSFT", 400, 401)]), settings)
    panel._filter_btn.click()
    panel._pos_filter.setText("nd")
    assert not panel._pos_view.isRowHidden(0)
    assert panel._pos_view.isRowHidden(1)
    assert panel._pos_status_lbl.text().startswith("1 of 2")


def test_closing_filter_shows_all(qtbot, settings):
    """UT-GUI-025.008.M02.T02: Closing the filter clears it and shows every row."""
    panel = _panel(qtbot, _service([_pos("NDAQ", 100, 101), _pos("MSFT", 400, 401)]), settings)
    panel._filter_btn.click()
    panel._pos_filter.setText("zzz")
    panel._filter_btn.click()
    assert panel._pos_filter.text() == ""
    assert not panel._pos_view.isRowHidden(0) and not panel._pos_view.isRowHidden(1)
    assert panel._pos_status_lbl.text().startswith("2")


def test_hidden_column_remembered(qtbot, settings):
    """UT-GUI-025.009.M02.T01: An unticked column is hidden and stays hidden after restart."""
    panel = _panel(qtbot, _service([_pos("NDAQ", 100, 101)]), settings)
    panel._set_column_shown("Stop", False)
    stop = panel._pos_col_names().index("Stop")
    assert panel._pos_view.isColumnHidden(stop)
    again = _panel(qtbot, _service([]), settings)
    assert again._pos_view.isColumnHidden(again._pos_col_names().index("Stop"))


def test_symbol_column_cannot_hide(qtbot, settings):
    """UT-GUI-025.009.M02.T02: Symbol is greyed out in the menu and never hidden."""
    panel = _panel(qtbot, _service([]), settings)
    menu = panel._columns_menu()
    symbol_action = next(a for a in menu.actions() if a.text() == "Symbol")
    assert not symbol_action.isEnabled()
    panel._set_column_shown("Symbol", False)
    panel._set_column_shown("User", False)
    names = panel._pos_col_names()
    assert not panel._pos_view.isColumnHidden(names.index("Symbol"))
    assert not panel._pos_view.isColumnHidden(names.index("User"))


def _history_panel(qtbot, settings):
    svc = _service([])
    svc.get_all_trades.return_value = [
        _trade("A", 0, "FILLED"), _trade("B", 0, "CANCELLED"),
        _trade("C", 3, "FILLED"), _trade("D", 40, "FILLED"),
    ]
    return _panel(qtbot, svc, settings)


def _pick(button, text: str) -> None:
    next(a for a in button.menu().actions() if a.text() == text).trigger()


def test_history_range_and_state(qtbot, settings):
    """UT-GUI-025.010.M02.T01: Range and state menus filter the orders and set the count."""
    panel = _history_panel(qtbot, settings)
    assert panel._hist_model.rowCount() == 2
    _pick(panel._hist_state_btn, "Filled")
    assert panel._hist_model.rowCount() == 1
    _pick(panel._hist_range_btn, "7 days")
    assert panel._hist_model.rowCount() == 2
    _pick(panel._hist_state_btn, "All")
    _pick(panel._hist_range_btn, "All")
    assert panel._hist_model.rowCount() == 4
    assert panel._hist_tile.count_lbl.text().startswith("All")


def test_history_choice_remembered(qtbot, settings):
    """UT-GUI-025.010.M02.T02: Range and state come back after a restart; bad value falls back."""
    panel = _history_panel(qtbot, settings)
    _pick(panel._hist_range_btn, "30 days")
    _pick(panel._hist_state_btn, "Cancelled")
    again = _history_panel(qtbot, settings)
    assert again._hist_range_btn.text() == "30 days"
    assert again._hist_state_btn.text() == "State: Cancelled"
    assert again._hist_model.rowCount() == 1
    settings.setValue("hist_range", "bogus")
    third = _history_panel(qtbot, settings)
    assert third._hist_range_btn.text() == "Today"


def test_export_writes_shown_rows(qtbot, settings, tmp_path):
    """UT-GUI-025.011.M02.T01: Export writes the header and the shown rows to CSV."""
    import csv
    panel = _history_panel(qtbot, settings)
    out = tmp_path / "orders.csv"
    panel.export_history(str(out))
    rows = list(csv.reader(out.open(encoding="utf-8")))
    assert rows[0][:3] == ["User", "Date & Time", "Symbol"]
    assert sorted(r[2] for r in rows[1:]) == ["A", "B"]


def test_export_bad_path_logs_error(qtbot, settings, tmp_path, caplog):
    """UT-GUI-025.011.M02.T02: A path that cannot be written logs an error, no crash."""
    panel = _history_panel(qtbot, settings)
    with patch("us_swing.gui.dashboard_panel.QMessageBox.warning") as warn:
        panel.export_history(str(tmp_path))      # a folder, not a file
    assert any("[Trade History] Could not save" in r.message for r in caplog.records)
    warn.assert_called_once()


def test_watch_row_cross_removes_symbol(qtbot, settings):
    """UT-GUI-025.012.M01.T01: Clicking ✕ removes that row's symbol from the watchlist."""
    svc = _service([])
    svc.get_watchlist_items.return_value = [_watch_item("AAPL"), _watch_item("MSFT")]
    panel = _panel(qtbot, svc, settings)
    model = panel._watch_list._model
    assert model.data(model.index(1, model.remove_col)) == "✕"
    panel._watch_list._on_cell_clicked(model.index(1, model.remove_col))
    svc.remove_from_watchlist.assert_called_once_with("MSFT")


def test_watch_other_cell_does_not_remove(qtbot, settings):
    """UT-GUI-025.012.M01.T02: Clicking any other cell removes nothing; right panel has no ✕."""
    svc = _service([])
    svc.get_watchlist_items.return_value = [_watch_item("AAPL")]
    panel = _panel(qtbot, svc, settings)
    model = panel._watch_list._model
    panel._watch_list._on_cell_clicked(model.index(0, 0))
    svc.remove_from_watchlist.assert_not_called()
    assert panel._watchlist_tab._model.remove_col == -1


def test_filter_and_columns_survive_reload(qtbot, settings):
    """UT-GUI-025.008.M02.T03: Hidden rows and columns stay after a price refresh and scope switch."""
    svc = _service([_pos("NDAQ", 100, 101), _pos("MSFT", 400, 401)])
    panel = _panel(qtbot, svc, settings)
    panel._set_column_shown("Stop", False)
    panel._filter_btn.click()
    panel._pos_filter.setText("ms")
    panel._refresh_positions()
    svc.get_viewing_uid.return_value = 1
    panel._on_scope_changed()
    names = panel._pos_col_names()
    assert "User" not in names
    assert panel._pos_view.isColumnHidden(names.index("Stop"))
    assert panel._pos_view.isRowHidden(0) and not panel._pos_view.isRowHidden(1)


def test_right_panel_shows_saved_watchlist_on_start(qtbot, settings):
    """UT-GUI-025.019.M02.T01: The right-panel watchlist shows saved stocks with no feed update."""
    svc = _service([])
    svc.get_watchlist_items.return_value = [_watch_item("AAPL"), _watch_item("NVDA")]
    panel = _panel(qtbot, svc, settings)
    assert panel.watchlist_widget.symbol_count == 2
    assert panel.watchlist_widget._empty_lbl.isHidden()


def test_watch_columns_survive_reload(qtbot, settings):
    """UT-GUI-025.012.M01.T03: Tile watchlist keeps its hidden columns after new quotes."""
    svc = _service([])
    svc.get_watchlist_items.return_value = [_watch_item("AAPL")]
    panel = _panel(qtbot, svc, settings)
    panel._watch_list.reload()
    view = panel._watch_list.table_view
    assert view.isColumnHidden(4) and not view.isColumnHidden(panel._watch_list._model.remove_col)


# ── Phase 4: Performance band and Exposure tab (SRD-GUI-025.013–.015) ─────────

_CURVE = (CurvePoint("2026-10-24T13:30:00", 25_000.0),
          CurvePoint("2026-10-24T14:00:00", 25_041.75))


def test_change_text_for_range():
    """UT-GUI-025.013.M03.T01: Change shows amount, percent and the range words."""
    assert change_text(_CURVE, "1D") == ("+$41.75 (+0.17%) today", pytest.approx(41.75))
    down = (_CURVE[1], _CURVE[0])
    assert change_text(down, "1W")[0] == "−$41.75 (−0.17%) this week"


def test_change_text_needs_two_points():
    """UT-GUI-025.013.M03.T02: Fewer than two points gives no change text."""
    assert change_text(_CURVE[:1], "1D") == ("", 0.0)


def test_band_shows_value_change_and_chart(qtbot):
    """UT-GUI-025.013.M03.T03: Band shows equity, change and passes points to the chart."""
    band = PerformanceBand()
    qtbot.addWidget(band)
    band.set_range("3M")
    band.show_curve(_CURVE, lambda iso: iso[11:16])
    assert band.range_key == "3M"
    assert band.value_lbl.text() == "$25,041.75"
    assert band.change_lbl.text().endswith("in 3 months")
    assert len(band.chart.points) == 2


def test_band_unknown_range_falls_back(qtbot):
    """UT-GUI-025.013.M03.T04: An unknown saved range selects 1D; empty curve has no change."""
    band = PerformanceBand()
    qtbot.addWidget(band)
    band.set_range("5Y")
    band.show_curve((), str)
    assert band.range_key == "1D"
    assert band.change_lbl.text() == ""
    assert band.value_lbl.text() == "—"


def test_exposure_bars_sum_and_sort():
    """UT-GUI-025.015.M03.T01: Value per symbol and side, largest first, entry price fallback."""
    bars = exposure_bars([_pos("NDAQ", 100, 103.23, qty=19), _pos("MSFT", 431.2, 427.9, 5, "SHORT"),
                          _pos("NDAQ", 100, 103.23, qty=1), _pos("AMD", 160.0, 0.0, qty=20)])
    assert [(b.symbol, b.side) for b in bars] == [("AMD", "Long"), ("MSFT", "Short"),
                                                  ("NDAQ", "Long")]
    assert bars[0].value == pytest.approx(3200.0)
    assert bars[2].value == pytest.approx(2064.6)


def test_exposure_view_totals_and_percent(qtbot):
    """UT-GUI-025.015.M03.T02: Totals and % of equity labels; no equity shows a dash."""
    view = ExposureView()
    qtbot.addWidget(view)
    positions = [_pos("AAPL", 200, 200.0, qty=10), _pos("MSFT", 400, 400.0, 5, "SHORT")]
    view.show_positions(positions, 10_000.0, as_percent=True)
    assert view.values["Long"].text() == "$2,000"
    assert view.values["Short"].text() == "$2,000"
    assert view.values["Net"].text() == "$0"
    assert view.values["Gross ÷ Equity"].text() == "40.0%"
    assert view.chart.labels == ["20.0%", "20.0%"]
    view.show_positions(positions, 0.0, as_percent=True)
    assert view.values["Gross ÷ Equity"].text() == "—"
    assert view.chart.labels == ["$2,000", "$2,000"]


def test_band_shown_by_default_and_toggle_remembered(qtbot, settings):
    """UT-GUI-025.014.M02.T01: Band open on first start; hiding it is remembered."""
    panel = _panel(qtbot, _service([]), settings)
    assert not panel._perf_card.isHidden() and panel._perf_btn.isChecked()
    panel._perf_btn.click()
    assert panel._perf_card.isHidden()
    again = _panel(qtbot, _service([]), settings)
    assert again._perf_card.isHidden() and not again._perf_btn.isChecked()


def test_band_range_asks_service_and_is_remembered(qtbot, settings):
    """UT-GUI-025.013.M02.T01: Picking 1W asks for the 1W curve and is kept for next start."""
    svc = _service([])
    svc.get_equity_curve.return_value = _CURVE
    panel = _panel(qtbot, svc, settings)
    panel._perf_band.ranges.buttons[1].click()
    svc.get_equity_curve.assert_called_with("1W")
    assert panel._perf_band.chart.points == _CURVE
    again = _panel(qtbot, _service([]), settings)
    assert again._perf_band.range_key == "1W"


def test_exposure_tab_swaps_view_and_tools(qtbot, settings):
    """UT-GUI-025.015.M02.T01: Exposure tab shows bars and the unit switch, hides filter tools."""
    panel = _panel(qtbot, _service([_pos("NDAQ", 100, 101, qty=19)]), settings)
    panel._pos_tabs.buttons[1].click()
    assert panel._pos_stack.currentWidget() is panel._exposure
    assert panel._filter_btn.isHidden() and panel._cols_btn.isHidden()
    assert not panel._expo_units.isHidden()
    assert panel._exposure.chart.labels == ["$1,919"]
    panel._expo_units.buttons[1].click()
    assert panel._exposure.chart.labels == ["7.7%"]
    panel._pos_tabs.buttons[0].click()
    assert panel._pos_stack.currentWidget() is panel._pos_view
    assert not panel._filter_btn.isHidden() and panel._expo_units.isHidden()


def test_many_symbols_grouped_into_others(qtbot):
    """UT-GUI-025.015.M03.T03: Beyond 8 bars the smallest join one "others" bar; totals stay whole."""
    positions = [_pos(f"S{i}", 10, 10.0 + i, qty=10) for i in range(12)]
    bars = exposure_bars(positions)
    assert len(bars) == MAX_BARS
    assert bars[-1].symbol == "5 others" and bars[-1].side == "Mixed"
    view = ExposureView()
    qtbot.addWidget(view)
    view.show_positions(positions, 0.0, as_percent=False)
    assert view.values["Long"].text() == f"${sum(100 + 10 * i for i in range(12)):,}"


# ── Phase 5: position table and P&L Today (SRD-GUI-025.016–.018) ──────────────

def test_side_column_and_unset_stop_target(qtbot):
    """UT-GUI-025.016.M04.T01: Side shows LONG / SHORT; unset stop and target read "No stop" / "—"."""
    from us_swing.gui.position_table_model import PositionTableModel
    model = PositionTableModel()
    short = _pos("NDAQ", 102.78, 103.23, qty=19, side="SHORT")
    long_ = _pos("AAPL", 200.0, 210.0, qty=2)
    long_.stop_loss, long_.target_price = 195.5, 230.0
    model.refresh([short, long_])
    cols = model.COLUMNS
    cell = lambda row, name: model.data(model.index(row, cols.index(name)))   # noqa: E731
    assert cols[:3] == ["Symbol", "Side", "Qty"]
    assert (cell(0, "Side"), cell(0, "P&L ($)")) == ("SHORT", "-$8.55")
    assert (cell(0, "Stop"), cell(0, "Target")) == ("No stop", "—")
    assert (cell(1, "Side"), cell(1, "Stop"), cell(1, "Target")) == ("LONG", "$195.50", "$230.00")


def test_side_column_with_user_column(qtbot):
    """UT-GUI-025.016.M04.T02: With the User column shown, Side still follows Symbol."""
    from us_swing.gui.position_table_model import PositionTableModel
    model = PositionTableModel()
    model.set_show_user(True, {1: "trader"})
    model.refresh([_pos("MSFT", 431.2, 427.9, qty=5, side="SHORT")])
    row = [model.data(model.index(0, c)) for c in range(model.columnCount())]
    assert row[:3] == ["trader", "MSFT", "SHORT"]
    assert row[-1] == "OPEN"


def test_pnl_today_is_equity_change(qtbot, settings):
    """UT-GUI-025.018.M02.T01: P&L Today = equity − start-of-day equity, not the realised field."""
    svc = _service([])
    svc.get_account_state.return_value = AccountState(
        user_id=1, equity=1_950.0, start_of_day_equity=2_000.0, open_position_value=0.0,
        daily_pnl=30.0, total_cash_value=1_000.0)
    panel = _panel(qtbot, svc, settings)
    assert panel._kpi.value("pnl") == "−$50.00"
