"""
Module: MD-GUI-031.075.M11 — Backtest header parts
Parent SRD: SRD-GUI-031.075

Step stepper (1 Stocks → 4 Report) and the labelled setup field grid.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

STEPS = ("Stocks", "Signals", "Portfolio", "Report")
FIELDS = (("run", "Run"), ("stocks", "Stocks"), ("screener", "Screener"),
          ("strategies", "Strategy"), ("account", "Account"))
_NO_STRATEGY = "None picked"


def repolish(widget: QWidget) -> None:
    """Re-apply QSS after a dynamic ``state`` property change."""
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)


def _set_state(widget: QWidget, state: str) -> None:
    widget.setProperty("state", state)
    repolish(widget)


class StepStrip(QWidget):
    """Numbered circles joined by lines; done steps turn green with a tick."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.nums: list[QLabel] = []
        self.names: list[QLabel] = []
        self._bars: list[QFrame] = []
        for i, name in enumerate(STEPS):
            if i:
                bar = QFrame()
                bar.setObjectName("bt_step_bar")
                bar.setFixedSize(40, 2)
                self._bars.append(bar)
                row.addWidget(bar)
            num = QLabel(str(i + 1))
            num.setObjectName("bt_step_num")
            num.setFixedSize(22, 22)
            num.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label = QLabel(name)
            label.setObjectName("bt_step_name")
            self.nums.append(num)
            self.names.append(label)
            row.addWidget(num)
            row.addWidget(label)

    def set_step(self, index: int, qss_state: str, note: str) -> None:
        """Show step ``index`` in ``qss_state`` ("", "downloading", "complete") with a note."""
        done = qss_state == "complete"
        self.nums[index].setText("✓" if done else str(index + 1))
        self.names[index].setText(f"{STEPS[index]} · {note}" if note else STEPS[index])
        _set_state(self.nums[index], qss_state)
        _set_state(self.names[index], qss_state)
        if index:
            _set_state(self._bars[index - 1], qss_state)


class PlanFields(QFrame):
    """One labelled cell per setup section; a missing strategy shows as a warning."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("bt_fields")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        self.values: dict[str, QLabel] = {}
        for i, (key, title) in enumerate(FIELDS):
            if i:
                line = QFrame()
                line.setObjectName("bt_field_div")
                line.setFixedWidth(1)
                row.addWidget(line)
            cell = QWidget()
            cell.setObjectName("bt_field")
            body = QVBoxLayout(cell)
            body.setContentsMargins(14, 8, 14, 8)
            body.setSpacing(2)
            head = QLabel(title.upper())
            head.setObjectName("bt_field_label")
            value = QLabel("")
            value.setObjectName("bt_field_value")
            value.setWordWrap(True)
            body.addWidget(head)
            body.addWidget(value)
            self.values[key] = value
            row.addWidget(cell, 1)

    def set_summaries(self, summaries: dict[str, str]) -> None:
        """Fill each cell from ``BacktestBuilder.summaries()``."""
        for key, value in summaries.items():
            label = self.values[key]
            label.setText(value)
            _set_state(label, "warn" if value == _NO_STRATEGY else "")
