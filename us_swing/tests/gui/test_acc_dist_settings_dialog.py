"""Tests for AccDistSettingsDialog (MD-SCR-017.013.M33).

Refs: UT-SCR-017.013.M33.T01–T05 (FO-SCR-015)
"""
from __future__ import annotations

import sys
import types
from collections.abc import Iterator
from typing import Any

import pytest
from PyQt6.QtWidgets import QCheckBox, QDialog, QWidget
from pytestqt.qtbot import QtBot

from us_swing.gui.acc_dist_settings_dialog import AccDistSettingsDialog
from us_swing.screener.screeners.acc_dist import SETTINGS, default_config


def _dialog(qtbot: QtBot, config: dict[str, object] | None) -> AccDistSettingsDialog:
    dlg = AccDistSettingsDialog(config)
    qtbot.addWidget(dlg)
    return dlg


def test_round_trip(qtbot: QtBot) -> None:
    """UT-SCR-017.013.M33.T01: A saved config loads and comes back unchanged."""
    cfg = {**default_config(), "mode": "distribution", "lookback": 30, "location_filter": False}
    assert _dialog(qtbot, cfg).get_config() == cfg


def test_every_setting_has_an_input(qtbot: QtBot) -> None:
    """UT-SCR-017.013.M33.T02: Every setting has an input and on/off settings are checkboxes."""
    dlg = _dialog(qtbot, None)
    assert set(dlg.inputs) == set(SETTINGS)
    assert isinstance(dlg.inputs["close_position"], QCheckBox)
    assert dlg.get_config() == default_config()


def test_inputs_are_range_limited(qtbot: QtBot) -> None:
    """UT-SCR-017.013.M33.T03: Inputs cannot go past the allowed range."""
    dlg = _dialog(qtbot, None)
    spin = dlg.inputs["lookback"]
    assert not isinstance(spin, QCheckBox)
    spin.setValue(999)
    assert dlg.get_config()["lookback"] == 120


def test_bad_config_and_reset(qtbot: QtBot) -> None:
    """UT-SCR-017.013.M33.T04: A bad saved config opens with defaults; Reset restores defaults."""
    dlg = _dialog(qtbot, {"mode": "sideways"})
    assert dlg.get_config() == default_config()
    dlg.mode_combo.setCurrentIndex(1)
    dlg.inputs["location_filter"].setChecked(False)  # type: ignore[union-attr]
    dlg._reset()
    assert dlg.get_config() == default_config()


def test_move_rule_input(qtbot: QtBot) -> None:
    """UT-SCR-017.016.M33.T01: Move rule round trips and enables only the input it uses."""
    dlg = _dialog(qtbot, {"min_move_pct": 0.8})
    assert dlg.move_rule_combo.currentData() == "fixed"
    assert dlg.inputs["min_move_pct"].isEnabled() and not dlg.inputs["move_factor"].isEnabled()
    assert dlg.get_config()["move_rule"] == "fixed"
    dlg.move_rule_combo.setCurrentIndex(0)
    assert dlg.inputs["move_factor"].isEnabled() and not dlg.inputs["min_move_pct"].isEnabled()
    assert dlg.get_config()["move_rule"] == "own"


def test_tabs_and_tip_panel(qtbot: QtBot) -> None:
    """UT-SCR-017.017.M33.T01: Four tabs switch pages; a clicked setting fills the tip panel."""
    dlg = _dialog(qtbot, {"mode": "distribution", "zone_pct": 25.0})
    assert len(dlg.tab_group.buttons()) == 4
    dlg.tab_group.button(2).click()  # type: ignore[union-attr]
    assert dlg.pages.currentIndex() == 2
    dlg.show_tip("zone_pct")
    assert dlg.tip_title_lbl.text() == "How near the high"
    assert "$95.00" in dlg.tip_example_lbl.text()
    dlg.mode_combo.setCurrentIndex(0)
    assert dlg.tip_title_lbl.text() == "How near the low"
    assert dlg.mode_chip.text() == "Accumulation"


def test_rules_chip_and_mode_enabling(qtbot: QtBot) -> None:
    """UT-SCR-017.018.M33.T01: The rules chip follows the values; unused inputs are disabled."""
    dlg = _dialog(qtbot, {"mode": "distribution"})
    assert dlg.strict_chip.text() == "Rules: Balanced"
    assert not dlg.inputs["min_ud_ratio"].isEnabled() and dlg.inputs["max_ud_ratio"].isEnabled()
    for key, value in (("min_score", 0.2), ("min_rally_days", 1), ("min_drop_days", 1)):
        dlg.inputs[key].setValue(value)  # type: ignore[union-attr]
    dlg.inputs["location_filter"].setChecked(False)  # type: ignore[union-attr]
    dlg.inputs["close_position"].setChecked(False)  # type: ignore[union-attr]
    assert dlg.strict_chip.text() == "Rules: Wide"
    assert not dlg.inputs["zone_pct"].isEnabled()
    assert "Rules overall: <b>Wide</b>" in dlg.summary_lbl.text()


@pytest.fixture
def panel_module(monkeypatch: pytest.MonkeyPatch) -> Iterator[types.ModuleType]:
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


class _AcceptingDialog:
    def __init__(self, config: dict[str, Any] | None, parent: QWidget | None = None) -> None:
        pass

    def exec(self) -> QDialog.DialogCode:
        return QDialog.DialogCode.Accepted

    def get_config(self) -> dict[str, Any]:
        return {**default_config(), "mode": "distribution"}


def test_panel_wiring(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, panel_module: types.ModuleType
) -> None:
    """UT-SCR-017.013.M33.T05: Builder shows Acc / Dist and both call sites store its config."""
    panel = panel_module
    assert panel._SCREENER_DISPLAY["acc_dist"] == "Acc / Dist"
    monkeypatch.setattr(panel, "AccDistSettingsDialog", _AcceptingDialog)
    group = panel._GroupWidget("g1", configs={"acc_dist": {}})
    qtbot.addWidget(group)
    with qtbot.waitSignal(group.changed, timeout=500):
        group._open_acc_dist_config("acc_dist")
    assert group._configs["acc_dist"]["mode"] == "distribution"
    row = panel._WeightedRow("acc_dist", 0.5, {})
    qtbot.addWidget(row)
    row._open_config()
    assert row.config()["mode"] == "distribution"
