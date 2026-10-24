"""
Module: MD-GUI-026.012.M04 — Chart drawings
Parent SRD: SRD-GUI-026.012

Horizontal lines, trend lines and rectangles drawn on the Charts chart, saved per
user, symbol and timeframe in the shared ``candles.db`` (table ``chart_drawings``).
"""
from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, replace
from datetime import datetime, timezone

import sqlalchemy as sa
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from sqlalchemy import Engine

_log = logging.getLogger(__name__)

# Own metadata: the store creates its table itself, and importing ``us_swing.db``
# first from the GUI hits that package's circular import.
metadata = sa.MetaData()

KINDS: dict[str, int] = {"hline": 1, "trend": 2, "rect": 2}   # kind → points needed

chart_drawings = sa.Table(
    "chart_drawings",
    metadata,
    sa.Column("id",          sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("user_id",     sa.Integer, nullable=False),
    sa.Column("symbol",      sa.Text,    nullable=False),
    sa.Column("timeframe",   sa.Text,    nullable=False),
    sa.Column("kind",        sa.Text,    nullable=False),
    sa.Column("points_json", sa.Text,    nullable=False),
    sa.Column("colour",      sa.Text,    nullable=False, default=""),
    sa.Column("updated_at",  sa.Text,    nullable=False),
)

idx_chart_drawings = sa.Index(
    "idx_chart_drawings_chart",
    chart_drawings.c.user_id, chart_drawings.c.symbol, chart_drawings.c.timeframe,
)

Point = tuple[float, float]   # (bar time, price)


@dataclass(frozen=True, slots=True)
class Drawing:
    """One drawing; ``id`` is None until it is saved."""

    kind: str
    points: tuple[Point, ...]
    colour: str = ""
    id: int | None = None

    def to_js(self) -> dict[str, object]:
        """Shape the chart page draws (``applyStudies`` ``drawings``)."""
        return {"id": self.id, "kind": self.kind, "colour": self.colour,
                "points": [{"time": t, "price": p} for t, p in self.points]}


def drawing_from_json(payload: str) -> Drawing | None:
    """Read a drawing sent by the chart page; None when it is not a valid drawing."""
    try:
        data = json.loads(payload)
        kind = str(data["kind"])
        points = tuple((float(p["time"]), float(p["price"])) for p in data["points"])
    except (ValueError, TypeError, KeyError):
        return None
    if KINDS.get(kind) != len(points) or not all(map(math.isfinite, sum(points, ()))):
        return None
    return Drawing(kind, points)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


class DrawingStore:
    """Save and read drawings keyed by (user_id, symbol, timeframe)."""

    __slots__ = ("_engine",)

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        chart_drawings.create(engine, checkfirst=True)
        idx_chart_drawings.create(engine, checkfirst=True)

    def load(self, user_id: int, symbol: str, timeframe: str) -> list[Drawing]:
        t = chart_drawings.c
        stmt = (sa.select(t.id, t.kind, t.points_json, t.colour)
                .where(t.user_id == user_id, t.symbol == symbol, t.timeframe == timeframe)
                .order_by(t.id))
        with self._engine.begin() as conn:
            rows = conn.execute(stmt).all()
        drawings = []
        for row in rows:
            points = tuple((float(p[0]), float(p[1])) for p in json.loads(row.points_json))
            drawings.append(Drawing(str(row.kind), points, str(row.colour), int(row.id)))
        return drawings

    def save(self, user_id: int, symbol: str, timeframe: str, drawing: Drawing) -> Drawing:
        """Insert ``drawing`` and return it with its new id."""
        values = {"user_id": user_id, "symbol": symbol, "timeframe": timeframe,
                  "kind": drawing.kind, "points_json": json.dumps(list(drawing.points)),
                  "colour": drawing.colour, "updated_at": _now()}
        with self._engine.begin() as conn:
            result = conn.execute(sa.insert(chart_drawings).values(**values))
        key = result.inserted_primary_key
        return replace(drawing, id=int(key[0]) if key else None)

    def delete(self, user_id: int, drawing_id: int) -> None:
        """Delete one of ``user_id``'s drawings."""
        t = chart_drawings.c
        with self._engine.begin() as conn:
            conn.execute(sa.delete(chart_drawings).where(t.id == drawing_id, t.user_id == user_id))

    def delete_all(self, user_id: int, symbol: str, timeframe: str) -> int:
        """Delete every drawing of one chart; returns the deleted count."""
        t = chart_drawings.c
        with self._engine.begin() as conn:
            result = conn.execute(sa.delete(chart_drawings).where(
                t.user_id == user_id, t.symbol == symbol, t.timeframe == timeframe))
        return int(result.rowcount or 0)


class ChartBridge(QObject):
    """Object the chart page calls through QWebChannel when a drawing is finished or erased."""

    drawing_added = pyqtSignal(object)   # Drawing
    drawing_deleted = pyqtSignal(int)    # drawing id

    @pyqtSlot(str)
    def add_drawing(self, payload: str) -> None:
        drawing = drawing_from_json(payload)
        if drawing is None:
            _log.warning("[Charts] A drawing from the chart could not be read")
            return
        self.drawing_added.emit(drawing)

    @pyqtSlot(int)
    def delete_drawing(self, drawing_id: int) -> None:
        self.drawing_deleted.emit(drawing_id)


__all__ = [
    "ChartBridge", "Drawing", "DrawingStore", "KINDS", "chart_drawings", "drawing_from_json",
    "idx_chart_drawings",
]
