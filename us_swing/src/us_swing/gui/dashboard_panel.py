"""
Module: MD-GUI-002.001.M01 — dashboard_panel.py
Parent SRD: SRD-GUI-002.001 – SRD-GUI-002.008, SRD-GUI-025.001 – SRD-GUI-025.015

Dashboard: KPI strip and four tiles — open positions, market watch, trade history and
P&L by strategy (tiled workspace, FO-GUI-025).
"""
from __future__ import annotations

import csv
import datetime

import logging
from zoneinfo import ZoneInfo

from PyQt6.QtCore import (
    QAbstractTableModel,
    QEasingCurve,
    QModelIndex,
    QPoint,
    QPropertyAnimation,
    QSettings,
    QStringListModel,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QHideEvent,
    QKeyEvent,
    QKeySequence,
    QActionGroup,
    QResizeEvent,
    QShortcut,
    QShowEvent,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QCompleter,
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QFileDialog,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from us_swing.gui.app_service import AppService
from us_swing.gui.cards import GAP, card, gutter
from us_swing.gui.dashboard_tiles import (
    ROW_H,
    KpiStrip,
    StrategyPnlList,
    Tile,
    TileGrid,
    table_rows,
)
from us_swing.gui.performance_band import ExposureView, PerformanceBand
from us_swing.gui.screener_views import ChipGroup
from us_swing.gui.strategy_pnl_chart import money, since_iso
from us_swing.gui.strategy_store import load_strategies
from us_swing.gui._types import AccountState, OpenPosition
from us_swing.gui.position_table_model import PositionTableModel, TradeHistoryModel
from us_swing.gui.icons import icon_button, mark_danger, set_icon, set_tab_icon
from us_swing.gui.theme import C
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

class _ExitForm(QWidget):
    """
    Position-exit form shown in the Exit drawer (SRD-GUI-019.006).  Tabs:

      1. Market Exit   — full close at market (MKT)
      2. Limit Exit    — full or partial close at a limit price
      3. Scale Out     — partial close by qty / pct at market
      4. Stop / Trail  — set or update SL (fixed / trailing)

    Review shows what will be sent; Confirm emits ``submitted(action, params)``
    with the same values the old Exit Position dialog returned.
    """

    submitted = pyqtSignal(str, dict)
    cancelled = pyqtSignal()

    def __init__(self, pos: OpenPosition, user_name: str = "", tab: int = 0,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pos = pos
        self.action: str = ""
        self.params: dict = {}
        self._reviewing = False
        self._done = False
        self.setStyleSheet(_DLG_QSS)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(14, 12, 14, 14)
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

        # ── Review line (shown after Review) ──────────────────────────────────
        self._review_lbl = QLabel()
        self._review_lbl.setWordWrap(True)
        self._review_lbl.setStyleSheet(
            f"color:{C.RED}; border:1px solid {C.RED}; padding:8px; font-weight:bold;"
        )
        self._review_lbl.hide()
        content_layout.addWidget(self._review_lbl)

        # ── Back · Cancel · Review / Confirm ──────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._back_btn = QPushButton("Back")
        set_icon(self._back_btn, "arrow-left")
        self._back_btn.hide()
        self._cancel_btn = QPushButton("Cancel")
        self._confirm_btn = QPushButton("Review")
        set_icon(self._confirm_btn, "check", "go")
        self._back_btn.clicked.connect(self._on_back)
        self._cancel_btn.clicked.connect(self.cancelled)
        self._confirm_btn.clicked.connect(self._on_confirm)
        btn_row.addWidget(self._back_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._cancel_btn)
        btn_row.addWidget(self._confirm_btn)
        content_layout.addLayout(btn_row)

        root.addWidget(content, 1)
        self._tabs.setCurrentIndex(tab)

    # ── Title bar & summary card builders ────────────────────────────────────

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

        state_badge = QLabel("OPEN" if pos.quantity > 0 else "CLOSED")
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
        self._tabs.addTab(w, "Market Exit")
        set_tab_icon(self._tabs, self._tabs.count() - 1, "log-out", "danger")

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
        self._tabs.addTab(w, "Limit Exit")
        set_tab_icon(self._tabs, self._tabs.count() - 1, "tag", "go")

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
        self._tabs.addTab(w, "Scale Out")
        set_tab_icon(self._tabs, self._tabs.count() - 1, "trending-down", "go")

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
        self._tabs.addTab(w, "Stop / Trail")
        set_tab_icon(self._tabs, self._tabs.count() - 1, "shield", "go")

    # ── Update helpers ────────────────────────────────────────────────────────

    def _update_confirm_label(self, idx: int) -> None:
        labels = ["Sell at Market", "Place Limit Order", "Scale Out", "Set Stop Loss"]
        self._confirm_btn.setText(labels[idx])
        is_sell = idx < 3
        self._confirm_btn.setProperty("role", "danger" if is_sell else "")
        set_icon(self._confirm_btn, "log-out" if is_sell else "shield", "danger" if is_sell else "go")
        style = self._confirm_btn.style()
        if style is not None:
            style.unpolish(self._confirm_btn)
            style.polish(self._confirm_btn)

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
        if self._reviewing:
            if self._done:
                return
            self._done = True
            self.setEnabled(False)
            self.submitted.emit(self.action, self.params)
            return
        self._collect()
        self._reviewing = True
        self._tabs.setEnabled(False)
        self._review_lbl.setText(f"This sends: {self._review_text()}")
        self._review_lbl.show()
        self._back_btn.show()
        self._update_confirm_label(self._tabs.currentIndex())

    def _on_back(self) -> None:
        self._reviewing = False
        self._tabs.setEnabled(True)
        self._review_lbl.hide()
        self._back_btn.hide()
        self._confirm_btn.setText("Review")
        self._confirm_btn.setProperty("role", "")
        set_icon(self._confirm_btn, "check", "go")
        style = self._confirm_btn.style()
        if style is not None:
            style.unpolish(self._confirm_btn)
            style.polish(self._confirm_btn)

    def _review_text(self) -> str:
        sym, p = self._pos.symbol, self.params
        if self.action == "full_close":
            return f"Sell {p['qty']} {sym} at market ({p['tif']})"
        if self.action == "limit_close":
            return f"Sell {p['qty']} {sym} at limit ${p['limit_price']:.2f} ({p['tif']})"
        if self.action == "partial_close":
            tail = " and move the stop to break-even" if p["move_sl_to_be"] else ""
            return f"Sell {p['qty']} {sym} at market{tail}"
        trail = f", trailing by {p['trail_val']:g} ({p['trail_by']})" if p["trailing"] else ""
        return f"Set the stop for {sym} at ${p['price']:.2f}{trail}"

    def _collect(self) -> None:
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


class _SquareOffForm(QWidget):
    """List of every open position with Review → Confirm (SRD-GUI-019.007)."""

    submitted = pyqtSignal(str, dict)
    cancelled = pyqtSignal()

    def __init__(self, positions: list[OpenPosition], scope_text: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._reviewing = False
        self._done = False
        self._count = len(positions)
        self._scope_text = scope_text

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)

        head = QLabel(f"Close all {len(positions)} open positions for {scope_text} at market")
        head.setWordWrap(True)
        layout.addWidget(head)

        table = QTableWidget(len(positions), 4)
        table.setHorizontalHeaderLabels(["Symbol", "Qty", "Price", "P&L"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        proceeds = 0.0
        total_pnl = 0.0
        for row, pos in enumerate(positions):
            pnl = (pos.current_price - pos.average_price) * pos.quantity
            proceeds += pos.current_price * pos.quantity
            total_pnl += pnl
            cells = [pos.symbol, str(pos.quantity), f"${pos.current_price:,.2f}", f"{pnl:+,.2f}"]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if col == 3:
                    item.setForeground(QColor(C.GREEN if pnl >= 0 else C.RED))
                table.setItem(row, col, item)
        layout.addWidget(table, 1)

        total = QLabel(f"Estimated proceeds ${proceeds:,.2f}  ·  Realised P&L {total_pnl:+,.2f}")
        total.setStyleSheet(f"color:{C.SUBTEXT};")
        layout.addWidget(total)

        self._review_lbl = QLabel(
            f"This sends {len(positions)} market sell orders for {scope_text}. It cannot be undone."
        )
        self._review_lbl.setWordWrap(True)
        self._review_lbl.setStyleSheet(
            f"color:{C.RED}; border:1px solid {C.RED}; padding:8px; font-weight:bold;"
        )
        self._review_lbl.hide()
        layout.addWidget(self._review_lbl)

        btn_row = QHBoxLayout()
        self._back_btn = QPushButton("Back")
        set_icon(self._back_btn, "arrow-left")
        self._back_btn.hide()
        cancel = QPushButton("Cancel")
        self._confirm_btn = QPushButton("Review")
        set_icon(self._confirm_btn, "check", "go")
        self._back_btn.clicked.connect(self._on_back)
        cancel.clicked.connect(self.cancelled)
        self._confirm_btn.clicked.connect(self._on_confirm)
        btn_row.addWidget(self._back_btn)
        btn_row.addStretch()
        btn_row.addWidget(cancel)
        btn_row.addWidget(self._confirm_btn)
        layout.addLayout(btn_row)

    def _on_confirm(self) -> None:
        if self._reviewing:
            if self._done:
                return
            self._done = True
            self.setEnabled(False)
            self.submitted.emit("square_off_all", {})
            return
        self._reviewing = True
        self._review_lbl.show()
        self._back_btn.show()
        self._confirm_btn.setText("Confirm Square Off")
        set_icon(self._confirm_btn, "square-x", "danger")
        mark_danger(self._confirm_btn)

    def _on_back(self) -> None:
        self._reviewing = False
        self._review_lbl.hide()
        self._back_btn.hide()
        self._confirm_btn.setText("Review")
        set_icon(self._confirm_btn, "check", "go")
        self._confirm_btn.setProperty("role", "")
        style = self._confirm_btn.style()
        if style is not None:
            style.unpolish(self._confirm_btn)
            style.polish(self._confirm_btn)


class _ExitDrawer(QFrame):
    """Non-modal panel that slides in from the right edge of the Dashboard."""

    WIDTH = 560
    closed = pyqtSignal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("exit_drawer")
        self.setStyleSheet(
            f"QFrame#exit_drawer {{ background:{C.BG}; border-left:1px solid {C.BLUE}; }}"
            f"QFrame#exit_drawer_hd {{ background:{C.SURFACE}; border-bottom:1px solid {C.OVERLAY}; }}"
        )
        self._open = False
        self._anim: QPropertyAnimation | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        head = QFrame()
        head.setObjectName("exit_drawer_hd")
        hl = QHBoxLayout(head)
        hl.setContentsMargins(14, 6, 6, 6)
        self._title = QLabel()
        self._title.setStyleSheet(f"color:{C.TEXT}; font-weight:bold; background:transparent;")
        close_btn = QPushButton()
        set_icon(close_btn, "x")
        close_btn.setFixedWidth(C.BTN_H)
        close_btn.setToolTip("Close")
        close_btn.setAccessibleName("Close")
        close_btn.clicked.connect(self.close_drawer)
        hl.addWidget(self._title)
        hl.addStretch()
        hl.addWidget(close_btn)
        layout.addWidget(head)
        self._body = QVBoxLayout()
        self._body.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._body, 1)
        self._form: QWidget | None = None
        self.hide()

    @property
    def is_open(self) -> bool:
        return self._open

    def open_with(self, form: QWidget, title: str) -> None:
        """Show ``form`` in the drawer and slide it in."""
        if self._form is not None:
            self._form.deleteLater()
        self._form = form
        self._body.addWidget(form)
        self._title.setText(title)
        self._open = True
        self.show()
        self.raise_()
        self.setFocus()
        self._slide(self._open_x())

    def close_drawer(self) -> None:
        if not self._open:
            return
        self._open = False
        self._slide(self._closed_x())
        self.closed.emit()

    def place(self) -> None:
        """Keep the drawer on the right edge after the Dashboard resizes."""
        parent = self.parentWidget()
        if parent is None:
            return
        self.setGeometry(self._open_x() if self._open else self._closed_x(), 0,
                         self.WIDTH, parent.height())

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        if event is not None and event.key() == Qt.Key.Key_Escape:
            self.close_drawer()
            return
        super().keyPressEvent(event)

    def _open_x(self) -> int:
        parent = self.parentWidget()
        return (parent.width() if parent else 0) - self.WIDTH

    def _closed_x(self) -> int:
        parent = self.parentWidget()
        return parent.width() if parent else 0

    def _slide(self, x: int) -> None:
        parent = self.parentWidget()
        self.resize(self.WIDTH, parent.height() if parent else self.height())
        if self._anim is not None:
            self._anim.stop()
        self._anim = QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.setEndValue(QPoint(x, 0))
        if not self._open:
            self._anim.finished.connect(lambda: None if self._open else self.hide())
        self._anim.start()


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
        self._removable = False

    def set_removable(self, on: bool) -> None:
        """Add a trailing remove-mark column (dashboard tile, SRD-GUI-025.012)."""
        self.beginResetModel()
        self._removable = on
        self.endResetModel()

    @property
    def remove_col(self) -> int:
        return len(self._COLS) if self._removable else -1

    def refresh(self, items: list[WatchlistItem]) -> None:
        self.beginResetModel()
        self._rows = list(items)
        self.endResetModel()

    def row_symbol(self, row: int) -> str:
        return self._rows[row].symbol if 0 <= row < len(self._rows) else ""

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._COLS) + (1 if self._removable else 0)

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self._COLS[section] if section < len(self._COLS) else ""
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        item = self._rows[index.row()]
        col  = index.column()

        if col == self.remove_col:
            return self._remove_mark(role)

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

    @staticmethod
    def _remove_mark(role: int) -> object:
        if role == Qt.ItemDataRole.DisplayRole:
            return "✕"
        if role == Qt.ItemDataRole.ToolTipRole:
            return "Remove from watchlist"
        if role == Qt.ItemDataRole.ForegroundRole:
            return QColor(C.MUTED)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter
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


# ── Watchlist tab widget ──────────────────────────────────────────────────────

class _WatchlistTab(QWidget):
    """Watchlist tab: add/remove symbols, live-refreshing quote table."""

    def __init__(self, svc: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._svc = svc

        # ── S&P 500 symbol set (validation + suggestions; refreshed on sp500_updated) ──
        self._sp500: frozenset[str] = frozenset()

        # ── Toolbar ───────────────────────────────────────────────────────────
        self._sym_input = QLineEdit()
        self._sym_input.setPlaceholderText("Symbol (e.g. AAPL)…")
        self._sym_input.setFixedWidth(160)
        # Suggestions start with the typed text, e.g. "a" → "AAPL — Apple Inc."
        self._completer = QCompleter(self)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._completer.setMaxVisibleItems(12)
        popup = self._completer.popup()
        assert popup is not None
        popup.setStyleSheet(
            f"QAbstractItemView {{ background:{C.SURFACE}; color:{C.TEXT};"
            f" border:1px solid {C.OVERLAY}; selection-background-color:{C.OVERLAY};"
            f" selection-color:{C.TEXT}; font-size:8pt; outline:none; }}"
        )
        self._sym_input.setCompleter(self._completer)
        self._refresh_suggestions()
        svc.sp500_updated.connect(self._refresh_suggestions)
        self._sym_input.returnPressed.connect(self._on_add)

        self._add_btn = QPushButton("Add")
        self._add_btn.setObjectName("btn_green")
        set_icon(self._add_btn, "plus", "add")
        self._add_btn.setFixedWidth(110)
        self._add_btn.clicked.connect(self._on_add)

        self._remove_btn = QPushButton("Remove")
        set_icon(self._remove_btn, "trash-2", "danger")
        mark_danger(self._remove_btn)
        self._remove_btn.setFixedWidth(110)
        self._remove_btn.setEnabled(False)
        self._remove_btn.clicked.connect(self._on_remove)

        self._refresh_btn = QPushButton("Refresh")
        set_icon(self._refresh_btn, "refresh-cw", "info")
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
        self._view.clicked.connect(self._on_cell_clicked)

        # ── Empty state overlay ───────────────────────────────────────────────
        self._empty_lbl = QLabel(
            "Watchlist is empty.\n\nType a symbol below and click Add,\n"
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

    def set_compact(self) -> None:
        """Fit the narrow right panel: key columns only, icon-only buttons."""
        for col in range(self._model.columnCount()):
            self._view.setColumnHidden(col, col not in (0, 1, 3))
        self._view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._sym_input.setMinimumWidth(0)
        self._sym_input.setMaximumWidth(16_777_215)
        for btn, tip in ((self._add_btn, "Add"), (self._remove_btn, "Remove"),
                         (self._refresh_btn, "Refresh")):
            btn.setText("")
            btn.setFixedWidth(C.BTN_H + 4)
            btn.setToolTip(tip)
            btn.setAccessibleName(tip)
        self._status_lbl.hide()
        self._updated_lbl.hide()

    def tile_tools(self) -> list[QWidget]:
        """Fit a dashboard tile: key columns and a ✕ per row; returns the header controls."""
        self._model.set_removable(True)
        remove_col = self._model.remove_col
        for col in range(self._model.columnCount()):
            self._view.setColumnHidden(col, col not in (0, 1, 2, 3, 7, remove_col))
        header = self._view.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(remove_col, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(remove_col, 32)
        self._sym_input.setFixedWidth(120)
        self._sym_input.setPlaceholderText("+ Add symbol")
        self._add_btn.setFixedWidth(70)
        self._refresh_btn.setText("")
        self._refresh_btn.setFixedWidth(C.BTN_H + 4)
        self._refresh_btn.setToolTip("Refresh")
        self._refresh_btn.setAccessibleName("Refresh")
        self._remove_btn.hide()
        self._status_lbl.hide()
        self._updated_lbl.hide()
        self._empty_lbl.setText("Watchlist is empty.\n\nType a symbol above and click Add.")
        return [self._sym_input, self._add_btn, self._refresh_btn]

    def _on_cell_clicked(self, index: QModelIndex) -> None:
        if index.column() == self._model.remove_col:
            symbol = self._model.row_symbol(index.row())
            if symbol:
                self._svc.remove_from_watchlist(symbol)

    def reload(self) -> None:
        """Load the current watchlist quotes now instead of waiting for the next update."""
        self._on_data_updated()

    @property
    def table_view(self) -> QTableView:
        return self._view

    @property
    def symbol_count(self) -> int:
        return self._model.rowCount()

    def add_symbol(self, symbol: str) -> None:
        """Public API — called by DashboardPanel.on_watchlist_add."""
        sym = symbol.strip().upper()
        if self._sp500 and sym not in self._sp500:
            self._warn_not_sp500(sym)
            return
        self._svc.add_to_watchlist(sym)

    def _warn_not_sp500(self, sym: str) -> None:
        # Imported here: the module pulls in the execution package, which must not load
        # before the app has set up the database modules.
        from us_swing.gui.active_cycles_panel import _ConfirmDialog

        _ConfirmDialog(
            "NOT IN S&P 500",
            f"{sym} is not an S&P 500 stock\n"
            "Only S&P 500 stocks can be added to the watchlist. "
            "Pick one from the suggestions as you type.",
            confirm_text="OK", accent=C.YELLOW, show_cancel=False, parent=self,
        ).exec()

    def _refresh_suggestions(self) -> None:
        records = self._svc.get_sp500_universe()
        self._sp500 = frozenset(r.symbol.upper() for r in records)
        items = sorted(f"{r.symbol} - {r.name}" for r in records)
        self._completer.setModel(QStringListModel(items, self._completer))

    def _on_add(self) -> None:
        sym = self._sym_input.text().split(" - ")[0].strip().upper()
        if not sym:
            return
        if self._sp500 and sym not in self._sp500:
            self._warn_not_sp500(sym)
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

    position_selected = pyqtSignal(object, str)   # OpenPosition | None, user name

    def __init__(
        self,
        demo: AppService,
        parent: QWidget | None = None,
        settings: QSettings | None = None,
    ) -> None:
        super().__init__(parent)
        self._demo = demo

        self._settings = settings or QSettings("USSwing", "DashboardPanel")

        # ── KPI strip with the view and density switches (SRD-GUI-025.001/.002) ─
        self._kpi = KpiStrip()
        self._view_uids: list[int | None] = [None] + [u.user_id for u in demo.get_users()]
        self._view_chips = ChipGroup(
            [("All users", None)] + [(u.username, str(u.user_id)) for u in demo.get_users()]
        )
        self._view_chips.changed.connect(self._on_view_chip)
        self._density_chips = ChipGroup([("Comfort", "comfort"), ("Compact", "compact")])
        self._density_chips.changed.connect(self._on_density_chip)
        self._kpi.tail.addWidget(self._view_chips)
        self._kpi.tail.addWidget(self._density_chips)

        # ── Performance band and its toggle (SRD-GUI-025.013/.014) ────────────
        self._perf_band = PerformanceBand()
        self._perf_band.ranges.changed.connect(self._on_perf_range)
        self._perf_card = card(self._perf_band)
        self._perf_btn = icon_button("chart-line", "info", "Show or hide the equity graph")
        self._perf_btn.setText("Performance")
        self._perf_btn.setCheckable(True)
        self._perf_btn.toggled.connect(self._on_perf_toggled)
        self._kpi.tail.addWidget(self._perf_btn)

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
        _resize_columns(self._pos_view, {0: 80, 1: 60, 2: 55, 9: 120})

        # ── Position action toolbar ────────────────────────────────────────────
        self._sq_all_btn = QPushButton("Square Off All")
        set_icon(self._sq_all_btn, "square-x", "danger")
        mark_danger(self._sq_all_btn)
        self._sq_all_btn.setToolTip("Close all open positions at market price")

        self._pos_view.selectionModel().selectionChanged.connect(self._on_pos_selection)
        self._pos_view.doubleClicked.connect(lambda _: self.open_exit(0))
        self._sq_all_btn.clicked.connect(self._on_square_off_all)

        # ── Filter box and column chooser (SRD-GUI-025.008/.009) ──────────────
        self._positions: list[OpenPosition] = []
        self._pos_filter = QLineEdit()
        self._pos_filter.setPlaceholderText("Filter symbol")
        self._pos_filter.setFixedWidth(130)
        self._pos_filter.setClearButtonEnabled(True)
        self._pos_filter.hide()
        self._pos_filter.textChanged.connect(self._apply_pos_filter)
        self._filter_btn = icon_button("filter", "neutral", "Filter by symbol")
        self._filter_btn.setCheckable(True)
        self._filter_btn.setFixedWidth(C.BTN_H)
        self._filter_btn.toggled.connect(self._on_filter_toggled)
        self._cols_btn = icon_button("columns-3", "neutral", "Choose columns")
        self._cols_btn.setFixedWidth(C.BTN_H)
        self._cols_btn.clicked.connect(self._show_columns_menu)

        self._pos_model.modelReset.connect(self._on_pos_model_reset)

        # ── Open Positions | Exposure tabs (SRD-GUI-025.015) ──────────────────
        self._exposure = ExposureView()
        self._pos_stack = QStackedWidget()
        self._pos_stack.addWidget(self._pos_view)
        self._pos_stack.addWidget(self._exposure)
        self._pos_tabs = ChipGroup([("Open Positions", "list"), ("Exposure", "expo")])
        self._pos_tabs.changed.connect(self._on_pos_tab)
        self._expo_units = ChipGroup([("$ Value", "value"), ("% Equity", "pct")])
        self._expo_units.changed.connect(self._refresh_exposure)
        self._expo_units.hide()
        self._positions_equity = 0.0

        self._pos_tile = Tile("Open Positions", self._pos_stack)
        self._pos_tile.set_title_widget(self._pos_tabs)
        pos_tools: tuple[QWidget, ...] = (
            self._pos_filter, self._filter_btn, self._cols_btn, self._expo_units,
            self._sq_all_btn)
        for tool in pos_tools:
            self._pos_tile.add_tool(tool)
        self._pos_status_lbl = self._pos_tile.count_lbl
        self._pos_view.setToolTip("Double-click a row to manage the position")

        # ── Trade history table (History tab) ─────────────────────────────────
        self._hist_model = TradeHistoryModel(
            tz_provider=lambda: self._demo.get_system_config().market_timezone
        )
        self._hist_view  = QTableView()
        self._hist_view.setModel(self._hist_model)
        self._hist_view.setAlternatingRowColors(True)
        self._hist_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._hist_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._hist_view.horizontalHeader().setStretchLastSection(True)
        self._hist_view.verticalHeader().setVisible(False)
        _resize_columns(self._hist_view, {0: 85, 1: 70, 2: 50, 3: 50})
        self._hist_tile = Tile("Trade History", self._hist_view)

        # ── Range, state and export (SRD-GUI-025.010/.011) ────────────────────
        self._hist_choice: dict[str, str] = {}
        self._hist_range_btn = QPushButton()
        self._hist_state_btn = QPushButton()
        self._hist_range_btn.setMenu(
            self._choice_menu(self._hist_range_btn, _HIST_RANGES, "hist_range", ""))
        self._hist_state_btn.setMenu(
            self._choice_menu(self._hist_state_btn, _HIST_STATES, "hist_state", "State: "))
        self._hist_range_btn.setFixedWidth(90)
        self._hist_state_btn.setFixedWidth(130)
        self._export_btn = icon_button("download", "neutral", "Export CSV")
        self._export_btn.setFixedWidth(C.BTN_H)
        self._export_btn.clicked.connect(self._on_export)
        for button in (self._hist_range_btn, self._hist_state_btn, self._export_btn):
            self._hist_tile.add_tool(button)

        # ── Watchlist (shown in the main window's right panel) ────────────────
        self._watchlist_tab = _WatchlistTab(demo)

        # ── Market Watch tile: the user's watchlist (SRD-GUI-025.007) ─────────
        self._watch_list = _WatchlistTab(demo)
        self._watch_tile = Tile("Market Watch", self._watch_list)
        for tool in self._watch_list.tile_tools():
            self._watch_tile.add_tool(tool)
        demo.watchlist_updated.connect(self._refresh_watch_count)

        # ── P&L by Strategy tile (SRD-GUI-025.005) ────────────────────────────
        self._strategy_list = StrategyPnlList()
        self._strategy_tile = Tile("P&L by Strategy", self._strategy_list)
        self._strategy_tile.set_count("Today")

        # ── Tile grid (SRD-GUI-025.003/.004) ──────────────────────────────────
        self._grid = TileGrid({
            "positions": self._pos_tile, "watch": self._watch_tile,
            "history": self._hist_tile, "strategy": self._strategy_tile,
        })
        self._grid.changed.connect(lambda name: self._settings.setValue("maximised", name))

        # ── Main layout: cards on the gutter, like Screener and Execution ─────
        gutter(self)
        main = QVBoxLayout(self)
        main.setSpacing(GAP)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(card(self._kpi))
        main.addWidget(self._perf_card)
        main.addWidget(self._grid, 1)

        self._drawer = _ExitDrawer(self)
        self._drawer.closed.connect(self._on_drawer_closed)
        self._selected_pos: OpenPosition | None = None
        self._drawer_pos: OpenPosition | None = None
        self._drawer_count = 0
        self._esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self._esc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._esc.setEnabled(False)
        self._esc.activated.connect(self._drawer.close_drawer)

        # ── Signals ────────────────────────────────────────────────────────────────
        demo.positions_updated.connect(self._refresh_positions)
        demo.account_updated.connect(self._refresh_account)
        demo.viewing_changed.connect(self._refresh_positions)
        demo.viewing_changed.connect(self._refresh_account)
        demo.exchange_unavail_updated.connect(self._pos_model.set_exchange_unavailable)
        self._strategy_debounce = QTimer(self)
        self._strategy_debounce.setSingleShot(True)
        self._strategy_debounce.setInterval(200)
        self._strategy_debounce.timeout.connect(self._refresh_strategies)
        self._strategy_timer = QTimer(self)
        self._strategy_timer.setInterval(60_000)
        self._strategy_timer.timeout.connect(self._strategy_debounce.start)
        self._strategy_load_failed = False
        demo.viewing_changed.connect(self._strategy_debounce.start)
        demo.strategy_status_changed.connect(self._on_strategy_status)
        self._perf_debounce = QTimer(self)
        self._perf_debounce.setSingleShot(True)
        self._perf_debounce.setInterval(300)
        self._perf_debounce.timeout.connect(self._refresh_performance)
        self._strategy_timer.timeout.connect(self._perf_debounce.start)
        demo.viewing_changed.connect(self._perf_debounce.start)
        self._restore_settings()
        self._on_scope_changed()   # initialise User column & column widths for current scope
        self._refresh_positions()
        self._refresh_account()
        self._watch_list.reload()
        self._refresh_watch_count()
        self._refresh_strategies()

    def showEvent(self, event: QShowEvent | None) -> None:
        super().showEvent(event)
        self._strategy_timer.start()
        self._strategy_debounce.start()
        self._perf_debounce.start()

    def hideEvent(self, event: QHideEvent | None) -> None:
        super().hideEvent(event)
        self._strategy_timer.stop()

    def _on_strategy_status(self, _name: str, _state: str) -> None:
        self._strategy_debounce.start()

    # ── Switches and remembered layout (SRD-GUI-025.002/.006) ──────────────────────

    def _restore_settings(self) -> None:
        density = str(self._settings.value("density", "compact"))
        self._density_chips.buttons[1 if density == "compact" else 0].setChecked(True)
        self._apply_density()
        saved = str(self._settings.value("view_uid", ""))
        uid = int(saved) if saved.isdigit() else None
        if uid in self._view_uids and uid != self._demo.get_viewing_uid():
            self._demo.set_viewing_uid(uid)
        self._grid.set_maximised(str(self._settings.value("maximised", "")))
        self._perf_band.set_range(str(self._settings.value("perf_range", "1D")))
        shown = str(self._settings.value("perf_shown", "true")).lower() == "true"
        self._perf_btn.setChecked(shown)
        self._perf_card.setVisible(shown)

    # ── Performance band (SRD-GUI-025.013/.014) ───────────────────────────────────

    def _on_perf_toggled(self, on: bool) -> None:
        self._perf_card.setVisible(on)
        self._settings.setValue("perf_shown", "true" if on else "false")
        if on:
            self._perf_debounce.start()

    def _on_perf_range(self) -> None:
        self._settings.setValue("perf_range", self._perf_band.range_key)
        self._refresh_performance()

    def _refresh_performance(self) -> None:
        if self._perf_card.isHidden():
            return
        key = self._perf_band.range_key
        points = self._demo.get_equity_curve(key)
        try:
            tz = ZoneInfo(self._demo.get_system_config().market_timezone)
        except Exception:
            _log.warning("[Equity] Market time zone is not valid; showing US Eastern times")
            tz = ZoneInfo("US/Eastern")
        fmt = "%H:%M" if key == "1D" else "%b %d"

        def label(iso: str) -> str:
            moment = datetime.datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S")
            return moment.replace(tzinfo=datetime.timezone.utc).astimezone(tz).strftime(fmt)

        self._perf_band.show_curve(points, label)

    # ── Exposure tab (SRD-GUI-025.015) ────────────────────────────────────────────

    def _on_pos_tab(self) -> None:
        exposure = self._pos_tabs.value == "expo"
        self._pos_stack.setCurrentIndex(1 if exposure else 0)
        self._expo_units.setVisible(exposure)
        self._cols_btn.setVisible(not exposure)
        self._filter_btn.setVisible(not exposure)
        self._pos_filter.setVisible(not exposure and self._filter_btn.isChecked())
        self._refresh_exposure()

    def _refresh_exposure(self) -> None:
        self._exposure.show_positions(self._positions, self._positions_equity,
                                      self._expo_units.value == "pct")

    def _on_density_chip(self) -> None:
        self._settings.setValue("density", self._density_chips.value)
        self._apply_density()

    def _apply_density(self) -> None:
        height = ROW_H[self._density_chips.value or "compact"]
        for view in (self._pos_view, self._hist_view, self._watch_list.table_view):
            header = view.verticalHeader()
            if header is not None:
                header.setDefaultSectionSize(height)

    def _on_view_chip(self) -> None:
        value = self._view_chips.value
        uid = int(value) if value else None
        self._settings.setValue("view_uid", value or "")
        self._demo.set_viewing_uid(uid)

    def _on_scope_changed(self) -> None:
        uid = self._demo.get_viewing_uid()
        # Sync the view switch (scope could have changed from the title bar dropdown)
        if uid in self._view_uids:
            button = self._view_chips.buttons[self._view_uids.index(uid)]
            button.blockSignals(True)
            button.setChecked(True)
            button.blockSignals(False)
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
                                          shift + 1: 60,
                                          shift + 2: 55,
                                          shift + 9: 120})
        _resize_columns(self._hist_view, {0: 70 if all_view else 85,
                                           shift + 1: 70, shift + 2: 55, shift + 3: 45})

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _refresh_positions(self) -> None:
        positions = self._demo.get_positions()
        self._positions = positions
        self._pos_model.refresh(positions)
        n = len(positions)
        self._kpi.set_value("pos", str(n))
        unreal = sum(p.unrealised_pnl for p in positions)
        self._kpi.set_value("unreal", money(unreal), _pnl_colour(unreal))
        self._sq_all_btn.setEnabled(n > 0)
        self._refresh_exposure()
        self._check_drawer_positions(positions)

    # ── Positions filter and columns (SRD-GUI-025.008/.009) ───────────────────

    def _on_pos_model_reset(self) -> None:
        """A model reset clears hidden rows and columns; put them back."""
        self._apply_hidden_cols()
        self._apply_pos_filter()

    def _on_filter_toggled(self, on: bool) -> None:
        self._pos_filter.setVisible(on)
        if on:
            self._pos_filter.setFocus()
        else:
            self._pos_filter.clear()
        self._apply_pos_filter()

    def _apply_pos_filter(self) -> None:
        text = self._pos_filter.text().strip().upper()
        shown = 0
        for row, pos in enumerate(self._positions):
            hide = bool(text) and text not in pos.symbol.upper()
            self._pos_view.setRowHidden(row, hide)
            shown += not hide
        n = len(self._positions)
        count = f"{shown} of {n}" if text else str(n)
        self._pos_status_lbl.setText(f"{count}  ·  streaming")

    def _hidden_cols(self) -> set[str]:
        saved = str(self._settings.value("hidden_cols", ""))
        return {name for name in saved.split(",") if name}

    def _pos_col_names(self) -> list[str]:
        horizontal = Qt.Orientation.Horizontal
        return [str(self._pos_model.headerData(col, horizontal))
                for col in range(self._pos_model.columnCount())]

    def _columns_menu(self) -> QMenu:
        menu = QMenu(self)
        hidden = self._hidden_cols()
        for name in self._pos_col_names():
            action = menu.addAction(name)
            if action is None:
                continue
            action.setCheckable(True)
            action.setChecked(name not in hidden)
            action.setEnabled(name not in _ALWAYS_SHOWN)
            action.toggled.connect(lambda on, n=name: self._set_column_shown(n, on))
        return menu

    def _show_columns_menu(self) -> None:
        menu = self._columns_menu()
        menu.exec(self._cols_btn.mapToGlobal(self._cols_btn.rect().bottomLeft()))
        menu.deleteLater()

    def _set_column_shown(self, name: str, shown: bool) -> None:
        hidden = self._hidden_cols()
        if shown:
            hidden.discard(name)
        else:
            hidden.add(name)
        self._settings.setValue("hidden_cols", ",".join(sorted(hidden)))
        self._apply_hidden_cols()

    def _apply_hidden_cols(self) -> None:
        hidden = self._hidden_cols()
        for col, name in enumerate(self._pos_col_names()):
            self._pos_view.setColumnHidden(col, name in hidden and name not in _ALWAYS_SHOWN)

    def _check_drawer_positions(self, positions: list[OpenPosition]) -> None:
        """Close the drawer if the position it acts on has closed or changed size."""
        if not self._drawer.is_open:
            return
        if self._drawer_pos is None:
            if len(positions) != self._drawer_count:
                _log.info("[Positions] Square off form closed because open positions changed")
                self._drawer.close_drawer()
            return
        key = (self._drawer_pos.symbol, self._drawer_pos.user_id)
        row = next((i for i, p in enumerate(positions) if (p.symbol, p.user_id) == key), -1)
        if row < 0 or positions[row].quantity != self._drawer_pos.quantity:
            _log.info("[Positions] Exit form for %s closed because the position changed",
                      self._drawer_pos.symbol)
            self._drawer.close_drawer()
            return
        self._pos_model.set_highlighted_row(row)

    def _on_drawer_closed(self) -> None:
        self._pos_model.set_highlighted_row(-1)
        self._esc.setEnabled(False)
        self._drawer_pos = None

    @property
    def watchlist_widget(self) -> QWidget:
        """Watchlist widget; the main window shows it in its right panel."""
        return self._watchlist_tab

    def resizeEvent(self, event: QResizeEvent | None) -> None:
        super().resizeEvent(event)
        self._drawer.place()

    def on_watchlist_add(self, symbol: str) -> None:
        """Called by MainWindow when screener requests adding symbol to watchlist."""
        self._watchlist_tab.add_symbol(symbol)
        self._demo.log_message.emit("INFO", f"Watchlist: {symbol} added from screener")

    # ── Position toolbar actions ───────────────────────────────────────────────

    def _on_pos_selection(self) -> None:
        rows = self._pos_view.selectionModel().selectedRows()
        positions = self._demo.get_positions()
        pos = positions[rows[0].row()] if rows and rows[0].row() < len(positions) else None
        self._selected_pos = pos
        if pos is not None:
            user = self._demo.get_user_by_id(pos.user_id)
            self.position_selected.emit(pos, user.username if user else "")
        else:
            self.position_selected.emit(None, "")

    def _live_mode_blocked(self, action: str) -> bool:
        """Explain why an unrouted position edit is unavailable in live mode."""
        if not self._demo.live_mutations_blocked():
            return False
        QMessageBox.information(
            self, "Not Available in Live Mode",
            f"{action} is not available while the active user is in live mode.<br><br>"
            "This control only updates the on-screen position — it never sends an "
            "order to the broker, so the position would stay open.<br><br>"
            "Use the stop button on the <b>Active Trades</b> tab, which sends a real "
            "exit order.",
        )
        return True

    def _on_square_off_all(self) -> None:
        if self._live_mode_blocked("Square Off All"):
            return
        positions = self._demo.get_positions()
        if not positions:
            return
        uid = self._demo.get_viewing_uid()
        scope_txt = "all users" if uid is None else self._demo.get_user_label()
        self._pos_model.set_highlighted_row(-1)
        self._drawer_pos = None
        self._drawer_count = len(positions)
        self._esc.setEnabled(True)
        form = _SquareOffForm(positions, scope_txt)
        form.cancelled.connect(self._drawer.close_drawer)
        form.submitted.connect(lambda _a, _p, ps=positions: self._finish_square_off(ps))
        self._drawer.open_with(form, "Square Off All")

    def _finish_square_off(self, positions: list[OpenPosition]) -> None:
        self._drawer.close_drawer()
        if self._live_mode_blocked("Square Off All"):
            return
        for pos in positions:
            self._demo.close_position(pos.symbol, pos.user_id)

    def open_exit(self, tab: int = 0) -> None:
        """Open the Exit drawer for the selected position on ``tab`` (0–3)."""
        if self._live_mode_blocked("Managing a position"):
            return
        rows = self._pos_view.selectionModel().selectedRows()
        if not rows:
            return
        positions = self._demo.get_positions()
        row = rows[0].row()
        if row >= len(positions):
            return
        pos = positions[row]
        self._pos_model.set_highlighted_row(row)
        self._drawer_pos = pos
        self._esc.setEnabled(True)
        u = self._demo.get_user_by_id(pos.user_id)
        user_name = u.username if u else ""
        form = _ExitForm(pos, user_name, tab)
        form.cancelled.connect(self._drawer.close_drawer)
        form.submitted.connect(lambda a, p, ps=pos: self._finish_exit(ps, a, p))
        self._drawer.open_with(form, f"Exit Position · {pos.symbol}")

    def _finish_exit(self, pos: OpenPosition, action: str, params: dict) -> None:
        self._drawer.close_drawer()
        if self._live_mode_blocked("Managing a position"):
            return
        self._apply_exit(pos, action, params)

    def _apply_exit(self, pos: OpenPosition, action: str, params: dict) -> None:
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

        pnl = acct.equity - acct.start_of_day_equity   # realised + unrealised (SRD-GUI-025.018)
        self._kpi.set_value("pnl", money(pnl), _pnl_colour(pnl))
        util = acct.capital_utilisation_pct
        cap_colour = C.RED if util > 90 else C.ORANGE if util > 70 else C.TEXT
        self._kpi.set_value("cap", f"{util:.1f}%", cap_colour, sub="of 95%")
        self._kpi.set_value("equity", f"${acct.equity:,.2f}")
        self._kpi.set_value("cash", f"${acct.total_cash_value:,.2f}")
        self._positions_equity = acct.equity
        self._refresh_exposure()

    def _refresh_watch_count(self) -> None:
        self._watch_tile.set_count(str(self._watch_list.symbol_count))

    def _refresh_strategies(self) -> None:
        """Today's realised P&L per strategy for the viewing scope (SRD-GUI-025.005)."""
        try:
            names = [cfg.name for cfg in load_strategies()]
        except Exception:
            if not self._strategy_load_failed:
                _log.warning("[Strategy] Could not load the strategy list for the dashboard")
            self._strategy_load_failed = True
            return
        self._strategy_load_failed = False
        rows = []
        for name in names:
            summary = self._demo.get_strategy_pnl(name, since_iso("1"))
            open_n = len(self._demo.get_open_symbols_for_strategy(name))
            rows.append((name, f"{open_n} open", summary.today))
        self._strategy_list.set_rows(rows)

    def _refresh_trades(self) -> None:
        try:
            tz = ZoneInfo(self._demo.get_system_config().market_timezone)
        except Exception:
            tz = ZoneInfo("US/Eastern")
        now = datetime.datetime.now(tz)
        span = self._hist_choice.get("hist_range", "today")
        state = self._hist_choice.get("hist_state", "all")

        def in_range(entry: datetime.datetime) -> bool:
            if span == "all":
                return True
            local = entry.astimezone(tz)
            if span == "today":
                return local.date() == now.date()
            return local >= now - datetime.timedelta(days=int(span))

        trades = [
            t for t in self._demo.get_all_trades()
            if in_range(t.entry_time) and (state == "all" or str(t.order_state) == state)
        ]
        self._hist_model.refresh(trades)
        n = len(trades)
        label = _RANGE_LABELS[span]
        self._hist_tile.set_count(f"{label}  ·  {n} order{'s' if n != 1 else ''}")

    # ── Trade History menus and export (SRD-GUI-025.010/.011) ─────────────────

    def _choice_menu(self, button: QPushButton, options: list[tuple[str, str]],
                     key: str, prefix: str) -> QMenu:
        """One-choice menu on ``button``; the choice is remembered under ``key``."""
        values = [value for _text, value in options]
        saved = str(self._settings.value(key, values[0]))
        self._hist_choice[key] = saved if saved in values else values[0]
        menu = QMenu(button)
        group = QActionGroup(menu)
        for text, value in options:
            action = menu.addAction(text)
            if action is None:
                continue
            action.setCheckable(True)
            action.setChecked(value == self._hist_choice[key])
            group.addAction(action)
            action.triggered.connect(
                lambda _c, v=value, t=text: self._on_choice(button, key, prefix, v, t))
            if value == self._hist_choice[key]:
                button.setText(prefix + text)
        return menu

    def _on_choice(self, button: QPushButton, key: str, prefix: str,
                   value: str, text: str) -> None:
        self._hist_choice[key] = value
        self._settings.setValue(key, value)
        button.setText(prefix + text)
        self._refresh_trades()

    def _on_export(self) -> None:
        tz = ZoneInfo(self._demo.get_system_config().market_timezone)
        default = f"trade_history_{datetime.datetime.now(tz):%Y%m%d}.csv"
        path, _filter = QFileDialog.getSaveFileName(
            self, "Export Trade History", default, "CSV files (*.csv)")
        if path:
            self.export_history(path)

    def export_history(self, path: str) -> None:
        """Write the shown Trade History rows and columns to ``path`` as CSV."""
        rows = table_rows(self._hist_view)
        try:
            with open(path, "w", newline="", encoding="utf-8") as handle:
                csv.writer(handle).writerows(rows)
        except OSError as exc:
            _log.error("[Trade History] Could not save the file %s: %s", path, exc.strerror or exc)
            QMessageBox.warning(self, "Export Failed",
                                f"Could not save the file:\n{path}\n\n{exc.strerror or exc}")
            return
        _log.info("[Trade History] Saved %d order(s) to %s", max(len(rows) - 1, 0), path)


# ── Helpers ───────────────────────────────────────────────────────────────────

_HIST_RANGES = [("Today", "today"), ("7 days", "7"), ("30 days", "30"), ("All", "all")]
_RANGE_LABELS = {value: text for text, value in _HIST_RANGES}
_ALWAYS_SHOWN = ("Symbol", "User")
_HIST_STATES = [("All", "all"), ("Filled", "FILLED"), ("Partial", "PARTIAL_FILLED"),
                ("Cancelled", "CANCELLED"), ("Rejected", "REJECTED"), ("New", "NEW")]

def _pnl_colour(value: float) -> str:
    return str(C.GREEN if value > 0 else C.RED if value < 0 else C.TEXT)


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
