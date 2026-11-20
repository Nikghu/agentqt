"""Tests for Dashboard Exit and Stop / Trail through strategy trades (FO-GUI-019)."""
from __future__ import annotations

import us_swing.data  # noqa: F401  (import order: avoids the db/data import cycle)

import datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import sqlalchemy as sa
from PyQt6.QtWidgets import QDialog
from sqlalchemy.pool import StaticPool

from us_swing.db.schema import create_schema
from us_swing.execution.trade_cycle import CycleSnapshot, TradeCycleState
from us_swing.execution.trade_cycle._repository import TradeCycleRepository
from us_swing.execution.trade_cycle._service import TradeCycleService
from us_swing.gui._types import OpenPosition
from us_swing.gui import position_trades as pt

from PyQt6.QtCore import QSettings

from tests.gui.test_dashboard_tiles import _panel, _service


@pytest.fixture()
def settings(tmp_path):
    store = QSettings(str(tmp_path / "dash.ini"), QSettings.Format.IniFormat)
    yield store
    store.clear()


@pytest.fixture()
def cycles():
    eng = sa.create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    create_schema(eng)
    service = TradeCycleService(repo=TradeCycleRepository(eng), bus=MagicMock())
    service.start()
    yield service
    service.stop()


def _fill(svc: TradeCycleService, **over: Any) -> CycleSnapshot:
    kw: dict[str, Any] = {
        "strategy_id": "WTrend", "symbol": "DIS", "user_id": 1,
        "entry_order_id": f"ord-{over.get('strategy_id', 'WTrend')}-{over.get('symbol', 'DIS')}"
                          f"-{over.get('user_id', 1)}",
        "entry_price": 119.81, "entry_qty": 8, "fill_time": "2026-11-20T09:35:00",
        "hard_stop_loss": 110.0, "target_price": 140.0, "target_type": "fixed",
        "stoploss_type": "fixed", "trailing_mode": None, "trailing_offset": None,
        "monitoring_session_date": "2026-11-20",
    }
    kw.update(over)
    return svc.on_entry_fill(**kw)


def _pos(symbol: str = "DIS", user_id: int = 1) -> OpenPosition:
    return OpenPosition(
        symbol=symbol, user_id=user_id, quantity=8, average_price=119.81, stop_loss=0.0,
        target_price=0.0, mode="paper", trailing_stop=False, filled_quantity=8,
        total_quantity=8, current_price=120.78, strategy_id="", trade_id="",
        entry_time=datetime.datetime(2026, 11, 20, 9, 35),
    )


# ── MD-GUI-019.012.M01 — helpers and popups ──────────────────────────────────

def test_open_trades_match_user_and_symbol(cycles):
    """UT-GUI-019.012.M01.T01: Only open trades of the same user and stock count."""
    mine = _fill(cycles)
    _fill(cycles, user_id=2, strategy_id="Other user")
    _fill(cycles, symbol="EW")
    gone = _fill(cycles, strategy_id="Old")
    cycles.close_cycle_by_id(
        gone.cycle_id, exit_order_id="x", exit_price=120.0, exit_qty=8,
        exit_time="2026-11-20T10:00:00", exit_reason="manual",
    )
    found = pt.open_trades(cycles, 1, "DIS")
    assert [s.cycle_id for s in found] == [mine.cycle_id]
    assert pt.open_trades(cycles, 1, "PRU") == []
    assert pt.open_trades(None, 1, "DIS") == []


def test_exit_text_names_strategy_and_value():
    """UT-GUI-019.013.M01.T01: Confirm text names shares, stock, strategy and value."""
    snap = CycleSnapshot(strategy_id="WTrend", symbol="DIS", entry_qty=8, entry_price=119.81,
                         current_price=120.78, state=TradeCycleState.OPEN)
    text = pt.exit_text(snap)
    assert text.startswith("Sell 8 DIS at market for strategy WTrend?")
    assert "About $966 · Entry $119.81" in text
    short = CycleSnapshot(strategy_id="S", symbol="X", entry_qty=2, entry_price=10.0,
                          direction="SHORT")
    assert pt.exit_text(short).startswith("Buy to cover 2 X")


def test_pick_trade_one_or_chosen(cycles, qtbot):
    """UT-GUI-019.015.M01.T01: One trade needs no question; with two, the picked one is used."""
    a = _fill(cycles)
    b = _fill(cycles, strategy_id="Chart plan - DIS", entry_qty=5)
    assert pt.pick_trade(None, [a]) is a

    def _choose_second(self: pt._PickTradeDialog) -> QDialog.DialogCode:
        assert self.combo.itemText(1) == "Chart plan - DIS · 5 sh"
        self.combo.setCurrentIndex(1)
        return QDialog.DialogCode.Accepted

    with patch.object(pt._PickTradeDialog, "exec", _choose_second):
        assert pt.pick_trade(None, [a, b]) is b


def test_pick_trade_cancel_returns_none(cycles):
    """UT-GUI-019.015.M01.T02: Cancelling the pick returns nothing."""
    trades = [_fill(cycles), _fill(cycles, strategy_id="Other")]
    with patch.object(pt._PickTradeDialog, "exec", return_value=QDialog.DialogCode.Rejected):
        assert pt.pick_trade(None, trades) is None


def test_stop_trail_save_updates_trade(cycles, qtbot):
    """UT-GUI-019.014.M01.T01: Save in the popup writes the new stop on the trade."""
    snap = _fill(cycles)
    dialog = pt.StopTrailDialog(snap, cycles)
    qtbot.addWidget(dialog)
    dialog.editor._hsl.setValue(115.0)
    dialog.editor._save_btn.click()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert cycles.cycle(snap.cycle_id).hard_stop_loss == pytest.approx(115.0)


def test_stop_trail_bad_value_keeps_popup(cycles, qtbot):
    """UT-GUI-019.014.M01.T02: A rejected stop shows its error and the popup stays open."""
    snap = _fill(cycles)
    dialog = pt.StopTrailDialog(snap, cycles)
    qtbot.addWidget(dialog)
    dialog.editor.saved.emit(snap.cycle_id, {"hard_sl": 500.0})
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert not dialog.editor._err_lbl.isHidden()
    assert cycles.cycle(snap.cycle_id).hard_stop_loss == pytest.approx(110.0)


# ── MD-GUI-019.012.M02 — Dashboard wiring ────────────────────────────────────

def _dash(qtbot, settings, cycles, positions, live=False):
    svc = _service(positions)
    svc.cycle_query = cycles
    svc.cycle_cmd = cycles
    svc.live_mutations_blocked.return_value = live
    svc.get_user_by_id.return_value = SimpleNamespace(username="trader")
    panel = _panel(qtbot, svc, settings)
    panel._pos_view.selectRow(0)
    return panel, svc


def test_exit_confirmed_sends_trade_exit(qtbot, settings, cycles):
    """UT-GUI-019.013.M02.T01: Exit on a strategy stock confirms, then exits that trade."""
    snap = _fill(cycles)
    panel, svc = _dash(qtbot, settings, cycles, [_pos()], live=True)
    with patch("us_swing.gui.dashboard_panel.confirm", return_value=True) as ask, \
         patch("us_swing.gui.dashboard_panel.notify") as warn:
        panel.open_exit(0)
    assert "for strategy WTrend" in ask.call_args.args[2]
    svc.force_exit_cycle.assert_called_once_with(snap.cycle_id, "manual")
    warn.assert_not_called()
    assert panel._drawer_pos is None


def test_exit_works_after_price_update(qtbot, settings, cycles):
    """UT-GUI-019.013.M02.T03: A price update keeps the selected row, so Exit still acts."""
    snap = _fill(cycles)
    panel, svc = _dash(qtbot, settings, cycles, [_pos(), _pos("EW")])
    ticked = [_pos(), _pos("EW")]
    ticked[0].current_price = 121.5
    panel._pos_model.refresh(ticked)
    assert [i.row() for i in panel._pos_view.selectionModel().selectedRows()] == [0]
    with patch("us_swing.gui.dashboard_panel.confirm", return_value=True):
        panel.open_exit(0)
    svc.force_exit_cycle.assert_called_once_with(snap.cycle_id, "manual")


def test_new_stock_list_resets_rows(qtbot, settings, cycles):
    """UT-GUI-019.013.M02.T04: A changed stock list still reloads the table."""
    panel, _svc = _dash(qtbot, settings, cycles, [_pos()])
    panel._pos_model.refresh([_pos(), _pos("EW")])
    assert panel._pos_model.rowCount() == 2
    assert panel._pos_view.selectionModel().selectedRows() == []


def test_exit_cancelled_sends_nothing(qtbot, settings, cycles):
    """UT-GUI-019.013.M02.T02: Saying No to the confirm sends no order."""
    _fill(cycles)
    panel, svc = _dash(qtbot, settings, cycles, [_pos()])
    with patch("us_swing.gui.dashboard_panel.confirm", return_value=False):
        panel.open_exit(0)
    svc.force_exit_cycle.assert_not_called()


def test_stop_trail_opens_trade_editor(qtbot, settings, cycles):
    """UT-GUI-019.014.M02.T01: Stop / Trail on a strategy stock opens the trade editor popup."""
    snap = _fill(cycles)
    panel, svc = _dash(qtbot, settings, cycles, [_pos()], live=True)
    with patch("us_swing.gui.dashboard_panel.StopTrailDialog") as dlg:
        panel.open_exit(3)
    assert dlg.call_args.args[0].cycle_id == snap.cycle_id
    assert dlg.call_args.args[1] is cycles
    dlg.return_value.exec.assert_called_once()
    svc.force_exit_cycle.assert_not_called()


def test_manual_position_live_shows_message(qtbot, settings, cycles):
    """UT-GUI-019.017.M02.T01: A manual stock in live mode shows the TWS message only."""
    panel, svc = _dash(qtbot, settings, cycles, [_pos()], live=True)
    with patch("us_swing.gui.dashboard_panel.notify") as warn:
        panel.open_exit(3)
    assert "DIS was not bought by a strategy" in warn.call_args.args[2]
    assert panel._drawer_pos is None
    svc.force_exit_cycle.assert_not_called()


def test_manual_position_paper_opens_drawer(qtbot, settings, cycles):
    """UT-GUI-019.017.M02.T02: A manual stock in paper mode keeps the old Exit drawer."""
    pos = _pos()
    panel, _svc = _dash(qtbot, settings, cycles, [pos])
    with patch("us_swing.gui.dashboard_panel.notify") as warn:
        panel.open_exit(0)
    warn.assert_not_called()
    assert panel._drawer_pos is pos


def test_square_off_exits_trades_and_counts_manual(qtbot, settings, cycles):
    """UT-GUI-019.016.M02.T01: Square Off All exits strategy trades; live manual ones are counted."""
    a = _fill(cycles)
    b = _fill(cycles, symbol="EW", entry_qty=3)
    positions = [_pos(), _pos("EW"), _pos("VRSN")]
    panel, svc = _dash(qtbot, settings, cycles, positions, live=True)
    with patch("us_swing.gui.dashboard_panel.confirm", return_value=True) as ask, \
         patch("us_swing.gui.dashboard_panel.notify") as warn:
        panel._on_square_off_all()
    assert "Exit 2 positions" in ask.call_args.args[2]
    assert [c.args for c in svc.force_exit_cycle.call_args_list] == [
        (a.cycle_id, "manual"), (b.cycle_id, "manual"),
    ]
    assert "1 stock was not bought by a strategy" in warn.call_args.args[2]
    svc.close_position.assert_not_called()
