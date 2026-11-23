"""
Module: MD-GUI-024.001.M01 — Execution page header
Parent SRD: SRD-GUI-024.001
Circuit breaker button: MD-GUI-027.009.M05 (Parent SRD: SRD-GUI-027.009)

Title, admin badge, last screener run, and chips for unrealised P&L,
strategies running and broker state, the circuit breaker button, plus the
Execute-for user combo.
"""
from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from us_swing.data.models import ConnectionStatus, FilteredStockEntry
from us_swing.gui.app_service import AppService
from us_swing.gui.icons import set_icon
from us_swing.gui.strategy_store import load_strategies
from us_swing.gui.theme import C

_UNREALISED_REFRESH_MS = 3_000
_LIVE_STATES = ("RUNNING", "SQUARING_OFF")


def _money(value: float) -> str:
    sign = "+" if value > 0 else "−" if value < 0 else ""
    return f"{sign}${abs(value):,.2f}"


def last_run_text(entries: list[FilteredStockEntry]) -> str:
    """Newest run as "Last screener run 22 Oct 2026 · 18:48 · 11 stocks"."""
    dates = sorted({e.date for e in entries if e.date}, reverse=True)
    if not dates:
        return "No screener run yet"
    day = datetime.strptime(dates[0], "%Y-%m-%d").strftime("%d %b %Y")
    time = max((e.time for e in entries if e.date == dates[0] and e.time), default="")
    count = len(entries)
    parts = [f"Last screener run {day}", time, f"{count} stock{'s' if count != 1 else ''}"]
    return " · ".join(p for p in parts if p)


class ExecutionHeader(QFrame):
    """Execution page header (SRD-GUI-024.001)."""

    def __init__(self, svc: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._svc = svc
        self.setObjectName("screener_header")
        # The header is its own card here, so the Screener's bottom rule would show as
        # a stray line above the card edge.
        self.setStyleSheet("QFrame#screener_header { border-bottom: none; }")

        title = QLabel("Execution")
        title.setObjectName("page_title")
        admin = QLabel("ADMIN")
        admin.setObjectName("page_tag")
        self._last_run = QLabel("")
        self._last_run.setObjectName("view_key")

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title_row.addWidget(title)
        title_row.addWidget(admin)
        title_row.addStretch(1)
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        title_box.addLayout(title_row)
        self.cb_banner = QLabel(
            "⚠  Circuit Breaker ACTIVE — daily loss limit reached. "
            "New entries are disabled."
        )
        self.cb_banner.setObjectName("cb_banner")
        self.cb_banner.setVisible(False)
        self.cb_banner.setWordWrap(True)
        meta_row = QHBoxLayout()
        meta_row.setSpacing(16)
        meta_row.addWidget(self._last_run)
        meta_row.addWidget(self.cb_banner, 1)
        title_box.addLayout(meta_row)

        stats = QFrame()
        stats.setObjectName("exec_stats")
        stats_row = QHBoxLayout(stats)
        stats_row.setContentsMargins(0, 0, 0, 0)
        stats_row.setSpacing(0)
        self.unrealised_chip = self._stat(stats_row, "UNREALISED P&L", first=True)
        self.running_chip = self._stat(stats_row, "STRATEGIES")
        self.broker_chip = self._stat(stats_row, "BROKER")
        self.breaker_btn = QPushButton()
        self.breaker_btn.setToolTip("Stops all new orders until you reset it.")
        self.breaker_btn.clicked.connect(
            lambda: svc.set_circuit_breaker(not svc.circuit_breaker_active)
        )
        self.show_breaker_state(svc.circuit_breaker_active)
        self.charts_btn = QPushButton()
        self.show_charts_state(False)

        exec_for = QLabel("Execute for")
        exec_for.setObjectName("view_key")
        self.user_combo = QComboBox()
        self.user_combo.setMinimumWidth(160)
        self.user_combo.setStyleSheet(
            "QComboBox { outline: none; } QComboBox:focus { outline: none; }"
        )
        self.user_combo.addItem("All users", None)
        for user in svc.get_users():
            self.user_combo.addItem(f"{user.username}  ({user.mode.upper()})", user.user_id)
        divider = QFrame()
        divider.setObjectName("side_sep")
        divider.setFixedSize(1, 24)

        row = QHBoxLayout(self)
        row.setContentsMargins(20, 12, 20, 12)
        row.setSpacing(8)
        row.addLayout(title_box, 1)
        row.addWidget(stats)
        row.addSpacing(16)
        row.addWidget(exec_for)
        row.addWidget(self.user_combo)
        row.addWidget(self.charts_btn)
        row.addSpacing(4)
        row.addWidget(divider)
        row.addSpacing(4)
        row.addWidget(self.breaker_btn)

        svc.screener_results_updated.connect(self.set_last_run)
        svc.viewing_changed.connect(self._on_scope_changed)
        svc.viewing_changed.connect(self.refresh)
        svc.positions_updated.connect(self.refresh_unrealised)
        svc.strategy_status_changed.connect(self.refresh_running)
        svc.feed_status_changed.connect(self.refresh_broker)
        svc.circuit_breaker_changed.connect(self.show_breaker_state)
        self._timer = QTimer(self)
        self._timer.setInterval(_UNREALISED_REFRESH_MS)
        self._timer.timeout.connect(self.refresh_unrealised)
        self._timer.start()
        self.set_last_run(svc.get_latest_screener_results())
        self.refresh()

    @staticmethod
    def _stat(row: QHBoxLayout, name: str, *, first: bool = False) -> QLabel:
        """Add one labelled cell to the joined stat box; return its value label."""
        cell = QWidget()
        cell.setObjectName("exec_stat" if first else "exec_stat_next")
        box = QVBoxLayout(cell)
        box.setContentsMargins(16, 6, 16, 6)
        box.setSpacing(2)
        label = QLabel(name)
        label.setObjectName("exec_stat_label")
        value = QLabel()
        value.setObjectName("exec_stat_value")
        box.addWidget(label)
        box.addWidget(value)
        row.addWidget(cell)
        return value

    def show_charts_state(self, hidden: bool) -> None:
        """Tooltip the charts toggle with its next action (SRD-GUI-024.008)."""
        tip = "Show charts" if hidden else "Hide charts"
        self.charts_btn.setToolTip(tip)
        self.charts_btn.setAccessibleName(tip)
        set_icon(self.charts_btn, "chart-candlestick", "neutral", 15)

    def show_breaker_state(self, active: bool) -> None:
        """Label the breaker button: Trip when off, Reset when tripped (SRD-GUI-027.009)."""
        self.breaker_btn.setText("Reset breaker" if active else "Trip breaker")
        set_icon(self.breaker_btn, "power", "neutral" if active else "danger", 13)
        self.breaker_btn.setProperty("role", "" if active else "danger")
        style = self.breaker_btn.style()
        if style is not None:
            style.unpolish(self.breaker_btn)
            style.polish(self.breaker_btn)

    def set_last_run(self, entries: list[FilteredStockEntry]) -> None:
        self._last_run.setText(last_run_text(entries))

    def refresh(self) -> None:
        self.refresh_unrealised()
        self.refresh_running()
        self.refresh_broker()

    def refresh_unrealised(self) -> None:
        total = self._unrealised_total()
        colour = C.GREEN if total > 0 else C.RED if total < 0 else C.TEXT
        self.unrealised_chip.setText(f"<span style='color:{colour}'>{_money(total)}</span>")

    def refresh_running(self, *_: object) -> None:
        configs = load_strategies()
        with_open = self._svc.get_strategies_with_open_cycles()
        running = sum(
            1 for c in configs if c.name in with_open or c.run_state in _LIVE_STATES
        )
        self.running_chip.setText(
            f"<b>{running}</b> of <b>{len(configs)}</b> "
            f"<span style='color:{C.SUBTEXT}'>running</span>"
        )

    def refresh_broker(self, *_: object) -> None:
        if self._svc.get_active_user().mode != "live":
            self.broker_chip.setText(f"Paper <span style='color:{C.GREEN}'>ready</span>")
            return
        connected = self._svc.connection_status is ConnectionStatus.CONNECTED
        colour, state = (C.GREEN, "live") if connected else (C.RED, "offline")
        self.broker_chip.setText(f"IBKR <span style='color:{colour}'>{state}</span>")

    def _unrealised_total(self) -> float:
        query = self._svc.cycle_query
        if query is None:
            return 0.0
        uid = self._svc.get_viewing_uid()
        return sum(
            c.current_pnl_usd or 0.0
            for c in query.open_cycles()
            if uid is None or c.user_id == uid
        )

    def _on_scope_changed(self) -> None:
        """Sync the Execute-for combo with the admin viewing scope."""
        uid = self._svc.get_viewing_uid()
        for i in range(self.user_combo.count()):
            if self.user_combo.itemData(i) == uid:
                self.user_combo.setCurrentIndex(i)
                break
