"""
Module: MD-GUI-031.003.M03 — Backtest workspace
Parent SRD: SRD-GUI-031.003, SRD-GUI-031.004, SRD-GUI-031.011, SRD-GUI-031.012,
            SRD-GUI-031.021, SRD-GUI-031.022, SRD-GUI-031.023, SRD-GUI-031.031–.034,
            SRD-GUI-031.040, SRD-GUI-031.044, SRD-GUI-031.050–.054

Builder on the left; step strip, data check and the Trade Inspector and Detail
Report sections on the right.
Estimates and runs go to ``BacktestService`` in worker threads.
"""
from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING, Any

import pandas as pd
from PyQt6.QtCore import QSettings, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QShowEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from us_swing.backtest.cache import StepCache
from us_swing.backtest.results import ResultsStore
from us_swing.backtest.service import BacktestService, DailyList, Estimate
from us_swing.backtest.spec import RunPlan
from us_swing.backtest.steps.portfolio import VariantResult
from us_swing.backtest.steps.report import Report
from us_swing.backtest.steps.stocks import StepCancelled, top_n
from us_swing.backtest.store import BacktestStore
from us_swing.core.backtest_bridge import list_presets, load_preset_dict, load_strategies
from us_swing.data.models import ConnectionStatus
from us_swing.gui.backtest_builder import BacktestBuilder
from us_swing.gui.backtest_dock import DockSection, PanelSpec
from us_swing.gui.backtest_report_view import ReportView
from us_swing.gui.backtest_trade_chart import TradeChart
from us_swing.gui.backtest_trade_list import TradeList
from us_swing.gui.backtest_use_charts import UsePanel, margin_use, screener_use
from us_swing.gui.cards import GAP, card, gutter
from us_swing.gui.icons import set_icon
from us_swing.gui.theme import C

if TYPE_CHECKING:
    from us_swing.gui.app_service import AppService

_log = logging.getLogger(__name__)

STEPS = ("Stocks", "Signals", "Portfolio", "Report")
_ESTIMATE_DELAY_MS = 500
_RUN_TEXT = "Run"
_ALL = "All strategies"
_ET = "America/New_York"
_ALL_DAYS = "All sessions"
_DAILY_CHART_DAYS = 90


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
    """Step 1, then Step 2 when the plan has strategies (SRD-GUI-031.021)."""

    progress = pyqtSignal(int, int, int)  # (step index, done, total)
    done = pyqtSignal(object)  # DailyList
    signals_done = pyqtSignal(object)  # DataFrame of signal periods
    portfolio_done = pyqtSignal(object)  # list[VariantResult]
    report_done = pyqtSignal(object)  # list[Report]
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
        def stop() -> bool:
            return self._cancel

        try:
            daily = self._service.run_stocks(
                self._plan, self._user, cancel=stop,
                progress=lambda d, t: self.progress.emit(0, d, t),
            )
            self.done.emit(daily)
            if self._plan.strategies:
                found = self._service.run_signals(
                    self._plan, daily, cancel=stop,
                    progress=lambda d, t: self.progress.emit(1, d, t),
                )
                self.signals_done.emit(found)
                results = self._service.run_portfolio(
                    self._plan, daily, found, cancel=stop,
                    progress=lambda d, t: self.progress.emit(2, d, t),
                )
                self.portfolio_done.emit(results)
                if results:
                    self.progress.emit(3, 0, 1)
                    self.report_done.emit(self._service.build_reports(self._plan, results))
        except StepCancelled:
            self.cancelled.emit()
        except Exception as exc:  # noqa: BLE001 — shown to the user
            _log.warning("[Backtest] Run failed: %s", exc)
            self.failed.emit(str(exc))


def data_check_text(est: Estimate) -> str:
    """One line of counts, then any plan errors on their own lines."""
    line = (f"{len(est.symbols)} stocks · {len(est.missing_1d)} missing 1d · "
            f"{len(est.missing_3m)} missing 3m candles")
    if est.days_total:
        line += f" · Step 1: {est.days_cached} of {est.days_total} days cached"
    return "\n".join([line, *est.errors])


def _head(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("view_head")
    return label


def _note(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("details_key")
    return label


def _stack(top: QWidget, table: QTableWidget) -> QWidget:
    box = QWidget()
    body = QVBoxLayout(box)
    body.setContentsMargins(0, 0, 0, 0)
    body.setSpacing(6)
    body.addWidget(top)
    body.addWidget(table, 1)
    return box


def _fill(table: QTableWidget, columns: list[list[str]]) -> None:
    table.setRowCount(len(columns[0]) if columns else 0)
    for col, values in enumerate(columns):
        for row, value in enumerate(values):
            table.setItem(row, col, QTableWidgetItem(value))
    table.resizeColumnsToContents()


def _usd(value: float) -> str:
    return f"-${-value:,.2f}" if value < 0 else f"${value:,.2f}"


def _et(values: pd.Series, fmt: str = "%Y-%m-%d %H:%M") -> list[str]:
    return list(pd.DatetimeIndex(pd.to_datetime(values, utc=True)).tz_convert(_ET).strftime(fmt))


def _et_day(values: pd.Series) -> pd.Series:
    """US/Eastern session date of each timestamp."""
    times = pd.DatetimeIndex(pd.to_datetime(values, utc=True)).tz_convert(_ET)
    return pd.Series(times.date, index=values.index)


def trades_summary(trades: pd.DataFrame) -> str:
    """Trades count, net P&L and win rate (SRD-GUI-031.032)."""
    if trades.empty:
        return "TRADES · none"
    wins = int((trades["net_pnl"] > 0).sum())
    return (f"TRADES · {len(trades)} trades · net P&L {_usd(trades['net_pnl'].sum())} · "
            f"win rate {wins / len(trades):.0%}")


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
    """SRD-GUI-031.003–.004, .011–.012, .021–.023, .050–.052 — the Backtest screen."""

    chart_requested = pyqtSignal(str, str)  # (symbol, timeframe)

    def __init__(self, svc: AppService, service: BacktestService | None = None,
                 parent: QWidget | None = None, settings: QSettings | None = None) -> None:
        super().__init__(parent)
        self._svc = svc
        self._settings = settings or QSettings("USSwing", "BacktestDock")
        self._service = service or BacktestService(
            BacktestStore(), StepCache(), ResultsStore(),
            svc.get_sp500_universe, load_preset_dict, load_strategies,
        )
        self._estimate: Estimate | None = None
        self._ticket = 0
        self._estimators: list[_EstimateWorker] = []
        self._runner: _RunWorker | None = None
        self._daily: DailyList | None = None
        self._signals: pd.DataFrame | None = None
        self._results: list[VariantResult] = []
        self._variant = 0
        self._day_trades = pd.DataFrame(columns=["symbol", "direction", "entry_ts", "exit_ts"])

        gutter(self)
        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(GAP)
        self.builder = BacktestBuilder()
        scroll = QScrollArea()
        scroll.setWidget(self.builder)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedWidth(self.builder.width() + 14)
        main.addWidget(card(scroll))
        right = QVBoxLayout()
        right.setSpacing(GAP)
        right.addWidget(card(self._build_header()))
        right.addWidget(card(self._build_views()), 1)
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
        risk = getattr(svc.get_active_user(), "risk_config", None)
        if risk is not None:
            self.builder.set_account_defaults(float(risk.max_capital_value),
                                              float(risk.max_daily_loss_pct))

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

    def _build_views(self) -> QWidget:
        self.tabs = QTabWidget()
        self.inspector = DockSection("inspector", [
            [PanelSpec("chart", "Chart", "chart-candlestick", self._build_chart()),
             PanelSpec("money", "Money", "briefcase", self._build_money())],
            [PanelSpec("stocks", "Screener list", "filter", self._build_step1()),
             PanelSpec("trades", "Trades", "list", self._build_trades())],
            [PanelSpec("signals", "Signals", "activity", self._build_step2()),
             PanelSpec("log", "Decisions", "clipboard-list", self._build_log())],
        ], left=self._build_sessions(), settings=self._settings)
        self.report_view = ReportView()
        self.report_view.variant.currentIndexChanged.connect(self._render_variant)
        report_scroll = QScrollArea()
        report_scroll.setWidget(self.report_view)
        report_scroll.setWidgetResizable(True)
        report_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.report_view.setMinimumHeight(980)
        self.trade_list = TradeList()
        self.trade_list.trade_clicked.connect(self._open_trade)
        self.screener_use = UsePanel((C.BLUE, C.MUTED), ("Traded", "Not traded"), money=False)
        self.margin_use = UsePanel((C.BLUE, C.TEAL), ("Deployed peak", "Lowest margin left"),
                                   money=True)
        self.detail = DockSection("detail", [
            [PanelSpec("report", "Report", "chart-line", report_scroll)],
            [PanelSpec("tradelist", "Trade list", "list", self.trade_list)],
            [PanelSpec("screener_use", "Screener use", "filter", self.screener_use),
             PanelSpec("margin_use", "Margin use", "briefcase", self.margin_use)],
        ], settings=self._settings)
        self.tabs.addTab(self.inspector, "Trade Inspector")
        self.tabs.addTab(self.detail, "Detail Report")
        self.tabs.setCornerWidget(self.report_view.variant)
        return self.tabs

    def _build_sessions(self) -> QWidget:
        box = QWidget()
        box.setFixedWidth(480)
        body = QVBoxLayout(box)
        body.setContentsMargins(12, 8, 12, 10)
        body.setSpacing(6)
        body.addWidget(_head("SESSIONS"))
        self.days_table = _table(["Session", "Data up to", "Picks", "Trades", "Day P&L"])
        self.days_table.itemSelectionChanged.connect(self._render_day)
        body.addWidget(self.days_table, 1)
        return box

    def _build_chart(self) -> QWidget:
        box = QWidget()
        body = QVBoxLayout(box)
        body.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        self.chart_head = _note("")
        self.chart_tf = QComboBox()
        self.chart_tf.addItems(["3m", "15m", "1d"])
        self.chart_tf.setCurrentText("15m")
        self.chart_tf.setFixedWidth(80)
        self.chart_tf.currentIndexChanged.connect(self._render_chart)
        top.addWidget(self.chart_head, 1)
        top.addWidget(self.chart_tf)
        body.addLayout(top)
        self.chart = TradeChart()
        body.addWidget(self.chart, 1)
        return box

    def _build_money(self) -> QWidget:
        self.money_table = _table(["Date", "Deployed", "Lowest margin", "Margin at close",
                                   "Open value", "Equity"])
        return self.money_table

    def _build_trades(self) -> QWidget:
        self.trades_head = _note("TRADES")
        self.trades_table = _table(["Strategy", "Symbol", "Side", "Entry", "Entry $", "Shares",
                                    "Exit", "Exit $", "Reason", "Net P&L"])
        self.trades_table.itemSelectionChanged.connect(self._render_chart)
        return _stack(self.trades_head, self.trades_table)

    def _build_log(self) -> QWidget:
        self.log_table = _table(["Time", "Symbol", "Strategy", "Decision", "Margin left",
                                 "Strategy deployed"])
        return self.log_table

    def _build_step2(self) -> QWidget:
        self.strategy_filter = QComboBox()
        self.strategy_filter.setFixedWidth(220)
        self.strategy_filter.addItem(_ALL)
        self.strategy_filter.currentIndexChanged.connect(self._render_signals)
        top = QWidget()
        row = QHBoxLayout(top)
        row.setContentsMargins(0, 0, 0, 0)
        self.signals_head = _note("SIGNAL WINDOWS")
        row.addWidget(self.signals_head, 1)
        row.addWidget(self.strategy_filter)
        self.signals_table = _table(["Strategy", "Symbol", "Kind", "Start", "End", "Close"])
        self.signals_table.cellDoubleClicked.connect(self._on_signal_double_clicked)
        for col in (3, 4):
            self.signals_table.setColumnWidth(col, 150)
        return _stack(top, self.signals_table)

    def _build_step1(self) -> QWidget:
        self.stocks_head = _note("STOCKS FOR SESSION")
        self.stocks_table = _table(["Rank", "Symbol", "Score", "Session"])
        return _stack(self.stocks_head, self.stocks_table)

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

    def refresh_strategies(self) -> None:
        """Reload the live strategies (SRD-GUI-031.020)."""
        try:
            self.builder.set_strategies(load_strategies())
        except Exception as exc:  # noqa: BLE001 — an empty list is shown instead
            _log.warning("[Backtest] Could not load strategies: %s", exc)

    def showEvent(self, event: QShowEvent | None) -> None:
        self.refresh_presets()
        self.refresh_strategies()
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
        runner.progress.connect(lambda step, d, t: self.set_step(step, "running", d, t))
        runner.done.connect(self._on_run_done)
        runner.signals_done.connect(self._on_signals_done)
        runner.portfolio_done.connect(self._on_portfolio_done)
        runner.report_done.connect(self._on_report_done)
        runner.failed.connect(self._on_run_failed)
        runner.cancelled.connect(self._on_run_cancelled)
        runner.finished.connect(self._on_runner_finished)
        self._runner = runner
        self.run_btn.setText("Cancel")
        set_icon(self.run_btn, "square-x", "inverse")
        self.set_step(0, "running")
        self.set_step(1, "waiting")
        self.set_step(2, "waiting")
        self.set_step(3, "waiting")
        self._results = []
        self._variant = 0
        self.report_view.set_reports([])
        runner.start()

    def _on_run_done(self, daily: DailyList) -> None:
        self._daily = daily
        self.set_step(0, "done")
        self._render_days()

    def _on_signals_done(self, found: pd.DataFrame) -> None:
        self._signals = found
        self.set_step(1, "done")
        current = self.strategy_filter.currentText()
        self.strategy_filter.blockSignals(True)
        self.strategy_filter.clear()
        self.strategy_filter.addItems([_ALL, *sorted(set(found["strategy"]))])
        self.strategy_filter.setCurrentText(current)
        self.strategy_filter.blockSignals(False)
        self._render_signals()

    def _running_steps(self) -> list[int]:
        return [i for i in (0, 1, 2, 3) if self.pills[i].property("state") == "downloading"]

    def _on_run_failed(self, message: str) -> None:
        for step in self._running_steps():
            self.set_step(step, "waiting")
        self.check_label.setText(f"Run failed: {message}")

    def _on_run_cancelled(self) -> None:
        for step in self._running_steps():
            self.set_step(step, "waiting")
        _log.info("[Backtest] Run cancelled — finished work is kept")

    def _on_runner_finished(self) -> None:
        self._runner = None
        self.run_btn.setText(_RUN_TEXT)
        set_icon(self.run_btn, "play", "inverse")
        self._render_buttons()
        self._timer.start()

    # ── Inspector (SRD-GUI-031.051, .012 / .013) ──────────────────────────────

    def _shown(self) -> pd.DataFrame:
        if self._daily is None:
            return pd.DataFrame(columns=["date", "symbol", "score", "rank"])
        return top_n(self._daily.frame, self.builder.top_n)

    def _result(self) -> VariantResult | None:
        return self._results[self._variant] if self._variant < len(self._results) else None

    def _render_days(self) -> None:
        if self._daily is None:
            return
        picks = self._shown().groupby("date").size()
        res = self._result()
        trades = res.trades if res is not None else pd.DataFrame(columns=["entry_ts", "net_pnl"])
        by_day = trades.groupby(_et_day(trades["entry_ts"]))["net_pnl"]
        counts, pnl = by_day.size(), by_day.sum()
        days = sorted(self._daily.days, reverse=True)
        selected, show_all = self._selected_day(), self._all_selected()
        rows = [(_ALL_DAYS, "", int(picks.sum()), len(trades), float(trades["net_pnl"].sum()))]
        rows += [(day.isoformat(), self._data_day(day), int(picks.get(day, 0)),
                  int(counts.get(day, 0)), float(pnl.get(day, 0.0))) for day in days]
        self.days_table.blockSignals(True)
        self.days_table.setRowCount(len(rows))
        for row, (name, data_day, n_picks, n_trades, value) in enumerate(rows):
            for col, text in enumerate((name, data_day, str(n_picks), str(n_trades),
                                        _usd(value) if n_trades else "—")):
                self.days_table.setItem(row, col, QTableWidgetItem(text))
        self.days_table.resizeColumnsToContents()
        if show_all or not days:
            self.days_table.selectRow(0)
        else:
            self.days_table.selectRow(days.index(selected) + 1 if selected in days else 1)
        self.days_table.blockSignals(False)
        self._render_day()

    def _all_selected(self) -> bool:
        rows = self.days_table.selectionModel()
        return rows is not None and any(r.row() == 0 for r in rows.selectedRows())

    def _selected_day(self) -> datetime.date | None:
        rows = self.days_table.selectionModel()
        if rows is None or not rows.selectedRows():
            return None
        item = self.days_table.item(rows.selectedRows()[0].row(), 0)
        if item is None or item.text() == _ALL_DAYS:
            return None
        return pd.Timestamp(item.text()).date()

    def _data_day(self, session: datetime.date) -> str:
        day = None if self._daily is None else self._daily.data_days.get(session)
        return "" if day is None else day.isoformat()

    def _render_day(self) -> None:
        self._render_stocks()
        self._render_signals()
        self._render_results()

    def _render_stocks(self) -> None:
        day = self._selected_day()
        frame = self._shown()
        rows = frame[frame["date"] == day] if day is not None else frame
        self.stocks_head.setText(
            f"ALL SESSIONS · {len(rows)}" if day is None
            else f"SESSION {day.isoformat()} · DATA UP TO {self._data_day(day)} "
                 f"CLOSE · {len(rows)}"
        )
        self.stocks_table.setRowCount(len(rows))
        for i, rec in enumerate(rows.itertuples()):
            self.stocks_table.setItem(i, 0, QTableWidgetItem(str(rec.rank)))
            self.stocks_table.setItem(i, 1, QTableWidgetItem(str(rec.symbol)))
            self.stocks_table.setItem(i, 2, QTableWidgetItem(f"{rec.score:.2f}"))
            self.stocks_table.setItem(i, 3, QTableWidgetItem(str(rec.date)))

    def _on_day(self, frame: pd.DataFrame, column: str) -> pd.DataFrame:
        day = self._selected_day()
        if day is None or frame.empty:
            return frame
        return frame[_et_day(frame[column]) == day]

    # ── Signals (SRD-GUI-031.022 / .023) ──────────────────────────────────────

    def _render_signals(self) -> None:
        frame = self._signals
        if frame is None:
            return
        name = self.strategy_filter.currentText()
        if name and name != _ALL:
            frame = frame[frame["strategy"] == name]
        frame = self._on_day(frame, "start").sort_values("start", ascending=False)
        self.signals_head.setText(f"{len(frame):,} WINDOWS WHEN ENTRY OR EXIT CONDITION IS TRUE")
        self.signals_table.setRowCount(len(frame))
        cells: list[list[Any]] = [
            list(frame["strategy"]), list(frame["symbol"]), list(frame["kind"]),
            _et(frame["start"]), _et(frame["end"]),
            [f"{v:.2f}" for v in frame["close_at_start"]],
        ]
        for col, values in enumerate(cells):
            for row, value in enumerate(values):
                self.signals_table.setItem(row, col, QTableWidgetItem(str(value)))

    def _on_signal_double_clicked(self, row: int, _col: int) -> None:
        item = self.signals_table.item(row, 1)
        if item is not None:
            self.chart_requested.emit(item.text(), "1d")

    # ── Step 3 panels (SRD-GUI-031.031–.034) ──────────────────────────────────

    def _on_portfolio_done(self, results: list[VariantResult]) -> None:
        self._results = results
        self.set_step(2, "done")
        if results:
            self._render_variant(0)

    def _render_variant(self, index: int) -> None:
        """Show the picked variant in every panel (SRD-GUI-031.044)."""
        if not 0 <= index < len(self._results):
            return
        self._variant = index
        self._render_days()
        res = self._results[index]
        self.trade_list.set_trades(res.trades)
        days = [] if self._daily is None else list(self._daily.days)
        self.screener_use.set_use(screener_use(days, self._shown(), res.trades))
        self.margin_use.set_use(margin_use(res.money))

    def _open_trade(self, trade: pd.Series) -> None:
        """Open the clicked trade's day in the Inspector with it selected (SRD-GUI-031.053)."""
        day = trade["day"].isoformat()
        for row in range(self.days_table.rowCount()):
            item = self.days_table.item(row, 0)
            if item is not None and item.text() == day:
                self.days_table.selectRow(row)
                break
        same = ((self._day_trades["symbol"] == trade["symbol"])
                & (self._day_trades["entry_ts"] == trade["entry_ts"]))
        if same.any():
            self.trades_table.selectRow(int(same.to_numpy().argmax()))
        self.tabs.setCurrentWidget(self.inspector)

    def _render_results(self) -> None:
        res = self._result()
        if res is None:
            return
        trades = self._on_day(res.trades, "entry_ts").sort_values("entry_ts", ascending=False)
        self._day_trades = trades.reset_index(drop=True)
        self.trades_head.setText(trades_summary(trades))
        self.trades_table.blockSignals(True)
        _fill(self.trades_table, [
            list(trades["strategy"]), list(trades["symbol"]), list(trades["direction"]),
            _et(trades["entry_ts"]), [f"{v:.2f}" for v in trades["entry_px"]],
            [str(v) for v in trades["qty"]], _et(trades["exit_ts"]),
            [f"{v:.2f}" for v in trades["exit_px"]], list(trades["exit_reason"]),
            [f"{v:,.2f}" for v in trades["net_pnl"]],
        ])
        if len(trades):
            self.trades_table.selectRow(0)
        self.trades_table.blockSignals(False)
        log = self._on_day(res.day_log, "ts").sort_values("ts", ascending=False)
        _fill(self.log_table, [
            _et(log["ts"]), list(log["symbol"]), list(log["strategy"]), list(log["decision"]),
            [f"{v:,.2f}" for v in log["margin_available"]],
            [f"{v:,.2f}" for v in log["strategy_deployed"]],
        ])
        day = self._selected_day()
        money = res.money if day is None else res.money[res.money["date"] == day]
        money = money.sort_values("date", ascending=False)
        _fill(self.money_table, [
            [str(d) for d in money["date"]],
            *[[f"{v:,.2f}" for v in money[c]] for c in
              ("deployed", "margin_min", "margin_close", "open_value", "equity")],
        ])
        self._render_chart()

    # ── Chart (SRD-GUI-031.052) ───────────────────────────────────────────────

    def _selected_trade(self) -> pd.Series | None:
        rows = self.trades_table.selectionModel()
        if rows is None or not rows.selectedRows():
            return None
        row = rows.selectedRows()[0].row()
        return self._day_trades.iloc[row] if row < len(self._day_trades) else None

    def _render_chart(self) -> None:
        trade = self._selected_trade()
        if trade is None:
            self.chart_head.setText("")
            self.chart.set_data(self.chart.bars.iloc[0:0], self._day_trades.iloc[0:0],
                                "No trade on this session")
            return
        symbol, tf = str(trade["symbol"]), self.chart_tf.currentText()
        day = _et_day(pd.Series([trade["entry_ts"]])).iloc[0]
        start = day - datetime.timedelta(days=_DAILY_CHART_DAYS) if tf == "1d" else day
        try:
            bars = self._service.bars(symbol, tf, start, day)  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001 — shown on the chart instead
            _log.warning("[Backtest] Could not read candles for %s: %s", symbol, exc)
            bars = self.chart.bars.iloc[0:0]
        trades = self._day_trades[self._day_trades["symbol"] == symbol]
        self.chart_head.setText(f"{symbol} · {trade['strategy']} · {day.isoformat()}")
        self.chart.set_data(bars, trades, f"No {tf} candles saved for {symbol}")

    # ── Step 4 view (SRD-GUI-031.040–.045) ────────────────────────────────────

    def _on_report_done(self, reports: list[Report]) -> None:
        self.set_step(3, "done")
        self.report_view.set_reports(reports)
        self.tabs.setCurrentWidget(self.detail)
