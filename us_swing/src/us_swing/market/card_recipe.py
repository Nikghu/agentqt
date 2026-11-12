"""
Module: MD-MKT-019.003.M02 — market/card_recipe.py
Parent SRD: SRD-MKT-019.003
Also: SRD-MKT-019.004 (recipe check)

The test recipe of a strategy card. The AI may use only the daily indicator rules and price
patterns of the shared catalogues; code checks every block, setting and stop before any
replay runs, and names what it cannot test.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from us_swing.core.indicator_rules import CATALOGUE, Condition, IndicatorSpec, ParamSpec
from us_swing.core.price_patterns import PATTERNS, PatternSpec

MAX_INDICATORS = 4
MAX_PATTERNS = 3
STOP_RANGES: dict[str, tuple[float, float]] = {
    "n_day": (2, 60), "atr": (0.5, 5), "percent": (1, 20)}


def daily_indicators() -> dict[str, IndicatorSpec]:
    """Indicators that daily bars alone can compute, by id."""
    return {s.id: s for s in CATALOGUE if s.compute is not None and s.context == "none"}


def daily_patterns() -> dict[str, PatternSpec]:
    """Price patterns that can be checked now, by id."""
    return {p.id: p for p in PATTERNS if p.available}


class IndicatorBlock(BaseModel):
    """One indicator rule of the recipe."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(max_length=40)
    condition: str = Field(max_length=20)
    value: float | None = None
    to: float | None = None
    params: dict[str, float] = Field(default_factory=dict)


class PatternBlock(BaseModel):
    """One price pattern of the recipe."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(max_length=40)
    params: dict[str, float] = Field(default_factory=dict)


class StopBlock(BaseModel):
    """Where the stop goes."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["signal_bar", "n_day", "atr", "percent"]
    n: float = 0.0


class Recipe(BaseModel):
    """The model's answer for the recipe step."""

    model_config = ConfigDict(extra="forbid")

    side: Literal["long", "short"]
    indicators: list[IndicatorBlock] = Field(default_factory=list, max_length=MAX_INDICATORS)
    patterns: list[PatternBlock] = Field(default_factory=list, max_length=MAX_PATTERNS)
    entry: Literal["next_open", "signal_break"]
    stop: StopBlock
    unmapped: list[str] = Field(default_factory=list, max_length=6,
                                description="card parts no block can express")


def _param_line(params: tuple[ParamSpec, ...]) -> str:
    return ", ".join(f"{p.key} {p.min:g}-{p.max:g} (default {p.default:g})" for p in params)


def block_menu() -> str:
    """The blocks the recipe may use, one line each."""
    lines = ["Indicator rules (id: conditions; value range; settings):"]
    for spec in daily_indicators().values():
        conds = "/".join(c.value for c in spec.conditions)
        settings = _param_line(spec.params)
        lines.append(f"- {spec.id}: {conds}; {spec.value_min:g} to {spec.value_max:g}"
                     + (f"; {settings}" if settings else ""))
    lines.append("Price patterns (id: settings):")
    for pat in daily_patterns().values():
        settings = _param_line(pat.params)
        lines.append(f"- {pat.id}" + (f": {settings}" if settings else ""))
    lines.append("Entry: next_open (buy the next day's open) or signal_break (the next days "
                 "break the signal day's high, or low for shorts).")
    lines.append("Stop: signal_bar (signal day's low or high), n_day (lowest low or highest "
                 "high of n days, n 2-60), atr (n x ATR14, n 0.5-5), percent (n 1-20).")
    return "\n".join(lines)


def _settings(name: str, params: tuple[ParamSpec, ...], given: Mapping[str, float]
              ) -> list[str]:
    known = {p.key: p for p in params}
    out = [f"{name} has no setting {k}" for k in given if k not in known]
    out += [f"{name} {k} {v:g} is outside {known[k].min:g}-{known[k].max:g}"
            for k, v in given.items() if k in known and not known[k].min <= v <= known[k].max]
    return out


def _indicator(block: IndicatorBlock, specs: Mapping[str, IndicatorSpec]) -> list[str]:
    spec = specs.get(block.id)
    if spec is None:
        return [f"{block.id} has no block"]
    try:
        cond = Condition(block.condition)
    except ValueError:
        cond = None
    if cond is None or cond not in spec.conditions:
        return [f"{block.id} cannot use the condition {block.condition}"]
    problems = _settings(block.id, spec.params, block.params)
    if cond.needs_value:
        values = [block.value, block.to] if cond.needs_to else [block.value]
        if any(v is None for v in values):
            problems.append(f"{block.id} {cond.value} needs a value")
        elif any(not spec.value_min <= float(v) <= spec.value_max for v in values if v is not None):
            problems.append(f"{block.id} value is outside {spec.value_min:g} to "
                            f"{spec.value_max:g}")
    return problems


def check_recipe(recipe: Recipe) -> list[str]:
    """Every reason the recipe cannot be tested; empty when it can."""
    problems = [f"{part.strip()} has no block" for part in recipe.unmapped if part.strip()]
    specs, patterns = daily_indicators(), daily_patterns()
    for block in recipe.indicators:
        problems += _indicator(block, specs)
    for pat in recipe.patterns:
        spec = patterns.get(pat.id)
        problems += ([f"{pat.id} has no block"] if spec is None
                     else _settings(pat.id, spec.params, pat.params))
    if not recipe.indicators and not recipe.patterns:
        problems.append("the entry has no block")
    low_high = STOP_RANGES.get(recipe.stop.kind)
    if low_high and not low_high[0] <= recipe.stop.n <= low_high[1]:
        problems.append(f"the {recipe.stop.kind} stop {recipe.stop.n:g} is outside "
                        f"{low_high[0]:g}-{low_high[1]:g}")
    return problems


def recipe_text(recipe: Recipe) -> str:
    """One plain line describing the recipe, for logs and results."""
    stop = recipe.stop.kind.replace("_", " ") + (f" {recipe.stop.n:g}" if recipe.stop.n else "")
    blocks = [b.id for b in recipe.indicators] + [p.id for p in recipe.patterns]
    return (f"{recipe.side}; entry blocks {', '.join(blocks) or 'none'}; "
            f"{recipe.entry.replace('_', ' ')}; {stop} stop")
