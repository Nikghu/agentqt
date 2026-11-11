"""
Module: MD-MKT-015.002.M02 — market/setup_knobs.py
Parent SRD: SRD-MKT-015.002

Named limits of the desk setups: each knob has today's value as its default and a fixed
range a setup tuning ticket may try. The setup rules read their limits from here, so live
picks stay the same until someone changes a default by hand.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

Values = Mapping[str, float]


@dataclass(frozen=True)
class Knob:
    """One setup limit: today's value and the range a test may try."""

    name: str
    default: float
    low: float
    high: float
    whole: bool = False


KNOBS: dict[str, tuple[Knob, ...]] = {
    "Squeeze": (Knob("width_vs_min", 1.1, 1.0, 1.5), Knob("atr_ratio", 0.8, 0.5, 1.0)),
    "Flat base": (Knob("near_high", 0.9, 0.8, 0.97), Knob("depth", 0.15, 0.08, 0.25)),
    "Pullback": (Knob("near_sma", 1.02, 1.0, 1.05), Knob("sma_days", 21, 10, 50, True)),
    "Failed breakout": (Knob("pivot_days", 25, 10, 50, True),
                        Knob("recent_days", 10, 5, 20, True)),
    "Lower highs": (Knob("swing_days", 10, 5, 20, True),),
    "Breakdown": (Knob("volume_x", 1.5, 1.0, 3.0),),
}
LONG_SETUPS: tuple[str, ...] = ("Squeeze", "Flat base", "Pullback")
SHORT_SETUPS: tuple[str, ...] = ("Failed breakout", "Lower highs", "Breakdown")


def _knob(setup: str, name: str) -> Knob:
    return next(k for k in KNOBS[setup] if k.name == name)


def knob_value(values: Mapping[str, Values] | None, setup: str, name: str) -> float:
    """Return the tested value of a knob, or its default when the test does not change it."""
    knob = _knob(setup, name)
    value = float((values or {}).get(setup, {}).get(name, knob.default))
    return float(round(value)) if knob.whole else value


def window(values: Mapping[str, Values] | None, setup: str, name: str) -> int:
    """Return a whole-number knob (a day count) as an ``int``."""
    return int(knob_value(values, setup, name))


def side_of(setup: str) -> str:
    """Return ``long`` or ``short`` for a desk setup name."""
    return "long" if setup in LONG_SETUPS else "short"


def check_changes(setup: str, changes: Mapping[str, float]) -> dict[str, float]:
    """Keep the changes that name a knob of ``setup`` and sit inside its range.

    Whole-number knobs are rounded; a change equal to the default is dropped.
    """
    known = {k.name: k for k in KNOBS.get(setup, ())}
    kept: dict[str, float] = {}
    for name, value in changes.items():
        knob = known.get(name)
        if knob is None:
            continue
        value = float(round(value)) if knob.whole else float(value)
        if knob.low <= value <= knob.high and value != knob.default:
            kept[name] = value
    return kept


def knobs_text() -> str:
    """One line per setup listing its knobs as name default (low to high)."""
    lines = []
    for setup, knobs in KNOBS.items():
        parts = ", ".join(f"{k.name} {k.default:g} ({k.low:g} to {k.high:g})" for k in knobs)
        lines.append(f"{setup} ({side_of(setup)}): {parts}")
    return "\n".join(lines)
