"""Module: tests/broker/test_ibkr_order_key.py
Parent SRD: SRD-EXE-015.010, SRD-EXE-015.011

IBKR order numbers that never repeat, and catch-up of fills from an earlier
session (ISS-EXE-0018).  A fake TWS stands in for ib_insync.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from us_swing.broker import ibkr
from us_swing.broker.ibkr import IBKRClientGateway, IbkrOrderUpdate


class _Event(list):  # type: ignore[type-arg]
    def __iadd__(self, handler: Any) -> _Event:
        self.append(handler)
        return self


class _FakeIB:
    def __init__(self, tws_id: int = 95) -> None:
        self.tws_id = tws_id
        self.errorEvent = _Event()
        self.execDetailsEvent = _Event()
        self.connectedEvent = _Event()
        self.cancelled: list[int] = []
        self._trades: list[Any] = []
        self._fills: list[Any] = []

    def placeOrder(self, _contract: Any, order: Any) -> Any:
        order.orderId = self.tws_id
        trade = SimpleNamespace(
            order=order,
            statusEvent=_Event(),
            orderStatus=SimpleNamespace(status="Filled", avgFillPrice=23.1),
            filled=lambda: 5,
            log=[],
        )
        self._trades.append(trade)
        return trade

    def trades(self) -> list[Any]:
        return self._trades

    def cancelOrder(self, order: Any) -> None:
        self.cancelled.append(order.orderId)

    def fills(self) -> list[Any]:
        return self._fills

    def add_fill(self, ref: str, shares: int, price: float) -> Any:
        fill = SimpleNamespace(execution=SimpleNamespace(orderRef=ref, shares=shares, price=price))
        self._fills.append(fill)
        return fill


_NOW_LOOP = SimpleNamespace(call_soon_threadsafe=lambda fn: fn())


def _gateway(ib: _FakeIB) -> tuple[IBKRClientGateway, list[IbkrOrderUpdate]]:
    client = SimpleNamespace(ib=ib, loop=_NOW_LOOP, is_connected=lambda: True)
    gateway = IBKRClientGateway(client)  # type: ignore[arg-type]
    seen: list[IbkrOrderUpdate] = []
    gateway.on_status(seen.append)
    return gateway, seen


def test_same_tws_id_gets_different_order_numbers(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-EXE-015.010.M01.T01: Two sessions given TWS id 95 still get different numbers."""
    clock = [1_764_000_000.0]
    monkeypatch.setattr(ibkr.time, "time", lambda: clock[0])
    first, _ = _gateway(_FakeIB(tws_id=95))
    key_a = first.submit("PRU", "SELL", 7, "MARKET", None)
    clock[0] += 60.0
    second_ib = _FakeIB(tws_id=95)
    second, _ = _gateway(second_ib)
    key_b = second.submit("HRL", "SELL", 5, "MARKET", None)

    assert key_a != key_b
    assert key_a.isdigit() and key_b.isdigit()
    assert second_ib.trades()[0].order.orderRef == key_b


def test_status_error_and_cancel_use_the_app_number() -> None:
    """UT-EXE-015.010.M01.T02: Status, error and cancel for TWS id 95 use the app number."""
    ib = _FakeIB(tws_id=95)
    gateway, seen = _gateway(ib)
    key = gateway.submit("HRL", "SELL", 5, "MARKET", None)
    trade = ib.trades()[0]

    trade.statusEvent[0](trade)
    gateway._on_error(95, 201, "Order rejected")
    gateway._on_error(96, 201, "someone else's order")
    gateway.cancel(key)

    assert [(u.broker_order_id, u.status) for u in seen] == [(key, "Filled"), (key, "Inactive")]
    assert ib.cancelled == [95]


def test_earlier_session_fill_is_passed_on_with_totals() -> None:
    """UT-EXE-015.011.M01.T01: An earlier session's fill is sent with total shares and average."""
    ib = _FakeIB()
    ib.add_fill("1764000000000", 2, 23.00)
    ib.add_fill("1764000000000", 3, 23.20)
    gateway, seen = _gateway(ib)

    gateway.start_catch_up()

    assert seen == [IbkrOrderUpdate("1764000000000", "Submitted", 5, pytest.approx(23.12))]
    assert ib.execDetailsEvent == [gateway._on_exec_details]

    ib.connectedEvent[0]()

    assert len(seen) == 2


def test_manual_and_own_fills_are_not_passed_on() -> None:
    """UT-EXE-015.011.M01.T02: Fills with no reference, or of this session's orders, are skipped."""
    ib = _FakeIB()
    ib.add_fill("", 10, 50.0)
    gateway, seen = _gateway(ib)
    gateway.start_catch_up()
    key = gateway.submit("HRL", "SELL", 5, "MARKET", None)
    seen.clear()

    gateway._on_exec_details(None, ib.add_fill(key, 5, 23.1))

    assert seen == []
