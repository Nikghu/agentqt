"""
Module: MD-GUI-031.055.M09 — Backtest saved reports
Parent SRD: SRD-GUI-031.055

Saved runs table and a details panel: open the run into the Inspector and Detail
Report, rename it, keep a note, or delete it (with a confirm).
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from us_swing.backtest.service import SavedReport, stocks_text
from us_swing.gui.icons import mark_danger, set_icon
from us_swing.gui.theme import C

if TYPE_CHECKING:
    from us_swing.backtest.service import BacktestService

_log = logging.getLogger(__name__)

HEADERS = ["Name", "Saved", "Period", "Return", "Max DD", "Trades", "Net P&L", "Status",
           "Stocks"]


class _ListWorker(QThread):
    done = pyqtSignal(object)  # list[SavedReport]

    def __init__(self, service: BacktestService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service

    def run(self) -> None:
        try:
            self.done.emit(self._service.saved_reports())
        except Exception as exc:  # noqa: BLE001 — an empty list is shown instead
            _log.warning("[Backtest] Could not read saved reports: %s", exc)
            self.done.emit([])


def plan_text(saved: SavedReport) -> str:
    """Plan facts for the details panel, one per line."""
    plan = saved.plan
    strategies = ", ".join(f"{s.id} {s.allocation_pct[0]:g}%/{s.per_trade_pct[0]:g}%"
                           for s in plan.strategies) or "None"
    capital = ", ".join(f"${c:,.0f}" for c in plan.account.capital)
    return "\n".join([
        f"Period: {plan.period.start} → {plan.period.end}",
        f"Stocks: {stocks_text(plan)}",
        f"Stocks per day: {plan.screener.top_n or 'All'}",
        f"Strategies: {strategies}",
        f"Capital: {capital} · daily loss stop {plan.account.max_daily_loss_pct:g}%",
        f"Costs: ${plan.costs.per_order:g} an order · "
        f"{plan.costs.slippage_bps:g} bps",
    ])


class ReportsView(QWidget):
    """SRD-GUI-031.055 — saved runs list (``list_box``) and details (``details_box``)."""

    open_requested = pyqtSignal(object)  # SavedReport

    def __init__(self, service: BacktestService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self.saved: list[SavedReport] = []
        self._workers: list[_ListWorker] = []
        self.list_box = self._build_list()
        self.details_box = self._build_details()
        self._show_details()

    def _build_list(self) -> QWidget:
        box = QWidget()
        body = QVBoxLayout(box)
        body.setContentsMargins(0, 0, 0, 0)
        self.count = QLabel("")
        self.count.setObjectName("details_key")
        self.table = QTableWidget(0, len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.verticalHeader().setVisible(False)  # type: ignore[union-attr]
        self.table.horizontalHeader().setStretchLastSection(True)  # type: ignore[union-attr]
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self._show_details)
        self.table.cellDoubleClicked.connect(lambda *_: self._on_open())
        body.addWidget(self.count)
        body.addWidget(self.table, 1)
        return box

    def _build_details(self) -> QWidget:
        box = QWidget()
        body = QVBoxLayout(box)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(8)
        row = QHBoxLayout()
        self.name = QLineEdit()
        self.name.setStyleSheet("QLineEdit { outline: none; } QLineEdit:focus { outline: none; }")
        self.rename_btn = QPushButton("Rename")
        self.rename_btn.clicked.connect(self._on_rename)
        row.addWidget(self.name, 1)
        row.addWidget(self.rename_btn)
        body.addLayout(row)
        self.facts = QLabel("")
        self.facts.setObjectName("details_key")
        self.facts.setWordWrap(True)
        body.addWidget(self.facts)
        self.note = QTextEdit()
        self.note.setAcceptRichText(False)
        self.note.setPlaceholderText("Notes")
        self.note.setMaximumHeight(120)
        body.addWidget(self.note)
        self.note_btn = QPushButton("Save note")
        set_icon(self.note_btn, "save")
        self.note_btn.clicked.connect(self._on_note)
        buttons = QHBoxLayout()
        self.open_btn = QPushButton("Open")
        self.open_btn.setObjectName("run_btn")
        set_icon(self.open_btn, "play", "inverse")
        self.open_btn.clicked.connect(self._on_open)
        self.delete_btn = QPushButton("Delete")
        set_icon(self.delete_btn, "trash-2", "danger")
        mark_danger(self.delete_btn)
        self.delete_btn.clicked.connect(self._on_delete)
        buttons.addWidget(self.note_btn)
        buttons.addStretch(1)
        buttons.addWidget(self.delete_btn)
        buttons.addWidget(self.open_btn)
        body.addLayout(buttons)
        body.addStretch(1)
        return box

    # ── List ──────────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Reload the saved runs in a worker thread."""
        worker = _ListWorker(self._service, self)
        worker.done.connect(self.set_saved)
        worker.finished.connect(lambda: self._workers.remove(worker))
        self._workers.append(worker)
        worker.start()

    def set_saved(self, saved: list[SavedReport]) -> None:
        """Fill the table; the same run stays selected when it is still there."""
        keep = self.selected()
        self.saved = saved
        self.count.setText(f"{len(saved)} saved run(s) · double-click to open")
        self.table.blockSignals(True)
        self.table.setRowCount(len(saved))
        for row, rep in enumerate(saved):
            texts = [rep.run.name, rep.run.started.astimezone().strftime("%Y-%m-%d %H:%M"),
                     f"{rep.plan.period.start} → {rep.plan.period.end}",
                     f"{rep.return_pct:+.1%}", f"{rep.max_dd_pct:.1%}", str(rep.trades),
                     _usd(rep.net_pnl), rep.run.status, stocks_text(rep.plan)]
            for col, text in enumerate(texts):
                item = QTableWidgetItem(text)
                if col in (3, 6):
                    item.setForeground(QColor(C.GREEN if rep.net_pnl > 0 else C.RED))
                self.table.setItem(row, col, item)
        self.table.resizeColumnsToContents()
        ids = [r.run.run_id for r in saved]
        if saved:
            self.table.selectRow(ids.index(keep.run.run_id) if keep and keep.run.run_id in ids
                                 else 0)
        self.table.blockSignals(False)
        self._show_details()

    def selected(self) -> SavedReport | None:
        """The run picked in the table."""
        rows = self.table.selectionModel()
        if rows is None or not rows.selectedRows():
            return None
        row = rows.selectedRows()[0].row()
        return self.saved[row] if row < len(self.saved) else None

    def _show_details(self) -> None:
        rep = self.selected()
        for widget in (self.name, self.note, self.rename_btn, self.note_btn, self.open_btn,
                       self.delete_btn):
            widget.setEnabled(rep is not None)
        self.name.setText("" if rep is None else rep.run.name)
        self.note.setPlainText("" if rep is None else rep.run.note)
        self.facts.setText("Run a backtest to save a report" if rep is None else plan_text(rep))

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_rename(self) -> None:
        rep, name = self.selected(), self.name.text().strip()
        if rep is not None and name:
            self._service.rename_run(rep.run.run_id, name)
            self.refresh()

    def _on_note(self) -> None:
        rep = self.selected()
        if rep is not None:
            self._service.set_note(rep.run.run_id, self.note.toPlainText())
            self.refresh()

    def _on_open(self) -> None:
        rep = self.selected()
        if rep is not None:
            self.open_requested.emit(rep)

    def _on_delete(self) -> None:
        rep = self.selected()
        if rep is None or not self.confirm_delete(rep):
            return
        self._service.delete_run(rep.run.run_id)
        self.refresh()

    def confirm_delete(self, rep: SavedReport) -> bool:
        """Ask before deleting; tests replace this."""
        # Imported here: the module pulls in the execution package.
        from us_swing.gui.active_cycles_panel import _ConfirmDialog

        dialog = _ConfirmDialog(
            "DELETE REPORT", f"Delete the saved run \"{rep.run.name}\" and all its trades?",
            confirm_text="Delete", accent=C.RED, parent=self)
        return dialog.exec() == QDialog.DialogCode.Accepted


def _usd(value: float) -> str:
    return f"-${-value:,.2f}" if value < 0 else f"${value:,.2f}"
