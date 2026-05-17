"""Tests for MD-EXE-009.001.M03 — core/monitoring_session/_events.py."""
from __future__ import annotations

import logging

import pytest

from us_swing.core.monitoring_session import (
    SymbolEnteredPosition,
    SymbolEvicted,
    SymbolExitedPosition,
    SymbolStartedMonitoring,
)
from us_swing.core.monitoring_session._events import (
    _InProcessBus,
)


def _make_bus() -> _InProcessBus:
    return _InProcessBus()


def _started_event(symbol: str = "A") -> SymbolStartedMonitoring:
    return SymbolStartedMonitoring(
        event_id="e1",
        occurred_at="2026-05-14T13:30:00",
        symbol=symbol,
        session_date="2026-05-14",
        preset_id="p",
        run_timestamp="2026-05-14T13:30:00Z",
    )


# ── UT-EXE-009.001.M03.T02 ──────────────────────────────────────────────────


def test_publish_invokes_handler_synchronously() -> None:
    """UT-EXE-009.001.M03.T02: publish invokes the registered handler synchronously."""
    bus = _make_bus()
    received: list[SymbolStartedMonitoring] = []

    bus.subscribe(SymbolStartedMonitoring, received.append)
    evt = _started_event()
    bus.publish(evt)

    # Handler must have been called before publish returned.
    assert len(received) == 1
    assert received[0] is evt


# ── UT-EXE-009.001.M03.T03 ──────────────────────────────────────────────────


def test_subscription_cancel_detaches_handler() -> None:
    """UT-EXE-009.001.M03.T03: Subscription.cancel() detaches the handler."""
    bus = _make_bus()
    received: list[object] = []

    sub = bus.subscribe(SymbolStartedMonitoring, received.append)
    sub.cancel()
    bus.publish(_started_event())

    assert len(received) == 0


# ── UT-EXE-009.001.M03.T04 ──────────────────────────────────────────────────


def test_handler_exception_caught_sibling_still_called(caplog: pytest.LogCaptureFixture) -> None:
    """UT-EXE-009.001.M03.T04: A handler exception is caught, logged, and sibling handlers still run."""
    bus = _make_bus()
    sibling_called: list[bool] = []

    def _bad_handler(_evt: object) -> None:
        raise RuntimeError("intentional")

    bus.subscribe(SymbolStartedMonitoring, _bad_handler)
    bus.subscribe(SymbolStartedMonitoring, lambda _e: sibling_called.append(True))

    with caplog.at_level(logging.ERROR):
        bus.publish(_started_event())

    # Second handler must still fire.
    assert sibling_called == [True]
    # Error must be logged with [Lifecycle] topic.
    assert any("[Lifecycle]" in r.message for r in caplog.records)
    # publish must return normally (no exception propagated).


# ── UT-EXE-009.001.M03.T05 ──────────────────────────────────────────────────


def test_publish_no_subscribers_is_noop(caplog: pytest.LogCaptureFixture) -> None:
    """UT-EXE-009.001.M03.T05: publish with no subscribers is a no-op."""
    bus = _make_bus()
    evicted = SymbolEvicted(
        event_id="e1",
        occurred_at="2026-05-14T13:30:00",
        symbol="B",
        evicted_session_dates=("2026-05-13",),
    )

    with caplog.at_level(logging.DEBUG):
        bus.publish(evicted)  # Must not raise.

    assert len(caplog.records) == 0


# ── UT-EXE-009.001.M03.T06 ──────────────────────────────────────────────────


def test_subscriptions_scoped_by_event_type() -> None:
    """UT-EXE-009.001.M03.T06: Subscriptions are scoped by event type."""
    bus = _make_bus()
    a_called: list[object] = []
    b_called: list[object] = []

    bus.subscribe(SymbolEnteredPosition, a_called.append)
    bus.subscribe(SymbolExitedPosition, b_called.append)

    entered_evt = SymbolEnteredPosition(
        event_id="e1",
        occurred_at="2026-05-14T13:30:00",
        symbol="A",
        anchor_session_date="2026-05-14",
        trade_id="t1",
        fill_qty=100,
        fill_time="2026-05-14T14:00:00Z",
    )
    bus.publish(entered_evt)

    assert len(a_called) == 1
    assert len(b_called) == 0
