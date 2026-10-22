"""
Module: MD-GUI-006.001.M01 — tests (ISS-GUI-0005)
Parent SRD: SRD-GUI-006.002

Editing a user must keep the fields the dialog does not show. The dialog used
to rebuild the profile from scratch, which reset Telegram settings on every edit.
"""
from __future__ import annotations

import sys
import types
from typing import Any
from unittest.mock import MagicMock

# QWebEngineWidgets DLL is unavailable in the test environment — stub it so
# settings_panel.py can be imported without the DLL.
_web_stub = types.ModuleType("PyQt6.QtWebEngineWidgets")
_web_stub.QWebEngineView = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("PyQt6.QtWebEngineWidgets", _web_stub)

from us_swing.data.models import RiskConfig, UserProfile  # noqa: E402
from us_swing.gui.settings_panel import _UserDialog  # noqa: E402


def _user() -> UserProfile:
    return UserProfile(
        user_id=1, username="trader", display_name="Trader", ibkr_client_id=101,
        mode="paper", risk_config=RiskConfig(), strategy_config={"k": 1},
        screener_config={"s": 2}, telegram_enabled=True, telegram_chat_id="12345",
        notify_tool_started=False, notify_screener_approved=True, notify_day_end_pnl=False,
    )


def test_edit_keeps_hidden_fields(qapp: Any) -> None:
    """UT-GUI-006.001.M01.T17: Telegram, notify and config fields survive an edit."""
    dlg = _UserDialog(_user())
    dlg._display.setText("New Name")

    profile = dlg.get_profile()

    assert profile.display_name == "New Name"
    assert (profile.telegram_enabled, profile.telegram_chat_id) == (True, "12345")
    assert (profile.notify_tool_started, profile.notify_day_end_pnl) == (False, False)
    assert (profile.strategy_config, profile.screener_config) == ({"k": 1}, {"s": 2})
    assert profile.user_id == 1


def test_new_user_gets_defaults(qapp: Any) -> None:
    """UT-GUI-006.001.M01.T18: a new user starts with Telegram off and id -1."""
    dlg = _UserDialog(None)
    dlg._username.setText("bob")

    profile = dlg.get_profile()

    assert profile.user_id == -1
    assert profile.username == "bob"
    assert (profile.telegram_enabled, profile.telegram_chat_id) == (False, "")
