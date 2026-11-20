"""
Module: MD-GUI-045.001.M01 — gui/chart_plan.py (chart plan strategy builder)
Parent SRD: SRD-GUI-045.001

Builds the one-stock, one-trade auto strategy that Charts → Send to Execution
creates from the trade plan (Entry / Stop / Target).
"""
from __future__ import annotations

import datetime

from us_swing.gui.chart_inspector import plan_size
from us_swing.gui.strategy_store import StrategyConfig

CHART_PLAN_TYPE = "chart_plan"
_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


def chart_plan_name(symbol: str) -> str:
    """Strategy name used for *symbol*'s chart plan."""
    return f"Chart plan - {symbol}"


def is_chart_plan(cfg: StrategyConfig) -> bool:
    """True when *cfg* was made by Send to Execution."""
    return cfg.strategy_type == CHART_PLAN_TYPE


def is_expired(cfg: StrategyConfig, today: datetime.date) -> bool:
    """True when a chart plan's buy day is over."""
    return is_chart_plan(cfg) and cfg.end_date < today.isoformat()


def capital_pct(entry: float, stop: float, risk_pct: float,
                equity: float, capital: float) -> int:
    """Capital % that buys the same shares as the Inspector's risk size.

    Args:
        entry: Plan entry price.
        stop: Plan stop price (below entry).
        risk_pct: Account risk per trade, in percent.
        equity: Account equity the risk size is based on.
        capital: Dollar budget the strategy engine sizes from.

    Returns:
        Whole percent from 1 to 100.
    """
    if capital <= 0:
        return 1
    pct = round(plan_size(entry, stop, equity, risk_pct) * entry / capital * 100)
    return max(1, min(100, pct))


def build_chart_plan(symbol: str, entry: float, stop: float, target: float,
                     capital_max: int, today: datetime.date) -> StrategyConfig:
    """Return the auto strategy that buys *symbol* once above *entry* today.

    Stop and target are stored as percent of the buy price, measured from *entry*.
    """
    day = today.isoformat()
    return StrategyConfig(
        name=chart_plan_name(symbol),
        mode="auto",
        capital_max=capital_max,
        start_time="09:30",
        end_time="16:00",
        start_date=day,
        end_date=day,
        days=list(_WEEKDAYS),
        entry_condition=f"Price('Stock', 'current', 'close', '3m') > {entry:.2f}",
        exit_condition="",
        strategy_type=CHART_PLAN_TYPE,
        symbol_mode="include",
        symbols_include=[symbol],
        target_enabled=True,
        target_type="fixed",
        target_value=round((target - entry) / entry * 100, 2),
        stoploss_enabled=True,
        stoploss_type="fixed",
        stoploss_value=round((entry - stop) / entry * 100, 2),
        auto_trade=True,
        trade_type="Positional",
        minute_close=3,
        rex_count=0,
        per_trade_pct=100,
        run_state="RUNNING",
        direction="LONG",
    )
