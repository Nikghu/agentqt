"""
Tests for scheduler_store auto-close config.
Module under test: MD-GUI-000.003 — scheduler_store.py
"""
from __future__ import annotations

from pathlib import Path

import pytest

from us_swing.gui import scheduler_store as ss
from us_swing.gui.scheduler_store import CloseConfig, USSwingConfig


@pytest.fixture
def temp_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    store = tmp_path / "scheduler.json"
    monkeypatch.setattr(ss, "_APP_DIR", tmp_path)
    monkeypatch.setattr(ss, "_STORE_FILE", store)
    return store


def test_load_close_config_default(temp_store: Path) -> None:
    """UT-GUI-000.003.T01: Missing close section returns disabled default."""
    cfg = ss.load_close_config()
    assert cfg.enabled is False
    assert cfg.close_time == "16:30"


def test_save_and_load_close_config(temp_store: Path) -> None:
    """UT-GUI-000.003.T02: Saved close config round-trips through JSON."""
    ss.save_close_config(CloseConfig(enabled=True, close_time="23:00"))
    cfg = ss.load_close_config()
    assert cfg.enabled is True
    assert cfg.close_time == "23:00"


def test_delete_close_config(temp_store: Path) -> None:
    """UT-GUI-000.003.T03: Delete removes the close section, reverting to default."""
    ss.save_close_config(CloseConfig(enabled=True, close_time="23:00"))
    ss.delete_close_config()
    cfg = ss.load_close_config()
    assert cfg.enabled is False


def test_close_config_isolated_from_usswing(temp_store: Path) -> None:
    """UT-GUI-000.003.T04: Saving close config leaves the usswing section intact."""
    ss.save_usswing_config(USSwingConfig(task_name="X_App"))
    ss.save_close_config(CloseConfig(enabled=True, close_time="22:15"))
    assert ss.load_usswing_config().task_name == "X_App"  # type: ignore[union-attr]
    assert ss.load_close_config().close_time == "22:15"
