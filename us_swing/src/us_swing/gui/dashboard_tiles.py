"""
Module: MD-GUI-025.003.M01 — Dashboard tiles, KPI strip and strategy P&L bars
Parent SRD: SRD-GUI-025.003

Building blocks of the tiled Dashboard (canvas Option E): a titled tile with its own
tool buttons and a Maximise button, the 2 × 2 tile grid, the one-line KPI strip and
the "P&L by Strategy" bar list.
"""
from __future__ import annotations

from PyQt6.QtCore import QRectF, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPaintEvent
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from us_swing.gui.cards import GAP, card, gutter
from us_swing.gui.icons import icon_button, set_icon
from us_swing.gui.strategy_pnl_chart import money
from us_swing.gui.theme import C

TILES = ("positions", "watch", "history", "strategy")
ROW_H = {"compact": 24, "comfort": 32}
_CELLS = {"positions": (0, 0), "watch": (0, 1), "history": (1, 0), "strategy": (1, 1)}
_MONO = '"IBM Plex Mono", Consolas, monospace'


def _rule() -> QFrame:
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background:{C.OVERLAY}; border:none;")
    return line


class Tile(QWidget):
    """Tile with a header (title, count, tools, Maximise) over a body (SRD-GUI-025.003)."""

    maximise_clicked = pyqtSignal()

    def __init__(self, title: str, body: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet(f"color:{C.TEXT}; font-weight:bold; font-size:9.5pt;")
        self.count_lbl = QLabel("")
        self.count_lbl.setStyleSheet(f"color:{C.MUTED}; font-size:8pt;")
        self._tools = QHBoxLayout()
        self._tools.setSpacing(4)
        self.max_btn = icon_button("maximize-2", "neutral", "Maximise")
        self.max_btn.setFixedWidth(C.BTN_H)
        self.max_btn.clicked.connect(self.maximise_clicked)

        head = QHBoxLayout()
        head.setContentsMargins(10, 5, 6, 5)
        head.setSpacing(8)
        head.addWidget(self.title_lbl)
        head.addWidget(self.count_lbl)
        head.addStretch()
        head.addLayout(self._tools)
        head.addWidget(self.max_btn)

        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(0)
        box.addLayout(head)
        box.addWidget(_rule())
        box.addWidget(body, 1)

    def add_tool(self, widget: QWidget) -> None:
        self._tools.addWidget(widget)

    def set_count(self, text: str) -> None:
        self.count_lbl.setText(text)

    def set_maximised(self, on: bool) -> None:
        tip = "Restore" if on else "Maximise"
        set_icon(self.max_btn, "minimize-2" if on else "maximize-2", "neutral")
        self.max_btn.setToolTip(tip)
        self.max_btn.setAccessibleName(tip)


class TileGrid(QWidget):
    """2 × 2 grid of tile cards; one tile can be maximised over the others (SRD-GUI-025.004)."""

    changed = pyqtSignal(str)   # maximised tile name, "" when restored

    def __init__(self, tiles: dict[str, Tile], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        gutter(self)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(GAP)
        self._grid.setColumnStretch(0, 19)
        self._grid.setColumnStretch(1, 10)
        self._grid.setRowStretch(0, 23)
        self._grid.setRowStretch(1, 20)
        self._tiles = tiles
        self._cards = {name: card(tiles[name]) for name in TILES}
        for name in TILES:
            tiles[name].maximise_clicked.connect(lambda n=name: self.toggle(n))
        self._max = ""
        self._place()

    @property
    def maximised(self) -> str:
        return self._max

    def is_shown(self, name: str) -> bool:
        return not self._cards[name].isHidden()

    def toggle(self, name: str) -> None:
        self.set_maximised("" if self._max == name else name)

    def set_maximised(self, name: str) -> None:
        self._max = name if name in TILES else ""
        self._place()
        self.changed.emit(self._max)

    def _place(self) -> None:
        for frame in self._cards.values():
            self._grid.removeWidget(frame)
        for name, frame in self._cards.items():
            shown = not self._max or name == self._max
            frame.setVisible(shown)
            self._tiles[name].set_maximised(name == self._max)
            if not shown:
                continue
            if self._max:
                self._grid.addWidget(frame, 0, 0, 2, 2)
            else:
                self._grid.addWidget(frame, *_CELLS[name])


class KpiStrip(QWidget):
    """One-line account figures with a slot for switches on the right (SRD-GUI-025.001)."""

    KEYS = (("pnl", "P&L Today"), ("unreal", "Unrealised"), ("equity", "Equity"),
            ("cash", "Cash"), ("cap", "Capital Used"), ("pos", "Positions"))

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(6, 6, 8, 6)
        row.setSpacing(0)
        self._vals: dict[str, QLabel] = {}
        self._subs: dict[str, QLabel] = {}
        for index, (key, label) in enumerate(self.KEYS):
            if index:
                bar = QFrame()
                bar.setFixedWidth(1)
                bar.setStyleSheet(f"background:{C.OVERLAY}; border:none;")
                row.addWidget(bar)
            name = QLabel(label.upper())
            name.setStyleSheet(
                f"color:{C.MUTED}; font-size:7.5pt; font-weight:bold; letter-spacing:1px;")
            self._vals[key] = QLabel("—")
            self._subs[key] = QLabel("")
            self._subs[key].setStyleSheet(f"color:{C.MUTED}; font-size:8pt;")
            cell = QHBoxLayout()
            cell.setContentsMargins(12, 0, 12, 0)
            cell.setSpacing(8)
            cell.addWidget(name)
            cell.addWidget(self._vals[key])
            cell.addWidget(self._subs[key])
            row.addLayout(cell)
            self.set_value(key, "—")
        row.addStretch()
        self.tail = QHBoxLayout()
        self.tail.setSpacing(8)
        row.addLayout(self.tail)

    def set_value(self, key: str, text: str, colour: str = "", sub: str = "") -> None:
        value = self._vals[key]
        value.setText(text)
        value.setStyleSheet(f"color:{colour or C.TEXT}; font-family:{_MONO}; font-size:12pt;")
        self._subs[key].setText(sub)
        self._subs[key].setVisible(bool(sub))

    def value(self, key: str) -> str:
        return self._vals[key].text()


class PnlBar(QWidget):
    """Bar from a centre line: green to the right for a gain, red to the left for a loss."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(8)
        self.fraction = 0.0

    def set_fraction(self, fraction: float) -> None:
        self.fraction = max(-1.0, min(1.0, fraction))
        self.update()

    def paintEvent(self, _event: QPaintEvent | None) -> None:  # noqa: N802
        painter = QPainter(self)
        mid = self.width() / 2
        painter.fillRect(QRectF(mid, 0, 1, self.height()), QColor(C.OVERLAY2))
        length = abs(self.fraction) * (mid - 1)
        if length <= 0:
            return
        left = mid + 1 if self.fraction > 0 else mid - length
        colour = C.GREEN if self.fraction > 0 else C.RED
        painter.fillRect(QRectF(left, 0, length, self.height()), QColor(colour))


class StrategyPnlList(QWidget):
    """Today's P&L per strategy as bars, with a total row (SRD-GUI-025.005)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows = QVBoxLayout()
        self._rows.setSpacing(12)
        self.empty_lbl = QLabel("No strategies")
        self.empty_lbl.setStyleSheet(f"color:{C.MUTED};")
        self.total_lbl = QLabel(money(0.0))
        total = QHBoxLayout()
        total_name = QLabel("Total")
        total_name.setStyleSheet(f"color:{C.MUTED};")
        total.addWidget(total_name)
        total.addStretch()
        total.addWidget(self.total_lbl)

        box = QVBoxLayout(self)
        box.setContentsMargins(14, 12, 14, 12)
        box.setSpacing(10)
        box.addLayout(self._rows)
        box.addWidget(self.empty_lbl)
        box.addStretch()
        box.addWidget(_rule())
        box.addLayout(total)
        self.bars: list[PnlBar] = []

    def set_rows(self, rows: list[tuple[str, str, float]]) -> None:
        """Show ``(name, note, pnl)`` rows; bar length is relative to the largest P&L."""
        while self._rows.count():
            item = self._rows.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        self.bars = []
        peak = max((abs(pnl) for _n, _t, pnl in rows), default=0.0) or 1.0
        for name, note, pnl in rows:
            self._rows.addWidget(self._row(name, note, pnl, peak))
        self.empty_lbl.setVisible(not rows)
        total = sum(pnl for _n, _t, pnl in rows)
        self.total_lbl.setText(money(total))
        self.total_lbl.setStyleSheet(f"color:{_pnl_colour(total)}; font-family:{_MONO};")

    def _row(self, name: str, note: str, pnl: float, peak: float) -> QWidget:
        row = QWidget()
        box = QVBoxLayout(row)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(5)
        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(QLabel(name))
        note_lbl = QLabel(note)
        note_lbl.setStyleSheet(f"color:{C.MUTED}; font-size:8pt;")
        top.addWidget(note_lbl)
        top.addStretch()
        value = QLabel(money(pnl))
        value.setStyleSheet(f"color:{_pnl_colour(pnl)}; font-family:{_MONO};")
        top.addWidget(value)
        bar = PnlBar()
        bar.set_fraction(pnl / peak)
        self.bars.append(bar)
        box.addLayout(top)
        box.addWidget(bar)
        return row


def _pnl_colour(value: float) -> str:
    return str(C.GREEN if value > 0 else C.RED if value < 0 else C.MUTED)
