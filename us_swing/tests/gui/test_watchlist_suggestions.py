"""Tests for the watchlist symbol suggestions (SRD-GUI-019.004)."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QCompleter

from us_swing.gui.dashboard_panel import _WatchlistTab


class _StubService(QObject):
    sp500_updated = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.records: list[SimpleNamespace] = []
        self.added: list[str] = []

    def get_sp500_universe(self) -> list[SimpleNamespace]:
        return self.records

    def add_to_watchlist(self, symbol: str) -> None:
        self.added.append(symbol)

    def __getattr__(self, name: str) -> Any:
        return MagicMock()


def _rec(symbol: str, name: str) -> SimpleNamespace:
    return SimpleNamespace(symbol=symbol, name=name)


@pytest.fixture()
def tab(qtbot: Any) -> tuple[_WatchlistTab, _StubService]:
    svc = _StubService()
    widget = _WatchlistTab(svc)  # type: ignore[arg-type]
    qtbot.addWidget(widget)
    return widget, svc


def test_suggestions_fill_when_universe_loads(tab: Any) -> None:
    """UT-GUI-019.004.M02.T01: suggestions pop up and fill once the S&P 500 list loads."""
    widget, svc = tab
    svc.records = [_rec("MSFT", "Microsoft"), _rec("AAPL", "Apple Inc.")]

    svc.sp500_updated.emit()

    completer = widget._sym_input.completer()
    assert completer.completionMode() == QCompleter.CompletionMode.PopupCompletion
    completer.setCompletionPrefix("a")
    assert completer.currentCompletion() == "AAPL - Apple Inc."
    assert completer.model().rowCount() == 2


def test_picked_suggestion_adds_symbol_only(tab: Any) -> None:
    """UT-GUI-019.004.M02.T02: a picked "AAPL - Apple Inc." adds just AAPL."""
    widget, svc = tab
    svc.records = [_rec("AAPL", "Apple Inc.")]
    svc.sp500_updated.emit()

    widget._sym_input.setText("AAPL - Apple Inc.")
    widget._on_add()

    assert svc.added == ["AAPL"]


def test_unknown_symbol_shows_themed_notice(tab: Any, monkeypatch: Any) -> None:
    """UT-GUI-019.004.M02.T03: a non-S&P 500 symbol shows the app's OK-only notice, adds nothing."""
    from us_swing.gui import active_cycles_panel

    shown: list[dict[str, Any]] = []

    class _Dialog:
        def __init__(self, title: str, text: str, **kw: Any) -> None:
            shown.append({"title": title, "text": text, **kw})

        def exec(self) -> int:
            return 1

    monkeypatch.setattr(active_cycles_panel, "_ConfirmDialog", _Dialog)
    widget, svc = tab
    svc.records = [_rec("AAPL", "Apple Inc.")]
    svc.sp500_updated.emit()

    widget._sym_input.setText("AA")
    widget._on_add()

    assert svc.added == []
    assert shown[0]["title"] == "NOT IN S&P 500"
    assert shown[0]["text"].startswith("AA is not an S&P 500 stock")
    assert shown[0]["show_cancel"] is False
