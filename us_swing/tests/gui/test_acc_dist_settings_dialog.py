"""Tests for AccDistSettingsDialog (MD-SCR-017.013.M33).

Refs: UT-SCR-017.013.M33.T01–T04 (FO-SCR-015)
"""
from __future__ import annotations

from PyQt6.QtWidgets import QCheckBox
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
