"""
Module: MD-GUI-016.001.M08 / MD-GUI-015.003.M04 / MD-GUI-015.011.M05 / MD-GUI-003.001.M01
test cases (FO-GUI-016)
Parent SRD: SRD-GUI-016.001

Unit tests for PriceActionRulesDialog, the shared library tree and params popup, and the
Screener Builder wiring.
"""
from __future__ import annotations

import copy
import logging
import re
import sys
import types
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from PyQt6.QtCore import QMimeData, QPointF, Qt
from PyQt6.QtGui import QDropEvent
from PyQt6.QtWidgets import QDialog, QLabel, QLineEdit, QPushButton, QSpinBox, QWidget
from pytestqt.qtbot import QtBot

import us_swing.gui.pattern_rule_model as model_mod
import us_swing.gui.price_action_rules_dialog as dialog_mod
from us_swing.core.price_patterns import (
    PATTERNS,
    PatternCategory,
    get_pattern,
    pattern_rules_from_config,
)
from us_swing.gui.indicator_library_model import MIME_INDICATOR, InUseRole, LibraryTreeModel
from us_swing.gui.indicator_params_dialog import IndicatorParamsDialog
from us_swing.gui.pattern_rule_model import COL_SETTINGS
from us_swing.gui.price_action_rules_dialog import PriceActionRulesDialog


@pytest.fixture
def dialog(qtbot: QtBot) -> PriceActionRulesDialog:
    dlg = PriceActionRulesDialog({"schema": 2, "rules": [], "threshold": 0.2})
    qtbot.addWidget(dlg)
    return dlg


# ── Shared widgets (M04, M05) ─────────────────────────────────────────────────

def test_tree_built_from_pattern_catalogue() -> None:
    """UT-GUI-016.002.M04.T01: tree from PATTERNS shows 7 categories and pattern items."""
    tree = LibraryTreeModel(entries=PATTERNS, categories=PatternCategory)
    assert tree.rowCount() == 7
    assert tree.find_item("hammer") is not None


def test_default_tree_is_indicator_catalogue() -> None:
    """UT-GUI-016.002.M04.T02: default tree still lists indicators, not patterns."""
    tree = LibraryTreeModel()
    assert tree.find_item("rsi") is not None
    assert tree.find_item("hammer") is None


def test_params_popup_edits_pattern_spec(qtbot: QtBot) -> None:
    """UT-GUI-016.006.M05.T01: params popup shows one spinbox per VCP setting."""
    popup = IndicatorParamsDialog(get_pattern("vcp"), {})
    qtbot.addWidget(popup)
    for key in ("lookback", "contractions", "final_depth"):
        assert popup.findChild(QWidget, f"param_{key}") is not None


# ── Dialog (M08) ──────────────────────────────────────────────────────────────

def test_dialog_builds_both_panes(dialog: PriceActionRulesDialog) -> None:
    """UT-GUI-016.001.M08.T01: title and all named widgets are present."""
    assert dialog.windowTitle() == "Price Action Patterns"
    assert dialog.objectName() == "price_action_rules_dialog"
    assert dialog.findChild(QLineEdit, "rule_search") is dialog.search
    assert dialog.findChild(QWidget, "rule_library_tree") is dialog.tree
    assert dialog.findChild(QWidget, "rule_table") is dialog.table
    assert dialog.findChild(QLabel, "rule_header") is dialog.header
    assert dialog.findChild(QSpinBox, "threshold_spin") is dialog.threshold_spin
    assert dialog.ok_btn.objectName() == "btn_green"
    assert dialog.findChild(QPushButton, "rule_cancel_btn") is not None


def test_cancel_leaves_input_config_unchanged(qtbot: QtBot) -> None:
    """UT-GUI-016.001.M08.T02: editing then Cancel rejects and keeps the input dict."""
    config: dict[str, Any] = {}
    dlg = PriceActionRulesDialog(config)
    qtbot.addWidget(dlg)
    dlg._model.set_enabled(0, False)
    dlg.open()
    dlg.findChild(QPushButton, "rule_cancel_btn").click()
    assert dlg.result() == QDialog.DialogCode.Rejected
    assert config == {}


def test_add_pattern_adds_row_and_tags(dialog: PriceActionRulesDialog) -> None:
    """UT-GUI-016.003.M08.T01: adding Hammer adds a row, tags it and updates the header."""
    dialog._add_pattern("hammer")
    assert [r.pattern_id for r in dialog.rules()] == ["hammer"]
    item = dialog.tree_model.find_item("hammer")
    assert item is not None and item.data(InUseRole) is True
    assert dialog.header.text() == "1 pattern · 1 on"


def test_drop_pattern_adds_row(dialog: PriceActionRulesDialog) -> None:
    """UT-GUI-016.003.M08.T02: dropping the Doji payload appends one Doji row."""
    mime = QMimeData()
    mime.setData(MIME_INDICATOR, b"doji")
    event = QDropEvent(
        QPointF(5, 5), Qt.DropAction.CopyAction, mime,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    )
    dialog.table.dropEvent(event)
    assert [r.pattern_id for r in dialog.rules()] == ["doji"]


def test_unknown_pattern_adds_nothing(
    dialog: PriceActionRulesDialog, caplog: pytest.LogCaptureFixture
) -> None:
    """UT-GUI-016.003.M08.T03: unknown id adds no row and logs a [Screener] warning."""
    with caplog.at_level(logging.WARNING):
        dialog._add_pattern("nope")
    assert dialog.rules() == []
    assert any("[Screener]" in r.getMessage() for r in caplog.records)


def test_threshold_box_saves_fraction(dialog: PriceActionRulesDialog) -> None:
    """UT-GUI-016.007.M08.T01: threshold 40 % saves 0.4."""
    dialog.threshold_spin.setValue(40)
    assert dialog.get_config()["threshold"] == pytest.approx(0.4)


def test_out_of_range_threshold_clamped(qtbot: QtBot) -> None:
    """UT-GUI-016.007.M08.T02: saved threshold 1.7 shows as 100 %."""
    dlg = PriceActionRulesDialog({"schema": 2, "rules": [], "threshold": 1.7})
    qtbot.addWidget(dlg)
    assert dlg.threshold_spin.value() == 100


def test_threshold_box_refuses_negative(dialog: PriceActionRulesDialog) -> None:
    """UT-GUI-016.007.M08.T03: setting -10 % leaves 0 % and saves 0.0."""
    dialog.threshold_spin.setValue(-10)
    assert dialog.threshold_spin.value() == 0
    assert dialog.get_config()["threshold"] == 0.0


def test_settings_popup_saves_params(
    dialog: PriceActionRulesDialog, monkeypatch: pytest.MonkeyPatch
) -> None:
    """UT-GUI-016.006.M08.T01: accepted popup stores within 3 and updates the cell text."""

    class _Accepting:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def place_under(self, anchor: Any) -> None:
            pass

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

        def get_params(self) -> dict[str, float]:
            return {"within": 3.0}

    monkeypatch.setattr(dialog_mod, "IndicatorParamsDialog", _Accepting)
    dialog._add_pattern("hammer")
    dialog._edit_params(0)
    assert dialog.rules()[0].params["within"] == 3.0
    assert dialog._model.index(0, COL_SETTINGS).data() == "3-bar window"


def test_legacy_config_loads_five_rows(qtbot: QtBot) -> None:
    """UT-GUI-016.009.M08.T01: {} loads 5 legacy rows (2 on) and 20 %."""
    dlg = PriceActionRulesDialog({})
    qtbot.addWidget(dlg)
    assert len(dlg.rules()) == 5
    assert sum(r.enabled for r in dlg.rules()) == 2
    assert dlg.threshold_spin.value() == 20


def test_get_config_is_reloadable(dialog: PriceActionRulesDialog) -> None:
    """UT-GUI-016.009.M08.T02: get_config after adding Hammer is schema 2 and reloads equal."""
    dialog._add_pattern("hammer")
    config = dialog.get_config()
    assert config["schema"] == 2
    assert pattern_rules_from_config(config) == (dialog.rules(), pytest.approx(0.2))


def test_bad_saved_config_kept(qtbot: QtBot, caplog: pytest.LogCaptureFixture) -> None:
    """UT-GUI-016.009.M08.T03: unknown id gives 0 rows, a warning and the original config."""
    config: dict[str, Any] = {"schema": 2, "rules": [{"pattern_id": "nope"}], "threshold": 0.3}
    with caplog.at_level(logging.WARNING):
        dlg = PriceActionRulesDialog(copy.deepcopy(config))
    qtbot.addWidget(dlg)
    assert dlg.rules() == []
    assert any(r.levelno == logging.WARNING for r in caplog.records)
    assert dlg.get_config() == config


def test_style_rules_followed(dialog: PriceActionRulesDialog) -> None:
    """UT-GUI-016.011.M08.T01: no fixed heights in new modules; threshold QSS has outline none."""
    for mod in (model_mod, dialog_mod):
        source = Path(str(mod.__file__)).read_text(encoding="utf-8")
        assert "setFixedHeight(" not in source, mod.__name__
        assert "setFixedSize(" not in source, mod.__name__
    assert "outline: none" in dialog.threshold_spin.styleSheet()


def test_warning_text_is_user_facing(qtbot: QtBot, caplog: pytest.LogCaptureFixture) -> None:
    """UT-GUI-016.011.M08.T02: bad-config warning starts [Screener], no internal names."""
    with caplog.at_level(logging.WARNING):
        dlg = PriceActionRulesDialog({"schema": 2, "rules": "bad"})
    qtbot.addWidget(dlg)
    message = next(r.getMessage() for r in caplog.records if r.levelno == logging.WARNING)
    assert message.startswith("[Screener]")
    assert not re.search(r"[a-z]+_[a-z]+|[a-z][A-Z]|Error|Dialog", message)


# ── Screener Builder wiring (M01) ─────────────────────────────────────────────

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


def _fake(code: QDialog.DialogCode) -> type:
    class _Fake:
        def __init__(self, config: dict[str, Any] | None, parent: QWidget | None = None) -> None:
            pass

        def exec(self) -> QDialog.DialogCode:
            return code

        def get_config(self) -> dict[str, Any]:
            return {"schema": 2, "rules": [], "threshold": 0.2}

    return _Fake


def test_call_sites_store_new_config(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, screener_panel_module: types.ModuleType
) -> None:
    """UT-GUI-016.010.M01.T01: group and weighted call sites store the schema-2 config."""
    panel = screener_panel_module
    monkeypatch.setattr(panel, "PriceActionRulesDialog", _fake(QDialog.DialogCode.Accepted))
    group = panel._GroupWidget("g1", configs={"price_action": {}})
    qtbot.addWidget(group)
    with qtbot.waitSignal(group.changed, timeout=500):
        group._open_price_action_config("price_action")
    assert group._configs["price_action"]["schema"] == 2
    row = panel._WeightedRow("price_action", 0.5, {})
    qtbot.addWidget(row)
    row._open_config()
    assert row.config()["schema"] == 2


def test_cancel_keeps_config_and_old_dialog_gone(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, screener_panel_module: types.ModuleType
) -> None:
    """UT-GUI-016.010.M01.T02: rejected dialog keeps the old config; old dialog is deleted."""
    panel = screener_panel_module
    monkeypatch.setattr(panel, "PriceActionRulesDialog", _fake(QDialog.DialogCode.Rejected))
    old: dict[str, Any] = {"patterns": {}}
    group = panel._GroupWidget("g1", configs={"price_action": old})
    qtbot.addWidget(group)
    with qtbot.assertNotEmitted(group.changed):
        group._open_price_action_config("price_action")
    assert group._configs["price_action"] == old
    for name in ("_PriceActionConfigDialog", "_PA_DEFAULTS", "_PA_PATTERN_LABELS",
                 "_format_price_action_config"):
        assert not hasattr(panel, name), name
