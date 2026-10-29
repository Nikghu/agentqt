"""
Module: MD-GUI-030.001.M01 — gui/backtest_data_panel.py
Parent SRD: SRD-GUI-030.001

Backtest data section in Settings (Option D): one plain status sentence with coverage,
progress and a single download button, range and auto delta fields, and a type-to-confirm
clear. Business logic lives in AppService / backtest.
"""
from __future__ import annotations

import datetime
import math
import time
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QDate, QTime, QTimer
from PyQt6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from us_swing.backtest import DEFAULT_ROOT
from us_swing.backtest.settings import BacktestDataSettings
from us_swing.backtest.store import BacktestStats
from us_swing.data.models import ConnectionStatus
from us_swing.gui.icons import set_icon
from us_swing.gui.theme import C

if TYPE_CHECKING:
    from us_swing.gui.app_service import AppService

_DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_TF_NAMES = {"1d": "daily", "3m": "3-minute"}
_CONFIRM_WORD = "CLEAR"
_SP500_SIZE = 503
_STATS_REFRESH_S = 15.0   # stats re-read while a download runs
_SECONDS_1D = 1.0   # measured on TWS: one 1d request per stock
_SECONDS_3M = 25.0  # measured on TWS: one 3-month 3m request (parallel requests time out)
_SECONDS = {"1d": _SECONDS_1D, "3m": _SECONDS_3M}
_EMPTY = BacktestStats(0, 0, 0, None, None, 0, None)


def _qdate(day: datetime.date) -> QDate:
    return QDate(day.year, day.month, day.day)


def _pydate(day: QDate) -> datetime.date:
    return datetime.date(day.year(), day.month(), day.day())


def _day(day: datetime.date) -> str:
    return f"{day:%b} {day.day}, {day.year}"


def _stocks(n: int) -> str:
    return "1 stock" if n == 1 else f"{n:,} stocks"


def _duration(seconds: float) -> str:
    minutes = seconds / 60
    if minutes >= 48 * 60:
        return f"{minutes / 1440:.1f} days"
    if minutes >= 90:
        return f"{int(minutes // 60)} h {int(minutes % 60)} min"
    return f"{max(round(minutes), 1)} min"


def _coverage(stats: BacktestStats) -> str:
    parts = []
    if stats.first and stats.last:
        parts.append(f"Daily {_day(stats.first)} – {_day(stats.last)}")
    if stats.first_3m:
        parts.append(f"3-minute from {_day(stats.first_3m)}")
    return " · ".join(parts)


def _size(n: int) -> str:
    return f"{n / 1e9:.1f} GB" if n >= 1e9 else f"{n / 1e6:.0f} MB"


def _separator() -> QFrame:
    sep = QFrame()
    sep.setObjectName("side_sep")
    sep.setFixedHeight(1)
    return sep


def _group_label(title: str) -> QLabel:
    label = QLabel(title)
    label.setObjectName("panel_group")
    return label


def _key_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("details_key")
    return label


def build_clear_dialog(detail: str, parent: QWidget) -> tuple[QDialog, QLineEdit, QPushButton]:
    """Frameless confirm whose Clear button enables only after typing CLEAR (SRD-GUI-030.005)."""
    # Imported here: active_cycles_panel pulls in the execution package.
    from us_swing.gui.active_cycles_panel import _ConfirmDialog

    dialog = _ConfirmDialog(
        "CLEAR BACKTEST DATA", f"Clear all backtest candles?\n{detail}",
        confirm_text="Clear", accent=C.RED, parent=parent,
    )
    button = next(b for b in dialog.findChildren(QPushButton) if b.text() == "Clear")
    button.setStyleSheet(
        button.styleSheet()
        + f"QPushButton:disabled {{ background: {C.OVERLAY}; color: {C.MUTED}; outline: none; }}"
    )
    button.setEnabled(False)
    field = QLineEdit()
    field.setPlaceholderText(f"Type {_CONFIRM_WORD} to confirm")
    field.setStyleSheet("QLineEdit { outline: none; } QLineEdit:focus { outline: none; }")
    field.textChanged.connect(lambda text: button.setEnabled(text == _CONFIRM_WORD))
    card = dialog.findChild(QFrame, "confirm_card")
    if card is not None and card.layout() is not None:
        card.layout().addWidget(field)  # type: ignore[union-attr]
    return dialog, field, button


class BacktestDataPanel(QWidget):
    """SRD-GUI-030.001–.009 — Backtest data section (Option D: one sentence, one button).

    ``state`` is ``empty``, ``running``, ``behind`` or ``ok`` for the section dot.
    """

    def __init__(
        self, svc: AppService, root: Path = DEFAULT_ROOT, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._svc = svc
        self._root = root
        self._stats: BacktestStats | None = None
        self._running = svc.is_backtest_running()
        self._stats_asked = 0.0
        self._progress: dict[str, tuple[int, int]] = {}
        self._tf_now = ""
        self._symbol = ""
        self.state = "empty"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_status())
        layout.addWidget(_separator())
        layout.addWidget(self._build_range())
        layout.addWidget(_separator())
        layout.addWidget(self._build_auto())
        layout.addStretch()
        layout.addWidget(_separator())
        layout.addLayout(self._build_actions())

        self.inputs: list[QWidget] = [
            self._start, self._end, self._latest, self._auto, self._time, *self._days,
        ]
        self.load()

        svc.backtest_stats_changed.connect(self._on_stats)
        svc.backtest_progress.connect(self._on_progress)
        svc.backtest_finished.connect(self._on_finished)
        svc.feed_status_changed.connect(lambda _s: self._render())
        self._render()
        QTimer.singleShot(300, svc.refresh_backtest_stats)

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_status(self) -> QWidget:
        top = QWidget()
        top_l = QVBoxLayout(top)
        top_l.setContentsMargins(14, 16, 14, 14)
        top_l.setSpacing(8)
        self._headline = QLabel("Checking backtest data…")
        self._headline.setObjectName("data_headline")
        self._headline.setWordWrap(True)
        self._detail = _key_label("")
        self._detail.setWordWrap(True)
        self._bar = QProgressBar()
        self._bar.setObjectName("data_bar")
        self._bar.setRange(0, 100)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(4)
        self._bar.hide()
        self._info_row = QWidget()
        info = QHBoxLayout(self._info_row)
        info.setContentsMargins(0, 0, 0, 0)
        self._info = _key_label("")
        self._eta = _key_label("")
        info.addWidget(self._info, 1)
        info.addWidget(self._eta)
        self._start_btn = QPushButton("Download")
        self._start_btn.setObjectName("run_btn")
        self._start_btn.clicked.connect(self._on_start_clicked)
        self._hint = _key_label("")
        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        button_row.addWidget(self._start_btn)
        button_row.addWidget(self._hint, 1)
        top_l.addWidget(self._headline)
        top_l.addWidget(self._detail)
        top_l.addWidget(self._bar)
        top_l.addWidget(self._info_row)
        top_l.addLayout(button_row)
        return top

    def _build_range(self) -> QWidget:
        box = QWidget()
        body = QVBoxLayout(box)
        body.setContentsMargins(14, 12, 14, 12)
        body.setSpacing(8)
        body.addWidget(_group_label("RANGE"))
        self._start = self._date_edit()
        self._end = self._date_edit()
        self._latest = QCheckBox("Up to latest trading day")
        self._latest.toggled.connect(self._on_latest_toggled)
        self._end.dateChanged.connect(self._clamp_start)
        self._start.dateChanged.connect(lambda _d: self._render())
        start_row = QHBoxLayout()
        start_row.addWidget(_key_label("Start date"))
        start_row.addStretch()
        start_row.addWidget(self._start)
        end_row = QHBoxLayout()
        end_row.addWidget(_key_label("End date"))
        end_row.addStretch()
        end_row.addWidget(self._latest)
        end_row.addWidget(self._end)
        body.addLayout(start_row)
        body.addLayout(end_row)
        return box

    def _build_auto(self) -> QWidget:
        box = QWidget()
        body = QVBoxLayout(box)
        body.setContentsMargins(14, 12, 14, 12)
        body.setSpacing(8)
        body.addWidget(_group_label("AUTO DELTA"))
        self._auto = QCheckBox("Fill new days automatically")
        self._auto.toggled.connect(lambda _on: self._sync_auto_fields())
        self._time = QTimeEdit()
        self._time.setDisplayFormat("HH:mm")
        self._time.setFixedWidth(80)
        self._zone = _key_label("US/Eastern")
        time_row = QHBoxLayout()
        time_row.addWidget(self._auto)
        time_row.addStretch()
        time_row.addWidget(self._time)
        time_row.addWidget(self._zone)
        day_row = QHBoxLayout()
        day_row.setSpacing(4)
        self._days: list[QPushButton] = []
        for name in _DAY_NAMES:
            chip = QPushButton(name)
            chip.setObjectName("filter_chip")
            chip.setCheckable(True)
            day_row.addWidget(chip)
            self._days.append(chip)
        day_row.addStretch()
        body.addLayout(time_row)
        body.addLayout(day_row)
        return box

    def _build_actions(self) -> QHBoxLayout:
        footer = QHBoxLayout()
        footer.setContentsMargins(14, 12, 14, 12)
        footer.setSpacing(8)
        self._facts = _key_label("")
        self._clear_btn = QPushButton("Clear database…")
        self._clear_btn.setObjectName("link_danger")
        set_icon(self._clear_btn, "trash-2", "danger")
        self._clear_btn.clicked.connect(self._on_clear_clicked)
        footer.addWidget(self._facts)
        footer.addStretch()
        footer.addWidget(self._clear_btn)
        return footer

    @staticmethod
    def _date_edit() -> QDateEdit:
        edit = QDateEdit()
        edit.setCalendarPopup(True)
        edit.setDisplayFormat("yyyy-MM-dd")
        edit.setMinimumDate(QDate(2000, 1, 1))
        edit.setMaximumDate(QDate.currentDate())
        return edit

    # ── Settings (SRD-GUI-030.002 / .003) ─────────────────────────────────────

    def load(self, settings: BacktestDataSettings | None = None) -> None:
        """Fill the fields from ``settings`` or from ``settings.json``."""
        s = settings or BacktestDataSettings.load(self._root)
        self._latest.setChecked(s.end_date is None)
        self._end.setDate(_qdate(s.end_date) if s.end_date else QDate.currentDate())
        self._start.setDate(_qdate(s.start_date))
        self._auto.setChecked(s.auto_delta)
        self._time.setTime(QTime(s.run_time.hour, s.run_time.minute))
        for index, chip in enumerate(self._days):
            chip.setChecked(index in s.run_days)
        self._on_latest_toggled(self._latest.isChecked())

    def save(self) -> None:
        """Write the fields to ``settings.json``."""
        latest = self._latest.isChecked()
        run = self._time.time()
        BacktestDataSettings(
            start_date=_pydate(self._start.date()),
            end_date=None if latest else _pydate(self._end.date()),
            auto_delta=latest and self._auto.isChecked(),
            run_time=datetime.time(run.hour(), run.minute()),
            run_days=tuple(i for i, chip in enumerate(self._days) if chip.isChecked()),
        ).save(self._root)

    def defaults(self) -> None:
        """Fill the fields with the default settings (saved on Apply)."""
        self.load(BacktestDataSettings())

    def _on_latest_toggled(self, latest: bool) -> None:
        self._end.setEnabled(not latest)
        if not latest:
            self._auto.setChecked(False)
        self._auto.setEnabled(latest)
        self._clamp_start()
        self._sync_auto_fields()

    def _clamp_start(self) -> None:
        latest = self._latest.isChecked()
        self._start.setMaximumDate(QDate.currentDate() if latest else self._end.date())
        self._render()

    def _sync_auto_fields(self) -> None:
        on = self._auto.isEnabled() and self._auto.isChecked()
        self._time.setEnabled(on)
        for chip in self._days:
            chip.setEnabled(on)

    def _range_changed(self) -> bool:
        saved = BacktestDataSettings.load(self._root)
        end = None if self._latest.isChecked() else _pydate(self._end.date())
        return saved.start_date != _pydate(self._start.date()) or saved.end_date != end

    def _full_estimate(self) -> str:
        end = QDate.currentDate() if self._latest.isChecked() else self._end.date()
        years = max(self._start.date().daysTo(end) / 365.25, 0.0)
        stocks = len(self._svc.get_sp500_universe()) or _SP500_SIZE
        windows = stocks * math.ceil(years * 4)
        seconds = stocks * _SECONDS_1D + windows * _SECONDS_3M
        return f"{stocks + windows:,} requests for this range · about {_duration(seconds)}"

    # ── Service signals ───────────────────────────────────────────────────────

    def _on_stats(self, stats: object) -> None:
        if isinstance(stats, BacktestStats):
            self._stats = stats
            self._render()

    def _on_progress(self, tf: str, done: int, total: int, symbol: str) -> None:
        if tf not in _TF_NAMES:
            return
        self._running = True
        self._progress[tf] = (done, total)
        self._tf_now = tf
        self._symbol = symbol
        if time.monotonic() - self._stats_asked >= _STATS_REFRESH_S:
            self._stats_asked = time.monotonic()
            self._svc.refresh_backtest_stats()
        self._render()

    def _on_finished(self, _ok: bool, message: str) -> None:
        self._running = False
        self._progress = {}
        self._tf_now = ""
        self._hint.setText(message)
        self._render()

    # ── Actions (SRD-GUI-030.004 / .005 / .009) ───────────────────────────────

    def _on_start_clicked(self) -> None:
        if self._running:
            self._svc.stop_backtest_download()
            self._start_btn.setEnabled(False)
            self._hint.setText("Pausing after the current request…")
            return
        if self._range_changed():
            self.save()
        if not self._svc.start_backtest_download():
            return
        self._running = True
        stats = self._stats
        self._progress = {"1d": (0, stats.missing_1d), "3m": (0, stats.missing_3m)} if stats else {}
        self._tf_now = ""
        self._hint.setText("")
        self._render()

    def _on_clear_clicked(self) -> None:
        if not self._confirm_clear():
            return
        freed = _size(self._stats.size_bytes) if self._stats and self._stats.size_bytes else ""
        if not self._svc.clear_backtest_data():
            self._hint.setText("Pause the download before clearing")
            return
        self._stats = _EMPTY
        self._hint.setText(f"Backtest data cleared · {freed} freed" if freed
                           else "Backtest data cleared")
        self._render()

    def _confirm_clear(self) -> bool:
        size = _size(self._stats.size_bytes) if self._stats else "all"
        dialog, _field, _button = build_clear_dialog(
            f"Deletes {size} of backtest candles. Settings are kept.", self
        )
        return dialog.exec() == QDialog.DialogCode.Accepted

    # ── Render (SRD-GUI-030.006 / .009) ───────────────────────────────────────

    def _render(self) -> None:
        stats = self._stats
        missing = stats.missing_1d + stats.missing_3m if stats else 0
        if self._running:
            self.state = "running"
        elif stats is None or not stats.stocks:
            self.state = "empty"
        else:
            self.state = "behind" if missing else "ok"
        self._headline.setText(self._headline_text())
        self._detail.setText(_coverage(stats) if stats and stats.stocks else "")
        self._detail.setVisible(bool(self._detail.text()))
        self._facts.setText(
            f"{_stocks(stats.stocks)} · {_size(stats.size_bytes)}" if stats and stats.stocks else ""
        )
        self._render_progress(missing)
        self._render_actions()

    def _headline_text(self) -> str:
        stats = self._stats
        if self._running:
            name = _TF_NAMES.get(self._tf_now)
            return f"Getting {name} candles" if name else "Getting candles"
        if stats is None:
            return "Checking backtest data…"
        if not stats.stocks:
            return "No backtest candles yet"
        names = [n for n, c in (("Daily", stats.missing_1d), ("3-minute", stats.missing_3m)) if c]
        if not names:
            return "All candles saved"
        return f"{' and '.join(names)} candles missing for {_stocks(stats.short_stocks)}"

    def _render_progress(self, missing: int) -> None:
        self._bar.setVisible(self._running)
        self._eta.setText("")
        if self._running:
            done = sum(d for d, _t in self._progress.values())
            total = sum(t for _d, t in self._progress.values())
            left = sum((t - d) * _SECONDS[tf] for tf, (d, t) in self._progress.items())
            self._bar.setValue(round(done * 100 / total) if total else 0)
            parts = [f"{done:,} of {total:,}"] if total else []
            parts += [self._symbol] if self._symbol else []
            parts += [f"about {_duration(left)} left"] if total else []
            self._info.setText(" · ".join(parts))
            if total:
                finish = datetime.datetime.now() + datetime.timedelta(seconds=left)
                fmt = "%b %d %H:%M" if left >= 20 * 3600 else "%H:%M"
                self._eta.setText(f"Done around {finish:{fmt}}")
        elif self._range_changed():
            self._info.setText("Range changed · not saved yet")
        elif self.state == "empty":
            self._info.setText(self._full_estimate())
        elif self.state == "behind" and self._stats is not None:
            seconds = self._stats.missing_1d * _SECONDS_1D + self._stats.missing_3m * _SECONDS_3M
            self._info.setText(f"{missing:,} requests · about {_duration(seconds)}")
        else:
            self._info.setText("")
        self._info_row.setVisible(bool(self._info.text()))

    def _render_actions(self) -> None:
        connected = self._svc.connection_status is ConnectionStatus.CONNECTED
        if self._running:
            label, icon, enabled = "Pause", "pause", True
        elif self._range_changed():
            label, icon, enabled = "Save range and download", "play", connected
        elif self.state == "ok":
            label, icon, enabled = "Up to date", "check", False
        elif self.state == "empty":
            label, icon, enabled = "Download", "play", connected
        else:
            label, icon, enabled = "Download missing", "play", connected
        self._start_btn.setText(label)
        set_icon(self._start_btn, icon, "go")
        self._start_btn.setEnabled(enabled)
        self._clear_btn.setEnabled(connected and not self._running)
        if not connected and not self._running:
            self._hint.setText("Connect TWS to download")
        elif self._hint.text() == "Connect TWS to download":
            self._hint.setText("")
