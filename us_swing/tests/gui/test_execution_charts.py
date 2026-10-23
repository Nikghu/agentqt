"""
Module: MD-GUI-024.008.M06 — Execution chart pane tests
Parent SRD: SRD-GUI-024.008
"""
from __future__ import annotations

import sys
import types
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import QObject, QSettings, pyqtSignal
from PyQt6.QtWidgets import QWidget
from pytestqt.qtbot import QtBot

# QWebEngineWidgets DLL is unavailable in the test environment — stub it.
_web_stub = types.ModuleType("PyQt6.QtWebEngineWidgets")
_web_stub.QWebEngineView = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("PyQt6.QtWebEngineWidgets", _web_stub)

import us_swing.data  # noqa: E402,F401  — load data before db (db ↔ data import cycle)
import us_swing.gui.execution_panel as ep  # noqa: E402


class _FakeWeb(QWidget):
    def setHtml(self, *_: Any) -> None:  # noqa: N802
        pass

    def page(self) -> None:
        return None


class _Svc(QObject):
    live_bar_data_updated = pyqtSignal(str)


@pytest.fixture
def settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "exec.ini"), QSettings.Format.IniFormat)


def _pane(qtbot: QtBot, settings: QSettings, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(ep, "QWebEngineView", _FakeWeb)
    pane = ep._IntradayChartPane(_Svc(), settings=settings)  # type: ignore[arg-type]
    qtbot.addWidget(pane)
    return pane


def test_hide_charts_remembered(
    qtbot: QtBot, settings: QSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """UT-GUI-024.008.M06.T01: Hide charts is saved and a new pane starts hidden."""
    pane = _pane(qtbot, settings, monkeypatch)
    assert not pane.charts_hidden

    pane.toggle_btn.click()

    assert pane.charts_hidden
    assert pane._splitter.isHidden()
    assert pane.toggle_btn.text() == "Show charts"
    assert settings.value(ep.CHARTS_HIDDEN_KEY, type=bool) is True
    assert _pane(qtbot, settings, monkeypatch).charts_hidden


def _bar(day: int, hour: int, close: float) -> dict[str, float]:
    ts = datetime(2026, 10, day, hour, tzinfo=timezone.utc).timestamp()
    return {"time": ts, "open": close, "high": close, "low": close, "close": close, "volume": 1}


def test_price_change_vs_previous_session() -> None:
    """UT-GUI-024.008.M06.T02: Change is measured from the previous session's last close."""
    candles = [_bar(21, 15, 90.0), _bar(21, 19, 100.0), _bar(22, 14, 101.0), _bar(22, 18, 102.0)]

    last, diff, pct = ep.price_change(candles)  # type: ignore[misc]

    assert last == 102.0
    assert diff == pytest.approx(2.0)
    assert pct == pytest.approx(2.0)


def test_price_change_needs_earlier_session() -> None:
    """UT-GUI-024.008.M06.T03: One session only (or no candles) gives no change."""
    assert ep.price_change([_bar(22, 14, 101.0), _bar(22, 18, 102.0)]) is None
    assert ep.price_change([]) is None
