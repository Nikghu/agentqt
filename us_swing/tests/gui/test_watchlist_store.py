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
from unittest.mock import MagicMock, patch

import pytest

_web_stub = types.ModuleType("PyQt6.QtWebEngineWidgets")
_web_stub.QWebEngineView = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("PyQt6.QtWebEngineWidgets", _web_stub)

from us_swing.data.models import ConnectionStatus, WatchlistItem  # noqa: E402
from us_swing.gui import watchlist_store  # noqa: E402
from us_swing.gui.app_service import AppService  # noqa: E402
from us_swing.gui.watchlist_store import MARKET_WATCH  # noqa: E402


@pytest.fixture(autouse=True)
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(watchlist_store, "_STORE_DIR", tmp_path)
    return tmp_path


def _svc(saved: list[str] | None = None) -> Any:
    svc = SimpleNamespace(
        _active_uid=1,
        _watchlist=[],
        _market_list=[],
        _connection_status=ConnectionStatus.DISCONNECTED,
        watchlist_updated=SimpleNamespace(emit=lambda: None),
        market_list_updated=SimpleNamespace(emit=lambda: None),
    )
    if saved is not None:
        watchlist_store.save_watchlist("1", saved)
    svc._load_saved_watchlist = lambda: AppService._load_saved_watchlist(svc)
    svc._save_watchlist = lambda: AppService._save_watchlist(svc)
    svc._save_market_list = lambda: AppService._save_market_list(svc)
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


def test_market_list_survives_restart_and_is_separate() -> None:
    """UT-GUI-025.020.M05.T01: the Market Watch list is saved on its own and back after a restart."""
    svc = _svc(["AAPL"])
    AppService.add_to_market_list(svc, " pltr ")

    restarted = _svc()
    AppService._load_saved_watchlist(restarted)
    AppService._load_saved_market_list(restarted)

    assert [w.symbol for w in restarted._market_list] == ["PLTR"]
    assert _symbols(restarted) == ["AAPL"]


def test_market_list_remove_survives_restart() -> None:
    """UT-GUI-025.020.M05.T02: a stock removed from Market Watch stays removed after a restart."""
    watchlist_store.save_watchlist("1", ["TSLA", "PLTR"], MARKET_WATCH)
    svc = _svc()
    AppService._load_saved_market_list(svc)

    AppService.remove_from_market_list(svc, "TSLA")

    assert watchlist_store.load_watchlist("1", MARKET_WATCH) == ["PLTR"]
    assert watchlist_store.load_watchlist("1") == []


def test_market_list_starts_empty_with_saved_watchlist() -> None:
    """UT-GUI-025.020.M05.T03: Market Watch starts empty; the watchlist is not copied into it."""
    svc = _svc(["AAPL", "NVDA"])
    AppService._load_saved_market_list(svc)

    assert svc._market_list == []


def test_tick_updates_both_lists() -> None:
    """UT-GUI-025.020.M01.T01: a tick for a stock in both lists updates both and both redraw."""
    emitted: list[str] = []
    svc = _svc()
    svc._mw_items = []
    svc._watchlist = [WatchlistItem(symbol="AAPL", prev_close=100.0)]
    svc._market_list = [WatchlistItem(symbol="AAPL", prev_close=100.0)]
    svc.watchlist_updated = SimpleNamespace(emit=lambda: emitted.append("wl"))
    svc.market_list_updated = SimpleNamespace(emit=lambda: emitted.append("mw"))

    AppService._on_watchlist_tick(svc, "AAPL", 110.0)

    assert svc._watchlist[0].ltp == 110.0 and svc._market_list[0].change_pct == 10.0
    assert emitted == ["wl", "mw"]


def test_market_list_subscribed_without_sp500_gate() -> None:
    """UT-GUI-025.020.M01.T02: a non-S&P 500 Market Watch stock gets live ticks."""
    sent: dict[str, Any] = {}
    svc = _svc()
    svc._tick_worker = SimpleNamespace(set_contracts=sent.update)
    svc._mw_items = []
    svc._cycle_symbols = set()
    svc._pending_store = SimpleNamespace(list=lambda: [])
    svc._sp500_cache = {"AAPL"}
    svc._sp500 = []
    svc._ibkr_positions = []
    svc._market_list = [WatchlistItem(symbol="PLTR")]
    svc._watchlist = [WatchlistItem(symbol="ZZZZ")]

    with patch("us_swing.gui.app_service._make_stk_contract", side_effect=lambda s: s):
        AppService._sync_tick_subscriptions(svc)

    assert set(sent) == {"PLTR"}


def test_refresh_keeps_running_fetch_alive(qtbot: Any) -> None:
    """UT-GUI-025.020.M01.T03: a second refresh while one runs keeps both fetches alive."""
    from PyQt6.QtCore import QObject

    from us_swing.gui import app_service

    owner = QObject()
    owner._market_list = [WatchlistItem(symbol="PLTR")]  # type: ignore[attr-defined]
    owner._on_market_list_data = lambda _r: None  # type: ignore[attr-defined]
    with patch.object(app_service._WatchlistQuoteWorker, "run", lambda self: self.msleep(200)):
        AppService._refresh_market_list(owner)  # type: ignore[arg-type]
        first = owner._ml_worker  # type: ignore[attr-defined]

        AppService._refresh_market_list(owner)  # type: ignore[arg-type]
        second = owner._ml_worker  # type: ignore[attr-defined]
        assert first is not second and first.parent() is owner and second.parent() is owner
        with qtbot.waitSignals([first.finished, second.finished], timeout=3000):
            pass
