"""
Module: MD-GUI-034.027.M21 — gui/ai_desk_hiring.py
Parent SRD: SRD-GUI-034.027
Also: SRD-GUI-034.028 (Start hire form), SRD-GUI-034.029 (shadow report),
SRD-GUI-034.030 (decision buttons), SRD-GUI-034.031 (Command approvals box)
Also: MD-GUI-034.034.M24 — SRD-GUI-034.034–.036 (trade picks in Approvals waiting)
Also: MD-GUI-034.062.M36 — approval cards (SRD-GUI-034.062)

The AI Desk Hiring section: hires made through the pipeline, the Start hire form, the
chosen hire's shadow report and the Replace / Add / Reject decision. All rules live in
``core.desk_hiring``; this module only shows them.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

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
from us_swing.core.desk_feed import ask_cards
from us_swing.core.desk_steps import SKILL_PATHS
from us_swing.core.desk_trades import DeskTradeSink
from us_swing.gui.ai_desk_sections import heading, make_table, muted, section_frame
from us_swing.gui.floor_feed import FeedCardWidget, FeedContext

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


class WaitingBox(QWidget):
    """Command "Approvals waiting": one feed card per waiting pick or ready hire."""

    chart_requested = pyqtSignal(str)
    count_changed = pyqtSignal(int)

    def __init__(self, home: Path, open_hiring: Callable[[], None],
                 sink: DeskTradeSink | None, clock: Callable[[], datetime],
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._home, self._open_hiring = home, open_hiring
        self._context = FeedContext(home, sink, clock)
        self._lines = QVBoxLayout(self)
        self._lines.setContentsMargins(0, 0, 0, 0)
        self._lines.setSpacing(6)
        self.count = 0
        self.reload()

    def cards(self) -> list[FeedCardWidget]:
        """Return the cards on show, top first."""
        return self.findChildren(FeedCardWidget)

    def reload(self) -> None:
        """Read the waiting asks again and rebuild the cards."""
        while (item := self._lines.takeAt(0)) is not None:
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()  # a card may still be inside its own click handler
        asks = ask_cards(self._home, self._context.clock())
        self.count = len(asks)
        self._lines.addWidget(heading(f"Approvals waiting · {self.count}" if asks
                                      else "Approvals waiting"))
        if not asks:
            self._lines.addWidget(muted(NO_APPROVALS))
        for ask in asks:
            card = FeedCardWidget(ask, self._context)
            # card → section_requested → box → open Hiring; chart_requested → page → window
            card.section_requested.connect(lambda _name: self._open_hiring())
            card.chart_requested.connect(self.chart_requested)
            # card → decided → box → reload after the click has finished
            card.decided.connect(lambda: QTimer.singleShot(0, self.reload))
            self._lines.addWidget(card)
        self._lines.addStretch(1)
        self.count_changed.emit(self.count)


def approvals_box(home: Path | None, open_hiring: Callable[[], None],
                  sink: DeskTradeSink | None = None,
                  clock: Callable[[], datetime] | None = None) -> WaitingBox:
    """The Command "Approvals waiting" box: cards for ready hires and waiting picks."""
    return WaitingBox(home or desk_home(), open_hiring, sink,
                      clock or (lambda: datetime.now(NY)))
