"""
Module: MD-GUI-031.003.M03 — Backtest workspace
Parent SRD: SRD-GUI-031.003, SRD-GUI-031.004, SRD-GUI-031.011, SRD-GUI-031.012

Builder on the left; step strip, data check and the Step 1 view on the right.
Estimates and runs go to ``BacktestService`` in worker threads.
"""
from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING

import pandas as pd
from PyQt6.QtCore import QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QShowEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from us_swing.backtest.cache import StepCache
from us_swing.backtest.results import ResultsStore
from us_swing.backtest.service import BacktestService, DailyList, Estimate
from us_swing.backtest.spec import RunPlan
from us_swing.backtest.steps.stocks import StepCancelled, top_n
from us_swing.backtest.store import BacktestStore
from us_swing.core.backtest_bridge import list_presets, load_preset_dict
from us_swing.data.models import ConnectionStatus
from us_swing.gui.backtest_builder import BacktestBuilder
from us_swing.gui.cards import GAP, card, gutter
from us_swing.gui.icons import set_icon

if TYPE_CHECKING:
    from us_swing.gui.app_service import AppService

_log = logging.getLogger(__name__)

STEPS = ("Stocks", "Signals", "Portfolio", "Report")
_ESTIMATE_DELAY_MS = 500
_RUN_TEXT = "Run Step 1"


class _EstimateWorker(QThread):
    done = pyqtSignal(int, object)  # (ticket, Estimate)

    def __init__(self, service: BacktestService, plan: RunPlan, user_id: str, ticket: int,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service, self._plan, self._user, self._ticket = service, plan, user_id, ticket

    def run(self) -> None:
        try:
            est = self._service.estimate(self._plan, self._user)
        except Exception as exc:  # noqa: BLE001 — shown on the data check line
            _log.warning("[Backtest] Data check failed: %s", exc)
            est = Estimate([], [], [], False, 0, 0, [f"Data check failed: {exc}"])
        self.done.emit(self._ticket, est)


class _RunWorker(QThread):
    progress = pyqtSignal(int, int)
    done = pyqtSignal(object)  # DailyList
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, service: BacktestService, plan: RunPlan, user_id: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service, self._plan, self._user = service, plan, user_id
        self._cancel = False

    def request_cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            out = self._service.run_stocks(
                self._plan, self._user, progress=self.progress.emit, cancel=lambda: self._cancel
            )
        except StepCancelled:
            self.cancelled.emit()
            return
        except Exception as exc:  # noqa: BLE001 — shown to the user
            _log.warning("[Backtest] Step 1 failed: %s", exc)
            self.failed.emit(str(exc))
            return
        self.done.emit(out)


def data_check_text(est: Estimate) -> str:
    """One line of counts, then any plan errors on their own lines."""
    line = (f"{len(est.symbols)} stocks · {len(est.missing_1d)} missing 1d · "
            f"{len(est.missing_3m)} missing 3m candles")
    if not est.benchmark_ok:
        line += " · SPY missing"
    if est.days_total:
        line += f" · Step 1: {est.days_cached} of {est.days_total} days cached"
    return "\n".join([line, *est.errors])


def _table(headers: list[str]) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().setVisible(False)  # type: ignore[union-attr]
    table.horizontalHeader().setStretchLastSection(True)  # type: ignore[union-attr]
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    return table


class BacktestWorkspace(QWidget):
    """SRD-GUI-031.003–.004, .011–.012 — the Backtest screen."""

    def __init__(self, svc: AppService, service: BacktestService | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._svc = svc
        self._service = service or BacktestService(
            BacktestStore(), StepCache(), ResultsStore(),
            svc.get_sp500_universe, load_preset_dict,
        )
        self._estimate: Estimate | None = None
        self._ticket = 0
        self._estimators: list[_EstimateWorker] = []
        self._runner: _RunWorker | None = None
        self._daily: DailyList | None = None

        gutter(self)
        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(GAP)
        self.builder = BacktestBuilder()
        main.addWidget(card(self.builder))
        right = QVBoxLayout()
        right.setSpacing(GAP)
        right.addWidget(card(self._build_header()))
        right.addWidget(card(self._build_step1()), 1)
        main.addLayout(right, 1)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(_ESTIMATE_DELAY_MS)
        self._timer.timeout.connect(self._start_estimate)
        # builder → changed → debounced data check (SRD-GUI-031.004)
        self.builder.changed.connect(self._timer.start)
        # builder → changed → Step 1 view re-filtered by Stocks per day
        self.builder.changed.connect(self._render_days)
        svc.sp500_updated.connect(self._load_universe)
        svc.backtest_finished.connect(lambda _ok, _msg: self._timer.start())
        svc.feed_status_changed.connect(lambda _s: self._render_buttons())
        self._load_universe()
        self.refresh_presets()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_header(self) -> QWidget:
        box = QWidget()
        body = QVBoxLayout(box)
        body.setContentsMargins(14, 12, 14, 12)
        body.setSpacing(10)
        title = QLabel("Backtest")
        title.setObjectName("page_title")
        body.addWidget(title)
        strip = QHBoxLayout()
        strip.setSpacing(8)
        self.pills: list[QLabel] = []
        for name in STEPS:
            pill = QLabel()
            pill.setObjectName("data_pill")
            self.pills.append(pill)
            strip.addWidget(pill)
            self.set_step(len(self.pills) - 1, "waiting")
        strip.addStretch()
        body.addLayout(strip)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.check_label = QLabel("Checking data…")
        self.check_label.setObjectName("details_key")
        self.check_label.setWordWrap(True)
        self.download_btn = QPushButton("Download")
        set_icon(self.download_btn, "download")
        self.download_btn.clicked.connect(self._on_download)
        self.run_btn = QPushButton(_RUN_TEXT)
        self.run_btn.setObjectName("run_btn")
        set_icon(self.run_btn, "play", "inverse")
        self.run_btn.clicked.connect(self._on_run_clicked)
        row.addWidget(self.check_label, 1)
        row.addWidget(self.download_btn)
        row.addWidget(self.run_btn)
        body.addLayout(row)
        self._render_buttons()
        return box

    def _build_step1(self) -> QWidget:
        box = QWidget()
        body = QVBoxLayout(box)
        body.setContentsMargins(14, 12, 14, 12)
        body.setSpacing(8)
        head = QLabel("STEP 1 · STOCKS")
        head.setObjectName("view_head")
        body.addWidget(head)
        tables = QHBoxLayout()
        tables.setSpacing(GAP)
        self.days_table = _table(["Date", "Stocks"])
        self.days_table.setFixedWidth(220)
        self.days_table.itemSelectionChanged.connect(self._render_stocks)
        self.stocks_table = _table(["Rank", "Symbol", "Score"])
        tables.addWidget(self.days_table)
        tables.addWidget(self.stocks_table, 1)
        body.addLayout(tables, 1)
        return box

    # ── Inputs ────────────────────────────────────────────────────────────────

    def _user_id(self) -> str:
        return str(self._svc.get_active_user().user_id)

    def _load_universe(self) -> None:
        self.builder.set_universe(self._svc.get_sp500_universe())

    def refresh_presets(self) -> None:
        """Reload the screener picker (presets may change in the Screener screen)."""
        try:
            self.builder.set_presets(list_presets(self._user_id()))
        except Exception as exc:  # noqa: BLE001 — an empty picker is shown instead
            _log.warning("[Backtest] Could not load screener presets: %s", exc)

    def showEvent(self, event: QShowEvent | None) -> None:
        self.refresh_presets()
        super().showEvent(event)

    # ── Data check (SRD-GUI-031.004) ──────────────────────────────────────────

    def _start_estimate(self) -> None:
        self._ticket += 1
        worker = _EstimateWorker(self._service, self.builder.plan(), self._user_id(),
                                 self._ticket, self)
        worker.done.connect(self._on_estimate)
        worker.finished.connect(lambda: self._estimators.remove(worker))
        self._estimators.append(worker)
        worker.start()

    def _on_estimate(self, ticket: int, est: Estimate) -> None:
        if ticket != self._ticket:
            return
        self._estimate = est
        self.check_label.setText(data_check_text(est))
        if self._runner is None and self._daily is None:
            cached = est.days_total > 0 and est.days_cached == est.days_total
            self.set_step(0, "cached" if cached else "waiting")
        self._render_buttons()

    def _render_buttons(self) -> None:
        est = self._estimate
        connected = self._svc.connection_status is ConnectionStatus.CONNECTED
        missing = est is not None and bool(est.missing_1d or est.missing_3m)
        self.download_btn.setEnabled(
            connected and missing and not self._svc.is_backtest_running()
        )
        self.download_btn.setToolTip("" if connected else "Connect TWS to download")
        if self._runner is None:
            self.run_btn.setEnabled(est is not None and not est.errors)

    def _on_download(self) -> None:
        if self._svc.start_backtest_download():
            _log.info("[Backtest] Candle download started from the Backtest screen")
        self._render_buttons()

    # ── Step strip (SRD-GUI-031.003) ──────────────────────────────────────────

    def set_step(self, index: int, state: str, done: int = 0, total: int = 0) -> None:
        """Show a step as waiting, running (done of total), done or cached."""
        text = {"waiting": "Waiting", "done": "Done", "cached": "Cached"}.get(
            state, f"{done} of {total}"
        )
        qss_state = {"running": "downloading", "done": "complete", "cached": "complete"}.get(
            state, ""
        )
        pill = self.pills[index]
        pill.setText(f"{index + 1} {STEPS[index]} · {text}")
        pill.setProperty("state", qss_state)
        style = pill.style()
        if style is not None:
            style.unpolish(pill)
            style.polish(pill)

    # ── Run (SRD-GUI-031.011) ─────────────────────────────────────────────────

    def _on_run_clicked(self) -> None:
        if self._runner is not None:
            self._runner.request_cancel()
            self.run_btn.setEnabled(False)
            return
        runner = _RunWorker(self._service, self.builder.plan(), self._user_id(), self)
        runner.progress.connect(lambda d, t: self.set_step(0, "running", d, t))
        runner.done.connect(self._on_run_done)
        runner.failed.connect(self._on_run_failed)
        runner.cancelled.connect(self._on_run_cancelled)
        runner.finished.connect(self._on_runner_finished)
        self._runner = runner
        self.run_btn.setText("Cancel")
        set_icon(self.run_btn, "square-x", "inverse")
        self.set_step(0, "running")
        runner.start()

    def _on_run_done(self, daily: DailyList) -> None:
        self._daily = daily
        self.set_step(0, "done")
        self._render_days()

    def _on_run_failed(self, message: str) -> None:
        self.set_step(0, "waiting")
        self.check_label.setText(f"Step 1 failed: {message}")

    def _on_run_cancelled(self) -> None:
        self.set_step(0, "waiting")
        _log.info("[Backtest] Step 1 cancelled — finished days are kept")

    def _on_runner_finished(self) -> None:
        self._runner = None
        self.run_btn.setText(_RUN_TEXT)
        set_icon(self.run_btn, "play", "inverse")
        self._render_buttons()
        self._timer.start()

    # ── Step 1 view (SRD-GUI-031.012) ─────────────────────────────────────────

    def _shown(self) -> pd.DataFrame:
        if self._daily is None:
            return pd.DataFrame(columns=["date", "symbol", "score", "rank"])
        return top_n(self._daily.frame, self.builder.top_n)

    def _render_days(self) -> None:
        if self._daily is None:
            return
        counts = self._shown().groupby("date").size()
        days = sorted(self._daily.days, reverse=True)
        selected = self._selected_day()
        self.days_table.blockSignals(True)
        self.days_table.setRowCount(len(days))
        for row, day in enumerate(days):
            self.days_table.setItem(row, 0, QTableWidgetItem(day.isoformat()))
            self.days_table.setItem(row, 1, QTableWidgetItem(str(int(counts.get(day, 0)))))
        self.days_table.blockSignals(False)
        keep = days.index(selected) if selected in days else 0
        if days:
            self.days_table.selectRow(keep)
        self._render_stocks()

    def _selected_day(self) -> datetime.date | None:
        rows = self.days_table.selectionModel()
        if rows is None or not rows.selectedRows():
            return None
        item = self.days_table.item(rows.selectedRows()[0].row(), 0)
        return None if item is None else pd.Timestamp(item.text()).date()

    def _render_stocks(self) -> None:
        day = self._selected_day()
        frame = self._shown()
        rows = frame[frame["date"] == day] if day is not None else frame.iloc[0:0]
        self.stocks_table.setRowCount(len(rows))
        for i, rec in enumerate(rows.itertuples()):
            self.stocks_table.setItem(i, 0, QTableWidgetItem(str(rec.rank)))
            self.stocks_table.setItem(i, 1, QTableWidgetItem(str(rec.symbol)))
            self.stocks_table.setItem(i, 2, QTableWidgetItem(f"{rec.score:.2f}"))
