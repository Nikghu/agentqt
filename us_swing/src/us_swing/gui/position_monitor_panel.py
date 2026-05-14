"""
Module: MD-GUI-005 — position_monitor_panel.py
FO-GUI-005 Position Monitor: capital availability indicator + live position table.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from us_swing.gui.app_service import AppService
from us_swing.gui.position_table_model import PositionTableModel
from us_swing.gui.theme import C


# ── Capital row widget ────────────────────────────────────────────────────────

class _CapitalRow(QFrame):
    """Compact capital-availability indicator shown at top of panel."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)

        self._remaining_lbl  = QLabel()
        self._remaining_lbl.setStyleSheet(f"font-size: 10pt; font-weight: bold;")

        self._utilisation_lbl = QLabel()
        self._utilisation_lbl.setStyleSheet(f"color: {C.MUTED}; font-size: 9pt;")

        self._can_enter = QLabel()
        self._can_enter.setFixedWidth(120)
        self._can_enter.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setFixedHeight(8)
        self._bar.setTextVisible(False)

        left = QVBoxLayout()
        left.setSpacing(2)
        left.addWidget(QLabel("Capital Available"))
        left.addWidget(self._remaining_lbl)
        left.addWidget(self._utilisation_lbl)

        right = QVBoxLayout()
        right.setAlignment(Qt.AlignmentFlag.AlignTop)
        right.addWidget(self._can_enter)

        row = QHBoxLayout(self)
        row.setContentsMargins(14, 12, 14, 4)
        row.addLayout(left, 1)
        row.addWidget(self._bar, 2)
        row.addLayout(right)

    def refresh(self, equity: float, open_val: float, max_capital_pct: float) -> None:
        available = equity - open_val
        util_pct  = open_val / equity * 100 if equity > 0 else 0.0
        max_pct   = max_capital_pct

        self._remaining_lbl.setText(f"${available:,.0f}  of  ${equity:,.0f}")
        colour = C.GREEN if available > 0 else C.RED
        self._remaining_lbl.setStyleSheet(f"color: {colour}; font-size: 10pt; font-weight: bold;")

        self._utilisation_lbl.setText(
            f"{util_pct:.1f}% used · limit {max_pct:.0f}%"
        )

        self._bar.setValue(int(min(util_pct, 100)))
        alert = util_pct >= 90
        self._bar.setProperty("alert", str(alert).lower())
        self._bar.style().unpolish(self._bar)
        self._bar.style().polish(self._bar)

        can = available > 0 and util_pct < max_pct
        if can:
            self._can_enter.setText("CAN ENTER")
            self._can_enter.setObjectName("can_enter_yes")
        else:
            self._can_enter.setText("CANNOT ENTER")
            self._can_enter.setObjectName("can_enter_no")
        # force style re-apply after objectName change
        self._can_enter.setStyleSheet("")
        self._can_enter.style().unpolish(self._can_enter)
        self._can_enter.style().polish(self._can_enter)


# ── Position Monitor Panel ────────────────────────────────────────────────────

class PositionMonitorPanel(QWidget):
    """
    FO-GUI-005 Position Monitor Panel.
    Capital availability row + full position table with state colour coding.
    """

    def __init__(self, demo: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._demo = demo

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # ── Capital row ────────────────────────────────────────────────────────
        self._cap_row = _CapitalRow()
        main.addWidget(self._cap_row)

        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {C.OVERLAY};")
        main.addWidget(sep)

        # ── Position table ─────────────────────────────────────────────────────
        positions_grp = QGroupBox("Open Positions")
        grp_layout    = QVBoxLayout(positions_grp)
        grp_layout.setContentsMargins(8, 8, 8, 8)

        self._pos_model = PositionTableModel()
        self._pos_view  = QTableView()
        self._pos_view.setModel(self._pos_model)
        self._pos_view.setAlternatingRowColors(True)
        self._pos_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._pos_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._pos_view.verticalHeader().setVisible(False)
        self._pos_view.setShowGrid(True)
        hdrs = self._pos_view.horizontalHeader()
        hdrs.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed); hdrs.resizeSection(0, 80)
        hdrs.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed); hdrs.resizeSection(1, 60)
        hdrs.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed); hdrs.resizeSection(2, 90)
        hdrs.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed); hdrs.resizeSection(3, 90)
        hdrs.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed); hdrs.resizeSection(4, 90)
        hdrs.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed); hdrs.resizeSection(5, 70)
        hdrs.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed); hdrs.resizeSection(6, 90)
        hdrs.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed); hdrs.resizeSection(7, 90)
        hdrs.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)

        grp_layout.addWidget(self._pos_view)

        # Close-position button
        self._close_btn = QPushButton("Close Selected Position")
        self._close_btn.setObjectName("close_btn")
        self._close_btn.setEnabled(False)
        self._close_btn.setFixedWidth(200)
        self._pos_view.selectionModel().selectionChanged.connect(self._on_sel)
        self._close_btn.clicked.connect(self._on_close)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self._close_btn)
        grp_layout.addLayout(btn_row)

        main.addWidget(positions_grp, 1)

        # ── Status footer ──────────────────────────────────────────────────────
        self._status = QLabel()
        self._status.setStyleSheet(f"color: {C.MUTED}; font-size: 8pt; padding: 4px 12px;")
        main.addWidget(self._status)

        # ── Connect demo signals ────────────────────────────────────────────────
        demo.positions_updated.connect(self._refresh_positions)
        demo.account_updated.connect(self._refresh_account)
        demo.exchange_unavail_updated.connect(self._pos_model.set_exchange_unavailable)
        self._refresh_positions()
        self._refresh_account()

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _refresh_positions(self) -> None:
        positions = self._demo.get_positions()
        self._pos_model.refresh(positions)
        self._status.setText(
            f"{len(positions)} active position(s)  ·  "
            f"prices update every 2 s"
        )

    def _refresh_account(self) -> None:
        acct    = self._demo.get_account_state()
        user    = self._demo.get_active_user()
        self._cap_row.refresh(acct.equity, acct.open_position_value, user.max_capital_pct)

    def _on_sel(self) -> None:
        self._close_btn.setEnabled(
            bool(self._pos_view.selectionModel().selectedRows())
        )

    def _on_close(self) -> None:
        rows = self._pos_view.selectionModel().selectedRows()
        if not rows:
            return
        row   = rows[0].row()
        positions = self._demo.get_positions()
        if row >= len(positions):
            return
        symbol = positions[row].symbol
        from PyQt6.QtWidgets import QMessageBox
        ret = QMessageBox.question(
            self,
            "Close Position",
            f"Close <b>{symbol}</b> at market?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ret == QMessageBox.StandardButton.Yes:
            self._demo.close_position(symbol)
