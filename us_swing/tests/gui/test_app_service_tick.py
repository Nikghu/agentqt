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
from PyQt6.QtCore import QObject, QTimer

from us_swing.gui import app_service

from us_swing.data.models import (
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
def svc(qapp, tmp_path):
    """Minimal AppService with all side-effect entry points patched; no real candles.db."""
    mock_net_watcher = MagicMock()
    mock_net_watcher.start = MagicMock()
    mock_net_watcher.status_changed = MagicMock()
    mock_net_watcher.status_changed.connect = MagicMock()

    with (
        patch("us_swing.gui.app_service.NetWatcher", return_value=mock_net_watcher),
        patch("us_swing.gui.app_service.load_users", return_value=[]),
        patch("us_swing.gui.app_service.load_system_config") as mock_cfg,
        patch("us_swing.gui.app_service.QTimer") as mock_qtimer_cls,
        patch("us_swing.gui.app_service._CANDLE_DB_PATH", tmp_path / "candles.db"),
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
        # Market Watch is now four ETFs held as WatchlistItem rows on _mw_items,
        # not Yahoo index symbols on _watch.
        service._mw_items = [WatchlistItem(symbol="SPY")]
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
                patch.object(svc, "_refresh_mw_quotes"),
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
                patch.object(svc, "_refresh_mw_quotes"),
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
    """Market Watch tracks four ETFs as ordinary stock contracts.

    The old Yahoo-index mapping (^GSPC → SPX on CBOE) is gone: index contracts
    need a market-data subscription most accounts lack, so SPY/QQQ/DIA/IWM are
    used instead and go through the same `_make_stk_contract` path as any stock.
    """

    def test_sync_subscribes_market_watch_etfs(self, svc, mock_tick_worker):
        """UT-GUI-012.002.M01.T04: Market Watch symbols are subscribed as stock contracts."""
        svc._tick_worker = mock_tick_worker
        svc._mw_items = [WatchlistItem(symbol="SPY"), WatchlistItem(symbol="QQQ")]

        svc._sync_tick_subscriptions()

        mock_tick_worker.set_contracts.assert_called_once()
        contracts: dict[str, Any] = mock_tick_worker.set_contracts.call_args[0][0]
        assert {"SPY", "QQQ"} <= set(contracts)
        assert contracts["SPY"].symbol == "SPY"

    def test_sync_is_a_no_op_without_a_worker(self, svc):
        """UT-GUI-012.002.M01.T05: syncing before connect does nothing and does not raise."""
        svc._tick_worker = None

        svc._sync_tick_subscriptions()   # must not raise


# ---------------------------------------------------------------------------
# SRD-GUI-012.003 — Market Watch tick slot
# ---------------------------------------------------------------------------

class TestMarketWatchTick:
    """Market Watch ticks arrive through `_on_watchlist_tick`.

    The separate `_on_mktwatch_tick` slot was folded into it: both surfaces hold
    `WatchlistItem` rows and compute change the same way, off `item.prev_close`
    rather than a side dict.
    """

    def test_tick_updates_ltp_and_change_pct(self, svc):
        """UT-GUI-012.003.M01.T06: a tick sets ltp and computes change against prev_close."""
        item = WatchlistItem(symbol="SPY")
        item.prev_close = 500.0
        svc._mw_items = [item]
        emitted: list[bool] = []
        svc.market_watch_updated.connect(lambda: emitted.append(True))

        svc._on_watchlist_tick("SPY", 510.0)
        svc._flush_tick_refresh()

        assert item.ltp == 510.0
        assert item.change_pct == pytest.approx((510.0 - 500.0) / 500.0 * 100, rel=1e-3)
        assert emitted

    def test_tick_without_prev_close_leaves_change_unset(self, svc):
        """UT-GUI-012.003.M01.T07: with no prev_close the price still updates, change does not."""
        item = WatchlistItem(symbol="SPY")
        item.prev_close = 0.0
        svc._mw_items = [item]
        emitted: list[bool] = []
        svc.market_watch_updated.connect(lambda: emitted.append(True))

        svc._on_watchlist_tick("SPY", 510.0)
        svc._flush_tick_refresh()

        assert item.ltp == 510.0
        assert item.change_pct == 0.0, "change must stay at its default without a prev_close"
        assert emitted

    def test_unknown_tag_emits_nothing(self, svc):
        """UT-GUI-012.003.M01.T08: a tick for an untracked symbol updates nothing."""
        svc._mw_items = [WatchlistItem(symbol="SPY")]
        svc._watchlist = []
        emitted: list[bool] = []
        svc.market_watch_updated.connect(lambda: emitted.append(True))

        svc._on_watchlist_tick("UNKNOWN_TAG", 100.0)
        svc._flush_tick_refresh()

        assert emitted == []


# ---------------------------------------------------------------------------
# ISS-GUI-0024 — previous close: daily candle (up to date) → IBKR → Yahoo
# ---------------------------------------------------------------------------

def _write_candles(path: Any, rows: list[tuple[str, str, float]]) -> None:
    import sqlite3

    with sqlite3.connect(path) as conn:
        conn.execute("DROP TABLE IF EXISTS price_1d")
        conn.execute("CREATE TABLE price_1d (symbol TEXT, datetime TEXT, close REAL)")
        conn.executemany("INSERT INTO price_1d VALUES (?, ?, ?)", rows)
    conn.close()


def _prior_day() -> str:
    import datetime

    today = datetime.datetime.now(app_service._ET).date()
    return app_service._prior_session_day(today).isoformat()


class TestPreviousClose:
    def test_prior_session_day(self):
        """UT-GUI-012.003.M01.T09: prior day skips weekends and holidays; weekend uses Friday."""
        import datetime

        day = datetime.date
        assert app_service._prior_session_day(day(2026, 11, 25)) == day(2026, 11, 24)  # Wed
        assert app_service._prior_session_day(day(2026, 11, 23)) == day(2026, 11, 20)  # Mon
        assert app_service._prior_session_day(day(2026, 11, 28)) == day(2026, 11, 25)  # Sat
        assert app_service._prior_session_day(day(2026, 12, 28)) == day(2026, 12, 24)  # Xmas

    def test_up_to_date_candle_wins(self, svc):
        """UT-GUI-012.003.M01.T10: an up-to-date daily candle is the base, not IBKR or Yahoo."""
        _write_candles(app_service._CANDLE_DB_PATH, [("SPY", f"{_prior_day()} 00:00:00", 400.0)])
        svc._ibkr_prev["SPY"] = 410.0
        svc._yahoo_prev["SPY"] = 420.0

        svc._on_watchlist_tick("SPY", 404.0)

        item = svc._mw_items[0]
        assert item.prev_close == 400.0 and item.change_pct == pytest.approx(1.0)

    def test_stale_candle_uses_ibkr(self, svc):
        """UT-GUI-012.003.M01.T11: a candle older than the prior day is skipped for IBKR's close."""
        _write_candles(app_service._CANDLE_DB_PATH, [("SPY", "2020-01-02 00:00:00", 300.0)])
        svc._ibkr_prev["SPY"] = 400.0
        svc._yahoo_prev["SPY"] = 420.0

        svc._on_watchlist_tick("SPY", 404.0)

        assert svc._mw_items[0].change == pytest.approx(4.0)

    def test_no_candle_no_ibkr_uses_yahoo(self, svc):
        """UT-GUI-012.003.M01.T12: without a candle file or IBKR close, Yahoo's close is used."""
        svc._yahoo_prev["SPY"] = 400.0

        svc._on_watchlist_tick("SPY", 396.0)

        assert svc._mw_items[0].change_pct == pytest.approx(-1.0)

    def test_new_day_rereads_candles(self, svc):
        """UT-GUI-012.003.M01.T13: a stale day key re-reads candles; a stale close is not kept."""
        _write_candles(app_service._CANDLE_DB_PATH, [("SPY", f"{_prior_day()} 00:00:00", 400.0)])
        svc._candle_prev = {"SPY": 999.0}
        svc._candle_prev_day = None

        svc._on_watchlist_tick("SPY", 404.0)

        assert svc._mw_items[0].prev_close == 400.0

    def test_ibkr_close_signal_stored(self, svc):
        """UT-GUI-012.003.M01.T14: IBKR's previous-day close from the feed is kept per symbol."""
        svc._on_ibkr_prev_close("SPY", 401.5)

        assert svc._prev_close("SPY") == 401.5


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
        svc._flush_tick_refresh()

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
        svc._flush_tick_refresh()

        assert pos.current_price == 185.0
        assert emitted

    def test_on_position_tick_no_positions_no_emit(self, svc):
        """UT-GUI-012.005.M01.T12: tick with empty positions list does not emit positions_updated."""
        svc._ibkr_positions = []
        emitted: list[bool] = []
        svc.positions_updated.connect(lambda: emitted.append(True))

        svc._on_position_tick("AAPL", 185.0)
        svc._flush_tick_refresh()

        assert not emitted


# ---------------------------------------------------------------------------
# SRD-GUI-000.008 — Tick refresh batching
# ---------------------------------------------------------------------------

class TestTickBatching:
    def test_ticks_coalesce_into_one_refresh(self, svc, qtbot):
        """UT-GUI-000.008.M03.T01: many ticks in one interval give one refresh per view."""
        svc._tick_flush = QTimer(svc)  # the fixture mocks QTimer; this flush must really fire
        svc._tick_flush.setSingleShot(True)
        svc._tick_flush.setInterval(app_service._TICK_REFRESH_MS)
        svc._tick_flush.timeout.connect(svc._flush_tick_refresh)
        svc._ibkr_positions = [_make_open_position("AAPL", current_price=180.0)]
        svc._watchlist = [WatchlistItem(symbol="AAPL", prev_close=175.0)]
        emitted: list[str] = []
        svc.positions_updated.connect(lambda: emitted.append("positions"))
        svc.watchlist_updated.connect(lambda: emitted.append("watchlist"))

        for price in (181.0, 182.0, 183.0):
            svc._on_watchlist_tick("AAPL", price)
            svc._on_position_tick("AAPL", price)

        assert emitted == []
        with qtbot.waitSignal(svc.positions_updated, timeout=2000):
            pass
        assert emitted == ["watchlist", "positions"]
        assert svc._ibkr_positions[0].current_price == 183.0

        svc._on_position_tick("AAPL", 184.0)
        svc.disconnect_feed()   # a pending tick refresh is dropped, not emitted late
        assert not svc._tick_flush.isActive() and svc._tick_dirty == {}

    def test_refresh_interval_is_250_ms(self, svc):
        """UT-GUI-000.008.M03.T02: tick refreshes go out at most every 250 ms, once per burst."""
        svc._queue_tick_refresh("positions_updated")
        svc._queue_tick_refresh("positions_updated")

        assert app_service._TICK_REFRESH_MS == 250
        svc._tick_flush.setInterval.assert_any_call(250)
        svc._tick_flush.setSingleShot.assert_any_call(True)
        assert list(svc._tick_dirty) == ["positions_updated"]


# ---------------------------------------------------------------------------
# SRD-GUI-012.006 — Subscription sync
# ---------------------------------------------------------------------------

class TestSubscriptionSync:
    def test_sync_includes_mw_watchlist_and_positions(self, svc, mock_tick_worker):
        """UT-GUI-012.006.M01.T13: sync includes Market Watch, S&P 500 watchlist and position."""
        svc._tick_worker = mock_tick_worker
        svc._mw_items = [WatchlistItem(symbol="SPY")]
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
        assert "SPY" in contracts
        assert "AAPL" in contracts
        assert "MSFT" in contracts

    def test_sync_caps_at_95_trims_positions_logs_warning(self, svc, mock_tick_worker, caplog):
        """UT-GUI-012.006.M01.T14: 100 contracts cap at 95, warn, and keep Market Watch + watchlist."""
        svc._tick_worker = mock_tick_worker

        # 3 Market Watch ETFs
        mw_symbols = ["SPY", "QQQ", "DIA"]
        svc._mw_items = [WatchlistItem(symbol=s) for s in mw_symbols]

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
            WatchlistItem(symbol="SPY", ltp=5200.0),
            WatchlistItem(symbol="QQQ", ltp=18000.0),
            WatchlistItem(symbol="DIA", ltp=40000.0),
        ]
        svc._mw_items = items
        svc._tick_worker = mock_tick_worker
        emitted: list[bool] = []
        svc.market_watch_updated.connect(lambda: emitted.append(True))

        with (
            patch.object(svc, "_set_status"),
            patch.object(svc, "_acct_timer"),
        ):
            svc.disconnect_feed()

        for item in items:
            # WatchlistItem carries numeric defaults, so the panel renders "–"
            # from a zeroed row rather than from None.
            assert item.ltp == 0.0
            assert item.change_pct == 0.0
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
        direction="LONG",
    )


class TestRehydrateDedup:
    def test_repeated_rehydrate_does_not_duplicate_trade_history(self, svc):
        """UT-EXE-016.001.M02.T01: rehydrate rebuilds Trade History instead of appending duplicates."""
        snap = _make_closed_cycle_snapshot()
        tc_query = MagicMock()
        tc_query.open_cycles.return_value = []
        tc_query.history.return_value = [snap]
        svc._tc_query = tc_query
        svc._db = None  # keep the real trades ledger out of this cycle-only check

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


class TestTradeHistoryFromLedger:
    """ISS-GUI-0022: Trade History reads each order's real state from the trades ledger."""

    @staticmethod
    def _ledger(tmp_path):
        from us_swing.db.manager import DatabaseManager

        db = DatabaseManager(f"sqlite:///{(tmp_path / 'trades.db').as_posix()}")
        db.create_schema()
        return db

    @staticmethod
    def _order(trade_id: str, side: str, state: str, **over):
        import datetime as _dt

        from us_swing.data.models import TradeRecord

        kw = dict(trade_id=trade_id, user_id=1, symbol="SATS", side=side, quantity=1,
                  entry_price=113.0, mode="paper", strategy_id="SUPERTREND",
                  entry_time=_dt.datetime.now(), order_state=state)
        kw.update(over)
        return TradeRecord(**kw)

    def test_waiting_and_cancelled_orders_show_their_state(self, svc, tmp_path):
        """UT-GUI-002.005.M01.T04: A waiting order shows NEW and a cancelled one CANCELLED."""
        db = self._ledger(tmp_path)
        db.insert_trade(self._order("sell-9", "SELL", "NEW"))
        db.insert_trade(self._order("sell-8", "SELL", "CANCELLED"))
        svc._db = db
        svc._tc_query = MagicMock(**{"open_cycles.return_value": [],
                                     "history.return_value": []})

        svc._rehydrate_positions_from_cycles()

        assert {t.trade_id: t.order_state for t in svc._trades} == {
            "sell-9": "NEW", "sell-8": "CANCELLED"}

    def test_ledger_rows_replace_cycle_rows(self, svc, tmp_path):
        """UT-GUI-002.005.M01.T05: A filled exit shows once, with its fill price; older cycles still show."""
        db = self._ledger(tmp_path)
        db.insert_trade(self._order("buy-1", "BUY", "FILLED", filled_quantity=1))
        db.insert_trade(self._order("sell-1", "SELL", "FILLED", filled_quantity=1,
                                    exit_price=113.84))
        svc._db = db
        svc._tc_query = MagicMock(**{
            "open_cycles.return_value": [],
            "history.return_value": [_make_closed_cycle_snapshot(),
                                     _make_closed_cycle_snapshot("OLD", cycle_id=2)],
        })

        svc._rehydrate_positions_from_cycles()

        ids = sorted(t.trade_id for t in svc._trades)
        assert ids == ["buy-1", "buy-2", "sell-1", "sell-2"]
        sell = next(t for t in svc._trades if t.trade_id == "sell-1")
        assert sell.entry_price == 113.84


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
