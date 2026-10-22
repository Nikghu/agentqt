"""
Module: MD-GUI-015.011.M05 — Indicator Parameters Panel
Parent SRD: SRD-GUI-015.011
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from us_swing.core.indicator_rules import ParamSpec
from us_swing.gui.theme import C


class ParamsOwner(Protocol):
    """A catalogue entry with editable parameters (indicator or price action pattern)."""

    @property
    def name(self) -> str: ...
    @property
    def params(self) -> tuple[ParamSpec, ...]: ...

_PANEL_QSS = f"""
    QDialog#indicator_params_dialog {{
        background: {C.OVERLAY};
        border: 1px solid {C.BLUE};
        border-radius: 6px;
    }}
    QDialog#indicator_params_dialog QLabel {{
        background: transparent;
        color: {C.TEXT};
    }}
    QSpinBox, QDoubleSpinBox {{
        background: {C.INPUT};
        color: {C.TEXT};
        border: 1px solid {C.OVERLAY2};
        border-radius: 4px;
        padding: 0 4px;
        outline: none;
    }}
    QSpinBox:focus, QDoubleSpinBox:focus {{
        border: 1px solid {C.BLUE};
        outline: none;
    }}
    QPushButton#param_reset_btn {{
        background: transparent;
        border: none;
        color: {C.BLUE};
        padding: 0;
        outline: none;
    }}
    QPushButton#param_reset_btn:focus {{ outline: none; }}
"""


class IndicatorParamsDialog(QDialog):
    """Small panel without a title bar that edits one indicator's parameters.

    It opens as a popup under the Settings cell: Enter saves, Esc or a click
    outside the panel discards the changes.
    """

    def __init__(
        self,
        spec: ParamsOwner,
        params: Mapping[str, float],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("indicator_params_dialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_PANEL_QSS)
        self._spec = spec
        self._spins: dict[str, QSpinBox | QDoubleSpinBox] = {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        title = QLabel(f"{spec.name} settings")
        title.setStyleSheet(f"color: {C.TEXT}; font-weight: 600;")
        lay.addWidget(title)

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(6)
        for param in spec.params:
            spin = self._make_spin(param)
            self._set_spin(spin, params.get(param.key, param.default))
            self._spins[param.key] = spin
            form.addRow(param.label, spin)
        lay.addLayout(form)

        defaults = " · ".join(f"{p.default:g}" for p in spec.params)
        reset_btn = QPushButton(f"Reset to {defaults}")
        reset_btn.setObjectName("param_reset_btn")
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        hint = QLabel("Enter = save")
        hint.setStyleSheet(f"color: {C.SUBTEXT}; font-size: 11px;")
        foot = QHBoxLayout()
        foot.addWidget(reset_btn)
        foot.addStretch()
        foot.addWidget(hint)
        lay.addLayout(foot)

        # reset_btn → clicked → panel → _reset
        reset_btn.clicked.connect(self._reset)

    def place_under(self, anchor: QPoint) -> None:
        """Move the panel so its top-right corner sits at ``anchor`` (global coords)."""
        self.adjustSize()
        self.move(anchor.x() - self.width() + 1, anchor.y() + 2)

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        if event is not None and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.accept()
            return
        super().keyPressEvent(event)

    def _make_spin(self, param: ParamSpec) -> QSpinBox | QDoubleSpinBox:
        spin: QSpinBox | QDoubleSpinBox
        if param.kind == "int":
            spin = QSpinBox()
            spin.setRange(int(param.min), int(param.max))
            spin.setSingleStep(int(param.step))
        else:
            spin = QDoubleSpinBox()
            spin.setRange(param.min, param.max)
            spin.setSingleStep(param.step)
            spin.setDecimals(2)
        spin.setObjectName(f"param_{param.key}")
        spin.setFixedWidth(80)
        spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        return spin

    @staticmethod
    def _set_spin(spin: QSpinBox | QDoubleSpinBox, value: float) -> None:
        if isinstance(spin, QSpinBox):
            spin.setValue(int(value))
        else:
            spin.setValue(float(value))

    def _reset(self) -> None:
        for param in self._spec.params:
            self._set_spin(self._spins[param.key], param.default)

    def get_params(self) -> dict[str, float]:
        """Return the edited values keyed by parameter key."""
        return {key: float(spin.value()) for key, spin in self._spins.items()}
