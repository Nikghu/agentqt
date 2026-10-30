"""
Module: MD-BKT-002.020.M09 — core/expr
Parent SRD: SRD-BKT-002.020

Shared strategy condition parser. Re-exports the live parser from
``execution/strategy_engine/_evaluator.py`` so the backtest parses conditions
exactly like live trading; the live code is not moved or changed.
"""
from __future__ import annotations

from typing import Any

import us_swing.data  # noqa: F401 — loads db/data in the order that avoids their import cycle
from us_swing.execution.strategy_engine._evaluator import (
    ConditionEvaluator,
    EvaluatorError,
    _Parser,
    _tokenize,
)

__all__ = ["ConditionEvaluator", "EvaluatorError", "parse"]


def parse(expr: str) -> dict[str, Any]:
    """Return the live parser's AST (plain dicts) for a condition."""
    return _Parser(_tokenize(expr)).parse()
