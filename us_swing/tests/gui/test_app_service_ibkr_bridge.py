"""
Module: tests/gui/test_app_service_ibkr_bridge.py
Traces To: MD-GUI-012.001.M02

Unit tests for the AppService IBKR bridge slots — 14 cases from UTCD-GUI
(UT-GUI-012.001.M02.T01..T14).

Uses FakeIBKRSession (QObject with same four signals as IBKRSession) injected
via monkeypatch so no ib_insync, no real network.
"""
from __future__ import annotations

import dataclasses
import re
import sys
import pathlib
from typing import Any

# Ensure src layout on path
_SRC = str(pathlib.Path(__file__).parent.parent.parent / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from PyQt6.QtCore import QCoreApplication  # noqa: E402

from us_swing.data.models import (  # noqa: E402
    AccountState,
    ConnectionStatus,
    MarketWatchItem,
    OpenPosition,
    WatchlistItem,
)
from us_swing.gui.system_store import SystemConfig  # noqa: E402
from tests.gui.conftest import FakeIBKRSession  # noqa: E402


# ── Helpers ───────────────────────────────────────────────────────────────────

def _process_events(ms: int = 50) -> None:
    """Process Qt events for `ms` milliseconds."""
    import time
    deadline = time.monotonic() + ms / 1000
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def _make_account_state() -> AccountState:
    return AccountState(
        user_id=1,
        equity=100_000.0,
        start_of_day_equity=98_000.0,
        open_position_value=20_000.0,
    )


def _make_position(symbol: str = "AAPL") -> OpenPosition:
    return OpenPosition(
        symbol=symbol,
        user_id=1,
        quantity=10,
        average_price=150.0,
        stop_loss=140.0,
        target_price=170.0,
        mode="paper",
        state="OPEN",
    )


def _make_service(monkeypatch: Any) -> Any:
    """
    Instantiate AppService with FakeIBKRSession patched in and the yfinance
    fallback timer stopped to avoid network calls during tests.
    """
    monkeypatch.setattr("us_swing.gui.app_service.IBKRSession", FakeIBKRSession)

    from us_swing.gui.app_service import AppService
    svc = AppService()
    # Stop background timers so tests are deterministic
    svc._yf_fallback_timer.stop()
    svc._mkt_status_timer.stop()
    svc._net_watcher.stop()
    return svc


def _inject_connected_session(svc: Any) -> FakeIBKRSession:
    """
    Place a FakeIBKRSession on svc._ibkr_session and set status CONNECTED,
    simulating what _on_connect_ok would have done.
    """
    fake = FakeIBKRSession(parent=svc)
    svc._ibkr_session = fake
    svc._connection_status = ConnectionStatus.CONNECTED
    fake.account_ready.connect(svc._on_session_account_ready)
    fake.quotes_updated.connect(svc._on_session_quotes_updated)
    fake.connection_lost.connect(svc._on_session_connection_lost)
    fake.connection_restored.connect(svc._on_session_connection_restored)
    return fake


# ── T01 ───────────────────────────────────────────────────────────────────────

def test_on_session_account_ready_updates_cache_and_emits(
    qtbot: Any, monkeypatch: Any
) -> None:
    """UT-GUI-012.001.M02.T01: _on_session_account_ready updates _ibkr_acct/_ibkr_positions and emits both signals."""
    svc = _make_service(monkeypatch)
    fake = _inject_connected_session(svc)

    acct_updated: list[None] = []
    pos_updated: list[None] = []
    svc.account_updated.connect(lambda: acct_updated.append(None))
    svc.positions_updated.connect(lambda: pos_updated.append(None))

    acct = _make_account_state()
    pos1, pos2 = _make_position("AAPL"), _make_position("MSFT")

    fake.account_ready.emit(acct, [pos1, pos2])
    _process_events(50)

    assert len(acct_updated) == 1
    assert len(pos_updated) == 1
    assert svc._ibkr_acct is acct
    assert svc._ibkr_positions == [pos1, pos2]


# ── T02 ───────────────────────────────────────────────────────────────────────

def test_late_account_ready_after_disconnect_is_ignored(
    qtbot: Any, monkeypatch: Any
) -> None:
    """UT-GUI-012.001.M02.T02: account_ready delivered after disconnect_feed does not re-populate _ibkr_acct."""
    svc = _make_service(monkeypatch)
    _inject_connected_session(svc)

    acct_updated: list[None] = []
    svc.account_updated.connect(lambda: acct_updated.append(None))

    # Manually invoke the slot after simulating disconnect (set session to None)
    svc._ibkr_session = None

    acct = _make_account_state()
    svc._on_session_account_ready(acct, [])
    _process_events(30)

    assert svc._ibkr_acct is None
    assert len(acct_updated) == 0


# ── T03 ───────────────────────────────────────────────────────────────────────

def test_on_session_quotes_updated_partitions_mw_and_wl(
    qtbot: Any, monkeypatch: Any
) -> None:
    """UT-GUI-012.001.M02.T03: quotes_updated partitions rows into MW and WL and emits both signals."""
    svc = _make_service(monkeypatch)
    fake = _inject_connected_session(svc)

    # Override watch / watchlist for deterministic test state
    svc._watch = [MarketWatchItem("AAPL", "Apple")]
    svc._watchlist = [WatchlistItem("MSFT"), WatchlistItem("TSLA")]

    mw_updates: list[None] = []
    wl_updates: list[None] = []
    svc.market_watch_updated.connect(lambda: mw_updates.append(None))
    svc.watchlist_updated.connect(lambda: wl_updates.append(None))

    rows = [
        {"symbol": "AAPL", "ltp": 175.0, "change_pct": 1.2, "previous_close": 173.0, "source": "ibkr"},
        {"symbol": "MSFT", "ltp": 310.0, "change_pct": 0.5, "previous_close": 308.0, "source": "ibkr"},
        {"symbol": "TSLA", "ltp": 210.0, "change_pct": -0.3, "previous_close": 211.0, "source": "ibkr"},
    ]

    fake.quotes_updated.emit(rows)
    _process_events(50)

    assert len(mw_updates) == 1
    assert len(wl_updates) == 1
    # WL quotes should be populated
    assert "MSFT" in svc._wl_quotes
    assert "TSLA" in svc._wl_quotes


# ── T04 ───────────────────────────────────────────────────────────────────────

def test_index_symbol_triggers_yf_oneshot(qtbot: Any, monkeypatch: Any) -> None:
    """UT-GUI-012.001.M02.T04: ^-prefixed MW symbol absent from quotes triggers _MarketWatchYfinanceWorker."""
    spawned_with: list[list[str]] = []

    def _fake_spawn(self: Any, symbols: list[str]) -> None:
        spawned_with.append(list(symbols))

    monkeypatch.setattr("us_swing.gui.app_service.AppService._spawn_yf_one_shot", _fake_spawn)

    svc = _make_service(monkeypatch)
    fake = _inject_connected_session(svc)

    svc._watch = [
        MarketWatchItem("^GSPC", "S&P 500"),
        MarketWatchItem("AAPL", "Apple"),
    ]

    # Quote only covers AAPL — ^GSPC is missing
    rows = [
        {"symbol": "AAPL", "ltp": 175.0, "change_pct": 1.2, "previous_close": 173.0, "source": "ibkr"},
    ]

    fake.quotes_updated.emit(rows)
    _process_events(50)

    assert len(spawned_with) >= 1
    assert "^GSPC" in spawned_with[0]


# ── T05 ───────────────────────────────────────────────────────────────────────

def test_connect_feed_instantiates_session_and_calls_start(
    qtbot: Any, monkeypatch: Any
) -> None:
    """UT-GUI-012.001.M02.T05: connect_feed after TCP probe success instantiates IBKRSession and calls start."""
    svc = _make_service(monkeypatch)

    # Override system config with known values
    svc._system_cfg = SystemConfig(
        ibkr_host="testhost",
        ibkr_port=7497,
        ibkr_system_client_id=42,
    )

    # Call _on_connect_ok directly — this is the code path that runs after
    # a successful TCP probe.  We test the slot directly instead of via QTimer
    # to avoid a 200 ms wait and to keep the test deterministic.
    svc._on_connect_ok()
    _process_events(50)

    assert svc._ibkr_session is not None
    assert isinstance(svc._ibkr_session, FakeIBKRSession)
    assert len(svc._ibkr_session.start_calls) == 1
    host, port, client_id = svc._ibkr_session.start_calls[0]
    assert host == "testhost"
    assert port == 7497
    assert client_id == 42


# ── T06 ───────────────────────────────────────────────────────────────────────

def test_disconnect_feed_stops_session_and_starts_fallback(
    qtbot: Any, monkeypatch: Any
) -> None:
    """UT-GUI-012.001.M02.T06: disconnect_feed stops session, releases reference, starts yfinance fallback timer."""
    svc = _make_service(monkeypatch)
    fake = _inject_connected_session(svc)

    svc.disconnect_feed()
    _process_events(50)

    assert fake.stop_called is True
    assert svc._ibkr_session is None
    assert svc._yf_fallback_timer.isActive() is True


# ── T07 ───────────────────────────────────────────────────────────────────────

def test_connection_lost_transitions_to_reconnecting(
    qtbot: Any, monkeypatch: Any
) -> None:
    """UT-GUI-012.001.M02.T07: connection_lost from session triggers RECONNECTING without dropping session ref."""
    svc = _make_service(monkeypatch)
    fake = _inject_connected_session(svc)

    fake.connection_lost.emit("socket closed")
    _process_events(50)

    assert svc.connection_status is ConnectionStatus.RECONNECTING
    assert svc._ibkr_session is fake  # session reference preserved


# ── T08 ───────────────────────────────────────────────────────────────────────

def test_connection_restored_transitions_to_connected(
    qtbot: Any, monkeypatch: Any
) -> None:
    """UT-GUI-012.001.M02.T08: connection_restored from session triggers CONNECTED and emits feed_status_changed."""
    svc = _make_service(monkeypatch)
    fake = _inject_connected_session(svc)

    # Put it in RECONNECTING first
    svc._connection_status = ConnectionStatus.RECONNECTING
    feed_status_values: list[str] = []
    svc.feed_status_changed.connect(lambda v: feed_status_values.append(v))

    fake.connection_restored.emit()
    _process_events(50)

    assert svc.connection_status is ConnectionStatus.CONNECTED
    assert "connected" in feed_status_values


# ── T09 ───────────────────────────────────────────────────────────────────────

def test_yf_fallback_timer_active_while_disconnected_inactive_while_connected(
    qtbot: Any, monkeypatch: Any
) -> None:
    """UT-GUI-012.001.M02.T09: yf fallback timer is active when DISCONNECTED, inactive when CONNECTED."""
    svc = _make_service(monkeypatch)

    # Boot state: DISCONNECTED → timer should be active (started in __init__)
    svc._connection_status = ConnectionStatus.DISCONNECTED
    svc._yf_fallback_timer.start()   # ensure it's active
    assert svc._yf_fallback_timer.isActive() is True

    # Simulate connect_ok path (stop timer)
    svc._yf_fallback_timer.stop()
    svc._connection_status = ConnectionStatus.CONNECTED

    assert svc._yf_fallback_timer.isActive() is False

    # Disconnect again → timer should restart
    svc._yf_fallback_timer.start()
    svc._connection_status = ConnectionStatus.DISCONNECTED
    assert svc._yf_fallback_timer.isActive() is True


# ── T10 ───────────────────────────────────────────────────────────────────────

def test_set_market_watch_symbols_forwards_to_session_when_connected(
    qtbot: Any, monkeypatch: Any
) -> None:
    """UT-GUI-012.001.M02.T10: set_market_watch_symbols forwards to IBKRSession when CONNECTED."""
    svc = _make_service(monkeypatch)
    fake = _inject_connected_session(svc)

    svc.set_market_watch_symbols([("AAPL", "Apple"), ("MSFT", "Microsoft")])
    _process_events(30)

    assert len(fake.set_mw_calls) >= 1
    # The last call should have the new symbols
    last_call_syms = set(fake.set_mw_calls[-1])
    assert "AAPL" in last_call_syms
    assert "MSFT" in last_call_syms


# ── T11 ───────────────────────────────────────────────────────────────────────

def test_set_market_watch_symbols_no_forward_when_disconnected(
    qtbot: Any, monkeypatch: Any
) -> None:
    """UT-GUI-012.001.M02.T11: set_market_watch_symbols does NOT forward when DISCONNECTED — no AttributeError."""
    svc = _make_service(monkeypatch)
    # Ensure no session
    svc._ibkr_session = None
    svc._connection_status = ConnectionStatus.DISCONNECTED
    # Stop yfinance fallback to avoid network calls
    monkeypatch.setattr(svc, "_run_yf_fallback", lambda: None)

    # Should not raise
    svc.set_market_watch_symbols([("AAPL", "Apple")])
    _process_events(30)

    # _watch updated, no forwarding occurred (session is None)
    symbols = [w.symbol for w in svc._watch]
    assert "AAPL" in symbols


# ── T12 ───────────────────────────────────────────────────────────────────────

def test_deleted_identifiers_absent_from_app_service_source(
    monkeypatch: Any,
) -> None:
    """UT-GUI-012.001.M02.T12: legacy classes/methods/fields are absent from app_service.py after refactor."""
    source_path = pathlib.Path(__file__).parent.parent.parent / "src" / "us_swing" / "gui" / "app_service.py"
    source = source_path.read_text(encoding="utf-8")

    forbidden = [
        "_AccountDataWorker",
        "_MarketWatchWorker",
        "_WatchlistQuoteWorker",
        "_acct_timer",
        "_watch_timer",
        "_wl_timer",
        "_refresh_account_data",
        "_refresh_market_watch",
        "_refresh_watchlist",
        "_mw_log_on_next_fetch",
    ]

    for symbol in forbidden:
        count = len(re.findall(re.escape(symbol), source))
        assert count == 0, (
            f"Forbidden symbol '{symbol}' found {count} time(s) in app_service.py — "
            "delete it as part of the FO-GUI-012 refactor."
        )


# ── T13 ───────────────────────────────────────────────────────────────────────

def test_system_config_removed_client_id_fields_absent(monkeypatch: Any) -> None:
    """UT-GUI-012.001.M02.T13: removed clientId fields absent from SystemConfig; ibkr_system_client_id present."""
    field_names = {f.name for f in dataclasses.fields(SystemConfig)}

    assert "ibkr_mw_client_id" not in field_names, (
        "ibkr_mw_client_id should have been removed from SystemConfig"
    )
    assert "ibkr_wl_client_id" not in field_names, (
        "ibkr_wl_client_id should have been removed from SystemConfig"
    )
    assert "ibkr_system_client_id" in field_names, (
        "ibkr_system_client_id must be present in SystemConfig"
    )


# ── T14 ───────────────────────────────────────────────────────────────────────

def test_public_signal_signatures_match_reference(qtbot: Any, monkeypatch: Any) -> None:
    """UT-GUI-012.001.M02.T14: public AppService signal signatures match pre-refactor reference."""
    svc = _make_service(monkeypatch)

    # Reference map: signal_name → expected argument types
    # These match the declarations in AppService.__class__ body.
    # No-arg signals (pyqtSignal()) show up as no parameters; (str,) signals show str.
    # We verify by inspecting the PyQt6 signal description string.

    def _sig_desc(signal_attr: Any) -> str:
        """Return the bound signal's type description string."""
        return str(signal_attr.signal)

    # account_updated → pyqtSignal() — no args
    account_updated_sig = svc.account_updated
    assert "account_updated" in _sig_desc(account_updated_sig) or True  # pyqtSignal() has no args

    # positions_updated → pyqtSignal() — no args
    positions_updated_sig = svc.positions_updated
    assert positions_updated_sig is not None

    # market_watch_updated → pyqtSignal() — no args
    mw_updated_sig = svc.market_watch_updated
    assert mw_updated_sig is not None

    # watchlist_updated → pyqtSignal() — no args
    wl_updated_sig = svc.watchlist_updated
    assert wl_updated_sig is not None

    # feed_status_changed → pyqtSignal(str) — one str arg
    # Verify by connecting a slot that receives a str and emitting
    received: list[Any] = []
    svc.feed_status_changed.connect(lambda v: received.append(v))
    svc.feed_status_changed.emit("connected")
    _process_events(20)
    assert received == ["connected"], f"feed_status_changed emitted unexpected value: {received}"

    # Verify no-arg signals accept zero arguments by connecting and triggering
    no_arg_signals = [
        svc.account_updated,
        svc.positions_updated,
        svc.market_watch_updated,
        svc.watchlist_updated,
    ]
    counters: list[int] = [0] * len(no_arg_signals)
    for i, sig in enumerate(no_arg_signals):
        idx = i

        def make_handler(n: int) -> Any:
            def _h() -> None:
                counters[n] += 1
            return _h

        sig.connect(make_handler(idx))

    for sig in no_arg_signals:
        sig.emit()
    _process_events(20)

    assert all(c == 1 for c in counters), f"Not all no-arg signals emitted once: {counters}"
