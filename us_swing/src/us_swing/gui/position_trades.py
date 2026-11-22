"""
Module: MD-GUI-019.012.M01 — Position trade actions
Parent SRD: SRD-GUI-019.012

Links a Dashboard position to the strategy trade that bought it, so Exit and
Stop / Trail go through that trade (SRD-GUI-019.012–.015).
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from PyQt6.QtWidgets import QComboBox, QDialog, QWidget

from us_swing.execution.trade_cycle import InvariantViolation, TradeCycleState
from us_swing.gui.active_cycles_panel import _ConfirmDialog, _order_verb
from us_swing.gui.risk_editor_widget import _RiskEditorWidget
from us_swing.gui.theme import C

if TYPE_CHECKING:
    from us_swing.execution.trade_cycle import CycleSnapshot

log = logging.getLogger(__name__)


def open_trades(query: Any, user_id: int, symbol: str) -> list[CycleSnapshot]:
    """Open strategy trades of *user_id* on *symbol*; empty for a manual position."""
    if query is None:
        return []
    return [
        s for s in query.open_cycles()
        if s.user_id == user_id and s.symbol == symbol and s.state is TradeCycleState.OPEN
    ]


def _trade_label(snap: CycleSnapshot) -> str:
    return f"{snap.strategy_id} · {snap.entry_qty} sh"


def exit_text(snap: CycleSnapshot) -> str:
    """Confirm text for a full exit: headline, then a muted detail line."""
    price = snap.current_price if snap.current_price else snap.entry_price
    verb = _order_verb(snap.direction, True)
    return (
        f"{verb} {snap.entry_qty} {snap.symbol} at market for strategy {snap.strategy_id}?\n"
        f"About ${snap.entry_qty * price:,.0f} · Entry ${snap.entry_price:,.2f}"
    )


def square_off_text(trades: list[CycleSnapshot]) -> str:
    """Confirm text for Square Off All over strategy trades."""
    lines = ", ".join(f"{s.symbol} ({s.entry_qty})" for s in trades)
    noun = "position" if len(trades) == 1 else "positions"
    return f"Exit {len(trades)} {noun} at market through their strategies?\n{lines}"


class _PickTradeDialog(_ConfirmDialog):
    """Asks which strategy trade to act on when one stock has several."""

    def __init__(self, trades: list[CycleSnapshot], parent: QWidget | None = None) -> None:
        symbol = trades[0].symbol
        super().__init__(
            "CHOOSE TRADE",
            f"{symbol} is held by more than one strategy\nPick the trade to use",
            confirm_text="Next",
            parent=parent,
        )
        self.combo = QComboBox()
        self.combo.addItems([_trade_label(s) for s in trades])
        self.combo.setStyleSheet("QComboBox { outline: none; } QComboBox:focus { outline: none; }")
        card = self.findChild(QWidget, "confirm_card")
        if card is not None and card.layout() is not None:
            card.layout().addWidget(self.combo)  # type: ignore[union-attr]


def pick_trade(parent: QWidget | None, trades: list[CycleSnapshot]) -> CycleSnapshot | None:
    """The one trade, or the trade the user picks; None when cancelled."""
    if len(trades) == 1:
        return trades[0]
    dialog = _PickTradeDialog(trades, parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return trades[dialog.combo.currentIndex()]


class StopTrailDialog(_ConfirmDialog):
    """Popup with the Active Trades stop, target and trail editor (SRD-GUI-019.014)."""

    def __init__(self, snap: CycleSnapshot, cycle_cmd: Any,
                 parent: QWidget | None = None) -> None:
        super().__init__(
            "STOP / TRAIL",
            f"{snap.symbol} · {_trade_label(snap)}",
            accent=C.BLUE,
            parent=parent,
        )
        self._cmd = cycle_cmd
        self.editor = _RiskEditorWidget(snap, parent=self)
        self.editor.saved.connect(self._on_saved)
        self.editor.cancelled.connect(lambda _cid: self.reject())
        root = self.layout()
        if root is not None:
            buttons = root.itemAt(2)
            if buttons is not None and buttons.widget() is not None:
                buttons.widget().hide()  # type: ignore[union-attr]
            root.addWidget(self.editor)
        self.setStyleSheet(f"QDialog {{ background: {C.BG}; }}")

    def _on_saved(self, cycle_id: int, fields: dict[str, Any]) -> None:
        try:
            self._cmd.update_risk(cycle_id, **fields)
        except InvariantViolation as exc:
            self.editor.show_error(str(exc))
            return
        except Exception:
            log.exception("[Trades] Could not save the stop for trade %d", cycle_id)
            self.editor.show_error("Could not save — see the log for details")
            return
        self.accept()
