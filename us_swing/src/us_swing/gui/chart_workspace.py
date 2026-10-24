"""
Module: MD-GUI-026.001.M01 — Charts Workspace
Parent SRD: SRD-GUI-026.001

The Charts screen: a symbol source list, one large chart with a header, and a
collapsible Inspector, as three cards on the gutter (Focus + Inspector layout).
"""
from __future__ import annotations

import logging
from functools import partial
from typing import Any

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from us_swing.gui.app_service import AppService
from us_swing.gui.cards import GAP, card, gutter
from us_swing.gui.chart_inspector import ChartContext, Inspector, TradePlan, plan_rr
from us_swing.gui.chart_panel import CandleChartPanel
from us_swing.gui.chart_source_list import SourceList
from us_swing.gui.icons import set_icon
from us_swing.gui.screener_views import ChipGroup
from us_swing.gui.theme import active_palette

_log = logging.getLogger(__name__)

TIMEFRAMES: tuple[tuple[str, str], ...] = (("1D", "1d"), ("1W", "1w"))
DEFAULT_OVERLAYS: list[tuple[str, int]] = [("sma", 20), ("sma", 50)]
OVERLAY_KINDS = ("sma", "ema")
OVERLAY_LENGTHS = (9, 20, 50, 100, 200)
_MAX_LENGTH = 400
_SOURCE_W = 250
_INSPECTOR_W = 310


def parse_overlays(text: str) -> list[tuple[str, int]]:
    """``"sma:20,ema:9"`` → ``[("sma", 20), ("ema", 9)]``; bad or repeated entries dropped."""
    overlays: list[tuple[str, int]] = []
    for part in text.split(","):
        kind, _, length = part.strip().partition(":")
        if kind not in OVERLAY_KINDS or not length.isdigit():
            continue
        entry = (kind, int(length))
        if 1 <= entry[1] <= _MAX_LENGTH and entry not in overlays:
            overlays.append(entry)
    return overlays


def overlay_label(overlay: tuple[str, int]) -> str:
    return f"{overlay[0].upper()} {overlay[1]}"


class ChartWorkspace(QWidget):
    """Source list | chart | Inspector, with remembered tab, overlays and sections."""

    def __init__(self, svc: AppService, parent: QWidget | None = None,
                 settings: QSettings | None = None) -> None:
        super().__init__(parent)
        gutter(self)
        self._svc = svc
        self._settings = settings or QSettings("USSwing", "ChartWorkspace")
        self._edited_plans: dict[str, TradePlan] = {}
        self._names: dict[str, str] = {}
        saved = self._settings.value("overlays")
        self._overlays = (DEFAULT_OVERLAYS.copy() if saved is None
                          else parse_overlays(str(saved)))

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(GAP)

        self.source = SourceList(svc, self._settings)
        self.source.symbol_selected.connect(lambda s: self.open_symbol(s, self.timeframe))
        self._source_card = card(self.source)
        self._source_card.setFixedWidth(_SOURCE_W)
        row.addWidget(self._source_card)

        self.chart = CandleChartPanel(svc)
        self.chart.hide_toolbar()
        self.chart.set_rsi_pane(True)
        self.chart.set_overlays(self._overlays)
        self.chart.chart_loaded.connect(self._on_chart_loaded)
        column = QWidget()
        col = QVBoxLayout(column)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.addWidget(self._build_header())
        col.addWidget(self.chart, 1)
        row.addWidget(card(column), 1)

        self.inspector = Inspector(self._settings)
        self.inspector.plan_changed.connect(self._on_plan_edited)
        self._inspector_card = card(self.inspector)
        self._inspector_card.setFixedWidth(_INSPECTOR_W)
        row.addWidget(self._inspector_card)

        shown = str(self._settings.value("inspector_shown", "true")).lower() == "true"
        self._set_inspector_shown(shown)
        svc.sp500_updated.connect(self._names.clear)
        self._restyle()

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self) -> QWidget:
        header = QWidget()
        line = QHBoxLayout(header)
        line.setContentsMargins(14, 8, 10, 8)
        line.setSpacing(14)

        names = QVBoxLayout()
        names.setSpacing(0)
        top = QHBoxLayout()
        top.setSpacing(10)
        self.symbol_lbl = QLabel("Charts")
        self.symbol_lbl.setObjectName("page_title")
        top.addWidget(self.symbol_lbl)
        self.price_lbl = QLabel("")
        top.addWidget(self.price_lbl)
        self.change_lbl = QLabel("")
        top.addWidget(self.change_lbl)
        top.addStretch(1)
        names.addLayout(top)
        self.company_lbl = QLabel("Pick a symbol on the left")
        names.addWidget(self.company_lbl)
        line.addLayout(names)

        self.tf_chips = ChipGroup(list(TIMEFRAMES))
        self.tf_chips.changed.connect(self._on_timeframe)
        line.addWidget(self.tf_chips)

        self._overlay_row = QHBoxLayout()
        self._overlay_row.setSpacing(6)
        line.addLayout(self._overlay_row)
        self.add_overlay_btn = QPushButton("Overlay")
        set_icon(self.add_overlay_btn, "plus")
        self.add_overlay_btn.setToolTip("Add a moving average")
        self.add_overlay_btn.clicked.connect(self._show_overlay_menu)
        line.addWidget(self.add_overlay_btn)
        line.addStretch(1)

        self.inspector_btn = QPushButton()
        self.inspector_btn.setCheckable(True)
        set_icon(self.inspector_btn, "columns-3")
        self.inspector_btn.clicked.connect(self._set_inspector_shown)
        line.addWidget(self.inspector_btn)
        self._fill_overlay_chips()
        return header

    def _fill_overlay_chips(self) -> None:
        while self._overlay_row.count():
            item = self._overlay_row.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        for overlay in self._overlays:
            chip = QPushButton(f"{overlay_label(overlay)}  ✕")
            chip.setObjectName("filter_chip")
            chip.setToolTip(f"Remove {overlay_label(overlay)}")
            chip.setAccessibleName(f"Remove {overlay_label(overlay)}")
            chip.clicked.connect(partial(self.remove_overlay, overlay))
            self._overlay_row.addWidget(chip)

    def _show_overlay_menu(self) -> None:
        menu = QMenu(self)
        for kind in OVERLAY_KINDS:
            sub = menu.addMenu(kind.upper())
            assert sub is not None
            for length in OVERLAY_LENGTHS:
                overlay = (kind, length)
                action = sub.addAction(overlay_label(overlay))
                assert action is not None
                action.setEnabled(overlay not in self._overlays)
                action.triggered.connect(partial(self.add_overlay, overlay))
        menu.exec(self.add_overlay_btn.mapToGlobal(self.add_overlay_btn.rect().bottomLeft()))

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def timeframe(self) -> str:
        return self.tf_chips.value or "1d"

    @property
    def overlays(self) -> list[tuple[str, int]]:
        return list(self._overlays)

    def open_symbol(self, symbol: str, timeframe: str = "1d") -> None:
        """Load ``symbol`` in the chart and highlight it in the source list."""
        symbol = symbol.strip().upper()
        if not symbol:
            return
        for button, (_label, value) in zip(self.tf_chips.buttons, TIMEFRAMES):
            if value == timeframe:
                button.setChecked(True)
        self.source.select_symbol(symbol)
        self.chart.show_symbol(symbol, self.timeframe)
        if self.chart.current_symbol != symbol:
            self._show_quote(symbol, [])   # no bars: the chart shows its no-data page

    def add_overlay(self, overlay: tuple[str, int]) -> None:
        if overlay not in self._overlays:
            self._set_overlays([*self._overlays, overlay])

    def remove_overlay(self, overlay: tuple[str, int]) -> None:
        self._set_overlays([o for o in self._overlays if o != overlay])

    def refresh_theme(self, _theme_id: str = "") -> None:
        """Re-render the chart and restyle the cards in the new theme colours."""
        self.chart.refresh_theme(_theme_id)
        self.inspector.restyle()
        self.source.refresh()
        self._restyle()
        if self.chart.current_symbol:
            self._show_quote(self.chart.current_symbol, self.chart.candles)

    # ── Internals ─────────────────────────────────────────────────────────────

    def _set_overlays(self, overlays: list[tuple[str, int]]) -> None:
        self._overlays = overlays
        self._settings.setValue("overlays", ",".join(f"{k}:{n}" for k, n in overlays))
        self._fill_overlay_chips()
        self.chart.set_overlays(overlays)

    def _set_inspector_shown(self, shown: bool) -> None:
        self._inspector_card.setVisible(shown)
        self.inspector_btn.setChecked(shown)
        tip = "Hide Inspector" if shown else "Show Inspector"
        self.inspector_btn.setToolTip(tip)
        self.inspector_btn.setAccessibleName(tip)
        self._settings.setValue("inspector_shown", "true" if shown else "false")

    def _on_timeframe(self) -> None:
        symbol = self.chart.current_symbol
        if symbol:
            self.chart.show_symbol(symbol, self.timeframe)

    def _on_chart_loaded(self, symbol: str, timeframe: str) -> None:
        candles = self.chart.candles
        self._show_quote(symbol, candles)
        plan = self._plan_for(symbol)
        self._draw_plan(plan)
        risk_pct, equity = self._risk()
        self.inspector.update_context(ChartContext(
            symbol=symbol, timeframe=timeframe, candles=candles,
            plan=plan, risk_pct=risk_pct, equity=equity,
        ))

    def _on_plan_edited(self, plan: TradePlan) -> None:
        symbol = self.chart.current_symbol
        if symbol:
            self._edited_plans[symbol] = plan
            self._draw_plan(plan)

    def _draw_plan(self, plan: TradePlan | None) -> None:
        """Draw only a long-shaped plan; any other plan clears the lines."""
        valid = plan is not None and plan_rr(*plan.levels) is not None
        self.chart.set_plan(plan.levels if plan is not None and valid else None)

    def _plan_for(self, symbol: str) -> TradePlan | None:
        """Edited plan, else the screener's AI plan, else the open position's levels."""
        if symbol in self._edited_plans:
            return self._edited_plans[symbol]
        for entry in self._svc.get_latest_screener_results():
            if (entry.symbol == symbol and entry.plan_entry and entry.plan_stop
                    and entry.plan_target):
                return TradePlan(entry.plan_entry, entry.plan_stop, entry.plan_target)
        for pos in self._svc.get_positions():
            if pos.symbol == symbol and pos.quantity > 0 and pos.stop_loss > 0 \
                    and pos.target_price > 0:
                return TradePlan(pos.average_price, pos.stop_loss, pos.target_price)
        return None

    def _risk(self) -> tuple[float, float]:
        try:
            risk_pct = self._svc.get_active_user().risk_config.risk_per_trade_pct
            equity = self._svc.get_account_state().equity
        except Exception:  # noqa: BLE001
            _log.warning("[Charts] Could not read risk settings — size not shown")
            return 1.0, 0.0
        return float(risk_pct), float(equity)

    def _company(self, symbol: str) -> str:
        if not self._names:
            try:
                self._names = {r.symbol: r.name for r in self._svc.get_sp500_universe()}
            except Exception:  # noqa: BLE001
                _log.debug("[Charts] Company names are not available", exc_info=True)
        return self._names.get(symbol, "")

    def _show_quote(self, symbol: str, candles: list[dict[str, Any]]) -> None:
        ct: Any = active_palette()
        self.symbol_lbl.setText(symbol)
        self.company_lbl.setText(self._company(symbol))
        if not candles:
            self.price_lbl.setText("")
            self.change_lbl.setText("No data")
            self.change_lbl.setStyleSheet(f"color:{ct.SUBTEXT};")
            return
        last = float(candles[-1]["close"])
        self.price_lbl.setText(f"{last:,.2f}")
        if len(candles) < 2 or not candles[-2]["close"]:
            self.change_lbl.setText("")
            return
        prev = float(candles[-2]["close"])
        change = last - prev
        self.change_lbl.setText(f"{change:+,.2f} ({change / prev * 100:+.2f}%)")
        self.change_lbl.setStyleSheet(f"color:{ct.GREEN if change >= 0 else ct.RED};")

    def _restyle(self) -> None:
        ct: Any = active_palette()
        self.price_lbl.setStyleSheet(f"color:{ct.TEXT}; font-size:13pt;")
        self.company_lbl.setStyleSheet(f"color:{ct.SUBTEXT}; font-size:8pt;")
