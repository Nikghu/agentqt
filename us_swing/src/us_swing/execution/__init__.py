"""Execution & Risk Management package."""
from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

from us_swing.execution._enums import ExecutionEnums

if TYPE_CHECKING:
    from us_swing.execution.intraday_candle_loader import (
        CandleLoadResult,
        IntradayCandleLoader,
        SymbolReadiness,
    )
    from us_swing.execution.live_bar_worker import LiveBarWorker

__all__ = [
    "CandleLoadResult",
    "ExecutionEnums",
    "IntradayCandleLoader",
    "LiveBarWorker",
    "SymbolReadiness",
]

# The candle / live-bar workers import PyQt6.  They are loaded lazily (PEP 562)
# so that `import us_swing.execution` stays Qt-free, letting the headless `core/`
# layer import `ExecutionEnums` without pulling in the GUI framework
# (SRD-EXE-009.012 Qt-free boundary).
_LAZY_SUBMODULES = {
    "CandleLoadResult": "us_swing.execution.intraday_candle_loader",
    "IntradayCandleLoader": "us_swing.execution.intraday_candle_loader",
    "SymbolReadiness": "us_swing.execution.intraday_candle_loader",
    "LiveBarWorker": "us_swing.execution.live_bar_worker",
}


def __getattr__(name: str) -> Any:
    module_path = _LAZY_SUBMODULES.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(importlib.import_module(module_path), name)
