"""
Module: MD-GUI-021.001.M01 — tests
Parent SRD: SRD-GUI-021.001

Settings page: a section list on the left shows one section at a time (FO-GUI-021).
"""
from __future__ import annotations

import sys
import types
from typing import Any
from unittest.mock import MagicMock

import pytest
from PyQt6.QtWidgets import QWidget

# QWebEngineWidgets DLL is unavailable in the test environment — stub it so
# settings_panel.py can be imported without the DLL.
_web_stub = types.ModuleType("PyQt6.QtWebEngineWidgets")
_web_stub.QWebEngineView = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("PyQt6.QtWebEngineWidgets", _web_stub)

from us_swing.data.models import RiskConfig, UserProfile  # noqa: E402
from us_swing.gui import settings_panel  # noqa: E402
from us_swing.gui.system_store import SystemConfig  # noqa: E402


class _Signal:
    def connect(self, *_a: Any) -> None:
        pass


class _StubService:
    def __init__(self) -> None:
        self.user = UserProfile(
            user_id=1, username="trader", display_name="Trader", ibkr_client_id=101,
            mode="paper", risk_config=RiskConfig(), strategy_config={}, screener_config={},
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


@pytest.fixture()
def svc(monkeypatch: pytest.MonkeyPatch) -> _StubService:
    from us_swing.gui import telegram_token_store
    monkeypatch.setattr(telegram_token_store, "load", lambda _uid: "")
    return _StubService()


def test_system_sections_split(qapp: Any, svc: _StubService) -> None:
    """UT-GUI-021.001.M01.T01: the old System tab is split into three named sections."""
    sections = settings_panel._SystemSections(svc)  # type: ignore[arg-type]

    names = [name for name, _page in sections.pages]

    assert names == ["Connection", "Scheduler", "Telegram"]


def test_appearance_page_only(qapp: Any, svc: _StubService) -> None:
    """UT-GUI-027.005.M04.T01: Appearance is the only app page; Updates moved to the sidebar."""
    sections = settings_panel._SystemSections(svc)  # type: ignore[arg-type]
    pages = dict(sections.app_pages)

    assert list(pages) == ["Appearance"]
    assert pages["Appearance"].isAncestorOf(sections._btn_carbon)


def test_strip_keeps_three_buttons(qapp: Any) -> None:
    """UT-GUI-027.007.M06.T01: the right icon strip has no System or Data button."""
    from us_swing.gui.side_panels import IconStrip

    strip = IconStrip()

    assert list(strip._buttons) == ["details", "watch", "log"]


class _PlainTab(QWidget):
    def __init__(self, *_a: Any) -> None:
        super().__init__()

    def refresh_theme(self, _theme_id: str = "") -> None:
        pass


def test_section_click_shows_one_section(
    qapp: Any, svc: _StubService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """UT-GUI-021.001.M01.T02: clicking a section in the list shows only that section."""
    for name in ("_UsersTab", "_UniverseTab", "_DataPanel"):
        monkeypatch.setattr(settings_panel, name, _PlainTab)
    panel = settings_panel.SettingsPanel(svc)  # type: ignore[arg-type]
    buttons = panel._nav_group.buttons()
    names = [b.text() for b in buttons]
    assert panel._stack.count() == len(buttons)
    assert panel._stack.currentIndex() == 0 and buttons[0].isChecked()

    buttons[names.index("Telegram")].click()

    assert panel._stack.currentIndex() == names.index("Telegram")
    assert not buttons[0].isChecked()


def test_eight_sections_in_order(
    qapp: Any, svc: _StubService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """UT-GUI-027.002.M04.T01: the dialog lists all eight sections in order."""
    for name in ("_UsersTab", "_UniverseTab", "_DataPanel"):
        monkeypatch.setattr(settings_panel, name, _PlainTab)
    panel = settings_panel.SettingsPanel(svc)  # type: ignore[arg-type]

    names = [b.text() for b in panel._nav_group.buttons()]

    assert names == ["Users", "Risk", "Connection", "Scheduler", "Telegram", "Universe",
                     "Candle data", "Appearance"]
    assert panel._stack.count() == 8


@pytest.fixture()
def panel(svc: _StubService, monkeypatch: pytest.MonkeyPatch) -> settings_panel.SettingsPanel:
    for name in ("_UsersTab", "_UniverseTab", "_DataPanel"):
        monkeypatch.setattr(settings_panel, name, _PlainTab)
    return settings_panel.SettingsPanel(svc)  # type: ignore[arg-type]


def _risk_tab(panel: settings_panel.SettingsPanel) -> Any:
    return next(w for w in panel.findChildren(settings_panel._RiskTab))


def test_edit_then_apply_saves_once(qapp: Any, panel: Any, svc: _StubService) -> None:
    """UT-GUI-027.010.M04.T01: an edit marks the panel dirty; Apply saves once and clears it."""
    seen: list[bool] = []
    panel.dirty_changed.connect(seen.append)

    _risk_tab(panel)._risk.setValue(2.5)
    panel.apply()

    assert seen == [True, False]
    assert len(svc.updated) == 1
    assert svc.updated[0].risk_config.risk_per_trade_pct == 2.5
    assert not panel.is_dirty


def test_cancel_drops_edits(qapp: Any, panel: Any, svc: _StubService) -> None:
    """UT-GUI-027.010.M04.T02: revert reloads the saved value and saves nothing."""
    saved = svc.user.risk_config.risk_per_trade_pct
    _risk_tab(panel)._risk.setValue(2.5)

    panel.revert()

    assert svc.updated == []
    assert _risk_tab(panel)._risk.value() == saved
    assert not panel.is_dirty


@pytest.mark.parametrize(("answer", "dirty"), [("Yes", True), ("No", False)])
def test_restore_defaults_asks_first(
    qapp: Any, panel: Any, monkeypatch: pytest.MonkeyPatch, answer: str, dirty: bool
) -> None:
    """UT-GUI-027.011.M04.T01–T02: Restore defaults fills defaults only after yes."""
    button = getattr(settings_panel.QMessageBox.StandardButton, answer)
    monkeypatch.setattr(settings_panel.QMessageBox, "question", lambda *_a: button)
    panel.show_section("Risk")
    tab = _risk_tab(panel)
    tab._risk.setValue(2.5)
    panel._set_clean()

    panel.restore_defaults()

    expected = RiskConfig().risk_per_trade_pct if dirty else 2.5
    assert tab._risk.value() == expected
    assert panel.is_dirty is dirty


def test_section_dot_states(qapp: Any, panel: Any) -> None:
    """UT-GUI-027.012.M04.T01: dots show ok, warn and off, and hide for none."""
    dot = panel._dots["Telegram"]
    for state in ("ok", "warn", "off"):
        panel.set_section_state("Telegram", state)
        assert not dot.isHidden() and dot.property("state") == state

    panel.set_section_state("Telegram", "none")

    assert dot.isHidden()


@pytest.mark.parametrize(
    ("enabled", "token", "chat", "state"),
    [(True, "t", "c", "ok"), (True, "t", "", "warn"), (False, "t", "c", "off")],
)
def test_telegram_dot_rule(enabled: bool, token: str, chat: str, state: str) -> None:
    """UT-GUI-027.012.M04.T02: Telegram is ok when ready, warn when incomplete, else off."""
    assert settings_panel.telegram_dot(enabled, token, chat) == state


def test_theme_waits_for_apply(
    qapp: Any, panel: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """UT-GUI-027.013.M04.T01: picking a theme applies nothing until Apply."""
    from us_swing.gui import theme

    applied: list[str] = []
    monkeypatch.setattr(theme, "apply_theme", applied.append)
    monkeypatch.setattr(theme, "save_theme_id", lambda _t: None)
    panel._sys._btn_mocha.click()
    assert applied == [] and panel.is_dirty

    panel.apply()

    assert applied == ["mocha"]


def test_risk_save_persists(qapp: Any, svc: _StubService) -> None:
    """UT-GUI-021.002.M01.T01: Save Risk Settings writes the values to the active user."""
    tab = settings_panel._RiskTab(svc)  # type: ignore[arg-type]
    tab._risk.setValue(2.5)
    tab._ord_type.setCurrentText("LMT")

    tab._on_save()

    assert len(svc.updated) == 1
    saved = svc.updated[0].risk_config
    assert (saved.risk_per_trade_pct, saved.default_order_type) == (2.5, "LMT")


def test_risk_save_keeps_other_fields(qapp: Any, svc: _StubService) -> None:
    """UT-GUI-021.002.M01.T02: Risk save does not touch Telegram or other user fields."""
    svc.user.telegram_chat_id = "12345"
    tab = settings_panel._RiskTab(svc)  # type: ignore[arg-type]

    tab._on_save()

    assert svc.updated[0].telegram_chat_id == "12345"
    assert svc.updated[0].username == "trader"
