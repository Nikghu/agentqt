"""
Module: MD-GUI-031.050.M05 — Backtest dock panels
Parent SRD: SRD-GUI-031.050

A section made of titled panels in rows; a right icon strip and each panel's ✕
turn panels on or off, remembered in QSettings.
"""
from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from us_swing.gui.cards import GAP, card, gutter
from us_swing.gui.icons import icon_button, set_icon


@dataclass(frozen=True)
class PanelSpec:
    """One panel: settings key, title, strip icon and body widget."""

    key: str
    title: str
    icon: str
    body: QWidget


class Panel(QWidget):
    """A titled panel with a ✕ that hides it."""

    def __init__(self, spec: PanelSpec, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.key = spec.key
        box = QVBoxLayout(self)
        box.setContentsMargins(12, 8, 12, 10)
        box.setSpacing(6)
        top = QHBoxLayout()
        self.title = QLabel(spec.title.upper())
        self.title.setObjectName("view_head")
        self.close_btn = icon_button("x", "neutral", f"Hide {spec.title}")
        self.close_btn.setObjectName("strip_btn")
        self.close_btn.setFixedWidth(24)
        top.addWidget(self.title, 1)
        top.addWidget(self.close_btn)
        box.addLayout(top)
        box.addWidget(spec.body, 1)


class DockSection(QWidget):
    """Rows of panels in splitters, with a right icon strip of on/off buttons."""

    def __init__(self, name: str, rows: list[list[PanelSpec]], left: QWidget | None = None,
                 settings: QSettings | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._name = name
        self._settings = settings or QSettings("USSwing", "BacktestDock")
        self.panels: dict[str, QFrame] = {}
        self.buttons: dict[str, QPushButton] = {}
        self._rows: list[QSplitter] = []

        gutter(self)
        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(GAP)
        if left is not None:
            main.addWidget(card(left))
        column = gutter(QSplitter(Qt.Orientation.Vertical))
        assert isinstance(column, QSplitter)
        column.setHandleWidth(GAP)
        strip = QFrame()
        strip.setObjectName("icon_strip")
        strip.setFixedWidth(46)
        icons = QVBoxLayout(strip)
        icons.setContentsMargins(4, 8, 4, 8)
        icons.setSpacing(4)
        for specs in rows:
            row = gutter(QSplitter(Qt.Orientation.Horizontal))
            assert isinstance(row, QSplitter)
            row.setHandleWidth(GAP)
            for spec in specs:
                panel = Panel(spec)
                frame = card(panel)
                row.addWidget(frame)
                self.panels[spec.key] = frame
                icons.addWidget(self._button(spec))
                panel.close_btn.clicked.connect(
                    lambda _c=False, k=spec.key: self.set_shown(k, False))
            column.addWidget(row)
            self._rows.append(row)
        icons.addStretch(1)
        column.setStretchFactor(0, 2)
        main.addWidget(column, 1)
        main.addWidget(strip)
        for key in self.panels:
            self.set_shown(key, self._settings.value(self._key(key), True, type=bool))

    def _key(self, panel: str) -> str:
        return f"{self._name}/{panel}"

    def _button(self, spec: PanelSpec) -> QPushButton:
        btn = QPushButton()
        btn.setObjectName("strip_btn")
        btn.setCheckable(True)
        btn.setFixedWidth(36)
        set_icon(btn, spec.icon, "neutral", 20)
        btn.setToolTip(spec.title)
        btn.setAccessibleName(spec.title)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.toggled.connect(lambda on, k=spec.key: self.set_shown(k, on))
        self.buttons[spec.key] = btn
        return btn

    def set_shown(self, key: str, shown: bool) -> None:
        """Show or hide one panel; a row with no panel left is hidden too."""
        self.panels[key].setVisible(shown)
        btn = self.buttons[key]
        btn.blockSignals(True)
        btn.setChecked(shown)
        btn.blockSignals(False)
        self._settings.setValue(self._key(key), shown)
        for row in self._rows:
            row.setVisible(any(not row.widget(i).isHidden()  # type: ignore[union-attr]
                               for i in range(row.count())))

    def is_shown(self, key: str) -> bool:
        """True when the panel is turned on."""
        return not self.panels[key].isHidden()
