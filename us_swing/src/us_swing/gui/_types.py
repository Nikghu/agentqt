"""GUI types — re-exports from the canonical infrastructure models.

All dataclasses are defined in ``us_swing.data.models`` (single source of
truth).  This module exists only so that existing GUI imports
``from us_swing.gui._types import X`` continue to work without change.
"""
from us_swing.data.models import (  # noqa: F401
    AccountState,
    FilteredStockEntry,
    OpenPosition,
    PositionRecord,
    RiskConfig,
    ScreenerResult,
    TradeRecord,
    TradeSignal,
    TradingMode,
    UserProfile,
)

__all__ = [
    "AccountState",
    "FilteredStockEntry",
    "OpenPosition",
    "PositionRecord",
    "RiskConfig",
    "ScreenerResult",
    "TradeRecord",
    "TradeSignal",
    "TradingMode",
    "UserProfile",
]
