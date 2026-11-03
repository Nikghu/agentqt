"""
Module: MD-GUI-024.004.M04 / MD-GUI-032.003.M03 — Strategies tab (grouped or table + detail)
Parent SRD: SRD-GUI-024.004, SRD-GUI-024.005, SRD-GUI-024.007, SRD-GUI-032.002

Replaces the Strategy Builder table.  Two views: a grouped list with the
selected strategy's detail on the right, or a table whose clicked row opens
the same detail under it.  The detail holds the header and actions, four
setting boxes, the P&L card and today's trades.  The add / edit / delete /
reset / run logic is the old ``_StrategyTablePane`` logic.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Any

from PyQt6.QtCore import QSettings, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from us_swing.gui.app_service import AppService
from us_swing.gui.icons import mark_danger, set_icon
from us_swing.gui.strategy_builder_dialog import (
    StrategyBuilderDialog,
    StrategyConfig,
    load_strategies,
    save_strategies,
)
from us_swing.gui.strategy_pnl_chart import StrategyPnlCard, money
from us_swing.gui.strategy_table_model import (
    COL_CAPITAL,
    COL_SCOPE,
    COL_STOPLOSS,
    COL_STOPLOSS_TYPE,
    COL_TARGET,
    COL_TARGET_TYPE,
    StrategyTableModel,
    _cell_text,
)
from us_swing.gui.strategies_views import (
    LIVE,
    GroupedList,
    StrategyRow,
    StrategyTable,
    pill_text,
    status_colour,
    strategy_rows,
)
from us_swing.gui.popups import confirm, notify
from us_swing.gui.theme import C

_MONO = '"IBM Plex Mono", Consolas, monospace'
GROUPED, TABLE = "grouped", "table"
_VIEW_KEY = "strategies_view"


def unique_copy_name(name: str, taken: set[str]) -> str:
    """First free name of the form "<name> copy", "<name> copy 2", …"""
    candidate = f"{name} copy"
    n = 2
    while candidate in taken:
        candidate = f"{name} copy {n}"
        n += 1
    return candidate


def _date(text: str) -> str:
    try:
        return datetime.strptime(text, "%Y-%m-%d").strftime("%d %b %Y")
    except ValueError:
        return text


class _InfoBox(QFrame):
    """Titled box of key / value rows."""

    def __init__(self, title: str) -> None:
        super().__init__()
        self.setObjectName("detail_tile")
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(12, 10, 12, 10)
        self._grid.setVerticalSpacing(6)
        head = QLabel(title)
        head.setObjectName("view_head")
        self._grid.addWidget(head, 0, 0, 1, 2)
        self.values: dict[str, QLabel] = {}

    def set_rows(self, rows: list[tuple[str, str, str | None]]) -> None:
        for r, (key, text, colour) in enumerate(rows, start=1):
            if key not in self.values:
                key_lbl = QLabel(key)
                key_lbl.setObjectName("details_key")
                value = QLabel()
                value.setAlignment(Qt.AlignmentFlag.AlignRight)
                self._grid.addWidget(key_lbl, r, 0)
                self._grid.addWidget(value, r, 1)
                self.values[key] = value
            self.values[key].setText(text)
            self.values[key].setStyleSheet(f"color:{colour};" if colour else "")


class StrategiesPane(QWidget):
    """Strategies tab (SRD-GUI-024.004–.007, SRD-GUI-032.002–.007)."""

    count_changed = pyqtSignal(int)

    def __init__(self, demo: AppService, parent: QWidget | None = None,
                 settings: QSettings | None = None) -> None:
        super().__init__(parent)
        self._demo = demo
        self._settings = settings or QSettings("USSwing", "ExecutionPanel")
        self._configs: list[StrategyConfig] = load_strategies()
        self._selected: str | None = None
        self._filter = ""
        self._view = GROUPED if self._settings.value(_VIEW_KEY) != TABLE else TABLE
        # Used only for status_for(): RUNNING when an open cycle forces it.
        self._model = StrategyTableModel(self)
        demo.strategy_status_changed.connect(self._on_engine_status)

        self.tools = self._build_tools()

        # ── Grouped view: list on the left ─────────────────────────────────────
        self.groups = GroupedList()
        self.groups.setFixedWidth(300)
        self.groups.picked.connect(self._on_picked)
        sep = QFrame()
        sep.setObjectName("side_sep")
        sep.setFixedWidth(1)

        # ── Detail ─────────────────────────────────────────────────────────────
        self.title_lbl = QLabel("")
        self.title_lbl.setStyleSheet(f"font-family:{_MONO}; font-size:12pt; font-weight:bold;")
        self.status_lbl = QLabel("")
        self.since_lbl = QLabel("")
        self.since_lbl.setObjectName("view_key")
        self.edit_btn = QPushButton("Edit")
        set_icon(self.edit_btn, "pencil", "info")
        self.copy_btn = QPushButton("Duplicate")
        set_icon(self.copy_btn, "copy", "info")
        self.reset_btn = QPushButton("Reset count")
        set_icon(self.reset_btn, "refresh-cw", "info")
        self.reset_btn.setToolTip("Clear the per-stock re-entry budget")
        self.run_btn = QPushButton("Start")
        self.delete_btn = QPushButton()
        set_icon(self.delete_btn, "trash-2", "danger")
        self.delete_btn.setToolTip("Delete strategy")
        self.delete_btn.setAccessibleName("Delete strategy")
        self.delete_btn.setFixedWidth(C.BTN_H + 6)
        mark_danger(self.delete_btn)
        self.edit_btn.clicked.connect(lambda: self._on_edit(self._sel_row()))
        self.copy_btn.clicked.connect(lambda: self._on_duplicate(self._sel_row()))
        self.reset_btn.clicked.connect(lambda: self._on_reset(self._sel_row()))
        self.run_btn.clicked.connect(lambda: self._on_run(self._sel_row()))
        self.delete_btn.clicked.connect(lambda: self._on_delete(self._sel_row()))

        detail_head = QHBoxLayout()
        detail_head.setSpacing(8)
        detail_head.addWidget(self.title_lbl)
        detail_head.addWidget(self.status_lbl)
        detail_head.addWidget(self.since_lbl)
        detail_head.addStretch(1)
        for btn in (self.edit_btn, self.copy_btn, self.reset_btn, self.run_btn, self.delete_btn):
            detail_head.addWidget(btn)

        self.trades_box = _InfoBox("WHAT IT TRADES")
        self.when_box = _InfoBox("WHEN")
        self.size_box = _InfoBox("SIZE")
        self.exit_box = _InfoBox("EXIT RULES")
        boxes = QHBoxLayout()
        boxes.setSpacing(8)
        for box in (self.trades_box, self.when_box, self.size_box, self.exit_box):
            boxes.addWidget(box, 1)

        self.pnl_card = StrategyPnlCard()

        today_head = QLabel("TODAY")
        today_head.setObjectName("view_head")
        self.today_lbl = QLabel("")
        self.today_lbl.setTextFormat(Qt.TextFormat.RichText)
        today = QFrame()
        today.setObjectName("detail_tile")
        today_row = QHBoxLayout(today)
        today_row.setContentsMargins(12, 8, 12, 8)
        today_row.setSpacing(16)
        today_row.addWidget(today_head)
        today_row.addWidget(self.today_lbl, 1)

        self.detail = QWidget()
        detail_box = QVBoxLayout(self.detail)
        detail_box.setContentsMargins(14, 10, 14, 10)
        detail_box.setSpacing(8)
        detail_box.addLayout(detail_head)
        detail_box.addLayout(boxes)
        detail_box.addWidget(self.pnl_card, 1)
        detail_box.addWidget(today)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        grouped = QWidget()
        grouped_box = QHBoxLayout(grouped)
        grouped_box.setContentsMargins(0, 0, 0, 0)
        grouped_box.setSpacing(0)
        grouped_box.addWidget(self.groups)
        grouped_box.addWidget(sep)
        grouped_box.addWidget(self._scroll, 1)

        # ── Table view: bulk bar over the table ────────────────────────────────
        self.table = StrategyTable(stash=self)
        self.table.row_clicked.connect(self._on_row_clicked)
        self.table.run_clicked.connect(self._on_row_run)
        self.table.checked_changed.connect(self._on_checked)
        table_page = QWidget()
        table_box = QVBoxLayout(table_page)
        table_box.setContentsMargins(0, 0, 0, 0)
        table_box.setSpacing(0)
        table_box.addWidget(self._build_bulk_bar())
        table_box.addWidget(self.table, 1)

        self.views = QStackedWidget()
        self.views.addWidget(grouped)
        self.views.addWidget(table_page)

        self.empty_lbl = QLabel("No strategies yet — click Add to create one.")
        self.empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_lbl.setStyleSheet(f"color:{C.MUTED}; padding:24px;")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self.views, 1)
        root.addWidget(self.empty_lbl, 1)

        self._show_view(self._view)

    def _build_tools(self) -> QWidget:
        """Running count, Find, Add and the two view icons (SRD-GUI-032.002)."""
        self.running_lbl = QLabel("")
        self.running_lbl.setObjectName("view_key")
        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText("Find strategy…")
        self.find_edit.setClearButtonEnabled(True)
        self.find_edit.setFixedWidth(200)
        self.find_edit.textChanged.connect(self._on_find)
        add_btn = QPushButton("Add")
        set_icon(add_btn, "plus", "add")
        add_btn.clicked.connect(self._on_add)
        self.grouped_btn = QPushButton()
        set_icon(self.grouped_btn, "list", "neutral")
        self.grouped_btn.setToolTip("Grouped view")
        self.grouped_btn.setAccessibleName("Grouped view")
        self.table_btn = QPushButton()
        set_icon(self.table_btn, "table", "neutral")
        self.table_btn.setToolTip("Table view")
        self.table_btn.setAccessibleName("Table view")
        views = QButtonGroup(self)
        for btn, view in ((self.grouped_btn, GROUPED), (self.table_btn, TABLE)):
            btn.setObjectName("mode_btn")
            btn.setCheckable(True)
            btn.setFixedWidth(C.BTN_H + 6)
            views.addButton(btn)
            btn.clicked.connect(lambda _on, v=view: self.set_view(v))

        tools = QWidget()
        row = QHBoxLayout(tools)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(self.running_lbl)
        row.addSpacing(6)
        row.addWidget(self.find_edit)
        row.addWidget(add_btn)
        row.addWidget(self.grouped_btn)
        row.addWidget(self.table_btn)
        return tools

    def _build_bulk_bar(self) -> QWidget:
        """"N selected" with Start, Stop and Reset count (SRD-GUI-032.006)."""
        self.bulk_lbl = QLabel("")
        self.bulk_lbl.setObjectName("view_key")
        start = QPushButton("Start")
        set_icon(start, "play", "go")
        start.clicked.connect(lambda: self._bulk_run(start=True))
        stop = QPushButton("Stop")
        set_icon(stop, "square-x", "danger")
        mark_danger(stop)
        stop.clicked.connect(lambda: self._bulk_run(start=False))
        reset = QPushButton("Reset count")
        set_icon(reset, "refresh-cw", "info")
        reset.clicked.connect(lambda: self._reset_names(self.table.checked_names()))
        self.bulk_bar = QFrame()
        self.bulk_bar.setObjectName("strategy_bulk")
        row = QHBoxLayout(self.bulk_bar)
        row.setContentsMargins(14, 6, 14, 6)
        row.setSpacing(8)
        row.addWidget(self.bulk_lbl)
        for btn in (start, stop, reset):
            row.addWidget(btn)
        row.addStretch(1)
        self.bulk_bar.hide()
        return self.bulk_bar

    # ── Views ─────────────────────────────────────────────────────────────────

    @property
    def view(self) -> str:
        return self._view

    @property
    def strategy_count(self) -> int:
        return len(self._configs)

    def set_view(self, view: str) -> None:
        """Show the grouped or table view and remember it (SRD-GUI-032.007)."""
        self._settings.setValue(_VIEW_KEY, view)
        self._show_view(view)

    def _show_view(self, view: str) -> None:
        self._view = view
        self.grouped_btn.setChecked(view == GROUPED)
        self.table_btn.setChecked(view == TABLE)
        self.views.setCurrentIndex(0 if view == GROUPED else 1)
        if view == TABLE and self._scroll.widget() is self.detail:
            self._scroll.takeWidget()
            self.detail.setParent(self)
        self._refresh_table(open_selected=view == TABLE)

    def _place_detail(self, open_selected: bool) -> None:
        """Put the detail on the grouped right side, or under the table row."""
        if self._view == GROUPED:
            self.table.close_detail()
            if self._scroll.widget() is not self.detail:
                self._scroll.setWidget(self.detail)
                self.detail.show()
        elif open_selected and self._selected is not None:
            self.table.open_detail(self._selected, self.detail)

    # ── Data helpers ──────────────────────────────────────────────────────────

    def _status(self, cfg: StrategyConfig) -> str:
        return self._model.status_for(cfg)

    def _rows(self) -> list[StrategyRow]:
        text = self._filter.lower()
        shown = [c for c in self._configs if text in c.name.lower()]
        return strategy_rows(
            shown, self._status,
            lambda name: self._demo.get_strategy_pnl(name, None),
            lambda name: len(self._demo.get_open_symbols_for_strategy(name)),
        )

    def _refresh_table(self, select: str | None = None, open_selected: bool = False) -> None:
        """Reload both views; keep (or move to) the selected strategy."""
        running_override = self._demo.get_strategies_with_open_cycles()
        self._model.load(self._configs, running_override=running_override)
        names = [c.name for c in self._configs]
        current = select or self._selected
        if current not in names:
            current = names[0] if names else None
        self._selected = current
        rows = self._rows()
        if select is not None and self._view == TABLE:
            open_selected = True
        self._show_detail(self._sel_row())
        self.groups.fill(rows, current)
        self.table.fill(rows)
        self._place_detail(open_selected)
        live = sum(self._status(c) in LIVE for c in self._configs)
        self.running_lbl.setText(f"{live} of {len(self._configs)} running")
        has_rows = bool(self._configs)
        self.views.setVisible(has_rows)
        self.empty_lbl.setVisible(not has_rows)
        self.count_changed.emit(len(self._configs))

    def _sel_row(self) -> int:
        names = [c.name for c in self._configs]
        return names.index(self._selected) if self._selected in names else -1

    def _current_name(self) -> str | None:
        return self._selected

    # ── View events ───────────────────────────────────────────────────────────

    def _on_picked(self, name: str) -> None:
        self._selected = name
        self._show_detail(self._sel_row())

    def _on_row_clicked(self, name: str) -> None:
        """Open the clicked row; close it when it is already open (SRD-GUI-032.005)."""
        if self.table.open_name == name:
            self.table.close_detail()
            return
        self._selected = name
        self._show_detail(self._sel_row())
        self.table.open_detail(name, self.detail)

    def _on_row_run(self, name: str) -> None:
        """Row button acts on its own strategy without moving the selection."""
        names = [c.name for c in self._configs]
        if name not in names:
            return
        row = names.index(name)
        cfg = self._configs[row]
        if cfg.mode.lower() == "disabled" and self._status(cfg) not in LIVE:
            self._on_edit(row)
        else:
            self._on_run(row)

    def _on_find(self, text: str) -> None:
        self._filter = text.strip()
        self._refresh_table(open_selected=self.table.open_name is not None)

    def _on_checked(self, names: list[str]) -> None:
        self.bulk_lbl.setText(f"{len(names)} selected")
        self.bulk_bar.setVisible(bool(names))

    # ── Detail ────────────────────────────────────────────────────────────────

    def _show_detail(self, row: int) -> None:
        if not 0 <= row < len(self._configs):
            self.pnl_card.set_provider(None)
            return
        cfg = self._configs[row]
        status = self._status(cfg)
        colour = status_colour(status)
        self.title_lbl.setText(cfg.name)
        self.status_lbl.setText(pill_text(status))
        self.status_lbl.setStyleSheet(
            f"color:{colour}; border:1px solid {colour}; border-radius:8px;"
            f" padding:1px 8px; font-size:7.5pt; font-weight:bold;"
        )
        self.since_lbl.setText(f"{cfg.mode.capitalize()} · since {_date(cfg.start_date)}")
        live = status in LIVE
        self.run_btn.setText("Stop" if live else "Start")
        set_icon(self.run_btn, "square-x" if live else "play", "danger" if live else "go")
        if live:
            mark_danger(self.run_btn)
        else:
            self.run_btn.setProperty("role", "")
            style = self.run_btn.style()
            if style is not None:
                style.unpolish(self.run_btn)
                style.polish(self.run_btn)

        side = "Short" if cfg.direction == "SHORT" else "Long"
        self.trades_box.set_rows([
            ("Universe", _cell_text(cfg, COL_SCOPE), None),
            ("Trade type", cfg.trade_type, None),
            ("Direction", side, C.RED if side == "Short" else C.GREEN),
        ])
        self.when_box.set_rows([
            ("Entry window", f"{cfg.start_time} – {cfg.end_time}", None),
            ("Start date", cfg.start_date, None),
            ("End date", cfg.end_date, None),
        ])
        self.size_box.set_rows([
            ("Capital", _cell_text(cfg, COL_CAPITAL), None),
            ("Per trade", f"{cfg.per_trade_pct} %", None),
            ("Re-entries", f"{cfg.rex_count} per stock" if cfg.rex_count else "None", None),
        ])
        self.exit_box.set_rows([
            ("Target", self._rule(cfg, COL_TARGET, COL_TARGET_TYPE), None),
            ("Stop loss", self._rule(cfg, COL_STOPLOSS, COL_STOPLOSS_TYPE), None),
            ("Exit rule", "Set" if cfg.exit_condition else "None", None),
        ])
        name = cfg.name
        self.pnl_card.set_provider(lambda since: self._demo.get_strategy_pnl(name, since))
        self._show_today(name)

    @staticmethod
    def _rule(cfg: StrategyConfig, value_col: int, type_col: int) -> str:
        value = _cell_text(cfg, value_col)
        return "Not set" if value == "—" else f"{value} · {_cell_text(cfg, type_col)}"

    def _show_today(self, name: str) -> None:
        parts = [self._trade_html(c) for c in self._today_cycles(name)]
        self.today_lbl.setText(
            "&nbsp;&nbsp;&nbsp;&nbsp;".join(parts) if parts
            else f"<span style='color:{C.MUTED}'>No trades today</span>"
        )

    def _today_cycles(self, name: str) -> list[Any]:
        from us_swing.gui.active_cycles_model import _today_et_bounds_utc

        query = self._demo.cycle_query
        if query is None:
            return []
        uid = self._demo.get_viewing_uid()
        cycles = list(query.open_cycles_for_strategy(name)) + [
            c for c in query.closed_between(*_today_et_bounds_utc()) if c.strategy_id == name
        ]
        return [c for c in cycles if uid is None or c.user_id == uid]

    @staticmethod
    def _trade_html(c: Any) -> str:
        closed = str(c.state) == "CLOSED"
        pnl = (c.realized_pnl_usd if closed else c.current_pnl_usd) or 0.0
        side = "Short" if c.direction == "SHORT" else "Long"
        side_colour = C.RED if side == "Short" else C.GREEN
        pnl_colour = C.GREEN if pnl > 0 else C.RED if pnl < 0 else C.TEXT
        state = "Closed" if closed else str(c.state).title()
        qty = c.exit_qty if closed and c.exit_qty else c.entry_qty
        return (
            f"<b>{c.symbol}</b> <span style='color:{side_colour}'>{side}</span> {qty}"
            f" · {state} · <span style='color:{pnl_colour}'>{money(pnl)}</span>"
        )

    # ── Slots (logic of the old Strategy Builder table) ───────────────────────

    def _on_add(self) -> None:
        existing_names = {c.name for c in self._configs}
        dlg = StrategyBuilderDialog(
            self, existing_names=existing_names, max_capital=self._demo.effective_capital()
        )
        dlg.strategy_saved.connect(self._append_config)
        dlg.exec()

    def _on_edit(self, src_row: int) -> None:
        if src_row < 0 or src_row >= len(self._configs):
            return
        original = self._configs[src_row]
        existing_names = {c.name for c in self._configs}
        dlg = StrategyBuilderDialog(
            self, existing=original, existing_names=existing_names,
            max_capital=self._demo.effective_capital(),
            has_open_trades=bool(self._demo.has_live_or_pending_trades(original.name)),
        )

        def _on_saved(cfg: StrategyConfig) -> None:
            self._configs[src_row] = cfg
            save_strategies(self._configs)
            self._demo.reload_strategy_registry()
            self._refresh_table(select=cfg.name)

        dlg.strategy_saved.connect(_on_saved)
        dlg.exec()

    def _on_duplicate(self, src_row: int) -> None:
        """Save a stopped copy under a new unique name (SRD-GUI-024.005)."""
        if src_row < 0 or src_row >= len(self._configs):
            return
        source = self._configs[src_row]
        copy = dataclasses.replace(
            source,
            name=unique_copy_name(source.name, {c.name for c in self._configs}),
            run_state="STOPPED",
            days=list(source.days),
            symbols_include=list(source.symbols_include),
            symbols_exclude=list(source.symbols_exclude),
        )
        self._configs.append(copy)
        save_strategies(self._configs)
        self._demo.reload_strategy_registry()
        self._refresh_table(select=copy.name)

    def _on_delete(self, src_row: int) -> None:
        if src_row < 0 or src_row >= len(self._configs):
            return
        cfg = self._configs[src_row]
        if confirm(self, "Delete Strategy",
                   f"Delete strategy '{cfg.name}'?\n\nIts closed trades stay in the database.",
                   confirm_text="Delete", danger=True):
            self._configs.pop(src_row)
            save_strategies(self._configs)
            repo = getattr(self._demo, "rex_counters", None)
            if repo is not None:
                try:
                    repo.reset(cfg.name)
                except Exception:
                    pass
            self._refresh_table()

    def _on_reset(self, src_row: int) -> None:
        if src_row < 0 or src_row >= len(self._configs):
            return
        self._reset_names([self._configs[src_row].name])

    def _reset_names(self, names: list[str]) -> None:
        """Clear the rex counters of ``names`` after one confirm."""
        if not names:
            return
        repo = getattr(self._demo, "rex_counters", None)
        if repo is None:
            notify(
                self,
                "Reset unavailable",
                "Rex counter repository is not initialized — restart the app and try again.",
                "warning",
            )
            return
        label = f"'{names[0]}'" if len(names) == 1 else f"{len(names)} strategies"
        if not confirm(
            self,
            "Reset Strategy",
            f"Reset rex counters for {label}?\n\n"
            "This clears the per-stock re-entry budget so the strategy can take fresh entries.\n"
            "Open positions are NOT affected.",
            confirm_text="Reset",
        ):
            return
        deleted = 0
        try:
            for name in names:
                deleted += repo.reset(name)
        except Exception as exc:
            notify(self, "Reset failed", f"Could not reset counters:\n{exc}", "error")
            return
        notify(
            self,
            "Reset complete",
            f"Cleared {deleted} rex counter row(s) for {label}.",
        )

    def _append_config(self, cfg: StrategyConfig) -> None:
        self._configs.append(cfg)
        save_strategies(self._configs)
        self._refresh_table(select=cfg.name)

    def _on_run(self, src_row: int) -> None:
        """Start / Stop toggle.

        Start (STOPPED → RUNNING): arms evaluation immediately.

        Stop (RUNNING → STOPPED or SQUARING_OFF):
        - With no open cycles: transitions to STOPPED immediately.
        - With one or more open cycles: transitions to SQUARING_OFF; the
          engine emits forced EXITs for each open cycle and auto-transitions
          to STOPPED when the last cycle closes (FO-EXE-013 AC#3).

        Stop while SQUARING_OFF: forces STOPPED once no open cycles remain
        (or the cycle ledger is absent), so a strategy can never be locked
        into the squaring-off badge; stays SQUARING_OFF while cycles remain.
        """
        if src_row < 0 or src_row >= len(self._configs):
            return
        self._apply_run_states([self._configs[src_row]])

    def _bulk_run(self, start: bool) -> None:
        """Start the checked stopped strategies, or stop the checked live ones."""
        checked = set(self.table.checked_names())
        targets = [
            c for c in self._configs if c.name in checked
            and (self._status(c) == "STOPPED" and c.mode.lower() != "disabled"
                 if start else self._status(c) in LIVE)
        ]
        self._apply_run_states(targets)

    def _next_run_state(self, cfg: StrategyConfig) -> str | None:
        # Effective state (badge source) so a Stop always performs a stop,
        # even when RUNNING is forced by an open cycle.
        current = self._status(cfg)
        if current == "STOPPED":
            return "RUNNING"
        open_syms = self._demo.get_open_symbols_for_strategy(cfg.name)
        if current == "SQUARING_OFF":
            return None if open_syms else "STOPPED"
        return "SQUARING_OFF" if open_syms else "STOPPED"

    def _apply_run_states(self, configs: list[StrategyConfig]) -> None:
        changes = [(c, s) for c in configs if (s := self._next_run_state(c)) is not None]
        if not changes:
            return
        for cfg, new_state in changes:
            cfg.run_state = new_state
        save_strategies(self._configs)
        for cfg, new_state in changes:
            self._notify_engine_run_state(cfg.name, new_state)
        self._demo.reload_strategy_registry()
        self._refresh_table()

    def _notify_engine_run_state(self, strategy_id: str, new_state: str) -> None:
        engine = getattr(self._demo, "_strategy_engine", None)
        if engine is None:
            return
        try:
            from us_swing.execution import ExecutionEnums
            engine.set_run_state(strategy_id, ExecutionEnums.StrategyRunState(new_state))
        except Exception:
            pass

    def _on_engine_status(self, strategy_name: str, new_status: str) -> None:
        """A strategy entered or exited a position.

        The RUNNING status is derived live from open cycles in
        ``_refresh_table`` (via ``running_override``), so we only refresh
        here; the P&L card and Today strip reload with the detail.
        ``run_state`` must never be overwritten with the legacy
        ``"Active"`` / ``"Running"`` vocabulary — those are not valid
        ``StrategyRunState`` values and corrupt the persisted column.
        """
        self._refresh_table()
