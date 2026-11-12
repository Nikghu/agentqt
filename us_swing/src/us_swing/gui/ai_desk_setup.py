"""
Module: MD-GUI-036.001.M01 — gui/ai_desk_setup.py
Parent SRD: SRD-GUI-036.001
Also: SRD-GUI-036.002–.007 — form tabs, prompt, model list, save, history and draft test
Also: SRD-GUI-036.009–.010 — reporting tree and number codes

AI Desk → Team setup: pick an employee from the reporting tree, edit its employee.md in a
form and save it as the next version. All file work goes through ``core.desk_employee``.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QModelIndex, QObject, QRect, QRunnable, Qt, QThreadPool, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen, QShowEvent
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from us_swing.core.desk_agents import LEVELS
from us_swing.core.desk_employee import (
    DraftResult,
    EmployeeFile,
    JobSpec,
    check,
    employee_folders,
    known_models,
    last_run,
    load,
    migrate_all,
    parse,
    read_employee,
    render,
    restore,
    save_employee,
    try_draft,
    versions,
)
from us_swing.core.desk_events import EVENT_KINDS
from us_swing.gui.popups import confirm
from us_swing.gui.ai_desk_sections import MONO, muted, section_frame
from us_swing.gui.ai_desk_team_pane import (
    bar_style,
    chip_style,
    chip_text,
    initials,
    lift_fill,
    panel,
    skill_text,
    tab_style,
)
from us_swing.gui.theme import C

TABS = ("Prompt", "Profile", "Model", "Limits & wake", "History")
SOURCES = ("claude", "openrouter")
STATUSES = ("active", "shadow", "retired")
NO_BOSS = "None"
NO_LEAD = "No lead"
_LEAD = "lead"
_SOURCE_LABELS = {"claude": "Claude", "openrouter": "OpenRouter"}


def _label(value: str) -> str:
    """A stored value as shown: first letter capital (sources keep their brand case)."""
    return _SOURCE_LABELS.get(value, value[:1].upper() + value[1:])


def _fill(box: QComboBox, values: tuple[str, ...]) -> None:
    """Show each value with a capital first letter; the stored value is the item data."""
    for value in values:
        box.addItem(_label(value), value)


def _pick(box: QComboBox, value: str) -> None:
    """Select the item whose stored value is ``value``."""
    box.setCurrentIndex(max(0, box.findData(value)))


def _value(box: QComboBox) -> str:
    """The stored value of the selected item."""
    return str(box.currentData())
NO_RUN_NOTE = "No recorded run yet"
RULES_TEXT = ("Added by code: answer with one JSON object matching the skill's schema. "
              "{name} and {title} are filled in.")
_STATUS_KEY = {"active": "done", "shadow": "waiting", "retired": "asleep"}
_ROLE = Qt.ItemDataRole.UserRole
_Runner = Callable[[Path, str, str], DraftResult]
_RUNNING: set[_DraftJob] = set()  # keeps a running test alive even if the page closes


def _list_style() -> str:
    return (f"QListWidget {{ background: transparent; border: none; outline: none; }}"
            f" QListWidget::item {{ padding: 6px 8px; border-radius: 6px; }}"
            f" QListWidget::item:hover:!selected {{ background: {C.OVERLAY}; }}"
            f" QListWidget::item:selected {{ background: {lift_fill()}; color: {C.TEXT}; }}"
            f" QListWidget::item:focus {{ outline: none; border: none; }}")


def _tree_style() -> str:
    return (f"QTreeWidget {{ background: transparent; border: none; outline: none; }}"
            f" QTreeWidget::item {{ padding: 5px 6px; border-radius: 6px; }}"
            f" QTreeWidget::item:hover:!selected {{ background: {C.OVERLAY}; }}"
            f" QTreeWidget::item:selected {{ background: {lift_fill()}; color: {C.TEXT}; }}"
            f" QTreeWidget::item:focus {{ outline: none; border: none; }}")


class _TeamTree(QTreeWidget):
    """Team tree that draws thin lines from each person to the people below them."""

    def drawBranches(self, painter: QPainter | None, rect: QRect,  # noqa: N802
                     index: QModelIndex) -> None:
        """Draw the joining lines, and a fold arrow on rows that have people below."""
        if painter is None:
            return
        chain = [index]
        while chain[-1].parent().isValid():
            chain.append(chain[-1].parent())
        depth, step, mid = len(chain) - 1, self.indentation(), rect.center().y()
        painter.save()
        painter.setPen(QPen(QColor(C.OVERLAY2), 1))
        for level in range(depth):
            x = rect.left() + level * step + step // 2
            owner = chain[depth - level - 1]
            last = not owner.siblingAtRow(owner.row() + 1).isValid()
            if level == depth - 1:
                painter.drawLine(x, rect.top(), x, mid if last else rect.bottom())
                painter.drawLine(x, mid, x + step // 2, mid)
            elif not last:
                painter.drawLine(x, rect.top(), x, rect.bottom())
        item = self.itemFromIndex(index)
        if item is not None and item.childCount():
            painter.setPen(QColor(C.MUTED))
            painter.drawText(QRect(rect.left() + depth * step, rect.top(), step, rect.height()),
                             Qt.AlignmentFlag.AlignCenter, "▾" if item.isExpanded() else "▸")
        painter.restore()


class _DraftSignals(QObject):
    """Carries a finished draft test back to the window thread."""

    done = pyqtSignal(int, object)


class _DraftJob(QRunnable):
    """Runs one draft test off the window thread."""

    def __init__(self, runner: _Runner, home: Path, emp_id: str, text: str, token: int) -> None:
        super().__init__()
        self.setAutoDelete(False)
        self.signals = _DraftSignals()
        self._args = (runner, home, emp_id, text, token)

    def run(self) -> None:
        """Call the runner and emit its result (or a plain failure)."""
        runner, home, emp_id, text, token = self._args
        try:
            result = runner(home, emp_id, text)
        except Exception:  # noqa: BLE001 — any failure is shown as a plain note
            result = DraftResult(False, "", "the test did not finish")
        self.signals.done.emit(token, result)


class TeamSetup(QWidget):
    """Employee list on the left; form with tabs and a save bar on the right."""

    saved = pyqtSignal(str)

    def __init__(self, home: Path, ask: Callable[[str], bool] | None = None,
                 runner: _Runner = try_draft, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._home = home
        self._ask = ask or (lambda text: confirm(self, "Team setup", text))
        self._runner = runner
        self._current = ""
        self._name = ""
        self._spec: JobSpec | None = None
        self._dirty = False
        self._loading = False
        self._token = 0
        self._testing = False
        self._has_run = False
        self._ids: list[str] = []
        self._items: dict[str, QTreeWidgetItem] = {}
        self._folder: QTreeWidgetItem | None = None
        self._people: dict[str, str] = {}
        self._models: dict[str, list[str]] = {}
        self._build()
        self.reload()

    # ── build ─────────────────────────────────────────────────────────────

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        frame, body = section_frame("Team setup", sample=False)
        outer.addWidget(frame)
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(self._build_left())
        row.addWidget(self._build_right(), 1)
        body.addLayout(row, 1)

    def _build_left(self) -> QWidget:
        box = QWidget()
        lines = QVBoxLayout(box)
        lines.setContentsMargins(0, 0, 0, 0)
        lines.setSpacing(8)
        self.count_label = QLabel("Team")
        self.count_label.setObjectName("view_head")
        self.emp_tree = _TeamTree()
        self.emp_tree.setHeaderHidden(True)
        self.emp_tree.setIndentation(16)
        self.emp_tree.setStyleSheet(_tree_style())
        lines.addWidget(self.count_label)
        lines.addWidget(self.emp_tree, 1)
        frame = panel(box)
        frame.setFixedWidth(260)
        # tree → currentItemChanged → page → _on_item
        self.emp_tree.currentItemChanged.connect(self._on_item)
        # tree → itemClicked → page → _on_click (the No lead folder folds on one click)
        self.emp_tree.itemClicked.connect(self._on_click)
        return frame

    def _build_right(self) -> QWidget:
        box = QWidget()
        lines = QVBoxLayout(box)
        lines.setContentsMargins(0, 0, 0, 0)
        lines.setSpacing(10)
        head = QHBoxLayout()
        names = QVBoxLayout()
        names.setSpacing(2)
        self.name_label = QLabel()
        self.name_label.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.role_label = muted("")
        names.addWidget(self.name_label)
        names.addWidget(self.role_label)
        self.status_chip = QLabel()
        head.addLayout(names, 1)
        head.addWidget(self.status_chip, 0, Qt.AlignmentFlag.AlignTop)
        lines.addLayout(head)
        self.form = QWidget()
        form = QVBoxLayout(self.form)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)
        form.addWidget(self._build_tabs())
        self.stack = QStackedWidget()
        for page in (self._page_prompt(), self._page_profile(), self._page_model(),
                     self._page_limits(), self._page_history()):
            self.stack.addWidget(page)
        form.addWidget(self.stack, 1)
        lines.addWidget(self.form, 1)
        lines.addLayout(self._build_save_bar())
        self._wire_dirty()
        return panel(box)

    def _build_tabs(self) -> QWidget:
        row = QWidget()
        row.setStyleSheet(tab_style())
        line = QHBoxLayout(row)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(18)
        group = QButtonGroup(row)
        self.tabs: dict[str, QPushButton] = {}
        for index, name in enumerate(TABS):
            tab = QPushButton(name.replace("&", "&&"))
            tab.setCheckable(True)
            group.addButton(tab)
            self.tabs[name] = tab
            # tab → clicked → page → stack page
            tab.clicked.connect(lambda _=False, i=index: self.stack.setCurrentIndex(i))
            line.addWidget(tab)
        line.addStretch(1)
        self.tabs[TABS[0]].setChecked(True)
        return row

    def _page_prompt(self) -> QWidget:
        page = QWidget()
        lines = QVBoxLayout(page)
        lines.setContentsMargins(0, 0, 0, 0)
        lines.setSpacing(8)
        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setStyleSheet(f"QPlainTextEdit {{ {MONO} outline: none; }}")
        self.rules_label = muted(RULES_TEXT)
        self.result_label = QLabel()
        self.result_label.setWordWrap(True)
        self.result_label.setTextFormat(Qt.TextFormat.PlainText)
        self.result_label.hide()
        lines.addWidget(self.prompt_edit, 1)
        lines.addWidget(self.rules_label)
        lines.addWidget(self.result_label)
        return page

    def _page_profile(self) -> QWidget:
        page = QWidget()
        grid = QFormLayout(page)
        grid.setContentsMargins(0, 0, 0, 0)
        self.name_edit = QLineEdit()
        self.title_edit = QLineEdit()
        self.level_box = QComboBox()
        _fill(self.level_box, tuple(LEVELS))
        self.boss_box = QComboBox()
        self.skill_label = QLabel()
        self.kpis_edit = QPlainTextEdit()
        self.kpis_edit.setPlaceholderText("One measure per line")
        self.kpis_edit.setStyleSheet("QPlainTextEdit { outline: none; }")
        for caption, widget in (("Name", self.name_edit), ("Title", self.title_edit),
                                ("Level", self.level_box), ("Reports to", self.boss_box),
                                ("Skill", self.skill_label), ("KPIs", self.kpis_edit)):
            grid.addRow(caption, widget)
        return page

    def _page_model(self) -> QWidget:
        page = QWidget()
        lines = QVBoxLayout(page)
        lines.setContentsMargins(0, 0, 0, 0)
        grid = QGridLayout()
        grid.setColumnStretch(2, 1)
        self.main_source, self.main_model = self._model_row(grid, 0, "Main")
        self.backup_source, self.backup_model = self._model_row(grid, 1, "Backup")
        lines.addLayout(grid)
        lines.addWidget(muted("Pick a model from the list or type another name."))
        lines.addStretch(1)
        return page

    def _model_row(self, grid: QGridLayout, row: int,
                   caption: str) -> tuple[QComboBox, QComboBox]:
        source = QComboBox()
        _fill(source, SOURCES)
        source.setFixedWidth(130)
        model = QComboBox()
        model.setEditable(True)
        model.setMinimumWidth(260)
        grid.addWidget(QLabel(caption), row, 0)
        grid.addWidget(source, row, 1)
        grid.addWidget(model, row, 2, Qt.AlignmentFlag.AlignLeft)
        # source → currentTextChanged → page → refill that model list
        source.currentTextChanged.connect(lambda _t, s=source, m=model: self._fill_models(s, m))
        return source, model

    def _page_limits(self) -> QWidget:
        page = QWidget()
        lines = QVBoxLayout(page)
        lines.setContentsMargins(0, 0, 0, 0)
        grid = QFormLayout()
        self.calls_spin = QSpinBox()
        self.calls_spin.setRange(1, 500)
        self.cap_spin = QDoubleSpinBox()
        self.cap_spin.setRange(0.01, 10000.0)
        self.cap_spin.setDecimals(2)
        self.cap_spin.setPrefix("$")
        self.status_box = QComboBox()
        _fill(self.status_box, STATUSES)
        grid.addRow("Calls per day", self.calls_spin)
        grid.addRow("Month cap", self.cap_spin)
        grid.addRow("Status", self.status_box)
        lines.addLayout(grid)
        lines.addWidget(QLabel("Wakes on"))
        wake = QGridLayout()
        self.wake_checks: dict[str, QCheckBox] = {}
        for index, kind in enumerate(EVENT_KINDS):
            box = QCheckBox(kind.replace("_", " ").capitalize())
            self.wake_checks[kind] = box
            wake.addWidget(box, index // 2, index % 2)
        lines.addLayout(wake)
        lines.addStretch(1)
        return page

    def _page_history(self) -> QWidget:
        page = QWidget()
        lines = QHBoxLayout(page)
        lines.setContentsMargins(0, 0, 0, 0)
        left = QVBoxLayout()
        self.history_list = QListWidget()
        self.history_list.setStyleSheet(_list_style())
        self.history_list.setFixedWidth(220)
        self.restore_btn = QPushButton("Restore")
        left.addWidget(self.history_list, 1)
        left.addWidget(self.restore_btn)
        self.history_view = QPlainTextEdit()
        self.history_view.setReadOnly(True)
        self.history_view.setStyleSheet(f"QPlainTextEdit {{ {MONO} outline: none; }}")
        lines.addLayout(left)
        lines.addWidget(self.history_view, 1)
        # history list → currentRowChanged → page → _show_version
        self.history_list.currentRowChanged.connect(self._show_version)
        # restore → clicked → page → _on_restore
        self.restore_btn.clicked.connect(self._on_restore)
        return page

    def _build_save_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        self.note_label = QLabel()
        self.note_label.setWordWrap(True)
        self.test_btn = QPushButton("Test on yesterday")
        self.save_btn = QPushButton("Save")
        self.save_btn.setEnabled(False)
        bar.addWidget(self.note_label, 1)
        bar.addWidget(self.test_btn)
        bar.addWidget(self.save_btn)
        # buttons → clicked → page → _on_test, _on_save
        self.test_btn.clicked.connect(self._on_test)
        self.save_btn.clicked.connect(self._on_save)
        return bar

    def _wire_dirty(self) -> None:
        for edit in (self.name_edit, self.title_edit):
            edit.textChanged.connect(self._mark_dirty)
        for text in (self.prompt_edit, self.kpis_edit):
            text.textChanged.connect(self._mark_dirty)
        for combo in (self.level_box, self.boss_box, self.main_source, self.backup_source,
                      self.main_model, self.backup_model, self.status_box):
            combo.currentTextChanged.connect(self._mark_dirty)
        self.calls_spin.valueChanged.connect(self._mark_dirty)
        self.cap_spin.valueChanged.connect(self._mark_dirty)
        for box in self.wake_checks.values():
            box.toggled.connect(self._mark_dirty)

    # ── public ────────────────────────────────────────────────────────────

    def employee_ids(self) -> list[str]:
        """Return every employee id in tree order (top to bottom)."""
        return list(self._ids)

    def current_id(self) -> str:
        """Return the id of the picked employee, or an empty text."""
        return self._current

    def select(self, emp_id: str) -> None:
        """Pick ``emp_id`` in the tree (asks first when there are unsaved edits)."""
        item = self._items.get(emp_id)
        if item is not None:
            self.emp_tree.setCurrentItem(item)

    def reload(self) -> None:
        """Read the desk folder again and keep the picked employee."""
        keep = self._current
        shut = self._folded()
        self._models = known_models(self._home)
        self._ids, self._people, self._items = [], {}, {}
        self.emp_tree.blockSignals(True)
        self.emp_tree.clear()
        self._fill_tree(employee_folders(self._home), shut)
        target = keep if keep in self._items else (self._ids[0] if self._ids else "")
        if target:
            self.emp_tree.setCurrentItem(self._items[target])
        self.emp_tree.blockSignals(False)
        self.count_label.setText(f"Team · {len(self._ids)}")
        if not target:
            self._show_empty()
            return
        if target != keep or not (self._dirty or self._testing):
            self._open(target)
        if keep and keep not in self._ids and self._dirty:
            self._set_note("The employee you were editing is no longer in the desk folder",
                           C.RED)

    def showEvent(self, event: QShowEvent | None) -> None:  # noqa: N802
        """Move old employee files, then read the list again."""
        super().showEvent(event)
        migrate_all(self._home)
        self.reload()

    # ── tree ──────────────────────────────────────────────────────────────

    def _folded(self) -> set[str]:
        shut = {emp_id for emp_id, item in self._items.items()
                if item.childCount() and not item.isExpanded()}
        if self._folder is not None and not self._folder.isExpanded():
            shut.add(NO_LEAD)
        return shut

    def _fill_tree(self, folders: list[Path], shut: set[str]) -> None:
        """Leads (and anyone with people below) at the top; everyone else under No lead."""
        rows: dict[str, QTreeWidgetItem] = {}
        bosses: dict[str, str | None] = {}
        leads: set[str] = set()
        for folder in folders:
            item, spec = self._person(folder)
            rows[folder.name] = item
            bosses[folder.name] = spec.reports_to if spec else None
            if spec and spec.level == _LEAD:
                leads.add(folder.name)
        kids: dict[str, list[str]] = {emp_id: [] for emp_id in rows}
        for emp_id, boss in bosses.items():
            if boss in rows and boss != emp_id:
                kids[boss].append(emp_id)
        placed: set[str] = set()
        tree = (rows, kids, placed)
        loose: list[str] = []
        for emp_id, boss in bosses.items():
            if boss in rows and boss != emp_id:
                continue
            if emp_id in leads or kids[emp_id]:
                self._attach(self.emp_tree.invisibleRootItem(), emp_id, tree)
            else:
                loose.append(emp_id)
        loose += [emp_id for emp_id in rows if emp_id not in placed and emp_id not in loose]
        self._folder = None
        if loose:
            self._folder = QTreeWidgetItem()
            self._folder.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._folder.setForeground(0, QBrush(QColor(C.MUTED)))
            self.emp_tree.addTopLevelItem(self._folder)
            before = len(self._ids)
            for emp_id in loose:
                self._attach(self._folder, emp_id, tree)
            self._folder.setText(0, f"{NO_LEAD} · {len(self._ids) - before}")
            self._folder.setExpanded(NO_LEAD not in shut)
        for emp_id, item in self._items.items():
            item.setExpanded(emp_id not in shut)

    def _attach(self, parent: QTreeWidgetItem | None, emp_id: str,
                tree: tuple[dict[str, QTreeWidgetItem], dict[str, list[str]], set[str]]) -> None:
        rows, kids, placed = tree
        if parent is None or emp_id in placed:
            return
        placed.add(emp_id)
        item = rows[emp_id]
        parent.addChild(item)
        self._items[emp_id] = item
        self._ids.append(emp_id)
        for kid in kids[emp_id]:
            self._attach(item, kid, tree)

    def _person(self, folder: Path) -> tuple[QTreeWidgetItem, JobSpec | None]:
        emp_id = folder.name
        spec: JobSpec | None = None
        try:
            emp = load(folder)
        except ValueError as exc:
            item = QTreeWidgetItem([f"{emp_id}\nnot valid: {exc}"])
            item.setForeground(0, QBrush(Qt.GlobalColor.red))
        else:
            spec = emp.spec
            self._people[emp_id] = spec.name
            item = QTreeWidgetItem([f"{initials(spec.name)}  {spec.name}\n"
                                    f"{skill_text(spec.skill)} · {_label(spec.status)}"])
        item.setData(0, _ROLE, emp_id)
        return item, spec

    def _on_click(self, item: QTreeWidgetItem | None, _column: int) -> None:
        if item is not None and item is self._folder:
            item.setExpanded(not item.isExpanded())

    def _on_item(self, current: QTreeWidgetItem | None, _previous: object) -> None:
        emp_id = str(current.data(0, _ROLE) or "") if current is not None else ""
        if not emp_id or emp_id == self._current:
            return
        if self._dirty and not self._ask(f"Discard unsaved changes to {self._name}?"):
            back = self._items.get(self._current)
            self.emp_tree.blockSignals(True)
            if back is not None:
                self.emp_tree.setCurrentItem(back)
            self.emp_tree.blockSignals(False)
            return
        self.note_label.clear()
        self._open(emp_id)

    # ── form ──────────────────────────────────────────────────────────────

    def _show_empty(self) -> None:
        self._current, self._name, self._spec = "", "", None
        self._set_dirty(False)
        self._token += 1
        self._testing = False
        self.name_label.setText("")
        self.role_label.setText("")
        self.status_chip.hide()
        self.form.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.test_btn.setEnabled(False)
        self._set_note("No employees yet", C.MUTED)

    def _open(self, emp_id: str) -> None:
        changed = emp_id != self._current
        self._current = emp_id
        self._token += 1
        self._testing = False
        folder = self._home / "employees" / emp_id
        try:
            emp = load(folder)
        except ValueError as exc:
            self._show_broken(emp_id, str(exc))
            return
        self._spec, self._name = emp.spec, emp.spec.name
        self.form.setEnabled(True)
        self._fill(emp)
        self._fill_history(folder)
        self._has_run = last_run(self._home, emp_id) is not None
        if changed:
            self.result_label.hide()
        self._refresh_test()
        if changed and not self._has_run:
            self._show_result(NO_RUN_NOTE, C.MUTED)
        self._set_dirty(False)

    def _show_broken(self, emp_id: str, reason: str) -> None:
        self._spec, self._name = None, emp_id
        self.name_label.setText(emp_id)
        self.role_label.setText("")
        self.status_chip.hide()
        self.form.setEnabled(False)
        self.test_btn.setEnabled(False)
        self._set_note(f"Not valid: {reason}", C.RED)
        self._set_dirty(False)

    def _fill(self, emp: EmployeeFile) -> None:
        spec = emp.spec
        self._loading = True
        try:
            self.name_label.setText(spec.name)
            self.role_label.setText(f"{spec.title} · {skill_text(spec.skill)}")
            self.status_chip.setText(chip_text(_label(spec.status)))
            self.status_chip.setStyleSheet(chip_style(_STATUS_KEY[spec.status]))
            self.status_chip.show()
            self.prompt_edit.setPlainText(emp.prompt)
            self.name_edit.setText(spec.name)
            self.title_edit.setText(spec.title)
            _pick(self.level_box, spec.level)
            self._fill_boss(spec)
            self.skill_label.setText(skill_text(spec.skill))
            self.kpis_edit.setPlainText("\n".join(spec.kpis))
            for source, model, choice in ((self.main_source, self.main_model,
                                           spec.models.primary),
                                          (self.backup_source, self.backup_model,
                                           spec.models.backup)):
                _pick(source, choice.source)
                self._fill_models(source, model)
                model.setEditText(choice.model)
            self.calls_spin.setValue(spec.calls_per_day)
            self.cap_spin.setValue(spec.monthly_cost_usd)
            _pick(self.status_box, spec.status)
            for kind, box in self.wake_checks.items():
                box.setChecked(kind in spec.trigger)
        finally:
            self._loading = False

    def _fill_boss(self, spec: JobSpec) -> None:
        self.boss_box.clear()
        self.boss_box.addItem(NO_BOSS, None)
        for emp_id, name in self._people.items():
            if emp_id != spec.id:
                self.boss_box.addItem(name, emp_id)
        if spec.reports_to and self.boss_box.findData(spec.reports_to) < 0:
            self.boss_box.addItem(spec.reports_to, spec.reports_to)
        self.boss_box.setCurrentIndex(max(0, self.boss_box.findData(spec.reports_to)))

    def _fill_models(self, source: QComboBox, model: QComboBox) -> None:
        keep = model.currentText()
        model.blockSignals(True)
        model.clear()
        model.addItems(self._models.get(_value(source), []))
        model.setEditText(keep)
        model.blockSignals(False)

    def _fields(self) -> dict[str, Any]:
        boss = self.boss_box.currentData()
        return {
            "name": self.name_edit.text(),
            "title": self.title_edit.text(),
            "level": _value(self.level_box),
            "reports_to": boss if boss else None,
            "kpis": [k.strip() for k in self.kpis_edit.toPlainText().splitlines()
                     if k.strip()],
            "models": {
                "primary": {"source": _value(self.main_source),
                            "model": self.main_model.currentText().strip()},
                "backup": {"source": _value(self.backup_source),
                           "model": self.backup_model.currentText().strip()},
            },
            "trigger": [k for k, box in self.wake_checks.items() if box.isChecked()],
            "calls_per_day": self.calls_spin.value(),
            "monthly_cost_usd": round(self.cap_spin.value(), 2),
            "status": _value(self.status_box),
        }

    def _mark_dirty(self, *_args: object) -> None:
        if not self._loading and self._spec is not None:
            self._set_dirty(True)

    def _set_dirty(self, dirty: bool) -> None:
        self._dirty = dirty
        self.save_btn.setEnabled(dirty and self._spec is not None)

    def _set_note(self, text: str, colour: str) -> None:
        self.note_label.setText(text)
        self.note_label.setStyleSheet(f"color: {colour};")

    # ── save ──────────────────────────────────────────────────────────────

    def _on_save(self) -> None:
        reason = save_employee(self._home, self._current, self._fields(),
                               self.prompt_edit.toPlainText())
        if reason:
            self._set_note(f"Not saved: {reason}", C.RED)
            return
        self._after_new_version()

    def _after_new_version(self) -> None:
        emp_id = self._current
        self._set_dirty(False)
        self.reload()
        found = read_employee(self._home / "employees" / emp_id)
        number = found.spec.version if found else 0
        self._set_note(f"Saved as version {number} · applies from the next wake", C.GREEN)
        self.saved.emit(emp_id)

    # ── history ───────────────────────────────────────────────────────────

    def _fill_history(self, folder: Path) -> None:
        self.history_list.blockSignals(True)
        self.history_list.clear()
        for ver in versions(folder):
            text = f"v {ver.number} · {ver.saved:%d-%m-%Y %H:%M}"
            item = QListWidgetItem(text + (" · current" if ver.current else ""))
            item.setData(_ROLE, (ver.number, str(ver.path), ver.current))
            self.history_list.addItem(item)
        self.history_list.blockSignals(False)
        self.history_list.setCurrentRow(0 if self.history_list.count() else -1)
        self._show_version(self.history_list.currentRow())

    def _show_version(self, row: int) -> None:
        item = self.history_list.item(row) if row >= 0 else None
        if item is None:
            self.history_view.clear()
            self.restore_btn.setEnabled(False)
            return
        _number, path, current = item.data(_ROLE)
        try:
            self.history_view.setPlainText(parse(Path(path).read_text(encoding="utf-8")).prompt)
        except (OSError, ValueError) as exc:
            self.history_view.setPlainText(f"This version cannot be read: {exc}")
        self.restore_btn.setEnabled(not current)

    def _on_restore(self) -> None:
        item = self.history_list.currentItem()
        if item is None:
            return
        number = int(item.data(_ROLE)[0])
        lost = " Your unsaved changes will be lost." if self._dirty else ""
        if not self._ask(f"Restore version {number} as a new version?{lost}"):
            return
        reason = restore(self._home, self._current, number)
        if reason:
            self._set_note(f"Not saved: {reason}", C.RED)
            return
        self._after_new_version()

    # ── test on yesterday ─────────────────────────────────────────────────

    def _refresh_test(self) -> None:
        if self._testing:
            self.test_btn.setText("Testing…")
            self.test_btn.setEnabled(False)
            return
        self.test_btn.setText("Test on yesterday")
        self.test_btn.setEnabled(self._has_run)
        self.test_btn.setToolTip("" if self._has_run else NO_RUN_NOTE)

    def _show_result(self, text: str, colour: str) -> None:
        self.result_label.setText(text)
        self.result_label.setStyleSheet(bar_style(colour))
        self.result_label.show()

    def _on_test(self) -> None:
        if self._spec is None or self._testing:
            return
        try:
            data = self._spec.model_dump(mode="json") | self._fields()
            text = render(check(data), self.prompt_edit.toPlainText())
        except ValueError as exc:
            self._show_result(f"Not valid\n{exc}", C.RED)
            return
        self._token += 1
        self._testing = True
        self._refresh_test()
        self.result_label.hide()
        job = _DraftJob(self._runner, self._home, self._current, text, self._token)
        _RUNNING.add(job)
        # job → done → module → _forget (drops the finished job even when the page is gone)
        job.signals.done.connect(lambda *_: _RUNNING.discard(job))
        # job → done → page → _on_draft_done
        job.signals.done.connect(self._on_draft_done)
        QThreadPool.globalInstance().start(job)  # type: ignore[union-attr]

    def _on_draft_done(self, token: int, result: DraftResult) -> None:
        if token != self._token:
            return
        self._testing = False
        self._refresh_test()
        if result.valid:
            self._show_result(f"Valid answer\n{result.answer}", C.GREEN)
        else:
            detail = "\n".join(t for t in (result.note, result.answer) if t)
            self._show_result(f"Not valid\n{detail}".rstrip(), C.RED)

