"""
Module: MD-GUI-006 — settings_panel.py
FO-GUI-006 Settings Panel: sub-tabs — Users, System, Universe, Database.
"""
from __future__ import annotations

import datetime
import json

from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

from us_swing.gui.app_service import AppService
from us_swing.data.models import RiskConfig, UserProfile
from us_swing.gui.theme import C, active_palette, colors


# ── User dialog ───────────────────────────────────────────────────────────────

class _UserDialog(QDialog):
    """Create or edit a UserProfile."""

    def __init__(self, user: UserProfile | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit User" if user else "Create User")
        self.setMinimumWidth(380)
        self._user = user

        form = QFormLayout()
        form.setSpacing(10)

        self._username   = QLineEdit(user.username   if user else "")
        self._display    = QLineEdit(user.display_name if user else "")
        self._ibkr_id    = QSpinBox()
        self._ibkr_id.setRange(1, 99999)
        self._ibkr_id.setValue(user.ibkr_client_id if user else 100)
        self._mode       = QComboBox()
        self._mode.addItems(["paper"])
        if user:
            self._mode.setCurrentText(user.mode if user.mode == "paper" else "paper")

        form.addRow("Username:",         self._username)
        form.addRow("Display Name:",     self._display)
        form.addRow("IBKR Client ID:",   self._ibkr_id)
        form.addRow("Mode:",             self._mode)

        # ── Risk Settings section ─────────────────────────────────────────────
        risk_box = QGroupBox("Risk Settings")
        risk_form = QFormLayout(risk_box)
        risk_form.setSpacing(8)

        rc = user.risk_config if user else RiskConfig()
        self._risk       = QDoubleSpinBox()
        self._risk.setRange(0.1, 10.0)
        self._risk.setDecimals(1)
        self._risk.setSuffix(" %")
        self._risk.setValue(rc.risk_per_trade_pct)
        self._max_pos    = QDoubleSpinBox()
        self._max_pos.setRange(1_000.0, 500_000.0)
        self._max_pos.setDecimals(0)
        self._max_pos.setPrefix("$ ")
        self._max_pos.setSingleStep(1_000)
        self._max_pos.setValue(rc.max_position_value)
        self._max_cap    = QDoubleSpinBox()
        self._max_cap.setRange(100.0, 1_000_000.0)
        self._max_cap.setDecimals(0)
        self._max_cap.setPrefix("$ ")
        self._max_cap.setSingleStep(500)
        self._max_cap.setValue(rc.max_capital_value)
        self._max_loss   = QDoubleSpinBox()
        self._max_loss.setRange(0.5, 10.0)
        self._max_loss.setDecimals(1)
        self._max_loss.setSuffix(" %")
        self._max_loss.setValue(rc.max_daily_loss_pct)
        self._order_type = QComboBox()
        self._order_type.addItems(["MKT", "LMT", "MOO", "LOO"])
        if user:
            self._order_type.setCurrentText(rc.default_order_type)
        self._confirm    = QCheckBox("Require order confirmation")
        self._confirm.setChecked(rc.confirm_orders if user else True)

        risk_form.addRow("Risk per trade:",   self._risk)
        risk_form.addRow("Max position:",     self._max_pos)
        risk_form.addRow("Max capital:",      self._max_cap)
        risk_form.addRow("Max daily loss:",   self._max_loss)
        risk_form.addRow("Default order:",    self._order_type)
        risk_form.addRow("",                  self._confirm)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(risk_box)
        layout.addWidget(btns)

    def get_profile(self) -> UserProfile:
        username = self._username.text().strip() or "unnamed"
        return UserProfile(
            user_id         = self._user.user_id if self._user else -1,
            username        = username,
            display_name    = self._display.text().strip() or username,
            ibkr_client_id  = self._ibkr_id.value(),
            mode            = self._mode.currentText(),
            risk_config     = RiskConfig(
                risk_per_trade_pct = self._risk.value(),
                max_position_value = self._max_pos.value(),
                max_capital_value  = self._max_cap.value(),
                max_daily_loss_pct = self._max_loss.value(),
                default_order_type = self._order_type.currentText(),
                confirm_orders     = self._confirm.isChecked(),
            ),
            strategy_config = {},
            screener_config = {},
        )


# ── Users sub-tab ─────────────────────────────────────────────────────────────

class _UsersTab(QWidget):
    def __init__(self, demo: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._demo = demo

        self._table = QTableWidget(0, 11)
        self._table.setHorizontalHeaderLabels([
            "ID", "Username", "Display Name", "IBKR ID", "Mode",
            "Risk %", "Max Capital $", "Max Position", "Max Daily Loss", "Default Order", "Order Confirm",
        ])
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hdr.setStretchLastSection(True)
        self._table.setColumnWidth(0, 40)   # ID
        self._table.setColumnWidth(3, 70)   # IBKR ID
        self._table.setColumnWidth(4, 60)   # Mode
        self._table.setColumnWidth(5, 65)   # Risk %
        self._table.setColumnWidth(6, 100)  # Max Capital $
        self._table.setColumnWidth(7, 110)  # Max Position
        self._table.setColumnWidth(8, 105)  # Max Daily Loss
        self._table.setColumnWidth(9, 100)  # Default Order
        self._table.setColumnWidth(10, 105) # Order Confirm

        self._new_btn  = QPushButton("＋  New User")
        self._edit_btn = QPushButton("✎  Edit")
        self._del_btn  = QPushButton("✕  Delete")
        self._del_btn.setObjectName("danger_btn")
        self._edit_btn.setEnabled(False)
        self._del_btn.setEnabled(False)
        self._table.selectionModel().selectionChanged.connect(self._on_sel)
        self._new_btn.clicked.connect(self._on_new)
        self._edit_btn.clicked.connect(self._on_edit)
        self._del_btn.clicked.connect(self._on_delete)
        self._demo.users_changed.connect(self._refresh)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self._new_btn)
        btn_row.addWidget(self._edit_btn)
        btn_row.addWidget(self._del_btn)
        btn_row.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(self._table, 1)
        layout.addLayout(btn_row)

        self._refresh()

    def _refresh(self) -> None:
        users = self._demo.get_users()
        self._table.setRowCount(len(users))
        for r, u in enumerate(users):
            rc = u.risk_config
            items = [
                str(u.user_id),
                u.username,
                u.display_name,
                str(u.ibkr_client_id),
                u.mode,
                f"{rc.risk_per_trade_pct:.1f}%",
                f"${rc.max_capital_value:,.0f}",
                f"${rc.max_position_value:,.0f}",
                f"{rc.max_daily_loss_pct:.1f}%",
                rc.default_order_type,
                "Yes" if rc.confirm_orders else "No",
            ]
            for c, txt in enumerate(items):
                item = QTableWidgetItem(txt)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._table.setItem(r, c, item)

    def _on_sel(self) -> None:
        has = bool(self._table.selectionModel().selectedRows())
        self._edit_btn.setEnabled(has)
        self._del_btn.setEnabled(has)

    def _get_selected_user(self) -> UserProfile | None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return None
        users = self._demo.get_users()
        idx   = rows[0].row()
        return users[idx] if idx < len(users) else None

    def _on_new(self) -> None:
        dlg = _UserDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._demo.add_user(dlg.get_profile())

    def _on_edit(self) -> None:
        user = self._get_selected_user()
        if user is None:
            return
        dlg = _UserDialog(user, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._demo.update_user(dlg.get_profile())

    def _on_delete(self) -> None:
        user = self._get_selected_user()
        if user is None:
            return
        from PyQt6.QtWidgets import QMessageBox
        ret = QMessageBox.question(
            self, "Delete User",
            f"Delete user <b>{user.username}</b>?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ret == QMessageBox.StandardButton.Yes:
            err = self._demo.delete_user(user.user_id)
            if err:
                QMessageBox.warning(self, "Cannot Delete", err)


# ── Risk sub-tab ──────────────────────────────────────────────────────────────

class _RiskTab(QWidget):
    def __init__(self, demo: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        user = demo.get_active_user()
        form = QFormLayout()
        form.setSpacing(12)

        def _spin(lo, hi, val, dec=1, suffix=""):
            s = QDoubleSpinBox()
            s.setRange(lo, hi)
            s.setDecimals(dec)
            s.setValue(val)
            if suffix:
                s.setSuffix(suffix)
            return s

        rc = user.risk_config
        self._risk      = _spin(0.1, 10.0, rc.risk_per_trade_pct, suffix=" %")
        self._max_pos   = _spin(1000, 500_000, rc.max_position_value, dec=0, suffix=" $")
        self._max_cap   = _spin(100, 1_000_000, rc.max_capital_value, dec=0, suffix=" $")
        self._max_loss  = _spin(0.5, 10.0, rc.max_daily_loss_pct, suffix=" %")
        self._ord_type  = QComboBox()
        self._ord_type.addItems(["MKT", "LMT", "MOO", "LOO"])
        self._ord_type.setCurrentText(rc.default_order_type)
        self._confirm   = QCheckBox("Require confirmation dialog before submitting order")
        self._confirm.setChecked(rc.confirm_orders)

        form.addRow("Risk per trade:",         self._risk)
        form.addRow("Max single position:",    self._max_pos)
        form.addRow("Max capital:",            self._max_cap)
        form.addRow("Max daily loss:",         self._max_loss)
        form.addRow("Default order type:",     self._ord_type)
        form.addRow("",                        self._confirm)

        save_btn = QPushButton("Save Risk Settings")
        save_btn.setObjectName("run_btn")
        save_btn.setFixedWidth(200)
        save_btn.clicked.connect(self._on_save)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.addLayout(form)
        layout.addStretch()
        layout.addWidget(save_btn)

        self._note = QLabel("")
        self._note.setStyleSheet(f"color: {C.GREEN}; font-size: 9pt;")
        layout.addWidget(self._note)

    def _on_save(self) -> None:
        self._note.setText("✔  Settings saved (demo mode — will persist to real backend)")


# ── System sub-tab ────────────────────────────────────────────────────────────

class _SystemTab(QWidget):
    theme_changed = pyqtSignal(str)

    def __init__(self, demo: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._demo = demo
        cfg = demo.get_system_config()

        # ── Config form ────────────────────────────────────────────────────────
        form = QFormLayout()
        form.setSpacing(10)
        form.setContentsMargins(20, 20, 20, 20)

        self._host      = QLineEdit(cfg.ibkr_host)
        self._port      = QSpinBox()
        self._port.setRange(1, 65535)
        self._port.setValue(cfg.ibkr_port)
        self._log_level = QComboBox()
        self._log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self._log_level.setCurrentText(cfg.log_level)
        self._sched_en  = QCheckBox()
        self._sched_en.setChecked(cfg.scheduler_enabled)
        self._open_t    = QLineEdit(cfg.market_open)
        self._close_t   = QLineEdit(cfg.market_close)
        self._mkt_tz    = QComboBox()
        self._mkt_tz.addItems([
            "US/Eastern",
            "US/Central",
            "US/Mountain",
            "US/Pacific",
            "UTC",
            "Asia/Kolkata",
        ])
        self._mkt_tz.setCurrentText(cfg.market_timezone)

        self._tick_id = QSpinBox()
        self._tick_id.setRange(1, 999)
        self._tick_id.setValue(cfg.ibkr_tick_client_id)
        self._tick_id.setToolTip(
            "Dedicated IBKR client ID for live tick streaming (reqMktData). "
            "Must be unique — not shared with other connections."
        )

        form.addRow("IBKR TWS Host:",          self._host)
        form.addRow("IBKR TWS Port:",          self._port)
        form.addRow("Tick Data Client ID:",    self._tick_id)
        form.addRow("Log level:",              self._log_level)
        form.addRow("Market open time:",       self._open_t)
        form.addRow("Market close time:",      self._close_t)
        form.addRow("Market timezone:",        self._mkt_tz)
        form.addRow("Enable daily scheduler:", self._sched_en)

        save_btn = QPushButton("💾  Save Settings")
        save_btn.setObjectName("run_btn")
        save_btn.setFixedWidth(140)
        save_btn.clicked.connect(self._on_save)

        self._sched_btn = QPushButton("📅  Add Scheduler")
        self._sched_btn.setFixedWidth(160)
        self._sched_btn.clicked.connect(self._on_scheduler)
        self._refresh_sched_btn_label()

        self._save_note = QLabel("")
        self._save_note.setStyleSheet(f"color: {C.GREEN}; font-size: 9pt;")

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(20, 12, 20, 0)
        btn_row.addWidget(self._save_note)
        btn_row.addStretch()
        btn_row.addWidget(self._sched_btn)
        btn_row.addWidget(save_btn)

        # ── Theme group ────────────────────────────────────────────────────────
        from us_swing.gui import theme as _theme
        theme_box = QGroupBox("Theme")
        theme_row = QHBoxLayout(theme_box)
        theme_row.setContentsMargins(12, 8, 12, 8)
        theme_row.setSpacing(8)

        self._btn_mocha  = QPushButton("Mocha (Default)")
        self._btn_mocha.setCheckable(True)
        self._btn_mocha.setFixedWidth(140)
        self._btn_vscode = QPushButton("VS Code Dark")
        self._btn_vscode.setCheckable(True)
        self._btn_vscode.setFixedWidth(140)

        current_theme = _theme.load_theme_id()
        self._btn_mocha.setChecked(current_theme == "mocha")
        self._btn_vscode.setChecked(current_theme == "vscode")

        self._btn_mocha.clicked.connect(lambda: self._on_theme("mocha"))
        self._btn_vscode.clicked.connect(lambda: self._on_theme("vscode"))

        theme_row.addWidget(self._btn_mocha)
        theme_row.addWidget(self._btn_vscode)
        theme_row.addStretch()

        theme_wrapper = QHBoxLayout()
        theme_wrapper.setContentsMargins(20, 12, 20, 0)
        theme_wrapper.addWidget(theme_box)

        # ── Diagnostics group ────────────────────────────────────────────────────
        diag_box = QGroupBox("Diagnostics")
        diag_row = QHBoxLayout(diag_box)
        diag_row.setContentsMargins(12, 8, 12, 8)
        diag_row.setSpacing(8)

        self._candle_db_btn = QPushButton("Candle DB")
        self._candle_db_btn.setFixedWidth(120)
        self._candle_db_btn.clicked.connect(self._on_candle_db)

        self._cb_toggle = QPushButton()
        self._cb_toggle.setObjectName("danger_btn")
        self._cb_toggle.setFixedWidth(200)
        self._cb_toggle.clicked.connect(self._on_toggle_cb)
        self._refresh_cb_label()
        self._demo.circuit_breaker_changed.connect(lambda _a: self._refresh_cb_label())

        diag_row.addWidget(self._candle_db_btn)
        diag_row.addWidget(self._cb_toggle)
        diag_row.addStretch()

        diag_wrapper = QHBoxLayout()
        diag_wrapper.setContentsMargins(20, 12, 20, 0)
        diag_wrapper.addWidget(diag_box)

        # ── Updates group ────────────────────────────────────────────────────────
        update_box = QGroupBox("Updates")
        update_row = QHBoxLayout(update_box)
        update_row.setContentsMargins(12, 8, 12, 8)
        update_row.setSpacing(8)

        self._update_btn = QPushButton("Check for Updates")
        self._update_btn.setFixedWidth(160)
        self._update_btn.clicked.connect(self._on_check_updates)

        self._update_note = QLabel("")
        self._update_note.setStyleSheet(f"color: {C.GREEN}; font-size: 9pt;")
        self._update_worker: object | None = None

        update_row.addWidget(self._update_btn)
        update_row.addWidget(self._update_note)
        update_row.addStretch()

        update_wrapper = QHBoxLayout()
        update_wrapper.setContentsMargins(20, 12, 20, 0)
        update_wrapper.addWidget(update_box)

        # ── Main layout ────────────────────────────────────────────────────────
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(form)
        layout.addLayout(btn_row)
        layout.addLayout(theme_wrapper)
        layout.addLayout(diag_wrapper)
        layout.addLayout(update_wrapper)
        layout.addStretch()

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _refresh_cb_label(self) -> None:
        active = self._demo.circuit_breaker_active
        self._cb_toggle.setText("Reset Circuit Breaker" if active else "Trip Circuit Breaker")

    def _on_toggle_cb(self) -> None:
        self._demo.set_circuit_breaker(not self._demo.circuit_breaker_active)

    def _on_candle_db(self) -> None:
        from us_swing.gui.execution_panel import _CandleDbDiagDialog
        _CandleDbDiagDialog(self._demo, self).exec()

    def _on_check_updates(self) -> None:
        from update_dialog import _CheckWorker  # type: ignore[import]

        self._update_btn.setEnabled(False)
        self._update_note.setStyleSheet(f"color: {C.GREEN}; font-size: 9pt;")
        self._update_note.setText("Checking for updates…")
        worker = _CheckWorker()
        worker.found.connect(self._on_update_found)
        worker.up_to_date.connect(self._on_update_up_to_date)
        worker.failed.connect(self._on_update_failed)
        worker.start()
        self._update_worker = worker

    def _on_update_found(self, info: object) -> None:
        from update_dialog import _UpdateDialog  # type: ignore[import]
        from updater_stub import UpdateInfo  # type: ignore[import]

        self._update_btn.setEnabled(True)
        self._update_note.setText("")
        if isinstance(info, UpdateInfo):
            _UpdateDialog(info).exec()

    def _on_update_up_to_date(self) -> None:
        self._update_btn.setEnabled(True)
        self._update_note.setText("You're on the latest version")

    def _on_update_failed(self, msg: str) -> None:
        self._update_btn.setEnabled(True)
        self._update_note.setStyleSheet(f"color: {C.RED}; font-size: 9pt;")
        self._update_note.setText(f"Could not check for updates — {msg}")

    def _refresh_sched_btn_label(self) -> None:
        from us_swing.gui.scheduler_store import load_scheduler_config, load_usswing_config
        has_task = bool(load_scheduler_config() or load_usswing_config())
        self._sched_btn.setText("📅  Edit Scheduler" if has_task else "📅  Add Scheduler")

    def _on_scheduler(self) -> None:
        from us_swing.gui.scheduler_dialog import SchedulerDialog
        dlg = SchedulerDialog(parent=self)
        dlg.exec()
        self._refresh_sched_btn_label()

    def _on_save(self) -> None:
        from us_swing.gui.system_store import SystemConfig
        cfg = SystemConfig(
            ibkr_host             = self._host.text().strip() or "127.0.0.1",
            ibkr_port             = self._port.value(),
            ibkr_tick_client_id   = self._tick_id.value(),
            log_level             = self._log_level.currentText(),
            scheduler_enabled     = self._sched_en.isChecked(),
            market_open           = self._open_t.text().strip(),
            market_close          = self._close_t.text().strip(),
            market_timezone       = self._mkt_tz.currentText(),
        )
        self._demo.save_system_config(cfg)
        self._save_note.setText("✔  Settings saved")

    def _on_theme(self, theme_id: str) -> None:
        from us_swing.gui import theme as _theme
        _theme.save_theme_id(theme_id)
        _theme.apply_theme(theme_id)
        self._btn_mocha.setChecked(theme_id == "mocha")
        self._btn_vscode.setChecked(theme_id == "vscode")
        self.theme_changed.emit(theme_id)


# ── Universe Tab ─────────────────────────────────────────────────────────────

_UNIVERSE_HTML = """\
<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:{bg};color:{fg};font-family:'Segoe UI',Tahoma,sans-serif;font-size:12px;overflow-x:auto}}
table{{border-collapse:collapse;table-layout:fixed;width:max-content;min-width:100%}}
thead{{position:sticky;top:0;z-index:10}}
thead th{{
  background:{hdr_bg};color:{hdr_fg};
  padding:6px 10px;text-align:center;
  cursor:pointer;user-select:none;
  border-bottom:2px solid {border};border-right:1px solid {border};
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  position:relative;
}}
thead th:last-child{{border-right:none}}
thead th:hover{{background:{hdr_hover}}}
thead th.asc::after{{content:" \u25b2";font-size:10px}}
thead th.desc::after{{content:" \u25bc";font-size:10px}}
/* resize handle */
.resizer{{
  position:absolute;right:0;top:0;bottom:0;width:5px;
  cursor:col-resize;background:transparent;z-index:20;
}}
.resizer:hover,.resizer.resizing{{background:{accent};opacity:.5}}
/* drag-over indicator */
th.drag-over{{outline:2px dashed {accent};outline-offset:-2px}}
tbody tr:nth-child(odd){{background:{row_odd}}}
tbody tr:nth-child(even){{background:{row_even}}}
tbody tr:hover{{background:{row_hover}}}
tbody tr.stale{{background:#322a14}}
tbody tr.missing{{background:#321414}}
tbody tr.stale:hover,tbody tr.missing:hover{{background:{row_hover}}}
td{{padding:4px 10px;text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
td.sym{{font-weight:600;color:{sym_fg};text-align:center}}
td.cap{{font-variant-numeric:tabular-nums}}
td.name{{white-space:normal;text-align:center}}
</style></head><body>
<table id="tbl"><thead><tr id="hdr"></tr></thead>
<tbody id="tb"></tbody></table>
<script>
const D={data};
/* column definitions: [label, dataIndex, defaultWidth] */
let COLS=[
  ['#',            -1, 50],
  ['Symbol',        1, 80],
  ['IBKR',          2, 80],
  ['Sector',        3,150],
  ['Mkt Cap',       4,100],
  ['Name',          5,220],
  ['DB',            7, 50],
  ['Last Updated',  6,120],
];
let colOrder=[0,1,2,3,4,5,6,7];   /* indices into COLS */
let sc=4, sa=false, ft='';

function fc(b){{if(b===null)return'\u2014';if(b>=1000)return'$'+(b/1000).toFixed(2)+'T';if(b>=1)return'$'+b.toFixed(1)+'B';return'$'+(b*1000).toFixed(0)+'M';}}
function applyFilters(text,_mn,_mx){{ft=text.toLowerCase();render();}}
function S(ci){{
  const di=COLS[colOrder[ci]][1];
  if(sc===di){{sa=!sa}}else{{sc=di;sa=(di!==-1&&di!==4)}};
  render();
}}

/* ── Build header ── */
function buildHeader(){{
  const hdr=document.getElementById('hdr');
  hdr.innerHTML='';
  colOrder.forEach((ci,pos)=>{{
    const [label,,w]=COLS[ci];
    const th=document.createElement('th');
    th.textContent=label;
    th.dataset.pos=pos;
    th.dataset.ci=ci;
    th.style.width=w+'px';
    th.style.minWidth='40px';
    if(COLS[ci][1]===sc)th.classList.add(sa?'asc':'desc');
    th.onclick=()=>S(pos);

    /* resize handle */
    const rz=document.createElement('span');
    rz.className='resizer';
    rz.addEventListener('mousedown',e=>startResize(e,th,ci));
    th.appendChild(rz);

    /* drag-to-reorder */
    th.draggable=true;
    th.addEventListener('dragstart',e=>{{e.dataTransfer.setData('pos',pos);th.style.opacity='.4';}});
    th.addEventListener('dragend',  ()=>{{th.style.opacity='1';document.querySelectorAll('th').forEach(h=>h.classList.remove('drag-over'));}});
    th.addEventListener('dragover', e=>{{e.preventDefault();th.classList.add('drag-over');}});
    th.addEventListener('dragleave',()=>th.classList.remove('drag-over'));
    th.addEventListener('drop', e=>{{
      e.preventDefault();
      th.classList.remove('drag-over');
      const from=parseInt(e.dataTransfer.getData('pos'));
      const to=parseInt(th.dataset.pos);
      if(from===to)return;
      const tmp=colOrder[from]; colOrder[from]=colOrder[to]; colOrder[to]=tmp;
      buildHeader(); render(false);
    }});
    hdr.appendChild(th);
  }});
}}

/* ── Column resize ── */
let _rzTh=null,_rzStart=0,_rzW=0;
function startResize(e,th,ci){{
  e.stopPropagation(); e.preventDefault();
  _rzTh=th; _rzStart=e.clientX; _rzW=th.offsetWidth;
  const rz=th.querySelector('.resizer'); rz.classList.add('resizing');
  document.addEventListener('mousemove',doResize);
  document.addEventListener('mouseup',endResize);
}}
function doResize(e){{
  if(!_rzTh)return;
  const nw=Math.max(40,_rzW+(e.clientX-_rzStart));
  _rzTh.style.width=nw+'px';
  const ci=parseInt(_rzTh.dataset.ci);
  COLS[ci][2]=nw;
  /* sync td widths */
  const pos=parseInt(_rzTh.dataset.pos);
  document.querySelectorAll('#tb tr').forEach(tr=>{{
    if(tr.cells[pos]){{tr.cells[pos].style.width=nw+'px';tr.cells[pos].style.maxWidth=nw+'px';}};
  }});
}}
function endResize(){{
  if(_rzTh){{_rzTh.querySelector('.resizer').classList.remove('resizing');_rzTh=null;}}
  document.removeEventListener('mousemove',doResize);
  document.removeEventListener('mouseup',endResize);
}}

/* ── Render tbody ── */
function render(resort=true){{
  let v=D.filter(r=>{{
    if(!ft)return true;
    return (r[1]+' '+r[5]+' '+r[3]).toLowerCase().includes(ft);
  }});
  if(resort){{
    v.sort((a,b)=>{{
      let av=(sc===-1)?0:a[sc], bv=(sc===-1)?0:b[sc];
      if(av===null)av=sa?Infinity:-Infinity;
      if(bv===null)bv=sa?Infinity:-Infinity;
      return typeof av==='string'?(sa?av.localeCompare(bv):bv.localeCompare(av)):(sa?av-bv:bv-av);
    }});
  }}
  document.querySelectorAll('thead th').forEach((h,i)=>{{
    h.classList.remove('asc','desc');
    const ci=parseInt(h.dataset.ci);
    if(COLS[ci][1]===sc)h.classList.add(sa?'asc':'desc');
  }});
  const tb=document.getElementById('tb');
  tb.innerHTML=v.map((r,i)=>{{
    const cells=colOrder.map((ci,pos)=>{{
      const [,di,w]=COLS[ci];
      const style=`style="width:${{w}}px;max-width:${{w}}px"`;
      if(di===-1) return `<td ${{style}}>${{i+1}}</td>`;
      if(ci===1)  return `<td class="sym" ${{style}}>${{r[1]}}</td>`;
      if(ci===4)  return `<td class="cap" ${{style}}>${{fc(r[4])}}</td>`;
      if(ci===5)  return `<td class="name" ${{style}}>${{r[5]}}</td>`;
      if(ci===6){{const st=r[7];const cl=st==='current'?'{st_ok}':st==='stale'?'{st_warn}':'{st_err}';const ic=st==='current'?'✔':st==='stale'?'⚠':'✘';return `<td style="width:${{w}}px;max-width:${{w}}px;color:${{cl}};font-size:13px;text-align:center">${{ic}}</td>`;}}
      if(ci===7){{const dt=r[6];const st=r[7];const cl=st==='current'?'{st_ok}':st==='stale'?'{st_warn}':'{st_err}';return `<td style="width:${{w}}px;max-width:${{w}}px;color:${{cl}};text-align:center">${{dt||'—'}}</td>`;}}
      return `<td ${{style}}>${{r[di]}}</td>`;
    }}).join('');
    const rc=r[7]==='current'?'':r[7]==='stale'?' class="stale"':' class="missing"';
    return `<tr${{rc}}>${{cells}}</tr>`;
  }}).join('');
}}

buildHeader();
render();
</script></body></html>
"""


def _build_universe_html(
    records: list,
    coverage: "dict[str, str | None] | None" = None,
    last_trading_day: str | None = None,
) -> str:
    """Serialize records to an HTML page with all data embedded as JSON.

    Args:
        records: List of Sp500Record from AppService.
        coverage: {symbol: last_1d_candle_date | None} from candles.db.
            ``None`` means the DB has not been queried yet.
        last_trading_day: "YYYY-MM-DD"; rows with older dates are marked stale.
    """
    cov = coverage or {}

    def _sym_status(sym: str) -> "tuple[str | None, str]":
        last_date = cov.get(sym)
        if last_date is None:
            return None, "missing"
        if last_trading_day and last_date < last_trading_day:
            return last_date, "stale"
        return last_date, "current"

    data = [
        [i + 1, r.symbol, r.ibkr_symbol, r.sector,
         round(r.market_cap / 1e9, 4) if r.market_cap else None,
         r.name,
         *_sym_status(r.symbol)]
        for i, r in enumerate(records)
    ]
    ct = active_palette()
    return _UNIVERSE_HTML.format(
        data=json.dumps(data),
        bg=ct.BG,
        fg=ct.TEXT,
        hdr_bg=ct.SURFACE,
        hdr_fg=ct.TEXT,
        hdr_hover=ct.OVERLAY,
        border=ct.OVERLAY2,
        accent=ct.BLUE,
        row_odd=ct.SURFACE,
        row_even=ct.BG,
        row_hover=ct.OVERLAY,
        sym_fg=ct.GREEN,
        st_ok=ct.GREEN,
        st_warn=ct.YELLOW,
        st_err=ct.RED,
    )


class _UniverseTab(QWidget):
    """S&P 500 universe viewer — HTML table rendered in QWebEngineView.

    Sorting (click any column header) and filtering (text + cap range)
    are handled entirely in JavaScript inside the web page; Python
    controls simply call ``runJavaScript("applyFilters(...)")``.  """

    def __init__(self, svc: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._svc = svc

        # ── Meta bar ──────────────────────────────────────────────────────────
        self._meta_label = QLabel("Loading…")
        self._meta_label.setStyleSheet(f"color: {active_palette().SUBTEXT}; font-size: 9pt;")

        refresh_btn = QPushButton("🔄  Refresh")
        refresh_btn.setObjectName("run_btn")
        refresh_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        refresh_btn.clicked.connect(self._on_refresh)

        top = QHBoxLayout()
        top.addWidget(self._meta_label)
        top.addStretch()
        top.addWidget(refresh_btn)

        # ── Search bar ────────────────────────────────────────────────────────
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Symbol / Name / Sector…")
        self._search.textChanged.connect(self._push_filters)

        # ── Web view ──────────────────────────────────────────────────────────
        self._web = QWebEngineView()
        self._web.setHtml(f"<body style='background:{active_palette().BG}'></body>")

        # ── Layout ────────────────────────────────────────────────────────────
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addLayout(top)
        layout.addWidget(self._search)
        layout.addWidget(self._web)

        self._load_from_cache()
        svc.sp500_updated.connect(self._load_from_cache)
        svc.candle_db_status_changed.connect(lambda _: self._load_from_cache())

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _load_from_cache(self) -> None:
        records  = self._svc.get_sp500_universe()
        coverage = self._svc.get_candle_symbol_coverage()
        ltd      = self._svc.get_last_trading_day()
        self._web.setHtml(_build_universe_html(records, coverage, ltd))
        meta  = self._svc.get_sp500_meta()
        stale = " (stale)" if meta.is_stale() else ""
        self._meta_label.setText(
            f"{len(records)} constituents · last fetched: {meta.age_str()}{stale}"
        )

    def _push_filters(self) -> None:
        text = json.dumps(self._search.text())
        self._web.page().runJavaScript(f"applyFilters({text}, 0, 0);")

    def _on_refresh(self) -> None:
        self._meta_label.setText("Refreshing from Wikipedia…")
        self._svc.refresh_sp500_universe()

    def refresh_theme(self, _theme_id: str = "") -> None:
        self._meta_label.setStyleSheet(f"color: {active_palette().SUBTEXT}; font-size: 9pt;")
        self._load_from_cache()


# ── Database tab ─────────────────────────────────────────────────────────────

class _DatabaseTab(QWidget):
    """SRD-GUI-006.011 — Candle database lifecycle management.

    Displays current DB status (EMPTY / PARTIAL / CURRENT), data coverage
    stats, and provides a build/delta-fill button backed by
    AppService candle download workers.
    """

    def __init__(self, svc: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._svc = svc
        self._db_info = None        # last CandleDbInfo received
        self._downloading = False

        # ── Status group ──────────────────────────────────────────────────────
        status_group = QGroupBox("Database Status")
        sg_layout = QVBoxLayout(status_group)
        sg_layout.setSpacing(6)

        self._badge = QLabel("Checking…")
        self._badge.setFixedHeight(24)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setObjectName("db_status_badge")

        self._last_trading_day_lbl = QLabel("Last trading day: —")
        self._last_trading_day_lbl.setStyleSheet(f"color: {C.SUBTEXT}; font-size: 9pt;")

        self._data_through_lbl = QLabel("Data through: —")
        self._data_through_lbl.setStyleSheet(f"color: {C.SUBTEXT}; font-size: 9pt;")

        self._coverage_lbl = QLabel("Coverage: —")
        self._coverage_lbl.setStyleSheet(f"color: {C.SUBTEXT}; font-size: 9pt;")

        self._candle_count_lbl = QLabel("Total candles: —")
        self._candle_count_lbl.setStyleSheet(f"color: {C.SUBTEXT}; font-size: 9pt;")

        self._refresh_status_btn = QPushButton("↻  Refresh Status")
        self._refresh_status_btn.setFixedWidth(160)
        self._refresh_status_btn.clicked.connect(self._on_refresh_status)

        status_row = QHBoxLayout()
        status_row.addWidget(self._refresh_status_btn)
        status_row.addStretch()

        sg_layout.addWidget(self._badge)
        sg_layout.addWidget(self._last_trading_day_lbl)
        sg_layout.addWidget(self._data_through_lbl)
        sg_layout.addWidget(self._coverage_lbl)
        sg_layout.addWidget(self._candle_count_lbl)
        sg_layout.addLayout(status_row)

        # ── Build group ───────────────────────────────────────────────────────
        build_group = QGroupBox("Build / Update Database")
        bg_layout = QVBoxLayout(build_group)
        bg_layout.setSpacing(8)

        # Start date (only shown in EMPTY mode)
        date_row = QHBoxLayout()
        date_lbl = QLabel("Start date:")
        date_lbl.setStyleSheet(f"color: {C.SUBTEXT}; font-size: 9pt;")
        self._start_date_edit = QDateEdit()
        self._start_date_edit.setCalendarPopup(True)
        self._start_date_edit.setDisplayFormat("yyyy-MM-dd")
        default_start = QDate.currentDate().addYears(-2)
        self._start_date_edit.setDate(default_start)
        self._start_date_edit.setMaximumDate(QDate.currentDate())
        date_row.addWidget(date_lbl)
        date_row.addWidget(self._start_date_edit)
        date_row.addStretch()

        self._start_date_row_widget = QWidget()
        self._start_date_row_widget.setLayout(date_row)
        self._start_date_row_widget.hide()  # shown only when EMPTY

        self._build_btn = QPushButton("↻  Checking…")
        self._build_btn.setObjectName("run_btn")
        self._build_btn.setFixedWidth(220)
        self._build_btn.setEnabled(False)
        self._build_btn.clicked.connect(self._on_build_clicked)

        bg_layout.addWidget(self._start_date_row_widget)
        bg_layout.addWidget(self._build_btn)

        # ── Progress group ────────────────────────────────────────────────────
        self._progress_group = QGroupBox("Download Progress")
        pg_layout = QVBoxLayout(self._progress_group)
        pg_layout.setSpacing(6)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFixedHeight(18)

        self._progress_label = QLabel("Starting…")
        self._progress_label.setStyleSheet(f"color: {C.SUBTEXT}; font-size: 9pt;")

        self._fail_count_lbl = QLabel("")
        self._fail_count_lbl.setStyleSheet(f"color: {C.RED}; font-size: 9pt;")
        self._fail_count_lbl.hide()

        self._cancel_btn = QPushButton("✕  Cancel")
        self._cancel_btn.setObjectName("danger_btn")
        self._cancel_btn.setFixedWidth(120)
        self._cancel_btn.clicked.connect(self._on_cancel)

        cancel_row = QHBoxLayout()
        cancel_row.addWidget(self._cancel_btn)
        cancel_row.addStretch()

        pg_layout.addWidget(self._progress_bar)
        pg_layout.addWidget(self._progress_label)
        pg_layout.addWidget(self._fail_count_lbl)
        pg_layout.addLayout(cancel_row)

        self._progress_group.hide()

        # ── Discrepancies group (SRD-GUI-006.016) ─────────────────────────────
        self._disc_group = QGroupBox("⚠  Download Discrepancies")
        self._disc_group.setStyleSheet(
            f"QGroupBox {{ color: {C.RED}; font-weight: bold; }}"
        )
        dg_layout = QVBoxLayout(self._disc_group)
        dg_layout.setSpacing(6)

        self._disc_summary_lbl = QLabel("")
        self._disc_summary_lbl.setStyleSheet(
            f"color: {C.RED}; font-size: 9pt;"
        )
        self._disc_symbols_lbl = QLabel("")
        self._disc_symbols_lbl.setStyleSheet(
            f"color: {C.SUBTEXT}; font-size: 8pt;"
        )
        self._disc_symbols_lbl.setWordWrap(True)

        self._fix_btn = QPushButton("🔧  Fix Discrepancies")
        self._fix_btn.setObjectName("run_btn")
        self._fix_btn.setFixedWidth(200)
        self._fix_btn.clicked.connect(self._on_fix_discrepancies)

        fix_row = QHBoxLayout()
        fix_row.addWidget(self._fix_btn)
        fix_row.addStretch()

        dg_layout.addWidget(self._disc_summary_lbl)
        dg_layout.addWidget(self._disc_symbols_lbl)
        dg_layout.addLayout(fix_row)

        self._disc_group.hide()
        self._disc_failed_symbols: list[str] = []

        # ── Danger Zone group ─────────────────────────────────────────────────
        danger_group = QGroupBox("⚠  Danger Zone")
        danger_group.setStyleSheet(
            f"QGroupBox {{ color: {C.RED}; font-weight: bold; border: 1px solid {C.RED};"
            f" border-radius: 4px; margin-top: 6px; padding-top: 6px; }}"
        )
        dz_layout = QVBoxLayout(danger_group)
        dz_layout.setSpacing(8)

        dz_info = QLabel(
            "Permanently deletes ALL candle data and recreates an empty database.\n"
            "Use this to start fresh. A full re-download will be required."
        )
        dz_info.setStyleSheet(f"color: {C.SUBTEXT}; font-size: 9pt;")
        dz_info.setWordWrap(True)

        self._reset_db_btn = QPushButton("🗑  Reset Database")
        self._reset_db_btn.setObjectName("danger_btn")
        self._reset_db_btn.setFixedWidth(200)
        self._reset_db_btn.clicked.connect(self._on_reset_db)

        dz_row = QHBoxLayout()
        dz_row.addWidget(self._reset_db_btn)
        dz_row.addStretch()

        dz_layout.addWidget(dz_info)
        dz_layout.addLayout(dz_row)

        # ── Main layout ───────────────────────────────────────────────────────
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)
        layout.addWidget(status_group)
        layout.addWidget(build_group)
        layout.addWidget(self._progress_group)
        layout.addWidget(self._disc_group)
        layout.addWidget(danger_group)
        layout.addStretch()

        # ── Signal wiring ─────────────────────────────────────────────────────
        svc.candle_db_status_changed.connect(self._on_status_loaded)
        svc.candle_download_progress.connect(self._on_progress)
        svc.candle_download_finished.connect(self._on_finished)
        svc.candle_download_failed.connect(self._on_failed)
        svc.candle_download_paused.connect(self._on_paused)
        svc.candle_symbol_failed.connect(self._on_symbol_failed)
        svc.candle_download_failures.connect(self._on_failures_ready)

        # Show resume button immediately if a checkpoint exists
        self._apply_checkpoint_state()

        # Trigger initial status check (deferred so the tab renders first)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(300, self._on_refresh_status)

        # Restore persisted failures from prior session (SRD-GUI-006.016)
        self._load_persisted_failures()

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_refresh_status(self) -> None:
        self._badge.setText("Checking…")
        _badge_fg = colors()["badge_text_dark"]
        self._badge.setStyleSheet(
            f"background: {C.SUBTEXT}; color: {_badge_fg}; border-radius: 4px;"
            "font-weight: bold; padding: 2px 10px;"
        )
        self._build_btn.setEnabled(False)
        self._svc.refresh_candle_db_status()

    def _on_status_loaded(self, info: object) -> None:
        from us_swing.gui.app_service import CandleDbStatus, CandleDbInfo
        if not isinstance(info, CandleDbInfo):
            return
        self._db_info = info

        # Badge
        _badge_styles = {
            CandleDbStatus.EMPTY:   (C.RED,    "EMPTY"),
            CandleDbStatus.PARTIAL: ("#f9a825", "PARTIAL"),
            CandleDbStatus.CURRENT: (C.GREEN,  "CURRENT"),
        }
        color, label = _badge_styles[info.status]
        self._badge.setText(f"  {label}  ")
        _badge_fg = colors()["badge_text_dark"]
        self._badge.setStyleSheet(
            f"background: {color}; color: {_badge_fg}; border-radius: 4px;"
            "font-weight: bold; padding: 2px 10px;"
        )

        # Labels
        self._last_trading_day_lbl.setText(
            f"Last trading day:  {info.last_trading_day}"
        )
        self._data_through_lbl.setText(
            f"Data through:  {info.last_candle_date or '—'}"
        )
        universe = info.universe_size or 0
        sym = max(info.symbols_1d, info.symbols_1w)
        self._coverage_lbl.setText(
            f"Coverage:  {sym} / {universe} symbols  ·  Daily + Weekly"
        )
        total = info.total_1d + info.total_1w
        self._candle_count_lbl.setText(
            f"Total candles:  {total:,}"
            f"  ({info.total_1d:,} daily · {info.total_1w:,} weekly)"
        )

        # Build button
        if self._downloading:
            return   # don't change button state mid-download

        if info.status == CandleDbStatus.EMPTY:
            self._build_btn.setText("⬇  Build Full Database")
            self._build_btn.setEnabled(True)
            self._build_btn.setObjectName("run_btn")
            self._start_date_row_widget.show()
        elif info.status == CandleDbStatus.PARTIAL:
            self._build_btn.setText("🔄  Fill Delta")
            self._build_btn.setEnabled(True)
            self._build_btn.setObjectName("run_btn")
            self._start_date_row_widget.hide()
        else:  # CURRENT
            self._build_btn.setText("✔  Database Current")
            self._build_btn.setEnabled(False)
            self._build_btn.setObjectName("")
            self._start_date_row_widget.hide()

        # Force QSS re-evaluation after objectName change
        self._build_btn.style().unpolish(self._build_btn)
        self._build_btn.style().polish(self._build_btn)

        # Override with resume button if checkpoint exists
        self._apply_checkpoint_state()

    def _on_build_clicked(self) -> None:
        from us_swing.gui.app_service import CandleDbStatus
        from us_swing.data.models import ConnectionStatus

        # ── IBKR connection gate (SRD-GUI-006.012) ───────────────────────────
        if self._svc.connection_status is not ConnectionStatus.CONNECTED:
            QMessageBox.warning(
                self,
                "IBKR Not Connected",
                "IBKR Gateway must be connected before downloading candle data.\n\n"
                "Use the '🟢 Connect Feed' button in the title bar to connect first.",
            )
            return

        # ── Determine mode ────────────────────────────────────────────────────
        if self._svc.has_candle_checkpoint():
            # Resume interrupted download — AppService detects checkpoint automatically
            self._svc.start_candle_download(
                start_date=datetime.date.today(), mode="full"
            )
        elif self._db_info is None or self._db_info.status == CandleDbStatus.EMPTY:
            qd = self._start_date_edit.date()
            start = datetime.date(qd.year(), qd.month(), qd.day())
            self._svc.start_candle_download(start_date=start, mode="full")
        else:
            # PARTIAL — delta fill; start_date computed internally
            self._svc.start_candle_download(
                start_date=datetime.date.today(), mode="delta"
            )
        self._set_downloading(True)

    def _on_cancel(self) -> None:
        self._svc.stop_candle_download()
        self._progress_label.setText("Cancelling…")
        self._cancel_btn.setEnabled(False)

    def _on_progress(self, symbol: str, done: int, total: int) -> None:
        if total > 0:
            pct = int(done / total * 100)
            self._progress_bar.setValue(pct)
        self._progress_label.setText(
            f"Downloading {symbol}…   ({done + 1} / {total})"
        )

    def _on_finished(self, inserted_1d: int, inserted_1w: int) -> None:
        self._set_downloading(False)
        self._progress_bar.setValue(100)
        self._progress_label.setText(
            f"Done — {inserted_1d:,} daily bars · {inserted_1w:,} weekly bars inserted."
        )
        self._apply_checkpoint_state()
        # Status will auto-refresh (triggered in AppService._on_candle_finished)

    def _on_failed(self, reason: str) -> None:
        self._set_downloading(False)
        self._progress_label.setText(f"Failed: {reason}")
        self._apply_checkpoint_state()

    def _on_paused(self, reason: str) -> None:
        """Called when IBKR disconnects mid-download (SRD-GUI-006.014)."""
        self._set_downloading(False)
        self._progress_label.setText("⏸ Paused — IBKR disconnected")
        self._apply_checkpoint_state()

    def _on_symbol_failed(self, symbol: str, reason: str) -> None:
        """Increment live fail counter in progress section (SRD-GUI-006.016)."""
        count = len(self._disc_failed_symbols) + 1
        # Update internal list so it matches AppService accumulation
        if symbol not in self._disc_failed_symbols:
            self._disc_failed_symbols.append(symbol)
        self._fail_count_lbl.setText(f"⚠  {count} symbol(s) failed so far")
        self._fail_count_lbl.show()

    def _on_failures_ready(self, symbols: object) -> None:
        """Show/hide discrepancy panel after download finishes (SRD-GUI-006.016)."""
        failed: list[str] = list(symbols) if symbols else []  # type: ignore[arg-type]
        self._disc_failed_symbols = failed
        self._fail_count_lbl.hide()
        if failed:
            self._show_discrepancies(failed)
        else:
            self._disc_group.hide()
            self._svc.clear_failed_symbols()

    def _on_fix_discrepancies(self) -> None:
        """Re-download only failed symbols (SRD-GUI-006.016)."""
        from us_swing.data.models import ConnectionStatus

        if self._svc.connection_status is not ConnectionStatus.CONNECTED:
            QMessageBox.warning(
                self,
                "IBKR Not Connected",
                "IBKR Gateway must be connected before downloading candle data.\n\n"
                "Use the '🟢 Connect Feed' button in the title bar to connect first.",
            )
            return

        failed = self._disc_failed_symbols or self._svc.get_failed_symbols()
        if not failed:
            return

        self._svc.start_candle_download(
            start_date=datetime.date.today(),
            mode="fix",
            symbols=failed,
        )
        self._disc_failed_symbols = []
        self._disc_group.hide()
        self._set_downloading(True)

    def _on_reset_db(self) -> None:
        """Confirm and reset the candle database (delete + recreate empty schema)."""
        reply = QMessageBox.warning(
            self,
            "Reset Candle Database",
            "This will permanently delete ALL candle data and cannot be undone.\n\n"
            "A full re-download from IBKR will be required afterwards.\n\n"
            "Are you sure you want to reset the database?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._reset_db_btn.setEnabled(False)
        self._reset_db_btn.setText("⏳  Resetting…")
        # Clear any in-progress/discrepancy state in the UI
        self._disc_group.hide()
        self._disc_failed_symbols = []
        self._fail_count_lbl.hide()

        self._svc.reset_candle_db()

        self._reset_db_btn.setEnabled(True)
        self._reset_db_btn.setText("🗑  Reset Database")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _show_discrepancies(self, symbols: list[str]) -> None:
        """Populate and show the discrepancy group."""
        n = len(symbols)
        self._disc_summary_lbl.setText(
            f"{n} symbol{'s' if n != 1 else ''} could not be downloaded:"
        )
        joined = ", ".join(symbols)
        if len(joined) > 120:
            joined = joined[:117] + "…"
        self._disc_symbols_lbl.setText(joined)
        self._disc_group.show()

    def _load_persisted_failures(self) -> None:
        """Restore failed-symbols panel from disk on startup (SRD-GUI-006.016)."""
        failed = self._svc.get_failed_symbols()
        if failed:
            self._disc_failed_symbols = failed
            self._show_discrepancies(failed)

    def _apply_checkpoint_state(self) -> None:
        """Show '▶ Resume Download' if a checkpoint exists; restore normal label otherwise."""
        if self._downloading:
            return
        if self._svc.has_candle_checkpoint():
            self._build_btn.setText("▶  Resume Download")
            self._build_btn.setEnabled(True)
            self._start_date_row_widget.hide()
            self._build_btn.setObjectName("run_btn")
            self._build_btn.style().unpolish(self._build_btn)
            self._build_btn.style().polish(self._build_btn)

    def _set_downloading(self, active: bool) -> None:
        self._downloading = active
        self._progress_group.setVisible(active)
        self._build_btn.setEnabled(not active)
        self._refresh_status_btn.setEnabled(not active)
        self._reset_db_btn.setEnabled(not active)
        if active:
            self._build_btn.setText("⏳  Downloading…")
            self._progress_bar.setValue(0)
            self._progress_label.setText("Starting…")
            self._cancel_btn.setEnabled(True)
            # Hide discrepancy panel while downloading; reset live counter
            self._disc_group.hide()
            self._fail_count_lbl.hide()
            self._disc_failed_symbols = []


# ── Settings Panel ────────────────────────────────────────────────────────────

class SettingsPanel(QWidget):
    """
    FO-GUI-006 Settings Panel — 5 sub-tabs.
    """

    theme_changed = pyqtSignal(str)

    def __init__(self, demo: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._db_tab       = _DatabaseTab(demo)
        self._sys_tab      = _SystemTab(demo)
        self._universe_tab = _UniverseTab(demo)
        self._sys_tab.theme_changed.connect(self.theme_changed)
        self._sys_tab.theme_changed.connect(self._universe_tab.refresh_theme)

        tabs = QTabWidget()
        tabs.addTab(_UsersTab(demo),       "Users")
        tabs.addTab(self._sys_tab,         "System")
        tabs.addTab(self._universe_tab,    "Universe")
        tabs.addTab(self._db_tab,          "Database")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(tabs)

    def trigger_fill_delta(self) -> None:
        """Programmatically invoke fill delta — identical to clicking the button manually."""
        self._db_tab._on_build_clicked()
