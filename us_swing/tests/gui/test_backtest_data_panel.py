"""
Module: MD-GUI-030.001.M01 — tests
Parent SRD: SRD-GUI-030.001

Backtest data section: status, progress, range and auto delta fields, actions,
type-to-confirm clear and the section dot.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any

import pytest
from PyQt6.QtCore import QDate, QObject, QTime, pyqtSignal

from us_swing.backtest.settings import BacktestDataSettings
from us_swing.backtest.store import BacktestStats
from us_swing.data.models import ConnectionStatus
from us_swing.gui import backtest_data_panel as mod
from us_swing.gui.backtest_data_panel import BacktestDataPanel


class _FakeService(QObject):
    backtest_progress = pyqtSignal(str, int, int, str)
    backtest_finished = pyqtSignal(bool, str)
    backtest_stats_changed = pyqtSignal(object)
    feed_status_changed = pyqtSignal(str)

    def __init__(self, connected: bool = True) -> None:
        super().__init__()
        self.connection_status = (
            ConnectionStatus.CONNECTED if connected else ConnectionStatus.DISCONNECTED
        )
        self.running = False
        self.calls: list[str] = []

    def is_backtest_running(self) -> bool:
        return self.running

    def start_backtest_download(self) -> bool:
        self.calls.append("start")
        self.running = True
        return True

    def stop_backtest_download(self) -> None:
        self.calls.append("stop")

    def fill_backtest_delta(self) -> bool:
        self.calls.append("delta")
        return True

    def clear_backtest_data(self) -> bool:
        self.calls.append("clear")
        return True

    def refresh_backtest_stats(self) -> None:
        self.calls.append("stats")

    def get_sp500_universe(self) -> list[object]:
        return []

    def get_last_trading_day(self) -> str:
        return "2026-10-27"


def _stats(stocks: int = 503, last: date | None = date(2026, 10, 27)) -> BacktestStats:
    return BacktestStats(
        stocks=stocks, bars_1d=1_300_000 if stocks else 0, bars_3m=186_000_000 if stocks else 0,
        first=date(2016, 1, 4) if stocks else None, last=last if stocks else None,
        size_bytes=3_900_000_000 if stocks else 0,
        last_delta=datetime(2026, 10, 27, 21, 35, tzinfo=timezone.utc) if stocks else None,
    )


@pytest.fixture()
def make(qtbot: Any, tmp_path: Path) -> Any:
    def _make(connected: bool = True) -> tuple[BacktestDataPanel, _FakeService]:
        svc = _FakeService(connected)
        panel = BacktestDataPanel(svc, root=tmp_path)  # type: ignore[arg-type]
        qtbot.addWidget(panel)
        return panel, svc
    return _make


def test_status_from_stats(make: Any) -> None:
    """UT-GUI-030.001.M01.T01: Summary, strip and pill come from the stats."""
    panel, svc = make()
    svc.backtest_stats_changed.emit(_stats())

    assert panel._headline.text() == "All candles saved"
    assert panel._detail.text() == (
        "Daily Jan 4, 2016 – Oct 27, 2026\n15-minute and weekly candles are built from these"
    )
    assert panel._facts.text() == "503 stocks · 3.9 GB"
    assert panel._start_btn.text() == "Up to date"
    assert not panel._start_btn.isEnabled()


def test_empty_store(make: Any) -> None:
    """UT-GUI-030.001.M01.T03: Empty store says so, shows the range estimate and Download."""
    panel, svc = make()
    svc.backtest_stats_changed.emit(_stats(stocks=0))

    assert panel._headline.text() == "No backtest candles yet"
    assert panel._detail.isHidden()
    assert "requests for this range" in panel._info.text()
    assert panel._start_btn.text() == "Download"


def test_progress_lines_update(make: Any) -> None:
    """UT-GUI-030.001.M01.T02: Progress (even from auto delta) shows the bar, count and time left."""
    panel, svc = make()
    svc.backtest_progress.emit("3m", 191, 503, "AAPL")

    assert panel.state == "running"
    assert panel._headline.text() == "Getting 3-minute candles"
    assert panel._bar.value() == 38
    assert panel._info.text() == "191 of 503 · AAPL · about 2 h 10 min left"
    assert panel._eta.text().startswith("Done around ")
    assert panel._start_btn.text() == "Pause"


def test_load_and_save_settings(make: Any, tmp_path: Path) -> None:
    """UT-GUI-030.002.M01.T01: Fields load from settings.json and save the same values."""
    BacktestDataSettings(start_date=date(2018, 1, 1)).save(tmp_path)
    panel, _svc = make()
    panel.load()

    assert panel._start.date() == QDate(2018, 1, 1)
    assert panel._latest.isChecked()
    assert not panel._end.isEnabled()
    (tmp_path / "settings.json").unlink()
    panel.save()
    assert BacktestDataSettings.load(tmp_path) == BacktestDataSettings(start_date=date(2018, 1, 1))


def test_start_never_after_end(make: Any) -> None:
    """UT-GUI-030.002.M01.T02: Start date is held at a fixed end date."""
    panel, _svc = make()
    panel._latest.setChecked(False)
    panel._end.setDate(QDate(2020, 1, 1))
    panel._start.setDate(QDate(2021, 1, 1))

    assert panel._start.date() == QDate(2020, 1, 1)


def test_estimate_uses_measured_3m_speed(make: Any, tmp_path: Path) -> None:
    """UT-GUI-030.002.M01.T03: Estimate uses 25 s per 3m request; long runs show days."""
    BacktestDataSettings(start_date=date(2024, 1, 2), end_date=date(2025, 1, 1)).save(tmp_path)
    panel, svc = make()
    svc.backtest_stats_changed.emit(_stats(stocks=0))

    assert panel._info.text() == "2,515 requests for this range · about 14 h 6 min"

    BacktestDataSettings(start_date=date(2015, 1, 2), end_date=date(2025, 1, 1)).save(tmp_path)
    panel.load()
    assert panel._info.text().endswith("days")


def test_auto_delta_fields_load(make: Any, tmp_path: Path) -> None:
    """UT-GUI-030.003.M01.T02: Auto delta switch, time, zone label and day chips load."""
    BacktestDataSettings().save(tmp_path)
    panel, _svc = make()
    panel.load()

    assert panel._auto.isChecked()
    assert panel._time.time() == QTime(17, 30)
    assert panel._zone.text() == "US/Eastern"
    assert [c.isChecked() for c in panel._days] == [True] * 5 + [False] * 2


def test_fixed_end_turns_off_auto_delta(make: Any, tmp_path: Path) -> None:
    """UT-GUI-030.003.M01.T01: Unchecking latest disables auto delta and saves it off."""
    panel, _svc = make()
    panel.load()
    panel._latest.setChecked(False)

    assert not panel._auto.isEnabled()
    panel.save()
    saved = BacktestDataSettings.load(tmp_path)
    assert saved.auto_delta is False
    assert saved.end_date is not None
    assert saved.run_time == time(17, 30)


def test_tws_not_connected(make: Any) -> None:
    """UT-GUI-030.004.M01.T01: Without TWS the actions are disabled with a hint."""
    panel, _svc = make(connected=False)

    assert not panel._start_btn.isEnabled()
    assert not panel._clear_btn.isEnabled()
    assert panel._hint.text() == "Connect TWS to download"


def test_start_becomes_pause(make: Any) -> None:
    """UT-GUI-030.004.M01.T02: Start calls the service and the button turns into Pause."""
    panel, svc = make()
    panel._start_btn.click()

    assert "start" in svc.calls
    assert panel._start_btn.text() == "Pause"
    assert not panel._clear_btn.isEnabled()
    panel._start_btn.click()
    assert "stop" in svc.calls


def test_clear_cancelled(make: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-GUI-030.005.M01.T01: Cancelling the confirm deletes nothing."""
    panel, svc = make()
    monkeypatch.setattr(panel, "_confirm_clear", lambda: False)
    panel._clear_btn.click()

    assert "clear" not in svc.calls


def test_clear_needs_typed_word(make: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-GUI-030.005.M01.T02: Clear enables only on CLEAR; accepting calls clear."""
    panel, svc = make()
    dialog, field, button = mod.build_clear_dialog("Deletes 3.9 GB.", panel)
    field.setText("clear")
    assert not button.isEnabled()
    field.setText("CLEAR")
    assert button.isEnabled()
    dialog.reject()

    svc.backtest_stats_changed.emit(_stats())
    monkeypatch.setattr(panel, "_confirm_clear", lambda: True)
    panel._clear_btn.click()
    assert "clear" in svc.calls
    assert panel._hint.text() == "Backtest data cleared · 3.9 GB freed"
    assert panel._headline.text() == "No backtest candles yet"


def test_dot_state(make: Any) -> None:
    """UT-GUI-030.006.M01.T01: State is empty, running or ok for the section dot."""
    panel, svc = make()
    svc.backtest_stats_changed.emit(_stats(stocks=0))
    assert panel.state == "empty"
    panel._start_btn.click()
    assert panel.state == "running"
    svc.running = False
    svc.backtest_finished.emit(True, "Done")
    svc.backtest_stats_changed.emit(_stats())
    assert panel.state == "ok"
    svc.backtest_stats_changed.emit(replace(_stats(), missing_1d=3, short_stocks=3))
    assert panel.state == "behind"


def test_short_3m_shows_behind(make: Any, tmp_path: Path) -> None:
    """UT-GUI-030.006.M01.T02: Missing 3m requests give a plain sentence and Download missing."""
    BacktestDataSettings(start_date=date(2016, 1, 1)).save(tmp_path)
    panel, svc = make()
    svc.backtest_stats_changed.emit(replace(
        _stats(), first_3m=date(2026, 1, 2), missing_3m=498, short_stocks=503,
    ))

    assert panel.state == "behind"
    assert panel._headline.text() == "3-minute candles missing for 503 stocks"
    assert panel._detail.text().splitlines()[0].endswith("· 3-minute from Jan 2, 2026")
    assert panel._info.text() == "498 requests · about 3 h 27 min"
    assert panel._start_btn.text() == "Download missing"
    assert panel._start_btn.isEnabled()


def test_changed_range_saved_on_download(make: Any, tmp_path: Path) -> None:
    """UT-GUI-030.009.M01.T01: An unsaved range turns the button into Save range and download."""
    BacktestDataSettings(start_date=date(2026, 1, 1)).save(tmp_path)
    panel, svc = make()
    svc.backtest_stats_changed.emit(_stats())
    panel._start.setDate(QDate(2025, 11, 1))

    assert panel._info.text() == "Range changed · not saved yet"
    assert panel._start_btn.text() == "Save range and download"
    panel._start_btn.click()
    assert BacktestDataSettings.load(tmp_path).start_date == date(2025, 11, 1)
    assert "start" in svc.calls
    assert panel._start_btn.text() == "Pause"


def test_status_bar_shows_backtest(qtbot: Any) -> None:
    """UT-GUI-030.007.M05.T01: Status bar shows progress, then the result, then hides."""
    import sys
    import types
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QLabel

    # QWebEngineWidgets cannot load in tests — same stub as test_settings_sections.py.
    web_stub = types.ModuleType("PyQt6.QtWebEngineWidgets")
    web_stub.QWebEngineView = MagicMock  # type: ignore[attr-defined]
    sys.modules.setdefault("PyQt6.QtWebEngineWidgets", web_stub)
    from us_swing.gui.main_window import MainWindow

    label = QLabel("")
    label.hide()
    qtbot.addWidget(label)
    hide = QTimer()
    hide.setSingleShot(True)
    hide.setInterval(15_000)
    hide.timeout.connect(label.hide)
    win = SimpleNamespace(_sb_backtest=label, _sb_backtest_hide=hide)

    MainWindow._on_backtest_progress(win, "1d", 35, 503, "AAPL")  # type: ignore[arg-type]
    assert label.text() == "Backtest data · 1d 35 of 503"
    assert not label.isHidden()

    MainWindow._on_backtest_finished(win, True, "Done")  # type: ignore[arg-type]
    assert label.text() == "Backtest data · Done"
    assert hide.isActive()
    hide.timeout.emit()
    assert label.isHidden()
