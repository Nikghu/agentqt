"""
Module: MD-EXE-012.002.M04 — execution/trade_cycle/_protocols.py
Parent SRD: SRD-EXE-012.010, SRD-EXE-012.011

CQRS-lite Protocols separating the read surface (``TradeCycleQuery``)
from the write surface (``TradeCycleCommand``).  Consumers MUST
type-annotate dependencies against these Protocols, never against the
concrete ``_service.TradeCycleService``.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from us_swing.execution._enums import ExecutionEnums
from us_swing.execution.trade_cycle._dto import CycleSnapshot


@runtime_checkable
class TradeCycleQuery(Protocol):
    """Read-only side of the service.  Cheap, side-effect-free, thread-safe."""

    def open_cycles(self) -> tuple[CycleSnapshot, ...]: ...

    def cycle(self, cycle_id: int) -> CycleSnapshot | None: ...

    def history(
        self,
        *,
        symbol: str | None      = None,
        strategy_id: str | None = None,
        days: int               = 30,
    ) -> tuple[CycleSnapshot, ...]: ...

    def has_open_cycle(self, strategy_id: str, symbol: str) -> bool: ...

    def open_cycles_for_strategy(
        self, strategy_id: str
    ) -> tuple[CycleSnapshot, ...]: ...

    def closed_between(
        self, start_iso: str, end_iso: str
    ) -> tuple[CycleSnapshot, ...]: ...


@runtime_checkable
class TradeCycleCommand(Protocol):
    """Mutating side of the service.

    Called by the order pipeline (fill events) and by the GUI (manual risk
    edits).  Tick handling is internal and not part of the public Command
    surface — ticks arrive via the ``LiveTickWorker`` bridge wired at the
    AppService boundary.
    """

    def on_entry_fill(
        self,
        *,
        strategy_id:     str,
        symbol:          str,
        user_id:         int,
        entry_order_id:  str,
        entry_price:     float,
        entry_qty:       int,
        fill_time:       str,
        hard_stop_loss:  float,
        target_price:    float | None,
        target_type:     str,
        stoploss_type:   str,
        trailing_mode:   str | None,
        trailing_offset: float | None,
        monitoring_session_date: str,
        order_state:     ExecutionEnums.BuyOrderState = ExecutionEnums.BuyOrderState.FILLED,
    ) -> CycleSnapshot: ...

    def on_exit_fill(
        self,
        *,
        exit_order_id: str,
        symbol:        str,
        strategy_id:   str,
        exit_price:    float,
        exit_qty:      int,
        exit_time:     str,
        exit_reason:   str,
        order_state:   ExecutionEnums.SellOrderState = ExecutionEnums.SellOrderState.FILLED,
    ) -> CycleSnapshot: ...

    def abort_entry_order(
        self, entry_order_id: str, reason: str
    ) -> CycleSnapshot | None: ...

    def on_entry_failed(self, cycle_id: int, reason: str) -> CycleSnapshot: ...

    def update_risk(
        self,
        cycle_id: int,
        *,
        hard_sl:         float | None = None,
        target:          float | None = None,
        trailing_offset: float | None = None,
        trailing_mode:   str | None   = None,
    ) -> CycleSnapshot: ...

    def reload(self) -> None: ...


__all__ = [
    "TradeCycleQuery",
    "TradeCycleCommand",
]
