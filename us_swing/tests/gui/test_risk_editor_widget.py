"""
Module: MD-GUI-014.001.M03 test cases (FO-GUI-014)
Parent SRD: SRD-GUI-014.007

Unit tests for _RiskEditorWidget — the "Off" trailing-mode option added so a
user can disable trailing on an open cycle from the inline editor.
"""
from __future__ import annotations

from pytestqt.qtbot import QtBot

from us_swing.execution.trade_cycle._dto import CycleSnapshot
from us_swing.gui.risk_editor_widget import _RiskEditorWidget


def _snap(**overrides: object) -> CycleSnapshot:
    base: dict[str, object] = {
        "cycle_id": 7,
        "entry_price": 180.0,
        "hard_stop_loss": 179.0,
        "target_price": 189.0,
        "current_price": 185.0,
    }
    base.update(overrides)
    return CycleSnapshot(**base)  # type: ignore[arg-type]


def test_trail_mode_defaults_to_off_when_unset(qtbot: QtBot) -> None:
    """UT-GUI-014.001.M03.T09: a cycle with no trailing mode shows 'Off' selected."""
    w = _RiskEditorWidget(_snap(trailing_mode=None))
    qtbot.addWidget(w)
    assert w._trail_mode.currentText() == "Off"


def test_selecting_off_emits_empty_trailing_mode(qtbot: QtBot) -> None:
    """UT-GUI-014.001.M03.T10: switching a trailing cycle to 'Off' saves trailing_mode=""."""
    w = _RiskEditorWidget(_snap(trailing_mode="$", trailing_offset=2.5))
    qtbot.addWidget(w)
    assert w._trail_mode.currentText() == "$"

    w._trail_mode.setCurrentText("Off")
    fields = w._collect_changed_fields()
    assert fields["trailing_mode"] == ""
