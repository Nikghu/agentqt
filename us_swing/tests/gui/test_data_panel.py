"""
Module: MD-GUI-021.001.M01 — tests
Parent SRD: SRD-GUI-021.004

Data panel on the right strip: download percent, Complete / Partial result and
the strip badge (FO-GUI-021).
"""
from __future__ import annotations

import sys
import types
from typing import Any
from unittest.mock import MagicMock

import pytest

# QWebEngineWidgets DLL is unavailable in the test environment — stub it so
# settings_panel.py can be imported without the DLL.
_web_stub = types.ModuleType("PyQt6.QtWebEngineWidgets")
_web_stub.QWebEngineView = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("PyQt6.QtWebEngineWidgets", _web_stub)

from us_swing.gui import settings_panel  # noqa: E402
from us_swing.gui.side_panels import IconStrip  # noqa: E402


class _Signal:
    def connect(self, *_a: Any) -> None:
        pass


class _StubService:
    def __init__(self, failed: list[str] | None = None) -> None:
        self._failed = failed or []

    def get_failed_symbols(self) -> list[str]:
        return list(self._failed)

    def has_candle_checkpoint(self) -> bool:
        return False

    def __getattr__(self, name: str) -> Any:
        if name.startswith("candle_"):
            return _Signal()
        return lambda *_a, **_k: None


@pytest.fixture()
def panel(qapp: Any) -> settings_panel._DataPanel:
    widget = settings_panel._DataPanel(_StubService())  # type: ignore[arg-type]
    seen: list[tuple[str, int]] = []
    widget.state_changed.connect(lambda s, p: seen.append((s, p)))
    widget.seen = seen  # type: ignore[attr-defined]
    return widget


def test_progress_shows_percent(panel: settings_panel._DataPanel) -> None:
    """UT-GUI-021.004.M01.T01: progress shows percent, stock count and current stock."""
    panel._set_downloading(True)
    panel._on_progress("MSFT", 312, 503)

    assert panel._pct_lbl.text() == "62%"
    assert panel._count_lbl.text() == "312 / 503 stocks"
    assert panel._progress_label.text() == "Now: MSFT"
    assert panel.seen[-1] == ("downloading", 62)  # type: ignore[attr-defined]


def test_finish_without_failures_is_complete(panel: settings_panel._DataPanel) -> None:
    """UT-GUI-021.004.M01.T02: a download with no failures ends as Complete at 100%."""
    panel._set_downloading(True)
    panel._on_progress("ZTS", 502, 503)
    panel._on_finished(100, 20)
    panel._on_failures_ready([])

    assert panel._dl_pill.text() == "Complete"
    assert panel._pct_lbl.text() == "100%"
    assert panel.seen[-1] == ("complete", 100)  # type: ignore[attr-defined]


def test_finish_with_failures_is_partial(panel: settings_panel._DataPanel) -> None:
    """UT-GUI-021.004.M01.T03: a download with failed stocks ends as Partial."""
    panel._set_downloading(True)
    panel._on_progress("ZTS", 502, 503)
    panel._on_finished(100, 20)
    panel._on_failures_ready(["BRK.B", "BF.B", "KVUE"])

    assert panel._dl_pill.text() == "Partial"
    assert panel._count_lbl.text() == "500 / 503 stocks"
    assert panel._fail_count_lbl.text() == "3 failed"
    assert not panel._disc_group.isHidden()
    assert panel.seen[-1][0] == "partial"  # type: ignore[attr-defined]


def test_persisted_failures_mark_partial(qapp: Any) -> None:
    """UT-GUI-021.004.M01.T04: failures from a past session show Failed and a partial state."""
    widget = settings_panel._DataPanel(_StubService(["KVUE"]))  # type: ignore[arg-type]

    assert widget.state == ("partial", 0)
    assert not widget._disc_group.isHidden()
    assert widget._download_box.isHidden()


@pytest.mark.parametrize(
    ("state", "percent", "text"),
    [("downloading", 62, "62"), ("complete", 100, ""), ("partial", 99, "!")],
)
def test_strip_data_badge(qapp: Any, state: str, percent: int, text: str) -> None:
    """UT-GUI-021.004.M02.T01: the Data strip button shows percent, tick or !."""
    strip = IconStrip()

    strip.set_data_state(state, percent)

    assert not strip._data_badge.isHidden()
    assert strip._data_badge.text() == text
    pixmap = strip._data_badge.pixmap()
    assert (pixmap is not None and not pixmap.isNull()) == (state == "complete")


def test_strip_data_badge_hidden_when_idle(qapp: Any) -> None:
    """UT-GUI-021.004.M02.T02: an idle state hides the Data badge."""
    strip = IconStrip()
    strip.set_data_state("complete", 100)

    strip.set_data_state("idle", 0)

    assert strip._data_badge.isHidden()
