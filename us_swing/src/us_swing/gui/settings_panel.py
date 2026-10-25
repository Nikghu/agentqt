"""
Module: MD-GUI-006 — settings_panel.py
FO-GUI-006 Settings Panel; FO-GUI-021 section list layout (Carbon Workspace).
Dialog sections: MD-GUI-027.005.M04 (Parent SRD: SRD-GUI-027.005).
"""
from __future__ import annotations

import dataclasses
import datetime
import json
import logging

from PyQt6.QtCore import Qt, QDate, QObject, pyqtSignal
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

from us_swing.gui.app_service import AppService
from us_swing.data.models import RiskConfig, UserProfile
from us_swing.gui.icons import mark_danger, set_icon
from us_swing.gui.theme import C, active_palette

_log = logging.getLogger(__name__)


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
        self._mode.addItems(["paper", "live"])
        if user:
            self._mode.setCurrentText(user.mode if user.mode in ("paper", "live") else "paper")

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
        """Return the edited profile; fields this dialog does not show keep their values.

        Rebuilding the profile from scratch reset Telegram and notification settings
        on every user edit (ISS-GUI-0005).
        """
        username = self._username.text().strip() or "unnamed"
        base = self._user or UserProfile(
            user_id=-1, username="", display_name="", ibkr_client_id=0, mode="",
            risk_config=RiskConfig(), strategy_config={}, screener_config={},
        )
        return dataclasses.replace(
            base,
            username        = username,
            display_name    = self._display.text().strip() or username,
            ibkr_client_id  = self._ibkr_id.value(),
            mode            = self._mode.currentText(),
            risk_config     = dataclasses.replace(
                base.risk_config,
                risk_per_trade_pct = self._risk.value(),
                max_position_value = self._max_pos.value(),
                max_capital_value  = self._max_cap.value(),
                max_daily_loss_pct = self._max_loss.value(),
                default_order_type = self._order_type.currentText(),
                confirm_orders     = self._confirm.isChecked(),
            ),
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

        self._new_btn  = QPushButton("New User")
        self._edit_btn = QPushButton("Edit")
        self._del_btn  = QPushButton("Delete")
        set_icon(self._new_btn, "user-plus", "add")
        set_icon(self._edit_btn, "pencil")
        set_icon(self._del_btn, "trash-2", "danger")
        mark_danger(self._del_btn)
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
            profile = dlg.get_profile()
            if not self._confirm_live(profile.mode, "paper"):
                return
            self._demo.add_user(profile)

    def _on_edit(self) -> None:
        user = self._get_selected_user()
        if user is None:
            return
        dlg = _UserDialog(user, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            profile = dlg.get_profile()
            if not self._confirm_live(profile.mode, user.mode):
                return
            self._demo.update_user(profile)
            if profile.mode != user.mode:
                QMessageBox.information(
                    self, "Restart Required",
                    "Restart the tool for the new trading mode to take effect.",
                )

    def _confirm_live(self, new_mode: str, old_mode: str) -> bool:
        """Warn before a switch into live mode.  Returns False to cancel the save.

        Live routes real orders to whichever account is logged into TWS, so the
        user gets an explicit confirmation before it is enabled.
        """
        if new_mode != "live" or old_mode == "live":
            return True
        ret = QMessageBox.warning(
            self, "Enable Live Trading",
            "Live mode sends real orders to whichever account is logged into "
            "Trader Workstation.\n\n"
            "If TWS holds a funded account, these orders trade real money.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return ret == QMessageBox.StandardButton.Yes

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
        self._demo = demo
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
        self._confirm   = QCheckBox("Confirm before each order")
        self._confirm.setToolTip("Show a confirmation dialog before an order is sent")
        self._confirm.setChecked(rc.confirm_orders)

        form.addRow("Risk per trade:",         self._risk)
        form.addRow("Max single position:",    self._max_pos)
        form.addRow("Max capital:",            self._max_cap)
        form.addRow("Max daily loss:",         self._max_loss)
        form.addRow("Default order type:",     self._ord_type)
        form.addRow("",                        self._confirm)

        save_btn = QPushButton("Save Risk Settings")
        set_icon(save_btn, "save", "go")
        save_btn.setObjectName("run_btn")
        save_btn.setFixedWidth(200)
        save_btn.clicked.connect(self._on_save)

        self._note = QLabel("")
        self._note.setStyleSheet(f"color: {C.GREEN}; font-size: 9pt;")

        btn_row = QHBoxLayout()
        btn_row.addWidget(save_btn)
        btn_row.addWidget(self._note)
        btn_row.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)
        layout.addLayout(form)
        layout.addLayout(btn_row)
        layout.addStretch()

    def _on_save(self) -> None:
        user = self._demo.get_active_user()
        user.risk_config = dataclasses.replace(
            user.risk_config,
            risk_per_trade_pct = self._risk.value(),
            max_position_value = self._max_pos.value(),
            max_capital_value  = self._max_cap.value(),
            max_daily_loss_pct = self._max_loss.value(),
            default_order_type = self._ord_type.currentText(),
            confirm_orders     = self._confirm.isChecked(),
        )
        self._demo.update_user(user)
        self._note.setText("✔  Risk settings saved")


# ── System sections ───────────────────────────────────────────────────────────


def _page(*items: QWidget | QHBoxLayout | QFormLayout) -> QWidget:
    """Stack ``items`` top-down with the standard section padding."""
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(14, 14, 14, 14)
    layout.setSpacing(12)
    for item in items:
        if isinstance(item, QWidget):
            layout.addWidget(item)
        else:
            layout.addLayout(item)
    layout.addStretch()
    return page


class _SystemSections(QObject):
    """Connection, Scheduler and Telegram pages, plus the Appearance and Updates pages."""

    theme_changed = pyqtSignal(str)

    def __init__(self, demo: AppService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._demo = demo
        cfg = demo.get_system_config()

        # ── Connection and Scheduler forms ─────────────────────────────────────
        conn_form = QFormLayout()
        conn_form.setSpacing(10)
        sched_form = QFormLayout()
        sched_form.setSpacing(10)

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

        conn_form.addRow("IBKR TWS Host:",          self._host)
        conn_form.addRow("IBKR TWS Port:",          self._port)
        conn_form.addRow("Tick Data Client ID:",    self._tick_id)
        conn_form.addRow("Log level:",              self._log_level)
        sched_form.addRow("Market open time:",       self._open_t)
        sched_form.addRow("Market close time:",      self._close_t)
        sched_form.addRow("Market timezone:",        self._mkt_tz)
        sched_form.addRow("Enable daily scheduler:", self._sched_en)

        self._sched_btn = QPushButton("Add Scheduler")
        set_icon(self._sched_btn, "calendar", "info")
        self._sched_btn.setFixedWidth(160)
        self._sched_btn.clicked.connect(self._on_scheduler)
        self._refresh_sched_btn_label()

        self._save_notes: list[QLabel] = []

        def _save_row(*extra: QPushButton) -> QHBoxLayout:
            save_btn = QPushButton("Save Settings")
            set_icon(save_btn, "save", "go")
            save_btn.setObjectName("run_btn")
            save_btn.setFixedWidth(140)
            save_btn.clicked.connect(self._on_save)
            note = QLabel("")
            note.setStyleSheet(f"color: {C.GREEN}; font-size: 9pt;")
            self._save_notes.append(note)
            row = QHBoxLayout()
            row.addWidget(save_btn)
            for btn in extra:
                row.addWidget(btn)
            row.addWidget(note)
            row.addStretch()
            return row

        # ── Theme ──────────────────────────────────────────────────────────────
        from us_swing.gui import theme as _theme
        theme_row = QHBoxLayout()
        theme_row.setSpacing(4)

        self._btn_carbon = QPushButton("Carbon")
        self._btn_carbon.setCheckable(True)
        self._btn_mocha  = QPushButton("Mocha")
        self._btn_mocha.setCheckable(True)
        self._btn_vscode = QPushButton("VS Code")
        self._btn_vscode.setCheckable(True)
        for btn in (self._btn_carbon, self._btn_mocha, self._btn_vscode):
            btn.setObjectName("mode_btn")

        current_theme = _theme.load_theme_id()
        self._btn_carbon.setChecked(current_theme == "carbon")
        self._btn_mocha.setChecked(current_theme == "mocha")
        self._btn_vscode.setChecked(current_theme == "vscode")

        self._btn_carbon.clicked.connect(lambda: self._on_theme("carbon"))
        self._btn_mocha.clicked.connect(lambda: self._on_theme("mocha"))
        self._btn_vscode.clicked.connect(lambda: self._on_theme("vscode"))

        theme_row.addWidget(self._btn_carbon)
        theme_row.addWidget(self._btn_mocha)
        theme_row.addWidget(self._btn_vscode)

        # ── Updates ────────────────────────────────────────────────────────────
        self._update_btn = QPushButton("Check for Updates")
        set_icon(self._update_btn, "circle-arrow-up", "info")
        self._update_btn.clicked.connect(self._on_check_updates)

        self._update_note = QLabel("")
        self._update_note.setStyleSheet(f"color: {C.GREEN}; font-size: 9pt;")
        self._update_note.setWordWrap(True)
        self._update_note.hide()
        self._update_worker: object | None = None

        # ── Telegram Notifications (FO-INF-010) ────────────────────────────────
        from us_swing.gui import telegram_token_store
        _active = self._demo.get_active_user()

        tg_form = QFormLayout()
        tg_form.setSpacing(8)

        self._tg_enabled = QCheckBox("Enable notifications")
        self._tg_enabled.setChecked(_active.telegram_enabled)
        self._tg_token = QLineEdit(telegram_token_store.load(_active.user_id))
        self._tg_token.setEchoMode(QLineEdit.EchoMode.Password)
        self._tg_token.setFixedWidth(260)
        self._tg_chat = QLineEdit(_active.telegram_chat_id)
        self._tg_chat.setFixedWidth(260)

        self._tg_ev_tool = QCheckBox("Tool started")
        self._tg_ev_tool.setChecked(_active.notify_tool_started)
        self._tg_ev_screener = QCheckBox("Screener approved")
        self._tg_ev_screener.setChecked(_active.notify_screener_approved)
        self._tg_ev_pnl = QCheckBox("Day-end profit and loss")
        self._tg_ev_pnl.setChecked(_active.notify_day_end_pnl)

        tg_events = QVBoxLayout()
        tg_events.setSpacing(4)
        tg_events.addWidget(self._tg_ev_tool)
        tg_events.addWidget(self._tg_ev_screener)
        tg_events.addWidget(self._tg_ev_pnl)

        self._tg_note = QLabel("")
        self._tg_note.setStyleSheet(f"color: {C.GREEN}; font-size: 9pt;")
        self._tg_test = QPushButton("Send Test")
        set_icon(self._tg_test, "send", "info")
        self._tg_test.setFixedWidth(120)
        self._tg_test.clicked.connect(self._on_test_telegram)
        tg_save = QPushButton("Save")
        set_icon(tg_save, "save", "go")
        tg_save.setObjectName("run_btn")
        tg_save.setFixedWidth(120)
        tg_save.clicked.connect(self._on_save_telegram)

        tg_btn_row = QHBoxLayout()
        tg_btn_row.addWidget(self._tg_test)
        tg_btn_row.addWidget(tg_save)
        tg_btn_row.addWidget(self._tg_note)
        tg_btn_row.addStretch()

        tg_form.addRow("", self._tg_enabled)
        tg_form.addRow("Bot Token:", self._tg_token)
        tg_form.addRow("Chat ID:",   self._tg_chat)
        tg_form.addRow("Notify on:", tg_events)

        # ── Section pages ──────────────────────────────────────────────────────
        from us_swing import __version__
        version = QLabel(f"Installed v{__version__}")
        version.setObjectName("details_key")
        update_row = QHBoxLayout()
        update_row.addWidget(self._update_btn)
        update_row.addStretch()

        self.pages: list[tuple[str, QWidget]] = [
            ("Connection",  _page(conn_form, _save_row())),
            ("Scheduler",   _page(sched_form, _save_row(self._sched_btn))),
            ("Telegram",    _page(tg_form, tg_btn_row)),
        ]
        # Shown after Universe and Candle data (SRD-GUI-027.005).
        theme_row.addStretch()
        self.app_pages: list[tuple[str, QWidget]] = [
            ("Appearance",  _page(theme_row)),
            ("Updates",     _page(version, update_row, self._update_note)),
        ]

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _on_check_updates(self) -> None:
        from update_dialog import _CheckWorker  # type: ignore[import]

        self._update_btn.setEnabled(False)
        self._update_note.setStyleSheet(f"color: {C.GREEN}; font-size: 9pt;")
        self._update_note.setText("Checking for updates…")
        self._update_note.show()
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
        self._sched_btn.setText("Edit Scheduler" if has_task else "Add Scheduler")

    def _on_scheduler(self) -> None:
        from us_swing.gui.scheduler_dialog import SchedulerDialog
        dlg = SchedulerDialog(parent=self._sched_btn.window())
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
        for note in self._save_notes:
            note.setText("✔  Settings saved")

    def _on_save_telegram(self) -> None:
        from us_swing.gui import telegram_token_store
        user = self._demo.get_active_user()
        telegram_token_store.save(user.user_id, self._tg_token.text().strip())
        user.telegram_enabled = self._tg_enabled.isChecked()
        user.telegram_chat_id = self._tg_chat.text().strip()
        user.notify_tool_started      = self._tg_ev_tool.isChecked()
        user.notify_screener_approved = self._tg_ev_screener.isChecked()
        user.notify_day_end_pnl       = self._tg_ev_pnl.isChecked()
        self._demo.update_user(user)
        self._demo.reconfigure_notifications()
        self._tg_note.setText("✔  Telegram settings saved")

    def _on_test_telegram(self) -> None:
        self._demo.send_test_notification()
        self._tg_note.setText("✔  Test message sent")

    def _on_theme(self, theme_id: str) -> None:
        from us_swing.gui import theme as _theme
        _theme.save_theme_id(theme_id)
        _theme.apply_theme(theme_id)
        self._btn_carbon.setChecked(theme_id == "carbon")
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

        refresh_btn = QPushButton("Refresh")
        set_icon(refresh_btn, "refresh-cw", "info")
        refresh_btn.setObjectName("run_btn")
        refresh_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        refresh_btn.clicked.connect(self._on_refresh)

        top = QHBoxLayout()
        top.addWidget(self._meta_label)
        top.addStretch()
        top.addWidget(refresh_btn)

        # ── Search bar ────────────────────────────────────────────────────────
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search symbol, name or sector")
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


# ── Data panel ───────────────────────────────────────────────────────────────

def _set_state(widget: QWidget, state: str) -> None:
    """Set the ``state`` property that the theme QSS colours, and repaint."""
    widget.setProperty("state", state)
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)


def _group(title: str, right: QWidget | None = None) -> tuple[QWidget, QVBoxLayout]:
    """A titled group for the Data panel; returns the group and its body layout."""
    box = QWidget()
    body = QVBoxLayout(box)
    body.setContentsMargins(12, 12, 12, 12)
    body.setSpacing(8)
    head = QHBoxLayout()
    label = QLabel(title)
    label.setObjectName("panel_group")
    head.addWidget(label)
    head.addStretch()
    if right is not None:
        head.addWidget(right)
    body.addLayout(head)
    return box, body


def _separator() -> QFrame:
    sep = QFrame()
    sep.setObjectName("side_sep")
    sep.setFixedHeight(1)
    return sep


class _DataPanel(QWidget):
    """SRD-GUI-006.011 / SRD-GUI-027.006 — Candle data section of the Settings dialog.

    Shows download progress, failed stocks, database status and the build,
    retry and reset actions.
    """

    state_changed = pyqtSignal(str, int)   # downloading | complete | partial | idle, percent

    def __init__(self, svc: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._svc = svc
        self._db_info = None        # last CandleDbInfo received
        self._downloading = False
        self._total = 0
        self.state: tuple[str, int] = ("idle", 0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Download group ────────────────────────────────────────────────────
        self._dl_pill = QLabel("")
        self._dl_pill.setObjectName("data_pill")
        self._download_box, dl = _group("DOWNLOAD", self._dl_pill)

        self._pct_lbl = QLabel("0%")
        self._pct_lbl.setObjectName("data_pct")
        self._count_lbl = QLabel("")
        self._count_lbl.setObjectName("details_key")
        pct_row = QHBoxLayout()
        pct_row.addWidget(self._pct_lbl)
        pct_row.addStretch()
        pct_row.addWidget(self._count_lbl)

        self._progress_bar = QProgressBar()
        self._progress_bar.setObjectName("data_bar")
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(6)

        self._progress_label = QLabel("")
        self._progress_label.setObjectName("details_key")
        self._fail_count_lbl = QLabel("")
        self._fail_count_lbl.setStyleSheet(f"color: {C.RED};")
        now_row = QHBoxLayout()
        now_row.addWidget(self._progress_label)
        now_row.addStretch()
        now_row.addWidget(self._fail_count_lbl)

        self._cancel_btn = QPushButton("Cancel")
        set_icon(self._cancel_btn, "x", "danger")
        self._cancel_btn.clicked.connect(self._on_cancel)

        dl.addLayout(pct_row)
        dl.addWidget(self._progress_bar)
        dl.addLayout(now_row)
        dl.addWidget(self._cancel_btn)
        self._download_sep = _separator()

        # ── Failed group (SRD-GUI-006.016) ────────────────────────────────────
        self._disc_group, fg = _group("FAILED")
        self._disc_symbols_lbl = QLabel("")
        self._disc_symbols_lbl.setWordWrap(True)
        self._fix_btn = QPushButton("Retry Failed")
        set_icon(self._fix_btn, "refresh-cw", "go")
        self._fix_btn.setObjectName("run_btn")
        self._fix_btn.clicked.connect(self._on_fix_discrepancies)
        fg.addWidget(self._disc_symbols_lbl)
        fg.addWidget(self._fix_btn)
        self._disc_sep = _separator()
        self._disc_failed_symbols: list[str] = []

        # ── Status group ──────────────────────────────────────────────────────
        status_right = QWidget()
        sr = QHBoxLayout(status_right)
        sr.setContentsMargins(0, 0, 0, 0)
        sr.setSpacing(6)
        self._badge = QLabel("Checking…")
        self._badge.setObjectName("data_pill")
        self._refresh_status_btn = QPushButton()
        set_icon(self._refresh_status_btn, "refresh-cw", "info")
        self._refresh_status_btn.setToolTip("Refresh status")
        self._refresh_status_btn.setAccessibleName("Refresh status")
        self._refresh_status_btn.setFixedWidth(28)
        self._refresh_status_btn.clicked.connect(self._on_refresh_status)
        sr.addWidget(self._badge)
        sr.addWidget(self._refresh_status_btn)
        status_box, sg = _group("STATUS", status_right)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(5)
        self._values: dict[str, QLabel] = {}
        for row, key in enumerate(("Data to", "Last trading day", "Stocks", "Candles")):
            name = QLabel(key)
            name.setObjectName("details_key")
            value = QLabel("—")
            value.setAlignment(Qt.AlignmentFlag.AlignRight)
            grid.addWidget(name, row, 0)
            grid.addWidget(value, row, 1)
            self._values[key] = value
        sg.addLayout(grid)

        # Start date (only shown when the database is EMPTY)
        date_row = QHBoxLayout()
        date_lbl = QLabel("Start date")
        date_lbl.setObjectName("details_key")
        self._start_date_edit = QDateEdit()
        self._start_date_edit.setCalendarPopup(True)
        self._start_date_edit.setDisplayFormat("yyyy-MM-dd")
        self._start_date_edit.setDate(QDate.currentDate().addYears(-2))
        self._start_date_edit.setMaximumDate(QDate.currentDate())
        date_row.addWidget(date_lbl)
        date_row.addStretch()
        date_row.addWidget(self._start_date_edit)
        self._start_date_row_widget = QWidget()
        self._start_date_row_widget.setLayout(date_row)
        self._start_date_row_widget.hide()
        sg.addWidget(self._start_date_row_widget)

        # ── Actions ───────────────────────────────────────────────────────────
        actions, act = _group("ACTIONS")
        self._build_btn = QPushButton("Checking…")
        set_icon(self._build_btn, "refresh-cw", "go")
        self._build_btn.setObjectName("run_btn")
        self._build_btn.setEnabled(False)
        self._build_btn.clicked.connect(self._on_build_clicked)
        self._candle_db_btn = QPushButton("Open Candle DB")
        set_icon(self._candle_db_btn, "database", "info")
        self._candle_db_btn.clicked.connect(self._on_candle_db)
        act.addWidget(self._build_btn)
        act.addWidget(self._candle_db_btn)

        self._reset_db_btn = QPushButton("Reset Database")
        set_icon(self._reset_db_btn, "trash-2", "danger")
        mark_danger(self._reset_db_btn)
        self._reset_db_btn.setToolTip("Deletes all candles. A full download is needed after.")
        self._reset_db_btn.clicked.connect(self._on_reset_db)
        reset_row = QVBoxLayout()
        reset_row.setContentsMargins(12, 12, 12, 12)
        reset_row.addWidget(self._reset_db_btn)

        layout.addWidget(self._download_box)
        layout.addWidget(self._download_sep)
        layout.addWidget(self._disc_group)
        layout.addWidget(self._disc_sep)
        layout.addWidget(status_box)
        layout.addWidget(_separator())
        layout.addWidget(actions)
        layout.addStretch()
        layout.addWidget(_separator())
        layout.addLayout(reset_row)

        self._show_download(False)
        self._show_failed(False)

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

        # Trigger initial status check (deferred so the panel renders first)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(300, self._on_refresh_status)

        # Restore persisted failures from prior session (SRD-GUI-006.016)
        self._load_persisted_failures()

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_refresh_status(self) -> None:
        self._badge.setText("Checking…")
        _set_state(self._badge, "")
        self._build_btn.setEnabled(False)
        self._svc.refresh_candle_db_status()

    def _on_status_loaded(self, info: object) -> None:
        from us_swing.gui.app_service import CandleDbStatus, CandleDbInfo
        if not isinstance(info, CandleDbInfo):
            return
        self._db_info = info

        badge = {
            CandleDbStatus.EMPTY:   ("empty",    "Empty"),
            CandleDbStatus.PARTIAL: ("partial",  "Partial"),
            CandleDbStatus.CURRENT: ("complete", "Current"),
        }
        state, label = badge[info.status]
        self._badge.setText(label)
        _set_state(self._badge, state)

        universe = info.universe_size or 0
        sym = max(info.symbols_1d, info.symbols_1w)
        self._values["Data to"].setText(str(info.last_candle_date or "—"))
        self._values["Last trading day"].setText(str(info.last_trading_day))
        self._values["Stocks"].setText(f"{sym} / {universe}")
        self._values["Candles"].setText(f"{info.total_1d + info.total_1w:,}")
        self._values["Candles"].setToolTip(
            f"{info.total_1d:,} daily · {info.total_1w:,} weekly"
        )

        if self._downloading:
            return   # don't change button state mid-download

        if info.status == CandleDbStatus.EMPTY:
            self._build_btn.setText("Build Full Database")
            set_icon(self._build_btn, "download", "go")
            self._build_btn.setEnabled(True)
            self._build_btn.setObjectName("run_btn")
            self._start_date_row_widget.show()
        elif info.status == CandleDbStatus.PARTIAL:
            self._build_btn.setText("Fill Delta")
            set_icon(self._build_btn, "refresh-cw", "go")
            self._build_btn.setEnabled(True)
            self._build_btn.setObjectName("run_btn")
            self._start_date_row_widget.hide()
        else:  # CURRENT
            self._build_btn.setText("Database Current")
            set_icon(self._build_btn, "check", "add")
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
                "Use the 'Connect Feed' button in the title bar to connect first.",
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
        self._total = total
        pct = int(done / total * 100) if total > 0 else 0
        self._progress_bar.setValue(pct)
        self._pct_lbl.setText(f"{pct}%")
        self._count_lbl.setText(f"{done} / {total} stocks")
        self._progress_label.setText(f"Now: {symbol}")
        self._emit_state("downloading", pct)

    def _on_finished(self, inserted_1d: int, inserted_1w: int) -> None:
        self._set_downloading(False)
        self._progress_label.setText(
            f"Finished {datetime.datetime.now():%H:%M}"
        )
        self._progress_label.setToolTip(
            f"{inserted_1d:,} daily · {inserted_1w:,} weekly bars added"
        )
        self._show_result(len(self._disc_failed_symbols))
        self._apply_checkpoint_state()
        # Status will auto-refresh (triggered in AppService._on_candle_finished)

    def _on_failed(self, reason: str) -> None:
        self._set_downloading(False)
        self._progress_label.setText("Failed")
        self._progress_label.setToolTip(reason)
        self._set_result("partial", "Failed")
        self._apply_checkpoint_state()

    def _on_paused(self, reason: str) -> None:
        """Called when IBKR disconnects mid-download (SRD-GUI-006.014)."""
        self._set_downloading(False)
        self._progress_label.setText("IBKR disconnected")
        self._set_result("partial", "Paused")
        self._apply_checkpoint_state()

    def _on_symbol_failed(self, symbol: str, reason: str) -> None:
        """Increment live fail counter in the download group (SRD-GUI-006.016)."""
        if symbol not in self._disc_failed_symbols:
            self._disc_failed_symbols.append(symbol)
        self._fail_count_lbl.setText(f"{len(self._disc_failed_symbols)} failed")

    def _on_failures_ready(self, symbols: object) -> None:
        """Show/hide the failed group after download finishes (SRD-GUI-006.016)."""
        failed: list[str] = list(symbols) if symbols else []  # type: ignore[arg-type]
        self._disc_failed_symbols = failed
        if failed:
            self._show_discrepancies(failed)
        else:
            self._show_failed(False)
            self._svc.clear_failed_symbols()
        if not self._download_box.isHidden() and not self._downloading:
            self._show_result(len(failed))

    def _on_fix_discrepancies(self) -> None:
        """Re-download only failed symbols (SRD-GUI-006.016)."""
        from us_swing.data.models import ConnectionStatus

        if self._svc.connection_status is not ConnectionStatus.CONNECTED:
            QMessageBox.warning(
                self,
                "IBKR Not Connected",
                "IBKR Gateway must be connected before downloading candle data.\n\n"
                "Use the 'Connect Feed' button in the title bar to connect first.",
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
        self._show_failed(False)
        self._set_downloading(True)

    def _on_candle_db(self) -> None:
        from us_swing.gui.execution_panel import _CandleDbDiagDialog
        _CandleDbDiagDialog(self._svc, self.window()).exec()

    def _on_reset_db(self) -> None:
        """Confirm and clear the daily and weekly candle tables."""
        reply = QMessageBox.warning(
            self,
            "Reset Candle Database",
            "This will permanently delete all daily and weekly candles "
            "and cannot be undone.\n\n"
            "A full re-download from IBKR will be required afterwards. "
            "Your trades, cycles and strategies are kept.\n\n"
            "Are you sure you want to reset the database?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._reset_db_btn.setEnabled(False)
        self._reset_db_btn.setText("Resetting…")
        # Clear any in-progress/discrepancy state in the UI
        self._show_failed(False)
        self._disc_failed_symbols = []
        self._show_download(False)
        self._emit_state("idle", 0)

        try:
            self._svc.reset_candle_db()
        except Exception as exc:
            _log.exception("[CandleDB] Database reset failed")
            QMessageBox.critical(
                self,
                "Reset Failed",
                "The candle database could not be reset.\n\n"
                f"{exc}\n\n"
                "Close any other program using the database and try again.",
            )
        finally:
            self._reset_db_btn.setEnabled(True)
            self._reset_db_btn.setText("Reset Database")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _emit_state(self, state: str, percent: int) -> None:
        self.state = (state, percent)
        self.state_changed.emit(state, percent)

    def _show_download(self, visible: bool) -> None:
        self._download_box.setVisible(visible)
        self._download_sep.setVisible(visible)

    def _show_failed(self, visible: bool) -> None:
        self._disc_group.setVisible(visible)
        self._disc_sep.setVisible(visible)

    def _set_result(self, state: str, label: str) -> None:
        """Colour the download group for ``state`` and tell the strip."""
        self._dl_pill.setText(label)
        for widget in (self._dl_pill, self._pct_lbl, self._progress_bar):
            _set_state(widget, state)
        self._emit_state(state, self._progress_bar.value())

    def _show_result(self, failed: int) -> None:
        """Show Complete or Partial once a download ends."""
        total = self._total
        done = max(total - failed, 0)
        pct = int(done / total * 100) if total and failed else 100
        self._progress_bar.setValue(pct)
        self._pct_lbl.setText(f"{pct}%")
        if total:
            self._count_lbl.setText(f"{done} / {total} stocks")
        self._fail_count_lbl.setText(f"{failed} failed" if failed else "")
        if failed:
            self._set_result("partial", "Partial")
        else:
            self._set_result("complete", "Complete")

    def _show_discrepancies(self, symbols: list[str]) -> None:
        """Populate and show the failed group."""
        joined = " · ".join(symbols)
        if len(joined) > 120:
            joined = joined[:117] + "…"
        self._disc_symbols_lbl.setText(joined)
        self._disc_symbols_lbl.setToolTip(", ".join(symbols))
        self._show_failed(True)

    def _load_persisted_failures(self) -> None:
        """Restore the failed group from disk on startup (SRD-GUI-006.016)."""
        failed = self._svc.get_failed_symbols()
        if failed:
            self._disc_failed_symbols = failed
            self._show_discrepancies(failed)
            self._emit_state("partial", 0)

    def _apply_checkpoint_state(self) -> None:
        """Show 'Resume Download' if a checkpoint exists; restore normal label otherwise."""
        if self._downloading:
            return
        if self._svc.has_candle_checkpoint():
            self._build_btn.setText("Resume Download")
            set_icon(self._build_btn, "play", "go")
            self._build_btn.setEnabled(True)
            self._start_date_row_widget.hide()
            self._build_btn.setObjectName("run_btn")
            self._build_btn.style().unpolish(self._build_btn)
            self._build_btn.style().polish(self._build_btn)

    def _set_downloading(self, active: bool) -> None:
        self._downloading = active
        self._build_btn.setEnabled(not active)
        self._refresh_status_btn.setEnabled(not active)
        self._reset_db_btn.setEnabled(not active)
        self._cancel_btn.setVisible(active)
        if active:
            self._build_btn.setText("Downloading…")
            self._progress_bar.setValue(0)
            self._pct_lbl.setText("0%")
            self._count_lbl.setText("")
            self._progress_label.setText("Starting…")
            self._progress_label.setToolTip("")
            self._fail_count_lbl.setText("")
            self._cancel_btn.setEnabled(True)
            self._show_download(True)
            # Hide failed group while downloading; reset live counter
            self._show_failed(False)
            self._disc_failed_symbols = []
            self._set_result("downloading", "Downloading")


# ── Settings Panel ────────────────────────────────────────────────────────────

class SettingsPanel(QWidget):
    """
    FO-GUI-006 Settings Panel — section list on the left, one section shown at a time (FO-GUI-021).
    """

    theme_changed = pyqtSignal(str)

    def __init__(self, demo: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._data         = _DataPanel(demo)
        self._sys          = _SystemSections(demo, self)
        self._universe_tab = _UniverseTab(demo)
        self._sys.theme_changed.connect(self.theme_changed)
        self._sys.theme_changed.connect(self._universe_tab.refresh_theme)

        sections: list[tuple[str, QWidget]] = [
            ("Users", _UsersTab(demo)),
            ("Risk",  _RiskTab(demo)),
            *self._sys.pages,
            ("Universe", self._universe_tab),
            ("Candle data", self._data),
            *self._sys.app_pages,
        ]

        nav = QFrame()
        nav.setObjectName("settings_nav")
        nav.setFixedWidth(180)
        nav_layout = QVBoxLayout(nav)
        nav_layout.setContentsMargins(4, 4, 4, 4)
        nav_layout.setSpacing(2)

        self._stack = QStackedWidget()
        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        self._names = [name for name, _body in sections]
        for index, (name, body) in enumerate(sections):
            btn = QPushButton(name)
            btn.setObjectName("side_btn")
            btn.setCheckable(True)
            self._nav_group.addButton(btn, index)
            nav_layout.addWidget(btn)
            self._stack.addWidget(self._section_card(name, body))
        nav_layout.addStretch()
        self._nav_group.idClicked.connect(self._stack.setCurrentIndex)
        first = self._nav_group.button(0)
        if first is not None:
            first.setChecked(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        layout.addWidget(nav)
        layout.addWidget(self._stack, 1)

    def show_section(self, name: str) -> None:
        """Select the section called ``name``; unknown names are ignored (SRD-GUI-027.001)."""
        if name not in self._names:
            return
        index = self._names.index(name)
        btn = self._nav_group.button(index)
        if btn is not None:
            btn.setChecked(True)
        self._stack.setCurrentIndex(index)

    @staticmethod
    def _section_card(name: str, body: QWidget) -> QFrame:
        card = QFrame()
        card.setObjectName("settings_card")
        head = QLabel(name.upper())
        head.setObjectName("settings_head")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)
        card_layout.addWidget(head)
        card_layout.addWidget(body, 1)
        return card

    @property
    def data_panel(self) -> _DataPanel:
        """Candle data section; its state drives the sidebar Settings badge (SRD-GUI-027.008)."""
        return self._data

    def trigger_fill_delta(self) -> None:
        """Programmatically invoke fill delta — identical to clicking the button manually."""
        self._data._on_build_clicked()
