"""
Module: MD-SCR-015.001.M23 — core/indicator_rules/_catalogue.py
Parent SRD: SRD-SCR-015.001

The indicator catalogue shared by the screener engine and the GUI rule dialog.
Adding a daily indicator means adding one ``IndicatorSpec`` here.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Literal, Mapping

from us_swing.core.indicator_rules import _ta
from us_swing.core.indicator_rules._ta import BarArrays, Series

ComputeFn = Callable[[BarArrays, Mapping[str, float]], Series]
ContextKind = Literal["none", "rs", "market_cap"]


class IndicatorRuleError(ValueError):
    """Raised for unknown indicators, unavailable indicators or malformed rules."""


class Category(Enum):
    """Library categories, in display order."""

    PRICE = "Price"
    MOMENTUM = "Momentum"
    TREND = "Trend"
    VOLATILITY = "Volatility"
    VOLUME = "Volume"
    RELATIVE_STRENGTH = "Relative strength"
    FUNDAMENTALS = "Fundamentals"
    DIVIDENDS = "Dividends"
    OTHERS = "Others"


class Condition(Enum):
    """How a rule compares an indicator; the value is the stored string."""

    AT_LEAST = "at_least"
    AT_MOST = "at_most"
    BETWEEN = "between"
    CROSSES_ABOVE = "crosses_above"
    CROSSES_BELOW = "crosses_below"
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    IS_TRUE = "is_true"

    @property
    def label(self) -> str:
        """Text shown in the GUI condition list."""
        return _CONDITION_LABELS[self]

    @property
    def needs_value(self) -> bool:
        """True when the condition compares against a Value."""
        return self in (Condition.AT_LEAST, Condition.AT_MOST, Condition.BETWEEN)

    @property
    def needs_to(self) -> bool:
        """True when the condition also needs an upper To value."""
        return self is Condition.BETWEEN


_CONDITION_LABELS: dict[Condition, str] = {
    Condition.AT_LEAST: "at least",
    Condition.AT_MOST: "at most",
    Condition.BETWEEN: "between",
    Condition.CROSSES_ABOVE: "crosses above signal",
    Condition.CROSSES_BELOW: "crosses below signal",
    Condition.PRICE_ABOVE: "price above",
    Condition.PRICE_BELOW: "price below",
    Condition.IS_TRUE: "is true",
}


@dataclass(frozen=True, slots=True)
class ParamSpec:
    """One editable indicator parameter."""

    key: str
    label: str
    kind: Literal["int", "float"]
    default: float
    min: float
    max: float
    step: float = 1.0
    display: str = "{}"

    def __post_init__(self) -> None:
        if not self.min <= self.default <= self.max:
            raise ValueError(
                f"Parameter '{self.key}' default {self.default} is outside {self.min}–{self.max}"
            )


@dataclass(frozen=True, slots=True)
class IndicatorSpec:
    """Catalogue entry describing one indicator."""

    id: str
    name: str
    short: str
    category: Category
    description: str
    params: tuple[ParamSpec, ...]
    conditions: tuple[Condition, ...]
    default_value: float | None
    default_to: float | None
    value_min: float
    value_max: float
    unit: str
    compute: ComputeFn | None
    context: ContextKind = "none"
    summary_params: bool = False
    available: bool = True
    unavailable_reason: str = ""


# ── Compute functions ─────────────────────────────────────────────────────────

def _p(params: Mapping[str, float], key: str) -> int:
    return int(params[key])


def _price(a: BarArrays, p: Mapping[str, float]) -> Series:
    return Series(a.close)


def _atr_pct(a: BarArrays, p: Mapping[str, float]) -> Series:
    return Series(_ta.atr_pct(a.high, a.low, a.close, _p(p, "period")))


def _rsi(a: BarArrays, p: Mapping[str, float]) -> Series:
    return Series(_ta.rsi(a.close, _p(p, "period")))


def _macd(a: BarArrays, p: Mapping[str, float]) -> tuple[_ta.FloatArray, ...]:
    return _ta.macd(a.close, _p(p, "fast"), _p(p, "slow"), _p(p, "signal"))


def _ppo(a: BarArrays, p: Mapping[str, float]) -> tuple[_ta.FloatArray, ...]:
    return _ta.ppo(a.close, _p(p, "fast"), _p(p, "slow"), _p(p, "signal"))


def _macd_line(a: BarArrays, p: Mapping[str, float]) -> Series:
    line, sig, _ = _macd(a, p)
    return Series(line, sig)


def _macd_hist(a: BarArrays, p: Mapping[str, float]) -> Series:
    return Series(_macd(a, p)[2])


def _macd_signal(a: BarArrays, p: Mapping[str, float]) -> Series:
    return Series(_macd(a, p)[1])


def _ppo_line(a: BarArrays, p: Mapping[str, float]) -> Series:
    line, sig, _ = _ppo(a, p)
    return Series(line, sig)


def _ppo_hist(a: BarArrays, p: Mapping[str, float]) -> Series:
    return Series(_ppo(a, p)[2])


def _ppo_signal(a: BarArrays, p: Mapping[str, float]) -> Series:
    return Series(_ppo(a, p)[1])


def _ema_fn(period: int) -> ComputeFn:
    def compute(a: BarArrays, p: Mapping[str, float]) -> Series:
        return Series(_ta.ema(a.close, period))
    return compute


def _price_ema_fn(period: int) -> ComputeFn:
    def compute(a: BarArrays, p: Mapping[str, float]) -> Series:
        avg = _ta.ema(a.close, period)
        return Series(_ta.safe_div(a.close, avg) * 100.0)
    return compute


def _breakout(a: BarArrays, p: Mapping[str, float]) -> Series:
    return Series(_ta.n_bar_breakout(a.close, _p(p, "lookback")))


def _volume_ratio(a: BarArrays, p: Mapping[str, float]) -> Series:
    return Series(_ta.volume_ratio(a.volume, _p(p, "period")))


# ── Shared parameter and condition sets ───────────────────────────────────────

def _period(default: int) -> ParamSpec:
    return ParamSpec("period", "Period", "int", default, 2, 200, display="period {}")


_MACD_PARAMS = (
    ParamSpec("fast", "Fast", "int", 12, 2, 100),
    ParamSpec("slow", "Slow", "int", 26, 3, 200),
    ParamSpec("signal", "Signal", "int", 9, 2, 100),
)
_RANGE = (Condition.AT_LEAST, Condition.AT_MOST, Condition.BETWEEN)
_CROSS = (Condition.CROSSES_ABOVE, Condition.CROSSES_BELOW, Condition.AT_LEAST, Condition.AT_MOST)
_INTRADAY_REASON = "needs intraday data"


def _ema_spec(period: int) -> IndicatorSpec:
    return IndicatorSpec(
        id=f"ema_{period}", name=f"EMA({period})", short=f"EMA({period})",
        category=Category.TREND,
        description=f"{period}-day exponential moving average of the close.",
        params=(), conditions=(Condition.PRICE_ABOVE, Condition.PRICE_BELOW),
        default_value=None, default_to=None, value_min=0.0, value_max=100_000.0,
        unit="$", compute=_ema_fn(period),
    )


def _price_ema_spec(period: int) -> IndicatorSpec:
    return IndicatorSpec(
        id=f"price_ema_{period}", name=f"Price/EMA({period})", short=f"Price/EMA({period})",
        category=Category.TREND,
        description=f"Close as a percentage of its {period}-day EMA.",
        params=(), conditions=_RANGE,
        default_value=100.0, default_to=None, value_min=0.0, value_max=1000.0,
        unit="%", compute=_price_ema_fn(period),
    )


def _intraday_spec(id_: str, name: str) -> IndicatorSpec:
    return IndicatorSpec(
        id=id_, name=name, short=name, category=Category.VOLUME,
        description=f"{name} from intraday candles.",
        params=(), conditions=(Condition.AT_LEAST,),
        default_value=1.0, default_to=None, value_min=0.0, value_max=100.0,
        unit="×", compute=None, available=False, unavailable_reason=_INTRADAY_REASON,
    )


CATALOGUE: tuple[IndicatorSpec, ...] = (
    IndicatorSpec(
        id="price", name="Price", short="Price", category=Category.PRICE,
        description="Last close in USD.",
        params=(), conditions=(Condition.BETWEEN, Condition.AT_LEAST, Condition.AT_MOST),
        default_value=5.0, default_to=5000.0, value_min=0.0, value_max=100_000.0,
        unit="$", compute=_price,
    ),
    IndicatorSpec(
        id="rsi", name="RSI", short="RSI", category=Category.MOMENTUM,
        description="Wilder Relative Strength Index.",
        params=(_period(14),),
        conditions=(Condition.BETWEEN, Condition.AT_LEAST, Condition.AT_MOST),
        default_value=30.0, default_to=70.0, value_min=0.0, value_max=100.0,
        unit="", compute=_rsi, summary_params=True,
    ),
    IndicatorSpec(
        id="macd", name="MACD", short="MACD", category=Category.MOMENTUM,
        description="MACD line; crosses compare it with its signal line.",
        params=_MACD_PARAMS, conditions=_CROSS,
        default_value=0.0, default_to=None, value_min=-1000.0, value_max=1000.0,
        unit="", compute=_macd_line,
    ),
    IndicatorSpec(
        id="macd_hist", name="MACD Histogram", short="MACD Hist", category=Category.MOMENTUM,
        description="MACD line minus its signal line.",
        params=_MACD_PARAMS, conditions=_RANGE,
        default_value=0.0, default_to=None, value_min=-1000.0, value_max=1000.0,
        unit="", compute=_macd_hist,
    ),
    IndicatorSpec(
        id="macd_signal", name="MACD Signal Line", short="MACD Signal",
        category=Category.MOMENTUM, description="EMA of the MACD line.",
        params=_MACD_PARAMS, conditions=_RANGE,
        default_value=0.0, default_to=None, value_min=-1000.0, value_max=1000.0,
        unit="", compute=_macd_signal,
    ),
    IndicatorSpec(
        id="ppo", name="PPO", short="PPO", category=Category.MOMENTUM,
        description="Percentage Price Oscillator; crosses compare it with its signal line.",
        params=_MACD_PARAMS, conditions=_CROSS,
        default_value=0.0, default_to=None, value_min=-100.0, value_max=100.0,
        unit="%", compute=_ppo_line,
    ),
    IndicatorSpec(
        id="ppo_hist", name="PPO Histogram", short="PPO Hist", category=Category.MOMENTUM,
        description="PPO minus its signal line.",
        params=_MACD_PARAMS, conditions=_RANGE,
        default_value=0.0, default_to=None, value_min=-100.0, value_max=100.0,
        unit="%", compute=_ppo_hist,
    ),
    IndicatorSpec(
        id="ppo_signal", name="PPO Signal Line", short="PPO Signal",
        category=Category.MOMENTUM, description="EMA of the PPO line.",
        params=_MACD_PARAMS, conditions=_RANGE,
        default_value=0.0, default_to=None, value_min=-100.0, value_max=100.0,
        unit="%", compute=_ppo_signal,
    ),
    _ema_spec(20), _ema_spec(50), _ema_spec(100), _ema_spec(200),
    _price_ema_spec(20), _price_ema_spec(50), _price_ema_spec(100),
    IndicatorSpec(
        id="breakout", name="Breakout (N-bar high)", short="Breakout", category=Category.TREND,
        description="Close is above the highest close of the previous N bars.",
        params=(ParamSpec("lookback", "Lookback bars", "int", 10, 1, 252, display="{} bars"),),
        conditions=(Condition.IS_TRUE,),
        default_value=None, default_to=None, value_min=0.0, value_max=1.0,
        unit="", compute=_breakout,
    ),
    IndicatorSpec(
        id="atr_pct", name="ATR %", short="ATR", category=Category.VOLATILITY,
        description="Wilder Average True Range as a percentage of the close.",
        params=(_period(14),), conditions=_RANGE,
        default_value=1.0, default_to=None, value_min=0.0, value_max=100.0,
        unit="%", compute=_atr_pct,
    ),
    IndicatorSpec(
        id="volume_ratio", name="Volume ratio", short="Vol", category=Category.VOLUME,
        description="Last volume divided by the average of the previous N days.",
        params=(ParamSpec("period", "MA period", "int", 10, 2, 200, display="MA {}"),),
        conditions=(Condition.AT_LEAST, Condition.AT_MOST),
        default_value=1.0, default_to=None, value_min=0.0, value_max=100.0,
        unit="×", compute=_volume_ratio,
    ),
    IndicatorSpec(
        id="rvol_1d", name="RVOL (1 Day)", short="RVOL", category=Category.VOLUME,
        description="Relative volume: last day's volume vs its 20-day average.",
        params=(ParamSpec("period", "Lookback days", "int", 20, 2, 200, display="{} days"),),
        conditions=(Condition.AT_LEAST, Condition.AT_MOST),
        default_value=1.5, default_to=None, value_min=0.0, value_max=100.0,
        unit="×", compute=_volume_ratio,
    ),
    _intraday_spec("rvol_3m", "RVOL (3 Min)"),
    _intraday_spec("rvol_5m", "RVOL (5 Min)"),
    _intraday_spec("rvol_10m", "RVOL (10 Min)"),
    _intraday_spec("stvol_3m", "Short-Term Volume 3 Min"),
    _intraday_spec("stvol_5m", "Short-Term Volume 5 Min"),
    _intraday_spec("stvol_10m", "Short-Term Volume 10 Min"),
    IndicatorSpec(
        id="rs_index", name="RS Index", short="RS", category=Category.RELATIVE_STRENGTH,
        description="252-day return percentile vs the universe, with optional RS-line slope.",
        params=(
            ParamSpec("slope_days", "Slope days (0 = off)", "int", 63, 0, 252,
                      display="slope {} d"),
        ),
        conditions=(Condition.AT_LEAST,),
        default_value=70.0, default_to=None, value_min=0.0, value_max=100.0,
        unit="", compute=None, context="rs",
    ),
    IndicatorSpec(
        id="market_cap", name="Market Cap", short="MCap", category=Category.FUNDAMENTALS,
        description="Market capitalisation in billions of USD.",
        params=(), conditions=_RANGE,
        default_value=10.0, default_to=None, value_min=0.0, value_max=10_000.0,
        unit="$B", compute=None, context="market_cap",
    ),
)

_BY_ID: dict[str, IndicatorSpec] = {spec.id: spec for spec in CATALOGUE}


def get_spec(indicator_id: str) -> IndicatorSpec:
    """Return the catalogue entry for ``indicator_id``.

    Raises:
        IndicatorRuleError: If the id is not in the catalogue.
    """
    try:
        return _BY_ID[indicator_id]
    except KeyError:
        raise IndicatorRuleError(f"Unknown indicator: {indicator_id}") from None
