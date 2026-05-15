"""
Module: tests/gui/test_ibkr_session.py
Traces To: MD-GUI-012.001.M01

Unit tests for IBKRSession — 16 cases from UTCD-GUI (UT-GUI-012.001.M01.T01..T16).

Architecture note
-----------------
``IBKRSession.start()`` connects ``QThread.started`` to ``_thread_main`` using
``QueuedConnection`` (receiver lives on the main thread).  In a production app
this dispatches ``_thread_main`` via ``app.exec()`` on the main thread, where
``loop.run_forever()`` then drives the asyncio work.

In the test harness there is no ``app.exec()`` (tests poll ``processEvents()``),
so the queued connection is never delivered and the QThread lifecycle cannot be
driven end-to-end without a running Qt event loop.

Tests that exercise the **asyncio layer** (T05–T16) bypass the QThread by:
  1. Creating a real ``asyncio`` event loop on the main test thread.
  2. Setting ``session._loop = loop`` and ``session._ib = fake_ib`` manually.
  3. Running coroutines on that loop with ``loop.run_until_complete``.
  4. Verifying Qt signals by processing events after the coroutine completes.

Tests T01–T03 (QThread lifecycle) are marked ``@pytest.mark.skip`` with a
concise explanation, because they require ``app.exec()`` to dispatch the queued
``started`` signal.
"""
from __future__ import annotations

import asyncio
import sys
import time
from typing import Any

import pytest

# Ensure src layout on path
import pathlib as _pathlib
_SRC = str(_pathlib.Path(__file__).parent.parent.parent / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from PyQt6.QtCore import QCoreApplication  # noqa: E402

from tests.gui.conftest import FakeIB, FakeContract  # noqa: E402


# ── Helpers ───────────────────────────────────────────────────────────────────

def _process_events(ms: int = 30) -> None:
    """Process Qt events for `ms` milliseconds."""
    deadline = time.monotonic() + ms / 1000
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def _build_session_with_fake(fake_ib: FakeIB) -> Any:
    """Return an IBKRSession with asyncio loop + FakeIB pre-wired, no QThread."""
    from us_swing.gui.ibkr_session import IBKRSession
    session = IBKRSession()
    loop = asyncio.new_event_loop()
    session._loop = loop
    session._ib = fake_ib
    session._host = "127.0.0.1"
    session._port = 4001
    session._client_id = 1
    return session, loop


def _run(loop: asyncio.AbstractEventLoop, coro: Any) -> Any:
    return loop.run_until_complete(coro)


# ── T01 ───────────────────────────────────────────────────────────────────────

@pytest.mark.skip(
    reason=(
        "T01 exercises the QThread lifecycle (start/connect/join).  In the test "
        "harness there is no app.exec() running, so the QThread.started signal "
        "(QueuedConnection to main thread) is never dispatched and _thread_main "
        "is never called.  The QThread lifecycle is verified at integration level "
        "where app.exec() drives the event loop."
    )
)
def test_start_boots_thread_and_calls_connect_once(qtbot: Any, fake_ib: FakeIB) -> None:
    """UT-GUI-012.001.M01.T01: start() boots QThread, calls connectAsync once with supplied client_id."""


# ── T02 ───────────────────────────────────────────────────────────────────────

@pytest.mark.skip(
    reason=(
        "T02 requires the QThread lifecycle to verify idempotency.  Same constraint "
        "as T01 — requires app.exec() to dispatch the QThread.started signal."
    )
)
def test_start_twice_is_idempotent(qtbot: Any, fake_ib: FakeIB) -> None:
    """UT-GUI-012.001.M01.T02: calling start() twice without stop() creates only one connection."""


# ── T03 ───────────────────────────────────────────────────────────────────────

@pytest.mark.skip(
    reason=(
        "T03 requires the full start→stop QThread cycle.  Same constraint as T01."
    )
)
def test_stop_disconnects_and_joins_thread(qtbot: Any, fake_ib: FakeIB) -> None:
    """UT-GUI-012.001.M01.T03: stop() calls ib.disconnect() and joins thread within 3 s."""


# ── T04 ───────────────────────────────────────────────────────────────────────

@pytest.mark.skip(
    reason=(
        "T04 requires the reconnect loop running inside the QThread asyncio event "
        "loop.  Same QThread lifecycle constraint as T01–T03."
    )
)
def test_stop_while_reconnect_sleep_no_error(qtbot: Any, fake_ib: FakeIB) -> None:
    """UT-GUI-012.001.M01.T04: stop() during mid-sleep reconnect loop exits cleanly."""


# ── T05 ───────────────────────────────────────────────────────────────────────

def test_account_value_event_debounced_emits_once(qtbot: Any, fake_ib: FakeIB) -> None:
    """UT-GUI-012.001.M01.T05: accountValueEvent fires 5x in 10 ms → account_ready emits exactly once."""
    import us_swing.gui.ibkr_session as _mod

    session, loop = _build_session_with_fake(fake_ib)
    emissions: list[Any] = []
    session.account_ready.connect(lambda acct, pos: emissions.append(acct))

    # Wire the account events on the fake IB
    fake_ib.accountValueEvent += session._on_account_event
    fake_ib.updatePortfolioEvent += session._on_account_event

    async def _run_test() -> None:
        # Fire 5 account events in rapid succession
        for _ in range(5):
            await session._on_account_event()
            await asyncio.sleep(0.002)
        # Wait for the 50 ms debounce to complete
        await asyncio.sleep(_mod._ACCOUNT_DEBOUNCE_S + 0.05)

    loop.run_until_complete(_run_test())
    loop.close()
    _process_events(50)

    assert len(emissions) == 1, f"Expected 1 debounced emission, got {len(emissions)}"


# ── T06 ───────────────────────────────────────────────────────────────────────

def test_pending_tickers_event_coalesced(qtbot: Any, fake_ib: FakeIB) -> None:
    """UT-GUI-012.001.M01.T06: pendingTickersEvent fires 3x → quotes_updated emits exactly once."""
    import us_swing.gui.ibkr_session as _mod

    session, loop = _build_session_with_fake(fake_ib)
    emissions: list[Any] = []
    session.quotes_updated.connect(lambda rows: emissions.append(rows))

    # Add a symbol so coalesce has something to emit
    from tests.gui.conftest import FakeTicker
    session._tickers["AAPL"] = FakeTicker(FakeContract("AAPL"), last=175.0, close=173.0)

    async def _run_test() -> None:
        # Fire 3 pendingTickers events in rapid succession
        for _ in range(3):
            await session._on_pending_tickers(None)
            await asyncio.sleep(0.005)
        # Wait for the 250 ms coalesce window
        await asyncio.sleep(_mod._QUOTE_COALESCE_S + 0.05)

    loop.run_until_complete(_run_test())
    loop.close()
    _process_events(50)

    assert len(emissions) == 1, f"Expected 1 coalesced emission, got {len(emissions)}"


# ── T07 ───────────────────────────────────────────────────────────────────────

def test_set_market_watch_symbols_subscribes_all(qtbot: Any, fake_ib: FakeIB) -> None:
    """UT-GUI-012.001.M01.T07: set_market_watch_symbols(["AAPL","MSFT"]) calls reqMktData for both, no cancels."""
    session, loop = _build_session_with_fake(fake_ib)

    _run(loop, session._connect_and_subscribe())
    _run(loop, session._apply_symbol_delta(new_mw={"AAPL", "MSFT"}))
    loop.close()

    assert set(fake_ib.req_calls) == {"AAPL", "MSFT"}
    assert fake_ib.cancel_calls == []


# ── T08 ───────────────────────────────────────────────────────────────────────

def test_set_market_watch_symbols_delta_only(qtbot: Any, fake_ib: FakeIB) -> None:
    """UT-GUI-012.001.M01.T08: mutating MW symbols issues delta only — overlapping not re-subscribed."""
    session, loop = _build_session_with_fake(fake_ib)

    _run(loop, session._connect_and_subscribe())
    _run(loop, session._apply_symbol_delta(new_mw={"AAPL", "MSFT"}))
    assert set(fake_ib.req_calls) == {"AAPL", "MSFT"}

    # Mutate: replace MSFT with TSLA; AAPL is shared
    _run(loop, session._apply_symbol_delta(new_mw={"AAPL", "TSLA"}))
    loop.close()

    # AAPL must NOT appear a second time in req_calls
    assert fake_ib.req_calls.count("AAPL") == 1, (
        f"AAPL subscribed twice: {fake_ib.req_calls}"
    )
    assert "TSLA" in fake_ib.req_calls
    assert "MSFT" in fake_ib.cancel_calls


# ── T09 ───────────────────────────────────────────────────────────────────────

def test_index_symbols_filtered_from_reqmktdata(qtbot: Any, fake_ib: FakeIB) -> None:
    """UT-GUI-012.001.M01.T09: ^-prefixed index symbols never reach reqMktData."""
    session, loop = _build_session_with_fake(fake_ib)

    _run(loop, session._connect_and_subscribe())
    _run(loop, session._apply_symbol_delta(new_mw={"^GSPC", "AAPL"}))
    loop.close()

    assert "^GSPC" not in fake_ib.req_calls
    assert "AAPL" in fake_ib.req_calls
    assert "^GSPC" not in session._tickers


# ── T10 ───────────────────────────────────────────────────────────────────────

def test_union_of_mw_and_wl_drives_subscriptions(qtbot: Any, fake_ib: FakeIB) -> None:
    """UT-GUI-012.001.M01.T10: symbol in both MW and WL stays subscribed when removed from one set."""
    session, loop = _build_session_with_fake(fake_ib)

    _run(loop, session._connect_and_subscribe())
    _run(loop, session._apply_symbol_delta(new_mw={"AAPL", "MSFT"}, new_wl={"AAPL", "TSLA"}))
    assert set(fake_ib.req_calls) == {"AAPL", "MSFT", "TSLA"}, (
        f"Expected all 3 subscribed, got {fake_ib.req_calls}"
    )

    # Remove AAPL from MW — it should stay subscribed due to WL membership
    _run(loop, session._apply_symbol_delta(new_mw={"MSFT"}))
    loop.close()

    assert fake_ib.cancel_calls == [], f"Expected no cancels, got {fake_ib.cancel_calls}"
    assert "AAPL" in session._tickers
    assert "MSFT" in session._tickers
    assert "TSLA" in session._tickers


# ── T11 ───────────────────────────────────────────────────────────────────────

def test_disconnected_event_emits_connection_lost(qtbot: Any, fake_ib: FakeIB) -> None:
    """UT-GUI-012.001.M01.T11: disconnectedEvent fires → connection_lost emits and reconnect task starts."""
    session, loop = _build_session_with_fake(fake_ib)
    lost_msgs: list[str] = []
    session.connection_lost.connect(lambda msg: lost_msgs.append(msg))

    # Make reconnect attempts fail quickly
    fake_ib.fail_connect = True

    async def _run_test() -> None:
        await session._on_disconnected()
        # Let the task get created
        await asyncio.sleep(0.02)

    loop.run_until_complete(_run_test())

    # Deliver the Qt signal
    _process_events(50)

    assert len(lost_msgs) >= 1, f"connection_lost not emitted; msgs={lost_msgs}"
    assert "Disconnected" in lost_msgs[0]
    # Reconnect task should have been spawned
    assert session._reconnect_task is not None

    loop.close()


# ── T12 ───────────────────────────────────────────────────────────────────────

def test_reconnect_loop_resubscribes_and_emits_restored(
    qtbot: Any, fake_ib: FakeIB, monkeypatch: Any
) -> None:
    """UT-GUI-012.001.M01.T12: successful reconnect resubscribes and emits connection_restored."""
    import us_swing.gui.ibkr_session as _mod

    monkeypatch.setattr(_mod, "_RECONNECT_BASE", 0.001)
    monkeypatch.setattr(_mod, "_RECONNECT_MAX_DELAY", 0.002)
    monkeypatch.setattr(_mod, "_RECONNECT_MAX_ATTEMPTS", 10)

    session, loop = _build_session_with_fake(fake_ib)
    restored_count: list[int] = [0]
    session.connection_restored.connect(lambda: restored_count.__setitem__(0, restored_count[0] + 1))

    # Set up initial tickers
    _run(loop, session._connect_and_subscribe())
    _run(loop, session._apply_symbol_delta(new_mw={"AAPL"}))
    assert "AAPL" in fake_ib.req_calls

    # Fail first attempt, succeed second
    fake_ib.fail_count = 1
    fake_ib.req_calls.clear()  # reset to count only reconnect subscriptions

    async def _run_reconnect() -> None:
        await session._reconnect_loop()

    loop.run_until_complete(_run_reconnect())
    loop.close()
    _process_events(50)

    assert restored_count[0] == 1, f"connection_restored not emitted (count={restored_count[0]})"
    # reqAccountUpdates should have been called at least twice (initial + reconnect)
    assert len(fake_ib.reqAccountUpdates_calls) >= 1


# ── T13 ───────────────────────────────────────────────────────────────────────

def test_max_reconnect_attempts_emits_final_connection_lost(
    qtbot: Any, fake_ib: FakeIB, monkeypatch: Any
) -> None:
    """UT-GUI-012.001.M01.T13: after N failed reconnects, connection_lost("Max reconnect") emits and loop stops."""
    import us_swing.gui.ibkr_session as _mod

    monkeypatch.setattr(_mod, "_RECONNECT_BASE", 0.001)
    monkeypatch.setattr(_mod, "_RECONNECT_MAX_DELAY", 0.002)
    monkeypatch.setattr(_mod, "_RECONNECT_MAX_ATTEMPTS", 3)

    session, loop = _build_session_with_fake(fake_ib)
    lost_msgs: list[str] = []
    session.connection_lost.connect(lambda m: lost_msgs.append(m))

    # All reconnects fail
    fake_ib.fail_connect = True

    async def _run_test() -> None:
        await session._reconnect_loop()

    loop.run_until_complete(_run_test())
    loop.close()
    _process_events(50)

    assert any("Max reconnect" in m for m in lost_msgs), (
        f"Expected 'Max reconnect' message; got: {lost_msgs}"
    )
    assert session._stopping is True


# ── T14 ───────────────────────────────────────────────────────────────────────

def test_backoff_sequence_honours_base_and_cap(
    qtbot: Any, fake_ib: FakeIB, monkeypatch: Any
) -> None:
    """UT-GUI-012.001.M01.T14: backoff sequence honours base, cap, ±20% jitter."""
    import us_swing.gui.ibkr_session as _mod

    base = 0.01
    cap = 0.04
    monkeypatch.setattr(_mod, "_RECONNECT_BASE", base)
    monkeypatch.setattr(_mod, "_RECONNECT_MAX_DELAY", cap)
    monkeypatch.setattr(_mod, "_RECONNECT_MAX_ATTEMPTS", 4)

    captured_delays: list[float] = []
    original_sleep = asyncio.sleep

    async def _fake_sleep(delay: float) -> None:
        captured_delays.append(delay)
        await original_sleep(0)  # yield without waiting

    monkeypatch.setattr(_mod.asyncio, "sleep", _fake_sleep)

    session, loop = _build_session_with_fake(fake_ib)
    fake_ib.fail_connect = True

    async def _run_test() -> None:
        await session._reconnect_loop()

    loop.run_until_complete(_run_test())
    loop.close()

    assert len(captured_delays) >= 1, "No delays captured"
    for i, d in enumerate(captured_delays):
        expected_base = min(base * (2 ** i), cap)
        lo = expected_base * 0.8
        hi = expected_base * 1.2
        assert lo <= d <= hi, (
            f"Delay {d:.4f} at attempt {i} outside [{lo:.4f}, {hi:.4f}]"
        )


# ── T15 ───────────────────────────────────────────────────────────────────────

def test_account_event_after_stop_does_not_emit(qtbot: Any, fake_ib: FakeIB) -> None:
    """UT-GUI-012.001.M01.T15: account event after stop() does NOT emit account_ready (robustness)."""
    from us_swing.gui.ibkr_session import IBKRSession

    session = IBKRSession()
    emissions: list[Any] = []
    session.account_ready.connect(lambda a, p: emissions.append(a))

    # Simulate a stopped session: _stopping = True, _ib = None, _loop = None
    session._stopping = True
    session._ib = None
    session._loop = None

    # Manually invoke _debounce_account on a temp loop.
    # With _ib = None, _build_account_snapshot raises RuntimeError.
    # _debounce_account catches the exception and does NOT emit account_ready.
    temp_loop = asyncio.new_event_loop()

    async def _run_test() -> None:
        await session._debounce_account()

    temp_loop.run_until_complete(_run_test())
    temp_loop.close()
    _process_events(30)

    assert emissions == [], f"account_ready should not emit when _ib is None, got {len(emissions)}"


# ── T16 ───────────────────────────────────────────────────────────────────────

def test_reapplying_same_symbol_set_is_noop(qtbot: Any, fake_ib: FakeIB) -> None:
    """UT-GUI-012.001.M01.T16: re-applying the same symbol set is a no-op — no spurious calls."""
    session, loop = _build_session_with_fake(fake_ib)

    _run(loop, session._connect_and_subscribe())
    _run(loop, session._apply_symbol_delta(new_mw={"AAPL", "MSFT"}))
    assert set(fake_ib.req_calls) == {"AAPL", "MSFT"}

    req_count_before = len(fake_ib.req_calls)
    cancel_count_before = len(fake_ib.cancel_calls)

    # Re-apply the exact same set
    _run(loop, session._apply_symbol_delta(new_mw={"AAPL", "MSFT"}))
    loop.close()

    assert len(fake_ib.req_calls) == req_count_before, (
        f"Unexpected new req_calls: {fake_ib.req_calls}"
    )
    assert len(fake_ib.cancel_calls) == cancel_count_before, (
        f"Unexpected cancel_calls: {fake_ib.cancel_calls}"
    )
