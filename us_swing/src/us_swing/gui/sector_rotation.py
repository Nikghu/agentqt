"""
Module: MD-GUI-025.022.M06 — Sector Rotation View
Parent SRD: SRD-GUI-025.022

Ranks the 11 sector ETFs by their move minus the equal-weight S&P 500 (RSP) move over
a range of trading days, and shows them as bars in the Market Watch tile.
"""
from __future__ import annotations

import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from us_swing.core.stock_context import (  # noqa: F401  (re-exported for gui callers)
    RANGE_DAYS,
    SECTOR_BENCHMARK,
    SECTOR_ETFS,
    SECTOR_SYMBOLS,
    SectorMove,
    sector_moves,
)
from us_swing.gui.dashboard_tiles import PnlBar
from us_swing.gui.theme import C

_MONO = '"IBM Plex Mono", Consolas, monospace'


class SectorRotationView(QWidget):
    """Ranked sector bars against RSP, with the last close date (SRD-GUI-025.022)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.note_lbl = QLabel("")
        self.note_lbl.setStyleSheet(f"color:{C.MUTED}; font-size:8pt;")
        self.empty_lbl = QLabel("No sector candles yet. Run a candle update to load them.")
        self.empty_lbl.setStyleSheet(f"color:{C.MUTED};")
        self.empty_lbl.setWordWrap(True)

        rows_box = QWidget()
        self._rows = QVBoxLayout(rows_box)
        self._rows.setContentsMargins(0, 0, 0, 0)
        self._rows.setSpacing(12)
        self._rows.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            "QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        self._scroll.setWidget(rows_box)

        box = QVBoxLayout(self)
        box.setContentsMargins(14, 12, 14, 12)
        box.setSpacing(10)
        box.addWidget(self.note_lbl)
        box.addWidget(self._scroll, 1)
        box.addWidget(self.empty_lbl)
        box.addStretch()
        self.bars: list[PnlBar] = []

    def show_moves(self, moves: list[SectorMove], as_of: str) -> None:
        """Replace the rows; bar length is relative to the largest move."""
        while self._rows.count():
            item = self._rows.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        self.bars = []
        peak = max((abs(m.relative_pct) for m in moves), default=0.0) or 1.0
        for move in moves:
            self._rows.addWidget(self._row(move, peak))
        self.empty_lbl.setVisible(not moves)
        self._scroll.setVisible(bool(moves))
        self.note_lbl.setVisible(bool(moves))
        if as_of:
            day = datetime.date.fromisoformat(as_of).strftime("%d-%m-%Y")
            self.note_lbl.setText(f"Against equal-weight S&P 500 (RSP) · last close {day}")

    def _row(self, move: SectorMove, peak: float) -> QWidget:
        row = QWidget()
        box = QVBoxLayout(row)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(5)
        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(QLabel(move.name))
        etf = QLabel(move.symbol)
        etf.setStyleSheet(f"color:{C.MUTED}; font-size:8pt;")
        top.addWidget(etf)
        top.addStretch()
        value = QLabel(f"{move.relative_pct:+.2f}%")
        colour = C.GREEN if move.relative_pct > 0 else C.RED if move.relative_pct < 0 else C.MUTED
        value.setStyleSheet(f"color:{colour}; font-family:{_MONO};")
        top.addWidget(value)
        bar = PnlBar()
        bar.set_fraction(move.relative_pct / peak)
        self.bars.append(bar)
        box.addLayout(top)
        box.addWidget(bar)
        return row
