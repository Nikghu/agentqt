"""Unit tests: MD-GUI-022.001.M01 — Edit Preset AI Provider choice.
Refs: UT-GUI-022.014.M01.T01 – T02, UT-GUI-022.015.M01.T01 – T02, UT-GUI-022.016.M01.T01
"""
from __future__ import annotations

from types import SimpleNamespace

from tests.screener.conftest import make_composite_preset
from us_swing.gui.screener_panel import _PresetBuilderDialog
from us_swing.screener.screeners._cloud_ai_models import DEFAULT_MODEL


def _dialog(qtbot, preset=None) -> _PresetBuilderDialog:  # type: ignore[no-untyped-def]
    dlg = _PresetBuilderDialog(mgr=SimpleNamespace(), user_id="u1", preset=preset)
    qtbot.addWidget(dlg)
    return dlg


def test_provider_choice_sets_model_and_is_saved(qtbot) -> None:  # type: ignore[no-untyped-def]
    """UT-GUI-022.014.M01.T01: Provider choice sets model and is saved."""
    dlg = _dialog(qtbot)
    assert dlg._ai_ranking_chk.text() == "Enable AI Ranking"
    assert [dlg._ai_provider.itemText(i) for i in range(dlg._ai_provider.count())] == [
        "OpenRouter", "Claude Code CLI",
    ]
    dlg._ai_provider.setCurrentIndex(dlg._ai_provider.findData("claude"))
    assert dlg._ai_model_combo.currentText() == "claude-sonnet-5-5"
    dlg._name.setText("AI preset")
    preset = dlg._build_preset_from_ui()
    assert preset.ai_provider == "claude"
    assert preset.ai_model == "claude-sonnet-5-5"
    assert dlg._ai_query_field.parentWidget() is not dlg._ai_model_combo.parentWidget()
    dlg._ai_provider.setCurrentIndex(dlg._ai_provider.findData("openrouter"))
    assert dlg._ai_model_combo.currentText() == DEFAULT_MODEL


def test_own_model_kept_and_old_preset_is_openrouter(qtbot) -> None:  # type: ignore[no-untyped-def]
    """UT-GUI-022.014.M01.T02: Own model kept on switch; old preset opens as OpenRouter."""
    dlg = _dialog(qtbot, make_composite_preset())
    assert dlg._ai_provider.currentData() == "openrouter"
    dlg._ai_model_combo.setEditText("google/gemini-2-flash")
    dlg._ai_provider.setCurrentIndex(dlg._ai_provider.findData("claude"))
    assert dlg._ai_model_combo.currentText() == "google/gemini-2-flash"


def test_model_list_follows_provider(qtbot) -> None:  # type: ignore[no-untyped-def]
    """UT-GUI-022.015.M01.T01: Model list follows the provider and allows typing."""
    dlg = _dialog(qtbot)
    combo = dlg._ai_model_combo

    def ids() -> list[str]:
        return [combo.itemText(i) for i in range(combo.count())]

    assert combo.isEditable()
    assert DEFAULT_MODEL in ids()
    dlg._ai_provider.setCurrentIndex(dlg._ai_provider.findData("claude"))
    assert ids() == ["claude-sonnet-5-5", "claude-haiku-5-5", "claude-opus-5-5"]
    combo.setEditText("claude-own-model")
    dlg._name.setText("AI preset")
    assert dlg._build_preset_from_ui().ai_model == "claude-own-model"


def test_model_list_opens_from_chevron_and_typing(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """UT-GUI-022.015.M01.T02: Chevron opens the list; typing shows matching models."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QCompleter

    dlg = _dialog(qtbot)
    combo = dlg._ai_model_combo
    opened: list[bool] = []
    monkeypatch.setattr(combo, "showPopup", lambda: opened.append(True))
    dlg._ai_model_list_action.trigger()
    assert opened == [True]
    completer = combo.completer()
    assert completer.filterMode() == Qt.MatchFlag.MatchContains
    assert completer.completionMode() == QCompleter.CompletionMode.PopupCompletion


def test_context_ticks_save_and_load(qtbot) -> None:  # type: ignore[no-untyped-def]
    """UT-GUI-022.016.M01.T01: Context ticks save and load."""
    dlg = _dialog(qtbot)
    for check in dlg._ai_ctx_checks.values():
        check.setChecked(True)
    dlg._name.setText("AI preset")
    preset = dlg._build_preset_from_ui()
    assert preset.ai_context == ["earnings", "sector"]
    again = _dialog(qtbot, preset)
    assert all(check.isChecked() for check in again._ai_ctx_checks.values())
