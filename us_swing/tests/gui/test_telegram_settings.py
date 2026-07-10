"""Tests for Telegram notification settings persistence (FO-INF-010 wiring)."""
from __future__ import annotations

import sys
import types

import pytest

from us_swing.data.models import RiskConfig, UserProfile
from us_swing.gui import telegram_token_store, user_store


@pytest.fixture()
def fake_keyring(monkeypatch):
    """Inject an in-memory ``keyring`` module so tests never touch the real OS
    keychain and do not require keyring to be installed."""
    store: dict[tuple[str, str], str] = {}
    module = types.ModuleType("keyring")
    module.set_password = lambda s, u, p: store.__setitem__((s, u), p)  # type: ignore[attr-defined]
    module.get_password = lambda s, u: store.get((s, u))                # type: ignore[attr-defined]
    module.delete_password = lambda s, u: store.pop((s, u), None)       # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "keyring", module)
    return store


def test_token_save_and_load(fake_keyring):
    """UT-INF-010.001.M08.T01: a saved token round-trips per user."""
    telegram_token_store.save(7, "secret-token")
    assert telegram_token_store.load(7) == "secret-token"


def test_token_missing_returns_empty(fake_keyring):
    """UT-INF-010.001.M08.T02: an unset user's token loads as empty string."""
    assert telegram_token_store.load(999) == ""


def test_token_blank_deletes(fake_keyring):
    """UT-INF-010.001.M08.T03: saving a blank token clears the stored entry."""
    telegram_token_store.save(7, "secret-token")
    telegram_token_store.save(7, "")
    assert telegram_token_store.load(7) == ""


def _profile(**kw) -> UserProfile:
    base = dict(
        user_id=1,
        username="trader",
        display_name="Trader",
        ibkr_client_id=100,
        mode="paper",
        risk_config=RiskConfig(),
        strategy_config={},
        screener_config={},
    )
    base.update(kw)
    return UserProfile(**base)  # type: ignore[arg-type]


def test_user_store_roundtrips_telegram_fields():
    """UT-INF-010.001.M08.T04: telegram_enabled + chat_id survive save/load."""
    profile = _profile(telegram_enabled=True, telegram_chat_id="12345")
    restored = user_store._from_dict(user_store._to_dict(profile))
    assert restored.telegram_enabled is True
    assert restored.telegram_chat_id == "12345"


def test_user_store_defaults_when_absent():
    """UT-INF-010.001.M08.T05: legacy records without telegram fields default off."""
    legacy = {"user_id": 2, "username": "old", "ibkr_client_id": 101, "mode": "paper"}
    restored = user_store._from_dict(legacy)
    assert restored.telegram_enabled is False
    assert restored.telegram_chat_id == ""


def test_user_store_roundtrips_event_toggles():
    """UT-INF-010.001.M08.T06: per-event toggles survive save/load."""
    profile = _profile(
        notify_tool_started=False,
        notify_screener_approved=True,
        notify_day_end_pnl=False,
    )
    restored = user_store._from_dict(user_store._to_dict(profile))
    assert restored.notify_tool_started is False
    assert restored.notify_screener_approved is True
    assert restored.notify_day_end_pnl is False


def test_user_store_event_toggles_default_on_for_legacy():
    """UT-INF-010.001.M08.T07: legacy records without toggle fields default on."""
    legacy = {"user_id": 3, "username": "old", "ibkr_client_id": 102, "mode": "paper"}
    restored = user_store._from_dict(legacy)
    assert restored.notify_tool_started is True
    assert restored.notify_screener_approved is True
    assert restored.notify_day_end_pnl is True
