"""
Module: MD-GUI-028.001.M01 — tests
Parent SRD: SRD-GUI-028.001

Candle data panel: summary line, progress, stat strip, footer and reset confirm
(FO-GUI-028). The badge moved to the sidebar Settings item (test_sidebar_shell.py).
"""
from __future__ import annotations

import sys
import types
from typing import Any
from unittest.mock import MagicMock

import pytest
from PyQt6.QtWidgets import QDialog

# QWebEngineWidgets DLL is unavailable in the test environment — stub it so
# settings_panel.py can be imported without the DLL.
_web_stub = types.ModuleType("PyQt6.QtWebEngineWidgets")
_web_stub.QWebEngineView = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("PyQt6.QtWebEngineWidgets", _web_stub)

from us_swing.gui import settings_panel  # noqa: E402
from us_swing.gui.app_service import CandleDbInfo, CandleDbStatus  # noqa: E402


class _Signal:
    def connect(self, *_a: Any) -> None:
        pass


class _StubService:
    def __init__(self, failed: list[str] | None = None) -> None:
        self._failed = failed or []
        self.resets = 0

    def get_failed_symbols(self) -> list[str]:
        return list(self._failed)

    def has_candle_checkpoint(self) -> bool:
        return False

    def reset_candle_db(self) -> None:
        self.resets += 1

    def __getattr__(self, name: str) -> Any:
        if name.startswith("candle_"):
            return _Signal()
        return lambda *_a, **_k: None


def _info(status: CandleDbStatus, data_to: str = "2026-10-23", stored: int = 503,
          universe: int = 503) -> CandleDbInfo:
    return CandleDbInfo(
        status=status, last_trading_day="2026-10-23", first_candle_date="2024-10-23",
        last_candle_date=data_to, symbols_1d=stored, symbols_1w=stored,
        total_1d=516_553, total_1w=104_000, universe_size=universe,
    )


@pytest.fixture()
def svc() -> _StubService:
    return _StubService()


@pytest.fixture()
def panel(qapp: Any, svc: _StubService) -> settings_panel._DataPanel:
    widget = settings_panel._DataPanel(svc)  # type: ignore[arg-type]
    seen: list[tuple[str, int]] = []
    widget.state_changed.connect(lambda s, p: seen.append((s, p)))
    widget.seen = seen  # type: ignore[attr-defined]
    return widget


def test_progress_line(panel: settings_panel._DataPanel) -> None:
    """UT-GUI-028.002.M01.T01: progress shows one summary line; a status check keeps it."""
    panel._set_downloading(True)
    panel._on_progress("MSFT", 312, 503)
    panel._on_refresh_status()

    assert panel._summary.text() == "Updating 312 of 503 stocks"
    assert panel._detail.text().startswith("62% · MSFT")
    assert panel._pill.text() == "DOWNLOADING"
    assert panel.seen[-1] == ("downloading", 62)  # type: ignore[attr-defined]


def test_eta_from_third_stock(panel: settings_panel._DataPanel, monkeypatch: Any) -> None:
    """UT-GUI-028.002.M01.T02: after 10 of 100 stocks in 20 s the ETA is about 3 minutes."""
    monkeypatch.setattr(settings_panel.time, "monotonic", lambda: 1000.0)
    panel._set_downloading(True)
    monkeypatch.setattr(settings_panel.time, "monotonic", lambda: 1020.0)
    panel._on_progress("AAPL", 10, 100)

    assert panel._detail.text() == "10% · AAPL · ~3 min left"


def test_finish_without_failures_is_complete(panel: settings_panel._DataPanel) -> None:
    """UT-GUI-028.001.M01.T01: a download with no failures ends as Complete at 100%."""
    panel._set_downloading(True)
    panel._on_progress("ZTS", 502, 503)
    panel._on_finished(100, 20)
    panel._on_failures_ready([])

    assert panel._pill.text() == "COMPLETE"
    assert panel._summary.text() == "Download complete · 503 stocks"
    assert panel.seen[-1] == ("complete", 100)  # type: ignore[attr-defined]


def test_finish_with_failures_is_partial(panel: settings_panel._DataPanel) -> None:
    """UT-GUI-028.001.M01.T02: a download with failed stocks ends as Partial."""
    panel._set_downloading(True)
    panel._on_progress("ZTS", 502, 503)
    panel._on_finished(100, 20)
    panel._on_failures_ready(["BRK.B", "BF.B", "KVUE"])

    assert panel._pill.text() == "PARTIAL"
    assert panel._summary.text() == "Download finished · 500 of 503 stocks"
    assert panel._fail_count_lbl.text() == "3 failed"
    assert not panel._disc_group.isHidden()
    assert panel.seen[-1][0] == "partial"  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("status", "data_to", "pill", "summary"),
    [
        (CandleDbStatus.CURRENT, "2026-10-23", "UP TO DATE", "Up to date · 503 stocks"),
        (CandleDbStatus.PARTIAL, "2026-10-22", "1 DAY BEHIND", "1 trading day behind"),
        (CandleDbStatus.EMPTY, None, "EMPTY", "No candle data yet"),
    ],
)
def test_status_pill_and_summary(panel: settings_panel._DataPanel, status: CandleDbStatus,
                                 data_to: str | None, pill: str, summary: str) -> None:
    """UT-GUI-028.001.M01.T03: the stored data sets one pill and one summary line."""
    panel._on_status_loaded(_info(status, data_to=data_to))  # type: ignore[arg-type]

    assert panel._pill.text() == pill
    assert panel._summary.text() == summary
    assert panel.state == ("idle", 0)


def test_extra_stocks_left_the_index(panel: settings_panel._DataPanel) -> None:
    """UT-GUI-028.003.M01.T01: 518 stored of 503 reads "503 / 503" and "+15 left the index"."""
    panel._on_status_loaded(_info(CandleDbStatus.CURRENT, stored=518))

    assert panel._values["Stocks"].text() == "503 / 503"
    assert panel._notes["Stocks"].text() == "+15 left the index"
    assert panel._values["Candles"].text() == "516,553"
    assert panel._notes["Last trading day"].text() == "Friday"


def test_footer_swaps_while_downloading(panel: settings_panel._DataPanel) -> None:
    """UT-GUI-028.004.M01.T01: while downloading, Cancel replaces Update and Reset is off."""
    panel._set_downloading(True)

    assert not panel._cancel_btn.isHidden()
    assert panel._build_btn.isHidden()
    assert not panel._reset_db_btn.isEnabled()


@pytest.mark.parametrize(("answer", "resets"), [(QDialog.DialogCode.Rejected, 0),
                                                (QDialog.DialogCode.Accepted, 1)])
def test_reset_asks_first(panel: settings_panel._DataPanel, svc: _StubService,
                          monkeypatch: Any, answer: QDialog.DialogCode, resets: int) -> None:
    """UT-GUI-028.005.M01.T01: Reset asks in the app's dialog; Cancel keeps the data."""
    asked: list[str] = []

    class _Dialog:
        def __init__(self, title: str, text: str, **_kw: Any) -> None:
            asked.append(text)

        def exec(self) -> QDialog.DialogCode:
            return answer

    fake = types.ModuleType("us_swing.gui.active_cycles_panel")
    fake._ConfirmDialog = _Dialog  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "us_swing.gui.active_cycles_panel", fake)

    panel._on_reset_db()

    assert "Deletes all stored candles" in asked[0]
    assert svc.resets == resets


def test_persisted_failures_mark_partial(qapp: Any) -> None:
    """UT-GUI-021.004.M01.T04: failures from a past session show Failed and a partial state."""
    widget = settings_panel._DataPanel(_StubService(["KVUE"]))  # type: ignore[arg-type]

    assert widget.state == ("partial", 0)
    assert not widget._disc_group.isHidden()
    assert widget._progress_box.isHidden()
