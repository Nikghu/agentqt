"""
Module: MD-GUI-014.001.M03 — _RiskEditorWidget
Parent SRD: SRD-GUI-014.007

Inline editor embedded under an OPEN cycle row via setIndexWidget.
Spinbox ranges are anchored to the snapshot's current_price to locally
pre-validate per FO-EXE-012 §11; the server-side `update_risk` check
remains authoritative.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from us_swing.execution.trade_cycle import CycleSnapshot


class _RiskEditorWidget(QWidget):
    """Inline editor for `hard_stop_loss`, `target_price`, `trailing_mode`,
    `trailing_offset`. Emits a diff-only `saved(cycle_id, fields)` payload."""

    saved     = pyqtSignal(int, dict)
    cancelled = pyqtSignal(int)

    def __init__(self, snap: CycleSnapshot, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._snap = snap
        self._cycle_id = snap.cycle_id

        anchor = snap.current_price if snap.current_price is not None else snap.entry_price

        # ── Spinboxes ────────────────────────────────────────────────────
        self._hsl = QDoubleSpinBox()
        self._hsl.setRange(0.01, max(0.01, anchor))
        self._hsl.setSingleStep(0.05)
        self._hsl.setDecimals(2)
        self._hsl.setPrefix("$")
        self._hsl.setValue(snap.hard_stop_loss if snap.hard_stop_loss is not None else 0.01)

        self._target = QDoubleSpinBox()
        self._target.setRange(anchor, 1_000_000.0)
        self._target.setSingleStep(0.05)
        self._target.setDecimals(2)
        self._target.setPrefix("$")
        self._target.setValue(snap.target_price if snap.target_price is not None else anchor)

        self._trail_mode = QComboBox()
        self._trail_mode.addItems(["Off", "$", "%"])
        if snap.trailing_mode in ("$", "%"):
            self._trail_mode.setCurrentText(snap.trailing_mode)

        self._trail_offset = QDoubleSpinBox()
        self._trail_offset.setRange(0.01, 999.99)
        self._trail_offset.setSingleStep(0.05)
        self._trail_offset.setDecimals(2)
        self._trail_offset.setValue(snap.trailing_offset if snap.trailing_offset is not None else 1.0)

        # ── Buttons + error label ────────────────────────────────────────
        self._save_btn   = QPushButton("Save")
        self._cancel_btn = QPushButton("Cancel")
        self._save_btn.clicked.connect(self._on_save)
        self._cancel_btn.clicked.connect(self._on_cancel)

        self._err_lbl = QLabel("")
        self._err_lbl.setObjectName("risk_err_lbl")
        self._err_lbl.setVisible(False)

        # ── Layout ───────────────────────────────────────────────────────
        row = QHBoxLayout()
        row.addWidget(QLabel("Hard Stop"))
        row.addWidget(self._hsl)
        row.addSpacing(16)
        row.addWidget(QLabel("Target"))
        row.addWidget(self._target)
        row.addSpacing(16)
        row.addWidget(QLabel("Trail Mode"))
        row.addWidget(self._trail_mode)
        row.addSpacing(16)
        row.addWidget(QLabel("Trail Offset"))
        row.addWidget(self._trail_offset)
        row.addSpacing(16)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setObjectName("risk_sep")
        row.addWidget(sep)

        row.addSpacing(16)
        row.addWidget(self._save_btn)
        row.addWidget(self._cancel_btn)
        row.addStretch()

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(6)
        root.addLayout(row)
        root.addWidget(self._err_lbl)

        for w in (self._hsl, self._target, self._trail_offset):
            w.valueChanged.connect(self._clear_error)
        self._trail_mode.currentTextChanged.connect(self._clear_error)

    # ── Public API ──────────────────────────────────────────────────────

    def show_error(self, msg: str) -> None:
        self._err_lbl.setText(msg)
        self._err_lbl.setVisible(True)

    @property
    def cycle_id(self) -> int:
        return self._cycle_id

    # ── Internal ────────────────────────────────────────────────────────

    def _clear_error(self, *_: Any) -> None:
        if self._err_lbl.isVisible():
            self._err_lbl.setVisible(False)
            self._err_lbl.setText("")

    def _collect_changed_fields(self) -> dict[str, Any]:
        snap = self._snap
        out: dict[str, Any] = {}
        if snap.hard_stop_loss is None or abs(self._hsl.value() - snap.hard_stop_loss) > 1e-9:
            out["hard_sl"] = float(self._hsl.value())
        target_changed = (
            snap.target_price is None
            or abs(self._target.value() - snap.target_price) > 1e-9
        )
        if target_changed:
            out["target"] = float(self._target.value())
        cur_mode = self._trail_mode.currentText()
        cur_mode = "" if cur_mode == "Off" else cur_mode
        if cur_mode != (snap.trailing_mode or ""):
            out["trailing_mode"] = cur_mode
        new_offset = float(self._trail_offset.value())
        if snap.trailing_offset is None or abs(new_offset - snap.trailing_offset) > 1e-9:
            out["trailing_offset"] = new_offset
        return out

    def _on_save(self) -> None:
        fields = self._collect_changed_fields()
        if not fields:
            self.cancelled.emit(self._cycle_id)
            return
        self.saved.emit(self._cycle_id, fields)

    def _on_cancel(self) -> None:
        self.cancelled.emit(self._cycle_id)


__all__ = ["_RiskEditorWidget"]
