"""
Module: MD-GUI-034.008.M07 — Floor layouts
Parent SRD: SRD-GUI-034.008
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

VERSION = 1
DEFAULT_NAME = "Default"
TAB_NAMES = ("Overview", "Ideas", "Sectors", "Regime & Breadth", "News & Calendar")

Panels = dict[str, list[dict[str, Any]]]


def _panel(pid: str, product: str, x: int, y: int, w: int, h: int, view: str = "table",
           filters: dict[str, str] | None = None, link: str = "") -> dict[str, Any]:
    return {"id": pid, "product": product, "view": view, "filters": filters or {},
            "link": link, "x": x, "y": y, "w": w, "h": h}


def default_layout() -> Panels:
    """Return the default panels for each of the five Market Floor tabs (12-column grid)."""
    return {
        "Overview": [
            _panel("p1", "ideas.top", 0, 0, 8, 8, link="A"),
            _panel("p2", "regime.today", 8, 0, 4, 4, view="card"),
            _panel("p3", "breadth.daily", 8, 4, 4, 4),
            _panel("p4", "news.latest", 0, 8, 12, 6),
        ],
        "Ideas": [
            _panel("p1", "ideas.top", 0, 0, 6, 8, filters={"side": "long"}, link="A"),
            _panel("p2", "ideas.top", 6, 0, 6, 8, filters={"side": "short"}, link="A"),
            _panel("p3", "flow.leaders", 0, 8, 12, 5),
        ],
        "Sectors": [
            _panel("p1", "sectors.rank", 0, 0, 7, 9),
            _panel("p2", "sectors.rrg", 7, 0, 5, 9),
        ],
        "Regime & Breadth": [
            _panel("p1", "regime.today", 0, 0, 5, 5, view="card"),
            _panel("p2", "breadth.daily", 5, 0, 7, 8),
        ],
        "News & Calendar": [
            _panel("p1", "news.latest", 0, 0, 7, 10),
            _panel("p2", "calendar.week", 7, 0, 5, 10),
        ],
    }


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _valid_panel(panel: object) -> bool:
    if not isinstance(panel, dict):
        return False
    if not all(_is_int(panel.get(k)) for k in ("x", "y", "w", "h")):
        return False
    if not all(isinstance(panel.get(k), str) for k in ("product", "view")):
        return False
    if not isinstance(panel.get("filters", {}), dict):
        return False
    return panel.get("link") is None or isinstance(panel.get("link"), str)


class LayoutStore:
    """Named Market Floor layouts, the last one used and the feed fold choice."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or Path.home() / ".usswing" / "floor_layouts.json"
        self._data = self._read()

    def names(self) -> list[str]:
        """Return the saved layout names (always includes Default)."""
        return list(self._data["layouts"])

    def load(self, name: str) -> Panels:
        """Return tab -> panels for ``name``; bad panels are dropped, empty tabs get defaults."""
        layout = self._data["layouts"].get(name)
        tabs = layout.get("tabs") if isinstance(layout, dict) else None
        tabs = tabs if isinstance(tabs, dict) else {}
        defaults = default_layout()
        result: Panels = {}
        for tab in TAB_NAMES:
            entry = tabs.get(tab)
            raw = entry.get("panels") if isinstance(entry, dict) else None
            panels: list[dict[str, Any]] = []
            for panel in raw if isinstance(raw, list) else []:
                if _valid_panel(panel):
                    panels.append(panel)
                else:
                    _log.warning("[Floor] Layout %s, tab %s: a broken panel was dropped", name, tab)
            result[tab] = panels or defaults[tab]
        return result

    def save(self, name: str, tabs: Panels) -> None:
        """Save ``tabs`` under ``name`` and write the file."""
        self._data["layouts"][name] = {
            "tabs": {tab: {"panels": panels} for tab, panels in tabs.items()}
        }
        self._write()

    def last(self) -> str:
        """Return the layout name to open at start."""
        last = str(self._data.get("last", DEFAULT_NAME))
        return last if last in self._data["layouts"] else DEFAULT_NAME

    def set_last(self, name: str) -> None:
        """Remember ``name`` as the layout to open at start."""
        self._data["last"] = name
        self._write()

    def feed_folded(self) -> bool:
        """Return whether the AI feed column is folded."""
        return bool(self._data.get("feed_folded", False))

    def set_feed_folded(self, folded: bool) -> None:
        """Remember the AI feed fold choice."""
        self._data["feed_folded"] = folded
        self._write()

    def _fresh(self) -> dict[str, Any]:
        tabs = {tab: {"panels": panels} for tab, panels in default_layout().items()}
        return {"version": VERSION, "last": DEFAULT_NAME, "feed_folded": False,
                "layouts": {DEFAULT_NAME: {"tabs": tabs}}}

    def _read(self) -> dict[str, Any]:
        if not self._path.exists():
            return self._fresh()
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("layouts"), dict):
                raise ValueError("layouts missing")
        except (OSError, ValueError) as exc:
            _log.warning("[Floor] Layout file could not be read, using the default layout: %s", exc)
            self._back_up()
            return self._fresh()
        data["layouts"].setdefault(DEFAULT_NAME, self._fresh()["layouts"][DEFAULT_NAME])
        return data

    def _back_up(self) -> None:
        try:
            os.replace(self._path, self._path.with_name(self._path.name + ".bak"))
        except OSError as exc:
            _log.warning("[Floor] Layout file could not be backed up: %s", exc)

    def _write(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
            os.replace(tmp, self._path)
        except OSError as exc:
            _log.warning("[Floor] Layout file could not be saved: %s", exc)
