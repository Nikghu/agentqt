"""
Module: MD-EXE-022.001.M01 — usswing parameters
Parent SRD: SRD-EXE-022.002
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


class ParameterError(ValueError):
    """A parameter is declared or used wrongly; the message starts with its label."""


def _show(value: float) -> str:
    return f"{value:g}"


@dataclass(frozen=True)
class Number:
    """A number box in the trigger popup.

    Args:
        label: Text shown in the popup and used by ``self.parameter(label)``.
        default: Value the popup starts with.
        minimum: Lowest allowed value.
        maximum: Highest allowed value.
        whole_number: True for counts such as candles; values are then ints.
    """

    label: str
    default: float
    minimum: float
    maximum: float
    whole_number: bool = False

    def __post_init__(self) -> None:
        if not str(self.label).strip():
            raise ParameterError("A parameter needs a label")
        if self.minimum > self.maximum:
            raise ParameterError(
                f"{self.label}: minimum {_show(self.minimum)} is above maximum "
                f"{_show(self.maximum)}")
        if self.whole_number and any(
                float(v) != math.floor(v) for v in (self.default, self.minimum, self.maximum)):
            raise ParameterError(f"{self.label}: default, minimum and maximum must be whole "
                                 f"numbers")
        if not self.minimum <= self.default <= self.maximum:
            raise ParameterError(
                f"{self.label}: default {_show(self.default)} is outside "
                f"{_show(self.minimum)} to {_show(self.maximum)}")

    def convert(self, raw: Any) -> int | float:
        """Turn a popup or expression value into a checked number."""
        try:
            value = float(raw)
        except (TypeError, ValueError):
            raise ParameterError(f"{self.label} must be a number, got {raw!r}") from None
        if self.whole_number and value != math.floor(value):
            raise ParameterError(f"{self.label} must be a whole number, got {_show(value)}")
        if not self.minimum <= value <= self.maximum:
            raise ParameterError(f"{self.label} must be {_show(self.minimum)} to "
                                 f"{_show(self.maximum)}, got {_show(value)}")
        return int(value) if self.whole_number else value


@dataclass(frozen=True)
class Input:
    """A dropdown in the trigger popup.

    Args:
        label: Text shown in the popup and used by ``self.parameter(label)``.
        options: The choices, in the order shown.
        default: The choice the popup starts with; must be one of ``options``.
    """

    label: str
    options: Sequence[str]
    default: str

    def __post_init__(self) -> None:
        options = tuple(str(option) for option in self.options)
        object.__setattr__(self, "options", options)
        if not str(self.label).strip():
            raise ParameterError("A parameter needs a label")
        if not options:
            raise ParameterError(f"{self.label}: needs at least one option")
        if len(set(options)) != len(options):
            raise ParameterError(f"{self.label}: options must not repeat")
        if self.default not in options:
            raise ParameterError(f"{self.label}: default {self.default!r} is not one of "
                                 f"{', '.join(options)}")

    def convert(self, raw: Any) -> str:
        """Return ``raw`` as text when it is one of the options."""
        text = str(raw)
        if text not in self.options:
            raise ParameterError(f"{self.label} must be one of {', '.join(self.options)}, "
                                 f"got {raw!r}")
        return text


Parameter = Number | Input


def resolve_values(parameters: Sequence[Parameter], values: dict[str, Any]) -> dict[str, Any]:
    """Checked value per label: the given value, else the default."""
    known = {p.label for p in parameters}
    for label in values:
        if label not in known:
            raise ParameterError(f"Unknown parameter {label!r}")
    return {p.label: p.convert(values.get(p.label, p.default)) for p in parameters}
