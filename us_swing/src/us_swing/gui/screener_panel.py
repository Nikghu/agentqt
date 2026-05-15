"""
Module: MD-GUI-003.001.M01 — screener_panel.py  (v2 — Phase 5 GUI integration)
Parent SRD: SRD-SCR-007.001–012

Screener Panel — Preset-based v2:
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  TOOLBAR  (▶ Run Now · progress · ← date → · result count · + Watchlist) │
  ├──────────────────────┬───────────────────────────────────────────────────┤
  │  PRESET LIST (260px) │  RESULTS TABLE (sortable, score colour-coded)      │
  │  ────────────────    │  (Symbol | Score | Matched | Details)              │
  │  ADMIN PRESETS       │                                                    │
  │  · Daily RSI    [C]  │                                                    │
  │  MY PRESETS          │                                                    │
  │  · Custom       [W]  │                                                    │
  │  ────────────────    │                                                    │
  │  [＋ New Preset]     │                                                    │
  └──────────────────────┴───────────────────────────────────────────────────┘
"""
from __future__ import annotations

import csv
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from datetime import date as _date

from PyQt6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QPoint,
    QSize,
    QSortFilterProxyModel,
    Qt,
    QThread,
    QUrl,
    pyqtSignal,
)
from PyQt6.QtGui import QAction, QColor, QCursor, QFont, QPainter
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStyle,
    QStyledItemDelegate,
    QTabBar,
    QTabWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from us_swing.gui.ai_transcript_panel import AITranscriptPanel
from us_swing.gui.app_service import AppService
from us_swing.gui.chart_panel import _build_html as _build_chart_html
from us_swing.gui.theme import C
from us_swing.screener.screeners import _api_key_store
from us_swing.screener.storage import INPUT_COST_PER_1K, OUTPUT_COST_PER_1K
from us_swing.screener.screeners._cloud_ai_models import (
    ALL_MODEL_PRESETS as _CLOUD_AI_ALL_MODELS,
    DEFAULT_MODEL as _CLOUD_AI_DEFAULT_MODEL,
)

# Trading-style filter options (label → style_filter value or None).
_STYLE_OPTIONS: list[tuple[str, str | None]] = [
    ("All Styles",       None),
    ("Swing Trading",    "swing"),
    ("Day Trading",      "day"),
    ("Position Trading", "position"),
]

# Canonical display names for all registered screener IDs.
_SCREENER_DISPLAY: dict[str, str] = {
    "indicator_composite": "Indicators",
    "price_action":        "Price Action",
    "llm_local_mistral":   "Local AI",
    "ml_ensemble_v3":      "Machine Learning Models",
    "mcp":                 "MCP",
}


# ── Per-symbol display row ────────────────────────────────────────────────────

@dataclass
class _Row:
    symbol: str
    score: float
    details: str   # compact per-screener breakdown
    ai_reasoning: str = ""  # SRD-SCR-013.007: ≤50-word AI rationale (Stage 3)


# ── Results table model ───────────────────────────────────────────────────────

_CHART_COL = 1  # index of the Chart button column


_AI_REASONING_PREVIEW_CHARS = 60


class _ResultsModel(QAbstractTableModel):
    COLS = ["Symbol", "Chart", "Score", "Details", "AI Reasoning"]

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._rows: list[_Row] = []

    def load(self, rows: list[_Row]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def clear(self) -> None:
        self.load([])

    def row_at(self, index: int) -> _Row | None:
        if 0 <= index < len(self._rows):
            return self._rows[index]
        return None

    # ── QAbstractTableModel interface ──────────────────────────────────────

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return len(self.COLS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal:
            if role == Qt.ItemDataRole.DisplayRole:
                return self.COLS[section]
            if role == Qt.ItemDataRole.TextAlignmentRole:
                return Qt.AlignmentFlag.AlignCenter
            if role == Qt.ItemDataRole.FontRole:
                f = QFont()
                f.setPointSize(8)
                f.setBold(True)
                return f
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        r = self._rows[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            match col:
                case 0: return r.symbol
                case 1: return ""           # painted by _ChartButtonDelegate
                case 2: return f"{r.score:.3f}"
                case 3: return r.details
                case 4:
                    return r.ai_reasoning
            return ""

        if role == Qt.ItemDataRole.ToolTipRole:
            # Full reasoning text in tooltip when hovering AI column
            if col == 4 and r.ai_reasoning:
                return r.ai_reasoning
            return None

        if role == Qt.ItemDataRole.ForegroundRole:
            if col == 0:
                return QColor(C.BLUE)
            if col == 2:
                if r.score >= 0.70:
                    return QColor(C.GREEN)
                if r.score >= 0.40:
                    return QColor(C.YELLOW)
                return QColor(C.RED)
            return None

        if role == Qt.ItemDataRole.BackgroundRole:
            if col == 2:
                if r.score >= 0.70:
                    return QColor(C.PNL_POS_BG)
                if r.score >= 0.40:
                    return QColor("#2e2a14")
                return QColor(C.PNL_NEG_BG)
            return None

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (0, 2):
                return Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        if role == Qt.ItemDataRole.FontRole:
            if col == 0:
                f = QFont()
                f.setBold(True)
                return f
            if col == 2:
                f = QFont()
                f.setBold(True)
                f.setPointSize(10)
                return f

        return None


# ── Preset run worker ─────────────────────────────────────────────────────────

class _PresetRunWorker(QThread):
    finished = pyqtSignal(object)   # ScreenerRunResult
    failed   = pyqtSignal(str)

    def __init__(
        self,
        preset_id: str,
        user_id: str,
        svc: AppService,
        mgr: Any,
        storage: Any,
        timeframe: str = "1d",
        manual: bool = True,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._preset_id  = preset_id
        self._user_id    = user_id
        self._svc        = svc
        self._mgr        = mgr
        self._storage    = storage
        self._timeframe  = timeframe
        self._manual     = manual

    def run(self) -> None:
        try:
            import types
            from us_swing.screener.executor import PresetExecutor

            # Symbols: S&P 500 universe intersected with what's in the candle DB
            db_symbols = set(self._svc.get_candle_symbols())
            universe   = self._svc.get_sp500_universe()
            sp500      = [r.symbol for r in universe] if universe else []
            symbols    = [s for s in sp500 if s in db_symbols] if db_symbols else sp500

            if not symbols:
                self.failed.emit(
                    "No candle data found in the database.\n"
                    "Download data first via the Database tab."
                )
                return

            # Bulk-load bars; convert dicts → namespace objects (screener uses b.close etc.)
            # Fetch 300 bars (252+ needed for RS rank computation).
            # Include the benchmark symbol so the RS index filter can access it.
            from datetime import datetime as _dt, timezone as _tz
            try:
                benchmark_sym: str = self._svc.get_system_config().benchmark_symbol
            except Exception:
                benchmark_sym = "SPY"
            fetch_syms = symbols if benchmark_sym in symbols else symbols + [benchmark_sym]
            raw = self._svc.get_candles_bulk(fetch_syms, timeframe=self._timeframe, limit=300)

            def _parse_dt(s: str) -> _dt:
                try:
                    return _dt.fromisoformat(s).replace(tzinfo=_tz.utc)
                except Exception:
                    return _dt(1970, 1, 1, tzinfo=_tz.utc)

            bars: dict[str, list] = {
                sym: [
                    types.SimpleNamespace(
                        datetime=_parse_dt(b["datetime"]),
                        open=b["open"], high=b["high"],
                        low=b["low"],  close=b["close"],
                        volume=b["volume"],
                    )
                    for b in bar_list
                ]
                for sym, bar_list in raw.items()
            }

            # Only run screener on universe symbols that have bar data (exclude benchmark).
            symbols = [s for s in symbols if s in bars]
            if not symbols:
                self.failed.emit(
                    f"No {'daily' if self._timeframe == '1d' else 'weekly'} bars "
                    "found in the database for the selected universe."
                )
                return

            # SRD-SCR-013.006: provide a DatabaseManager handle so the
            # tool-augmented Stage-3 LLM path can fetch on-demand candle data.
            db_mgr: Any = None
            try:
                from us_swing.db.manager import DatabaseManager
                _candle_db_path = Path.home() / ".usswing" / "candles.db"
                if _candle_db_path.exists():
                    db_mgr = DatabaseManager(f"sqlite:///{_candle_db_path}")
            except Exception:  # noqa: BLE001
                db_mgr = None

            executor = PresetExecutor(
                db=db_mgr,
                preset_manager=self._mgr,
                storage=self._storage,
                max_workers=4,
            )
            result = executor.run_preset(
                preset_id=self._preset_id,
                user_id=self._user_id,
                manual=self._manual,
                symbols=symbols,
                bars=bars,
            )
            self.finished.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


# ── Model validation worker ───────────────────────────────────────────────────

class _ModelValidateWorker(QThread):
    done = pyqtSignal(bool, str)   # (ok, message)

    def __init__(self, model_id: str, parent: Any = None) -> None:
        super().__init__(parent)
        self._model_id = model_id

    def run(self) -> None:
        from us_swing.gui.ai_model_store import validate_model
        ok, msg = validate_model(self._model_id)
        self.done.emit(ok, msg)


# ── Chart button delegate ─────────────────────────────────────────────────────

class _ChartButtonDelegate(QStyledItemDelegate):
    """Paints a small clickable-looking 📈 button in the Chart column."""

    def paint(self, painter: QPainter, option: Any, index: Any) -> None:
        painter.save()
        rect = option.rect.adjusted(5, 3, -5, -3)
        is_hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        bg = QColor(C.BLUE)
        bg.setAlpha(70 if is_hovered else 30)
        border = QColor(C.BLUE)
        border.setAlpha(140)
        painter.setBrush(bg)
        painter.setPen(border)
        painter.drawRoundedRect(rect, 3, 3)
        painter.setPen(QColor(C.BLUE))
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "📈")
        painter.restore()

    def sizeHint(self, option: Any, index: Any) -> QSize:
        return QSize(56, 28)


# ── Quick chart window (multi-tab, frameless, one per symbol) ────────────────

class QuickChartWindow(QWidget):
    """Standalone frameless chart window opened from the Screener results table.

    Maintains one tab per symbol; clicking the same symbol again switches
    focus to the existing tab rather than opening a duplicate.  Tabs have no
    close button — the window is dismissed via the custom title-bar controls.
    """

    def __init__(self, svc: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self._svc = svc
        self._drag_pos: QPoint | None = None
        self._maximized = False

        self.setWindowTitle("Quick Chart Viewer")
        self.resize(960, 640)
        self.setStyleSheet(
            f"QWidget#qcw_root {{ background: {C.BG};"
            f" border: 1px solid {C.OVERLAY2}; }}"
        )

        root_widget = QWidget()
        root_widget.setObjectName("qcw_root")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(root_widget)

        self._layout = QVBoxLayout(root_widget)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self._title_bar = self._make_title_bar()
        self._layout.addWidget(self._title_bar)

        self._tabs = QTabWidget()
        self._tabs.setTabsClosable(False)
        self._tabs.setMovable(True)
        self._tabs.setStyleSheet(
            f"QTabWidget::pane {{ border: none; background: {C.BG}; }}"
            f"QTabBar::tab {{"
            f"  background: {C.SURFACE}; color: {C.SUBTEXT};"
            f"  border: 1px solid {C.OVERLAY}; border-bottom: none;"
            f"  padding: 5px 14px; font-size: 8pt; margin-right: 2px; }}"
            f"QTabBar::tab:selected {{"
            f"  background: {C.BG}; color: {C.TEXT}; border-color: {C.OVERLAY2}; }}"
            f"QTabBar::tab:hover:!selected {{ background: {C.OVERLAY}; }}"
        )
        self._layout.addWidget(self._tabs, 1)

    # ── Title bar ─────────────────────────────────────────────────────────────

    def _make_title_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("qcw_title")
        bar.setFixedHeight(38)
        bar.setStyleSheet(
            f"QFrame#qcw_title {{ background: {C.SURFACE};"
            f" border-bottom: 1px solid {C.OVERLAY}; }}"
        )
        hl = QHBoxLayout(bar)
        hl.setContentsMargins(14, 0, 6, 0)
        hl.setSpacing(0)

        icon = QLabel("📈")
        icon.setStyleSheet("background: transparent; font-size: 13px;")
        title_lbl = QLabel("  Quick Chart Viewer")
        title_lbl.setStyleSheet(
            f"color: {C.TEXT}; font-size: 9pt; font-weight: bold; background: transparent;"
        )
        hl.addWidget(icon)
        hl.addWidget(title_lbl)
        hl.addStretch()

        _wc = (
            "QPushButton {{ background: transparent; color: {fg}; border: none;"
            " font-size: 14px; min-width: 32px; max-width: 32px;"
            " min-height: 28px; max-height: 28px; border-radius: 4px; }}"
            "QPushButton:hover {{ background: {hover}; color: white; }}"
        )
        min_btn = QPushButton("−")
        min_btn.setStyleSheet(_wc.format(fg=C.SUBTEXT, hover=C.OVERLAY2))
        min_btn.setToolTip("Minimize")
        min_btn.clicked.connect(self.showMinimized)

        self._max_btn = QPushButton("□")
        self._max_btn.setStyleSheet(_wc.format(fg=C.SUBTEXT, hover=C.OVERLAY2))
        self._max_btn.setToolTip("Maximize")
        self._max_btn.clicked.connect(self._toggle_maximize)

        close_btn = QPushButton("✕")
        close_btn.setStyleSheet(_wc.format(fg=C.SUBTEXT, hover="#c0392b"))
        close_btn.setToolTip("Close")
        close_btn.clicked.connect(self.close)

        hl.addWidget(min_btn)
        hl.addSpacing(2)
        hl.addWidget(self._max_btn)
        hl.addSpacing(2)
        hl.addWidget(close_btn)
        return bar

    def _toggle_maximize(self) -> None:
        if self._maximized:
            self.showNormal()
            self._max_btn.setText("□")
            self._max_btn.setToolTip("Maximize")
        else:
            self.showMaximized()
            self._max_btn.setText("❐")
            self._max_btn.setToolTip("Restore")
        self._maximized = not self._maximized

    # ── Drag to move ──────────────────────────────────────────────────────────

    def mousePressEvent(self, event: Any) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._title_bar.geometry().contains(event.pos())
        ):
            self._drag_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: Any) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self.move(self.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: Any) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    # ── Chart management ──────────────────────────────────────────────────────

    def open_symbol(self, symbol: str, timeframe: str = "1d") -> None:
        """Switch to an existing tab for *symbol*, or create a new one."""
        for i in range(self._tabs.count()):
            if self._tabs.tabText(i) == symbol:
                self._tabs.setCurrentIndex(i)
                return
        web = self._make_chart_view(symbol, timeframe)
        idx = self._tabs.addTab(web, symbol)
        self._attach_close_btn(idx)
        self._tabs.setCurrentIndex(idx)

    def _attach_close_btn(self, tab_idx: int) -> None:
        """Add a visible custom × button to the right side of a tab."""
        # Capture the content widget — its Python identity stays stable across
        # tab shifts, unlike the button returned by tabButton() which PyQt6 may
        # re-wrap as a new Python object on every call.
        content_widget = self._tabs.widget(tab_idx)
        btn = QPushButton("×")
        btn.setFixedSize(18, 18)
        btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C.SUBTEXT};"
            f" border: none; font-size: 13px; border-radius: 3px;"
            f" padding: 0; line-height: 18px; }}"
            f"QPushButton:hover {{ background: #c0392b88; color: white; }}"
        )
        btn.clicked.connect(lambda _checked=False, w=content_widget: self._close_tab_for_widget(w))
        self._tabs.tabBar().setTabButton(tab_idx, QTabBar.ButtonPosition.RightSide, btn)

    def _close_tab_for_widget(self, widget: QWidget) -> None:
        idx = self._tabs.indexOf(widget)
        if idx >= 0:
            self._tabs.removeTab(idx)

    def closeEvent(self, event: Any) -> None:
        self._tabs.clear()
        super().closeEvent(event)

    def _make_chart_view(self, symbol: str, timeframe: str) -> QWebEngineView:
        web = QWebEngineView()
        web.setStyleSheet(f"background: {C.BG};")
        candles = self._svc.get_candles_for_symbol(symbol, timeframe, 500)
        if candles:
            volume_data = [
                {
                    "time": c["time"],
                    "value": c["volume"],
                    "color": "#26a69a55" if c["close"] >= c["open"] else "#ef535055",
                }
                for c in candles
            ]
            tz = self._svc.get_system_config().market_timezone
            html = _build_chart_html(candles, volume_data, symbol, timeframe, timezone=tz)
            web.setHtml(html, QUrl("about:blank"))
        else:
            web.setHtml(
                f"""<!DOCTYPE html><html><body style="margin:0;background:{C.BG};
                display:flex;align-items:center;justify-content:center;height:100vh;
                font-family:monospace;">
                <div style="text-align:center;color:{C.MUTED};">
                  <div style="font-size:36px;margin-bottom:12px;">⚠</div>
                  <div>No candle data for <b style="color:{C.YELLOW}">{symbol}</b>
                  ({timeframe.upper()})</div>
                  <div style="font-size:11px;margin-top:8px;">
                    Download data from Settings → Database.</div>
                </div></body></html>"""
            )
        return web


# ── Indicator filter defaults (mirrors indicator.py tightened defaults) ────────

_INDICATOR_DEFAULTS: dict[str, dict] = {
    "volatility": {"enabled": True,  "min_atr_pct": 0.01},
    "rsi":        {"enabled": True,  "min": 30, "max": 70, "period": 14},
    "range":      {"enabled": True,  "min_price": 5.0, "max_price": 5000.0},
    "breakout":   {"enabled": True,  "lookback": 10},
    "volume":     {"enabled": True,  "min_volume_ratio": 1.0, "ma_period": 10},
    "rs_index":   {"enabled": False, "rs_min_percentile": 70.0, "rs_slope_days": 63},
}

_INDICATOR_SCREENER_ID   = "indicator_composite"
_PRICE_ACTION_SCREENER_ID = "price_action"
_LLM_CLAUDE_SCREENER_ID  = "llm_claude_ranking"

# Screeners hidden from the "Add Screener" menu — still registered for backward compat with saved presets
_HIDDEN_SCREENER_IDS: frozenset[str] = frozenset({_LLM_CLAUDE_SCREENER_ID})

_CHECKBOX_QSS = f"QCheckBox {{ color: {C.TEXT}; font-size: 9pt; spacing: 6px; }}"


def _format_indicator_config(config: dict) -> str:
    """Return a compact one-line summary of an IndicatorScreener config dict.

    Example: ``RSI(30–70 p14) · ATR≥1% · $5–5K · BK10 · Vol≥1.0×``
    Disabled filters are omitted; missing keys fall back to _INDICATOR_DEFAULTS.
    """
    filters = config.get("filters", {})

    def _f(section: str) -> dict:
        d = dict(_INDICATOR_DEFAULTS[section])
        d.update(filters.get(section, {}))
        return d

    parts: list[str] = []

    v = _f("volatility")
    if v.get("enabled", True):
        pct = float(v["min_atr_pct"]) * 100
        parts.append(f"ATR≥{pct:.1f}%")

    r = _f("rsi")
    if r.get("enabled", True):
        parts.append(f"RSI({int(r['min'])}–{int(r['max'])} p{int(r['period'])})")

    p = _f("range")
    if p.get("enabled", True):
        lo = float(p["min_price"])
        hi = float(p["max_price"])
        lo_s = f"${lo:.0f}" if lo < 1000 else f"${lo/1000:.0f}K"
        hi_s = f"${hi:.0f}" if hi < 1000 else f"${hi/1000:.0f}K"
        parts.append(f"{lo_s}–{hi_s}")

    b = _f("breakout")
    if b.get("enabled", True):
        parts.append(f"BK{int(b['lookback'])}")

    vo = _f("volume")
    if vo.get("enabled", True):
        parts.append(f"Vol≥{float(vo['min_volume_ratio']):.1f}×")

    ri = _f("rs_index")
    if ri.get("enabled", False):
        rs_pct = float(ri["rs_min_percentile"])
        rs_sl = int(ri["rs_slope_days"])
        rs_part = f"RS≥{rs_pct:.0f}%"
        if rs_sl > 0:
            rs_part += f" sl{rs_sl}"
        parts.append(rs_part)

    return "  ·  ".join(parts) if parts else ""


def _hdivider() -> QFrame:
    """Thin horizontal rule used between sections in config dialogs."""
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(1)
    line.setStyleSheet(f"background: {C.OVERLAY}; border: none;")
    return line


# ── Shared frameless dialog base ──────────────────────────────────────────────

class _FramelessDialog(QDialog):
    """QDialog subclass: frameless OS chrome + custom title bar with min/max/close."""

    def __init__(
        self,
        title: str,
        min_width: int = 420,
        min_height: int = 0,
        extra_qss: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(min_width)
        if min_height:
            self.setMinimumHeight(min_height)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet(
            f"QDialog {{ background: {C.BG}; border: 1px solid {C.OVERLAY2}; }}"
            + extra_qss
        )
        self._drag_pos: QPoint | None = None
        self._maximized = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._title_bar = self._make_title_bar(title)
        outer.addWidget(self._title_bar)

        self._content = QWidget()
        self._content.setStyleSheet("QWidget { background: transparent; }")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(16, 12, 16, 12)
        self._content_layout.setSpacing(8)
        outer.addWidget(self._content, 1)

    def content_layout(self) -> QVBoxLayout:
        return self._content_layout

    def _make_title_bar(self, title: str) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(38)
        bar.setStyleSheet(
            f"QFrame {{ background: {C.SURFACE}; border-bottom: 1px solid {C.OVERLAY}; }}"
        )
        hl = QHBoxLayout(bar)
        hl.setContentsMargins(14, 0, 6, 0)
        hl.setSpacing(0)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"color: {C.TEXT}; font-size: 9pt; font-weight: bold; background: transparent;"
        )
        hl.addWidget(title_lbl)
        hl.addStretch()

        _wc_style = (
            "QPushButton {{ background: transparent; color: {fg}; border: none;"
            " font-size: 14px; min-width: 32px; max-width: 32px;"
            " min-height: 28px; max-height: 28px; border-radius: 4px; }}"
            "QPushButton:hover {{ background: {hover}; color: white; }}"
        )
        min_btn = QPushButton("−")
        min_btn.setStyleSheet(_wc_style.format(fg=C.SUBTEXT, hover=C.OVERLAY2))
        min_btn.setToolTip("Minimize")
        min_btn.clicked.connect(self.showMinimized)

        self._max_btn = QPushButton("□")
        self._max_btn.setStyleSheet(_wc_style.format(fg=C.SUBTEXT, hover=C.OVERLAY2))
        self._max_btn.setToolTip("Maximize")
        self._max_btn.clicked.connect(self._toggle_maximize)

        close_btn = QPushButton("✕")
        close_btn.setStyleSheet(_wc_style.format(fg=C.SUBTEXT, hover="#c0392b"))
        close_btn.setToolTip("Close")
        close_btn.clicked.connect(self.reject)

        hl.addWidget(min_btn)
        hl.addSpacing(2)
        hl.addWidget(self._max_btn)
        hl.addSpacing(2)
        hl.addWidget(close_btn)
        return bar

    def _toggle_maximize(self) -> None:
        if self._maximized:
            self.showNormal()
            self._max_btn.setText("□")
            self._max_btn.setToolTip("Maximize")
        else:
            self.showMaximized()
            self._max_btn.setText("❐")
            self._max_btn.setToolTip("Restore")
        self._maximized = not self._maximized

    def mousePressEvent(self, event: Any) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._title_bar.geometry().contains(event.pos())
        ):
            self._drag_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: Any) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self.move(self.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: Any) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)


# ── Indicator config dialog ───────────────────────────────────────────────────

class _IndicatorConfigDialog(_FramelessDialog):
    """View / edit the 5 filter params of IndicatorScreener for one ScreenerRef."""

    def __init__(self, config: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(
            "Indicator Filter Settings",
            min_width=480,
            extra_qss=f" {_CHECKBOX_QSS}",
            parent=parent,
        )

        supplied_filters = (config or {}).get("filters", {})
        def _f(section: str) -> dict:
            d = dict(_INDICATOR_DEFAULTS[section])
            d.update(supplied_filters.get(section, {}))
            return d

        root = self.content_layout()

        def _section(title: str) -> QLabel:
            lbl = QLabel(title)
            lbl.setStyleSheet(f"color: {C.BLUE}; font-weight: bold; font-size: 9pt;")
            return lbl

        def _lbl(text: str) -> QLabel:
            l = QLabel(text)
            l.setStyleSheet(f"color: {C.SUBTEXT}; font-size: 8pt;")
            return l

        def _spin_d(lo: float, hi: float, step: float, val: float, dec: int = 3) -> QDoubleSpinBox:
            s = QDoubleSpinBox()
            s.setRange(lo, hi)
            s.setSingleStep(step)
            s.setDecimals(dec)
            s.setValue(val)
            s.setFixedWidth(80)
            s.setStyleSheet(
                f"QDoubleSpinBox {{ background: {C.OVERLAY}; color: {C.TEXT};"
                f" border: 1px solid {C.OVERLAY}; border-radius: 3px; padding: 1px 4px; }}"
            )
            return s

        def _spin_i(lo: int, hi: int, val: int) -> QDoubleSpinBox:
            return _spin_d(lo, hi, 1.0, float(val), dec=0)

        # ── Volatility ────────────────────────────────────────────────────────
        v = _f("volatility")
        root.addWidget(_section("Volatility  (ATR %)"))
        vr = QHBoxLayout()
        self._vol_en  = QCheckBox("Enabled")
        self._vol_en.setChecked(bool(v["enabled"]))
        self._vol_atr = _spin_d(0.001, 0.10, 0.001, float(v["min_atr_pct"]), dec=3)
        vr.addWidget(self._vol_en)
        vr.addStretch()
        vr.addWidget(_lbl("Min ATR %:"))
        vr.addWidget(self._vol_atr)
        root.addLayout(vr)
        root.addWidget(_hdivider())

        # ── RSI ───────────────────────────────────────────────────────────────
        r = _f("rsi")
        root.addWidget(_section("RSI"))
        rr = QHBoxLayout()
        self._rsi_en     = QCheckBox("Enabled")
        self._rsi_en.setChecked(bool(r["enabled"]))
        self._rsi_min    = _spin_i(0, 100, int(r["min"]))
        self._rsi_max    = _spin_i(0, 100, int(r["max"]))
        self._rsi_period = _spin_i(5,  50, int(r["period"]))
        rr.addWidget(self._rsi_en)
        rr.addStretch()
        rr.addWidget(_lbl("Min:"))
        rr.addWidget(self._rsi_min)
        rr.addWidget(_lbl("Max:"))
        rr.addWidget(self._rsi_max)
        rr.addWidget(_lbl("Period:"))
        rr.addWidget(self._rsi_period)
        root.addLayout(rr)
        root.addWidget(_hdivider())

        # ── Price Range ───────────────────────────────────────────────────────
        p = _f("range")
        root.addWidget(_section("Price Range  ($)"))
        pr = QHBoxLayout()
        self._rng_en  = QCheckBox("Enabled")
        self._rng_en.setChecked(bool(p["enabled"]))
        self._rng_min = _spin_d(1.0, 1000.0, 1.0, float(p["min_price"]), dec=2)
        self._rng_max = _spin_d(10.0, 10000.0, 10.0, float(p["max_price"]), dec=2)
        pr.addWidget(self._rng_en)
        pr.addStretch()
        pr.addWidget(_lbl("Min $:"))
        pr.addWidget(self._rng_min)
        pr.addWidget(_lbl("Max $:"))
        pr.addWidget(self._rng_max)
        root.addLayout(pr)
        root.addWidget(_hdivider())

        # ── Breakout ──────────────────────────────────────────────────────────
        b = _f("breakout")
        root.addWidget(_section("Breakout  (N-bar high)"))
        br = QHBoxLayout()
        self._bk_en = QCheckBox("Enabled")
        self._bk_en.setChecked(bool(b["enabled"]))
        self._bk_lb = _spin_i(1, 50, int(b["lookback"]))
        br.addWidget(self._bk_en)
        br.addStretch()
        br.addWidget(_lbl("Lookback bars:"))
        br.addWidget(self._bk_lb)
        root.addLayout(br)
        root.addWidget(_hdivider())

        # ── Volume ────────────────────────────────────────────────────────────
        vo = _f("volume")
        root.addWidget(_section("Volume  (ratio vs MA)"))
        vor = QHBoxLayout()
        self._vol2_en     = QCheckBox("Enabled")
        self._vol2_en.setChecked(bool(vo["enabled"]))
        self._vol2_ratio  = _spin_d(0.1, 5.0, 0.1, float(vo["min_volume_ratio"]), dec=1)
        self._vol2_period = _spin_i(5, 50, int(vo["ma_period"]))
        vor.addWidget(self._vol2_en)
        vor.addStretch()
        vor.addWidget(_lbl("Min ratio:"))
        vor.addWidget(self._vol2_ratio)
        vor.addWidget(_lbl("MA period:"))
        vor.addWidget(self._vol2_period)
        root.addLayout(vor)
        root.addWidget(_hdivider())

        # ── RS Index ──────────────────────────────────────────────────────────
        ri = _f("rs_index")
        root.addWidget(_section("RS Index  (vs benchmark)"))
        rir = QHBoxLayout()
        self._ri_en   = QCheckBox("Enabled")
        self._ri_en.setChecked(bool(ri["enabled"]))
        self._ri_pct  = _spin_d(0.0, 100.0, 1.0, float(ri["rs_min_percentile"]), dec=1)
        self._ri_sl   = _spin_i(0, 252, int(ri["rs_slope_days"]))
        rir.addWidget(self._ri_en)
        rir.addStretch()
        rir.addWidget(_lbl("Min percentile:"))
        rir.addWidget(self._ri_pct)
        rir.addWidget(_lbl("Slope days (0=off):"))
        rir.addWidget(self._ri_sl)
        root.addLayout(rir)

        # ── Buttons ───────────────────────────────────────────────────────────
        root.addWidget(_hdivider())
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton("✔  OK")
        ok_btn.setObjectName("btn_green")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addSpacing(4)
        btn_row.addWidget(ok_btn)
        root.addLayout(btn_row)

    def get_config(self) -> dict:
        """Return full IndicatorScreener config dict from current widget values."""
        return {
            "filters": {
                "volatility": {
                    "enabled": self._vol_en.isChecked(),
                    "min_atr_pct": round(self._vol_atr.value(), 4),
                },
                "rsi": {
                    "enabled": self._rsi_en.isChecked(),
                    "min": int(self._rsi_min.value()),
                    "max": int(self._rsi_max.value()),
                    "period": int(self._rsi_period.value()),
                },
                "range": {
                    "enabled": self._rng_en.isChecked(),
                    "min_price": round(self._rng_min.value(), 2),
                    "max_price": round(self._rng_max.value(), 2),
                },
                "breakout": {
                    "enabled": self._bk_en.isChecked(),
                    "lookback": int(self._bk_lb.value()),
                },
                "volume": {
                    "enabled": self._vol2_en.isChecked(),
                    "min_volume_ratio": round(self._vol2_ratio.value(), 2),
                    "ma_period": int(self._vol2_period.value()),
                },
                "rs_index": {
                    "enabled": self._ri_en.isChecked(),
                    "rs_min_percentile": round(self._ri_pct.value(), 1),
                    "rs_slope_days": int(self._ri_sl.value()),
                },
            }
        }


# ── Price Action config dialog ────────────────────────────────────────────────

_PA_PATTERN_LABELS: dict[str, str] = {
    "proximity_52w_high": "Near 52-Week High",
    "volume_breakout":    "Volume Breakout",
    "nr7_compression":    "NR7 Compression",
    "ema_pullback":       "EMA Pullback Crossover",
    "engulfing":          "Bullish Engulfing Candle",
}

_PA_DEFAULTS: dict[str, Any] = {
    "proximity_52w_high": {"enabled": True,  "min_ratio": 0.90, "lookback": 252},
    "volume_breakout":    {"enabled": True,  "lookback": 20,    "vol_multiplier": 1.5},
    "nr7_compression":    {"enabled": False},
    "ema_pullback":       {"enabled": False, "ema_period": 21},
    "engulfing":          {"enabled": False},
}


def _format_price_action_config(config: dict) -> str:
    """Return a compact one-line summary of a PriceActionScreener config dict."""
    patterns = config.get("patterns", _PA_DEFAULTS)
    active = [
        lbl
        for pid, lbl in _PA_PATTERN_LABELS.items()
        if patterns.get(pid, {}).get("enabled", _PA_DEFAULTS[pid]["enabled"])
    ]
    thr = config.get("threshold", 0.2)
    base = "  ·  ".join(active) if active else "no patterns enabled"
    return f"PA [{base}]  thr≥{thr}"


class _PriceActionConfigDialog(_FramelessDialog):
    """Toggle and tune the 5 price-action patterns for one ScreenerRef."""

    def __init__(self, config: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(
            "Price Action Pattern Settings",
            min_width=500,
            extra_qss=f" {_CHECKBOX_QSS}",
            parent=parent,
        )

        supplied = (config or {}).get("patterns", {})

        def _p(pid: str) -> dict:
            d = dict(_PA_DEFAULTS[pid])
            d.update(supplied.get(pid, {}))
            return d

        root = self.content_layout()

        def _section(title: str) -> QLabel:
            lbl = QLabel(title)
            lbl.setStyleSheet(f"color: {C.BLUE}; font-weight: bold; font-size: 9pt;")
            return lbl

        def _lbl(text: str) -> QLabel:
            l = QLabel(text)
            l.setStyleSheet(f"color: {C.SUBTEXT}; font-size: 8pt;")
            return l

        def _spin_d(lo: float, hi: float, step: float, val: float, dec: int = 2) -> QDoubleSpinBox:
            s = QDoubleSpinBox()
            s.setRange(lo, hi)
            s.setSingleStep(step)
            s.setDecimals(dec)
            s.setValue(val)
            s.setFixedWidth(80)
            s.setStyleSheet(
                f"QDoubleSpinBox {{ background: {C.OVERLAY}; color: {C.TEXT};"
                f" border: 1px solid {C.OVERLAY}; border-radius: 3px; padding: 1px 4px; }}"
            )
            return s

        def _spin_i(lo: int, hi: int, val: int) -> QDoubleSpinBox:
            return _spin_d(lo, hi, 1.0, float(val), dec=0)

        # ── 52-Week High ──────────────────────────────────────────────────────
        p52 = _p("proximity_52w_high")
        root.addWidget(_section("Near 52-Week High"))
        r52 = QHBoxLayout()
        self._52_en   = QCheckBox("Enabled")
        self._52_en.setChecked(bool(p52["enabled"]))
        self._52_rat  = _spin_d(0.50, 1.00, 0.01, float(p52["min_ratio"]))
        self._52_lb   = _spin_i(20, 504, int(p52["lookback"]))
        r52.addWidget(self._52_en)
        r52.addStretch()
        r52.addWidget(_lbl("Min ratio:"))
        r52.addWidget(self._52_rat)
        r52.addWidget(_lbl("Lookback days:"))
        r52.addWidget(self._52_lb)
        root.addLayout(r52)
        root.addWidget(_hdivider())

        # ── Volume Breakout ───────────────────────────────────────────────────
        pvb = _p("volume_breakout")
        root.addWidget(_section("Volume Breakout"))
        rvb = QHBoxLayout()
        self._vb_en   = QCheckBox("Enabled")
        self._vb_en.setChecked(bool(pvb["enabled"]))
        self._vb_lb   = _spin_i(5, 60, int(pvb["lookback"]))
        self._vb_mul  = _spin_d(1.0, 5.0, 0.1, float(pvb["vol_multiplier"]))
        rvb.addWidget(self._vb_en)
        rvb.addStretch()
        rvb.addWidget(_lbl("Lookback bars:"))
        rvb.addWidget(self._vb_lb)
        rvb.addWidget(_lbl("Vol multiplier:"))
        rvb.addWidget(self._vb_mul)
        root.addLayout(rvb)
        root.addWidget(_hdivider())

        # ── NR7 Compression ───────────────────────────────────────────────────
        pnr = _p("nr7_compression")
        root.addWidget(_section("NR7 Compression"))
        rnr = QHBoxLayout()
        self._nr7_en = QCheckBox("Enabled")
        self._nr7_en.setChecked(bool(pnr["enabled"]))
        rnr.addWidget(self._nr7_en)
        rnr.addStretch()
        rnr.addWidget(_lbl("Triggers when today's range is smallest of last 7 bars"))
        root.addLayout(rnr)
        root.addWidget(_hdivider())

        # ── EMA Pullback ──────────────────────────────────────────────────────
        pem = _p("ema_pullback")
        root.addWidget(_section("EMA Pullback Crossover"))
        rem = QHBoxLayout()
        self._ema_en  = QCheckBox("Enabled")
        self._ema_en.setChecked(bool(pem["enabled"]))
        self._ema_per = _spin_i(5, 200, int(pem["ema_period"]))
        rem.addWidget(self._ema_en)
        rem.addStretch()
        rem.addWidget(_lbl("EMA period:"))
        rem.addWidget(self._ema_per)
        root.addLayout(rem)
        root.addWidget(_hdivider())

        # ── Bullish Engulfing ─────────────────────────────────────────────────
        peg = _p("engulfing")
        root.addWidget(_section("Bullish Engulfing Candle"))
        reg = QHBoxLayout()
        self._eng_en = QCheckBox("Enabled")
        self._eng_en.setChecked(bool(peg["enabled"]))
        reg.addWidget(self._eng_en)
        reg.addStretch()
        reg.addWidget(_lbl("Bearish candle followed by larger bullish candle that engulfs it"))
        root.addLayout(reg)
        root.addWidget(_hdivider())

        # ── Threshold ─────────────────────────────────────────────────────────
        root.addWidget(_section("Pass Threshold"))
        thr_row = QHBoxLayout()
        self._thr = _spin_d(0.0, 1.0, 0.05, float((config or {}).get("threshold", 0.2)))
        thr_row.addWidget(_lbl("Min score to pass  (patterns matched / patterns enabled):"))
        thr_row.addWidget(self._thr)
        root.addLayout(thr_row)

        # ── Buttons ───────────────────────────────────────────────────────────
        root.addWidget(_hdivider())
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton("✔  OK")
        ok_btn.setObjectName("btn_green")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addSpacing(4)
        btn_row.addWidget(ok_btn)
        root.addLayout(btn_row)

    def get_config(self) -> dict:
        return {
            "patterns": {
                "proximity_52w_high": {
                    "enabled": self._52_en.isChecked(),
                    "min_ratio": round(self._52_rat.value(), 2),
                    "lookback": int(self._52_lb.value()),
                },
                "volume_breakout": {
                    "enabled": self._vb_en.isChecked(),
                    "lookback": int(self._vb_lb.value()),
                    "vol_multiplier": round(self._vb_mul.value(), 2),
                },
                "nr7_compression": {
                    "enabled": self._nr7_en.isChecked(),
                },
                "ema_pullback": {
                    "enabled": self._ema_en.isChecked(),
                    "ema_period": int(self._ema_per.value()),
                },
                "engulfing": {
                    "enabled": self._eng_en.isChecked(),
                },
            },
            "threshold": round(self._thr.value(), 2),
        }


# ── Composite group widget ────────────────────────────────────────────────────

class _GroupWidget(QFrame):
    """One group card in the Composite preset builder.

    Contains a drag-reorderable screener list with AND/OR toggle.
    """

    changed          = pyqtSignal()
    remove_requested = pyqtSignal(str)   # emits group_id

    def __init__(
        self,
        group_id: str,
        logic: str = "AND",
        screener_ids: list[str] | None = None,
        configs: dict[str, dict] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._group_id = group_id
        self._logic    = logic
        self._configs: dict[str, dict] = dict(configs or {})

        self.setObjectName("group_frame")
        self.setStyleSheet(
            f"QFrame#group_frame {{"
            f"  border: 1px solid {C.BLUE}55;"
            f"  border-radius: 6px;"
            f"  background: {C.SURFACE};"
            f"  margin-bottom: 8px;"
            f"}}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ──────────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(38)
        header.setStyleSheet(
            f"background: {C.OVERLAY}; border-radius: 5px 5px 0 0;"
        )
        hl = QHBoxLayout(header)
        hl.setContentsMargins(10, 0, 8, 0)
        hl.setSpacing(6)

        num = group_id.lstrip("g") or "1"
        self._title_lbl = QLabel(f"Group {num}")
        self._title_lbl.setStyleSheet(
            f"color: {C.BLUE}; font-weight: bold; font-size: 9pt; background: transparent;"
        )

        self._logic_btn = QPushButton(logic)
        self._logic_btn.setFixedSize(44, 26)
        self._logic_btn.setToolTip("Toggle AND / OR logic within this group")
        self._logic_btn.clicked.connect(self._toggle_logic)
        self._apply_logic_style()

        self._add_screener_btn = QPushButton("＋  Add Screener")
        add_btn = self._add_screener_btn
        add_btn.setObjectName("btn_add_screener")
        add_btn.setToolTip("Add a screener to this group")
        add_btn.clicked.connect(self._on_add_screener)

        self._cfg_btn = QPushButton("⚙  Configure")
        self._cfg_btn.setObjectName("btn_configure")
        self._cfg_btn.setToolTip("Configure the selected screener")
        self._cfg_btn.setEnabled(False)
        self._cfg_btn.clicked.connect(self._on_configure)

        del_btn = QPushButton("Remove")
        del_btn.setObjectName("btn_remove")
        del_btn.setToolTip("Remove this group")
        del_btn.clicked.connect(lambda: self.remove_requested.emit(self._group_id))

        hl.addWidget(self._title_lbl)
        hl.addStretch()
        hl.addWidget(self._logic_btn)
        hl.addSpacing(4)
        hl.addWidget(add_btn)
        hl.addSpacing(2)
        hl.addWidget(self._cfg_btn)
        hl.addSpacing(2)
        hl.addWidget(del_btn)
        root.addWidget(header)

        # ── Empty state (shown when list is empty) ───────────────────────────
        self._empty_lbl = QLabel("No screeners yet — click  ＋ Add Screener  above")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setFixedHeight(48)
        self._empty_lbl.setStyleSheet(
            f"color: {C.MUTED}; font-size: 8pt; font-style: italic;"
            f" background: {C.BG}; border: none;"
        )
        root.addWidget(self._empty_lbl)

        # ── Screener list (drag-reorderable) ────────────────────────────────
        self._list = QListWidget()
        self._list.setMinimumHeight(52)
        self._list.setMaximumHeight(160)
        self._list.setVisible(False)
        self._list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._list.setStyleSheet(
            f"QListWidget {{ border: none; background: {C.BG}; padding: 4px; outline: none; }}"
            f"QListWidget::item {{ padding: 5px 10px; color: {C.TEXT}; font-size: 9pt;"
            f"  border-radius: 3px; margin-bottom: 2px; }}"
            f"QListWidget::item:selected {{ background: #1a2d45; color: {C.BLUE}; }}"
            f"QListWidget::item:focus {{ outline: none; border: none; }}"
            f"QListWidget::item:hover:!selected {{ background: {C.OVERLAY}; }}"
        )
        self._list.model().rowsInserted.connect(self._on_list_changed)
        self._list.model().rowsRemoved.connect(self._on_list_changed)
        self._list.currentItemChanged.connect(self._on_selection_changed)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._list_ctx_menu)
        root.addWidget(self._list)

        for sid in (screener_ids or []):
            self._add_item(sid)
        self._sync_empty_state()

    # ── Internal helpers ───────────────────────────────────────────────────

    def _apply_logic_style(self) -> None:
        is_and = self._logic == "AND"
        fg  = "#89b4fa" if is_and else "#cba6f7"
        bg  = "#1a2d45" if is_and else "#2e1a2a"
        bdr = "#89b4fa" if is_and else "#cba6f7"
        hover = "#1e3558" if is_and else "#3d2240"
        self._logic_btn.setText(self._logic)
        self._logic_btn.setStyleSheet(
            f"QPushButton {{ background: {bg}; color: {fg}; font-size: 8pt;"
            f" font-weight: bold; border: 1px solid {bdr}; border-radius: 4px;"
            f" padding: 1px 4px; }}"
            f"QPushButton:hover {{ background: {hover}; }}"
            f"QPushButton:focus {{ outline: none; }}"
        )

    def _toggle_logic(self) -> None:
        self._logic = "OR" if self._logic == "AND" else "AND"
        self._apply_logic_style()
        self.changed.emit()

    def _on_list_changed(self) -> None:
        self._sync_empty_state()
        self.changed.emit()

    def _sync_empty_state(self) -> None:
        empty = self._list.count() == 0
        self._empty_lbl.setVisible(empty)
        self._list.setVisible(not empty)

    def _on_selection_changed(self) -> None:
        item = self._list.currentItem()
        sid = item.data(Qt.ItemDataRole.UserRole) if item else None
        self._cfg_btn.setEnabled(
            sid in (_INDICATOR_SCREENER_ID, _PRICE_ACTION_SCREENER_ID)
        )

    def _on_configure(self) -> None:
        item = self._list.currentItem()
        if not item:
            return
        sid = item.data(Qt.ItemDataRole.UserRole)
        if sid == _INDICATOR_SCREENER_ID:
            self._open_indicator_config(sid)
        elif sid == _PRICE_ACTION_SCREENER_ID:
            self._open_price_action_config(sid)

    def _on_add_screener(self) -> None:
        menu = QMenu(self)
        existing = set(self.screener_ids())
        added_any = False
        try:
            from us_swing.screener.registry import ScreenerRegistry
            available_ids = list(ScreenerRegistry.list_available())
        except Exception:  # noqa: BLE001
            available_ids = list(_SCREENER_DISPLAY)
        for sid in available_ids:
            if sid not in existing and sid not in _HIDDEN_SCREENER_IDS:
                label = _SCREENER_DISPLAY.get(sid, sid)
                act = menu.addAction(label)
                act.setData(sid)
                added_any = True
        if not added_any:
            menu.addAction("All screeners added").setEnabled(False)
        btn = self._add_screener_btn
        pos = btn.mapToGlobal(QPoint(0, btn.height()))
        chosen = menu.exec(pos)
        if chosen and chosen.data():
            self._add_item(chosen.data())
            self.changed.emit()

    def _list_ctx_menu(self, pos: Any) -> None:
        item = self._list.itemAt(pos)
        if not item:
            return
        sid  = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        if sid == _INDICATOR_SCREENER_ID:
            menu.addAction(
                "⚙  Configure…",
                lambda: self._open_indicator_config(sid),
            )
            menu.addSeparator()
        elif sid == _PRICE_ACTION_SCREENER_ID:
            menu.addAction(
                "⚙  Configure…",
                lambda: self._open_price_action_config(sid),
            )
            menu.addSeparator()
        menu.addAction(
            "Remove from group",
            lambda: (self._list.takeItem(self._list.row(item)), self.changed.emit()),
        )
        menu.exec(self._list.viewport().mapToGlobal(pos))

    def _open_indicator_config(self, sid: str) -> None:
        dlg = _IndicatorConfigDialog(self._configs.get(sid), parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._configs[sid] = dlg.get_config()
            self.changed.emit()

    def _open_price_action_config(self, sid: str) -> None:
        dlg = _PriceActionConfigDialog(self._configs.get(sid), parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._configs[sid] = dlg.get_config()
            self.changed.emit()

    def _add_item(self, sid: str) -> None:
        label = _SCREENER_DISPLAY.get(sid, sid)
        it = QListWidgetItem(f"≡  {label}")
        it.setData(Qt.ItemDataRole.UserRole, sid)
        it.setFlags(it.flags() | Qt.ItemFlag.ItemIsDragEnabled)
        self._list.addItem(it)

    # ── Public API ─────────────────────────────────────────────────────────

    def screener_ids(self) -> list[str]:
        return [
            self._list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self._list.count())
        ]

    def screener_configs(self) -> dict[str, dict]:
        return dict(self._configs)

    def logic(self) -> str:
        return self._logic

    def group_id(self) -> str:
        return self._group_id


# ── Weighted screener row ─────────────────────────────────────────────────────

class _WeightedRow(QFrame):
    """One row in the Weighted preset builder — screener label + weight spinbox."""

    changed         = pyqtSignal()
    remove_requested = pyqtSignal(object)   # emits self

    def __init__(
        self,
        sid: str,
        weight: float = 0.0,
        config: dict | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._sid    = sid
        self._config = dict(config) if config else {}

        self.setFixedHeight(34)
        self.setStyleSheet(
            f"QFrame {{ background: {C.SURFACE}; border-bottom: 1px solid {C.OVERLAY}; }}"
        )
        hl = QHBoxLayout(self)
        hl.setContentsMargins(8, 0, 6, 0)
        hl.setSpacing(6)

        drag_hint = QLabel("≡")
        drag_hint.setFixedWidth(14)
        drag_hint.setStyleSheet(f"color: {C.MUTED}; font-size: 12pt; background: transparent;")

        label = _SCREENER_DISPLAY.get(sid, sid)
        name_lbl = QLabel(label)
        name_lbl.setStyleSheet(f"color: {C.TEXT}; font-size: 9pt; background: transparent;")

        hl.addWidget(drag_hint)
        hl.addWidget(name_lbl, 1)

        if sid in (_INDICATOR_SCREENER_ID, _PRICE_ACTION_SCREENER_ID):
            cfg_btn = QPushButton("⚙")
            cfg_btn.setFixedSize(22, 22)
            cfg_btn.setToolTip("Edit screener settings")
            cfg_btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {C.SUBTEXT}; font-size: 11pt;"
                f" border: 1px solid {C.OVERLAY2}; border-radius: 3px; }}"
                f"QPushButton:hover {{ color: {C.BLUE}; border-color: {C.BLUE}; }}"
            )
            cfg_btn.clicked.connect(self._open_config)
            hl.addWidget(cfg_btn)

        wlbl = QLabel("Weight:")
        wlbl.setStyleSheet(f"color: {C.MUTED}; font-size: 8pt; background: transparent;")
        hl.addWidget(wlbl)

        self._spin = QDoubleSpinBox()
        self._spin.setRange(0.01, 1.00)
        self._spin.setSingleStep(0.05)
        self._spin.setDecimals(2)
        self._spin.setValue(weight)
        self._spin.setFixedWidth(62)
        self._spin.setStyleSheet(
            f"QDoubleSpinBox {{ background: {C.OVERLAY}; color: {C.TEXT};"
            f" border: 1px solid {C.OVERLAY}; border-radius: 3px; padding: 1px 4px; }}"
        )
        self._spin.valueChanged.connect(lambda _: self.changed.emit())
        hl.addWidget(self._spin)

        del_btn = QPushButton("×")
        del_btn.setFixedSize(20, 20)
        del_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C.SUBTEXT}; font-size: 12pt;"
            f" border: none; }}"
            f"QPushButton:hover {{ color: {C.RED}; }}"
        )
        del_btn.clicked.connect(lambda: self.remove_requested.emit(self))
        hl.addWidget(del_btn)

    def screener_id(self) -> str:
        return self._sid

    def weight(self) -> float:
        return self._spin.value()

    def config(self) -> dict:
        return dict(self._config)

    def _open_config(self) -> None:
        if self._sid == _PRICE_ACTION_SCREENER_ID:
            dlg = _PriceActionConfigDialog(self._config or None, parent=self)
        else:
            dlg = _IndicatorConfigDialog(self._config or None, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._config = dlg.get_config()  # type: ignore[union-attr]


# ── WYSIWYG Preset builder dialog ─────────────────────────────────────────────

class _UserTag(QWidget):
    """Removable badge representing a single user in the Assign Users section."""

    removed = pyqtSignal(str)   # emits user_id when × clicked

    def __init__(
        self,
        user_id: str,
        label: str | None = None,
        valid: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._user_id = user_id
        bg = "#1a2d1a" if valid else "#2d1a1a"
        fg = C.GREEN   if valid else C.RED

        lbl = QLabel(label or user_id)
        lbl.setStyleSheet(f"color: {fg}; font-size: 8pt;")

        close = QPushButton("×")
        close.setFixedSize(QSize(16, 16))
        close.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C.MUTED};"
            f" border: none; font-size: 10pt; padding: 0; }}"
            f"QPushButton:hover {{ color: {C.RED}; }}"
        )
        close.clicked.connect(lambda: self.removed.emit(self._user_id))

        row = QHBoxLayout(self)
        row.setContentsMargins(6, 2, 4, 2)
        row.setSpacing(4)
        row.addWidget(lbl)
        row.addWidget(close)

        self.setStyleSheet(
            f"background: {bg}; border: 1px solid {fg}; border-radius: 3px;"
        )
        if not valid:
            self.setToolTip("Unknown user ID")


class _UserPickerDialog(QDialog):
    """Popup that lists all users as checkboxes; returns selected user IDs."""

    def __init__(
        self,
        all_users: list[Any],
        already_assigned: set[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select Users")
        self.setMinimumWidth(300)
        self.setStyleSheet(
            f"QDialog {{ background: {C.BG}; }}"
            f"QLabel {{ color: {C.TEXT}; font-size: 9pt; }}"
        )

        self._checks: dict[str, QCheckBox] = {}   # uid → checkbox

        vl = QVBoxLayout(self)
        vl.setSpacing(6)
        vl.setContentsMargins(14, 12, 14, 12)

        header = QLabel("Select users to assign this preset to:")
        header.setStyleSheet(f"color: {C.SUBTEXT}; font-size: 8pt;")
        vl.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(180)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: 1px solid {C.OVERLAY}; border-radius: 4px; }}"
        )
        inner = QWidget()
        inner.setStyleSheet(f"background: {C.SURFACE};")
        inner_vl = QVBoxLayout(inner)
        inner_vl.setContentsMargins(8, 8, 8, 8)
        inner_vl.setSpacing(6)

        for u in all_users:
            uid = str(u.user_id)
            cb  = QCheckBox(f"{u.display_name}  ({u.username})")
            cb.setChecked(uid in already_assigned)
            cb.setStyleSheet(f"color: {C.TEXT}; font-size: 9pt;")
            self._checks[uid] = cb
            inner_vl.addWidget(cb)

        if not all_users:
            lbl = QLabel("No other users found.")
            lbl.setStyleSheet(f"color: {C.MUTED}; font-size: 9pt;")
            inner_vl.addWidget(lbl)

        inner_vl.addStretch()
        scroll.setWidget(inner)
        vl.addWidget(scroll)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok_btn = QPushButton("Confirm")
        ok_btn.setObjectName("btn_green")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        btn_row.addSpacing(6)
        btn_row.addWidget(ok_btn)
        vl.addLayout(btn_row)

    def selected_ids(self) -> set[str]:
        return {uid for uid, cb in self._checks.items() if cb.isChecked()}


class _AssignUsersWidget(QWidget):
    """Tag-based user assignment with a picker popup (SRD-SCR-007.012)."""

    def __init__(
        self,
        preset_id: str,
        mgr: Any,
        requestor_id: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._preset_id    = preset_id
        self._mgr          = mgr
        self._requestor_id = requestor_id
        self._tags: list[_UserTag] = []

        from us_swing.gui.user_store import load_users
        all_users = load_users()
        self._all_users = all_users
        self._id_label_map: dict[str, str] = {
            str(u.user_id): f"{u.display_name} ({u.username})"
            for u in self._all_users
        }

        self._tag_row = QHBoxLayout()
        self._tag_row.setSpacing(4)
        self._tag_row.setContentsMargins(0, 0, 0, 0)
        self._tag_row.addStretch()

        add_btn = QPushButton("＋  Add User")
        add_btn.setObjectName("btn_blue")
        add_btn.clicked.connect(self._on_open_picker)

        vl = QVBoxLayout(self)
        vl.setContentsMargins(0, 2, 0, 2)
        vl.setSpacing(4)

        tag_container = QWidget()
        tag_container.setLayout(self._tag_row)
        vl.addWidget(tag_container)
        vl.addWidget(add_btn)

    def load_existing(self, user_ids: list[str]) -> None:
        for uid in user_ids:
            self._insert_tag(uid)

    def _on_open_picker(self) -> None:
        already = {t._user_id for t in self._tags}
        dlg = _UserPickerDialog(self._all_users, already, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        selected = dlg.selected_ids()

        # grant newly ticked users
        for uid in selected - already:
            try:
                self._mgr.grant_access(self._preset_id, [uid], self._requestor_id)
                self._insert_tag(uid)
            except Exception:  # noqa: BLE001
                pass

        # revoke newly un-ticked users
        for uid in already - selected:
            self._on_remove(uid)

    def _on_remove(self, uid: str) -> None:
        tag = next((t for t in self._tags if t._user_id == uid), None)
        if tag is None:
            return
        try:
            self._mgr.revoke_access(self._preset_id, uid, self._requestor_id)
        except Exception:  # noqa: BLE001
            pass
        self._tag_row.removeWidget(tag)
        tag.deleteLater()
        self._tags.remove(tag)

    def _insert_tag(self, uid: str) -> None:
        label = self._id_label_map.get(uid, uid)
        tag = _UserTag(uid, label=label, valid=True, parent=self)
        tag.removed.connect(self._on_remove)
        self._tags.append(tag)
        # Insert before the trailing stretch
        self._tag_row.insertWidget(self._tag_row.count() - 1, tag)


class _PresetBuilderDialog(_FramelessDialog):
    """WYSIWYG Preset Builder — create new or edit existing preset.

    Composite mode: multiple groups with AND/OR toggle + drag-reorderable
    screener lists per group.  Weighted mode: flat screener list with
    per-screener weight spinboxes.  Live preview pane updates on every change.

    SRD-SCR-007.002 / SRD-SCR-007.003 / SRD-SCR-007.004 / SRD-SCR-007.005
    """

    def __init__(
        self,
        mgr: Any,
        user_id: str,
        preset: Any = None,          # None = create new; Preset = edit
        parent: QWidget | None = None,
    ) -> None:
        title = "Edit Preset" if preset else "New Screener Preset"
        super().__init__(title, min_width=960, min_height=580, parent=parent)
        self._mgr      = mgr
        self._user_id  = user_id
        self._preset   = preset
        self._saved_id: str | None = None

        self._content_layout.setContentsMargins(14, 10, 14, 12)
        root = self._content_layout

        # ── Row 1: name + description ────────────────────────────────────
        row1 = QHBoxLayout()
        row1.setSpacing(10)
        col_name = QVBoxLayout()
        col_name.addWidget(self._lbl("Preset Name *"))
        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. Daily RSI Momentum")
        self._name.textChanged.connect(self._refresh_preview)
        col_name.addWidget(self._name)
        row1.addLayout(col_name, 2)

        col_desc = QVBoxLayout()
        col_desc.addWidget(self._lbl("Description (optional)"))
        self._desc = QLineEdit()
        self._desc.setPlaceholderText("Brief description")
        col_desc.addWidget(self._desc)
        row1.addLayout(col_desc, 3)
        root.addLayout(row1)

        _sep = QFrame()
        _sep.setFrameShape(QFrame.Shape.HLine)
        _sep.setFrameShadow(QFrame.Shadow.Sunken)
        _sep.setStyleSheet(f"color: {C.OVERLAY};")
        root.addWidget(_sep)

        # ── Row 2: Type group box + Style/Users group box (horizontal) ───
        from PyQt6.QtWidgets import QStackedWidget
        _is_creator = preset is None or not preset.is_admin
        _gb_style = (
            f"QGroupBox {{ color: {C.MUTED}; font-size: 8pt;"
            f" border: 1px solid {C.OVERLAY}; border-radius: 4px;"
            f" padding: 6px 8px 6px 8px; margin-top: 8px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 2px; }}"
        )
        row2 = QHBoxLayout()
        row2.setSpacing(10)

        # ── Left: Type group box ──────────────────────────────────────────
        type_box = QGroupBox("Screener Builder")
        type_box.setStyleSheet(_gb_style)
        type_vl = QVBoxLayout(type_box)
        type_vl.setContentsMargins(8, 12, 8, 8)
        type_vl.setSpacing(6)

        radio_row = QHBoxLayout()
        radio_row.setSpacing(16)
        self._btn_grp = QButtonGroup(self)
        self._r_composite = QRadioButton("Composite  (AND/OR groups)")
        self._r_weighted  = QRadioButton("Weighted  (scored ensemble)")
        self._r_composite.setStyleSheet(f"color: {C.TEXT}; font-size: 9pt;")
        self._r_weighted.setStyleSheet(f"color: {C.TEXT}; font-size: 9pt;")
        self._r_composite.setChecked(True)
        self._btn_grp.addButton(self._r_composite, 0)
        self._btn_grp.addButton(self._r_weighted, 1)
        self._btn_grp.idToggled.connect(self._on_type_changed)
        radio_row.addWidget(self._r_composite)
        radio_row.addWidget(self._r_weighted)
        radio_row.addStretch()
        self._add_grp_btn = QPushButton("＋  Add Group")
        self._add_grp_btn.setObjectName("btn_blue")
        self._add_grp_btn.clicked.connect(lambda: self._add_group())
        radio_row.addWidget(self._add_grp_btn)
        if preset is not None:
            self._r_composite.setEnabled(False)
            self._r_weighted.setEnabled(False)
        type_vl.addLayout(radio_row)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_composite_area())  # index 0
        self._stack.addWidget(self._build_weighted_area())   # index 1
        type_vl.addWidget(self._stack, 1)

        type_vl.addWidget(self._lbl("Preview"))
        self._preview = QPlainTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setFixedHeight(72)
        self._preview.setStyleSheet(
            f"QPlainTextEdit {{ background: {C.SURFACE}; color: {C.SUBTEXT};"
            f" border: 1px solid {C.OVERLAY}; border-radius: 4px;"
            f" font-family: monospace; font-size: 9pt; padding: 4px; }}"
        )
        type_vl.addWidget(self._preview)
        row2.addWidget(type_box, 1)

        # ── Right: Trade Settings group box ───────────────────────────────
        style_users_box = QGroupBox("Trade Settings")
        style_users_box.setStyleSheet(_gb_style)
        style_users_vl = QVBoxLayout(style_users_box)
        style_users_vl.setContentsMargins(8, 12, 8, 8)
        style_users_vl.setSpacing(6)

        style_users_vl.addWidget(self._lbl("Timeframe"))
        self._tf_preset = QComboBox()
        self._tf_preset.addItem("Daily",  "1d")
        self._tf_preset.addItem("Weekly", "1w")
        style_users_vl.addWidget(self._tf_preset)

        style_users_vl.addSpacing(8)
        style_users_vl.addWidget(self._lbl("Trading Style"))
        self._style_checks: dict[str, QCheckBox] = {}
        for lbl_text, style_val in _STYLE_OPTIONS[1:]:   # skip "All Styles"
            cb = QCheckBox(lbl_text)
            cb.setEnabled(_is_creator)
            cb.setStyleSheet(f"color: {C.TEXT}; font-size: 9pt;")
            self._style_checks[style_val] = cb
            style_users_vl.addWidget(cb)

        # ── Assign Users (SRD-SCR-007.012) — user-owned edit mode only ───
        self._assign_widget: _AssignUsersWidget | None = None
        show_assign = (
            preset is not None
            and not preset.is_admin
            and _is_creator
        )
        if show_assign:
            style_users_vl.addSpacing(8)
            style_users_vl.addWidget(self._lbl("Assign Users"))
            self._assign_widget = _AssignUsersWidget(
                preset_id=preset.id,
                mgr=mgr,
                requestor_id=user_id,
            )
            self._assign_widget.load_existing(getattr(preset, "assigned_to", []))
            style_users_vl.addWidget(self._assign_widget)

        style_users_vl.addStretch()
        style_users_box.setMaximumWidth(210)
        row2.addWidget(style_users_box)

        root.addLayout(row2, 1)

        # ── AI Ranking (Stage 3) ──────────────────────────────────────────
        ai_box = QGroupBox("AI Ranking  (Stage 3)")
        ai_box.setStyleSheet(_gb_style)
        ai_vl = QVBoxLayout(ai_box)
        ai_vl.setContentsMargins(8, 12, 8, 8)
        ai_vl.setSpacing(6)

        ai_header_hl = QHBoxLayout()
        ai_header_hl.setContentsMargins(0, 0, 0, 0)
        self._ai_ranking_chk = QCheckBox(
            "Enable AI Ranking — let an AI model score and sort your filtered results"
        )
        self._ai_ranking_chk.setStyleSheet(f"color: {C.TEXT}; font-size: 9pt;")
        ai_header_hl.addWidget(self._ai_ranking_chk)
        ai_header_hl.addStretch()
        self._ai_model_validate_btn = QPushButton("⚡  Validate")
        self._ai_model_validate_btn.setFixedWidth(105)
        self._ai_model_validate_btn.setVisible(False)
        self._ai_model_validate_btn.clicked.connect(self._on_validate_model)
        ai_header_hl.addWidget(self._ai_model_validate_btn)
        ai_vl.addLayout(ai_header_hl)

        self._ai_ranking_row = QWidget()
        ai_fields_hl = QHBoxLayout(self._ai_ranking_row)
        ai_fields_hl.setContentsMargins(0, 2, 0, 0)
        ai_fields_hl.setSpacing(12)

        top_n_vl = QVBoxLayout()
        top_n_vl.setSpacing(2)
        top_n_vl.addWidget(self._lbl("Top N"))
        self._ai_top_n = QSpinBox()
        self._ai_top_n.setRange(1, 50)
        self._ai_top_n.setValue(5)
        self._ai_top_n.setFixedWidth(64)
        top_n_vl.addWidget(self._ai_top_n)
        top_n_vl.addStretch()
        ai_fields_hl.addLayout(top_n_vl)

        model_vl = QVBoxLayout()
        model_vl.setSpacing(2)
        model_vl.addWidget(self._lbl("Model"))
        self._ai_model_edit = QLineEdit()
        self._ai_model_edit.setPlaceholderText("e.g. google/gemini-2-flash-preview")
        self._ai_model_edit.setText(_CLOUD_AI_DEFAULT_MODEL)
        self._ai_model_edit.textChanged.connect(self._on_model_text_changed)
        model_vl.addWidget(self._ai_model_edit)
        self._ai_model_status_lbl = QLabel("")
        self._ai_model_status_lbl.setStyleSheet(f"font-size: 8pt; color: {C.MUTED};")
        model_vl.addWidget(self._ai_model_status_lbl)
        model_vl.addStretch()
        ai_fields_hl.addLayout(model_vl, 2)

        query_vl = QVBoxLayout()
        query_vl.setSpacing(2)
        query_vl.addWidget(self._lbl("Query  (optional — blank = auto-rank by features)"))
        self._ai_query_field = QLineEdit()
        self._ai_query_field.setPlaceholderText(
            "e.g. rank by strongest momentum with expanding volume"
        )
        self._ai_query_field.setMaxLength(500)
        query_vl.addWidget(self._ai_query_field)
        query_vl.addStretch()
        ai_fields_hl.addLayout(query_vl, 3)

        ai_vl.addWidget(self._ai_ranking_row)
        self._ai_ranking_row.setVisible(False)
        self._ai_ranking_chk.toggled.connect(self._ai_ranking_row.setVisible)
        self._ai_ranking_chk.toggled.connect(self._ai_model_validate_btn.setVisible)
        root.addWidget(ai_box)

        # ── Button row ────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._save_as_btn = QPushButton("💾  Save As…")
        self._save_as_btn.setVisible(preset is not None)
        self._save_as_btn.setToolTip("Save a copy of this preset with a new name")
        self._save_as_btn.clicked.connect(self._on_save_as)

        save_btn = QPushButton("✔  Save")
        save_btn.setObjectName("btn_green")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._on_save)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        btn_row.addWidget(self._save_as_btn)
        btn_row.addSpacing(6)
        btn_row.addWidget(cancel_btn)
        btn_row.addSpacing(4)
        btn_row.addWidget(save_btn)
        root.addLayout(btn_row)

        # ── Populate from existing preset (edit mode) ─────────────────────
        if preset is not None:
            self._populate_from_preset(preset)

        self._refresh_preview()

    # ── Composite area ────────────────────────────────────────────────────

    def _build_composite_area(self) -> QWidget:
        page = QWidget()
        vl   = QVBoxLayout(page)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(80)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: {C.BG}; }}"
        )
        self._groups_content = QWidget()
        self._groups_content.setStyleSheet(f"background: {C.BG};")
        self._groups_layout  = QVBoxLayout(self._groups_content)
        self._groups_layout.setContentsMargins(0, 0, 0, 0)
        self._groups_layout.setSpacing(0)
        self._groups_layout.addStretch()
        scroll.setWidget(self._groups_content)
        vl.addWidget(scroll, 1)

        self._group_widgets: list[_GroupWidget] = []
        self._group_counter = 0

        # Default first group on create
        return page

    def _add_group(
        self,
        gid: str | None = None,
        logic: str = "AND",
        screener_ids: list[str] | None = None,
        configs: dict[str, dict] | None = None,
    ) -> _GroupWidget:
        self._group_counter += 1
        gid = gid or f"g{self._group_counter}"
        w   = _GroupWidget(gid, logic, screener_ids, configs, parent=self._groups_content)
        w.changed.connect(self._refresh_preview)
        w.remove_requested.connect(self._on_remove_group)
        # Insert before the stretch at the end
        idx = self._groups_layout.count() - 1
        self._groups_layout.insertWidget(idx, w)
        self._group_widgets.append(w)
        self._refresh_preview()
        return w

    def _on_remove_group(self, gid: str) -> None:
        w = next((x for x in self._group_widgets if x.group_id() == gid), None)
        if w:
            self._groups_layout.removeWidget(w)
            w.deleteLater()
            self._group_widgets.remove(w)
            self._refresh_preview()

    # ── Weighted area ─────────────────────────────────────────────────────

    def _build_weighted_area(self) -> QWidget:
        page = QWidget()
        vl   = QVBoxLayout(page)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(6)

        # Threshold
        thr_row = QHBoxLayout()
        thr_row.addWidget(self._lbl("Pass Threshold (0–1):"))
        self._threshold = QDoubleSpinBox()
        self._threshold.setRange(0.0, 1.0)
        self._threshold.setSingleStep(0.05)
        self._threshold.setValue(0.60)
        self._threshold.setDecimals(2)
        self._threshold.setFixedWidth(72)
        self._threshold.valueChanged.connect(self._refresh_preview)
        thr_row.addWidget(self._threshold)
        thr_row.addStretch()
        self._add_screener_w_btn = QPushButton("＋  Add Screener")
        self._add_screener_w_btn.setObjectName("btn_add_screener")
        self._add_screener_w_btn.clicked.connect(self._on_add_weighted_screener)
        add_btn = self._add_screener_w_btn
        norm_btn = QPushButton("Normalize")
        norm_btn.setToolTip("Distribute weights equally across all screeners")
        norm_btn.clicked.connect(self._normalize_weights)
        thr_row.addWidget(norm_btn)
        thr_row.addWidget(add_btn)
        vl.addLayout(thr_row)

        # Rows scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: 1px solid {C.OVERLAY}; border-radius: 4px; }}"
        )
        self._w_content = QWidget()
        self._w_content.setStyleSheet(f"background: {C.SURFACE};")
        self._w_layout  = QVBoxLayout(self._w_content)
        self._w_layout.setContentsMargins(0, 0, 0, 0)
        self._w_layout.setSpacing(0)
        self._w_layout.addStretch()
        scroll.setWidget(self._w_content)
        vl.addWidget(scroll, 1)

        self._weighted_rows: list[_WeightedRow] = []

        return page

    def _add_weighted_row(self, sid: str, weight: float = 0.0, config: dict | None = None) -> None:
        row = _WeightedRow(sid, weight, config, parent=self._w_content)
        row.changed.connect(self._refresh_preview)
        row.remove_requested.connect(self._on_remove_weighted_row)
        idx = self._w_layout.count() - 1   # before stretch
        self._w_layout.insertWidget(idx, row)
        self._weighted_rows.append(row)
        self._refresh_preview()

    def _on_remove_weighted_row(self, row: _WeightedRow) -> None:
        self._w_layout.removeWidget(row)
        row.deleteLater()
        self._weighted_rows.remove(row)
        self._refresh_preview()

    def _on_add_weighted_screener(self) -> None:
        menu = QMenu(self)
        existing = {r.screener_id() for r in self._weighted_rows}
        added_any = False
        try:
            from us_swing.screener.registry import ScreenerRegistry
            available_ids = list(ScreenerRegistry.list_available())
        except Exception:  # noqa: BLE001
            available_ids = list(_SCREENER_DISPLAY)
        for sid in available_ids:
            if sid not in existing and sid not in _HIDDEN_SCREENER_IDS:
                act = menu.addAction(_SCREENER_DISPLAY.get(sid, sid))
                act.setData(sid)
                added_any = True
        if not added_any:
            menu.addAction("All screeners added").setEnabled(False)
        btn = self._add_screener_w_btn
        pos = btn.mapToGlobal(QPoint(0, btn.height()))
        chosen = menu.exec(pos)
        if chosen and chosen.data():
            n = len(self._weighted_rows) + 1
            self._add_weighted_row(chosen.data(), round(1.0 / n, 2))

    def _normalize_weights(self) -> None:
        n = len(self._weighted_rows)
        if n == 0:
            return
        w = round(1.0 / n, 4)
        for row in self._weighted_rows:
            row._spin.setValue(w)
        self._refresh_preview()

    # ── Type switch ───────────────────────────────────────────────────────

    def _on_type_changed(self, btn_id: int, checked: bool) -> None:
        if checked:
            self._stack.setCurrentIndex(btn_id)
            self._add_grp_btn.setVisible(btn_id == 0)  # only in Composite mode
            self._refresh_preview()

    def _is_composite(self) -> bool:
        return self._r_composite.isChecked()

    # ── Preview ───────────────────────────────────────────────────────────

    def _refresh_preview(self) -> None:
        if self._is_composite():
            lines: list[str] = []
            for i, w in enumerate(self._group_widgets, 1):
                sids   = w.screener_ids()
                labels = [_SCREENER_DISPLAY.get(s, s) for s in sids]
                lines.append(
                    f"Group {i} ({w.logic()}): "
                    + (", ".join(labels) if labels else "(empty)")
                )
            if len(self._group_widgets) > 1:
                groups_str = " OR ".join(f"G{i}" for i in range(1, len(self._group_widgets) + 1))
                lines.append(f"Final: {groups_str}")
            self._preview.setPlainText("\n".join(lines) or "(no groups yet)")
        else:
            parts = [
                f"{_SCREENER_DISPLAY.get(r.screener_id(), r.screener_id())}"
                f"×{r.weight():.2f}"
                for r in self._weighted_rows
            ]
            thr  = self._threshold.value()
            text = " + ".join(parts) if parts else "(no screeners yet)"
            text += f"\nThreshold: ≥ {thr:.2f}"
            self._preview.setPlainText(text)

    # ── Populate from existing preset (edit mode) ─────────────────────────

    def _collect_trading_styles(self) -> list[str]:
        return [v for v, cb in self._style_checks.items() if cb.isChecked()]

    def _populate_from_preset(self, preset: Any) -> None:
        self._name.setText(preset.name)
        self._desc.setText(getattr(preset, "description", ""))
        for val, cb in self._style_checks.items():
            cb.setChecked(val in getattr(preset, "trading_styles", []))
        tf = getattr(preset, "timeframe", "1d")
        idx = self._tf_preset.findData(tf)
        if idx >= 0:
            self._tf_preset.setCurrentIndex(idx)
        # AI Ranking (Stage 3) fields
        self._ai_ranking_chk.setChecked(getattr(preset, "enable_llm_ranking", False))
        self._ai_top_n.setValue(getattr(preset, "top_n", 5))
        _preset_model = getattr(preset, "ai_model", _CLOUD_AI_DEFAULT_MODEL) or _CLOUD_AI_DEFAULT_MODEL
        self._ai_model_edit.setText(_preset_model)
        self._ai_query_field.setText(getattr(preset, "ai_query", "") or "")

        from us_swing.screener.preset import PresetType
        if preset.preset_type == PresetType.WEIGHTED:
            self._r_weighted.setChecked(True)
            if preset.threshold is not None:
                self._threshold.setValue(preset.threshold)
            n = len(preset.screeners)
            for ref in preset.screeners:
                w = ref.weight if ref.weight is not None else (1.0 / n if n else 0.0)
                cfg = dict(ref.config or {})
                self._add_weighted_row(ref.screener_id, w, config=cfg or None)
        else:
            self._r_composite.setChecked(True)
            for group in preset.groups:
                cfgs = {r.screener_id: dict(r.config or {}) for r in group.screeners if r.config}
                self._add_group(
                    group.group_id,
                    group.logic.value if hasattr(group.logic, "value") else str(group.logic),
                    [r.screener_id for r in group.screeners],
                    configs=cfgs,
                )
            if not preset.groups:
                self._add_group()   # at least one group

    # ── Save / Save As ────────────────────────────────────────────────────

    def _build_preset_from_ui(self, preset_id: str | None = None) -> Any:
        from us_swing.screener.preset import (
            GroupLogic, Preset, PresetType, ScreenerGroup, ScreenerRef,
        )
        import uuid as _uuid

        pid  = preset_id or str(_uuid.uuid4())[:8]
        name = self._name.text().strip()

        enable_llm_ranking = self._ai_ranking_chk.isChecked()
        top_n              = self._ai_top_n.value()
        ai_model_stage3    = self._ai_model_edit.text().strip() or _CLOUD_AI_DEFAULT_MODEL
        ai_query_stage3    = self._ai_query_field.text().strip()

        if self._is_composite():
            groups = []
            for w in self._group_widgets:
                sids = w.screener_ids()
                cfgs = w.screener_configs()
                refs = [
                    ScreenerRef(screener_id=s, enabled=True, config=cfgs.get(s, {}))
                    for s in sids
                ]
                groups.append(
                    ScreenerGroup(
                        group_id=w.group_id(),
                        logic=GroupLogic(w.logic()),
                        screeners=refs,
                    )
                )
            return Preset(
                id=pid, name=name,
                description=self._desc.text().strip(),
                preset_type=PresetType.COMPOSITE,
                groups=groups,
                trading_styles=self._collect_trading_styles(),
                timeframe=self._tf_preset.currentData(),
                enable_llm_ranking=enable_llm_ranking,
                top_n=top_n,
                ai_model=ai_model_stage3,
                ai_query=ai_query_stage3,
            )
        else:
            refs = [
                ScreenerRef(
                    screener_id=r.screener_id(),
                    enabled=True,
                    weight=r.weight(),
                    config=r.config(),
                )
                for r in self._weighted_rows
            ]
            return Preset(
                id=pid, name=name,
                description=self._desc.text().strip(),
                preset_type=PresetType.WEIGHTED,
                screeners=refs,
                threshold=self._threshold.value(),
                trading_styles=self._collect_trading_styles(),
                timeframe=self._tf_preset.currentData(),
                enable_llm_ranking=enable_llm_ranking,
                top_n=top_n,
                ai_model=ai_model_stage3,
                ai_query=ai_query_stage3,
            )

    def _validate(self) -> str | None:
        """Return error message string if invalid, else None."""
        if not self._name.text().strip():
            return "Preset name is required."
        if self._is_composite():
            if not self._group_widgets:
                return "Add at least one group."
            for w in self._group_widgets:
                if not w.screener_ids():
                    return f"Group '{w.group_id()}' has no screeners."
        else:
            if not self._weighted_rows:
                return "Add at least one screener."
        return None

    def _on_save(self) -> None:
        err = self._validate()
        if err:
            self._name.setToolTip(err)
            self._name.setStyleSheet(
                f"border: 1px solid {C.RED}; background: {C.OVERLAY};"
                f" border-radius: 4px; color: {C.TEXT}; padding: 4px 8px;"
            )
            return
        self._name.setStyleSheet("")
        try:
            if self._preset is not None:
                # Edit mode — update existing preset
                updates = self._build_preset_from_ui(self._preset.id).__dict__.copy()
                if self._assign_widget is not None:
                    # Access writes happen immediately on picker-accept; don't
                    # let the empty-list default from _build_preset_from_ui clobber them.
                    updates.pop("assigned_to", None)
                self._mgr.update_preset(self._preset.id, updates, self._user_id)
                self._saved_id = self._preset.id
            else:
                p = self._build_preset_from_ui()
                self._mgr.create_preset(p, user_id=self._user_id)
                self._saved_id = p.id
            self.accept()
        except Exception as exc:  # noqa: BLE001
            self._name.setToolTip(str(exc))

    def _on_save_as(self) -> None:
        """Save a clone with a new name."""
        err = self._validate()
        if err:
            return
        import uuid as _uuid
        p = self._build_preset_from_ui(preset_id=str(_uuid.uuid4())[:8])
        p.name = p.name + " (copy)" if p.name == (self._preset.name if self._preset else p.name) else p.name
        try:
            self._mgr.create_preset(p, user_id=self._user_id)
            self._saved_id = p.id
            self.accept()
        except Exception as exc:  # noqa: BLE001
            self._name.setToolTip(str(exc))

    # ── Helpers ───────────────────────────────────────────────────────────

    def _on_model_text_changed(self) -> None:
        self._ai_model_status_lbl.setText("")

    def _on_validate_model(self) -> None:
        model_id = self._ai_model_edit.text().strip()
        if not model_id:
            self._ai_model_status_lbl.setStyleSheet(f"font-size: 8pt; color: {C.MUTED};")
            self._ai_model_status_lbl.setText("Enter a model ID first.")
            return
        self._ai_model_validate_btn.setEnabled(False)
        self._ai_model_validate_btn.setText("…")
        self._ai_model_status_lbl.setStyleSheet(f"font-size: 8pt; color: {C.MUTED};")
        self._ai_model_status_lbl.setText("Checking…")
        self._validate_worker = _ModelValidateWorker(model_id, parent=self)
        self._validate_worker.done.connect(self._on_validate_done)
        self._validate_worker.start()

    def _on_validate_done(self, ok: bool, message: str) -> None:
        self._ai_model_validate_btn.setEnabled(True)
        self._ai_model_validate_btn.setText("⚡  Validate")
        if ok:
            self._ai_model_status_lbl.setStyleSheet(f"font-size: 8pt; color: {C.GREEN};")
            self._ai_model_status_lbl.setText(f"✓  {message}")
        else:
            self._ai_model_status_lbl.setStyleSheet(f"font-size: 8pt; color: #e74c3c;")
            self._ai_model_status_lbl.setText(f"✗  {message}")

    @staticmethod
    def _lbl(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {C.MUTED}; font-size: 8pt;")
        return lbl

    def preset_id(self) -> str | None:
        return self._saved_id


# ── New preset dialog (LEGACY — replaced by _PresetBuilderDialog) ─────────────

class _NewPresetDialog(QDialog):
    """Simple dialog for creating a new Composite or Weighted preset."""

    def __init__(
        self,
        mgr: Any,
        user_id: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._mgr     = mgr
        self._user_id = user_id
        self._preset_id: str | None = None

        self.setWindowTitle("New Screener Preset")
        self.setMinimumWidth(400)
        self.setStyleSheet(
            f"QDialog {{ background: {C.BG}; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 14)
        layout.setSpacing(10)

        # Name
        layout.addWidget(self._label("Preset Name"))
        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. Daily RSI Momentum")
        layout.addWidget(self._name)

        # Description
        layout.addWidget(self._label("Description (optional)"))
        self._desc = QLineEdit()
        self._desc.setPlaceholderText("Brief description of this preset")
        layout.addWidget(self._desc)

        # Type
        layout.addWidget(self._label("Preset Type"))
        self._type_combo = QComboBox()
        self._type_combo.addItems(["Composite (AND/OR groups)", "Weighted (scored ensemble)"])
        layout.addWidget(self._type_combo)

        # Threshold (weighted only)
        self._threshold_row = QWidget()
        thr_layout = QHBoxLayout(self._threshold_row)
        thr_layout.setContentsMargins(0, 0, 0, 0)
        thr_layout.addWidget(self._label("Pass Threshold (0–1):"))
        self._threshold = QDoubleSpinBox()
        self._threshold.setRange(0.0, 1.0)
        self._threshold.setSingleStep(0.05)
        self._threshold.setValue(0.60)
        self._threshold.setDecimals(2)
        self._threshold.setFixedWidth(80)
        thr_layout.addWidget(self._threshold)
        thr_layout.addStretch()
        layout.addWidget(self._threshold_row)
        self._threshold_row.setVisible(False)
        self._type_combo.currentIndexChanged.connect(
            lambda i: self._threshold_row.setVisible(i == 1)
        )

        # Screener selection
        layout.addWidget(self._label("Include Screeners"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(160)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setStyleSheet(f"background: {C.SURFACE};")
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(8, 4, 8, 4)
        inner_layout.setSpacing(2)
        scroll.setWidget(inner)
        layout.addWidget(scroll)

        self._screener_checks: dict[str, QCheckBox] = {}
        _DISPLAY = {
            "indicator_composite": "Indicators",
            "price_action":        "Price Action",
            "llm_local_mistral":   "Local AI",
            "ml_ensemble_v3":      "Machine Learning Models",
            "mcp":                 "MCP",
        }
        try:
            from us_swing.screener.registry import ScreenerRegistry
            available = ScreenerRegistry.list_available()
        except Exception:  # noqa: BLE001
            available = {}

        for sid, _ in available.items():
            if sid in _HIDDEN_SCREENER_IDS:
                continue
            label = _DISPLAY.get(sid, sid)
            chk = QCheckBox(label)
            chk.setStyleSheet(f"color: {C.TEXT}; font-size: 9pt;")
            if sid == "indicator_composite":
                chk.setChecked(True)
            self._screener_checks[sid] = chk
            inner_layout.addWidget(chk)
        inner_layout.addStretch()

        # Buttons
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {C.MUTED}; font-size: 8pt;")
        return lbl

    def preset_id(self) -> str | None:
        return self._preset_id

    # ── Save ──────────────────────────────────────────────────────────────

    def _on_save(self) -> None:
        name = self._name.text().strip()
        if not name:
            self._name.setStyleSheet(
                f"border: 1px solid {C.RED}; background: {C.OVERLAY};"
                f" border-radius: 4px; color: {C.TEXT}; padding: 4px 8px;"
            )
            return

        selected_ids = [sid for sid, chk in self._screener_checks.items() if chk.isChecked()]
        if not selected_ids:
            return

        from us_swing.screener.preset import (
            GroupLogic,
            Preset,
            PresetType,
            ScreenerGroup,
            ScreenerRef,
        )

        pid = str(uuid.uuid4())[:8]
        is_weighted = self._type_combo.currentIndex() == 1

        if is_weighted:
            w = round(1.0 / len(selected_ids), 4)
            refs = [ScreenerRef(screener_id=sid, enabled=True, weight=w) for sid in selected_ids]
            preset = Preset(
                id=pid,
                name=name,
                description=self._desc.text().strip(),
                preset_type=PresetType.WEIGHTED,
                screeners=refs,
                threshold=self._threshold.value(),
            )
        else:
            refs = [ScreenerRef(screener_id=sid, enabled=True) for sid in selected_ids]
            group = ScreenerGroup(group_id="g1", logic=GroupLogic.AND, screeners=refs)
            preset = Preset(
                id=pid,
                name=name,
                description=self._desc.text().strip(),
                preset_type=PresetType.COMPOSITE,
                groups=[group],
            )

        try:
            self._mgr.create_preset(preset, user_id=self._user_id)
            self._preset_id = pid
            self.accept()
        except Exception as exc:  # noqa: BLE001
            self._name.setToolTip(str(exc))


# ── Screener panel (v2) ───────────────────────────────────────────────────────

class ScreenerPanel(QWidget):
    """FO-SCR-007 Screener Panel v2 — preset-based execution.

    Toolbar: Run Now / date navigation / status / Add to Watchlist.
    Left:    Preset list (admin + user + create-new).
    Right:   Results table (symbol · score · details · AI reasoning).
    """

    watchlist_add_requested = pyqtSignal(str)   # preserved — wired in main_window

    def __init__(self, demo: AppService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._demo = demo

        # ── Screener backend (lazy — fails gracefully) ─────────────────────
        self._mgr:     Any = None
        self._storage: Any = None
        self._init_backend()

        # ── State ──────────────────────────────────────────────────────────
        self._selected_preset_id:        str | None = None
        self._selected_preset_timeframe: str        = "1d"
        self._selected_preset:           Any        = None
        self._available_dates:           list[str]  = []
        self._date_idx:           int        = 0
        self._worker: _PresetRunWorker | None = None
        self._quick_chart_win: QuickChartWindow | None = None
        self._db_info:           Any        = None   # latest CandleDbInfo
        self._auto_run_queue:    list[str]  = []     # preset IDs pending auto-run

        # ── DB status subscription (SRD-SCR-004.007) ──────────────────────
        demo.candle_db_status_changed.connect(self._on_db_status_changed)

        # ── Build UI ───────────────────────────────────────────────────────
        toolbar      = self._build_toolbar()
        left_frame   = self._build_left_pane()
        right_widget = self._build_right_pane()

        body = QSplitter(Qt.Orientation.Horizontal)
        body.setHandleWidth(2)
        body.addWidget(left_frame)
        body.addWidget(right_widget)
        body.setSizes([260, 900])
        body.setCollapsible(0, False)
        body.setCollapsible(1, False)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(toolbar)
        root.addWidget(body, 1)

    # ── Backend init ──────────────────────────────────────────────────────

    def _init_backend(self) -> None:
        try:
            from us_swing.screener.manager import PresetManager
            from us_swing.screener.storage import ScreenerResultsStorage
            self._mgr     = PresetManager()
            self._storage = ScreenerResultsStorage()
        except Exception:  # noqa: BLE001
            self._mgr     = None
            self._storage = None

    # ── Toolbar ───────────────────────────────────────────────────────────

    def _build_toolbar(self) -> QFrame:
        _BTN_H = 30   # unified height for all toolbar interactive controls

        self._run_btn = QPushButton("▶  Run Now")
        self._run_btn.setObjectName("run_btn")
        self._run_btn.setFixedHeight(_BTN_H)
        self._run_btn.setMinimumWidth(110)
        self._run_btn.setEnabled(False)
        self._run_btn.clicked.connect(self._run_preset)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedHeight(4)
        self._progress.setFixedWidth(100)
        self._progress.setVisible(False)

        # Date navigation — square arrow buttons; font/padding defined by #btn_nav in theme
        self._nav_prev = QPushButton("‹")
        self._nav_prev.setObjectName("btn_nav")
        self._nav_prev.setFixedWidth(28)
        self._nav_prev.setEnabled(False)
        self._nav_prev.setToolTip("Older result")
        self._nav_prev.clicked.connect(lambda: self._navigate_date(+1))

        self._date_lbl = QLabel("—")
        self._date_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._date_lbl.setMinimumWidth(90)
        self._date_lbl.setStyleSheet(f"color: {C.SUBTEXT}; font-size: 9pt;")

        self._nav_next = QPushButton("›")
        self._nav_next.setObjectName("btn_nav")
        self._nav_next.setFixedWidth(28)
        self._nav_next.setEnabled(False)
        self._nav_next.setToolTip("Newer result")
        self._nav_next.clicked.connect(lambda: self._navigate_date(-1))

        self._mode_badge = QLabel()
        self._mode_badge.setFixedHeight(20)
        self._mode_badge.setVisible(False)

        self._status_lbl = QLabel("Select a preset to begin")
        self._status_lbl.setStyleSheet(f"color: {C.MUTED}; font-size: 9pt;")

        self._export_btn = QPushButton("⬇  CSV")
        self._export_btn.setFixedWidth(86)
        self._export_btn.setEnabled(False)
        self._export_btn.setToolTip("Export results to CSV")
        self._export_btn.clicked.connect(self._export_csv)

        self._add_btn = QPushButton("＋  Watchlist")
        self._add_btn.setObjectName("add_btn")
        self._add_btn.setEnabled(False)
        self._add_btn.setFixedHeight(_BTN_H)
        self._add_btn.setFixedWidth(110)
        self._add_btn.clicked.connect(self._on_add_watchlist)

        toolbar = QFrame()
        toolbar.setObjectName("screener_toolbar")
        toolbar.setFixedHeight(58)
        toolbar.setStyleSheet(
            f"QFrame#screener_toolbar {{ background: {C.BG};"
            f" border-bottom: 1px solid {C.OVERLAY}; }}"
        )
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(14, 0, 14, 8)
        tb.setSpacing(8)
        tb.addWidget(self._run_btn)
        tb.addSpacing(10)
        tb.addWidget(self._nav_prev)
        tb.addWidget(self._date_lbl)
        tb.addWidget(self._nav_next)
        tb.addSpacing(4)
        tb.addWidget(self._mode_badge)
        tb.addStretch()
        tb.addWidget(self._status_lbl)
        tb.addSpacing(8)
        tb.addWidget(self._progress)
        tb.addSpacing(8)
        tb.addWidget(self._export_btn)
        tb.addSpacing(6)
        tb.addWidget(self._add_btn)
        return toolbar

    # ── Left pane (preset list) ───────────────────────────────────────────

    def _build_left_pane(self) -> QFrame:
        header = QLabel("PRESETS")
        header.setStyleSheet(
            f"color: {C.MUTED}; font-size: 7pt; letter-spacing: 2px;"
            f" font-weight: bold; padding: 8px 12px 4px 12px;"
        )

        # Style filter dropdown (SRD-SCR-007.010)
        self._style_combo = QComboBox()
        for label, value in _STYLE_OPTIONS:
            self._style_combo.addItem(label, value)
        self._style_combo.setFixedHeight(26)
        self._style_combo.setStyleSheet(
            f"QComboBox {{ background: {C.OVERLAY}; color: {C.TEXT};"
            f" border: 1px solid {C.OVERLAY2}; border-radius: 4px;"
            f" padding: 2px 8px; font-size: 8pt; margin: 0 8px 4px 8px; outline: none; }}"
            f"QComboBox:focus {{ border: 1px solid {C.BLUE}; outline: none; }}"
            f"QComboBox::drop-down {{ border: none; width: 16px; }}"
        )
        self._style_combo.currentIndexChanged.connect(self._on_style_filter_changed)

        self._preset_list = QListWidget()
        self._preset_list.setStyleSheet(
            f"QListWidget {{ border: none; background: {C.SURFACE}; outline: none; }}"
            f"QListWidget::item {{ padding: 6px 10px; border-bottom: 1px solid {C.OVERLAY}; }}"
            f"QListWidget::item:selected {{ background: #1a2d45; color: {C.BLUE}; }}"
            f"QListWidget::item:focus {{ outline: none; border: none; }}"
            f"QListWidget::item:hover:!selected {{ background: {C.OVERLAY}22; }}"
        )
        self._preset_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._preset_list.itemClicked.connect(self._on_preset_clicked)
        self._preset_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._preset_list.customContextMenuRequested.connect(self._on_preset_context_menu)

        self._new_btn = QPushButton("＋  New Preset")
        self._new_btn.setObjectName("add_btn")
        self._new_btn.setEnabled(self._mgr is not None)
        self._new_btn.clicked.connect(self._on_new_preset)

        frame = QFrame()
        frame.setObjectName("preset_pane")
        frame.setFixedWidth(260)
        frame.setStyleSheet(
            f"QFrame#preset_pane {{ background: {C.SURFACE};"
            f" border-right: 1px solid {C.OVERLAY}; }}"
        )
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(0)
        fl.addWidget(header)
        fl.addWidget(self._style_combo)
        fl.addWidget(self._preset_list, 1)

        btn_row = QWidget()
        btn_row.setStyleSheet(f"background: {C.SURFACE};")
        br = QVBoxLayout(btn_row)
        br.setContentsMargins(8, 6, 8, 8)
        br.setSpacing(6)
        br.addWidget(self._new_btn)
        fl.addWidget(btn_row)

        self._populate_preset_list()
        return frame

    # ── Right pane (results) ──────────────────────────────────────────────

    def _build_right_pane(self) -> QWidget:
        # Empty state overlay
        self._empty_lbl = QLabel("Select a preset from the list\nand click ▶ Run Now")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(
            f"color: {C.MUTED}; font-size: 12pt; padding: 40px;"
        )

        # Results table
        self._model = _ResultsModel()
        self._proxy = QSortFilterProxyModel()
        self._proxy.setSourceModel(self._model)

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.sortByColumn(1, Qt.SortOrder.DescendingOrder)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setWordWrap(True)
        self._table.setStyleSheet(
            f"QTableView {{ border: none; background: {C.BG}; outline: none; }}"
            "QTableView::item { padding: 5px 8px; }"
            "QTableView::item:focus { outline: none; border: none; }"
        )

        hdrs = self._table.horizontalHeader()
        hdrs.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)   # Symbol
        hdrs.resizeSection(0, 80)
        hdrs.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)          # Chart button
        hdrs.resizeSection(1, 56)
        hdrs.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)   # Score
        hdrs.resizeSection(2, 72)
        hdrs.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)   # Details
        hdrs.resizeSection(3, 200)
        hdrs.setStretchLastSection(True)                                    # AI Reasoning fills remainder
        hdrs.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        hdrs.sectionDoubleClicked.connect(self._table.resizeColumnToContents)

        self._table.setItemDelegateForColumn(_CHART_COL, _ChartButtonDelegate(self._table))
        self._table.setMouseTracking(True)
        self._table.viewport().setMouseTracking(True)
        self._table.clicked.connect(self._on_table_clicked)

        self._table.selectionModel().selectionChanged.connect(self._on_selection)
        self._table.setVisible(False)

        table_container = QWidget()
        cl = QVBoxLayout(table_container)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        cl.addWidget(self._empty_lbl, 1)
        cl.addWidget(self._table, 1)

        self._transcript_panel = AITranscriptPanel()
        self._transcript_panel.setVisible(False)

        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.setHandleWidth(2)
        right_splitter.addWidget(table_container)
        right_splitter.addWidget(self._transcript_panel)
        right_splitter.setSizes([700, 300])
        right_splitter.setCollapsible(0, False)
        right_splitter.setCollapsible(1, True)
        return right_splitter

    # ── Preset list population ────────────────────────────────────────────

    def _on_style_filter_changed(self) -> None:
        self._populate_preset_list()

    def _populate_preset_list(self) -> None:
        self._preset_list.clear()
        if self._mgr is None:
            item = QListWidgetItem("Backend unavailable")
            item.setForeground(QColor(C.RED))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._preset_list.addItem(item)
            return

        style_filter: str | None = self._style_combo.currentData()
        uid = str(self._demo.get_active_user().user_id)
        try:
            admin_presets = self._mgr.list_admin_presets(style_filter=style_filter)
            user_presets  = self._mgr.list_user_presets(uid, style_filter=style_filter)
        except Exception:  # noqa: BLE001
            admin_presets, user_presets = [], []

        if not admin_presets and not user_presets:
            item = QListWidgetItem("No presets yet — create one below")
            item.setForeground(QColor(C.MUTED))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._preset_list.addItem(item)
            return

        if admin_presets:
            self._add_section_header("ADMIN")
            for p in admin_presets:
                self._add_preset_item(p)

        if user_presets:
            self._add_section_header("MINE")
            for p in user_presets:
                self._add_preset_item(p)

    def _add_section_header(self, text: str) -> None:
        item = QListWidgetItem(f"  {text}")
        item.setForeground(QColor(C.MUTED))
        item.setFont(self._section_font())
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setBackground(QColor(C.OVERLAY))
        self._preset_list.addItem(item)

    def _add_preset_item(self, preset: Any) -> None:
        type_tag = "C" if str(preset.preset_type).endswith("composite") else "W"
        item = QListWidgetItem(f"  {preset.name}  [{type_tag}]")
        item.setData(Qt.ItemDataRole.UserRole, preset.id)
        item.setForeground(QColor(C.TEXT))
        self._preset_list.addItem(item)

    @staticmethod
    def _section_font() -> QFont:
        f = QFont()
        f.setPointSize(7)
        f.setBold(True)
        return f

    # ── Preset selection ──────────────────────────────────────────────────

    def _on_preset_clicked(self, item: QListWidgetItem) -> None:
        pid = item.data(Qt.ItemDataRole.UserRole)
        if not pid:
            return
        self._selected_preset_id = pid
        if self._mgr is not None:
            try:
                uid = str(self._demo.get_active_user().user_id)
                _p = self._mgr.load_preset(pid, uid)
                self._selected_preset_timeframe = getattr(_p, "timeframe", "1d")
                self._selected_preset = _p
            except Exception:  # noqa: BLE001
                self._selected_preset_timeframe = "1d"
                self._selected_preset = None
        self._run_btn.setEnabled(True)
        self._refresh_date_nav()
        self._refresh_transcript_visibility()
        self._maybe_auto_run()

    def _refresh_date_nav(self) -> None:
        if not self._selected_preset_id or self._storage is None:
            self._available_dates = []
            self._date_idx        = 0
            self._date_lbl.setText("—")
            self._nav_prev.setEnabled(False)
            self._nav_next.setEnabled(False)
            return

        try:
            self._available_dates = self._storage.list_results(self._selected_preset_id)
        except Exception:  # noqa: BLE001
            self._available_dates = []

        if self._available_dates:
            self._date_idx = 0
            self._update_date_display()
            self._load_result_for_current_date()
        else:
            self._date_lbl.setText("no history")
            self._nav_prev.setEnabled(False)
            self._nav_next.setEnabled(False)
            self._show_empty("Run the screener to see results")

    def _update_date_display(self) -> None:
        dates = self._available_dates
        if not dates:
            self._date_lbl.setText("—")
            self._nav_prev.setEnabled(False)
            self._nav_next.setEnabled(False)
            return
        self._date_lbl.setText(dates[self._date_idx])
        self._nav_prev.setEnabled(self._date_idx < len(dates) - 1)
        self._nav_next.setEnabled(self._date_idx > 0)

    def _navigate_date(self, delta: int) -> None:
        new_idx = self._date_idx + delta
        if 0 <= new_idx < len(self._available_dates):
            self._date_idx = new_idx
            self._update_date_display()
            self._load_result_for_current_date()

    def _load_result_for_current_date(self) -> None:
        if not self._available_dates or self._storage is None:
            return
        date = self._available_dates[self._date_idx]
        try:
            result = self._storage.load_result(self._selected_preset_id, date)
            self._display_result(result)
        except Exception as exc:  # noqa: BLE001
            self._show_error(f"Could not load result for {date}: {exc}")

    def _on_db_status_changed(self, info: Any) -> None:
        """Cache latest CandleDbInfo and fire auto-run if DB just became CURRENT."""
        self._db_info = info
        self._maybe_auto_run()

    def _maybe_auto_run(self) -> None:
        """Auto-run today's screener (SRD-SCR-004.007).

        Fires when: flag ON, DB CURRENT, worker idle.
        Candidates: all presets (admin + user) where assigned_to is non-empty.
        Skips any preset that already has a scheduled result for today.
        Multiple candidates are queued and drained one at a time.
        """
        from us_swing.gui.system_store import load_system_config
        if not load_system_config().scheduler_enabled:
            return
        if self._mgr is None or self._storage is None:
            return
        if self._worker is not None and self._worker.isRunning():
            return
        try:
            from us_swing.gui.app_service import CandleDbStatus
            if self._db_info is None or self._db_info.status != CandleDbStatus.CURRENT:
                return
        except Exception:  # noqa: BLE001
            return
        try:
            uid = str(self._demo.get_active_user().user_id)
            admin_presets = self._mgr.list_admin_presets() or []
            user_presets = self._mgr.list_user_presets(uid) or []
        except Exception:  # noqa: BLE001
            return
        today = _date.today().isoformat()
        to_run: list[str] = []
        seen: set[str] = set()
        for preset in admin_presets + user_presets:
            if not getattr(preset, "assigned_to", []):
                continue  # not assigned to anyone — not an auto-run candidate
            if preset.id in seen:
                continue
            seen.add(preset.id)
            try:
                result = self._storage.load_result(preset.id, today)
                if getattr(result, "execution_mode", "") == "scheduled":
                    continue  # already auto-ran today
            except FileNotFoundError:
                pass
            to_run.append(preset.id)
        if not to_run:
            return
        self._auto_run_queue = to_run[1:]
        self._run_preset_as(preset_id=to_run[0], manual=False)

    # ── Run preset ────────────────────────────────────────────────────────

    def _run_preset(self) -> None:
        self._run_preset_as(preset_id=self._selected_preset_id, manual=True)

    def _run_preset_as(self, preset_id: str | None = None, manual: bool = True) -> None:
        if not preset_id or self._mgr is None:
            return
        if not manual:
            self._select_preset_in_list(preset_id)
        self._run_btn.setEnabled(False)
        self._run_btn.setText("Running…")
        self._progress.setVisible(True)
        status_msg = "Scanning symbols…" if manual else "Auto-running screener…"
        self._status_lbl.setText(status_msg)
        self._status_lbl.setStyleSheet(f"color: {C.SUBTEXT}; font-size: 9pt;")

        uid = str(self._demo.get_active_user().user_id)
        timeframe = self._selected_preset_timeframe
        self._worker = _PresetRunWorker(
            preset_id=preset_id,
            user_id=uid,
            svc=self._demo,
            mgr=self._mgr,
            storage=self._storage,
            timeframe=timeframe,
            manual=manual,
            parent=self,
        )
        self._worker.finished.connect(self._on_run_finished)
        self._worker.failed.connect(self._on_run_failed)
        self._worker.start()

    def _select_preset_in_list(self, preset_id: str) -> None:
        """Programmatically select a preset in the left list without re-triggering auto-run."""
        for i in range(self._preset_list.count()):
            item = self._preset_list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == preset_id:
                self._preset_list.setCurrentItem(item)
                self._selected_preset_id = preset_id
                if self._mgr is not None:
                    try:
                        uid = str(self._demo.get_active_user().user_id)
                        p = self._mgr.load_preset(preset_id, uid)
                        self._selected_preset_timeframe = getattr(p, "timeframe", "1d")
                        self._selected_preset = p
                    except Exception:  # noqa: BLE001
                        self._selected_preset_timeframe = "1d"
                        self._selected_preset = None
                self._run_btn.setEnabled(True)
                self._refresh_transcript_visibility()
                break

    def _on_run_finished(self, result: Any) -> None:
        self._run_btn.setEnabled(True)
        self._run_btn.setText("▶  Run Now")
        self._progress.setVisible(False)
        self._export_btn.setEnabled(True)

        # Refresh date list (new file was just written)
        try:
            self._available_dates = self._storage.list_results(self._selected_preset_id)
            self._date_idx = 0
            self._update_date_display()
        except Exception:  # noqa: BLE001
            pass

        self._display_result(result)

        # Notify Execution panel so its Filtered Stocks pane refreshes immediately
        try:
            self._svc.notify_screener_results_updated()
        except Exception:  # noqa: BLE001
            pass

        # Drain auto-run queue: start next assigned preset if any remain
        if self._auto_run_queue:
            next_id = self._auto_run_queue.pop(0)
            self._run_preset_as(preset_id=next_id, manual=False)

    def _on_run_failed(self, reason: str) -> None:
        self._run_btn.setEnabled(True)
        self._run_btn.setText("▶  Run Now")
        self._progress.setVisible(False)
        self._show_error(reason)

    # ── Display helpers ───────────────────────────────────────────────────

    def _refresh_transcript_visibility(self) -> None:
        """Show the transcript panel only when the active preset uses LLM ranking."""
        llm_enabled = bool(getattr(self._selected_preset, "enable_llm_ranking", False))
        if not llm_enabled:
            self._transcript_panel.setVisible(False)
            self._transcript_panel.clear()
        else:
            self._transcript_panel.setVisible(True)

    def _display_result(self, result: Any) -> None:
        """Populate the results table from a ScreenerRunResult."""
        rows = self._build_rows(result)
        count = len(rows)
        self._model.load(rows)
        self._table.resizeRowsToContents()

        mode = getattr(result, "execution_mode", "manual")
        self._update_mode_badge(mode)

        self._status_lbl.setText(
            f"{count} symbol{'s' if count != 1 else ''} matched"
            f"  ·  sorted by score ↓"
        )
        self._status_lbl.setStyleSheet(
            f"color: {C.SUBTEXT if count > 0 else C.MUTED}; font-size: 9pt;"
        )
        self._export_btn.setEnabled(count > 0)
        self._show_table(has_data=count > 0)

        transcript = list(getattr(result, "ai_transcript", None) or [])
        if transcript:
            self._transcript_panel.load_transcript(
                transcript,
                cost_per_1k_in=INPUT_COST_PER_1K,
                cost_per_1k_out=OUTPUT_COST_PER_1K,
            )
        else:
            self._transcript_panel.clear()
        self._refresh_transcript_visibility()

    def _build_rows(self, result: Any) -> list[_Row]:
        # Resolve indicator config summary once for the active preset
        _ind_cfg_summary = ""
        if self._mgr is not None and self._selected_preset_id:
            try:
                uid = str(self._demo.get_active_user().user_id)
                preset = self._mgr.load_preset(self._selected_preset_id, uid)
                refs = list(getattr(preset, "screeners", None) or [])
                for grp in getattr(preset, "groups", None) or []:
                    refs.extend(getattr(grp, "screeners", []))
                for ref in refs:
                    if getattr(ref, "screener_id", "") == _INDICATOR_SCREENER_ID:
                        cfg = getattr(ref, "config", None) or {}
                        if cfg:
                            _ind_cfg_summary = _format_indicator_config(cfg)
                        break
            except Exception:  # noqa: BLE001
                pass

        rows: list[_Row] = []
        results_dict: dict = getattr(result, "results", {})
        for symbol, meta in results_dict.items():
            score = float(meta.get("score", 0.0))

            # Details: full per-screener breakdown + indicator config summary
            details_dict = meta.get("details", {})
            if details_dict:
                detail_parts = []
                for k, v in details_dict.items():
                    short = k.split("_")[0]
                    if isinstance(v, bool):
                        detail_parts.append(f"{short}:{'✔' if v else '✘'}")
                    elif isinstance(v, (int, float)):
                        detail_parts.append(f"{short}:{float(v):.2f}")
                    else:
                        detail_parts.append(f"{short}:{v}")
                details_str = "  ·  ".join(detail_parts)
            else:
                details_str = "—"

            if _ind_cfg_summary:
                details_str = f"[{_ind_cfg_summary}]  {details_str}"

            ai_reasoning = str(meta.get("ai_reasoning", "") or "")
            rows.append(_Row(symbol=symbol, score=score,
                             details=details_str, ai_reasoning=ai_reasoning))

        rows.sort(key=lambda r: r.score, reverse=True)
        return rows

    def _update_mode_badge(self, mode: str) -> None:
        if mode == "scheduled":
            self._mode_badge.setText("Auto")
            self._mode_badge.setStyleSheet(
                f"color:{C.TEAL};background:#12302e;border:1px solid {C.TEAL};"
                "border-radius:8px;padding:2px 8px;font-size:7pt;font-weight:bold;"
            )
        else:
            self._mode_badge.setText("Manual")
            self._mode_badge.setStyleSheet(
                f"color:{C.BLUE};background:#1a2d45;border:1px solid {C.BLUE};"
                "border-radius:8px;padding:2px 8px;font-size:7pt;font-weight:bold;"
            )
        self._mode_badge.setVisible(True)

    def _show_table(self, *, has_data: bool) -> None:
        self._empty_lbl.setVisible(not has_data)
        self._table.setVisible(has_data)

    def _show_empty(self, message: str = "Select a preset from the list\nand click ▶ Run Now") -> None:
        self._empty_lbl.setText(message)
        self._empty_lbl.setStyleSheet(f"color: {C.MUTED}; font-size: 12pt; padding: 40px;")
        self._table.setVisible(False)
        self._empty_lbl.setVisible(True)

    def _show_error(self, reason: str) -> None:
        self._status_lbl.setText(f"⚠  {reason[:120]}")
        self._status_lbl.setStyleSheet(f"color: {C.RED}; font-size: 9pt;")
        self._show_empty(f"⚠  Run failed:\n{reason[:200]}")
        self._empty_lbl.setStyleSheet(f"color: {C.RED}; font-size: 10pt; padding: 40px;")

    # ── Preset context menu ───────────────────────────────────────────────

    def _on_preset_context_menu(self, pos: Any) -> None:
        item = self._preset_list.itemAt(pos)
        if not item or not item.data(Qt.ItemDataRole.UserRole):
            return
        menu = QMenu(self)
        menu.addAction(QAction("✏  Edit", self, triggered=self._on_edit_preset))
        menu.addAction(QAction("⧉  Duplicate", self, triggered=self._on_duplicate_preset))
        menu.addSeparator()
        menu.addAction(QAction("🗑  Delete", self, triggered=self._on_delete_preset))
        menu.exec(self._preset_list.viewport().mapToGlobal(pos))

    def _on_edit_preset(self) -> None:
        if self._mgr is None:
            return
        item = self._preset_list.currentItem()
        if not item:
            return
        pid = item.data(Qt.ItemDataRole.UserRole)
        if not pid:
            return
        uid = str(self._demo.get_active_user().user_id)
        try:
            preset = self._mgr.load_preset(pid, uid)
        except Exception:  # noqa: BLE001
            return
        dlg = _PresetBuilderDialog(mgr=self._mgr, user_id=uid, preset=preset, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._populate_preset_list()
            saved = dlg.preset_id()
            if saved:
                self._select_preset_by_id(saved)

    def _on_duplicate_preset(self) -> None:
        if self._mgr is None:
            return
        item = self._preset_list.currentItem()
        if not item:
            return
        pid = item.data(Qt.ItemDataRole.UserRole)
        if not pid:
            return
        uid = str(self._demo.get_active_user().user_id)
        try:
            original = self._mgr.load_preset(pid, uid)
        except Exception:  # noqa: BLE001
            return
        # Open builder pre-populated but in create mode (preset=None), name suffixed
        dlg = _PresetBuilderDialog(mgr=self._mgr, user_id=uid, preset=None, parent=self)
        dlg._populate_from_preset(original)
        dlg._name.setText(original.name + " (copy)")
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._populate_preset_list()
            saved = dlg.preset_id()
            if saved:
                self._select_preset_by_id(saved)

    def _on_delete_preset(self) -> None:
        if self._mgr is None:
            return
        item = self._preset_list.currentItem()
        if not item:
            return
        pid = item.data(Qt.ItemDataRole.UserRole)
        if not pid:
            return
        name = item.text().strip()
        reply = QMessageBox.question(
            self,
            "Delete Preset",
            f'Delete preset "{name}"?\nThis cannot be undone.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        uid = str(self._demo.get_active_user().user_id)
        try:
            self._mgr.delete_preset(pid, uid)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Delete Failed", str(exc))
            return
        if self._selected_preset_id == pid:
            self._selected_preset_id = None
            self._run_btn.setEnabled(False)
            self._show_empty()
        self._populate_preset_list()

    # ── New preset dialog ─────────────────────────────────────────────────

    def _on_new_preset(self) -> None:
        if self._mgr is None:
            return
        uid = str(self._demo.get_active_user().user_id)
        dlg = _PresetBuilderDialog(mgr=self._mgr, user_id=uid, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._populate_preset_list()
            new_pid = dlg.preset_id()
            if new_pid:
                self._select_preset_by_id(new_pid)

    def _select_preset_by_id(self, preset_id: str) -> None:
        for i in range(self._preset_list.count()):
            item = self._preset_list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == preset_id:
                self._preset_list.setCurrentItem(item)
                self._on_preset_clicked(item)
                break

    # ── Quick chart ───────────────────────────────────────────────────────

    def _on_table_clicked(self, proxy_index: QModelIndex) -> None:
        if proxy_index.column() != _CHART_COL:
            return
        src_index = self._proxy.mapToSource(proxy_index)
        row = self._model.row_at(src_index.row())
        if row:
            self._open_quick_chart(row.symbol)

    def _open_quick_chart(self, symbol: str) -> None:
        if self._quick_chart_win is None or not self._quick_chart_win.isVisible():
            self._quick_chart_win = QuickChartWindow(self._demo)
        self._quick_chart_win.open_symbol(symbol, self._selected_preset_timeframe)
        self._quick_chart_win.show()
        self._quick_chart_win.raise_()
        self._quick_chart_win.activateWindow()

    # ── Selection / watchlist ─────────────────────────────────────────────

    def _on_selection(self) -> None:
        has_row = bool(self._table.selectionModel().selectedRows())
        self._add_btn.setEnabled(has_row)

    def _on_add_watchlist(self) -> None:
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return
        src_idx = self._proxy.mapToSource(indexes[0])
        row = self._model.row_at(src_idx.row())
        if row:
            self.watchlist_add_requested.emit(row.symbol)
            self._status_lbl.setText(f"✔  {row.symbol} added to watchlist")
            self._status_lbl.setStyleSheet(f"color: {C.GREEN}; font-size: 9pt;")

    # ── CSV export ────────────────────────────────────────────────────────

    def _export_csv(self) -> None:
        if self._model.rowCount() == 0:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Screener Results", "screener_results.csv",
            "CSV files (*.csv)"
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(["Symbol", "Score", "Details", "AI Reasoning"])
                for i in range(self._model.rowCount()):
                    r = self._model.row_at(i)
                    if r:
                        w.writerow([r.symbol, f"{r.score:.4f}", r.details,
                                    r.ai_reasoning])
            self._status_lbl.setText(f"✔  Exported {self._model.rowCount()} rows to CSV")
            self._status_lbl.setStyleSheet(f"color: {C.GREEN}; font-size: 9pt;")
        except Exception as exc:  # noqa: BLE001
            self._show_error(f"Export failed: {exc}")
