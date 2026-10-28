"""
Module: MD-GUI-030.001.M01 — gui/backtest_data_panel.py
Parent SRD: SRD-GUI-030.001

Backtest data section in Settings: status card, range and auto delta fields, download
actions and a type-to-confirm clear. Business logic lives in AppService / backtest.
"""
from __future__ import annotations

import datetime
import math
import time
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

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

_ET = ZoneInfo("America/New_York")
_DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_STAT_KEYS = ("1d bars", "3m bars", "Last delta", "Disk")
_CONFIRM_WORD = "CLEAR"
_SP500_SIZE = 503
_STATS_REFRESH_S = 15.0   # stats re-read while a download runs
_SECONDS_1D = 1.0   # measured on TWS: one 1d request per stock
_SECONDS_3M = 25.0  # measured on TWS: one 3-month 3m request (parallel requests time out)


def _qdate(day: datetime.date) -> QDate:
    return QDate(day.year, day.month, day.day)


def _pydate(day: QDate) -> datetime.date:
    return datetime.date(day.year(), day.month(), day.day())


def _compact(n: int) -> str:
    if n >= 100_000_000:
        return f"{n / 1e6:.0f}M"
    if n >= 1_000_000:
        return f"{n / 1e6:.1f}M"
    if n >= 1_000:
        return f"{n / 1e3:.0f}K"
    return str(n)


def _size(n: int) -> str:
    return f"{n / 1e9:.1f} GB" if n >= 1e9 else f"{n / 1e6:.0f} MB"


def _separator() -> QFrame:
    sep = QFrame()
    sep.setObjectName("side_sep")
    sep.setFixedHeight(1)
    return sep


def _set_state(widget: QWidget, state: str) -> None:
    widget.setProperty("state", state)
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)


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
    """SRD-GUI-030.001–.006 — Backtest data section (Option A, single card).

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
        self.state = "empty"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_status())
        layout.addWidget(_separator())
        layout.addWidget(self._build_strip())
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
        svc.feed_status_changed.connect(lambda _s: self._update_actions())
        self._update_actions()
        QTimer.singleShot(300, svc.refresh_backtest_stats)

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_status(self) -> QWidget:
        top = QWidget()
        top_l = QVBoxLayout(top)
        top_l.setContentsMargins(14, 14, 14, 12)
        top_l.setSpacing(8)
        head = QHBoxLayout()
        self._summary = QLabel("Checking backtest data…")
        self._summary.setObjectName("data_summary")
        self._summary.setWordWrap(True)
        self._pill = QLabel("")
        self._pill.setObjectName("data_pill")
        self._pill.hide()
        head.addWidget(self._summary, 1)
        head.addWidget(self._pill)
        top_l.addLayout(head)
        self._bars: dict[str, QProgressBar] = {}
        self._counts: dict[str, QLabel] = {}
        for tf in ("1d", "3m"):
            row = QHBoxLayout()
            row.setSpacing(8)
            bar = QProgressBar()
            bar.setObjectName("data_bar")
            bar.setRange(0, 100)
            bar.setTextVisible(False)
            bar.setFixedHeight(4)
            count = _key_label("—")
            row.addWidget(_key_label(tf))
            row.addWidget(bar, 1)
            row.addWidget(count)
            top_l.addLayout(row)
            self._bars[tf] = bar
            self._counts[tf] = count
        return top

    def _build_strip(self) -> QWidget:
        strip = QWidget()
        strip_l = QHBoxLayout(strip)
        strip_l.setContentsMargins(0, 0, 0, 0)
        strip_l.setSpacing(0)
        self._values: dict[str, QLabel] = {}
        for index, key in enumerate(_STAT_KEYS):
            if index:
                line = QFrame()
                line.setObjectName("side_sep")
                line.setFixedWidth(1)
                strip_l.addWidget(line)
            cell = QWidget()
            cell_l = QVBoxLayout(cell)
            cell_l.setContentsMargins(14, 10, 14, 10)
            cell_l.setSpacing(2)
            value = QLabel("—")
            value.setObjectName("data_stat_value")
            cell_l.addWidget(_group_label(key.upper()))
            cell_l.addWidget(value)
            strip_l.addWidget(cell, 1)
            self._values[key] = value
        return strip

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
        start_row = QHBoxLayout()
        start_row.addWidget(_key_label("Start date"))
        start_row.addStretch()
        start_row.addWidget(self._start)
        end_row = QHBoxLayout()
        end_row.addWidget(_key_label("End date"))
        end_row.addStretch()
        end_row.addWidget(self._latest)
        end_row.addWidget(self._end)
        self._estimate = _key_label("")
        self._start.dateChanged.connect(lambda _d: self._update_estimate())
        body.addLayout(start_row)
        body.addLayout(end_row)
        body.addWidget(self._estimate)
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
        self._start_btn = QPushButton("Start download")
        self._start_btn.setObjectName("run_btn")
        set_icon(self._start_btn, "play", "go")
        self._start_btn.clicked.connect(self._on_start_clicked)
        self._delta_btn = QPushButton("Fill delta now")
        set_icon(self._delta_btn, "refresh-cw", "info")
        self._delta_btn.clicked.connect(self._on_delta_clicked)
        self._hint = _key_label("")
        self._clear_btn = QPushButton("Clear database…")
        self._clear_btn.setObjectName("link_danger")
        set_icon(self._clear_btn, "trash-2", "danger")
        self._clear_btn.clicked.connect(self._on_clear_clicked)
        footer.addWidget(self._start_btn)
        footer.addWidget(self._delta_btn)
        footer.addWidget(self._hint)
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
        self._update_estimate()

    def _sync_auto_fields(self) -> None:
        on = self._auto.isEnabled() and self._auto.isChecked()
        self._time.setEnabled(on)
        for chip in self._days:
            chip.setEnabled(on)

    def _update_estimate(self) -> None:
        end = QDate.currentDate() if self._latest.isChecked() else self._end.date()
        years = max(self._start.date().daysTo(end) / 365.25, 0.0)
        stocks = len(self._svc.get_sp500_universe()) or _SP500_SIZE
        windows = stocks * math.ceil(years * 4)
        minutes = (stocks * _SECONDS_1D + windows * _SECONDS_3M) / 60
        if minutes >= 48 * 60:
            took = f"{minutes / 1440:.1f} days"
        elif minutes >= 90:
            took = f"{minutes / 60:.0f} h"
        else:
            took = f"{max(minutes, 1):.0f} min"
        self._estimate.setText(f"Full download ≈ {stocks + windows:,} requests · about {took}")

    # ── Service signals ───────────────────────────────────────────────────────

    def _on_stats(self, stats: object) -> None:
        if not isinstance(stats, BacktestStats):
            return
        self._stats = stats
        if not stats.stocks:
            self._summary.setText("No backtest data yet")
            for value in self._values.values():
                value.setText("—")
        else:
            noun = "stock" if stats.stocks == 1 else "stocks"
            self._summary.setText(f"{stats.stocks} {noun} · {stats.first} to {stats.last}")
            self._values["1d bars"].setText(_compact(stats.bars_1d))
            self._values["3m bars"].setText(_compact(stats.bars_3m))
            last = stats.last_delta
            self._values["Last delta"].setText(
                last.astimezone(_ET).strftime("%b %d %H:%M") if last else "—"
            )
            self._values["Disk"].setText(_size(stats.size_bytes))
        self._update_estimate()
        self._refresh_state()

    def _on_progress(self, tf: str, done: int, total: int, _symbol: str) -> None:
        if tf not in self._bars:
            return
        self._bars[tf].setValue(round(done * 100 / total) if total else 0)
        self._counts[tf].setText(f"{done:,} of {total:,} this run")
        if time.monotonic() - self._stats_asked >= _STATS_REFRESH_S:
            self._stats_asked = time.monotonic()
            self._svc.refresh_backtest_stats()

    def _on_finished(self, _ok: bool, message: str) -> None:
        self._running = False
        self._hint.setText(message)
        self._update_actions()
        self._refresh_state()

    # ── Actions (SRD-GUI-030.004 / .005) ──────────────────────────────────────

    def _on_start_clicked(self) -> None:
        if self._running:
            self._svc.stop_backtest_download()
            self._start_btn.setEnabled(False)
            self._hint.setText("Pausing after the current request…")
            return
        self._begin(self._svc.start_backtest_download())

    def _on_delta_clicked(self) -> None:
        self._begin(self._svc.fill_backtest_delta())

    def _begin(self, started: bool) -> None:
        if not started:
            return
        self._running = True
        for bar in self._bars.values():
            bar.setValue(0)
        self._hint.setText("")
        self._update_actions()
        self._refresh_state()

    def _on_clear_clicked(self) -> None:
        if not self._confirm_clear():
            return
        freed = _size(self._stats.size_bytes) if self._stats and self._stats.size_bytes else ""
        if not self._svc.clear_backtest_data():
            self._hint.setText("Pause the download before clearing")
            return
        for tf, bar in self._bars.items():
            bar.setValue(0)
            self._counts[tf].setText("—")
        self._summary.setText("No backtest data yet")
        self._hint.setText(f"Backtest data cleared · {freed} freed" if freed
                           else "Backtest data cleared")

    def _confirm_clear(self) -> bool:
        size = _size(self._stats.size_bytes) if self._stats else "all"
        dialog, _field, _button = build_clear_dialog(
            f"Deletes {size} of backtest candles. Settings are kept.", self
        )
        return dialog.exec() == QDialog.DialogCode.Accepted

    def _update_actions(self) -> None:
        connected = self._svc.connection_status is ConnectionStatus.CONNECTED
        self._start_btn.setText("Pause" if self._running else "Start download")
        set_icon(self._start_btn, "pause" if self._running else "play", "go")
        self._start_btn.setEnabled(connected or self._running)
        self._delta_btn.setEnabled(connected and not self._running)
        self._clear_btn.setEnabled(connected and not self._running)
        if not connected and not self._running:
            self._hint.setText("Connect TWS to download")
        elif self._hint.text() == "Connect TWS to download":
            self._hint.setText("")

    # ── State (SRD-GUI-030.006) ───────────────────────────────────────────────

    def _refresh_state(self) -> None:
        stats = self._stats
        if self._running:
            self.state = "running"
        elif stats is None or not stats.stocks or stats.last is None:
            self.state = "empty"
        else:
            saved = BacktestDataSettings.load(self._root).end_date
            target = saved or datetime.date.fromisoformat(self._svc.get_last_trading_day())
            self.state = "behind" if stats.last < target else "ok"
        pill = {"running": ("DOWNLOADING", "downloading"), "behind": ("BEHIND", "partial"),
                "ok": ("UP TO DATE", "complete")}.get(self.state)
        self._pill.setText(pill[0] if pill else "")
        self._pill.setVisible(pill is not None)
        if pill is not None:
            _set_state(self._pill, pill[1])
