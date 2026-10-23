"""
Module: MD-GUI-024.008.M06 — Execution chart pane tests
Parent SRD: SRD-GUI-024.008
"""
from __future__ import annotations

import sys
import types
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
    toggled: list[bool] = []
    pane.charts_toggled.connect(toggled.append)
    assert not pane.charts_hidden

    pane.set_charts_hidden(True)

    assert pane.charts_hidden
    assert toggled == [True]
    assert settings.value(ep.CHARTS_HIDDEN_KEY, type=bool) is True
    assert _pane(qtbot, settings, monkeypatch).charts_hidden
