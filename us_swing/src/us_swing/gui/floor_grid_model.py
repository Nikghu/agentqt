"""
Module: MD-GUI-034.005.M05 — Floor grid model
Parent SRD: SRD-GUI-034.005

Pure grid rules for Market Floor panels: 12 columns, minimum 2 x 3 cells, push-down on overlap.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger(__name__)
COLUMNS = 12
MIN_W = 2
MIN_H = 3
DEFAULT_W = 6
DEFAULT_H = 6
_MAX_PASSES = 200


@dataclass
class PanelSpec:
    """One panel on the grid: what it shows and where it sits (in cells)."""

    id: str
    product: str
    view: str = "table"
    filters: dict[str, str] = field(default_factory=dict)
    link: str | None = None
    x: int = 0
    y: int = 0
    w: int = DEFAULT_W
    h: int = DEFAULT_H

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON form used by the layout file (no link is stored as empty text)."""
        return {"id": self.id, "product": self.product, "view": self.view,
                "filters": dict(self.filters), "link": self.link or "",
                "x": self.x, "y": self.y, "w": self.w, "h": self.h}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PanelSpec:
        """Build a spec from layout JSON.

        Raises:
            KeyError: When a required key is missing.
            TypeError: When a value has the wrong type.
            ValueError: When a number cannot be read.
        """
        filters = data.get("filters") or {}
        if not isinstance(filters, dict):
            raise TypeError("filters must be a dict")
        link = data.get("link") or None
        return cls(
            id=str(data.get("id", "")), product=str(data["product"]), view=str(data["view"]),
            filters={str(k): str(v) for k, v in filters.items()},
            link=str(link) if link else None,
            x=int(data["x"]), y=int(data["y"]), w=int(data["w"]), h=int(data["h"]),
        )


def _overlap(a: PanelSpec, b: PanelSpec) -> bool:
    return a.x < b.x + b.w and b.x < a.x + a.w and a.y < b.y + b.h and b.y < a.y + a.h


class GridModel:
    """The panels of one tab and the rules that keep them on the grid."""

    def __init__(self, panels: list[PanelSpec] | None = None) -> None:
        self.panels: list[PanelSpec] = []
        for spec in panels or []:
            self._clamp(spec)
            if not spec.id or self.get(spec.id) is not None:
                spec.id = self.next_id()
            self.panels.append(spec)
        self._settle(None)

    def get(self, panel_id: str) -> PanelSpec | None:
        """Return the panel with ``panel_id`` or ``None``."""
        return next((p for p in self.panels if p.id == panel_id), None)

    def next_id(self) -> str:
        """Return an unused panel id."""
        used = {p.id for p in self.panels}
        n = 1
        while f"p{n}" in used:
            n += 1
        return f"p{n}"

    def bottom(self) -> int:
        """Return the first free row below all panels."""
        return max((p.y + p.h for p in self.panels), default=0)

    def place_free(self, w: int, h: int) -> tuple[int, int]:
        """Return the first (x, y) scanning top-down, left-right where a w x h panel fits.

        Falls back to the row below the lowest panel.
        """
        w = min(max(w, MIN_W), COLUMNS)
        h = max(h, MIN_H)
        probe = PanelSpec("", "", w=w, h=h)
        for y in range(self.bottom()):
            for x in range(COLUMNS - w + 1):
                probe.x, probe.y = x, y
                if not any(_overlap(probe, p) for p in self.panels):
                    return x, y
        return 0, self.bottom()

    def add(self, spec: PanelSpec) -> PanelSpec:
        """Place ``spec`` at a free spot and add it."""
        self._clamp(spec)
        spec.x, spec.y = self.place_free(spec.w, spec.h)
        self.panels.append(spec)
        return spec

    def move(self, panel_id: str, x: int, y: int) -> None:
        """Move a panel; others are pushed down if they overlap."""
        spec = self.get(panel_id)
        if spec is None:
            return
        spec.x, spec.y = x, y
        self._clamp(spec)
        self._settle(spec)

    def resize(self, panel_id: str, w: int, h: int) -> None:
        """Resize a panel; others are pushed down if they overlap."""
        spec = self.get(panel_id)
        if spec is None:
            return
        spec.w, spec.h = w, h
        self._clamp(spec, keep_x=True)
        self._settle(spec)

    def remove(self, panel_id: str) -> None:
        """Remove a panel."""
        self.panels = [p for p in self.panels if p.id != panel_id]

    def to_list(self) -> list[dict[str, Any]]:
        """Return the panels as layout JSON."""
        return [p.to_dict() for p in self.panels]

    @staticmethod
    def _clamp(spec: PanelSpec, keep_x: bool = False) -> None:
        if keep_x:
            spec.x = min(max(spec.x, 0), COLUMNS - MIN_W)
            spec.w = min(max(spec.w, MIN_W), COLUMNS - spec.x)
        else:
            spec.w = min(max(spec.w, MIN_W), COLUMNS)
            spec.x = min(max(spec.x, 0), COLUMNS - spec.w)
        spec.h = max(spec.h, MIN_H)
        spec.y = max(spec.y, 0)

    def _settle(self, keep: PanelSpec | None) -> None:
        """Push overlapping panels down; ``keep`` (the one just moved) never moves."""
        for _ in range(_MAX_PASSES):
            moved = False
            ordered = sorted(self.panels, key=lambda p: (p.y, p.x))
            for i, a in enumerate(ordered):
                for b in ordered[i + 1:]:
                    if not _overlap(a, b):
                        continue
                    low, high = (b, a) if b is not keep else (a, b)
                    low.y = high.y + high.h
                    moved = True
            if not moved:
                return
        _log.warning("[Floor] Some panels still overlap after %d passes", _MAX_PASSES)


def snap_delta(dx_px: float, dy_px: float, cell_w: float, cell_h: float) -> tuple[int, int]:
    """Convert a drag distance in pixels to whole cells (cell sizes include the gap)."""
    if cell_w <= 0 or cell_h <= 0:
        return 0, 0
    return round(dx_px / cell_w), round(dy_px / cell_h)


def clamp_rect(
    x: int, y: int, w: int, h: int, keep_x: bool = False
) -> tuple[int, int, int, int]:
    """Return (x, y, w, h) kept inside the 12 columns with the minimum size.

    With ``keep_x`` (resizing) the width shrinks to fit; otherwise x shifts to fit.
    """
    probe = PanelSpec("", "", x=x, y=y, w=w, h=h)
    GridModel._clamp(probe, keep_x)
    return probe.x, probe.y, probe.w, probe.h
