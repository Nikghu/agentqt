"""Tests for the one-copy app lock (MD-EXE-015.007.M01)."""
from __future__ import annotations

import pytest

from us_swing.execution import app_lock
from us_swing.execution.app_lock import AppLock, OrderBlockedError


@pytest.fixture(autouse=True)
def _no_claim(monkeypatch):
    monkeypatch.setattr(app_lock, "_claimed", None)


def test_second_copy_cannot_take_lock(tmp_path):
    """UT-EXE-015.007.M01.T01: A second holder is refused until the first lets go."""
    path = tmp_path / "app.lock"
    first, second = AppLock(path), AppLock(path)
    assert first.acquire() and first.held
    assert second.acquire() is False and not second.held
    first.release()
    assert second.acquire() is True
    second.release()


def test_claim_fails_while_another_copy_holds_it(tmp_path):
    """UT-EXE-015.007.M01.T02: Claiming at start fails when another copy holds the lock."""
    path = tmp_path / "app.lock"
    other = AppLock(path)
    assert other.acquire()
    assert app_lock.claim_app_lock(path) is False
    assert app_lock._claimed is None
    other.release()
    assert app_lock.claim_app_lock(path) is True
    app_lock._claimed.release()  # type: ignore[union-attr]


def test_orders_allowed_while_lock_held(tmp_path):
    """UT-EXE-015.008.M01.T01: Orders pass when no lock is used or this copy holds it."""
    app_lock.check_order_allowed()
    assert app_lock.claim_app_lock(tmp_path / "app.lock")
    app_lock.check_order_allowed()
    app_lock._claimed.release()  # type: ignore[union-attr]


def test_order_blocked_when_lock_lost(tmp_path, caplog):
    """UT-EXE-015.008.M01.T02: Once the lock is lost the order is stopped with a plain error."""
    assert app_lock.claim_app_lock(tmp_path / "app.lock")
    app_lock._claimed.release()  # type: ignore[union-attr]
    with caplog.at_level("ERROR"), pytest.raises(OrderBlockedError):
        app_lock.check_order_allowed()
    assert "[Orders] Another USSwing is running — order not sent" in caplog.text
