"""
Module: MD-SCR-016.001.M27 — core/price_patterns/_spec.py
Parent SRD: SRD-SCR-016.001

Pattern spec types, kept apart from the assembled catalogue so the candle and
breakout modules can build specs without an import cycle.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum

from us_swing.core.indicator_rules import BarArrays, ParamSpec

Detect = Callable[[BarArrays, Mapping[str, float]], bool]
MinBars = Callable[[Mapping[str, float]], int]


class PatternRuleError(ValueError):
    """Raised for unknown patterns or malformed pattern rules."""


class PatternCategory(Enum):
    """Library categories, in display order."""

    BULLISH_CANDLES = "Bullish candles"
    BEARISH_CANDLES = "Bearish candles"
    NEUTRAL_CANDLES = "Neutral candles"
    BREAKOUT = "Breakout"
    TREND = "Trend"
    VOLATILITY = "Volatility"
    CHART_SHAPES = "Chart shapes"


class Direction(Enum):
    """Which way a pattern points."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


@dataclass(frozen=True, slots=True)
class PatternSpec:
    """Catalogue entry describing one price action pattern."""

    id: str
    name: str
    short: str
    category: PatternCategory
    direction: Direction
    description: str
    params: tuple[ParamSpec, ...]
    min_bars: MinBars
    detect: Detect
    available: bool = True
    unavailable_reason: str = ""
