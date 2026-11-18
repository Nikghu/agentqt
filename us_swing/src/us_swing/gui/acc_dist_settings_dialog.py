"""
Module: MD-SCR-017.013.M33 — Accumulation / Distribution Settings Dialog
Parent SRD: SRD-SCR-017.013, SRD-SCR-017.016, SRD-SCR-017.017, SRD-SCR-017.018
"""
from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from us_swing.gui.acc_dist_tips import LABELS, TABS, TabSpec, summary, tab_intro, tip
from us_swing.gui.frameless_dialog import FramelessDialog
from us_swing.gui.theme import C
from us_swing.screener.base import ScreenerValidationError
from us_swing.screener.screeners.acc_dist import (
    ACCUMULATION,
    DISTRIBUTION,
    FIXED_MOVE,
    OWN_MOVE,
    SETTINGS,
    default_config,
    read_config,
    strictness,
)

_SUFFIX: dict[str, str] = {
    "lookback": " days", "volume_period": " days", "high_factor": "×", "low_factor": "×",
    "move_factor": "× normal", "min_move_pct": " %", "range_period": " days",
    "zone_pct": " %", "close_zone_pct": " %",
}

_MODES = (("Accumulation", ACCUMULATION), ("Distribution", DISTRIBUTION))
_MOVE_RULES = (("Stock's own move", OWN_MOVE), ("Fixed %", FIXED_MOVE))
_TIP_WIDTH = 260


def _level_colour(level: str) -> str:
    return str({"Wide": C.GREEN, "Balanced": C.BLUE, "Strict": C.YELLOW}.get(level, C.RED))


def _tint(hex_colour: str, alpha: float) -> str:
    c = QColor(hex_colour)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha})"


def _qss() -> str:
    return (
        f"QFrame#acc_tabs {{ background: {C.BG}; border: 1px solid {C.OVERLAY2};"
        " border-radius: 8px; }"
        f"QPushButton#acc_tab {{ background: {C.INPUT}; color: {C.SUBTEXT};"
        f" border: 1px solid {C.OVERLAY2}; border-radius: 6px; padding: 0 12px; outline: none; }}"
        f"QPushButton#acc_tab:checked {{ color: {C.BLUE}; border-color: {C.BLUE};"
        f" background: {_tint(C.BLUE, 0.10)}; outline: none; }}"
        f"QFrame#acc_stage {{ border: 1px solid {C.OVERLAY2}; border-radius: 8px; }}"
        f"QFrame#acc_pair {{ background: {C.SURFACE}; border: 1px solid {C.OVERLAY};"
        " border-radius: 4px; }"
        "QFrame#acc_field { background: transparent; border: none; border-radius: 3px; }"
        f"QFrame#acc_field[on=\"true\"] {{ background: {_tint(C.BLUE, 0.14)}; }}"
        f"QLabel#acc_field_label[on=\"true\"] {{ color: {C.BLUE}; }}"
        f"QLabel#acc_field_label:disabled {{ color: {C.MUTED}; }}"
        f"QFrame#acc_field QAbstractSpinBox:disabled {{ color: {C.MUTED}; outline: none; }}"
        f"QFrame#acc_tip {{ background: {C.BG}; border: none;"
        f" border-left: 1px solid {C.OVERLAY2}; }}"
        f"QLabel#acc_intro {{ color: {C.SUBTEXT}; font-size: 9pt; }}"
        f"QLabel#acc_head {{ color: {C.BLUE}; font-size: 8pt; font-weight: 600; }}"
        f"QLabel#acc_tip_key {{ color: {C.MUTED}; font-size: 8pt; }}"
        f"QLabel#acc_tip_title {{ color: {C.BLUE}; font-size: 10.5pt; font-weight: 600; }}"
        f"QLabel#acc_tip_text {{ color: {C.TEXT}; }}"
        f"QLabel#acc_tip_example {{ color: {C.SUBTEXT}; border-left: 2px solid {C.OVERLAY2};"
        " padding-left: 8px; }"
        f"QLabel#acc_tip_value {{ color: {C.SUBTEXT}; }}"
        f"QLabel#acc_summary {{ color: {C.TEXT}; background: {_tint(C.BLUE, 0.07)};"
        f" border: 1px solid {_tint(C.BLUE, 0.35)}; border-radius: 4px; padding: 8px 10px; }}"
    )


class AccDistSettingsDialog(FramelessDialog):
    """Tabbed form for every Accumulation / Distribution setting, with a tip panel."""

    def __init__(self, config: dict[str, Any] | None, parent: QWidget | None = None) -> None:
        super().__init__("Accumulation / Distribution", min_width=820, extra_qss=_qss(),
                         parent=parent)
        self.setObjectName("acc_dist_settings_dialog")
        try:
            cfg = read_config(config or {})
        except ScreenerValidationError:
            cfg = default_config()

        self.mode_combo = QComboBox()
        for label, mode in _MODES:
            self.mode_combo.addItem(label, mode)
        self.mode_combo.setCurrentIndex(0 if cfg["mode"] == ACCUMULATION else 1)
        self.move_rule_combo = QComboBox()
        for label, rule in _MOVE_RULES:
            self.move_rule_combo.addItem(label, rule)
        self.move_rule_combo.setCurrentIndex(0 if cfg["move_rule"] == OWN_MOVE else 1)

        self.inputs: dict[str, QCheckBox | QSpinBox | QDoubleSpinBox] = {}
        for key, (default, lo, hi) in SETTINGS.items():
            self.inputs[key] = self._make_input(default, lo, hi, _SUFFIX.get(key, ""), cfg[key])

        self._fields: dict[str, QFrame] = {}
        self._tip_key = "mode"
        self._add_title_chips()
        layout = self.content_layout()
        layout.addWidget(self._build_tabs())
        layout.addWidget(self._build_stage(), 1)
        layout.addLayout(self._build_footer())
        self._connect_inputs()
        self._refresh()

    # ── Building ─────────────────────────────────────────────────────────

    def _add_title_chips(self) -> None:
        self.strict_chip = QLabel()
        self.mode_chip = QLabel()
        for chip in (self.strict_chip, self.mode_chip):
            chip.setFixedHeight(20)
            chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box = QWidget()
        box.setStyleSheet("background: transparent;")
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 10, 0)
        row.setSpacing(6)
        row.addWidget(self.strict_chip)
        row.addWidget(self.mode_chip)
        bar_layout = self._title_bar.layout()
        if isinstance(bar_layout, QHBoxLayout):
            bar_layout.insertWidget(2, box)

    def _build_tabs(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("acc_tabs")
        row = QHBoxLayout(frame)
        row.setContentsMargins(10, 10, 10, 10)
        row.setSpacing(8)
        self.tab_group = QButtonGroup(self)
        self.tab_group.setExclusive(True)
        for index, spec in enumerate(TABS):
            btn = QPushButton(f"{index + 1}   {spec.name.replace('&', '&&')}")
            btn.setObjectName("acc_tab")
            btn.setCheckable(True)
            btn.setChecked(index == 0)
            self.tab_group.addButton(btn, index)
            row.addWidget(btn, 1)
        # tab_group → idClicked → dialog → _show_tab (switch page and tip)
        self.tab_group.idClicked.connect(self._show_tab)
        return frame

    def _build_stage(self) -> QFrame:
        stage = QFrame()
        stage.setObjectName("acc_stage")
        row = QHBoxLayout(stage)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        left = QVBoxLayout()
        left.setContentsMargins(14, 12, 14, 12)
        left.setSpacing(8)
        self.intro_lbl = QLabel()
        self.intro_lbl.setObjectName("acc_intro")
        self.intro_lbl.setWordWrap(True)
        left.addWidget(self.intro_lbl)
        self.pages = QStackedWidget()
        for spec in TABS:
            self.pages.addWidget(self._build_page(spec))
        left.addWidget(self.pages, 1)
        row.addLayout(left, 1)
        row.addWidget(self._build_tip_panel())
        return stage

    def _build_page(self, spec: TabSpec) -> QWidget:
        page = QWidget()
        col = QVBoxLayout(page)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(8)
        if spec.heads:
            heads = QHBoxLayout()
            heads.setSpacing(10)
            for text in spec.heads:
                head = QLabel(text.upper())
                head.setObjectName("acc_head")
                heads.addWidget(head, 1)
            col.addLayout(heads)
        for left_key, right_key in spec.rows:
            pair = QFrame()
            pair.setObjectName("acc_pair")
            line = QHBoxLayout(pair)
            line.setContentsMargins(8, 6, 8, 6)
            line.setSpacing(10)
            line.addWidget(self._build_field(left_key), 1)
            line.addWidget(self._build_field(right_key), 1)
            col.addWidget(pair)
        if spec.summary:
            self.summary_lbl = QLabel()
            self.summary_lbl.setObjectName("acc_summary")
            self.summary_lbl.setWordWrap(True)
            self.summary_lbl.setTextFormat(Qt.TextFormat.RichText)
            col.addWidget(self.summary_lbl)
        col.addStretch()
        return page

    def _build_field(self, key: str | None) -> QWidget:
        if key is None:
            return QWidget()
        field = QFrame()
        field.setObjectName("acc_field")
        field.setProperty("on", False)
        line = QHBoxLayout(field)
        line.setContentsMargins(6, 2, 4, 2)
        line.setSpacing(8)
        label = QLabel(LABELS[key])
        label.setObjectName("acc_field_label")
        line.addWidget(label, 1)
        widget = self._widget(key)
        if not isinstance(widget, QCheckBox):
            widget.setFixedWidth(120)
        line.addWidget(widget)
        field.installEventFilter(self)
        widget.installEventFilter(self)
        self._fields[key] = field
        return field

    def _build_tip_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("acc_tip")
        panel.setFixedWidth(_TIP_WIDTH)
        col = QVBoxLayout(panel)
        col.setContentsMargins(14, 12, 14, 12)
        col.setSpacing(8)
        self.tip_key_lbl = QLabel()
        self.tip_key_lbl.setObjectName("acc_tip_key")
        self.tip_title_lbl = QLabel()
        self.tip_title_lbl.setObjectName("acc_tip_title")
        self.tip_text_lbl = QLabel()
        self.tip_text_lbl.setObjectName("acc_tip_text")
        self.tip_example_lbl = QLabel()
        self.tip_example_lbl.setObjectName("acc_tip_example")
        self.tip_example_lbl.setTextFormat(Qt.TextFormat.RichText)
        self.tip_value_lbl = QLabel()
        self.tip_value_lbl.setObjectName("acc_tip_value")
        self.tip_value_lbl.setTextFormat(Qt.TextFormat.RichText)
        for lbl in (self.tip_key_lbl, self.tip_title_lbl, self.tip_text_lbl,
                    self.tip_example_lbl, self.tip_value_lbl):
            lbl.setWordWrap(True)
            col.addWidget(lbl)
        col.addStretch()
        return panel

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

    def _connect_inputs(self) -> None:
        # mode / move rule combos → currentIndexChanged → dialog → _refresh
        self.mode_combo.currentIndexChanged.connect(self._refresh)
        self.move_rule_combo.currentIndexChanged.connect(self._refresh)
        for widget in self.inputs.values():
            if isinstance(widget, QCheckBox):
                # checkbox → toggled → dialog → _refresh (enable states, tips, rules level)
                widget.toggled.connect(self._refresh)
            else:
                # spin box → valueChanged → dialog → _refresh (tips, rules level)
                widget.valueChanged.connect(self._refresh)

    # ── Behaviour ────────────────────────────────────────────────────────

    def _widget(self, key: str) -> QWidget:
        if key == "mode":
            return self.mode_combo
        if key == "move_rule":
            return self.move_rule_combo
        return self.inputs[key]

    def eventFilter(self, obj: QObject | None, event: QEvent | None) -> bool:
        """Show the tip of the setting that gets focus or a click."""
        if event is not None and event.type() in (
            QEvent.Type.FocusIn, QEvent.Type.MouseButtonPress
        ):
            for key, field in self._fields.items():
                if obj is field or obj is self._widget(key):
                    if obj is field and self._widget(key).isEnabled():
                        self._widget(key).setFocus()
                    self.show_tip(key)
                    break
        return super().eventFilter(obj, event)

    def _show_tab(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        self.show_tip(TABS[index].rows[0][0])

    def show_tip(self, key: str) -> None:
        """Show ``key``'s tip in the side panel and mark its field."""
        self._tip_key = key
        self._refresh()

    def _refresh(self) -> None:
        cfg = self.get_config()
        own = cfg["move_rule"] == OWN_MOVE
        acc = cfg["mode"] == ACCUMULATION
        enabled = {
            "move_factor": own, "min_move_pct": not own,
            "min_ud_ratio": acc, "max_ud_ratio": not acc,
            "range_period": cfg["location_filter"], "zone_pct": cfg["location_filter"],
            "close_zone_pct": cfg["close_position"],
        }
        for key, on in enabled.items():
            self.inputs[key].setEnabled(on)
            label = self._fields[key].findChild(QLabel, "acc_field_label")
            if label is not None:
                label.setEnabled(on)
        for key, field in self._fields.items():
            label = field.findChild(QLabel, "acc_field_label")
            for widget in (field, label):
                if widget is None:
                    continue
                widget.setProperty("on", key == self._tip_key)
                style = widget.style()
                if style is not None:
                    style.unpolish(widget)
                    style.polish(widget)

        self.mode_chip.setText(self.mode_combo.currentText())
        self.mode_chip.setStyleSheet(
            f"color: {C.BLUE}; background: transparent; border: 1px solid {_tint(C.BLUE, 0.5)};"
            " border-radius: 9px; padding: 0 8px; font-size: 8pt;")
        rating = strictness(cfg)
        colour = _level_colour(rating.level)
        self.strict_chip.setText(f"Rules: {rating.level}")
        self.strict_chip.setStyleSheet(
            f"color: {colour}; background: transparent; border: 1px solid {_tint(colour, 0.5)};"
            " border-radius: 9px; padding: 0 8px; font-size: 8pt;")
        tightest = ", ".join(LABELS[k] for k in rating.tightest) or "none"
        self.strict_chip.setToolTip(
            "How strict the rules are overall, from every setting in use.\n"
            f"Strictest settings now: {tightest}.")

        self.intro_lbl.setText(tab_intro(self.pages.currentIndex(), cfg))
        info = tip(self._tip_key, cfg)
        self.tip_key_lbl.setText(LABELS[self._tip_key].upper())
        self.tip_title_lbl.setText(info.title)
        self.tip_text_lbl.setText(info.text)
        self.tip_example_lbl.setText(info.example)
        self.tip_value_lbl.setText(f"Current value: <b>{self._value_text(self._tip_key)}</b>")
        self.summary_lbl.setText(
            summary(cfg) + f"<br><br>Rules overall: <b>{rating.level}</b>"
            f" ({rating.value:.2f} on a 0 to 1 scale).")

    def _value_text(self, key: str) -> str:
        widget = self._widget(key)
        if isinstance(widget, QComboBox):
            return widget.currentText()
        if isinstance(widget, QCheckBox):
            return "On" if widget.isChecked() else "Off"
        return widget.text() if isinstance(widget, (QSpinBox, QDoubleSpinBox)) else ""

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
