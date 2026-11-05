"""
Module: MD-GUI-034.011.M10 — core/desk_floor.py
Parent SRD: SRD-GUI-034.011

Market Floor data from ``desk.db``: the real regime and breadth when the desk has them,
the fallback provider (sample data) for every other product.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from us_swing.core.desk_contract import DB_NAME, FloorData, ProductDescriptor, desk_home

REGIME_ID = "regime.today"
BREADTH_ID = "breadth.daily"
_REGIME_COLUMNS = ("regime", "volatility", "fear", "vix", "data_date", "note")
_BREADTH_COLUMNS = ("measure", "value", "reading")


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value:.0f}%"


def _reading(value: float | None, good: float, weak: float) -> str:
    if value is None:
        return "-"
    return "Healthy" if value >= good else "Weak" if value < weak else "Mixed"


class DeskFloorData:
    """``FloorData`` that reads the market tables in ``desk.db`` read-only."""

    def __init__(self, fallback: FloorData, home: Path | None = None) -> None:
        """Use ``fallback`` for products the desk does not provide yet."""
        self._fallback = fallback
        self._path = (home or desk_home()) / DB_NAME

    def _query(self, sql: str) -> tuple[Any, ...] | None:
        if not self._path.exists():
            return None
        try:
            con = sqlite3.connect(f"{self._path.as_uri()}?mode=ro", uri=True, timeout=2)
            try:
                row = con.execute(sql).fetchone()
            finally:
                con.close()
        except sqlite3.Error:
            return None
        return tuple(row) if row else None

    def _latest_regime(self) -> tuple[Any, ...] | None:
        return self._query(
            "SELECT date, regime, volatility, fear, vix, note FROM regime_snapshot "
            "ORDER BY date DESC LIMIT 1"
        )

    def _latest_breadth(self) -> tuple[Any, ...] | None:
        return self._query(
            "SELECT date, pct_above_20, pct_above_50, pct_above_200, new_highs, new_lows, "
            "advancers, decliners FROM breadth_daily ORDER BY date DESC LIMIT 1"
        )

    def products(self) -> Sequence[ProductDescriptor]:
        """Return the fallback products, marking regime and breadth real when stored."""
        real = {
            REGIME_ID: (self._latest_regime(), _REGIME_COLUMNS),
            BREADTH_ID: (self._latest_breadth(), _BREADTH_COLUMNS),
        }
        out: list[ProductDescriptor] = []
        for product in self._fallback.products():
            row, columns = real.get(product.id, (None, ()))
            out.append(replace(product, columns=columns, sample=False) if row else product)
        return out

    def rows(self, product_id: str, filters: Mapping[str, str]) -> list[dict[str, Any]]:
        """Return desk rows for regime and breadth when stored, else fallback rows."""
        if product_id == REGIME_ID and (row := self._latest_regime()):
            day, regime, volatility, fear, vix, note = row
            return [{
                "regime": regime, "volatility": volatility, "fear": fear,
                "vix": "-" if vix is None else f"{vix:.1f}", "data_date": day,
                "note": note or "-",
            }]
        if product_id == BREADTH_ID and (row := self._latest_breadth()):
            day, p20, p50, p200, highs, lows, adv, dec = row
            ratio = f"{adv / dec:.1f} : 1" if dec else "-"
            return [
                {"measure": "Data date", "value": day, "reading": ""},
                {"measure": "Stocks above 20-day average", "value": _pct(p20),
                 "reading": _reading(p20, 60, 40)},
                {"measure": "Stocks above 50-day average", "value": _pct(p50),
                 "reading": _reading(p50, 60, 40)},
                {"measure": "Stocks above 200-day average", "value": _pct(p200),
                 "reading": _reading(p200, 60, 40)},
                {"measure": "New highs minus new lows", "value": f"{highs - lows:+d}",
                 "reading": f"{highs} highs, {lows} lows"},
                {"measure": "Advancing vs declining", "value": ratio,
                 "reading": f"{adv} up, {dec} down"},
            ]
        return self._fallback.rows(product_id, filters)
