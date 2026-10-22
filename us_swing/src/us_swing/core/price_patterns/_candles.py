"""
Module: MD-SCR-016.003.M28 — core/price_patterns/_candles.py
Parent SRD: SRD-SCR-016.003

The 27 candlestick patterns, built from TA-Lib ``CDL*`` functions.
"""
from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import talib
from talib import abstract

from us_swing.core.indicator_rules import BarArrays, ParamSpec
from us_swing.core.price_patterns._spec import (
    Detect,
    Direction,
    MinBars,
    PatternCategory,
    PatternSpec,
)

_WITHIN = ParamSpec("within", "Within bars", "int", 1, 1, 5, display="{}-bar window")

_BULL = PatternCategory.BULLISH_CANDLES
_BEAR = PatternCategory.BEARISH_CANDLES
_NEUTRAL = PatternCategory.NEUTRAL_CANDLES

_DIRECTION = {_BULL: Direction.BULLISH, _BEAR: Direction.BEARISH, _NEUTRAL: Direction.NEUTRAL}

# id, name, short, category, TA-Lib function, sign (+1 / -1 / 0 = any), description
_CANDLES: tuple[tuple[str, str, str, PatternCategory, str, int, str], ...] = (
    ("hammer", "Hammer", "Hammer", _BULL, "CDLHAMMER", 0,
     "Small body near the high with a long lower shadow after a decline."),
    ("inverted_hammer", "Inverted Hammer", "InvHammer", _BULL, "CDLINVERTEDHAMMER", 0,
     "Small body near the low with a long upper shadow after a decline."),
    ("bullish_engulfing", "Bullish Engulfing", "BullEngulf", _BULL, "CDLENGULFING", 1,
     "A green body fully covers the previous red body."),
    ("piercing_line", "Piercing Line", "Piercing", _BULL, "CDLPIERCING", 0,
     "A green candle opens below and closes above the middle of the previous red body."),
    ("morning_star", "Morning Star", "MornStar", _BULL, "CDLMORNINGSTAR", 0,
     "Red candle, small star, then a strong green candle."),
    ("morning_doji_star", "Morning Doji Star", "MornDoji", _BULL, "CDLMORNINGDOJISTAR", 0,
     "Morning star whose middle candle is a doji."),
    ("bullish_harami", "Bullish Harami", "BullHarami", _BULL, "CDLHARAMI", 1,
     "A small green body inside the previous large red body."),
    ("three_white_soldiers", "Three White Soldiers", "3Soldiers", _BULL, "CDL3WHITESOLDIERS",
     0, "Three rising green candles, each closing near its high."),
    ("three_inside_up", "Three Inside Up", "3InUp", _BULL, "CDL3INSIDE", 1,
     "Bullish harami confirmed by a third candle closing higher."),
    ("three_outside_up", "Three Outside Up", "3OutUp", _BULL, "CDL3OUTSIDE", 1,
     "Bullish engulfing confirmed by a third candle closing higher."),
    ("dragonfly_doji", "Dragonfly Doji", "Dragonfly", _BULL, "CDLDRAGONFLYDOJI", 0,
     "Open, high and close equal with a long lower shadow."),
    ("shooting_star", "Shooting Star", "ShootStar", _BEAR, "CDLSHOOTINGSTAR", 0,
     "Small body near the low with a long upper shadow after a rise."),
    ("hanging_man", "Hanging Man", "HangMan", _BEAR, "CDLHANGINGMAN", 0,
     "Hammer shape that appears after a rise."),
    ("bearish_engulfing", "Bearish Engulfing", "BearEngulf", _BEAR, "CDLENGULFING", -1,
     "A red body fully covers the previous green body."),
    ("dark_cloud_cover", "Dark Cloud Cover", "DarkCloud", _BEAR, "CDLDARKCLOUDCOVER", 0,
     "A red candle opens above and closes below the middle of the previous green body."),
    ("evening_star", "Evening Star", "EveStar", _BEAR, "CDLEVENINGSTAR", 0,
     "Green candle, small star, then a strong red candle."),
    ("evening_doji_star", "Evening Doji Star", "EveDoji", _BEAR, "CDLEVENINGDOJISTAR", 0,
     "Evening star whose middle candle is a doji."),
    ("bearish_harami", "Bearish Harami", "BearHarami", _BEAR, "CDLHARAMI", -1,
     "A small red body inside the previous large green body."),
    ("three_black_crows", "Three Black Crows", "3Crows", _BEAR, "CDL3BLACKCROWS", 0,
     "Three falling red candles, each closing near its low."),
    ("three_inside_down", "Three Inside Down", "3InDown", _BEAR, "CDL3INSIDE", -1,
     "Bearish harami confirmed by a third candle closing lower."),
    ("three_outside_down", "Three Outside Down", "3OutDown", _BEAR, "CDL3OUTSIDE", -1,
     "Bearish engulfing confirmed by a third candle closing lower."),
    ("gravestone_doji", "Gravestone Doji", "Gravestone", _BEAR, "CDLGRAVESTONEDOJI", 0,
     "Open, low and close equal with a long upper shadow."),
    ("doji", "Doji", "Doji", _NEUTRAL, "CDLDOJI", 0,
     "Open and close almost equal: buyers and sellers in balance."),
    ("spinning_top", "Spinning Top", "SpinTop", _NEUTRAL, "CDLSPINNINGTOP", 0,
     "Small body with upper and lower shadows longer than the body."),
    ("marubozu", "Marubozu", "Marubozu", _NEUTRAL, "CDLMARUBOZU", 0,
     "Long body with almost no shadows."),
    ("three_methods", "Rising/Falling Three Methods", "3Methods", _NEUTRAL,
     "CDLRISEFALL3METHODS", 0, "Long candle, three small pullback candles, then a continuation."),
    ("kicker", "Kicker", "Kicker", _NEUTRAL, "CDLKICKING", 0,
     "Two marubozu candles of opposite colour with a gap between them."),
)


def _detector(function: str, sign: int) -> Detect:
    def detect(arrays: BarArrays, params: Mapping[str, float]) -> bool:
        # Looked up at call time so tests can patch the TA-Lib function
        cdl = getattr(talib, function)
        signal = np.asarray(cdl(arrays.open, arrays.high, arrays.low, arrays.close))
        recent = signal[-int(params["within"]):]
        if sign > 0:
            return bool(np.any(recent > 0))
        if sign < 0:
            return bool(np.any(recent < 0))
        return bool(np.any(recent != 0))

    return detect


def _min_bars(function: str) -> MinBars:
    lookback = int(abstract.Function(function).lookback)  # type: ignore[no-untyped-call]
    return lambda params: lookback + int(params["within"])


def candle_specs() -> tuple[PatternSpec, ...]:
    """Build the candlestick catalogue entries."""
    return tuple(
        PatternSpec(
            id=pid,
            name=name,
            short=short,
            category=category,
            direction=_DIRECTION[category],
            description=description,
            params=(_WITHIN,),
            min_bars=_min_bars(function),
            detect=_detector(function, sign),
        )
        for pid, name, short, category, function, sign, description in _CANDLES
    )
