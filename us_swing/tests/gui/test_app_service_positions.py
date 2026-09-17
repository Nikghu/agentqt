"""
Module: MD-EXE-018.012.M10 — AppService position direction tests
Parent SRD: SRD-EXE-018.013
"""
from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class _FakeIB:
    def __init__(self, portfolio: list[Any]) -> None:
        self._portfolio = portfolio
        self.connectAsync = AsyncMock()
        self.accountSummaryAsync = AsyncMock(return_value=[])

    def portfolio(self) -> list[Any]:
        return self._portfolio

    def isConnected(self) -> bool:
        return False


def test_ibkr_negative_quantity_maps_to_short() -> None:
    """UT-EXE-018.013.M10.T01: an IBKR portfolio row with negative quantity becomes a SHORT position."""
    from us_swing.gui.app_service import _AccountDataWorker

    item = SimpleNamespace(
        position=-10, averageCost=100.0, marketValue=-970.0,
        contract=SimpleNamespace(symbol="AAPL"),
    )
    fake_module = SimpleNamespace(IB=lambda: _FakeIB([item]))
    worker = _AccountDataWorker("127.0.0.1", 7497, 99)
    emitted: list[Any] = []
    worker.done.connect(lambda _acct, positions: emitted.extend(positions))
    worker.failed.connect(lambda msg: pytest.fail(msg))

    with patch.dict(sys.modules, {"ib_insync": fake_module}),             patch("us_swing.gui.app_service.asyncio.sleep", AsyncMock()):
        asyncio.run(worker._async_run())

    (pos,) = emitted
    assert pos.direction == "SHORT"
    assert pos.quantity == 10
    assert pos.unrealised_pnl == pytest.approx(30.0)


def test_cycle_position_copies_direction() -> None:
    """UT-EXE-018.013.M10.T02: positions built from open cycles keep the cycle direction."""
    from us_swing.gui.app_service import _CyclePositionSource

    snap = SimpleNamespace(
        symbol="AAPL", user_id=1, entry_qty=10, entry_price=100.0,
        hard_stop_loss=102.0, target_price=96.0, strategy_id="FADE", direction="SHORT",
    )
    query = MagicMock()
    query.open_cycles.return_value = (snap,)

    (pos,) = _CyclePositionSource(query, lambda: "paper").get_all(1)

    assert pos.direction == "SHORT"
