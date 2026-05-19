"""
Module: MD-GUI-002.001.M01 — dashboard_panel.py
Parent SRD: SRD-GUI-002.001 – SRD-GUI-002.008

Dashboard: TIKR-style KPI cards · open positions table · capital bar · trade history.
"""
from __future__ import annotations

import datetime

import logging

from PyQt6.QtCore import QAbstractTableModel, QEvent, QModelIndex, QStringListModel, Qt
from PyQt6.QtGui import QColor, QFont, QTextCursor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from us_swing.gui.log_viewer_panel import _html_entry

from us_swing.gui.app_service import AppService
from us_swing.gui._types import AccountState, OpenPosition
from us_swing.gui.position_table_model import PositionTableModel, TradeHistoryModel
from us_swing.gui.theme import C, colors
from us_swing.data.models import WatchlistItem

_log = logging.getLogger(__name__)


# ── Shared dialog stylesheet ──────────────────────────────────────────────────
_DLG_QSS = (
    f"QDialog {{ background:{C.BG}; color:{C.TEXT};"
    f"  border:1px solid {C.OVERLAY2}; border-radius:0px; }}"
    f"QLabel {{ color:{C.TEXT}; }}"
    f"QGroupBox {{ color:{C.MUTED}; border:1px solid {C.OVERLAY};"
    f"  border-radius:4px; margin-top:6px; padding-top:14px; }}"
    f"QGroupBox::title {{ subcontrol-origin:margin; left:8px; padding:0 4px; }}"
    f"QSpinBox, QDoubleSpinBox, QComboBox {{"
    f"  background:{C.SURFACE}; color:{C.TEXT}; border:1px solid {C.OVERLAY};"
    f"  border-radius:3px; padding:3px 6px; min-height:20px; outline:none; }}"
    f"QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{"
    f"  border:1px solid {C.BLUE}; outline:none; }}"
    f"QPushButton {{ background:{C.OVERLAY}; color:{C.TEXT}; border:none;"
    f"  border-radius:4px; padding:6px 14px; }}"
    f"QPushButton:hover {{ background:{C.OVERLAY2}; }}"
    f"QPushButton:focus {{ outline: none; }}"
    f"QCheckBox {{ color:{C.TEXT}; spacing:6px; }}"
    f"QRadioButton {{ color:{C.TEXT}; spacing:6px; }}"
    f"QTabWidget::pane {{ border:1px solid {C.OVERLAY}; background:{C.BG}; }}"
    f"QTabBar::tab {{ background:{C.SURFACE}; color:{C.MUTED}; padding:6px 16px;"
    f"  border:1px solid {C.OVERLAY}; border-bottom:none;"
    f"  border-top-left-radius:4px; border-top-right-radius:4px; margin-right:2px; font-size:9pt; }}"
    f"QTabBar::tab:selected {{ background:{C.BG}; color:{C.BLUE};"
    f"  border-bottom:2px solid {C.BLUE}; font-weight:bold; }}"
    f"QTabBar::tab:hover:!selected {{ color:{C.TEXT}; background:{C.OVERLAY}; }}"
)


# ── Exit Position Dialog ──────────────────────────────────────────────────────

class _ExitPositionDialog(QDialog):
    """
    Professional position-exit dialog modelled after Thinkorswim / IBKR TWS /
    Schwab StreetSmart.  Tabs:

      1. Market Exit   — full close at market (MKT)
      2. Limit Exit    — full or partial close at a limit price
      3. Scale Out     — partial close by qty / pct at market
      4. Stop / Trail  — set or update SL (fixed / trailing)

    Returns .action + .params on Accepted.
    """

    def __init__(self, pos: OpenPosition, user_name: str = "",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint
        )
        self.setWindowTitle(f"Exit Position — {pos.symbol}")
        self.setMinimumWidth(580)
        self.setMinimumHeight(540)
        self._pos = pos
        self.action: str = ""
        self.params: dict = {}
        self._drag_pos = None
        self.setStyleSheet(_DLG_QSS)

        # ── Root layout (no margins — title bar goes edge-to-edge) ────────────
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Custom draggable title bar ────────────────────────────────────────
        self._title_bar = self._build_title_bar(pos.symbol)
        root.addWidget(self._title_bar)

        # ── Content area ──────────────────────────────────────────────────────
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 12, 16, 14)
        content_layout.setSpacing(10)

        # ── Position summary card (two-row metrics grid) ──────────────────────
        content_layout.addWidget(self._build_summary_card(pos, user_name))

        # ── Tabs ──────────────────────────────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        content_layout.addWidget(self._tabs, 1)

        self._build_market_tab()
        self._build_limit_tab()
        self._build_scale_out_tab()
        self._build_stop_trail_tab()

        # ── Separator before buttons ──────────────────────────────────────────
        btn_sep = QFrame()
        btn_sep.setFrameShape(QFrame.Shape.HLine)
        btn_sep.setFixedHeight(1)
        btn_sep.setStyleSheet(f"background:{C.OVERLAY};")
        content_layout.addWidget(btn_sep)

        # ── Confirm + Cancel ──────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setFixedHeight(32)
        self._confirm_btn = QPushButton("Confirm Exit")
        self._confirm_btn.setFixedHeight(32)
        self._confirm_btn.setStyleSheet(
            f"background:{C.RED}; color:#fff; font-weight:bold; padding:0 24px;"
        )
        self._cancel_btn.clicked.connect(self.reject)
        self._confirm_btn.clicked.connect(self._on_confirm)
        btn_row.addStretch()
        btn_row.addWidget(self._cancel_btn)
        btn_row.addWidget(self._confirm_btn)
        content_layout.addLayout(btn_row)

        root.addWidget(content, 1)

        # Update confirm label based on active tab
        self._tabs.currentChanged.connect(self._update_confirm_label)
        self._update_confirm_label(0)

    # ── Title bar & summary card builders ────────────────────────────────────

    def _build_title_bar(self, symbol: str) -> QFrame:
        """Custom draggable title bar with symbol badge, title, and close button."""
        bar = QFrame()
        bar.setObjectName("dlg_title_bar")
        bar.setFixedHeight(36)
        bar.setStyleSheet(
            f"QFrame#dlg_title_bar {{"
            f"  background:#11111b;"
            f"  border-bottom:1px solid {C.OVERLAY};"
            f"}}"
        )

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 0, 10, 0)
        layout.setSpacing(10)

        title_lbl = QLabel("Exit Position")
        title_lbl.setStyleSheet(
            f"background:transparent; color:{C.TEXT}; font-size:9pt; font-weight:bold;"
        )

        layout.addWidget(title_lbl)
        layout.addStretch()

        # Wire drag events to the title bar frame
        bar.mousePressEvent   = self._title_mouse_press
        bar.mouseMoveEvent    = self._title_mouse_move
        bar.mouseReleaseEvent = self._title_mouse_release

        return bar

    def _build_summary_card(self, pos: OpenPosition, user_name: str = "") -> QFrame:
        """Two-row four-column position metrics card."""
        card = QFrame()
        card.setObjectName("pos_summary_card")
        card.setStyleSheet(
            f"QFrame#pos_summary_card {{"
            f"  background:{C.SURFACE}; border:1px solid {C.OVERLAY};"
            f"  border-radius:0px;"
            f"}}"
        )

        outer = QVBoxLayout(card)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(8)

        pnl       = pos.unrealised_pnl
        pnl_color = C.GREEN if pnl >= 0 else C.RED
        sign      = "+" if pnl >= 0 else ""
        risk_dist = abs(pos.current_price - pos.stop_loss) if pos.stop_loss else 0
        risk_val  = risk_dist * pos.quantity
        rr_num    = abs(pos.target_price - pos.average_price)
        rr_den    = abs(pos.average_price - pos.stop_loss) if pos.stop_loss else 0
        rr_ratio  = rr_num / rr_den if rr_den > 0 else 0

        # ── Row 0: symbol + badges ────────────────────────────────────────────
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        sym_lbl = QLabel(f"<b style='color:{C.BLUE};font-size:13pt'>{pos.symbol}</b>")
        sym_lbl.setTextFormat(Qt.TextFormat.RichText)

        state_badge = QLabel(pos.state)
        state_badge.setStyleSheet(
            f"background:{C.OVERLAY}; color:{C.TEXT};"
            f"border-radius:4px; padding:2px 8px; font-size:8pt; font-weight:bold;"
        )
        mode_badge = QLabel(pos.mode.upper())
        mode_badge.setStyleSheet(
            f"background:{C.BLUE}22; color:{C.BLUE};"
            f"border:1px solid {C.BLUE}44; border-radius:4px;"
            f"padding:2px 8px; font-size:8pt; font-weight:bold;"
        )
        top_row.addWidget(sym_lbl)
        top_row.addWidget(state_badge)
        top_row.addWidget(mode_badge)
        if user_name:
            admin_badge = QLabel("ADMIN")
            admin_badge.setStyleSheet(
                f"background:{C.YELLOW}22; color:{C.YELLOW};"
                f"border:1px solid {C.YELLOW}55; border-radius:4px;"
                f"padding:2px 8px; font-size:8pt; font-weight:bold;"
            )
            user_badge = QLabel(user_name)
            user_badge.setStyleSheet(
                f"background:#2a1a3a; color:{C.MAUVE};"
                f"border:1px solid {C.MAUVE}; border-radius:4px;"
                f"padding:2px 8px; font-size:8pt; font-weight:bold;"
            )
            top_row.addWidget(admin_badge)
            top_row.addWidget(user_badge)
        top_row.addStretch()
        outer.addLayout(top_row)

        # ── Thin divider ──────────────────────────────────────────────────────
        div1 = QFrame()
        div1.setFrameShape(QFrame.Shape.HLine)
        div1.setFixedHeight(1)
        div1.setStyleSheet(f"background:{C.OVERLAY};")
        outer.addWidget(div1)

        # ── Helper: one vertical metric column ────────────────────────────────
        def _metric(label: str, value: str, val_color: str = C.TEXT) -> QVBoxLayout:
            col = QVBoxLayout()
            col.setSpacing(3)
            lbl = QLabel(label.upper())
            lbl.setStyleSheet(
                f"color:{C.MUTED}; font-size:7pt; letter-spacing:0.5px;"
            )
            val = QLabel(value)
            val.setStyleSheet(
                f"color:{val_color}; font-size:10pt; font-weight:bold;"
            )
            col.addWidget(lbl)
            col.addWidget(val)
            return col

        def _vsep() -> QFrame:
            f = QFrame()
            f.setFrameShape(QFrame.Shape.VLine)
            f.setFixedWidth(1)
            f.setStyleSheet(f"background:{C.OVERLAY};")
            return f

        # ── Row 1: entry metrics ──────────────────────────────────────────────
        row1 = QHBoxLayout()
        row1.setSpacing(0)
        row1.addLayout(_metric("Qty", f"{pos.quantity} shares"))
        row1.addSpacing(16); row1.addWidget(_vsep()); row1.addSpacing(16)
        row1.addLayout(_metric("Avg Entry", f"${pos.average_price:,.2f}"))
        row1.addSpacing(16); row1.addWidget(_vsep()); row1.addSpacing(16)
        row1.addLayout(_metric("Current", f"${pos.current_price:,.2f}"))
        row1.addSpacing(16); row1.addWidget(_vsep()); row1.addSpacing(16)
        row1.addLayout(_metric(
            "Unrlzd P&L",
            f"{sign}${pnl:,.2f}  ({pos.pnl_pct:+.1f}%)",
            pnl_color
        ))
        row1.addStretch()
        outer.addLayout(row1)

        # ── Thin divider ──────────────────────────────────────────────────────
        div2 = QFrame()
        div2.setFrameShape(QFrame.Shape.HLine)
        div2.setFixedHeight(1)
        div2.setStyleSheet(f"background:{C.OVERLAY};")
        outer.addWidget(div2)

        # ── Row 2: risk metrics ───────────────────────────────────────────────
        rr_color = C.GREEN if rr_ratio >= 2 else C.YELLOW if rr_ratio >= 1 else C.RED
        row2 = QHBoxLayout()
        row2.setSpacing(0)
        row2.addLayout(_metric("Stop Loss", f"${pos.stop_loss:,.2f}"))
        row2.addSpacing(16); row2.addWidget(_vsep()); row2.addSpacing(16)
        row2.addLayout(_metric("Target", f"${pos.target_price:,.2f}"))
        row2.addSpacing(16); row2.addWidget(_vsep()); row2.addSpacing(16)
        row2.addLayout(_metric("Risk to SL", f"${risk_val:,.0f}", C.RED))
        row2.addSpacing(16); row2.addWidget(_vsep()); row2.addSpacing(16)
        row2.addLayout(_metric(
            "R/R Ratio",
            f"{rr_ratio:.1f} : 1" if rr_den > 0 else "—",
            rr_color
        ))
        row2.addStretch()
        outer.addLayout(row2)

        return card

    # ── Window drag support ───────────────────────────────────────────────────

    def _title_mouse_press(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def _title_mouse_move(self, event) -> None:
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def _title_mouse_release(self, event) -> None:
        self._drag_pos = None
        event.accept()

    # ── Tab builders ──────────────────────────────────────────────────────────

    def _build_market_tab(self) -> None:
        """Tab 1 — Market Exit: close full position instantly at market."""
        w = QWidget()
        ly = QVBoxLayout(w)
        ly.setContentsMargins(10, 12, 10, 8)
        ly.setSpacing(8)

        pnl = self._pos.unrealised_pnl
        clr = C.GREEN if pnl >= 0 else C.RED
        sgn = "+" if pnl >= 0 else ""

        ly.addWidget(QLabel(
            f"Sell <b>{self._pos.quantity} shares</b> of {self._pos.symbol} "
            f"at <b>Market</b> price."
        ))
        ly.addWidget(QLabel(
            f"<span style='color:{C.MUTED}'>Estimated fill ~ {self._pos.current_price:.2f} · "
            f"Est. P&amp;L: <b style='color:{clr}'>{sgn}${pnl:,.2f}</b></span>"
        ))

        # Time-in-force
        tif_row = QHBoxLayout()
        tif_row.addWidget(QLabel("Time-in-Force:"))
        self._mkt_tif = QComboBox()
        self._mkt_tif.addItems(["DAY", "IOC (Immediate-or-Cancel)", "GTC (Good-til-Cancel)"])
        tif_row.addWidget(self._mkt_tif)
        tif_row.addStretch()
        ly.addLayout(tif_row)
        ly.addStretch()
        self._tabs.addTab(w, "⚡  Market Exit")

    def _build_limit_tab(self) -> None:
        """Tab 2 — Limit Exit: close at a specified price or better."""
        w = QWidget()
        ly = QVBoxLayout(w)
        ly.setContentsMargins(10, 12, 10, 8)
        ly.setSpacing(8)

        ly.addWidget(QLabel(
            f"Sell {self._pos.symbol} at a <b>Limit</b> price (or better)."
        ))

        # Limit price
        price_row = QHBoxLayout()
        price_row.addWidget(QLabel("Limit price:"))
        self._lmt_price = QDoubleSpinBox()
        self._lmt_price.setRange(0.01, self._pos.current_price * 2)
        self._lmt_price.setValue(round(self._pos.current_price * 1.002, 2))
        self._lmt_price.setDecimals(2)
        self._lmt_price.setSingleStep(0.10)
        self._lmt_price.setPrefix("$ ")
        self._lmt_price.valueChanged.connect(self._update_limit_est)
        price_row.addWidget(self._lmt_price)
        price_row.addStretch()
        ly.addLayout(price_row)

        # Quantity
        qty_row = QHBoxLayout()
        qty_row.addWidget(QLabel("Quantity:"))
        self._lmt_qty = QSpinBox()
        self._lmt_qty.setRange(1, self._pos.quantity)
        self._lmt_qty.setValue(self._pos.quantity)
        self._lmt_qty.setSuffix(f"  / {self._pos.quantity}")
        self._lmt_qty.valueChanged.connect(self._update_limit_est)
        qty_row.addWidget(self._lmt_qty)
        qty_row.addStretch()
        ly.addLayout(qty_row)

        # TIF
        tif_row = QHBoxLayout()
        tif_row.addWidget(QLabel("Time-in-Force:"))
        self._lmt_tif = QComboBox()
        self._lmt_tif.addItems(["DAY", "GTC (Good-til-Cancel)", "GTD (Good-til-Date)"])
        tif_row.addWidget(self._lmt_tif)
        tif_row.addStretch()
        ly.addLayout(tif_row)

        self._lmt_est = QLabel()
        self._lmt_est.setStyleSheet(f"color:{C.MUTED}; font-size:8pt;")
        ly.addWidget(self._lmt_est)
        ly.addStretch()
        self._update_limit_est()
        self._tabs.addTab(w, "📋  Limit Exit")

    def _build_scale_out_tab(self) -> None:
        """Tab 3 — Scale Out: partial close, book profit at market."""
        w = QWidget()
        ly = QVBoxLayout(w)
        ly.setContentsMargins(10, 12, 10, 8)
        ly.setSpacing(8)

        ly.addWidget(QLabel(
            f"Partially exit {self._pos.symbol} — book profits or reduce exposure."
        ))

        # Mode: qty vs pct
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Close by:"))
        self._scale_mode = QComboBox()
        self._scale_mode.addItems(["Quantity", "Percentage"])
        self._scale_mode.currentIndexChanged.connect(self._update_scale_display)
        mode_row.addWidget(self._scale_mode)
        mode_row.addStretch()
        ly.addLayout(mode_row)

        # Qty / Pct spinners
        val_row = QHBoxLayout()
        val_row.addWidget(QLabel("Amount:"))
        self._scale_qty = QSpinBox()
        self._scale_qty.setRange(1, self._pos.quantity - 1)
        self._scale_qty.setValue(max(1, self._pos.quantity // 2))
        self._scale_qty.setSuffix("  shares")
        self._scale_qty.valueChanged.connect(self._sync_scale_pct)
        self._scale_pct = QDoubleSpinBox()
        self._scale_pct.setRange(1.0, 99.0)
        self._scale_pct.setValue(50.0)
        self._scale_pct.setSuffix("  %")
        self._scale_pct.setSingleStep(5.0)
        self._scale_pct.valueChanged.connect(self._sync_scale_qty)
        self._scale_pct.setVisible(False)
        val_row.addWidget(self._scale_qty)
        val_row.addWidget(self._scale_pct)

        # Quick-pick buttons
        for pct in (25, 50, 75):
            b = QPushButton(f"{pct}%")
            b.setFixedWidth(44)
            b.setStyleSheet(f"font-size:8pt; padding:3px;")
            b.clicked.connect(lambda _c, p=pct: self._set_scale_pct(p))
            val_row.addWidget(b)
        val_row.addStretch()
        ly.addLayout(val_row)

        # Estimation label
        self._scale_est = QLabel()
        self._scale_est.setStyleSheet(f"color:{C.MUTED}; font-size:8pt;")
        ly.addWidget(self._scale_est)

        # New SL for remaining
        sl_row = QHBoxLayout()
        self._scale_update_sl = QCheckBox("Move SL on remaining to breakeven")
        self._scale_update_sl.setChecked(False)
        sl_row.addWidget(self._scale_update_sl)
        sl_row.addStretch()
        ly.addLayout(sl_row)

        ly.addStretch()
        self._update_scale_est()
        self._tabs.addTab(w, "📤  Scale Out")

    def _build_stop_trail_tab(self) -> None:
        """Tab 4 — Stop Loss / Trailing: set or update protective stop."""
        w = QWidget()
        ly = QVBoxLayout(w)
        ly.setContentsMargins(10, 12, 10, 8)
        ly.setSpacing(8)

        ly.addWidget(QLabel(
            f"Set or update <b>Stop Loss</b> for {self._pos.symbol}."
        ))

        # Stop price
        sl_row = QHBoxLayout()
        sl_row.addWidget(QLabel("Stop price:"))
        self._sl_price = QDoubleSpinBox()
        self._sl_price.setRange(0.01, self._pos.current_price * 1.5)
        cur_sl = self._pos.stop_loss if self._pos.stop_loss > 0 else self._pos.current_price * 0.97
        self._sl_price.setValue(cur_sl)
        self._sl_price.setDecimals(2)
        self._sl_price.setSingleStep(0.25)
        self._sl_price.setPrefix("$ ")
        self._sl_price.valueChanged.connect(self._update_sl_info)
        sl_row.addWidget(self._sl_price)

        # Quick SL presets
        for label_text, mult in [("-1%", 0.99), ("-2%", 0.98), ("-3%", 0.97), ("B/E", None)]:
            b = QPushButton(label_text)
            b.setFixedWidth(40)
            b.setStyleSheet("font-size:8pt; padding:3px;")
            if mult is not None:
                b.clicked.connect(lambda _c, m=mult: self._sl_price.setValue(
                    round(self._pos.current_price * m, 2)))
            else:
                b.clicked.connect(lambda _c: self._sl_price.setValue(self._pos.average_price))
            sl_row.addWidget(b)
        sl_row.addStretch()
        ly.addLayout(sl_row)

        self._sl_info = QLabel()
        self._sl_info.setStyleSheet(f"color:{C.MUTED}; font-size:8pt;")
        ly.addWidget(self._sl_info)
        self._update_sl_info()

        # Trailing toggle
        self._trailing_chk = QCheckBox("Enable Trailing Stop")
        self._trailing_chk.toggled.connect(self._on_trailing_toggled)
        ly.addWidget(self._trailing_chk)

        trail_grp = QGroupBox("Trailing Parameters")
        self._trail_grp = trail_grp
        trail_grp.setEnabled(False)
        tgl = QVBoxLayout(trail_grp)
        tgl.setSpacing(6)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Trail method:"))
        self._trail_type = QComboBox()
        self._trail_type.addItems(["Trail by $ Amount", "Trail by % Distance"])
        type_row.addWidget(self._trail_type)
        type_row.addStretch()
        tgl.addLayout(type_row)

        val_row = QHBoxLayout()
        val_row.addWidget(QLabel("Trail value:"))
        self._trail_val = QDoubleSpinBox()
        self._trail_val.setRange(0.01, 999.0)
        self._trail_val.setValue(max(0.50, round(self._pos.current_price - cur_sl, 2)))
        self._trail_val.setDecimals(2)
        self._trail_val.setSingleStep(0.25)
        val_row.addWidget(self._trail_val)
        val_row.addStretch()
        tgl.addLayout(val_row)

        ly.addWidget(trail_grp)
        ly.addStretch()
        self._tabs.addTab(w, "🛡  Stop / Trail")

    # ── Update helpers ────────────────────────────────────────────────────────

    def _update_confirm_label(self, idx: int) -> None:
        labels = ["Sell at Market", "Place Limit Order", "Scale Out", "Set Stop Loss"]
        colors = [C.RED, C.ORANGE, C.BLUE, C.YELLOW]
        self._confirm_btn.setText(labels[idx])
        self._confirm_btn.setStyleSheet(
            f"background:{colors[idx]}; color:#fff; font-weight:bold; padding:7px 22px;"
        )

    def _update_limit_est(self) -> None:
        qty = self._lmt_qty.value()
        px = self._lmt_price.value()
        est = (px - self._pos.average_price) * qty
        clr = C.GREEN if est >= 0 else C.RED
        sgn = "+" if est >= 0 else ""
        self._lmt_est.setText(
            f"Sell {qty} @ ${px:.2f} · Est. P&L: {sgn}${est:,.2f}"
        )

    def _update_scale_display(self) -> None:
        by_pct = self._scale_mode.currentIndex() == 1
        self._scale_qty.setVisible(not by_pct)
        self._scale_pct.setVisible(by_pct)
        self._update_scale_est()

    def _sync_scale_pct(self, qty: int) -> None:
        self._scale_pct.blockSignals(True)
        self._scale_pct.setValue(qty / self._pos.quantity * 100)
        self._scale_pct.blockSignals(False)
        self._update_scale_est()

    def _sync_scale_qty(self, pct: float) -> None:
        self._scale_qty.blockSignals(True)
        self._scale_qty.setValue(max(1, round(self._pos.quantity * pct / 100)))
        self._scale_qty.blockSignals(False)
        self._update_scale_est()

    def _set_scale_pct(self, pct: int) -> None:
        self._scale_pct.setValue(float(pct))
        self._scale_qty.setValue(max(1, round(self._pos.quantity * pct / 100)))
        self._update_scale_est()

    def _update_scale_est(self) -> None:
        qty = self._scale_qty.value()
        est = (self._pos.current_price - self._pos.average_price) * qty
        clr = C.GREEN if est >= 0 else C.RED
        sgn = "+" if est >= 0 else ""
        remaining = self._pos.quantity - qty
        self._scale_est.setText(
            f"Close {qty} / {self._pos.quantity} shares at market · "
            f"Est. P&L: {sgn}${est:,.2f}  ·  Remaining: {remaining}"
        )

    def _update_sl_info(self) -> None:
        sl = self._sl_price.value()
        dist_pct = (self._pos.current_price - sl) / self._pos.current_price * 100
        risk = (self._pos.current_price - sl) * self._pos.quantity
        clr = C.GREEN if risk >= 0 else C.RED
        self._sl_info.setText(
            f"Distance from LTP: {dist_pct:.1f}%  ·  "
            f"Max risk: ${risk:,.0f}  ·  Current SL: {self._pos.stop_loss:.2f}"
        )

    def _on_trailing_toggled(self, checked: bool) -> None:
        self._trail_grp.setEnabled(checked)
        if checked:
            dist = self._pos.current_price - self._sl_price.value()
            if dist > 0:
                self._trail_val.setValue(round(dist, 2))

    # ── Confirm action ────────────────────────────────────────────────────────

    def _on_confirm(self) -> None:
        tab = self._tabs.currentIndex()
        if tab == 0:
            self.action = "full_close"
            self.params = {"qty": self._pos.quantity, "order_type": "MKT",
                           "tif": self._mkt_tif.currentText().split()[0]}
        elif tab == 1:
            self.action = "limit_close"
            self.params = {"qty": self._lmt_qty.value(),
                           "limit_price": self._lmt_price.value(),
                           "order_type": "LMT",
                           "tif": self._lmt_tif.currentText().split()[0]}
        elif tab == 2:
            self.action = "partial_close"
            self.params = {"qty": self._scale_qty.value(),
                           "order_type": "MKT",
                           "move_sl_to_be": self._scale_update_sl.isChecked()}
        else:
            trailing = self._trailing_chk.isChecked()
            self.action = "set_stop_loss"
            self.params = {
                "price":     self._sl_price.value(),
                "trailing":  trailing,
                "trail_by":  self._trail_type.currentText() if trailing else "",
                "trail_val": self._trail_val.value() if trailing else 0.0,
            }
        self.accept()


# ── TIKR-style KPI stat card ───────────────────────────────────────────────────

class _StatCard(QFrame):
    """
    TIKR-style KPI card:
      ┌──────────────────────────────┐
      │ LABEL   (muted, uppercase)   │
      │                              │
      │  VALUE  (large, bold)        │
      │  ▲ +12.5%  (change badge)   │
      │──────────────────────────────│  ← colored accent bottom bar
      └──────────────────────────────┘
    """

    def __init__(self, label: str, accent: str = C.BLUE,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("stat_card")
        self._accent = accent

        # card border + bottom accent achieved with nested frames
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        inner_widget = QWidget()
        inner_widget.setObjectName("stat_card_inner")
        inner = QVBoxLayout(inner_widget)
        inner.setContentsMargins(14, 12, 14, 10)
        inner.setSpacing(4)

        self._lbl = QLabel(label.upper())
        self._lbl.setStyleSheet(
            f"color: {C.MUTED}; font-size: 7pt; letter-spacing: 1px; font-weight: bold;"
        )

        self._val = QLabel("—")
        self._val.setStyleSheet(f"font-size: 20pt; font-weight: bold; color: {C.TEXT};")

        self._change = QLabel()
        self._change.setStyleSheet(f"font-size: 8pt; color: {C.MUTED};")

        inner.addWidget(self._lbl)
        inner.addSpacing(2)
        inner.addWidget(self._val)
        inner.addWidget(self._change)

        # bottom accent bar (2px)
        self._bar = QFrame()
        self._bar.setFixedHeight(3)
        self._bar.setStyleSheet(f"background: {accent}; border-radius: 0px;")

        outer.addWidget(inner_widget, 1)
        outer.addWidget(self._bar)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(100)

    def set_value(self, text: str, colour: str = C.TEXT,
                  change: str = "", change_colour: str = C.MUTED) -> None:
        self._val.setText(text)
        self._val.setStyleSheet(f"font-size: 20pt; font-weight: bold; color: {colour};")
        if change:
            self._change.setText(change)
            self._change.setStyleSheet(f"font-size: 8pt; color: {change_colour};")
        self._bar.setStyleSheet(f"background: {colour}; border-radius: 0px;")


# ── Mini market-pulse bar ──────────────────────────────────────────────────────

class _MarketPulseBar(QWidget):
    """A slim info bar below cards, showing key market context at a glance."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("market_pulse")
        self.setFixedHeight(32)
        self.setStyleSheet(
            f"QWidget#market_pulse {{ background: {C.SURFACE}; "
            f"border: 1px solid {C.OVERLAY}; border-radius: 4px; }}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(0)

        def _kv(key: str, val: str, color: str = C.TEXT) -> None:
            k = QLabel(f"{key}:")
            k.setStyleSheet(f"color: {C.MUTED}; font-size: 8pt; padding: 0 2px 0 12px;")
            v = QLabel(val)
            v.setStyleSheet(f"color: {color}; font-size: 8pt; font-weight: bold; padding: 0 2px;")
            layout.addWidget(k); layout.addWidget(v)

        def _div() -> None:
            d = QLabel("│")
            d.setStyleSheet(f"color: {C.OVERLAY2}; padding: 0 6px;")
            layout.addWidget(d)

        _kv("SESSION", "LIVE READ-ONLY", C.YELLOW)
        _div()
        _kv("BUYING POWER", "—")
        _div()
        _kv("MARGIN USED", "—")
        _div()
        _kv("EXE", "DISABLED", C.BLUE)
        layout.addStretch()

        self._bp_label   = layout.itemAt(3).widget()   # "—" after BUYING POWER
        self._margin_lbl = layout.itemAt(6).widget()   # "—" after MARGIN USED

    def refresh(self, equity: float, open_val: float) -> None:
        bp = equity - open_val
        self._bp_label.setText(f"${bp:,.0f}")
        margin_pct = (open_val / equity * 100) if equity else 0
        color = C.RED if margin_pct > 80 else C.GREEN if margin_pct < 50 else C.YELLOW
        self._margin_lbl.setText(f"{margin_pct:.1f}%")
        self._margin_lbl.setStyleSheet(f"color: {color}; font-size: 8pt; font-weight: bold; padding: 0 2px;")


# ── Watchlist table model ─────────────────────────────────────────────────────

class _WatchlistModel(QAbstractTableModel):
    """QAbstractTableModel for the Watchlist tab.

    Columns: Symbol | LTP | Chg ($) | Chg % | Open | High | Low | Volume | 52W H | 52W L | Mkt Cap
    """

    _COLS = ["Symbol", "LTP", "Chg ($)", "Chg %", "Open", "High", "Low",
             "Volume", "52W High", "52W Low", "Mkt Cap"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[WatchlistItem] = []

    def refresh(self, items: list[WatchlistItem]) -> None:
        self.beginResetModel()
        self._rows = list(items)
        self.endResetModel()

    def row_symbol(self, row: int) -> str:
        return self._rows[row].symbol if 0 <= row < len(self._rows) else ""

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._COLS)

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self._COLS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        item = self._rows[index.row()]
        col  = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display(item, col)

        if role == Qt.ItemDataRole.ForegroundRole:
            if col in (2, 3):   # Chg ($) / Chg %
                if item.change_pct > 0:
                    return QColor(C.GREEN)
                if item.change_pct < 0:
                    return QColor(C.RED)
                return QColor(C.MUTED)
            if col == 1 and item.ltp:   # LTP — tinted by direction
                return QColor(C.GREEN) if item.change_pct >= 0 else QColor(C.RED)

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col == 0:
                return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter

        return None

    def _display(self, item: WatchlistItem, col: int) -> str:
        def _p(v: float) -> str:
            return f"{v:,.2f}" if v else "—"

        def _vol(v: int) -> str:
            if not v:
                return "—"
            if v >= 1_000_000:
                return f"{v/1_000_000:.1f}M"
            if v >= 1_000:
                return f"{v/1_000:.1f}K"
            return str(v)

        def _cap(v: float) -> str:
            if not v:
                return "—"
            if v >= 1e12:
                return f"{v/1e12:.2f}T"
            if v >= 1e9:
                return f"{v/1e9:.2f}B"
            if v >= 1e6:
                return f"{v/1e6:.2f}M"
            return f"{v:,.0f}"

        match col:
            case 0:  return item.symbol
            case 1:  return f"{item.ltp:,.2f}" if item.ltp else "—"
            case 2:
                if item.change == 0 and not item.ltp:
                    return "—"
                sign = "+" if item.change >= 0 else ""
                return f"{sign}{item.change:.2f}"
            case 3:
                if item.change_pct == 0 and not item.ltp:
                    return "—"
                sign = "+" if item.change_pct >= 0 else ""
                return f"{sign}{item.change_pct:.2f}%"
            case 4:  return _p(item.day_open)
            case 5:  return _p(item.day_high)
            case 6:  return _p(item.day_low)
            case 7:  return _vol(item.volume)
            case 8:  return _p(item.year_high)
            case 9:  return _p(item.year_low)
            case 10: return _cap(item.market_cap)
            case _:  return ""


# ── Market Watch table model ──────────────────────────────────────────────────

class _MarketWatchModel(QAbstractTableModel):
    """QAbstractTableModel for the Market Watch tab.

    Columns: Symbol | Name | Price | Change | Chg % | Open | High | Low | Volume
    """

    _COLS = ["Symbol", "Name", "Price", "Change", "Chg %", "Open", "High", "Low", "Volume"]

    def __init__(self, names: dict[str, str], parent=None) -> None:
        super().__init__(parent)
        self._rows: list[WatchlistItem] = []
        self._names = names

    def refresh(self, items: list[WatchlistItem]) -> None:
        self.beginResetModel()
        self._rows = list(items)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._COLS)

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self._COLS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        item = self._rows[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display(item, col)

        if role == Qt.ItemDataRole.ForegroundRole:
            if col in (3, 4):
                if item.change_pct > 0:
                    return QColor(C.GREEN)
                if item.change_pct < 0:
                    return QColor(C.RED)
                return QColor(C.MUTED)
            if col == 2 and item.ltp:
                return QColor(C.GREEN) if item.change_pct >= 0 else QColor(C.RED)

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col <= 1:
                return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter

        return None

    def _display(self, item: WatchlistItem, col: int) -> str:
        def _p(v: float) -> str:
            return f"{v:,.2f}" if v else "—"

        def _vol(v: int) -> str:
            if not v:
                return "—"
            if v >= 1_000_000:
                return f"{v / 1_000_000:.1f}M"
            if v >= 1_000:
                return f"{v / 1_000:.1f}K"
            return str(v)

        match col:
            case 0: return item.symbol
            case 1: return self._names.get(item.symbol, item.symbol)
            case 2: return f"{item.ltp:,.2f}" if item.ltp else "—"
            case 3:
                if item.change == 0 and not item.ltp:
                    return "—"
                sign = "+" if item.change >= 0 else ""
                return f"{sign}{item.change:.2f}"
            case 4:
                if item.change_pct == 0 and not item.ltp:
                    return "—"
                sign = "+" if item.change_pct >= 0 else ""
                return f"{sign}{item.change_pct:.2f}%"
            case 5: return _p(item.day_open)
            case 6: return _p(item.day_high)
            case 7: return _p(item.day_low)
            case 8: return _vol(item.volume)
            case _: return ""


# ── Market Watch tab widget ───────────────────────────────────────────────────

class _MarketWatchTab(QWidget):
    """Market Watch tab: fixed index ETFs (SPY/QQQ/DIA/IWM) with live prices."""

    def __init__(self, svc: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._svc = svc

        names = dict(svc.get_mw_symbol_names())

        self._model = _MarketWatchModel(names)
        self._view = QTableView()
        self._view.setModel(self._model)
        self._view.setAlternatingRowColors(True)
        self._view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._view.horizontalHeader().setStretchLastSection(True)
        self._view.verticalHeader().setVisible(False)
        self._view.setSortingEnabled(False)

        _col_widths = {0: 70, 1: 120, 2: 90, 3: 90, 4: 80, 5: 90, 6: 90, 7: 90}
        h = self._view.horizontalHeader()
        for col, w in _col_widths.items():
            h.resizeSection(col, w)
            h.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        h.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)

        self._updated_lbl = QLabel("")
        self._updated_lbl.setStyleSheet(f"color:{C.MUTED}; font-size:8pt;")

        bottom_bar = QHBoxLayout()
        bottom_bar.addWidget(self._updated_lbl)
        bottom_bar.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(6)
        layout.addWidget(self._view)
        layout.addLayout(bottom_bar)

        svc.market_watch_updated.connect(self._on_data_updated)
        self._on_data_updated()

    def _on_data_updated(self) -> None:
        items = self._svc.get_market_watch_items()
        self._model.refresh(items)
        now = datetime.datetime.now().strftime("%H:%M:%S")
        self._updated_lbl.setText(f"Updated {now}")


# ── Watchlist tab widget ──────────────────────────────────────────────────────

class _WatchlistTab(QWidget):
    """Watchlist tab: add/remove symbols, live-refreshing quote table."""

    def __init__(self, svc: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._svc = svc

        # ── S&P 500 symbol set (loaded once; used for validation + completer) ──
        self._sp500: frozenset[str] = frozenset()
        try:
            from us_swing.universe import store as _store  # lazy import
            records = _store.load_sp500()
            if records:
                self._sp500 = frozenset(r.symbol.upper() for r in records)
            else:
                _log.warning("[Watchlist] S&P 500 universe unavailable — symbol filter disabled")
        except Exception:
            _log.warning("[Watchlist] S&P 500 universe unavailable — symbol filter disabled")

        # ── Toolbar ───────────────────────────────────────────────────────────
        self._sym_input = QLineEdit()
        self._sym_input.setPlaceholderText("Symbol (e.g. AAPL)…")
        self._sym_input.setFixedWidth(160)
        self._sym_input.setMaxLength(12)
        if self._sp500:
            _completer_model = QStringListModel(sorted(self._sp500))
            _completer = QCompleter(_completer_model, self._sym_input)
            _completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            _completer.setCompletionMode(QCompleter.CompletionMode.InlineCompletion)
            self._sym_input.setCompleter(_completer)
        self._sym_input.returnPressed.connect(self._on_add)

        self._add_btn = QPushButton("➕  Add")
        self._add_btn.setObjectName("btn_green")
        self._add_btn.setFixedWidth(110)
        self._add_btn.clicked.connect(self._on_add)

        self._remove_btn = QPushButton("🗑  Remove")
        self._remove_btn.setObjectName("btn_remove")
        self._remove_btn.setFixedWidth(110)
        self._remove_btn.setEnabled(False)
        self._remove_btn.clicked.connect(self._on_remove)

        self._refresh_btn = QPushButton("⟳  Refresh")
        self._refresh_btn.setFixedWidth(110)
        self._refresh_btn.clicked.connect(self._on_manual_refresh)

        self._status_lbl = QLabel("No symbols in watchlist")
        self._status_lbl.setStyleSheet(f"color:{C.MUTED}; font-size:8pt;")

        self._updated_lbl = QLabel("")
        self._updated_lbl.setStyleSheet(f"color:{C.MUTED}; font-size:8pt;")

        # ── Table ─────────────────────────────────────────────────────────────
        self._model = _WatchlistModel()
        self._view  = QTableView()
        self._view.setModel(self._model)
        self._view.setAlternatingRowColors(True)
        self._view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._view.horizontalHeader().setStretchLastSection(True)
        self._view.verticalHeader().setVisible(False)
        self._view.setSortingEnabled(False)
        _wl_col_widths = {0: 80, 1: 80, 2: 75, 3: 70, 4: 70, 5: 70, 6: 70, 7: 80, 8: 75, 9: 75}
        h = self._view.horizontalHeader()
        for col, w in _wl_col_widths.items():
            h.resizeSection(col, w)
            h.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        h.setSectionResizeMode(10, QHeaderView.ResizeMode.Stretch)

        self._view.selectionModel().selectionChanged.connect(self._on_selection)

        # ── Empty state overlay ───────────────────────────────────────────────
        self._empty_lbl = QLabel(
            "Watchlist is empty.\n\nType a symbol below and click ➕ Add,\n"
            "or click 'Add to Watchlist' on any Screener result."
        )
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(f"color:{C.MUTED}; font-size:10pt;")

        # ── Bottom bar: status left, controls right ────────────────────────────
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(8)
        bottom_bar.addWidget(self._status_lbl)
        bottom_bar.addWidget(self._updated_lbl)
        bottom_bar.addStretch()
        bottom_bar.addWidget(self._sym_input)
        bottom_bar.addWidget(self._add_btn)
        bottom_bar.addWidget(self._remove_btn)
        bottom_bar.addWidget(self._refresh_btn)

        # ── Layout ────────────────────────────────────────────────────────────
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(6)
        layout.addWidget(self._view)
        layout.addWidget(self._empty_lbl)
        layout.addLayout(bottom_bar)
        layout.addSpacing(4)

        self._update_empty_state()
        svc.watchlist_updated.connect(self._on_data_updated)

    def add_symbol(self, symbol: str) -> None:
        """Public API — called by DashboardPanel.on_watchlist_add."""
        sym = symbol.strip().upper()
        if self._sp500 and sym not in self._sp500:
            QMessageBox.warning(
                self, "Not in S&P 500",
                "Only S&P 500 stocks can be added to the watchlist.",
            )
            return
        self._svc.add_to_watchlist(sym)

    def _on_add(self) -> None:
        sym = self._sym_input.text().strip().upper()
        if not sym:
            return
        if self._sp500 and sym not in self._sp500:
            QMessageBox.warning(
                self, "Not in S&P 500",
                "Only S&P 500 stocks can be added to the watchlist.",
            )
            return
        self._svc.add_to_watchlist(sym)
        self._sym_input.clear()

    def _on_remove(self) -> None:
        rows = self._view.selectionModel().selectedRows()
        if not rows:
            return
        symbol = self._model.row_symbol(rows[0].row())
        if symbol:
            self._svc.remove_from_watchlist(symbol)

    def _on_manual_refresh(self) -> None:
        self._svc._refresh_watchlist()

    def _on_selection(self) -> None:
        has_row = bool(self._view.selectionModel().selectedRows())
        self._remove_btn.setEnabled(has_row)

    def _on_data_updated(self) -> None:
        items = self._svc.get_watchlist_items()
        self._model.refresh(items)
        n = len(items)
        if n == 0:
            self._status_lbl.setText("No symbols in watchlist")
        else:
            self._status_lbl.setText(f"{n} symbol{'s' if n != 1 else ''}")
        now = datetime.datetime.now().strftime("%H:%M:%S")
        self._updated_lbl.setText(f"Updated {now}")
        self._update_empty_state()

    def _update_empty_state(self) -> None:
        has_items = self._model.rowCount() > 0
        self._view.setVisible(has_items)
        self._empty_lbl.setVisible(not has_items)


# ── Dashboard panel ───────────────────────────────────────────────────────────

class DashboardPanel(QWidget):
    """
    FO-GUI-002 Dashboard Panel — TIKR terminal style.
    KPI cards → market pulse bar → positions splitter → trade history.
    """

    def __init__(self, demo: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._demo = demo

        # ── KPI stat cards ─────────────────────────────────────────────────────
        self._card_pnl    = _StatCard("Total P&L",             accent=C.GREEN)
        self._card_cap    = _StatCard("Capital Utilised",    accent=C.ORANGE)
        self._card_pos    = _StatCard("Open Positions",      accent=C.BLUE)
        self._card_equity = _StatCard("Account Equity",      accent=C.MAUVE)
        self._card_cash   = _StatCard("Available Cash",      accent=C.TEAL)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)
        for card in (self._card_pnl, self._card_cap, self._card_pos, self._card_equity, self._card_cash):
            cards_row.addWidget(card)

        # ── Admin user-scope pill strip ──────────────────────────────────────────────
        self._scope_strip = QWidget()
        self._scope_strip.setObjectName("scope_strip")
        self._scope_strip.setFixedHeight(32)
        ss_row = QHBoxLayout(self._scope_strip)
        ss_row.setContentsMargins(8, 0, 8, 0)
        ss_row.setSpacing(4)
        self._scope_lbl = QLabel("👥  View:")
        self._scope_lbl.setFixedHeight(20)
        self._scope_lbl.setStyleSheet("font-size:8pt; font-weight:bold;")
        ss_row.addWidget(self._scope_lbl)

        self._scope_pills: dict[object, QPushButton] = {}  # uid:None | int -> button
        users = demo.get_users()

        def _make_pill(label: str, uid, first: bool = False) -> QPushButton:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.setFixedHeight(20)
            if first:
                btn.setChecked(True)
            btn.clicked.connect(lambda _c, u=uid: demo.set_viewing_uid(u))
            ss_row.addWidget(btn)
            return btn

        self._scope_pills[None] = _make_pill("🌐 All", None, first=True)
        for u in users:
            self._scope_pills[u.user_id] = _make_pill(f"🔵 {u.username}", u.user_id)
        ss_row.addStretch()
        self._restyle_scope_strip()

        demo.viewing_changed.connect(self._on_scope_changed)

        # ── Market pulse bar ───────────────────────────────────────────────────────
        self._pulse = _MarketPulseBar()

        # ── Open positions table (Positions tab) ──────────────────────────────
        self._pos_model = PositionTableModel()
        self._pos_view  = QTableView()
        self._pos_view.setModel(self._pos_model)
        self._pos_view.setAlternatingRowColors(True)
        self._pos_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._pos_view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._pos_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._pos_view.horizontalHeader().setStretchLastSection(True)
        self._pos_view.verticalHeader().setVisible(False)
        _resize_columns(self._pos_view, {0: 80, 1: 55, 8: 120})

        # ── Position action toolbar ────────────────────────────────────────────
        self._sq_all_btn = QPushButton("⚡  Square Off All")
        self._sq_all_btn.setObjectName("danger_btn")
        self._sq_all_btn.setToolTip("Close all open positions at market price")
        self._pos_status_lbl = QLabel("Double-click a row to manage")
        self._pos_status_lbl.setStyleSheet(f"color:{C.MUTED}; font-size:8pt;")

        pos_toolbar = QHBoxLayout()
        pos_toolbar.setSpacing(8)
        pos_toolbar.addWidget(self._pos_status_lbl)
        pos_toolbar.addStretch()
        pos_toolbar.addWidget(self._sq_all_btn)

        self._pos_view.selectionModel().selectionChanged.connect(self._on_pos_selection)
        self._pos_view.doubleClicked.connect(lambda _: self._on_manage_selected())
        self._sq_all_btn.clicked.connect(self._on_square_off_all)

        pos_tab = QWidget()
        pos_tab_layout = QVBoxLayout(pos_tab)
        pos_tab_layout.setContentsMargins(4, 8, 4, 4)
        pos_tab_layout.setSpacing(6)
        pos_tab_layout.addWidget(self._pos_view)
        pos_tab_layout.addLayout(pos_toolbar)

        # ── Trade history table (History tab) ─────────────────────────────────
        self._hist_model = TradeHistoryModel()
        self._hist_view  = QTableView()
        self._hist_view.setModel(self._hist_model)
        self._hist_view.setAlternatingRowColors(True)
        self._hist_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._hist_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._hist_view.horizontalHeader().setStretchLastSection(True)
        self._hist_view.verticalHeader().setVisible(False)
        _resize_columns(self._hist_view, {0: 85, 1: 70, 2: 50, 3: 50})

        hist_tab = QWidget()
        hist_tab_layout = QVBoxLayout(hist_tab)
        hist_tab_layout.setContentsMargins(4, 8, 4, 4)
        hist_tab_layout.setSpacing(6)
        hist_tab_layout.addWidget(self._hist_view)

        # ── Watchlist tab ──────────────────────────────────────────────────────
        self._watchlist_tab = _WatchlistTab(demo)

        # ── Market Watch tab ───────────────────────────────────────────────────
        self._mw_tab = _MarketWatchTab(demo)

        # ── QTabWidget: Positions | Trade History | Watchlist | Market Watch ──
        self._dash_tabs = QTabWidget()
        self._dash_tabs.setObjectName("dash_tabs")
        self._dash_tabs.addTab(pos_tab,              "📋  Open Positions")
        self._dash_tabs.addTab(hist_tab,             "📜  Trade History")
        self._dash_tabs.addTab(self._watchlist_tab,  "👁  Watchlist")
        self._dash_tabs.addTab(self._mw_tab,         "📊  Market Watch")

        # ── Live log feed (right panel) ────────────────────────────────────────
        # ── Embedded log section ──────────────────────────────────────────────
        self._log_paused     = False
        self._log_line_count = 0
        self._log_buffer: list[tuple[str, str]] = []

        log_hdr = QLabel("LIVE LOG")
        log_hdr.setStyleSheet(
            f"color:{C.ORANGE}; font-size:7pt; letter-spacing:1px; font-weight:bold;"
        )

        _lbl_lvl = QLabel("Level:")
        self._level_combo = QComboBox()
        self._level_combo.addItems(["ALL", "DEBUG", "INFO", "WARNING", "ERROR"])
        self._level_combo.setCurrentText("ALL")
        self._level_combo.setFixedWidth(100)
        self._level_combo.currentTextChanged.connect(self._reapply_log_filter)

        _lbl_srch = QLabel("Search:")
        self._log_search = QLineEdit()
        self._log_search.setPlaceholderText("Filter by keyword…")
        self._log_search.setFixedWidth(220)
        self._log_search.textChanged.connect(self._reapply_log_filter)

        self._log_auto_scroll = QCheckBox("Auto-scroll")
        self._log_auto_scroll.setChecked(True)

        self._pause_btn = QPushButton("⏸  Pause")
        self._pause_btn.setFixedWidth(90)
        self._pause_btn.clicked.connect(self._toggle_log_pause)

        self._clear_btn = QPushButton("🗑  Clear")
        self._clear_btn.setFixedWidth(90)
        self._clear_btn.clicked.connect(self._clear_log)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        filter_row.addWidget(log_hdr)
        filter_row.addSpacing(8)
        filter_row.addWidget(_lbl_lvl)
        filter_row.addWidget(self._level_combo)
        filter_row.addWidget(_lbl_srch)
        filter_row.addWidget(self._log_search)
        filter_row.addWidget(self._log_auto_scroll)
        filter_row.addStretch()
        filter_row.addWidget(self._pause_btn)
        filter_row.addWidget(self._clear_btn)

        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        _lf = QFont("Consolas", 9)
        _lf.setStyleHint(QFont.StyleHint.Monospace)
        self._log_view.setFont(_lf)
        self._log_view.setFixedHeight(180)

        self._log_count_lbl = QLabel("0 entries")
        self._log_count_lbl.setStyleSheet(f"color: {C.MUTED}; font-size: 8pt;")

        demo.log_message.connect(self._on_log_message)

        # ── Main layout ────────────────────────────────────────────────────────
        main = QVBoxLayout(self)
        main.setSpacing(10)
        main.setContentsMargins(14, 14, 14, 14)
        main.addLayout(cards_row)
        main.addWidget(self._scope_strip)
        main.addWidget(self._dash_tabs, 1)
        main.addLayout(filter_row)
        main.addWidget(self._log_view)
        main.addWidget(self._log_count_lbl)

        # ── Signals ────────────────────────────────────────────────────────────────
        demo.positions_updated.connect(self._refresh_positions)
        demo.account_updated.connect(self._refresh_account)
        demo.viewing_changed.connect(self._refresh_positions)
        demo.viewing_changed.connect(self._refresh_account)
        demo.exchange_unavail_updated.connect(self._pos_model.set_exchange_unavailable)
        self._on_scope_changed()   # initialise User column & column widths for current scope
        self._refresh_positions()
        self._refresh_account()

    # ── Theme-aware scope strip ───────────────────────────────────────────────────────

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.StyleChange:
            self._restyle_scope_strip()

    def _restyle_scope_strip(self) -> None:
        _tc = colors()
        _ss_bg  = _tc["scope_strip_bg"]
        _ss_brd = _tc["scope_strip_border"]
        _pill_mu = _tc["scope_pill_muted"]
        _pill_ov = _tc["scope_pill_border"]
        _pill_ck_bg = _tc["scope_pill_checked_bg"]
        _pill_ck_fg = _tc["scope_pill_checked_fg"]
        _pill_ck_bd = _tc["scope_pill_checked_bd"]
        self._scope_strip.setStyleSheet(
            f"QWidget#scope_strip {{ background:{_ss_bg}; border:1px solid {_ss_brd};"
            f" border-radius:4px; }}"
        )
        self._scope_lbl.setStyleSheet(
            f"color:{_pill_mu}; font-size:8pt; font-weight:bold;"
        )
        pill_qss = (
            f"QPushButton {{ background:transparent; color:{_pill_mu}; border:1px solid {_pill_ov};"
            f" border-radius:10px; padding:0 10px; font-size:8pt; }}"
            f"QPushButton:checked {{ background:{_pill_ck_bg}; color:{_pill_ck_fg};"
            f" border:1px solid {_pill_ck_bd}; font-weight:bold; }}"
            f"QPushButton:focus {{ outline: none; }}"
        )
        for btn in self._scope_pills.values():
            btn.setStyleSheet(pill_qss)

    # ── Scope pill sync ───────────────────────────────────────────────────────────────

    def _on_scope_changed(self) -> None:
        uid = self._demo.get_viewing_uid()
        # Sync pill highlight (scope could have changed from title bar dropdown)
        for pill_uid, btn in self._scope_pills.items():
            btn.blockSignals(True)
            btn.setChecked(pill_uid == uid)
            btn.blockSignals(False)
        # Toggle User column in positions and trade history models
        all_view = uid is None
        if all_view:
            labels = {u.user_id: u.username for u in self._demo.get_users()}
        else:
            labels = {}
        self._pos_model.set_show_user(all_view, labels if all_view else None)
        self._hist_model.set_show_user(all_view, labels if all_view else None)
        self._pos_view.clearSelection()
        # Resize columns when User col appears/disappears
        shift = 1 if all_view else 0
        _resize_columns(self._pos_view, {0: 70 if all_view else 80,
                                          shift + 1: 55,
                                          shift + 8: 120})
        _resize_columns(self._hist_view, {0: 70 if all_view else 85,
                                           shift + 1: 70, shift + 2: 55, shift + 3: 45})

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _refresh_positions(self) -> None:
        positions = self._demo.get_positions()
        self._pos_model.refresh(positions)
        self._card_pos.set_value(str(len(positions)), C.BLUE)
        n = len(positions)
        self._pos_status_lbl.setText(
            f"{n} open position{'s' if n != 1 else ''}  ·  prices streaming live"
        )
        self._sq_all_btn.setEnabled(n > 0)

    def on_watchlist_add(self, symbol: str) -> None:
        """Called by MainWindow when screener requests adding symbol to watchlist."""
        self._watchlist_tab.add_symbol(symbol)
        self._demo.log_message.emit("INFO", f"Watchlist: {symbol} added from screener")

    # ── Position toolbar actions ───────────────────────────────────────────────

    def _on_pos_selection(self) -> None:
        rows = self._pos_view.selectionModel().selectedRows()
        if rows:
            positions = self._demo.get_positions()
            row = rows[0].row()
            if row < len(positions):
                pos = positions[row]
                self._pos_status_lbl.setText(
                    f"{pos.symbol} selected  ·  Double-click to manage"
                )
        else:
            self._pos_status_lbl.setText("Double-click a row to manage")

    def _on_square_off_all(self) -> None:
        positions = self._demo.get_positions()
        if not positions:
            return
        uid = self._demo.get_viewing_uid()
        scope_txt = "ALL users" if uid is None else f"<b>{self._demo.get_user_label()}</b>"
        ret = QMessageBox.warning(
            self,
            "Square Off All",
            f"Close <b>all {len(positions)} open positions</b> for {scope_txt} at market price?<br>"
            f"<span style='color:gray;font-size:9pt;'>This action cannot be undone.</span>",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ret == QMessageBox.StandardButton.Yes:
            for pos in positions:
                self._demo.close_position(pos.symbol, pos.user_id)

    def _on_manage_selected(self) -> None:
        rows = self._pos_view.selectionModel().selectedRows()
        if not rows:
            return
        positions = self._demo.get_positions()
        row = rows[0].row()
        if row >= len(positions):
            return
        pos = positions[row]
        # Highlight the row in red while the dialog is open
        self._pos_model.set_highlighted_row(row)
        # Resolve user name for the admin "acting for" banner
        u = self._demo.get_user_by_id(pos.user_id)
        user_name = u.username if u else ""
        dlg = _ExitPositionDialog(pos, user_name, self)
        result = dlg.exec()
        # Clear row highlight regardless of dialog outcome
        self._pos_model.set_highlighted_row(-1)
        if result != QDialog.DialogCode.Accepted:
            return

        action = dlg.action
        params = dlg.params

        if action == "full_close":
            self._demo.close_position(pos.symbol, pos.user_id)

        elif action in ("partial_close", "limit_close"):
            qty = params["qty"]
            self._demo.partial_close_position(pos.symbol, qty, pos.user_id)
            if params.get("move_sl_to_be"):
                self._demo.set_stop_loss(pos.symbol, price=pos.average_price, user_id=pos.user_id)

        elif action == "set_stop_loss":
            self._demo.set_stop_loss(
                pos.symbol,
                price    = params["price"],
                user_id  = pos.user_id,
                trailing = params["trailing"],
                trail_by = params["trail_by"],
                trail_val= params["trail_val"],
            )

    def _refresh_account(self) -> None:
        acct = self._demo.get_account_state()
        self._refresh_trades()

        pnl = acct.daily_pnl
        pnl_colour = C.GREEN if pnl >= 0 else C.RED
        sign = "+" if pnl >= 0 else ""
        arrow = "▲" if pnl >= 0 else "▼"
        self._card_pnl.set_value(
            f"{sign}${pnl:,.2f}", pnl_colour,
            change=f"{arrow}  Unrealized", change_colour=pnl_colour
        )

        util = acct.capital_utilisation_pct
        cap_colour = C.RED if util > 90 else C.ORANGE if util > 70 else C.GREEN
        self._card_cap.set_value(
            f"{util:.1f}%", cap_colour,
            change=f"Limit: 95%", change_colour=C.MUTED
        )
        self._card_equity.set_value(
            f"${acct.equity:,.0f}", C.TEXT,
            change=f"Positions: ${acct.gross_position_value:,.0f}", change_colour=C.MUTED
        )
        self._card_cash.set_value(f"${acct.total_cash_value:,.0f}", C.TEAL)



    def _refresh_trades(self) -> None:
        trades = self._demo.get_all_trades()
        self._hist_model.refresh(trades)

    def _on_log_message(self, level: str, message: str) -> None:
        self._log_buffer.append((level, message))
        if len(self._log_buffer) > 10_000:
            self._log_buffer = self._log_buffer[-10_000:]
        if not self._log_paused and self._matches_log_filter(level, message):
            self._log_view.append(_html_entry(level, message))
            self._log_line_count += 1
            self._log_count_lbl.setText(f"{self._log_line_count} entries")
            if self._log_auto_scroll.isChecked():
                self._log_view.moveCursor(QTextCursor.MoveOperation.End)

    def _matches_log_filter(self, level: str, message: str) -> bool:
        selected = self._level_combo.currentText()
        if selected != "ALL":
            levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            try:
                if levels.index(level) < levels.index(selected):
                    return False
            except ValueError:
                pass
        kw = self._log_search.text().strip().lower()
        if kw and kw not in message.lower():
            return False
        return True

    def _reapply_log_filter(self) -> None:
        self._log_view.clear()
        self._log_line_count = 0
        for level, msg in self._log_buffer:
            if self._matches_log_filter(level, msg):
                self._log_view.append(_html_entry(level, msg))
                self._log_line_count += 1
        self._log_count_lbl.setText(f"{self._log_line_count} entries (filtered)")
        if self._log_auto_scroll.isChecked():
            self._log_view.moveCursor(QTextCursor.MoveOperation.End)

    def _toggle_log_pause(self) -> None:
        self._log_paused = not self._log_paused
        if self._log_paused:
            self._pause_btn.setText("▶  Resume")
            self._pause_btn.setStyleSheet(f"color: {C.YELLOW};")
        else:
            self._pause_btn.setText("⏸  Pause")
            self._pause_btn.setStyleSheet("")
            self._reapply_log_filter()

    def _clear_log(self) -> None:
        self._log_buffer.clear()
        self._log_view.clear()
        self._log_line_count = 0
        self._log_count_lbl.setText("0 entries")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resize_columns(view: QTableView, fixed: dict[int, int]) -> None:
    h = view.horizontalHeader()
    for col in range(view.model().columnCount() if view.model() else 0):
        if col in fixed:
            h.resizeSection(col, fixed[col])
            h.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        else:
            h.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)


def _padded(layout: QVBoxLayout) -> QVBoxLayout:
    w = QVBoxLayout()
    w.setContentsMargins(0, 8, 0, 0)
    w.addLayout(layout)
    return w
