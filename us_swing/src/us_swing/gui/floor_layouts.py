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
    """Return the default panels for each of the five Market Floor tabs (12-column grid).

    Each tab is about 26 rows high so it fills the page at 1080p.
    """
    return {
        "Overview": [
            _panel("p1", "ideas.top", 0, 0, 8, 13, link="A"),
            _panel("p2", "regime.today", 8, 0, 4, 6, view="card"),
            _panel("p3", "breadth.daily", 8, 6, 4, 7),
            _panel("p4", "news.latest", 0, 13, 12, 13),
        ],
        "Ideas": [
            _panel("p1", "ideas.top", 0, 0, 6, 13, filters={"side": "long"}, link="A"),
            _panel("p2", "ideas.top", 6, 0, 6, 13, filters={"side": "short"}, link="A"),
            _panel("p3", "flow.leaders", 0, 13, 12, 13),
        ],
        "Sectors": [
            _panel("p1", "sectors.rank", 0, 0, 7, 26),
            _panel("p2", "sectors.rrg", 7, 0, 5, 26),
        ],
        "Regime & Breadth": [
            _panel("p1", "regime.today", 0, 0, 5, 26, view="card"),
            _panel("p2", "breadth.daily", 5, 0, 7, 26),
        ],
        "News & Calendar": [
            _panel("p1", "news.latest", 0, 0, 7, 26),
            _panel("p2", "calendar.week", 7, 0, 5, 26),
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
            if tab not in tabs:
                result[tab] = defaults[tab]
                continue
            entry = tabs.get(tab)
            raw = entry.get("panels") if isinstance(entry, dict) else None
            panels: list[dict[str, Any]] = []
            for panel in raw if isinstance(raw, list) else []:
                if _valid_panel(panel):
                    panels.append(panel)
                else:
                    _log.warning("[Floor] Layout %s, tab %s: a broken panel was dropped", name, tab)
            keep_empty = isinstance(raw, list) and not raw
            result[tab] = panels if panels or keep_empty else defaults[tab]
        return result

    def save(self, name: str, tabs: Panels) -> None:
        """Save ``tabs`` under ``name`` and write the file."""
        self._data["layouts"][name] = {
            "tabs": {tab: {"panels": panels} for tab, panels in tabs.items()}
        }
        self._write()

    def delete(self, name: str) -> bool:
        """Delete layout ``name``; Default and unknown names are kept. Returns True if deleted."""
        if name == DEFAULT_NAME or name not in self._data["layouts"]:
            return False
        del self._data["layouts"][name]
        if self._data.get("last") == name:
            self._data["last"] = DEFAULT_NAME
        self._write()
        return True

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
