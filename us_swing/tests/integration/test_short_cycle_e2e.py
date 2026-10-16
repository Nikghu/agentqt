"""Integration test for FO-EXE-018 — a full SHORT trade through the simulated broker.

Sells to open, trades against the live tick path, and buys to cover on the exit
trigger, asserting the real order sides, the stored order states and the realized
P&L that a user would see. Uses a real SQLite database (no DB mocking) and the
same ``SimBroker`` the paper mode runs on.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest
import sqlalchemy as sa

from us_swing.broker.sim import ImmediateFillModel, SimBroker
from us_swing.db.manager import DatabaseManager
from us_swing.db.schema import create_schema, trades
from us_swing.execution.broker_adapter import BrokerAdapter
from us_swing.execution.order_ingestion import OrderIngestion
from us_swing.execution.strategy_engine._signals import Action, TradeSignal
from us_swing.execution.trade_cycle._dto import TradeCycleState
from us_swing.execution.trade_cycle._events import ExitTrigger
from us_swing.execution.trade_cycle._repository import TradeCycleRepository
from us_swing.execution.trade_cycle._service import TradeCycleService


@dataclass
class _Config:
    target_enabled: bool = True
    stoploss_enabled: bool = True
    target_value: float = 4.0
    stoploss_value: float = 2.0
    target_type: str = "fixed"
    stoploss_type: str = "fixed"


class _Scheduler:
    """Holds the broker's fill callbacks until the test releases them."""

    def __init__(self) -> None:
        self._queued: list[Callable[[], None]] = []

    def __call__(self, callback: Callable[[], None]) -> None:
        self._queued.append(callback)

    def pump(self) -> None:
        while self._queued:
            self._queued.pop(0)()


class _Desk:
    """One user's paper trading desk: broker, ingestion, cycles and ledger."""

    def __init__(self) -> None:
        path = os.path.join(tempfile.mkdtemp(), "short_e2e.db")
        self.ledger = DatabaseManager("sqlite:///" + path.replace(os.sep, "/"))
        create_schema(self.ledger._engine)

        self.bus = MagicMock()
        self.cycles = TradeCycleService(
            repo=TradeCycleRepository(self.ledger._engine), bus=self.bus
        )
        self.cycles.start()

        self._scheduler = _Scheduler()
        self._exit_reason = "manual"
        self.adapter = BrokerAdapter(
            broker=SimBroker(ImmediateFillModel(), scheduler=self._scheduler),
            ingestion=OrderIngestion(
                ledger=self.ledger,
                fill_sink=lambda _f: None,
                reject_sink=lambda _r: None,
                cycles=self.cycles,
            ),
            config_provider=lambda _sid: _Config(),
            user_id_provider=lambda: 1,
            session_date_provider=lambda: "2026-09-17",
            exit_reason_provider=lambda: self._exit_reason,
        )

    def submit(self, action: Action, price: float, qty: int = 10, reason: str = "manual") -> int:
        self._exit_reason = reason
        order_id = self.adapter.submit(
            TradeSignal(
                action=action,
                symbol="AAPL",
                strategy_id="FADE",
                entry_price=price,
                qty_recommended=qty,
                user_id=1,
                direction="SHORT",
            ),
            qty,
        )
        self._scheduler.pump()
        assert order_id is not None
        return order_id

    def tick(self, price: float) -> None:
        loop = self.cycles._loop
        assert loop is not None

        async def _drive() -> None:
            await self.cycles._handle_tick("AAPL", price)
            for acc in list(self.cycles._accs.values()):
                if acc.dirty:
                    await self.cycles._flush(acc)

        asyncio.run_coroutine_threadsafe(_drive(), loop).result(timeout=2.0)

    def order_row(self, order_id: int) -> Any:
        with self.ledger._engine.connect() as conn:
            return conn.execute(
                sa.select(trades.c.side, trades.c.order_state, trades.c.filled_quantity)
                .where(trades.c.trade_id == str(order_id))
            ).first()

    def exit_reasons(self) -> list[str]:
        return [
            c[0][0].reason
            for c in self.bus.publish.call_args_list
            if isinstance(c[0][0], ExitTrigger)
        ]

    def close(self) -> None:
        self.cycles.stop()


@pytest.fixture
def desk() -> Any:
    d = _Desk()
    yield d
    d.close()


def _open_short(desk: _Desk) -> Any:
    """Sell 10 × AAPL to open at $100; stop $102, target $96."""
    entry_order = desk.submit(Action.ENTRY, 100.0)
    assert desk.order_row(entry_order)[0] == "SELL"

    (cycle,) = desk.cycles.open_cycles()
    assert cycle.direction == "SHORT"
    assert cycle.hard_stop_loss == pytest.approx(102.0)
    assert cycle.target_price == pytest.approx(96.0)
    return cycle


def test_short_cycle_reaches_target(desk: _Desk) -> None:
    """IT-EXE-018.001: a SHORT sold at $100 and covered at its $96 target books +$40."""
    cycle = _open_short(desk)

    desk.tick(98.0)
    live = desk.cycles.cycle(cycle.cycle_id)
    assert live is not None
    assert live.current_pnl_usd == pytest.approx(20.0)
    assert desk.exit_reasons() == []

    desk.tick(96.0)
    assert desk.exit_reasons() == ["target"]

    exit_order = desk.submit(Action.EXIT, 96.0, reason="target")
    side, order_state, filled = desk.order_row(exit_order)
    assert (side, order_state, filled) == ("BUY", "FILLED", 10)

    closed = desk.cycles.cycle(cycle.cycle_id)
    assert closed is not None
    assert closed.state is TradeCycleState.CLOSED
    assert closed.exit_reason == "target"
    assert closed.realized_pnl_usd == pytest.approx(40.0)
    assert closed.realized_pnl_pct == pytest.approx(4.0)
    assert desk.cycles.open_cycles() == ()


def test_short_cycle_hits_the_hard_stop(desk: _Desk) -> None:
    """IT-EXE-018.002: the same SHORT covered at its $102 stop books −$20."""
    cycle = _open_short(desk)

    desk.tick(102.0)
    assert desk.exit_reasons() == ["hard_sl"]

    exit_order = desk.submit(Action.EXIT, 102.0, reason="hard_sl")
    assert desk.order_row(exit_order)[0] == "BUY"

    closed = desk.cycles.cycle(cycle.cycle_id)
    assert closed is not None
    assert closed.state is TradeCycleState.CLOSED
    assert closed.exit_reason == "hard_sl"
    assert closed.realized_pnl_usd == pytest.approx(-20.0)
