"""
Module: MD-EXE-018.003.M04 — execution/direction.py
Parent SRD: SRD-EXE-018.003, SRD-EXE-018.004

Single source for how a trade direction turns into an order side and into
stop / target price levels. No other module may derive either on its own.
"""
from __future__ import annotations

from us_swing.broker.broker import OrderSide
from us_swing.execution._enums import ExecutionEnums


def order_side(direction: str, is_entry: bool) -> OrderSide:
    """Return the broker side for an entry or exit order.

    Args:
        direction: ``LONG`` or ``SHORT``.
        is_entry: True for the order that opens the trade.

    Returns:
        ``BUY`` / ``SELL`` for a long entry / exit, ``SELL`` / ``BUY`` for a short.
    """
    is_long = direction != ExecutionEnums.TradeDirection.SHORT
    return OrderSide.BUY if is_entry == is_long else OrderSide.SELL


def risk_levels(
    direction: str,
    price: float,
    stoploss_enabled: bool,
    stoploss_pct: float,
    target_enabled: bool,
    target_pct: float,
) -> tuple[float | None, float | None]:
    """Return absolute ``(stop, target)`` prices for a reference price.

    Args:
        direction: ``LONG`` or ``SHORT``.
        price: Reference (entry) price.
        stoploss_enabled: Whether a stop loss is set.
        stoploss_pct: Stop distance in percent of ``price``.
        target_enabled: Whether a target is set.
        target_pct: Target distance in percent of ``price``.

    Returns:
        Stop below / target above the price for a long, the reverse for a short;
        ``None`` for a level that is not enabled.
    """
    sign = -1.0 if direction == ExecutionEnums.TradeDirection.SHORT else 1.0
    stop = price * (1.0 - sign * stoploss_pct / 100.0) if stoploss_enabled else None
    target = price * (1.0 + sign * target_pct / 100.0) if target_enabled else None
    return stop, target
