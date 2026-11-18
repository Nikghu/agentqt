"""
Module: MD-SCR-017.013.M33 — Accumulation / Distribution Settings Dialog
Parent SRD: SRD-SCR-017.013, SRD-SCR-017.016
"""
from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QPushButton,
    QSpinBox,
    QWidget,
)

from us_swing.gui.frameless_dialog import FramelessDialog
from us_swing.screener.base import ScreenerValidationError
from us_swing.screener.screeners.acc_dist import (
    ACCUMULATION,
    DISTRIBUTION,
    FIXED_MOVE,
    OWN_MOVE,
    SETTINGS,
    default_config,
    read_config,
)

# key → (label, suffix)
_LABELS: dict[str, tuple[str, str]] = {
    "lookback": ("Lookback", " days"),
    "volume_period": ("Volume average", " days"),
    "high_factor": ("High volume ≥", "×"),
    "low_factor": ("Low volume ≤", "×"),
    "move_factor": ("Move factor", "× normal"),
    "min_move_pct": ("Minimum move", " %"),
    "min_rally_days": ("Minimum rally days", ""),
    "min_drop_days": ("Minimum drop days", ""),
    "min_ud_ratio": ("Up/down ratio ≥ (Acc)", ""),
    "max_ud_ratio": ("Up/down ratio ≤ (Dist)", ""),
    "location_filter": ("Near range low / high", ""),
    "range_period": ("Range period", " days"),
    "zone_pct": ("Range zone", " %"),
    "close_position": ("Close position check", ""),
    "close_zone_pct": ("Close zone", " %"),
    "min_score": ("Minimum score", ""),
}

_MODES = (("Accumulation", ACCUMULATION), ("Distribution", DISTRIBUTION))
_MOVE_RULES = (("Stock's own move", OWN_MOVE), ("Fixed %", FIXED_MOVE))


class AccDistSettingsDialog(FramelessDialog):
    """Form that edits every Accumulation / Distribution screener setting."""

    def __init__(self, config: dict[str, Any] | None, parent: QWidget | None = None) -> None:
        super().__init__("Accumulation / Distribution", min_width=380, parent=parent)
        self.setObjectName("acc_dist_settings_dialog")
        try:
            cfg = read_config(config or {})
        except ScreenerValidationError:
            cfg = default_config()

        form = QFormLayout()
        form.setSpacing(6)
        self.mode_combo = QComboBox()
        for label, mode in _MODES:
            self.mode_combo.addItem(label, mode)
        self.mode_combo.setCurrentIndex(0 if cfg["mode"] == ACCUMULATION else 1)
        form.addRow("Mode", self.mode_combo)
        self.move_rule_combo = QComboBox()
        for label, rule in _MOVE_RULES:
            self.move_rule_combo.addItem(label, rule)
        self.move_rule_combo.setCurrentIndex(0 if cfg["move_rule"] == OWN_MOVE else 1)
        self.move_rule_combo.setToolTip(
            "Stock's own move: a day counts when it moves at least the factor times the "
            "stock's normal daily move over the volume average days.\n"
            "Fixed %: a day counts when it moves at least the minimum move %."
        )
        form.addRow("Move rule", self.move_rule_combo)

        self.inputs: dict[str, QCheckBox | QSpinBox | QDoubleSpinBox] = {}
        for key, (default, lo, hi) in SETTINGS.items():
            label, suffix = _LABELS[key]
            widget = self._make_input(default, lo, hi, suffix, cfg[key])
            self.inputs[key] = widget
            form.addRow(label, widget)
        self.content_layout().addLayout(form)
        self.content_layout().addLayout(self._build_footer())

        # move_rule_combo → currentIndexChanged → dialog → _sync_move_inputs
        self.move_rule_combo.currentIndexChanged.connect(self._sync_move_inputs)
        self._sync_move_inputs()

    def _sync_move_inputs(self) -> None:
        """Enable only the move input that the chosen move rule uses."""
        own = self.move_rule_combo.currentData() == OWN_MOVE
        self.inputs["move_factor"].setEnabled(own)
        self.inputs["min_move_pct"].setEnabled(not own)

    @staticmethod
    def _make_input(
        default: Any, lo: float, hi: float, suffix: str, value: Any
    ) -> QCheckBox | QSpinBox | QDoubleSpinBox:
        if isinstance(default, bool):
            box = QCheckBox()
            box.setChecked(bool(value))
            return box
        spin: QSpinBox | QDoubleSpinBox
        if isinstance(default, int):
            spin = QSpinBox()
            spin.setRange(int(lo), int(hi))
            spin.setValue(int(value))
        else:
            spin = QDoubleSpinBox()
            spin.setDecimals(2)
            spin.setSingleStep(0.05 if hi <= 5 else 1.0)
            spin.setRange(lo, hi)
            spin.setValue(float(value))
        spin.setSuffix(suffix)
        spin.setFixedWidth(110)
        return spin

    def _build_footer(self) -> QHBoxLayout:
        row = QHBoxLayout()
        reset_btn = QPushButton("Reset")
        cancel_btn = QPushButton("Cancel")
        ok_btn = QPushButton("✔  OK")
        ok_btn.setObjectName("btn_green")
        ok_btn.setDefault(True)
        for btn in (reset_btn, cancel_btn, ok_btn):
            btn.setFixedWidth(80)
            btn.setStyleSheet("QPushButton { outline: none; }")
        row.addWidget(reset_btn)
        row.addStretch()
        row.addWidget(cancel_btn)
        row.addWidget(ok_btn)

        # reset_btn → clicked → dialog → _reset (all inputs back to defaults)
        reset_btn.clicked.connect(self._reset)
        # cancel_btn → clicked → dialog → reject
        cancel_btn.clicked.connect(self.reject)
        # ok_btn → clicked → dialog → accept
        ok_btn.clicked.connect(self.accept)
        return row

    def _reset(self) -> None:
        cfg = default_config()
        self.mode_combo.setCurrentIndex(0)
        self.move_rule_combo.setCurrentIndex(0)
        for key, widget in self.inputs.items():
            if isinstance(widget, QCheckBox):
                widget.setChecked(bool(cfg[key]))
            else:
                widget.setValue(cfg[key])

    def get_config(self) -> dict[str, Any]:
        """Return the screener config dict for the current inputs."""
        cfg: dict[str, Any] = {
            "mode": self.mode_combo.currentData(),
            "move_rule": self.move_rule_combo.currentData(),
        }
        for key, widget in self.inputs.items():
            cfg[key] = widget.isChecked() if isinstance(widget, QCheckBox) else widget.value()
        return read_config(cfg)
