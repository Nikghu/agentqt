"""
Module: MD-GUI-013.001.M01, MD-GUI-004.001.M02, MD-GUI-014.001.M01–M03 — trade direction GUI tests
Parent SRD: SRD-GUI-013.016–.019, SRD-GUI-014.016–.018

Long / Short surfaces added for FO-EXE-018: the Strategy Builder Direction selector,
the strategy table column, the Active Trades Side column and confirm wording, and the
risk-editor ranges for a short cycle.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import Qt
from pytestqt.qtbot import QtBot

from us_swing.data.models import AccountState  # noqa: F401  (loads data before db — breaks an import cycle)
from us_swing.execution.strategy_engine import Action, TradeSignal
from us_swing.execution.trade_cycle._dto import CycleSnapshot, TradeCycleState
from us_swing.gui.active_cycles_model import Col, _ActiveCyclesModel
from us_swing.gui.active_cycles_panel import ActiveCyclesPanel
from us_swing.gui.risk_editor_widget import _RiskEditorWidget
from us_swing.gui.strategy_builder_dialog import StrategyBuilderDialog
from us_swing.gui.strategy_store import StrategyConfig
from us_swing.gui.strategy_table_model import COL_DIRECTION, StrategyTableModel
from us_swing.gui.theme import C


def _cfg(**overrides: object) -> StrategyConfig:
    values: dict[str, object] = {
        "name": "FADE",
        "mode": "manual",
        "capital_max": 25,
        "start_time": "09:30",
        "end_time": "15:30",
        "start_date": "2026-09-17",
        "end_date": "2027-03-17",
        "days": ["Mon"],
        "entry_condition": "(Number(1)) == (Number(1))",
        "exit_condition": "(Number(1)) == (Number(1))",
    }
    values.update(overrides)
    return StrategyConfig(**values)  # type: ignore[arg-type]


def _dialog(qtbot: QtBot, **kwargs: Any) -> StrategyBuilderDialog:
    dlg = StrategyBuilderDialog(**kwargs)
    qtbot.addWidget(dlg)
    return dlg


def _saved(dlg: StrategyBuilderDialog) -> list[StrategyConfig]:
    out: list[StrategyConfig] = []
    dlg.strategy_saved.connect(out.append)
    return out


# ── Strategy Builder (SRD-GUI-013.016–.018) ───────────────────────────────────


def test_new_strategy_defaults_to_long(qtbot: QtBot) -> None:
    """UT-GUI-013.016.M01.T01: a new strategy starts as Long."""
    dlg = _dialog(qtbot)
    assert dlg._exec_page._direction_combo.currentData() == "LONG"


def test_short_choice_is_saved(qtbot: QtBot) -> None:
    """UT-GUI-013.016.M01.T02: picking Short saves direction SHORT."""
    dlg = _dialog(qtbot, existing=_cfg(), existing_names={"FADE"})
    combo = dlg._exec_page._direction_combo
    combo.setCurrentIndex(combo.findData("SHORT"))
    saved = _saved(dlg)

    dlg._on_save()

    assert [c.direction for c in saved] == ["SHORT"]


def test_edit_loads_stored_direction(qtbot: QtBot) -> None:
    """UT-GUI-013.016.M01.T03: editing a Short strategy shows Short."""
    dlg = _dialog(qtbot, existing=_cfg(direction="SHORT"), existing_names={"FADE"})
    assert dlg._exec_page._direction_combo.currentText() == "Short"


def test_direction_locked_while_trades_open(qtbot: QtBot) -> None:
    """UT-GUI-013.017.M01.T04: with open trades the Direction combo is disabled; other fields are not."""
    dlg = _dialog(qtbot, existing=_cfg(), existing_names={"FADE"}, has_open_trades=True)
    combo = dlg._exec_page._direction_combo
    assert not combo.isEnabled()
    assert combo.toolTip() == "Close open trades before changing direction"
    assert dlg._exec_page._trade_type_combo.isEnabled()


def test_direction_editable_without_open_trades(qtbot: QtBot) -> None:
    """UT-GUI-013.017.M01.T05: with no open trades the Direction combo is enabled."""
    dlg = _dialog(qtbot, existing=_cfg(), existing_names={"FADE"}, has_open_trades=False)
    assert dlg._exec_page._direction_combo.isEnabled()


def test_no_stop_note_for_short(qtbot: QtBot) -> None:
    """UT-GUI-013.018.M01.T06: Short with stop loss off shows the note; Save still works."""
    dlg = _dialog(qtbot, existing=_cfg(stoploss_enabled=False), existing_names={"FADE"})
    combo = dlg._exec_page._direction_combo
    combo.setCurrentIndex(combo.findData("SHORT"))
    saved = _saved(dlg)

    assert not dlg._risk_page._short_note.isHidden()
    dlg._on_save()
    assert len(saved) == 1


def test_no_note_when_stop_on_or_long(qtbot: QtBot) -> None:
    """UT-GUI-013.018.M01.T07: the note hides for Short with a stop, and for Long without one."""
    dlg = _dialog(qtbot, existing=_cfg(direction="SHORT", stoploss_enabled=False), existing_names={"FADE"})
    note = dlg._risk_page._short_note
    assert not note.isHidden()

    dlg._risk_page._sl_enabled.setChecked(True)
    assert note.isHidden()

    dlg._risk_page._sl_enabled.setChecked(False)
    combo = dlg._exec_page._direction_combo
    combo.setCurrentIndex(combo.findData("LONG"))
    assert note.isHidden()


def test_unknown_stored_direction_shows_long(qtbot: QtBot) -> None:
    """UT-GUI-013.016.M01.T08: an unknown stored direction shows and saves as Long."""
    dlg = _dialog(qtbot, existing=_cfg(direction="SIDEWAYS"), existing_names={"FADE"})
    saved = _saved(dlg)

    assert dlg._exec_page._direction_combo.currentText() == "Long"
    dlg._on_save()
    assert [c.direction for c in saved] == ["LONG"]


# ── Strategy table (SRD-GUI-013.019) ──────────────────────────────────────────


def test_direction_column_shows_short(qtbot: QtBot) -> None:
    """UT-GUI-013.019.M02.T01: the strategy table has a Direction column showing Short."""
    model = StrategyTableModel()
    model.load([_cfg(direction="SHORT")])
    assert model.headerData(COL_DIRECTION, Qt.Orientation.Horizontal) == "Direction"
    assert model.data(model.index(0, COL_DIRECTION)) == "Short"


def test_legacy_config_shows_long(qtbot: QtBot) -> None:
    """UT-GUI-013.019.M02.T02: a strategy saved before directions existed shows Long."""
    model = StrategyTableModel()
    model.load([_cfg()])
    assert model.data(model.index(0, COL_DIRECTION)) == "Long"


# ── Active Trades model (SRD-GUI-014.016) ─────────────────────────────────────


def _snap(**overrides: object) -> CycleSnapshot:
    values: dict[str, object] = {
        "cycle_id": 7,
        "strategy_id": "FADE",
        "symbol": "AAPL",
        "user_id": 1,
        "state": TradeCycleState.OPEN,
        "entry_time": "2026-09-17T14:00:00",
        "entry_price": 100.0,
        "entry_qty": 10,
        "hard_stop_loss": 102.0,
        "target_price": 96.0,
        "current_price": 97.0,
        "current_pnl_usd": 30.0,
    }
    values.update(overrides)
    return CycleSnapshot(**values)  # type: ignore[arg-type]


def _side_cell(model: _ActiveCyclesModel) -> tuple[Any, Any]:
    idx = model.index(0, int(Col.SIDE))
    fg = model.data(idx, Qt.ItemDataRole.ForegroundRole)
    return model.data(idx), fg.name() if fg is not None else None


def test_short_cycle_row_shows_red_short(qtbot: QtBot) -> None:
    """UT-GUI-014.016.M02.T01: a Short cycle row shows Short in red."""
    model = _ActiveCyclesModel(query=MagicMock(), pending_store=MagicMock())
    model.on_cycle_opened(_snap(direction="SHORT"))
    assert _side_cell(model) == ("Short", C.RED.lower())


def test_pending_long_row_shows_green_long(qtbot: QtBot) -> None:
    """UT-GUI-014.016.M02.T02: a pending Long entry row shows Long in green."""
    model = _ActiveCyclesModel(query=MagicMock(), pending_store=MagicMock())
    model.on_pending_added(TradeSignal(action=Action.ENTRY, symbol="AAPL", strategy_id="FADE"))
    assert _side_cell(model) == ("Long", C.GREEN.lower())


def test_unknown_direction_shows_long(qtbot: QtBot) -> None:
    """UT-GUI-014.016.M02.T03: a row with no recognised direction shows Long, never blank or Short."""
    model = _ActiveCyclesModel(query=MagicMock(), pending_store=MagicMock())
    model.on_cycle_opened(_snap(direction=""))
    assert _side_cell(model) == ("Long", C.GREEN.lower())


# ── Active Trades confirmations (SRD-GUI-014.017) ─────────────────────────────


def _panel(
    signals: list[TradeSignal] | None = None, snap: CycleSnapshot | None = None
) -> tuple[Any, list[str], MagicMock]:
    texts: list[str] = []
    affordability = MagicMock(return_value=(True, None))

    def _confirm(_title: str, text: str, **_kw: Any) -> bool:
        texts.append(text)
        return False

    fake = SimpleNamespace(
        _pending=SimpleNamespace(list=lambda: signals or []),
        _cycle_query=SimpleNamespace(cycle=lambda _cid: snap),
        _affordability=affordability,
        _confirm=_confirm,
    )
    return fake, texts, affordability


def _signal(action: Action, direction: str) -> TradeSignal:
    return TradeSignal(action=action, symbol="AAPL", strategy_id="FADE",
                       qty_recommended=10, signal_id="sig-1", direction=direction)


def test_short_entry_confirm_says_sell_short() -> None:
    """UT-GUI-014.017.M01.T01: a pending Short entry asks to Sell short and checks margin."""
    fake, texts, affordability = _panel([_signal(Action.ENTRY, "SHORT")])
    ActiveCyclesPanel._on_execute_clicked(fake, "sig-1")
    assert texts[0].startswith("Submit Sell short 10 × AAPL")
    affordability.assert_called_once()


def test_short_exit_confirm_says_buy_to_cover() -> None:
    """UT-GUI-014.017.M01.T02: a pending Short exit asks to Buy to cover without a margin check."""
    fake, texts, affordability = _panel([_signal(Action.EXIT, "SHORT")])
    ActiveCyclesPanel._on_execute_clicked(fake, "sig-1")
    assert texts[0].startswith("Submit Buy to cover 10 × AAPL")
    affordability.assert_not_called()


def test_close_short_cycle_says_buy_to_cover() -> None:
    """UT-GUI-014.017.M01.T03: closing an open Short asks to Buy to cover and shows its profit."""
    fake, texts, _aff = _panel(snap=_snap(direction="SHORT"))
    ActiveCyclesPanel._on_close_clicked(fake, 7)
    assert "Buy to cover 10 × AAPL" in texts[0]
    assert "+$30.00" in texts[0]


def test_short_entry_blocked_when_margin_short() -> None:
    """UT-GUI-014.017.M01.T04: a Short entry the margin cannot cover disables the confirm button."""
    fake, _texts, affordability = _panel([_signal(Action.ENTRY, "SHORT")])
    affordability.return_value = (False, "Not enough Margin Available")
    captured: dict[str, Any] = {}

    def _confirm(_title: str, _text: str, **kw: Any) -> bool:
        captured.update(kw)
        return False

    fake._confirm = _confirm
    ActiveCyclesPanel._on_execute_clicked(fake, "sig-1")

    assert captured["confirm_enabled"] is False
    assert captured["warning"] == "Not enough Margin Available"


def test_long_verbs_unchanged() -> None:
    """UT-GUI-014.017.M01.T05: Long entries still say Buy and Long closes still say Sell."""
    fake, texts, _aff = _panel([_signal(Action.ENTRY, "LONG")], snap=_snap(direction="LONG"))
    ActiveCyclesPanel._on_execute_clicked(fake, "sig-1")
    ActiveCyclesPanel._on_close_clicked(fake, 7)
    assert texts[0].startswith("Submit Buy 10 × AAPL")
    assert "Sell 10 × AAPL" in texts[1]


# ── Risk editor (SRD-GUI-014.018) ─────────────────────────────────────────────


def _editor(qtbot: QtBot, **overrides: object) -> _RiskEditorWidget:
    values: dict[str, object] = {"current_price": 100.0}
    values.update(overrides)
    w = _RiskEditorWidget(_snap(**values))
    qtbot.addWidget(w)
    return w


def test_short_ranges_flip_around_price(qtbot: QtBot) -> None:
    """UT-GUI-014.018.M03.T01: a Short editor keeps the stop at or above and the target at or below the price."""
    w = _editor(qtbot, direction="SHORT")
    assert w._hsl.minimum() == pytest.approx(100.0)
    assert w._target.maximum() == pytest.approx(100.0)


def test_short_stop_cannot_go_below_price(qtbot: QtBot) -> None:
    """UT-GUI-014.018.M03.T02: a Short stop typed below the price is held at the price."""
    w = _editor(qtbot, direction="SHORT")
    w._hsl.setValue(95.0)
    assert w._hsl.value() == pytest.approx(100.0)


def test_long_ranges_unchanged(qtbot: QtBot) -> None:
    """UT-GUI-014.018.M03.T03: a Long editor keeps the stop at or below and the target at or above the price."""
    w = _editor(qtbot, direction="LONG", hard_stop_loss=98.0, target_price=104.0)
    assert w._hsl.maximum() == pytest.approx(100.0)
    assert w._target.minimum() == pytest.approx(100.0)


def test_short_without_stop_saves_no_stop_unless_edited(qtbot: QtBot) -> None:
    """UT-GUI-014.018.M03.T04: saving a Short with no stop does not add a stop at the current price."""
    w = _editor(qtbot, direction="SHORT", hard_stop_loss=0.0)
    assert "hard_sl" not in w._collect_changed_fields()
    w._hsl.setValue(105.0)
    assert w._collect_changed_fields()["hard_sl"] == pytest.approx(105.0)
