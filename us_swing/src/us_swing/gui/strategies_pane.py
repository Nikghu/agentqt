"""
Module: MD-GUI-024.004.M04 — Strategies tab (list + detail)
Parent SRD: SRD-GUI-024.004, SRD-GUI-024.005, SRD-GUI-024.007

Replaces the Strategy Builder table.  Left: strategy list.  Right: the
selected strategy's header and actions, four setting boxes, its P&L card
and today's trades.  The add / edit / delete / reset / run logic is the old
``_StrategyTablePane`` logic, unchanged.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Any

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
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
from us_swing.gui.theme import C

_LIVE = ("RUNNING", "SQUARING_OFF")
_MONO = '"IBM Plex Mono", Consolas, monospace'


def _status_colour(status: str) -> str:
    colours: dict[str, str] = {"RUNNING": C.GREEN, "SQUARING_OFF": C.ORANGE}
    return colours.get(status, str(C.MUTED))


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


class _StrategyRow(QWidget):
    """List entry: status dot, name, mode, one-line summary."""

    def __init__(self, name: str, mode: str, summary: str, colour: str) -> None:
        super().__init__()
        self.setObjectName("preset_item")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        top = QHBoxLayout()
        top.setSpacing(8)
        dot = QLabel("●")
        dot.setStyleSheet(f"color:{colour};")
        title = QLabel(name)
        title.setStyleSheet(f"font-family:{_MONO}; font-weight:bold;")
        mode_lbl = QLabel(mode)
        mode_lbl.setObjectName("view_key")
        top.addWidget(dot)
        top.addWidget(title, 1)
        top.addWidget(mode_lbl)
        line = QLabel(summary)
        line.setObjectName("view_key")
        line.setContentsMargins(18, 0, 0, 0)
        body = QVBoxLayout(self)
        body.setContentsMargins(10, 7, 10, 7)
        body.setSpacing(2)
        body.addLayout(top)
        body.addWidget(line)


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
    """Strategies tab (SRD-GUI-024.004–.007)."""

    count_changed = pyqtSignal(int)

    def __init__(self, demo: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._demo = demo
        self._configs: list[StrategyConfig] = load_strategies()
        # Used only for status_for(): RUNNING when an open cycle forces it.
        self._model = StrategyTableModel(self)
        demo.strategy_status_changed.connect(self._on_engine_status)

        # ── List ───────────────────────────────────────────────────────────────
        head = QLabel("STRATEGIES")
        head.setObjectName("view_head")
        add_btn = QPushButton("Add")
        set_icon(add_btn, "plus", "add")
        add_btn.clicked.connect(self._on_add)
        list_head = QHBoxLayout()
        list_head.setContentsMargins(12, 8, 8, 8)
        list_head.addWidget(head)
        list_head.addStretch(1)
        list_head.addWidget(add_btn)

        self.list = QListWidget()
        self.list.setObjectName("preset_list")
        self.list.currentRowChanged.connect(self._show_detail)

        left = QWidget()
        left.setFixedWidth(260)
        left_box = QVBoxLayout(left)
        left_box.setContentsMargins(0, 0, 0, 0)
        left_box.setSpacing(0)
        left_box.addLayout(list_head)
        left_box.addWidget(self.list, 1)
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
        self.edit_btn.clicked.connect(lambda: self._on_edit(self.list.currentRow()))
        self.copy_btn.clicked.connect(lambda: self._on_duplicate(self.list.currentRow()))
        self.reset_btn.clicked.connect(lambda: self._on_reset(self.list.currentRow()))
        self.run_btn.clicked.connect(lambda: self._on_run(self.list.currentRow()))
        self.delete_btn.clicked.connect(lambda: self._on_delete(self.list.currentRow()))

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
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.detail)

        self.empty_lbl = QLabel("No strategies yet — click Add to create one.")
        self.empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_lbl.setStyleSheet(f"color:{C.MUTED}; padding:24px;")

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(left)
        root.addWidget(sep)
        root.addWidget(scroll, 1)
        root.addWidget(self.empty_lbl, 1)
        self._scroll = scroll

        self._refresh_table()

    # ── Data helpers ──────────────────────────────────────────────────────────

    def _status(self, cfg: StrategyConfig) -> str:
        return self._model.status_for(cfg)

    def _summary_line(self, cfg: StrategyConfig) -> str:
        open_syms = self._demo.get_open_symbols_for_strategy(cfg.name)
        state = self._status(cfg)
        tail = (f"{len(open_syms)} open" if open_syms
                else "stopped" if state == "STOPPED" else "waiting")
        side = "Short" if cfg.direction == "SHORT" else "Long"
        return f"{side} · {_cell_text(cfg, COL_SCOPE)} · {_cell_text(cfg, COL_CAPITAL)} · {tail}"

    def _refresh_table(self, select: str | None = None) -> None:
        """Reload list rows; keep (or move to) the selected strategy."""
        running_override = self._demo.get_strategies_with_open_cycles()
        self._model.load(self._configs, running_override=running_override)
        current = select or self._current_name()
        self.list.blockSignals(True)
        self.list.clear()
        for cfg in self._configs:
            item = QListWidgetItem(self.list)
            row = _StrategyRow(cfg.name, cfg.mode.capitalize(), self._summary_line(cfg),
                               _status_colour(self._status(cfg)))
            item.setSizeHint(QSize(0, row.sizeHint().height()))
            self.list.setItemWidget(item, row)
        self.list.blockSignals(False)
        names = [c.name for c in self._configs]
        self.list.setCurrentRow(names.index(current) if current in names else 0)
        has_rows = bool(self._configs)
        self._scroll.setVisible(has_rows)
        self.empty_lbl.setVisible(not has_rows)
        self._show_detail(self.list.currentRow())
        self.count_changed.emit(len(self._configs))

    def _current_name(self) -> str | None:
        row = self.list.currentRow()
        return self._configs[row].name if 0 <= row < len(self._configs) else None

    # ── Detail ────────────────────────────────────────────────────────────────

    def _show_detail(self, row: int) -> None:
        if not 0 <= row < len(self._configs):
            self.pnl_card.set_provider(None)
            return
        cfg = self._configs[row]
        status = self._status(cfg)
        colour = _status_colour(status)
        self.title_lbl.setText(cfg.name)
        self.status_lbl.setText(status.replace("_", " "))
        self.status_lbl.setStyleSheet(
            f"color:{colour}; border:1px solid {colour}; border-radius:8px;"
            f" padding:1px 8px; font-size:7.5pt; font-weight:bold;"
        )
        self.since_lbl.setText(f"{cfg.mode.capitalize()} · since {_date(cfg.start_date)}")
        live = status in _LIVE
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
        ret = QMessageBox.question(
            self,
            "Delete Strategy",
            f"Delete strategy '{cfg.name}'?\n\nIts closed trades stay in the database.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ret == QMessageBox.StandardButton.Yes:
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
        cfg = self._configs[src_row]
        repo = getattr(self._demo, "rex_counters", None)
        if repo is None:
            QMessageBox.warning(
                self,
                "Reset unavailable",
                "Rex counter repository is not initialized — restart the app and try again.",
            )
            return
        ret = QMessageBox.question(
            self,
            "Reset Strategy",
            f"Reset rex counters for '{cfg.name}'?\n\n"
            "This clears the per-stock re-entry budget so the strategy can take fresh entries.\n"
            "Open positions are NOT affected.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        try:
            deleted = repo.reset(cfg.name)
        except Exception as exc:
            QMessageBox.critical(self, "Reset failed", f"Could not reset counters:\n{exc}")
            return
        QMessageBox.information(
            self,
            "Reset complete",
            f"Cleared {deleted} rex counter row(s) for '{cfg.name}'.",
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
        cfg = self._configs[src_row]
        # Effective state (badge source) so a Stop always performs a stop,
        # even when RUNNING is forced by an open cycle.
        current = self._status(cfg)

        if current == "STOPPED":
            new_state = "RUNNING"
        elif current == "SQUARING_OFF":
            if self._demo.get_open_symbols_for_strategy(cfg.name):
                return
            new_state = "STOPPED"
        else:
            open_syms = self._demo.get_open_symbols_for_strategy(cfg.name)
            new_state = "SQUARING_OFF" if open_syms else "STOPPED"

        cfg.run_state = new_state
        save_strategies(self._configs)
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
