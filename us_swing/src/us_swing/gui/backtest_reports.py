"""
Module: MD-GUI-031.055.M09 — Backtest saved reports
Parent SRD: SRD-GUI-031.055

Saved runs table and a details panel: open the run into the Inspector and Detail
Report, download it as an HTML report (SRD-GUI-031.082), rename it, keep a note, or
delete it (with a confirm).
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
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
from us_swing.core.dates import DATE_TIME_FMT, show_date
from us_swing.gui.icons import mark_danger, set_icon
from us_swing.gui.theme import C

if TYPE_CHECKING:
    from us_swing.backtest.service import BacktestService
    from us_swing.backtest.spec import RunPlan

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


class _HtmlWorker(QThread):
    done = pyqtSignal(bool)  # True when the file was written

    def __init__(self, service: BacktestService, run_id: str, path: Path, user_id: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service, self._run_id, self._path = service, run_id, path
        self._user_id = user_id

    def run(self) -> None:
        try:
            self._service.export_html(self._run_id, self._path, self._user_id)
            self.done.emit(True)
        except Exception as exc:  # noqa: BLE001 — logged for the user
            _log.warning("[Backtest] Could not save the HTML report: %s", exc)
            self.done.emit(False)


def html_file_name(rep: SavedReport) -> str:
    """"Backtest_2026-11-01_2344.html": run name and save time, safe for a file name."""
    stem = re.sub(r"[^A-Za-z0-9]+", "_", rep.run.name).strip("_") or "Backtest"
    return f"{stem}_{rep.run.started.astimezone().strftime('%Y-%m-%d_%H%M')}.html"


Section = tuple[str, list[tuple[str, str]]]


def plan_sections(saved: SavedReport) -> list[Section]:
    """Plan facts for the details panel as (heading, [(label, value)]) groups."""
    plan = saved.plan
    strategies = [(s.id, f"Allocation {s.allocation_pct[0]:g}% · "
                         f"per trade {s.per_trade_pct[0]:g}%")
                  for s in plan.strategies] or [("None", "")]
    capital = ", ".join(f"${c:,.0f}" for c in plan.account.capital)
    return [
        ("UNIVERSE", [("Period", f"{show_date(plan.period.start)} → {show_date(plan.period.end)}"),
                      ("Stocks", _short_stocks(plan)),
                      ("Stocks per day", "All (no screener)" if plan.screener.skip
                       else str(plan.screener.top_n or "All"))]),
        ("STRATEGY", strategies),
        ("MONEY", [("Capital", capital),
                   ("Daily loss stop", f"{plan.account.max_daily_loss_pct:g}%"),
                   ("Costs", f"${plan.costs.per_order:g} an order · "
                             f"{plan.costs.slippage_bps:g} bps")]),
    ]


def _short_stocks(plan: RunPlan) -> str:
    """A count for long sector lists; the full list goes in the tooltip."""
    if plan.universe.mode == "sector" and len(plan.universe.sectors) > 2:
        return f"{len(plan.universe.sectors)} sectors"
    return stocks_text(plan)


def _fact_row(key: str, value: str, tip: str = "") -> QWidget:
    row = QWidget()
    line = QHBoxLayout(row)
    line.setContentsMargins(0, 0, 0, 0)
    label = QLabel(key)
    label.setObjectName("details_key")
    shown = QLabel(value)
    shown.setObjectName("fact_value")
    shown.setWordWrap(True)
    shown.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    shown.setToolTip(tip)
    line.addWidget(label)
    line.addWidget(shown, 1)
    return row


class ReportsView(QWidget):
    """SRD-GUI-031.055 — saved runs list (``list_box``) and details (``details_box``)."""

    open_requested = pyqtSignal(object)  # SavedReport

    def __init__(self, service: BacktestService, parent: QWidget | None = None,
                 user_id: Callable[[], str] = lambda: "") -> None:
        super().__init__(parent)
        self._service = service
        self._user_id = user_id
        self.saved: list[SavedReport] = []
        self._workers: list[QThread] = []
        self._saving = False
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
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
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
        self.sheet = QWidget()
        self._sheet_body = QVBoxLayout(self.sheet)
        self._sheet_body.setContentsMargins(0, 0, 0, 4)
        self._sheet_body.setSpacing(3)
        body.addWidget(self.sheet)
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
        set_icon(self.open_btn, "play", "go")
        self.open_btn.clicked.connect(self._on_open)
        self.html_btn = QPushButton("Download")
        set_icon(self.html_btn, "download")
        self.html_btn.setToolTip("Save this run as an HTML report")
        self.html_btn.clicked.connect(self._on_download)
        self.delete_btn = QPushButton("Delete")
        set_icon(self.delete_btn, "trash-2", "danger")
        mark_danger(self.delete_btn)
        self.delete_btn.clicked.connect(self._on_delete)
        buttons.addWidget(self.note_btn)
        buttons.addStretch(1)
        buttons.addWidget(self.delete_btn)
        buttons.addWidget(self.html_btn)
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
            texts = [rep.run.name, rep.run.started.astimezone().strftime(DATE_TIME_FMT),
                     f"{show_date(rep.plan.period.start)} → {show_date(rep.plan.period.end)}",
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

    def selected_all(self) -> list[SavedReport]:
        """Every run picked in the table, top to bottom."""
        rows = self.table.selectionModel()
        if rows is None:
            return []
        picked = sorted(index.row() for index in rows.selectedRows())
        return [self.saved[row] for row in picked if row < len(self.saved)]

    def _show_details(self) -> None:
        reps = self.selected_all()
        rep = reps[0] if len(reps) == 1 else None
        for widget in (self.name, self.note, self.rename_btn, self.note_btn, self.open_btn):
            widget.setEnabled(rep is not None)
        self.html_btn.setEnabled(rep is not None and not self._saving)
        self.delete_btn.setEnabled(bool(reps))
        self.delete_btn.setText(f"Delete ({len(reps)})" if len(reps) > 1 else "Delete")
        self.name.setText("" if rep is None else rep.run.name)
        self.note.setPlainText("" if rep is None else rep.run.note)
        self.facts.setVisible(rep is None)
        self.sheet.setVisible(rep is not None)
        if len(reps) > 1:
            self.facts.setText(f"{len(reps)} runs selected")
        elif rep is None:
            self.facts.setText("Run a backtest to save a report")
        else:
            self._fill_sheet(rep)

    def _fill_sheet(self, rep: SavedReport) -> None:
        while (item := self._sheet_body.takeAt(0)) is not None:
            if (widget := item.widget()) is not None:
                widget.setParent(None)
                widget.deleteLater()
        for n, (head, rows) in enumerate(plan_sections(rep)):
            if n:
                self._sheet_body.addSpacing(8)
            title = QLabel(head)
            title.setObjectName("view_head")
            self._sheet_body.addWidget(title)
            for key, value in rows:
                tip = stocks_text(rep.plan) if key == "Stocks" else ""
                self._sheet_body.addWidget(_fact_row(key, value, tip))

    def sheet_values(self) -> dict[str, str]:
        """Shown label → value pairs of the details sheet."""
        rows = (r for r in self.sheet.findChildren(QWidget) if r.parent() is self.sheet)
        pairs = (r.findChildren(QLabel) for r in rows)
        return {p[0].text(): p[1].text() for p in pairs if len(p) == 2}

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

    def _on_download(self) -> None:
        rep = self.selected()
        if rep is None:
            return
        path = self.ask_html_path(Path.home() / "Downloads" / html_file_name(rep))
        if path is None:
            return
        self._saving = True
        self.html_btn.setEnabled(False)
        self.html_btn.setText("Saving…")
        worker = _HtmlWorker(self._service, rep.run.run_id, path, self._user_id(), self)
        worker.done.connect(self._on_download_done)
        worker.finished.connect(lambda: self._workers.remove(worker))
        self._workers.append(worker)
        worker.start()

    def _on_download_done(self, _ok: bool) -> None:
        self._saving = False
        self.html_btn.setText("Download")
        self.html_btn.setEnabled(self.selected() is not None)

    def ask_html_path(self, default: Path) -> Path | None:
        """Ask where to save the HTML report; tests replace this."""
        name, _ = QFileDialog.getSaveFileName(self, "Download report", str(default),
                                              "HTML report (*.html)")
        return Path(name) if name else None

    def _on_delete(self) -> None:
        reps = self.selected_all()
        if not reps or not self.confirm_delete(reps):
            return
        for rep in reps:
            self._service.delete_run(rep.run.run_id)
        self.refresh()

    def confirm_delete(self, reps: list[SavedReport]) -> bool:
        """Ask before deleting; tests replace this."""
        # Imported here: the module pulls in the execution package.
        from us_swing.gui.active_cycles_panel import _ConfirmDialog

        text = (f"Delete the saved run \"{reps[0].run.name}\" and all its trades?"
                if len(reps) == 1 else f"Delete {len(reps)} saved runs and all their trades?")
        dialog = _ConfirmDialog("DELETE REPORT", text, confirm_text="Delete", accent=C.RED,
                                parent=self)
        return dialog.exec() == QDialog.DialogCode.Accepted


def _usd(value: float) -> str:
    return f"-${-value:,.2f}" if value < 0 else f"${value:,.2f}"
