"""Module: tests/execution/test_broker_adapter.py
Parent SRD: SRD-EXE-015.001, SRD-EXE-015.004

End-to-end wiring of the broker abstraction: BrokerAdapter → SimBroker →
OrderIngestion → trades ledger + trade-cycle command.  Uses a real SQLite
database for the ``trades`` writes (no DB mocking) and a recording stub for the
non-DB collaborators.
"""
from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass

import pytest
import sqlalchemy as sa

from us_swing.broker.sim import ImmediateFillModel, SimBroker
from us_swing.db.manager import DatabaseManager
from us_swing.db.schema import create_schema, trades
from us_swing.execution.broker_adapter import BrokerAdapter
from us_swing.execution.order_ingestion import OrderIngestion
from us_swing.execution.strategy_engine._signals import Action, TradeSignal


class _ManualScheduler:
    def __init__(self) -> None:
        self._queue: list[Callable[[], None]] = []

    def __call__(self, callback: Callable[[], None]) -> None:
        self._queue.append(callback)

    def pump(self) -> None:
        while self._queue:
            self._queue.pop(0)()


class _ImmediateScheduler:
    """Runs the deferred fill synchronously *inside* ``place_order`` — i.e.
    before ``submit`` reaches ``on_order_accepted``.  Reproduces the cross-thread
    race where the broker delivers a fill ahead of the acceptance step."""

    def __call__(self, callback: Callable[[], None]) -> None:
        callback()


@dataclass
class _StubConfig:
    target_enabled: bool = True
    stoploss_enabled: bool = True
    target_value: float = 10.0
    stoploss_value: float = 5.0
    target_type: str = "fixed"
    stoploss_type: str = "fixed"


class _StubCycles:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def on_entry_fill(self, **k: object) -> None:
        self.calls.append(("entry", k.get("hard_stop_loss")))

    def on_exit_fill(self, **k: object) -> None:
        self.calls.append(("exit", k.get("exit_reason")))

    def on_entry_failed(self, *a: object, **k: object) -> None:
        return None

    def update_risk(self, *a: object, **k: object) -> None:
        return None

    def reload(self) -> None:
        pass


def _make_db() -> DatabaseManager:
    path = os.path.join(tempfile.mkdtemp(), "adapter.db")
    mgr = DatabaseManager("sqlite:///" + path.replace(os.sep, "/"))
    create_schema(mgr._engine)
    return mgr


def _trade_row(mgr: DatabaseManager, trade_id: str) -> tuple:  # type: ignore[type-arg]
    with mgr._engine.connect() as conn:
        return conn.execute(
            sa.select(trades.c.order_state, trades.c.filled_quantity, trades.c.entry_price)
            .where(trades.c.trade_id == trade_id)
        ).first()


def test_entry_signal_flows_through_to_trades_and_cycle() -> None:
    """UT: an ENTRY signal submits, writes the trades row NEW, then on fill
    advances it to FILLED and opens a cycle with the config's stop snapshot."""
    mgr = _make_db()
    cycles = _StubCycles()
    engine_fills: list[object] = []
    broker_events: list[object] = []
    scheduler = _ManualScheduler()

    ingestion = OrderIngestion(ledger=mgr, fill_sink=engine_fills.append,
                               reject_sink=lambda _r: None, cycles=cycles)
    adapter = BrokerAdapter(
        broker=SimBroker(ImmediateFillModel(), scheduler=scheduler),
        ingestion=ingestion,
        config_provider=lambda _sid: _StubConfig(),
        user_id_provider=lambda: 1,
        session_date_provider=lambda: "2026-06-04",
        on_event=broker_events.append,
    )

    signal = TradeSignal(
        action=Action.ENTRY,
        symbol="AAPL",
        strategy_id="S1",
        entry_price=100.0,
        qty_recommended=10,
        user_id=1,
    )
    order_id = adapter.submit(signal, 10)

    assert isinstance(order_id, int)
    assert _trade_row(mgr, str(order_id))[0] == "NEW"
    assert engine_fills == []  # async — no fill before the scheduler runs

    scheduler.pump()

    state, filled, entry_price = _trade_row(mgr, str(order_id))
    assert state == "FILLED"
    assert filled == 10
    assert entry_price == 100.0
    assert len(engine_fills) == 1
    assert len(broker_events) == 1
    # cycle opened with hard stop = 100 * (1 - 5/100) = 95.0
    assert cycles.calls == [("entry", 95.0)]


def test_exit_signal_closes_cycle() -> None:
    """UT: an EXIT signal routes a SELL and drives the cycle close path."""
    mgr = _make_db()
    cycles = _StubCycles()
    scheduler = _ManualScheduler()
    ingestion = OrderIngestion(ledger=mgr, fill_sink=lambda _f: None,
                               reject_sink=lambda _r: None, cycles=cycles)
    adapter = BrokerAdapter(
        broker=SimBroker(ImmediateFillModel(), scheduler=scheduler),
        ingestion=ingestion,
        config_provider=lambda _sid: _StubConfig(),
        user_id_provider=lambda: 1,
        session_date_provider=lambda: "2026-06-04",
        exit_reason_provider=lambda: "target",
    )
    signal = TradeSignal(
        action=Action.EXIT,
        symbol="AAPL",
        strategy_id="S1",
        entry_price=110.0,
        qty_recommended=10,
        user_id=1,
    )
    order_id = adapter.submit(signal, 10)
    scheduler.pump()

    assert _trade_row(mgr, str(order_id))[0] == "FILLED"
    assert cycles.calls == [("exit", "target")]


def test_fill_arriving_before_acceptance_is_not_dropped() -> None:
    """Regression: a fill delivered before ``on_order_accepted`` must still be
    ingested — context is keyed by client_ref and registered before placement,
    so the order is never seen as "unknown" and the cycle still opens."""
    mgr = _make_db()
    cycles = _StubCycles()
    engine_fills: list[object] = []
    ingestion = OrderIngestion(ledger=mgr, fill_sink=engine_fills.append,
                               reject_sink=lambda _r: None, cycles=cycles)
    adapter = BrokerAdapter(
        # ImmediateScheduler fires the fill inside place_order — before the
        # acceptance insert — which is exactly the dropped-fill race condition.
        broker=SimBroker(ImmediateFillModel(), scheduler=_ImmediateScheduler()),
        ingestion=ingestion,
        config_provider=lambda _sid: _StubConfig(),
        user_id_provider=lambda: 1,
        session_date_provider=lambda: "2026-06-04",
    )

    signal = TradeSignal(
        action=Action.ENTRY,
        symbol="AAPL",
        strategy_id="S1",
        entry_price=100.0,
        qty_recommended=10,
        user_id=1,
    )
    order_id = adapter.submit(signal, 10)

    state, filled, entry_price = _trade_row(mgr, str(order_id))
    assert state == "FILLED"
    assert filled == 10
    assert entry_price == 100.0
    assert len(engine_fills) == 1
    assert cycles.calls == [("entry", 95.0)]


# ── FO-EXE-018 — direction-aware order placement ──────────────────────────────


class _CaptureBroker:
    """Records placed requests; never fills."""

    def __init__(self) -> None:
        self.requests: list[object] = []

    def on_event(self, _handler: object) -> None:
        return None

    def place_order(self, request: object) -> str:
        self.requests.append(request)
        return str(500 + len(self.requests))


class _CaptureIngestion:
    def __init__(self) -> None:
        self.contexts: list[object] = []

    def register(self, ctx: object) -> None:
        self.contexts.append(ctx)

    def discard(self, _signal_id: str) -> None:
        return None

    def on_order_accepted(self, _signal_id: str, _order_id: str) -> None:
        return None

    def on_order_event(self, _event: object) -> None:
        return None


def _capture_adapter(stop_pct: float = 2.0, target_pct: float = 4.0):  # type: ignore[no-untyped-def]
    broker = _CaptureBroker()
    ingestion = _CaptureIngestion()
    adapter = BrokerAdapter(
        broker=broker,  # type: ignore[arg-type]
        ingestion=ingestion,  # type: ignore[arg-type]
        config_provider=lambda _sid: _StubConfig(stoploss_value=stop_pct, target_value=target_pct),
        user_id_provider=lambda: 1,
        session_date_provider=lambda: "2026-09-17",
    )
    return adapter, broker, ingestion


def _signal(action: Action, direction: str) -> TradeSignal:
    return TradeSignal(action=action, symbol="AAPL", strategy_id="S1",
                       entry_price=100.0, qty_recommended=10, user_id=1, direction=direction)


def test_short_entry_places_sell_with_flipped_levels() -> None:
    """UT-EXE-018.005.M06.T01: a SHORT entry places a SELL with stop above and target below."""
    from us_swing.broker.broker import OrderSide

    adapter, broker, ingestion = _capture_adapter()
    adapter.submit(_signal(Action.ENTRY, "SHORT"), 10)

    assert broker.requests[0].side is OrderSide.SELL  # type: ignore[attr-defined]
    ctx = ingestion.contexts[0]
    assert ctx.direction == "SHORT"  # type: ignore[attr-defined]
    assert ctx.hard_stop_loss == pytest.approx(102.0)  # type: ignore[attr-defined]
    assert ctx.target_price == pytest.approx(96.0)  # type: ignore[attr-defined]


def test_short_exit_places_buy() -> None:
    """UT-EXE-018.005.M06.T02: a SHORT exit places a BUY."""
    from us_swing.broker.broker import OrderSide

    adapter, broker, _ingestion = _capture_adapter()
    adapter.submit(_signal(Action.EXIT, "SHORT"), 10)

    assert broker.requests[0].side is OrderSide.BUY  # type: ignore[attr-defined]


def test_long_orders_unchanged() -> None:
    """UT-EXE-018.005.M06.T03: LONG entry and exit keep BUY / SELL and the long levels."""
    from us_swing.broker.broker import OrderSide

    adapter, broker, ingestion = _capture_adapter()
    adapter.submit(_signal(Action.ENTRY, "LONG"), 10)
    adapter.submit(_signal(Action.EXIT, "LONG"), 10)

    assert [r.side for r in broker.requests] == [OrderSide.BUY, OrderSide.SELL]  # type: ignore[attr-defined]
    ctx = ingestion.contexts[0]
    assert ctx.hard_stop_loss == pytest.approx(98.0)  # type: ignore[attr-defined]
    assert ctx.target_price == pytest.approx(104.0)  # type: ignore[attr-defined]
