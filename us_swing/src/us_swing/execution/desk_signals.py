"""
Module: MD-EXE-021.002.M01 — execution/desk_signals.py
Parent SRD: SRD-EXE-021.002
Also: SRD-EXE-021.004 (close time of a desk signal)

Pending entry signals built from lead picks the Master user approved in AI Desk. They
all belong to one fixed strategy, "AI Desk", which never makes signals by itself.
"""
from __future__ import annotations

from datetime import date, datetime, time

from us_swing.core.desk_trades import TradePick
from us_swing.core.econ_calendar import next_trading_day
from us_swing.data.market_calendar import ET
from us_swing.execution.strategy_engine._signals import Action, TradeSignal

AI_DESK_STRATEGY = "AI Desk"
AI_DESK_TYPE = "ai_desk"
_PREFIX = "desk:"
_CLOSE = time(16, 0)
_REASON_MAX = 200


def desk_signal_id(pick: TradePick) -> str:
    """The pending signal id of a pick: ``desk:day:side:symbol``."""
    return f"{_PREFIX}{pick.subject}"


def build_desk_signal(pick: TradePick, qty: int, user_id: int) -> TradeSignal:
    """One ENTRY signal for the AI Desk strategy with the pick's levels."""
    return TradeSignal(
        action=Action.ENTRY,
        symbol=pick.symbol,
        strategy_id=AI_DESK_STRATEGY,
        entry_price=pick.entry,
        stop_loss=pick.stop,
        target=pick.target,
        qty_recommended=qty,
        user_id=user_id,
        reason=f"AI Desk pick {pick.day} rank {pick.rank}: {pick.reason}"[:_REASON_MAX],
        signal_id=desk_signal_id(pick),
        direction=pick.side.upper(),
    )


def desk_signal_close(signal_id: str) -> datetime | None:
    """Market close of a desk signal's trading day; ``None`` for any other id."""
    if not signal_id.startswith(_PREFIX):
        return None
    try:
        day = date.fromisoformat(signal_id[len(_PREFIX):].split(":", 1)[0])
    except ValueError:
        return None
    return datetime.combine(next_trading_day(day), _CLOSE, tzinfo=ET)
