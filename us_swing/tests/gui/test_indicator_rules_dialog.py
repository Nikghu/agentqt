"""
Module: MD-GUI-015.001.M06 / MD-GUI-003.001.M01 test cases (FO-GUI-015)
Parent SRD: SRD-GUI-015.001

Unit tests for IndicatorRulesDialog and the screener-group "Configure" wiring.
"""
from __future__ import annotations

import copy
import logging
import sys
import types
from collections.abc import Iterator
from typing import Any

import pytest
from PyQt6.QtCore import QMimeData, QPointF, Qt
from PyQt6.QtGui import QDropEvent
from PyQt6.QtWidgets import QDialog, QLabel, QLineEdit, QPushButton, QWidget
from pytestqt.qtbot import QtBot

from us_swing.core.indicator_rules import Condition, rules_from_config, rules_to_config
from us_swing.gui.indicator_library_model import MIME_INDICATOR, InUseRole
from us_swing.gui.indicator_rule_model import COL_ON, RuleRole
from us_swing.gui.indicator_rules_dialog import IndicatorRulesDialog

_LEGACY: dict[str, Any] = {
    "filters": {
        "volatility": {"enabled": True, "min_atr_pct": 0.01},
        "rsi": {"enabled": True, "min": 30, "max": 70, "period": 14},
        "range": {"enabled": True, "min_price": 5.0, "max_price": 5000.0},
        "breakout": {"enabled": True, "lookback": 10},
        "volume": {"enabled": True, "min_volume_ratio": 1.0, "ma_period": 10},
        "rs_index": {"enabled": False, "rs_min_percentile": 70.0, "rs_slope_days": 63},
    }
}


@pytest.fixture
def dialog(qtbot: QtBot) -> IndicatorRulesDialog:
    dlg = IndicatorRulesDialog({"schema": 2, "rules": []})
    qtbot.addWidget(dlg)
    return dlg


def _legacy_dialog(qtbot: QtBot) -> IndicatorRulesDialog:
    dlg = IndicatorRulesDialog(copy.deepcopy(_LEGACY))
    qtbot.addWidget(dlg)
    return dlg


def test_dialog_builds_both_panes(dialog: IndicatorRulesDialog) -> None:
    """UT-GUI-015.001.M06.T01: title and all named widgets are present."""
    assert dialog.windowTitle() == "Indicator Filters"
    assert dialog.objectName() == "indicator_rules_dialog"
    assert dialog.findChild(QLineEdit, "rule_search") is dialog.search
    assert dialog.findChild(QWidget, "rule_library_tree") is dialog.tree
    assert dialog.findChild(QWidget, "rule_table") is dialog.table
    assert dialog.findChild(QLabel, "rule_header") is dialog.header
    assert dialog.ok_btn.objectName() == "btn_green"
    assert dialog.findChild(QPushButton, "rule_cancel_btn") is not None


def test_cancel_leaves_input_config_unchanged(qtbot: QtBot) -> None:
    """UT-GUI-015.001.M06.T02: editing a row then Cancel rejects and keeps the input dict."""
    config = copy.deepcopy(_LEGACY)
    dlg = IndicatorRulesDialog(config)
    qtbot.addWidget(dlg)
    dlg._model.set_enabled(0, False)
    dlg.open()
    dlg.findChild(QPushButton, "rule_cancel_btn").click()
    assert dlg.result() == QDialog.DialogCode.Rejected
    assert config == _LEGACY


def test_add_indicator_adds_row_and_tags(dialog: IndicatorRulesDialog) -> None:
    """UT-GUI-015.007.M06.T01: adding EMA(50) adds a row and marks it in use."""
    dialog._add_indicator("ema_50")
    assert [r.indicator_id for r in dialog.rules()] == ["ema_50"]
    item = dialog.tree_model.find_item("ema_50")
    assert item is not None
    assert item.data(InUseRole) is True


def test_add_unavailable_indicator_ignored(dialog: IndicatorRulesDialog) -> None:
    """UT-GUI-015.007.M06.T02: an intraday-only indicator adds no row."""
    dialog._add_indicator("rvol_5m")
    assert dialog.rules() == []


def test_drop_indicator_adds_row(dialog: IndicatorRulesDialog) -> None:
    """UT-GUI-015.007.M06.T03: dropping the RSI mime payload appends one RSI row."""
    mime = QMimeData()
    mime.setData(MIME_INDICATOR, b"rsi")
    event = QDropEvent(
        QPointF(5, 5),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    dialog.table.dropEvent(event)
    assert [r.indicator_id for r in dialog.rules()] == ["rsi"]


def test_legacy_config_loads_six_rows(qtbot: QtBot) -> None:
    """UT-GUI-015.013.M06.T01: legacy 6-section config loads as 6 rows, RS row off."""
    dlg = _legacy_dialog(qtbot)
    rules = dlg.rules()
    assert len(rules) == 6
    rs = next(r for r in rules if r.indicator_id == "rs_index")
    assert rs.enabled is False
    assert dlg._model.index(0, COL_ON).data(RuleRole) is not None


def test_get_config_is_reloadable_schema_two(dialog: IndicatorRulesDialog) -> None:
    """UT-GUI-015.013.M06.T02: get_config after adding EMA(50) is schema 2 and reloads equal."""
    dialog._add_indicator("ema_50")
    config = dialog.get_config()
    assert config["schema"] == 2
    assert rules_from_config(config) == dialog.rules()
    assert config == rules_to_config(dialog.rules(), "SPY")
    assert dialog.rules()[0].condition in Condition


def test_bad_saved_config_starts_empty_and_is_kept(
    qtbot: QtBot, caplog: pytest.LogCaptureFixture
) -> None:
    """UT-GUI-015.013.M06.T03: unknown indicator id gives 0 rows, a warning, and original config."""
    config: dict[str, Any] = {
        "schema": 2,
        "rules": [{"indicator_id": "nope", "condition": "at_least", "value": 1}],
    }
    with caplog.at_level(logging.WARNING):
        dlg = IndicatorRulesDialog(config)
    qtbot.addWidget(dlg)
    assert dlg.rules() == []
    assert any(
        r.levelno == logging.WARNING and "[Screener]" in r.getMessage() for r in caplog.records
    )
    assert dlg.get_config() == config


@pytest.fixture
def screener_panel_module(monkeypatch: pytest.MonkeyPatch) -> Iterator[types.ModuleType]:
    """Import screener_panel, stubbing QtWebEngineWidgets when its DLL cannot load."""
    try:
        import PyQt6.QtWebEngineWidgets  # noqa: F401
    except ImportError:
        stub = types.ModuleType("PyQt6.QtWebEngineWidgets")
        stub.QWebEngineView = type("QWebEngineView", (QWidget,), {})  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "PyQt6.QtWebEngineWidgets", stub)
        monkeypatch.delitem(sys.modules, "us_swing.gui.screener_panel", raising=False)
    import us_swing.gui.screener_panel as panel

    yield panel
    sys.modules.pop("us_swing.gui.screener_panel", None)


class _FakeDialog:
    result_code = QDialog.DialogCode.Accepted
    new_config: dict[str, Any] = {"schema": 2, "rules": []}

    def __init__(self, config: dict[str, Any] | None, parent: QWidget | None = None) -> None:
        pass

    def exec(self) -> QDialog.DialogCode:
        return self.result_code

    def get_config(self) -> dict[str, Any]:
        return self.new_config


def _group(panel: types.ModuleType, qtbot: QtBot, old: dict[str, Any]) -> Any:
    group = panel._GroupWidget("g1", configs={"indicator": old})
    qtbot.addWidget(group)
    return group


def test_group_configure_stores_accepted_config(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, screener_panel_module: types.ModuleType
) -> None:
    """UT-GUI-015.014.M01.T01: accepted dialog stores the schema-2 config and emits changed."""
    fake = type("Accepting", (_FakeDialog,), {"result_code": QDialog.DialogCode.Accepted})
    monkeypatch.setattr(screener_panel_module, "IndicatorRulesDialog", fake)
    group = _group(screener_panel_module, qtbot, {"filters": {}})
    with qtbot.waitSignal(group.changed, timeout=500):
        group._open_indicator_config("indicator")
    assert group._configs["indicator"]["schema"] == 2


def test_group_configure_cancel_keeps_old_config(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, screener_panel_module: types.ModuleType
) -> None:
    """UT-GUI-015.014.M01.T02: rejected dialog leaves the stored config and emits nothing."""
    fake = type("Rejecting", (_FakeDialog,), {"result_code": QDialog.DialogCode.Rejected})
    monkeypatch.setattr(screener_panel_module, "IndicatorRulesDialog", fake)
    old: dict[str, Any] = {"filters": {}}
    group = _group(screener_panel_module, qtbot, old)
    with qtbot.assertNotEmitted(group.changed):
        group._open_indicator_config("indicator")
    assert group._configs["indicator"] == old
