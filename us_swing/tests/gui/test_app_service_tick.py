"""
Module: MD-GUI-004.001.M01 test cases (FO-GUI-012)
Parent SRD: SRD-GUI-012.001

Unit tests for AppService live tick streaming integration.
Covers SRD-GUI-012.001 through SRD-GUI-012.007.
"""
from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch, call

import pytest
from PyQt6.QtCore import QObject

from us_swing.data.models import (
    MarketWatchItem,
    OpenPosition,
    RiskConfig,
    WatchlistItem,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_open_position(symbol: str, current_price: float = 180.0) -> OpenPosition:
    return OpenPosition(
        symbol=symbol,
        user_id=1,
        quantity=10,
        average_price=170.0,
        stop_loss=160.0,
        target_price=200.0,
        mode="live",
        current_price=current_price,
        strategy_id="IBKR",
        filled_quantity=10,
        total_quantity=10,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def svc(qapp):
    """Minimal AppService with all side-effect entry points patched."""
    mock_net_watcher = MagicMock()
    mock_net_watcher.start = MagicMock()
    mock_net_watcher.status_changed = MagicMock()
    mock_net_watcher.status_changed.connect = MagicMock()

    with (
        patch("us_swing.gui.app_service.NetWatcher", return_value=mock_net_watcher),
        patch("us_swing.gui.app_service.load_users", return_value=[]),
        patch("us_swing.gui.app_service.load_system_config") as mock_cfg,
        patch("us_swing.gui.app_service.QTimer") as mock_qtimer_cls,
    ):
        from us_swing.gui.system_store import SystemConfig

        cfg = SystemConfig()
        cfg.ibkr_tick_client_id = 14
        mock_cfg.return_value = cfg

        # Build a QTimer mock that ignores start/stop/singleShot
        mock_timer_instance = MagicMock()
        mock_qtimer_cls.return_value = mock_timer_instance
        mock_qtimer_cls.singleShot = MagicMock()

        from us_swing.gui.app_service import AppService

        service = AppService()

        # Restore real _watch so we can manipulate it in tests
        service._watch = [MarketWatchItem("^GSPC", "S&P 500")]
        service._watch_prev_close = {}
        service._watchlist = []
        service._ibkr_positions = []
        service._tick_worker = None
        service._sp500_cache = set()
        service._sp500 = []

        yield service


@pytest.fixture()
def mock_tick_worker():
    """A MagicMock that mimics LiveTickWorker's public interface."""
    w = MagicMock()
    w.isRunning.return_value = True
    w.set_contracts = MagicMock()
    w.request_stop = MagicMock()
    w.quit = MagicMock()
    w.wait = MagicMock()
    w.tick_price = MagicMock()
    w.tick_price.disconnect = MagicMock()
    w.subscription_failed = MagicMock()
    w.subscription_failed.disconnect = MagicMock()
    return w


# ---------------------------------------------------------------------------
# SRD-GUI-012.001 — Worker lifecycle
# ---------------------------------------------------------------------------

class TestWorkerLifecycle:
    def test_on_connect_ok_creates_tick_worker(self, svc, mock_tick_worker):
        """UT-GUI-012.001.M01.T01: _on_connect_ok creates LiveTickWorker with clientId=14."""
        # LiveTickWorker is imported locally inside _on_connect_ok; patch via its source module.
        with patch(
            "us_swing.execution.live_tick_worker.LiveTickWorker",
            return_value=mock_tick_worker,
        ) as mock_cls:
            # Suppress side-effects called inside _on_connect_ok
            with (
                patch.object(svc, "_set_status"),
                patch.object(svc, "_acct_timer"),
                patch.object(svc, "_refresh_account_data"),
                patch.object(svc, "_fetch_mw_prev_close_once"),
                patch.object(svc, "_sync_tick_subscriptions"),
                patch.object(svc, "_refresh_watchlist"),
            ):
                svc._on_connect_ok()

        assert svc._tick_worker is not None
        mock_cls.assert_called_once()
        _, kwargs = mock_cls.call_args
        assert kwargs["client_id"] == 14

    def test_disconnect_feed_stops_worker(self, svc, mock_tick_worker):
        """UT-GUI-012.001.M01.T02: disconnect_feed calls request_stop and clears _tick_worker."""
        svc._tick_worker = mock_tick_worker

        with (
            patch.object(svc, "_set_status"),
            patch.object(svc, "_acct_timer"),
        ):
            svc.disconnect_feed()

        assert mock_tick_worker.request_stop.called
        assert svc._tick_worker is None

    def test_on_connect_ok_twice_creates_worker_once(self, svc, mock_tick_worker):
        """UT-GUI-012.001.M01.T03: _on_connect_ok while worker isRunning skips second construction."""
        with patch(
            "us_swing.execution.live_tick_worker.LiveTickWorker",
            return_value=mock_tick_worker,
        ) as mock_cls:
            with (
                patch.object(svc, "_set_status"),
                patch.object(svc, "_acct_timer"),
                patch.object(svc, "_refresh_account_data"),
                patch.object(svc, "_fetch_mw_prev_close_once"),
                patch.object(svc, "_sync_tick_subscriptions"),
                patch.object(svc, "_refresh_watchlist"),
            ):
                svc._on_connect_ok()  # first call — creates worker
                # Simulate worker is running; second call should NOT create another
                svc._on_connect_ok()

        mock_cls.assert_called_once()

    def test_disconnect_feed_no_worker_no_exception(self, svc):
        """UT-GUI-012.001.M01.T19: disconnect_feed with no worker emits market_watch_updated."""
        assert svc._tick_worker is None
        emitted: list[bool] = []
        svc.market_watch_updated.connect(lambda: emitted.append(True))

        with (
            patch.object(svc, "_set_status"),
            patch.object(svc, "_acct_timer"),
        ):
            svc.disconnect_feed()  # must not raise

        assert emitted, "market_watch_updated was not emitted"


# ---------------------------------------------------------------------------
# SRD-GUI-012.002 — Symbol translation
# ---------------------------------------------------------------------------

class TestSymbolTranslation:
    def test_sync_translates_gspc_to_ibkr_index(self, svc, mock_tick_worker):
        """UT-GUI-012.002.M01.T04: ^GSPC maps to Index contract with symbol SPX, exchange CBOE."""
        svc._tick_worker = mock_tick_worker
        svc._watch = [MarketWatchItem("^GSPC", "S&P 500")]

        mock_ind = MagicMock()
        mock_ind.symbol = "SPX"
        mock_ind.exchange = "CBOE"

        with patch("us_swing.gui.app_service._make_ind_contract", return_value=mock_ind):
            svc._sync_tick_subscriptions()

        mock_tick_worker.set_contracts.assert_called_once()
        contracts: dict[str, Any] = mock_tick_worker.set_contracts.call_args[0][0]
        assert "^GSPC" in contracts
        contract = contracts["^GSPC"]
        assert contract.symbol == "SPX"
        assert contract.exchange == "CBOE"

    def test_sync_skips_unknown_yahoo_symbol(self, svc, mock_tick_worker):
        """UT-GUI-012.002.M01.T05: ^CUSTOM not in _YAHOO_TO_IBKR is excluded from contracts."""
        svc._tick_worker = mock_tick_worker
        svc._watch = [MarketWatchItem("^CUSTOM", "Custom")]

        svc._sync_tick_subscriptions()

        mock_tick_worker.set_contracts.assert_called_once()
        contracts: dict[str, Any] = mock_tick_worker.set_contracts.call_args[0][0]
        assert "^CUSTOM" not in contracts


# ---------------------------------------------------------------------------
# SRD-GUI-012.003 — Market Watch tick slot
# ---------------------------------------------------------------------------

class TestMarketWatchTick:
    def test_on_mktwatch_tick_updates_ltp_and_change_pct(self, svc):
        """UT-GUI-012.003.M01.T06: tick updates ltp and computes change_pct when prev_close set."""
        svc._watch = [MarketWatchItem("^GSPC", "S&P 500")]
        svc._watch_prev_close = {"^GSPC": 5100.0}
        emitted: list[bool] = []
        svc.market_watch_updated.connect(lambda: emitted.append(True))

        svc._on_mktwatch_tick("^GSPC", 5200.0)

        item = svc._watch[0]
        assert item.ltp == 5200.0
        assert item.change_pct == pytest.approx((5200.0 - 5100.0) / 5100.0 * 100, rel=1e-3)
        assert emitted

    def test_on_mktwatch_tick_no_prev_close_sets_none(self, svc):
        """UT-GUI-012.003.M01.T07: tick with empty prev_close dict sets change_pct=None."""
        svc._watch = [MarketWatchItem("^GSPC", "S&P 500")]
        svc._watch_prev_close = {}
        emitted: list[bool] = []
        svc.market_watch_updated.connect(lambda: emitted.append(True))

        svc._on_mktwatch_tick("^GSPC", 5200.0)

        item = svc._watch[0]
        assert item.ltp == 5200.0
        assert item.change_pct is None
        assert emitted

    def test_on_mktwatch_tick_unknown_tag_no_emit(self, svc):
        """UT-GUI-012.003.M01.T08: tick for unknown tag does not emit market_watch_updated."""
        svc._watch = [MarketWatchItem("^GSPC", "S&P 500")]
        emitted: list[bool] = []
        svc.market_watch_updated.connect(lambda: emitted.append(True))

        svc._on_mktwatch_tick("UNKNOWN_TAG", 100.0)

        assert not emitted


# ---------------------------------------------------------------------------
# SRD-GUI-012.004 — Watchlist tick slot
# ---------------------------------------------------------------------------

class TestWatchlistTick:
    def test_on_watchlist_tick_updates_item(self, svc):
        """UT-GUI-012.004.M01.T09: watchlist tick updates ltp, change, change_pct and emits."""
        item = WatchlistItem(symbol="AAPL", prev_close=175.0)
        svc._watchlist = [item]
        emitted: list[bool] = []
        svc.watchlist_updated.connect(lambda: emitted.append(True))

        svc._on_watchlist_tick("AAPL", 180.0)

        assert item.ltp == 180.0
        assert item.change == pytest.approx(5.0)
        assert item.change_pct == pytest.approx(5.0 / 175.0 * 100, rel=1e-3)
        assert emitted

    def test_sync_excludes_non_sp500_watchlist_symbol(self, svc, mock_tick_worker):
        """UT-GUI-012.004.M01.T10: _sync_tick_subscriptions excludes watchlist symbol not in S&P 500."""
        svc._tick_worker = mock_tick_worker
        svc._watch = []  # no MW indices to keep contract set focused
        svc._sp500_cache = {"AAPL"}
        svc._watchlist = [
            WatchlistItem(symbol="AAPL"),
            WatchlistItem(symbol="NOTSP"),
        ]

        mock_stk = MagicMock()
        with patch("us_swing.gui.app_service._make_stk_contract", return_value=mock_stk):
            svc._sync_tick_subscriptions()

        contracts: dict[str, Any] = mock_tick_worker.set_contracts.call_args[0][0]
        assert "AAPL" in contracts
        assert "NOTSP" not in contracts


# ---------------------------------------------------------------------------
# SRD-GUI-012.005 — Position tick slot
# ---------------------------------------------------------------------------

class TestPositionTick:
    def test_on_position_tick_updates_price(self, svc):
        """UT-GUI-012.005.M01.T11: tick updates current_price on matching position and emits."""
        pos = _make_open_position("AAPL", current_price=180.0)
        svc._ibkr_positions = [pos]
        emitted: list[bool] = []
        svc.positions_updated.connect(lambda: emitted.append(True))

        svc._on_position_tick("AAPL", 185.0)

        assert pos.current_price == 185.0
        assert emitted

    def test_on_position_tick_no_positions_no_emit(self, svc):
        """UT-GUI-012.005.M01.T12: tick with empty positions list does not emit positions_updated."""
        svc._ibkr_positions = []
        emitted: list[bool] = []
        svc.positions_updated.connect(lambda: emitted.append(True))

        svc._on_position_tick("AAPL", 185.0)

        assert not emitted


# ---------------------------------------------------------------------------
# SRD-GUI-012.006 — Subscription sync
# ---------------------------------------------------------------------------

class TestSubscriptionSync:
    def test_sync_includes_mw_watchlist_and_positions(self, svc, mock_tick_worker):
        """UT-GUI-012.006.M01.T13: sync includes MW index, S&P 500 watchlist, and S&P 500 position."""
        svc._tick_worker = mock_tick_worker
        svc._watch = [MarketWatchItem("^GSPC", "S&P 500")]
        svc._sp500_cache = {"AAPL", "MSFT"}
        svc._watchlist = [WatchlistItem(symbol="AAPL")]
        svc._ibkr_positions = [_make_open_position("MSFT")]

        mock_ind = MagicMock()
        mock_stk = MagicMock()
        with (
            patch("us_swing.gui.app_service._make_ind_contract", return_value=mock_ind),
            patch("us_swing.gui.app_service._make_stk_contract", return_value=mock_stk),
        ):
            svc._sync_tick_subscriptions()

        contracts: dict[str, Any] = mock_tick_worker.set_contracts.call_args[0][0]
        assert "^GSPC" in contracts
        assert "AAPL" in contracts
        assert "MSFT" in contracts

    def test_sync_caps_at_95_trims_positions_logs_warning(self, svc, mock_tick_worker, caplog):
        """UT-GUI-012.006.M01.T14: 100-contract scenario caps at 95, warns, keeps MW and watchlist."""
        svc._tick_worker = mock_tick_worker

        # 3 MW indices (all in _YAHOO_TO_IBKR)
        mw_symbols = ["^GSPC", "^IXIC", "^DJI"]
        svc._watch = [MarketWatchItem(s, s) for s in mw_symbols]

        # 30 S&P 500 watchlist
        wl_symbols = [f"WL{i:02d}" for i in range(30)]
        svc._watchlist = [WatchlistItem(symbol=s) for s in wl_symbols]

        # 67 S&P 500 positions (3 MW + 30 WL + 67 positions = 100 > 95)
        pos_symbols = [f"PS{i:02d}" for i in range(67)]
        svc._ibkr_positions = [_make_open_position(s) for s in pos_symbols]

        all_sp500 = set(wl_symbols) | set(pos_symbols)
        svc._sp500_cache = all_sp500

        mock_ind = MagicMock()
        mock_stk = MagicMock()
        with (
            patch("us_swing.gui.app_service._make_ind_contract", return_value=mock_ind),
            patch("us_swing.gui.app_service._make_stk_contract", return_value=mock_stk),
            caplog.at_level(logging.WARNING, logger="us_swing.gui.app_service"),
        ):
            svc._sync_tick_subscriptions()

        contracts: dict[str, Any] = mock_tick_worker.set_contracts.call_args[0][0]
        assert len(contracts) <= 95
        for sym in mw_symbols:
            assert sym in contracts
        for sym in wl_symbols:
            assert sym in contracts
        assert any("cap" in r.message.lower() or "trim" in r.message.lower() for r in caplog.records)

    def test_sync_no_worker_no_set_contracts_call(self, svc):
        """UT-GUI-012.006.M01.T18: _sync_tick_subscriptions with no worker is a no-op."""
        svc._tick_worker = None
        # If _sync_tick_subscriptions calls set_contracts it will raise AttributeError
        svc._sync_tick_subscriptions()  # must not raise


# ---------------------------------------------------------------------------
# SRD-GUI-012.007 — Disconnect behavior
# ---------------------------------------------------------------------------

class TestDisconnectBehavior:
    def test_disconnect_clears_market_watch_ltp(self, svc, mock_tick_worker):
        """UT-GUI-012.007.M01.T15: disconnect_feed clears ltp on all MW items and emits."""
        items = [
            MarketWatchItem("^GSPC", "S&P 500", ltp=5200.0),
            MarketWatchItem("^IXIC", "NASDAQ",  ltp=18000.0),
            MarketWatchItem("^DJI",  "DJIA",    ltp=40000.0),
        ]
        svc._watch = items
        svc._tick_worker = mock_tick_worker
        emitted: list[bool] = []
        svc.market_watch_updated.connect(lambda: emitted.append(True))

        with (
            patch.object(svc, "_set_status"),
            patch.object(svc, "_acct_timer"),
        ):
            svc.disconnect_feed()

        for item in items:
            assert item.ltp is None
        assert emitted

    def test_disconnect_does_not_clear_position_price(self, svc, mock_tick_worker):
        """UT-GUI-012.007.M01.T16: disconnect_feed leaves position current_price unchanged."""
        pos = _make_open_position("AAPL", current_price=185.0)
        # Positions are cleared by disconnect_feed (_ibkr_positions = []);
        # the test verifies the price is NOT mutated before the list is replaced.
        svc._ibkr_positions = [pos]
        svc._tick_worker = mock_tick_worker

        with (
            patch.object(svc, "_set_status"),
            patch.object(svc, "_acct_timer"),
        ):
            svc.disconnect_feed()

        # The price on the original object must be untouched
        assert pos.current_price == 185.0

    def test_disconnect_does_not_clear_watchlist_ltp(self, svc, mock_tick_worker):
        """UT-GUI-012.007.M01.T17: disconnect_feed leaves watchlist item ltp unchanged."""
        item = WatchlistItem(symbol="AAPL", ltp=180.0)
        svc._watchlist = [item]
        svc._tick_worker = mock_tick_worker

        with (
            patch.object(svc, "_set_status"),
            patch.object(svc, "_acct_timer"),
        ):
            svc.disconnect_feed()

        assert item.ltp == 180.0


# ---------------------------------------------------------------------------
# Trade History rehydration — duplicate guard (FO-EXE-016)
# ---------------------------------------------------------------------------

def _make_closed_cycle_snapshot(symbol: str = "SATS", cycle_id: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        cycle_id=cycle_id,
        symbol=symbol,
        user_id=1,
        strategy_id="SUPERTREND",
        entry_order_id=f"buy-{cycle_id}",
        entry_qty=1,
        entry_price=113.84,
        entry_time="2026-06-08T09:30:00",
        exit_order_id=f"sell-{cycle_id}",
        exit_qty=1,
        exit_price=113.84,
        exit_time="2026-06-08T09:33:00",
        hard_stop_loss=110.0,
        target_price=120.0,
        current_price=113.84,
    )


class TestRehydrateDedup:
    def test_repeated_rehydrate_does_not_duplicate_trade_history(self, svc):
        """UT-EXE-016.001.M02.T01: rehydrate rebuilds Trade History instead of appending duplicates."""
        snap = _make_closed_cycle_snapshot()
        tc_query = MagicMock()
        tc_query.open_cycles.return_value = []
        tc_query.history.return_value = [snap]
        svc._tc_query = tc_query

        svc._rehydrate_positions_from_cycles()
        first = len(svc._trades)
        # Runs again on the next order event — must not accumulate.
        svc._rehydrate_positions_from_cycles()
        svc._rehydrate_positions_from_cycles()

        assert first == 2  # one BUY row + one SELL row for the closed cycle
        assert len(svc._trades) == first

    def test_repeated_rehydrate_does_not_duplicate_open_positions(self, svc):
        """UT-EXE-016.001.M02.T02: repeated rehydrate does not duplicate open positions."""
        snap = _make_closed_cycle_snapshot(symbol="V", cycle_id=2)
        tc_query = MagicMock()
        tc_query.open_cycles.return_value = [snap]
        tc_query.history.return_value = []
        svc._tc_query = tc_query

        svc._rehydrate_positions_from_cycles()
        svc._rehydrate_positions_from_cycles()

        assert len([p for p in svc._positions if p.symbol == "V"]) == 1


class TestFillConfirmedLog:
    def test_fill_confirmed_log_includes_symbol(self, svc):
        """UT-EXE-016.001.M02.T03: fill-confirmed log resolves and includes the stock symbol."""
        from us_swing.broker.broker import OrderEvent, OrderStatus

        snap = _make_closed_cycle_snapshot(symbol="SATS", cycle_id=1)  # exit_order_id="sell-1"
        tc_query = MagicMock()
        tc_query.open_cycles.return_value = []
        tc_query.history.return_value = [snap]
        svc._tc_query = tc_query

        messages: list[str] = []
        svc.log_message.connect(lambda _level, msg: messages.append(msg))

        event = OrderEvent(
            broker_order_id="sell-1",
            client_ref="r",
            status=OrderStatus.FILLED,
            filled_quantity=1,
            fill_price=113.84,
        )
        svc._on_order_event_gui(event)

        assert any("SATS" in m and "fill confirmed" in m for m in messages)

    def test_fill_confirmed_log_falls_back_when_symbol_unknown(self, svc):
        """UT-EXE-016.001.M02.T04: fill-confirmed log falls back gracefully for an unknown order id."""
        from us_swing.broker.broker import OrderEvent, OrderStatus

        tc_query = MagicMock()
        tc_query.open_cycles.return_value = []
        tc_query.history.return_value = []
        svc._tc_query = tc_query

        messages: list[str] = []
        svc.log_message.connect(lambda _level, msg: messages.append(msg))

        event = OrderEvent(
            broker_order_id="unknown-999",
            client_ref="r",
            status=OrderStatus.FILLED,
            filled_quantity=1,
            fill_price=67.91,
        )
        svc._on_order_event_gui(event)

        assert any("fill confirmed" in m for m in messages)
