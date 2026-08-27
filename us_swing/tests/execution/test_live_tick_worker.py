"""
Module: MD-EXE-008.001.M01 test cases
Parent SRD: SRD-EXE-008.001
"""
from __future__ import annotations

import asyncio
import math
import sys
import threading
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest
from PyQt6.QtCore import QThread

import importlib
import types

# Import the module directly, bypassing the execution package __init__ to
# avoid a circular-import chain in us_swing.execution.__init__.
_spec = importlib.util.spec_from_file_location(
    "us_swing.execution.live_tick_worker",
    str(__import__("pathlib").Path(__file__).parent.parent.parent
        / "src" / "us_swing" / "execution" / "live_tick_worker.py"),
)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]
LiveTickWorker = _mod.LiveTickWorker


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_worker(host: str = "127.0.0.1", port: int = 7497, cid: int = 14) -> LiveTickWorker:
    return LiveTickWorker(host, port, cid)


def _make_contract(con_id: int = 123, symbol: str = "AAPL") -> MagicMock:
    c = MagicMock()
    c.conId = con_id
    c.symbol = symbol
    return c


def _make_ticker(con_id: int = 123, last: float = 150.0, close: float = 149.5,
                 req_id: int | None = 1, bid: float = float("nan")) -> MagicMock:
    ticker = MagicMock()
    ticker.last = last
    # IBKR reports an index level as bid, so it sits between last and close in
    # the fallback chain.  Must be a real number — a bare MagicMock reaches the
    # `price <= 0` comparison and raises.
    ticker.bid = bid
    ticker.close = close
    ticker.reqId = req_id
    ticker.contract = MagicMock()
    ticker.contract.conId = con_id
    return ticker


def _make_mock_ib(con_id: int = 123, req_id: int = 1) -> MagicMock:
    """Return a mock IB object whose reqMktData returns a sensible ticker."""
    ib = MagicMock()
    ticker = _make_ticker(con_id=con_id, req_id=req_id)
    ticker.contract.conId = con_id
    ib.reqMktData.return_value = ticker
    ib.isConnected.return_value = True
    return ib


# ---------------------------------------------------------------------------
# SRD-EXE-008.001 — Class structure
# ---------------------------------------------------------------------------

def test_worker_is_qthread_with_signals():
    """UT-EXE-008.001.M01.T01: LiveTickWorker is a QThread with required signals."""
    w = _make_worker()
    assert isinstance(w, QThread)
    assert hasattr(w, "tick_price")
    assert hasattr(w, "subscription_failed")


def test_on_pending_tickers_no_emit_without_tag_mapping():
    """UT-EXE-008.001.M01.T02: _on_pending_tickers with empty _tag_by_conid emits nothing."""
    w = _make_worker()
    # _tag_by_conid is empty; create a ticker that would normally produce a price
    ticker = _make_ticker(con_id=99, last=100.0, req_id=None)

    received: list[Any] = []
    w.tick_price.connect(lambda tag, price: received.append((tag, price)))

    w._on_pending_tickers({ticker})

    assert received == []


def test_no_gui_or_db_side_effects_on_import():
    """UT-EXE-008.001.M01.T16: Importing live_tick_worker does not pull in gui or db modules."""
    # The module is loaded via direct file spec to bypass package __init__.
    # Verify that it does not introduce GUI widget or database namespace imports
    # beyond what Qt itself already provides for QThread.
    # PyQt6.QtWidgets is NOT a dependency of live_tick_worker (only QtCore is used).
    # However, since conftest loads a QApplication via pytest-qt before this test,
    # QtWidgets may already be present. We therefore check the module's own imports
    # rather than sys.modules at large.
    import types as _types
    mod = _mod  # the directly-loaded module object
    # The module must NOT have imported db or gui sub-packages as attributes
    assert not hasattr(mod, "db"), "live_tick_worker must not import db"
    assert not hasattr(mod, "gui"), "live_tick_worker must not import gui"
    # Confirm only QtCore (not QtWidgets) was imported into the module namespace
    qt_imports = [
        name for name, val in vars(mod).items()
        if isinstance(val, _types.ModuleType) and "QtWidgets" in getattr(val, "__name__", "")
    ]
    assert qt_imports == [], f"live_tick_worker must not import QtWidgets; found: {qt_imports}"


# ---------------------------------------------------------------------------
# SRD-EXE-008.002 — set_contracts
# ---------------------------------------------------------------------------

# ``set_contracts`` only routes: it queues when the loop is not up yet and
# otherwise marshals onto the ib_insync loop.  The subscribe/cancel diff itself
# lives in ``_apply_contracts``, which these tests drive directly.

def test_set_contracts_queues_before_the_loop_is_up(qapp: Any):
    """UT-EXE-008.002.M01.T03a: contracts set before connect are held for later."""
    w = _make_worker()
    contract = _make_contract(con_id=123, symbol="AAPL")

    w.set_contracts({"AAPL": contract})

    assert w._active == {"AAPL": contract}


async def test_apply_contracts_subscribes_and_tracks(qapp: Any):
    """UT-EXE-008.002.M01.T03: a new contract is subscribed and recorded in _active."""
    w = _make_worker()
    mock_ib = _make_mock_ib(con_id=123, req_id=1)

    contract = _make_contract(con_id=123, symbol="AAPL")
    await w._apply_contracts(mock_ib, {"AAPL": contract})

    assert mock_ib.reqMktData.call_count == 1
    assert "AAPL" in w._active


async def test_apply_contracts_empty_cancels_all(qapp: Any):
    """UT-EXE-008.002.M01.T04: an empty set cancels the subscription and clears _active."""
    w = _make_worker()
    mock_ib = _make_mock_ib(con_id=123, req_id=1)

    contract = _make_contract(con_id=123)
    await w._apply_contracts(mock_ib, {"AAPL": contract})
    await w._apply_contracts(mock_ib, {})

    assert mock_ib.cancelMktData.call_count == 1
    assert w._active == {}


async def test_apply_contracts_idempotent_no_double_subscribe(qapp: Any):
    """UT-EXE-008.002.M01.T05: the same symbol twice does not double-subscribe."""
    w = _make_worker()
    mock_ib = _make_mock_ib(con_id=123, req_id=1)

    contract = _make_contract(con_id=123)
    await w._apply_contracts(mock_ib, {"AAPL": contract})
    await w._apply_contracts(mock_ib, {"AAPL": contract})

    assert mock_ib.reqMktData.call_count == 1


async def test_apply_contracts_15_symbols_pauses_once(qapp: Any):
    """UT-EXE-008.002.M01.T06: 15 contracts pace as one batch of 10, a pause, then 5."""
    w = _make_worker()
    mock_ib = MagicMock()

    def make_ticker(*_a: Any, **_kw: Any) -> MagicMock:
        t = MagicMock()
        t.contract = MagicMock()
        t.contract.conId = 0
        t.reqId = None
        return t

    mock_ib.reqMktData.side_effect = make_ticker
    contracts = {f"SYM{i}": _make_contract(con_id=i) for i in range(15)}

    with patch.object(_mod.asyncio, "sleep", new=AsyncMock()) as mock_sleep:
        await w._apply_contracts(mock_ib, contracts)

    mock_sleep.assert_awaited_once_with(_mod._SUB_PAUSE)
    assert mock_ib.reqMktData.call_count == 15


# ---------------------------------------------------------------------------
# SRD-EXE-008.003 — Tick handler
# ---------------------------------------------------------------------------

def test_on_pending_tickers_emits_last_price(qapp: Any):
    """UT-EXE-008.003.M01.T07: _on_pending_tickers emits tick_price with last price when valid."""
    w = _make_worker()
    ticker = _make_ticker(con_id=123, last=150.0, req_id=None)
    w._tickers = {"AAPL": ticker}   # resolution is by ticker identity

    received: list[tuple[str, float]] = []
    w.tick_price.connect(lambda tag, price: received.append((tag, price)))

    w._on_pending_tickers({ticker})

    assert received == [("AAPL", 150.0)]


def test_on_pending_tickers_falls_back_to_close(qapp: Any):
    """UT-EXE-008.003.M01.T08: _on_pending_tickers emits close price when last is NaN."""
    w = _make_worker()
    ticker = _make_ticker(con_id=123, last=float("nan"), close=149.5, req_id=None)
    w._tickers = {"AAPL": ticker}

    received: list[tuple[str, float]] = []
    w.tick_price.connect(lambda tag, price: received.append((tag, price)))

    w._on_pending_tickers({ticker})

    assert received == [("AAPL", 149.5)]


def test_on_pending_tickers_no_emit_when_both_nan(qapp: Any):
    """UT-EXE-008.003.M01.T09: _on_pending_tickers emits nothing when last and close are both NaN."""
    w = _make_worker()
    ticker = _make_ticker(con_id=123, last=float("nan"), close=float("nan"), req_id=None)
    w._tickers = {"AAPL": ticker}

    received: list[tuple[str, float]] = []
    w.tick_price.connect(lambda tag, price: received.append((tag, price)))

    w._on_pending_tickers({ticker})

    assert received == []


# ---------------------------------------------------------------------------
# SRD-EXE-008.004 — Error handler
# ---------------------------------------------------------------------------

def test_on_ibkr_error_fatal_emits_subscription_failed(qapp: Any):
    """UT-EXE-008.004.M01.T10: Fatal error code 354 emits subscription_failed and removes from _active."""
    w = _make_worker()
    contract = _make_contract(con_id=123)
    w._active = {"AAPL": contract}
    w._tickers = {"AAPL": _make_ticker(con_id=123)}
    w._reqid_to_tag = {42: "AAPL"}
    w._tag_by_conid = {123: "AAPL"}

    received: list[tuple[str, int]] = []
    w.subscription_failed.connect(lambda tag, code: received.append((tag, code)))

    w._on_ibkr_error(42, 354, "msg", MagicMock())

    assert received == [("AAPL", 354)]
    assert "AAPL" not in w._active


def test_on_ibkr_error_non_fatal_does_not_emit(qapp: Any):
    """UT-EXE-008.004.M01.T11: Non-fatal error code 321 does not emit subscription_failed."""
    w = _make_worker()
    contract_aapl = _make_contract(con_id=123)
    contract_msft = _make_contract(con_id=456)
    w._active = {"AAPL": contract_aapl, "MSFT": contract_msft}
    w._reqid_to_tag = {10: "AAPL", 11: "MSFT"}

    received: list[tuple[str, int]] = []
    w.subscription_failed.connect(lambda tag, code: received.append((tag, code)))

    w._on_ibkr_error(10, 321, "msg", MagicMock())

    assert received == []
    assert "AAPL" in w._active
    assert "MSFT" in w._active


# ---------------------------------------------------------------------------
# SRD-EXE-008.005 — request_stop
# ---------------------------------------------------------------------------

def test_request_stop_sets_stop_event(qapp: Any):
    """UT-EXE-008.005.M01.T12: request_stop() sets _stop_event."""
    w = _make_worker()
    assert not w._stop_event.is_set()
    w.request_stop()
    assert w._stop_event.is_set()


def test_thread_exits_after_request_stop(qapp: Any):
    """UT-EXE-008.005.M01.T13: Worker thread exits within 3s after request_stop() with mocked IBKR."""
    # Patch ib_insync.IB so _async_run uses a mock that immediately returns
    mock_ib_instance = MagicMock()
    mock_ib_instance.isConnected.return_value = True

    connect_called = threading.Event()

    async def fake_connect_async(*args: Any, **kwargs: Any) -> None:
        connect_called.set()

    mock_ib_instance.connectAsync = fake_connect_async

    mock_ib_cls = MagicMock(return_value=mock_ib_instance)

    with patch.dict(sys.modules, {"ib_insync": MagicMock(IB=mock_ib_cls)}):
        w = _make_worker()
        w.start()
        connect_called.wait(timeout=2.0)
        w.request_stop()
        finished = w.wait(3000)  # Qt milliseconds

    assert finished, "Worker thread did not exit within 3 seconds"


# ---------------------------------------------------------------------------
# SRD-EXE-008.006 — ClientId retry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connect_with_retry_succeeds_on_second_attempt(caplog: Any):
    """UT-EXE-008.006.M01.T14: _connect_with_retry returns True when second clientId succeeds."""
    import logging as _logging

    w = _make_worker(cid=14)
    mock_ib = MagicMock()

    # First call: connectAsync succeeds but isConnected() returns False (326 collision)
    # Second call: connectAsync succeeds and isConnected() returns True
    call_count = 0

    async def fake_connect(*args: Any, **kwargs: Any) -> None:
        nonlocal call_count
        call_count += 1

    mock_ib.connectAsync = fake_connect
    mock_ib.isConnected.side_effect = [False, True]

    with caplog.at_level(_logging.WARNING, logger="us_swing.execution.live_tick_worker"):
        result = await w._connect_with_retry(mock_ib)

    assert result is True
    assert any("ClientId 14 in use" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_connect_with_retry_fails_after_all_attempts(caplog: Any):
    """UT-EXE-008.006.M01.T15: _connect_with_retry returns False after 4 failed attempts."""
    import logging as _logging

    w = _make_worker(cid=14)
    mock_ib = MagicMock()

    async def fake_connect(*args: Any, **kwargs: Any) -> None:
        pass  # returns without raising — simulates 326 every time

    mock_ib.connectAsync = fake_connect
    mock_ib.isConnected.return_value = False  # always disconnected

    with caplog.at_level(_logging.ERROR, logger="us_swing.execution.live_tick_worker"):
        result = await w._connect_with_retry(mock_ib)

    assert result is False
    assert any("Cannot connect" in r.message for r in caplog.records)


def test_on_pending_tickers_falls_back_to_bid(qapp: Any):
    """UT-EXE-008.003.M01.T10: an index reports its level as bid, not last."""
    w = _make_worker()
    ticker = _make_ticker(con_id=123, last=float("nan"), bid=5200.0, close=5190.0)
    w._tickers = {"^GSPC": ticker}

    received: list[tuple[str, float]] = []
    w.tick_price.connect(lambda tag, price: received.append((tag, price)))

    w._on_pending_tickers({ticker})

    assert received == [("^GSPC", 5200.0)]
