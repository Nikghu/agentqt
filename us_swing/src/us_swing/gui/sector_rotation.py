"""
Module: MD-GUI-025.022.M06 — Sector Rotation View
Parent SRD: SRD-GUI-025.022

Ranks the 11 sector ETFs by their move minus the equal-weight S&P 500 (RSP) move over
a range of trading days, and shows them as bars in the Market Watch tile.
"""
from __future__ import annotations

import datetime
from collections.abc import Mapping
from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from us_swing.gui.dashboard_tiles import PnlBar
from us_swing.gui.theme import C

SECTOR_BENCHMARK = "RSP"
SECTOR_ETFS: tuple[tuple[str, str], ...] = (
    ("XLK", "Technology"),
    ("XLF", "Financials"),
    ("XLE", "Energy"),
    ("XLV", "Health Care"),
    ("XLY", "Consumer Discretionary"),
    ("XLP", "Consumer Staples"),
    ("XLI", "Industrials"),
    ("XLB", "Materials"),
    ("XLU", "Utilities"),
    ("XLRE", "Real Estate"),
    ("XLC", "Communication"),
)
SECTOR_SYMBOLS: tuple[str, ...] = (SECTOR_BENCHMARK, *(sym for sym, _name in SECTOR_ETFS))
RANGE_DAYS: dict[str, int] = {"1W": 5, "1M": 21, "3M": 63}

_MONO = '"IBM Plex Mono", Consolas, monospace'


@dataclass(frozen=True, slots=True)
class SectorMove:
    """One sector's move over the range, minus the RSP move, in percent."""

    symbol: str
    name: str
    relative_pct: float


def sector_moves(
    closes: Mapping[str, Mapping[str, float]], days: int
) -> tuple[list[SectorMove], str]:
    """Sector moves against RSP over the last ``days`` RSP trading days, strongest first.

    Args:
        closes: Daily closes per symbol, keyed by ISO date (``YYYY-MM-DD``).
        days: Number of trading days back from RSP's last close.

    Returns:
        The ranked moves and RSP's last close date; ``([], "")`` when RSP has too few
        closes. A sector without a close on both the start and end day is left out.
    """
    bench = closes.get(SECTOR_BENCHMARK, {})
    dates = sorted(bench)
    if len(dates) <= days:
        return [], ""
    start, end = dates[-1 - days], dates[-1]
    bench_move = bench[end] / bench[start] - 1
    moves = []
    for symbol, name in SECTOR_ETFS:
        sector = closes.get(symbol, {})
        if sector.get(start) and end in sector:
            relative = (sector[end] / sector[start] - 1 - bench_move) * 100
            moves.append(SectorMove(symbol, name, relative))
    moves.sort(key=lambda move: move.relative_pct, reverse=True)
    return moves, end


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
