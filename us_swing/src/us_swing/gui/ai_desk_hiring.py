"""
Module: MD-GUI-034.027.M21 — gui/ai_desk_hiring.py
Parent SRD: SRD-GUI-034.027
Also: SRD-GUI-034.028 (Start hire form), SRD-GUI-034.029 (shadow report),
SRD-GUI-034.030 (decision buttons), SRD-GUI-034.031 (Command approvals box)
Also: MD-GUI-034.034.M24 — SRD-GUI-034.034–.036 (trade pick rows in Approvals waiting)

The AI Desk Hiring section: hires made through the pipeline, the Start hire form, the
chosen hire's shadow report and the Replace / Add / Reject decision. All rules live in
``core.desk_hiring``; this module only shows them.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from us_swing.core.desk_ai_settings import load_settings
from us_swing.core.desk_contract import desk_home
from us_swing.core.desk_hiring import (
    HIRE_LEVELS,
    SHADOW_DAYS,
    SOURCES,
    HireInfo,
    decide,
    list_hires,
    shadow_report,
    start_hire,
)
from us_swing.core.desk_steps import SKILL_PATHS
from us_swing.core.desk_trades import (
    DeskTradeSink,
    TradePick,
    pick_state,
    record_trade_decision,
    trade_picks,
)
from us_swing.gui.ai_desk_sections import heading, make_table, muted, section_frame

NY = ZoneInfo("America/New_York")
HIRE_COLUMNS = ("Name", "Skill", "Level", "Model", "Started", "Shadow days", "Status")
REPORT_COLUMNS = ("Who", "Days", "Valid", "Tokens", "Cost")
NO_HIRES = "No hires yet. Start one below; it runs in shadow for 14 evenings"
NO_APPROVALS = "Nothing waits for your approval"


def _status(hire: HireInfo) -> str:
    return "ready" if hire.ready else hire.employee.status


def _skill(key: str) -> str:
    return key.replace("_", " ")


def _fill(table: QTableWidget, rows: Sequence[Sequence[str]]) -> None:
    table.setRowCount(len(rows))
    for r, values in enumerate(rows):
        for c, value in enumerate(values):
            table.setItem(r, c, QTableWidgetItem(value))
    table.resizeColumnsToContents()


class HiringPanel(QWidget):
    """Hires list, Start hire form, shadow report and decisions for one desk folder."""

    def __init__(self, home: Path, parent: QWidget | None = None) -> None:
        """Build the panel from the employee files and ``desk.db`` in ``home``."""
        super().__init__(parent)
        self._home = home
        self._hires: list[HireInfo] = []
        self._chosen: HireInfo | None = None
        body = QVBoxLayout(self)
        body.setContentsMargins(0, 0, 0, 0)
        body.addWidget(heading("Hires"))
        self.empty = muted(NO_HIRES)
        self.table = make_table(HIRE_COLUMNS, [])
        self.table.setObjectName("hires_table")
        body.addWidget(self.empty)
        body.addWidget(self.table, 2)
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addLayout(self._form(), 2)
        row.addLayout(self._report_box(), 3)
        body.addLayout(row, 3)
        # table → currentCellChanged → panel → _choose
        self.table.currentCellChanged.connect(self._choose)
        self.reload()

    def _form(self) -> QVBoxLayout:
        box = QVBoxLayout()
        box.addWidget(heading("Start hire"))
        form = QFormLayout()
        self.skill = QComboBox()
        for key in SKILL_PATHS:
            self.skill.addItem(_skill(key), key)
        self.level = QComboBox()
        self.level.addItems(HIRE_LEVELS)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Name of the new employee")
        self.source = QComboBox()
        self.source.addItems(SOURCES)
        self.model = QLineEdit("default")
        form.addRow("Skill", self.skill)
        form.addRow("Level", self.level)
        form.addRow("Name", self.name)
        form.addRow("Source", self.source)
        form.addRow("Model", self.model)
        box.addLayout(form)
        self.start_btn = QPushButton("Start hire")
        self.start_btn.setFixedWidth(110)
        # start button → clicked → panel → start
        self.start_btn.clicked.connect(self.start)
        self.form_status = QLabel("")
        self.form_status.setWordWrap(True)
        box.addWidget(self.start_btn)
        box.addWidget(self.form_status)
        box.addStretch(1)
        return box

    def _report_box(self) -> QVBoxLayout:
        box = QVBoxLayout()
        box.addWidget(heading("Shadow report"))
        self.report: QTableWidget = make_table(REPORT_COLUMNS, [])
        self.report.setObjectName("shadow_report")
        self.agreement = QLabel("")
        buttons = QHBoxLayout()
        self.replace_btn = QPushButton("Replace")
        self.add_btn = QPushButton("Add")
        self.reject_btn = QPushButton("Reject")
        for btn, decision in ((self.replace_btn, "replace"), (self.add_btn, "add"),
                              (self.reject_btn, "reject")):
            btn.setFixedWidth(90)
            # decision button → clicked → panel → decide
            btn.clicked.connect(lambda _=False, d=decision: self.decide(d))
            buttons.addWidget(btn)
        buttons.addStretch(1)
        self.decision_status = QLabel("")
        self.decision_status.setWordWrap(True)
        box.addWidget(self.report, 1)
        box.addWidget(self.agreement)
        box.addLayout(buttons)
        box.addWidget(self.decision_status)
        return box

    def reload(self) -> None:
        """Read the hires again and refill the list; keep the chosen hire when it is still there."""
        chosen = self._chosen.employee.id if self._chosen else ""
        self._hires = list_hires(self._home)
        rows = [(h.employee.name, _skill(h.employee.skill), h.employee.level, h.employee.model,
                 h.employee.hired_on or "-", f"{h.days} of {SHADOW_DAYS}", _status(h))
                for h in self._hires]
        self.table.blockSignals(True)
        _fill(self.table, rows)
        self.table.blockSignals(False)
        self.empty.setVisible(not rows)
        self.table.setVisible(bool(rows))
        index = next((i for i, h in enumerate(self._hires) if h.employee.id == chosen), 0)
        if rows:
            self.table.setCurrentCell(index, 0)
        self._choose(index if rows else -1)

    def _choose(self, row: int, *_: int) -> None:
        self._chosen = self._hires[row] if 0 <= row < len(self._hires) else None
        hire = self._chosen
        report = shadow_report(self._home, hire.employee.id) if hire else None
        rows = [(r.who, str(r.days), "-" if r.valid is None else f"{r.valid:.0%}",
                 f"{r.tokens:,}", f"${r.cost:.4f}") for r in (report.rows if report else [])]
        _fill(self.report, rows)
        agree = report.agreement if report else None
        self.agreement.setText("" if hire is None else
                               f"Agreement with the holder: {'-' if agree is None else f'{agree:.0%}'}")
        shadow = hire is not None and hire.employee.status == "shadow"
        ready = hire is not None and hire.ready
        self.replace_btn.setEnabled(ready and hire is not None and hire.has_holder)
        self.add_btn.setEnabled(ready and hire is not None and not hire.has_holder)
        self.reject_btn.setEnabled(shadow)

    def start(self) -> None:
        """Start a hire from the form; show the reason when it is refused."""
        new_id, reason = start_hire(
            self._home, str(self.skill.currentData()), self.level.currentText(),
            self.name.text(), self.source.currentText(), self.model.text(),
            datetime.now(NY).date())
        if new_id is None:
            self.form_status.setText(f"Not started: {reason}")
            return
        self.form_status.setText(f"{self.name.text().strip()} started in shadow")
        self.name.clear()
        self._chosen = None
        self.reload()

    def decide(self, decision: str) -> None:
        """Record the Master decision for the chosen hire."""
        hire = self._chosen
        if hire is None:
            return
        reason = decide(self._home, hire.employee.id, decision, datetime.now(NY))
        self.decision_status.setText(f"Not saved: {reason}" if reason else
                                     f"{hire.employee.name}: {decision} saved; used from the "
                                     "next desk run")
        self.reload()


def hiring_frame(name: str, home: Path | None = None) -> QWidget:
    """Build the Hiring section for the desk folder ``home``."""
    frame, body = section_frame(name, sample=False)
    body.addWidget(HiringPanel(home or desk_home()), 1)
    return frame


class TradePickRow(QWidget):
    """One waiting lead pick with Approve and Reject; the Master's decision goes to ``approvals``."""

    def __init__(self, home: Path, pick: TradePick, sink: DeskTradeSink | None,
                 clock: Callable[[], datetime], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._home, self._pick, self._sink, self._clock = home, pick, sink, clock
        qty = sink.desk_pick_qty(pick) if sink is not None else None
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.text = QLabel(
            f"{pick.side.upper()}  {pick.symbol}  entry {pick.entry:.2f}  stop {pick.stop:.2f}  "
            f"target {pick.target:.2f}  qty {qty if qty is not None else '—'}")
        self.note = muted("")
        self.approve_btn = QPushButton("Approve")
        self.reject_btn = QPushButton("Reject")
        for btn in (self.approve_btn, self.reject_btn):
            btn.setEnabled(sink is not None)
        row.addWidget(self.text, 1)
        row.addWidget(self.note)
        row.addWidget(self.approve_btn)
        row.addWidget(self.reject_btn)
        # Approve / Reject → clicked → decision row (and the pending signal on Approve)
        self.approve_btn.clicked.connect(self._approve)
        self.reject_btn.clicked.connect(self._reject)

    def _still_waiting(self) -> bool:
        state = pick_state(self._home, self._pick, self._clock())
        if state == "waiting":
            return True
        self._done("expired at the market open" if state == "expired" else "already decided")
        return False

    def _done(self, note: str) -> None:
        self.note.setText(note)
        self.approve_btn.setEnabled(False)
        self.reject_btn.setEnabled(False)

    def _approve(self) -> None:
        if self._sink is None or not self._still_waiting():
            return
        qty, why = self._sink.send_desk_pick(self._pick)
        if why:
            self.note.setText(why)
            return
        err = record_trade_decision(self._home, self._pick, "approve", qty, self._clock())
        if err:
            self._sink.dismiss_desk_pick(self._pick)
            self._done(err)
            return
        self.hide()

    def _reject(self) -> None:
        if not self._still_waiting():
            return
        err = record_trade_decision(self._home, self._pick, "reject", 0, self._clock())
        if err:
            self._done(err)
            return
        self.hide()


def approvals_box(home: Path | None, open_hiring: Callable[[], None],
                  sink: DeskTradeSink | None = None,
                  clock: Callable[[], datetime] | None = None) -> QWidget:
    """The Command "Approvals waiting" box: ready hires (a click opens Hiring) and waiting picks."""
    folder = home or desk_home()
    now = clock or (lambda: datetime.now(NY))
    box = QWidget()
    lines = QVBoxLayout(box)
    lines.setContentsMargins(0, 0, 0, 0)
    lines.addWidget(heading("Approvals waiting"))
    ready = [h for h in list_hires(folder) if h.ready]
    picks = [p for p in trade_picks(folder, now(), load_settings(folder).trade_target_r)
             if p.state == "waiting"]
    if not ready and not picks:
        lines.addWidget(muted(NO_APPROVALS))
        lines.addStretch(1)
        return box
    if ready:
        listing = QListWidget()
        listing.setObjectName("approvals_list")
        listing.setStyleSheet("QListWidget { outline: none; }")
        listing.addItems([f"Hire: {h.employee.name} ({_skill(h.employee.skill)}) finished the "
                          "shadow" for h in ready])
        # approvals list → itemClicked → Command → open Hiring
        listing.itemClicked.connect(lambda _item: open_hiring())
        lines.addWidget(listing, 1)
    for pick in picks:
        lines.addWidget(TradePickRow(folder, pick, sink, now))
    if not ready:
        lines.addStretch(1)
    return box
