"""
Module: MD-GUI-033.001.M01 — tests
Parent SRD: SRD-GUI-033.001

AI notes settings on Settings → Telegram: provider cards, fallback rule, Apply gate,
save and load, and the Telegram dot (FO-GUI-033).
"""
from __future__ import annotations

from typing import Any

import pytest
from PyQt6.QtWidgets import QWidget

from us_swing.data.models import RiskConfig, UserProfile
from us_swing.gui import ai_settings_block as asb
from us_swing.gui import settings_panel, user_store
from us_swing.gui.ai_settings_block import (
    FALLBACK_HINT,
    AiSettings,
    AiSettingsBlock,
    ai_problem,
    ai_ready,
)
from us_swing.gui.settings_dialog import SettingsDialog
from us_swing.gui.system_store import SystemConfig


@pytest.fixture()
def block(qtbot: Any, monkeypatch: pytest.MonkeyPatch) -> AiSettingsBlock:
    monkeypatch.setattr(asb, "claude_found", lambda: True)
    widget = AiSettingsBlock()
    qtbot.addWidget(widget)
    return widget


def test_block_layout(block: AiSettingsBlock) -> None:
    """UT-GUI-033.001.M01.T01: AI off by default; card fields off; Claude model Sonnet 5.5."""
    assert not block._enabled.isChecked()
    for widget in (block._claude_on, block._claude_model, block._or_on, block._or_key,
                   block._or_model, block._fallback):
        assert not widget.isEnabled()
    assert block._claude_model.currentText() == "Sonnet 5.5"
    assert block.settings() == AiSettings()


def test_card_fields_follow_ticks(block: AiSettingsBlock) -> None:
    """UT-GUI-033.002.M01.T01: each card's fields follow its Use tick."""
    block._enabled.setChecked(True)
    block._claude_on.setChecked(False)
    block._or_on.setChecked(True)

    assert not block._claude_model.isEnabled() and not block._claude_default.isEnabled()
    assert block._or_key.isEnabled() and block._or_model.isEnabled()
    assert block._claude_status.text() == "Not used"


def test_fallback_needs_both(block: AiSettingsBlock) -> None:
    """UT-GUI-033.003.M01.T01: Fallback is off with a hint until both providers are ticked."""
    block._enabled.setChecked(True)
    assert not block._fallback.isEnabled()
    assert block._hint.isVisibleTo(block) and block._hint.text() == FALLBACK_HINT

    block._or_on.setChecked(True)

    assert block._fallback.isEnabled()
    assert not block._hint.isVisibleTo(block)


def test_untick_clears_fallback_and_moves_default(block: AiSettingsBlock) -> None:
    """UT-GUI-033.003.M01.T02: unticking a provider clears Fallback and moves Default."""
    block.load(AiSettings(enabled=True, openrouter_on=True, openrouter_model="m",
                          default="openrouter", fallback=True), "k")
    assert block._fallback.isChecked() and block._or_default.isChecked()

    block._or_on.setChecked(False)

    assert not block._fallback.isChecked()
    assert block.settings().default == "claude"


@pytest.mark.parametrize(
    ("settings", "key", "word"),
    [
        (AiSettings(enabled=True, claude_on=False, openrouter_on=True, openrouter_model="m"),
         "", "API key"),
        (AiSettings(enabled=True, claude_on=False), "", "provider"),
        (AiSettings(enabled=False, claude_on=False, openrouter_on=True), "", ""),
    ],
)
def test_problem_text(settings: AiSettings, key: str, word: str) -> None:
    """UT-GUI-033.004.M01.T01: the problem line names what is missing; empty when AI is off."""
    problem = ai_problem(settings, key)
    assert (word in problem) if word else problem == ""


@pytest.mark.parametrize(
    ("settings", "key", "claude_ok", "ready"),
    [
        (AiSettings(enabled=True), "", True, True),
        (AiSettings(enabled=True), "", False, False),
        (AiSettings(enabled=True, openrouter_on=True, openrouter_model="m",
                    default="openrouter"), "k", False, True),
        (AiSettings(enabled=True, openrouter_on=True, openrouter_model="m",
                    default="openrouter"), "", True, False),
    ],
)
def test_default_ready(settings: AiSettings, key: str, claude_ok: bool, ready: bool) -> None:
    """UT-GUI-033.006.M01.T01: ready follows the default provider only."""
    assert ai_ready(settings, key, claude_ok) is ready


# ── Panel and dialog ─────────────────────────────────────────────────────────


class _Signal:
    def connect(self, *_a: Any) -> None:
        pass


class _StubService:
    def __init__(self) -> None:
        self.user = UserProfile(
            user_id=1, username="trader", display_name="Trader", ibkr_client_id=101,
            mode="paper", risk_config=RiskConfig(), strategy_config={}, screener_config={},
            telegram_enabled=True, telegram_chat_id="42",
        )
        self.updated: list[UserProfile] = []
        self.circuit_breaker_active = False
        self.circuit_breaker_changed = _Signal()

    def get_system_config(self) -> SystemConfig:
        return SystemConfig()

    def get_active_user(self) -> UserProfile:
        return self.user

    def update_user(self, user: UserProfile) -> None:
        self.updated.append(user)

    def reconfigure_notifications(self) -> None:
        pass


class _PlainTab(QWidget):
    def __init__(self, *_a: Any) -> None:
        super().__init__()
        self.state = ("none", "")

    def refresh_theme(self, _theme_id: str = "") -> None:
        pass


class _PlainBacktest(_PlainTab):
    inputs: list[QWidget] = []
    state = "none"

    def save(self) -> None:
        pass

    def load(self) -> None:
        pass

    def defaults(self) -> None:
        pass


@pytest.fixture()
def svc(monkeypatch: pytest.MonkeyPatch) -> _StubService:
    from us_swing.gui import telegram_token_store
    monkeypatch.setattr(telegram_token_store, "load", lambda _uid: "token")
    monkeypatch.setattr(telegram_token_store, "save", lambda _uid, _token: None)
    monkeypatch.setattr(asb, "claude_found", lambda: True)
    monkeypatch.setattr(settings_panel, "claude_found", lambda: True)
    return _StubService()


def _panel(qtbot: Any, svc: _StubService, monkeypatch: pytest.MonkeyPatch) -> Any:
    for name in ("_UsersTab", "_UniverseTab", "_DataPanel"):
        monkeypatch.setattr(settings_panel, name, _PlainTab)
    monkeypatch.setattr(settings_panel, "BacktestDataPanel", _PlainBacktest)
    panel = settings_panel.SettingsPanel(svc)  # type: ignore[arg-type]
    qtbot.addWidget(panel)
    return panel


def test_apply_gated(qtbot: Any, svc: _StubService, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-GUI-033.004.M02.T01: Apply and OK stay off until the OpenRouter key is typed."""
    dialog = SettingsDialog(_panel(qtbot, svc, monkeypatch))
    qtbot.addWidget(dialog)
    block = dialog.panel._sys.ai_block
    block._enabled.setChecked(True)
    block._claude_on.setChecked(False)
    block._or_on.setChecked(True)
    block._or_model.setCurrentText("openai/gpt-4o-mini")

    assert not dialog._apply_btn.isEnabled() and not dialog._ok_btn.isEnabled()
    assert "API key" in block._problem.text()

    block._or_key.setText("sk-test")

    assert dialog._apply_btn.isEnabled() and dialog._ok_btn.isEnabled()


def test_save_and_load_round_trip(
    qtbot: Any, svc: _StubService, monkeypatch: pytest.MonkeyPatch,
    openrouter_key: dict[str, str],
) -> None:
    """UT-GUI-033.005.M02.T01: AI settings survive Apply; the key goes to the keychain only."""
    panel = _panel(qtbot, svc, monkeypatch)
    block = panel._sys.ai_block
    block._enabled.setChecked(True)
    block._or_on.setChecked(True)
    block._or_key.setText("sk-test")
    block._or_model.setCurrentText("openai/gpt-4o-mini")
    block._or_default.setChecked(True)
    block._fallback.setChecked(True)
    block._claude_model.setCurrentIndex(1)

    panel.apply()

    expected = AiSettings(enabled=True, claude_model="claude-haiku-5-5", openrouter_on=True,
                          openrouter_model="openai/gpt-4o-mini", default="openrouter",
                          fallback=True)
    assert openrouter_key["key"] == "sk-test"
    saved = user_store._to_dict(svc.updated[-1])
    assert "sk-test" not in saved.values()
    restored = user_store._from_dict(saved)
    svc.user = restored
    again = _panel(qtbot, svc, monkeypatch)._sys.ai_block
    assert again.settings() == expected
    assert again.key == "sk-test"


def test_blank_key_keeps_stored_key(
    qtbot: Any, svc: _StubService, monkeypatch: pytest.MonkeyPatch,
    openrouter_key: dict[str, str],
) -> None:
    """UT-GUI-033.005.M02.T01: a blank key field never deletes the screener's stored key."""
    openrouter_key["key"] = "sk-old"
    panel = _panel(qtbot, svc, monkeypatch)
    panel._sys.ai_block._or_key.setText("")
    panel._sys.ai_block._enabled.setChecked(True)

    panel.apply()

    assert openrouter_key["key"] == "sk-old"


def test_dot_warns_when_default_not_ready(
    qtbot: Any, svc: _StubService, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UT-GUI-033.006.M02.T01: Telegram dot is warn when AI is on and claude is missing."""
    panel = _panel(qtbot, svc, monkeypatch)
    assert panel._sys.telegram_state() == "ok"

    svc.user.ai_enabled = True
    monkeypatch.setattr(settings_panel, "claude_found", lambda: False)

    assert panel._sys.telegram_state() == "warn"


def test_keychain_error_still_saves(
    qtbot: Any, svc: _StubService, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UT-GUI-033.005.M02.T02: a keychain error keeps the other Telegram and AI settings."""
    from us_swing.screener.screeners import _api_key_store

    def _fail(_key: str) -> None:
        raise RuntimeError("locked")

    monkeypatch.setattr(_api_key_store, "save", _fail)
    panel = _panel(qtbot, svc, monkeypatch)
    block = panel._sys.ai_block
    block._enabled.setChecked(True)
    block._or_key.setText("sk-new")

    panel.apply()

    assert svc.updated[-1].ai_enabled is True
    assert "keychain" in panel._sys._tg_note.text()


def test_env_key_locks_field(qtbot: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-GUI-033.002.M01.T02: a key set by OPENROUTER_API_KEY cannot be edited here."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-env")
    monkeypatch.setattr(asb, "claude_found", lambda: True)
    block = AiSettingsBlock()
    qtbot.addWidget(block)
    block.load(AiSettings(enabled=True, openrouter_on=True, openrouter_model="m"), "sk-env")

    assert block.key_locked
    assert not block._or_key.isEnabled() and block._or_model.isEnabled()
