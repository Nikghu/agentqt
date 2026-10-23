"""
Module: MD-GUI-024.002.M02 — Execution watchlist tests
Parent SRD: SRD-GUI-024.002
"""
from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal
from pytestqt.qtbot import QtBot

from us_swing.data.models import FilteredStockEntry
from us_swing.gui.execution_watchlist import COL_SCORE, COL_SYMBOL, WatchlistPane


class _Svc(QObject):
    sp500_updated = pyqtSignal()
    screener_results_updated = pyqtSignal(list)
    candle_readiness_updated = pyqtSignal(dict)
    live_bar_data_updated = pyqtSignal(str)

    def __init__(self, entries: list[FilteredStockEntry]) -> None:
        super().__init__()
        self._entries = entries
        self.removed: list[str] = []

    def get_sp500_universe(self) -> list[Any]:
        return []

    def get_latest_screener_results(self) -> list[FilteredStockEntry]:
        return self._entries

    def get_latest_close(self, symbol: str, tf: str = "3m") -> float | None:
        return 100.0

    def remove_manual_pick(self, symbol: str) -> None:
        self.removed.append(symbol)

    def add_manual_pick(self, symbol: str) -> str | None:
        return None


def _entry(symbol: str, score: float, screener: str, run_type: str = "scheduled") -> FilteredStockEntry:
    return FilteredStockEntry(symbol, score, [], [], screener, run_type, "2026-10-22", "18:48")


def _pane(qtbot: QtBot, entries: list[FilteredStockEntry]) -> tuple[WatchlistPane, _Svc]:
    svc = _Svc(entries)
    pane = WatchlistPane(svc)  # type: ignore[arg-type]
    qtbot.addWidget(pane)
    return pane, svc


_ENTRIES = [
    _entry("NVDA", 0.88, "Price Action"),
    _entry("DELL", 0.0, "—", run_type="pick"),
    _entry("JCI", 0.79, "Price Action"),
    _entry("RVTY", 0.85, "Momentum"),
    _entry("A", 0.94, "Momentum"),
]


def test_groups_order_counts_and_score(qtbot: QtBot) -> None:
    """UT-GUI-024.002.M02.T01: Manual first, screeners A→Z, counts, higher score first."""
    pane, _ = _pane(qtbot, _ENTRIES)

    assert pane.group_names() == [("Manual", 1), ("Momentum", 2), ("Price Action", 2)]
    momentum = pane.tree.topLevelItem(1)
    assert momentum is not None
    child = momentum.child(0)
    assert child is not None
    assert child.text(COL_SYMBOL) == "A"
    assert pane.get_top_symbol() == "DELL"


def test_cross_on_pick_removes_it(qtbot: QtBot) -> None:
    """UT-GUI-024.002.M02.T02: Clicking ✕ on a pick removes it."""
    pane, svc = _pane(qtbot, _ENTRIES)
    manual = pane.tree.topLevelItem(0)
    assert manual is not None
    pick = manual.child(0)
    assert pick is not None

    pane.tree.itemClicked.emit(pick, COL_SCORE)

    assert svc.removed == ["DELL"]


def test_not_ready_symbol_tinted(qtbot: QtBot) -> None:
    """UT-GUI-024.002.M02.T03: A symbol without candles is tinted; others are not."""
    pane, _ = _pane(qtbot, _ENTRIES)

    pane.set_candle_readiness({"NVDA": False})

    tinted = {
        str(item.text(COL_SYMBOL)): item.background(COL_SYMBOL).style().value != 0
        for item in pane._symbol_items()
    }
    assert tinted["NVDA"] is True
    assert tinted["JCI"] is False


def test_empty_state(qtbot: QtBot) -> None:
    """UT-GUI-024.002.M02.T04: No entries shows the empty text."""
    pane, _ = _pane(qtbot, [])

    assert pane.tree.isHidden()
    assert not pane.empty_lbl.isHidden()
    assert pane.get_top_symbol() is None
