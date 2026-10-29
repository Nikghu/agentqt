"""
Module: MD-BKT-002.004.M02 — backtest/universe.py
Parent SRD: SRD-BKT-002.004

Resolve a run plan's stock list from universe records (S&P 500, sectors or
names), then apply add and remove.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from us_swing.backtest.spec import UniverseSpec


class UniverseRecord(Protocol):
    """Anything with a symbol and a sector, such as an S&P 500 record."""

    @property
    def symbol(self) -> str: ...

    @property
    def sector(self) -> str: ...


def resolve(spec: UniverseSpec, records: Sequence[UniverseRecord]) -> list[str]:
    """Return the sorted, unique stock list for ``spec``.

    Args:
        spec: Universe part of the run plan.
        records: Universe records; only ``symbol`` and ``sector`` are read.

    Returns:
        Symbols in alphabetical order.
    """
    if spec.mode == "sector":
        wanted = set(spec.sectors)
        chosen = {r.symbol for r in records if r.sector in wanted}
    elif spec.mode == "names":
        chosen = {n.strip().upper() for n in spec.names if n.strip()}
    else:
        chosen = {r.symbol for r in records}
    chosen |= {n.strip().upper() for n in spec.add if n.strip()}
    chosen -= {n.strip().upper() for n in spec.remove}
    return sorted(chosen)
