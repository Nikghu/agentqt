"""Tests for the Charts source list (FO-GUI-026, MD-GUI-026.002.M02)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PyQt6.QtCore import QObject, QSettings, pyqtSignal

from us_swing.gui.chart_source_list import SourceList, source_rows


class _Svc(QObject):
    watchlist_updated = pyqtSignal()
    positions_updated = pyqtSignal()
    screener_results_updated = pyqtSignal(list)

    def __init__(self, watch=(), screener=(), positions=()) -> None:
        super().__init__()
        self.watch, self.screener, self.positions = list(watch), list(screener), list(positions)

    def get_watchlist_items(self):
        return self.watch

    def get_latest_screener_results(self):
        return self.screener

    def get_positions(self):
        return self.positions


def _watch(symbol: str, ltp: float = 10.0, pct: float = 1.0):
    return SimpleNamespace(symbol=symbol, ltp=ltp, change_pct=pct)


def _entry(symbol: str, score: float, name: str = "Momentum", run_type: str = "manual"):
    return SimpleNamespace(symbol=symbol, score=score, screener_name=name, run_type=run_type)


def _position(symbol: str, qty: int, direction: str = "LONG"):
    return SimpleNamespace(symbol=symbol, quantity=qty, direction=direction,
                           current_price=50.0, pnl_pct=-1.5)


@pytest.fixture()
def settings(tmp_path) -> QSettings:
    return QSettings(str(tmp_path / "charts.ini"), QSettings.Format.IniFormat)


def test_rows_per_tab():
    """UT-GUI-026.002.M02.T01: Rows per tab."""
    svc = _Svc(watch=[_watch("NVDA"), _watch("AMD")],
               screener=[_entry("AVGO", 0.4), _entry("NVDA", 0.9),
                         _entry("DELL", 0.0, "—", "pick")],
               positions=[_position("KVUE", 20, "SHORT"), _position("OLD", 0)])
    assert [r.symbol for r in source_rows(svc, "watchlist")] == ["NVDA", "AMD"]
    screener = source_rows(svc, "screener")
    assert [r.symbol for r in screener] == ["NVDA", "AVGO", "DELL"]
    assert screener[0].sub == "Momentum · 0.90" and screener[2].sub == "Manual pick"
    trades = source_rows(svc, "trades")
    assert [(r.symbol, r.sub) for r in trades] == [("KVUE", "Short 20 sh")]


def test_filter_and_tab_remembered(qtbot, settings):
    """UT-GUI-026.002.M02.T02: Filter and tab remembered."""
    svc = _Svc(watch=[_watch("NVDA"), _watch("AMD")], positions=[_position("AAPL", 5)])
    widget = SourceList(svc, settings)  # type: ignore[arg-type]
    qtbot.addWidget(widget)
    widget.filter_box.setText("nv")
    assert widget.visible_symbols() == ["NVDA"]
    widget.tabs.buttons[2].click()
    again = SourceList(svc, settings)  # type: ignore[arg-type]
    qtbot.addWidget(again)
    assert again.tab == "trades" and again.visible_symbols() == ["AAPL"]


def test_empty_tab_shows_text(qtbot, settings):
    """UT-GUI-026.002.M02.T03: Empty tab shows empty text."""
    widget = SourceList(_Svc(), settings)  # type: ignore[arg-type]
    qtbot.addWidget(widget)
    widget.tabs.buttons[2].click()
    assert widget.list.isHidden()
    assert not widget.empty_lbl.isHidden()
    assert widget.empty_lbl.text() == "No open trades"


def test_click_emits_and_refresh_on_signal(qtbot, settings):
    """UT-GUI-026.002.M02.T04: Row click emits the symbol; watchlist signal reloads rows."""
    svc = _Svc(watch=[_watch("NVDA")])
    widget = SourceList(svc, settings)  # type: ignore[arg-type]
    qtbot.addWidget(widget)
    with qtbot.waitSignal(widget.symbol_selected) as blocker:
        widget._on_item(widget.list.item(0))
    assert blocker.args == ["NVDA"]
    svc.watch.append(_watch("AMD"))
    svc.watchlist_updated.emit()
    assert widget.visible_symbols() == ["NVDA", "AMD"]
