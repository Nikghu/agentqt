"""
Module: MD-EXE-011.001.M10 — signal_bridge
Parent SRD: SRD-EXE-011.009
"""
from __future__ import annotations

from us_swing.data.models import TradeSignal as GuiTradeSignal
from us_swing.execution.strategy_engine._signals import Action
from us_swing.execution.strategy_engine._signals import TradeSignal as EngineSignal


def engine_to_gui(ts: EngineSignal) -> GuiTradeSignal:
    """Convert an engine TradeSignal to the GUI TradeSignal model."""
    return GuiTradeSignal(
        symbol=ts.symbol,
        side="BUY" if ts.action == Action.ENTRY else "SELL",
        strategy_id=ts.strategy_id,
        score=0.0,
        entry_price=ts.entry_price or 0.0,
        stop_loss=ts.stop_loss or 0.0,
        target_price=ts.target or 0.0,
        recommended_qty=ts.qty_recommended,
        signal_id=ts.signal_id,
    )
