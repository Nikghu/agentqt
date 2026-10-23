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
    """UT-GUI-021.001.M01.T01: the old System tab is split into six named sections."""
    sections = settings_panel._SystemSections(svc)  # type: ignore[arg-type]

    names = [name for name, _page in sections.pages]

    assert names == ["Connection", "Scheduler", "Telegram", "Theme", "Updates", "Diagnostics"]


class _PlainTab(QWidget):
    def __init__(self, *_a: Any) -> None:
        super().__init__()

    def refresh_theme(self, _theme_id: str = "") -> None:
        pass


def test_section_click_shows_one_section(
    qapp: Any, svc: _StubService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """UT-GUI-021.001.M01.T02: clicking a section in the list shows only that section."""
    for name in ("_UsersTab", "_UniverseTab", "_DatabaseTab"):
        monkeypatch.setattr(settings_panel, name, _PlainTab)
    panel = settings_panel.SettingsPanel(svc)  # type: ignore[arg-type]
    buttons = panel._nav_group.buttons()
    names = [b.text() for b in buttons]
    assert panel._stack.count() == len(buttons) == 10
    assert panel._stack.currentIndex() == 0 and buttons[0].isChecked()

    buttons[names.index("Telegram")].click()

    assert panel._stack.currentIndex() == names.index("Telegram")
    assert not buttons[0].isChecked()


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
