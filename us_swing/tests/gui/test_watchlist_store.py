"""
Module: MD-GUI-025.019.M05 — tests
Parent SRD: SRD-GUI-025.019

Watchlist: stocks added by hand persist per user and come back after a restart.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

_web_stub = types.ModuleType("PyQt6.QtWebEngineWidgets")
_web_stub.QWebEngineView = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("PyQt6.QtWebEngineWidgets", _web_stub)

from us_swing.data.models import ConnectionStatus  # noqa: E402
from us_swing.gui import watchlist_store  # noqa: E402
from us_swing.gui.app_service import AppService  # noqa: E402


@pytest.fixture(autouse=True)
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(watchlist_store, "_STORE_FILE", tmp_path / "watchlist.json")
    return tmp_path


def _svc(saved: list[str] | None = None) -> Any:
    svc = SimpleNamespace(
        _active_uid=1,
        _watchlist=[],
        _connection_status=ConnectionStatus.DISCONNECTED,
        watchlist_updated=SimpleNamespace(emit=lambda: None),
    )
    if saved is not None:
        watchlist_store.save_watchlist("1", saved)
    svc._load_saved_watchlist = lambda: AppService._load_saved_watchlist(svc)
    svc._save_watchlist = lambda: AppService._save_watchlist(svc)
    return svc


def _symbols(svc: Any) -> list[str]:
    return [w.symbol for w in svc._watchlist]


def test_add_survives_restart() -> None:
    """UT-GUI-025.019.M05.T01: a stock added to the watchlist is back after a restart."""
    svc = _svc()
    AppService.add_to_watchlist(svc, " tsla ")
    AppService.add_to_watchlist(svc, "AAPL")

    restarted = _svc()
    AppService._load_saved_watchlist(restarted)

    assert _symbols(restarted) == ["TSLA", "AAPL"]


def test_remove_survives_restart() -> None:
    """UT-GUI-025.019.M05.T02: a stock removed from the watchlist stays removed after a restart."""
    svc = _svc(["TSLA", "AAPL"])
    AppService._load_saved_watchlist(svc)

    AppService.remove_from_watchlist(svc, "TSLA")

    restarted = _svc()
    AppService._load_saved_watchlist(restarted)
    assert _symbols(restarted) == ["AAPL"]


def test_duplicate_add_saved_once() -> None:
    """UT-GUI-025.019.M05.T03: adding the same stock twice saves it once."""
    svc = _svc()
    AppService.add_to_watchlist(svc, "TSLA")
    AppService.add_to_watchlist(svc, "tsla")

    assert watchlist_store.load_watchlist("1") == ["TSLA"]


def test_missing_file_gives_empty_watchlist() -> None:
    """UT-GUI-025.019.M05.T04: no saved file means an empty watchlist and no crash."""
    svc = _svc()
    AppService._load_saved_watchlist(svc)

    assert svc._watchlist == []


def test_broken_file_gives_empty_watchlist(home: Path) -> None:
    """UT-GUI-025.019.M05.T05: a corrupt file means an empty watchlist and no crash."""
    (home / "watchlist.json").write_text("{not json", encoding="utf-8")

    assert watchlist_store.load_watchlist("1") == []


def test_users_keep_separate_watchlists() -> None:
    """UT-GUI-025.019.M05.T06: each user sees only their own watchlist."""
    watchlist_store.save_watchlist("1", ["TSLA"])
    watchlist_store.save_watchlist("2", ["AAPL"])

    assert watchlist_store.load_watchlist("1") == ["TSLA"]
    assert watchlist_store.load_watchlist("2") == ["AAPL"]
