"""
Module: MD-GUI-013.001.M01 — StrategyBuilderDialog
Parent SRD: SRD-GUI-013.001
"""
from __future__ import annotations

from PyQt6.QtCore import QByteArray, QDate, QPoint, QSize, Qt, QTime, pyqtSignal
from PyQt6.QtGui import QColor, QDoubleValidator, QIcon, QIntValidator, QMouseEvent, QPainter, QPen, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QTimeEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from us_swing.gui.theme import C, active_palette


# ── Indicator catalogue ────────────────────────────────────────────────────────

_INDICATOR_DATA: list[dict] = [
    {
        "name": "Number",
        "parameters": [{"name": "Count", "Type": "EditBox", "Datatype": "float"}],
    },
    {
        "name": "PNL",
        "parameters": [
            {"name": "Timeframe", "Type": "DropDown", "Datatype": ["3m", "15m", "1d", "1w"]},
        ],
    },
    {
        "name": "VWAP",
        "parameters": [
            {"name": "Symbol Type", "Type": "DropDown", "Datatype": ["Spot", "RSP"]},
            {"name": "Timeframe", "Type": "DropDown", "Datatype": ["3m", "15m", "1d", "1w"]},
        ],
    },
    {
        "name": "Price",
        "parameters": [
            {"name": "Symbol Type", "Type": "DropDown", "Datatype": ["Spot", "RSP"]},
            {"name": "Candle", "Type": "DropDown", "Datatype": ["Last", "Current"]},
            {
                "name": "Price Type",
                "Type": "DropDown",
                "Datatype": ["close", "high", "low", "open"],
            },
            {
                "name": "Timeframe",
                "Type": "DropDown",
                "Datatype": ["3m", "15m", "1d", "1w"],
            },
        ],
    },
    {
        "name": "RSI",
        "parameters": [
            {"name": "Symbol Type", "Type": "DropDown", "Datatype": ["Spot", "RSP"]},
            {"name": "RSI Length", "Type": "EditBox", "Datatype": "int"},
            {
                "name": "Timeframe",
                "Type": "DropDown",
                "Datatype": ["3m", "15m", "1d", "1w"],
            },
        ],
    },
    {
        "name": "ADX",
        "parameters": [
            {"name": "Symbol Type", "Type": "DropDown", "Datatype": ["Spot", "RSP"]},
            {"name": "ADX Length", "Type": "EditBox", "Datatype": "int"},
            {
                "name": "Timeframe",
                "Type": "DropDown",
                "Datatype": ["3m", "15m", "1d", "1w"],
            },
        ],
    },
    {
        "name": "EMA",
        "parameters": [
            {"name": "Symbol Type", "Type": "DropDown", "Datatype": ["Spot", "RSP"]},
            {"name": "EMA Period", "Type": "EditBox", "Datatype": "int"},
            {
                "name": "Timeframe",
                "Type": "DropDown",
                "Datatype": ["3m", "15m", "1d", "1w"],
            },
        ],
    },
    {
        "name": "SUPERTREND",
        "parameters": [
            {"name": "Symbol Type", "Type": "DropDown", "Datatype": ["Spot", "RSP"]},
            {"name": "ATR Length", "Type": "EditBox", "Datatype": "int"},
            {"name": "Factor", "Type": "EditBox", "Datatype": "int"},
            {
                "name": "Absolute Price Deviation",
                "Type": "DropDown",
                "Datatype": ["No", "Yes"],
            },
            {
                "name": "Timeframe",
                "Type": "DropDown",
                "Datatype": ["3m", "15m", "1d", "1w"],
            },
        ],
    },
    {
        "name": "SWING",
        "parameters": [
            {"name": "Symbol Type", "Type": "DropDown", "Datatype": ["Spot", "RSP"]},
            {"name": "Candles", "Type": "EditBox", "Datatype": "int"},
            {"name": "LookbackDays", "Type": "EditBox", "Datatype": "int"},
            {
                "name": "Price Swing",
                "Type": "DropDown",
                "Datatype": ["High", "Low", "Range"],
            },
            {"name": "Type", "Type": "DropDown", "Datatype": ["Day", "Recent", "Old"]},
            {
                "name": "Timeframe",
                "Type": "DropDown",
                "Datatype": ["3m", "15m", "1d", "1w"],
            },
        ],
    },
    {
        "name": "MACD",
        "parameters": [
            {"name": "Symbol Type", "Type": "DropDown", "Datatype": ["Spot", "RSP"]},
            {"name": "MACD Fast", "Type": "EditBox", "Datatype": "int"},
            {"name": "MACD Slow", "Type": "EditBox", "Datatype": "int"},
            {"name": "MACD Signal", "Type": "EditBox", "Datatype": "int"},
            {
                "name": "Timeframe",
                "Type": "DropDown",
                "Datatype": ["3m", "15m", "1d", "1w"],
            },
        ],
    },
]

_INDICATOR_NAMES = [ind["name"] for ind in _INDICATOR_DATA]

# ── Strategy type constants ────────────────────────────────────────────────────

STRATEGY_DISPLAY_NAMES = ["BOSS EMA", "BOSS ADX", "BOSS SMT", "EMA Crossover", "Custom"]

STRATEGY_TYPE_MAP: dict[str, str] = {
    "BOSS EMA": "boss_ema",
    "BOSS ADX": "boss_adx",
    "BOSS SMT": "boss_smt",
    "EMA Crossover": "ema_crossover",
    "Custom": "custom",
}

_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
_DAY_LABELS: dict[str, str] = {
    "Monday": "MO", "Tuesday": "TU", "Wednesday": "WE",
    "Thursday": "TH", "Friday": "FR",
}

# StrategyConfig and its persistence now live in ``strategy_store`` (DB-backed).
# Re-exported here so existing ``from strategy_builder_dialog import ...`` callers
# keep working unchanged.
from us_swing.gui.strategy_store import StrategyConfig as StrategyConfig  # noqa: E402
from us_swing.gui.strategy_store import load_strategies as load_strategies  # noqa: E402
from us_swing.gui.strategy_store import save_strategies as save_strategies  # noqa: E402


# ── Shared helpers ─────────────────────────────────────────────────────────────

_INPUT_SS = "outline: none;"
_FOCUS_SS = "outline: none;"

_BTN_STYLE = (
    "QPushButton {{ background: transparent; color: {fg}; border: none;"
    " font-size: 14px; min-width: 32px; max-width: 32px;"
    " min-height: 28px; max-height: 28px; border-radius: 4px; }}"
    "QPushButton:hover {{ background: {hover}; }}"
)


def _combo_ss() -> str:
    return f"QComboBox {{ {_INPUT_SS} }} QComboBox:focus {{ {_FOCUS_SS} }}"


def _line_ss() -> str:
    return f"QLineEdit {{ {_INPUT_SS} }} QLineEdit:focus {{ {_FOCUS_SS} }}"


def _spin_ss() -> str:
    return f"QSpinBox {{ {_INPUT_SS} }} QSpinBox:focus {{ {_FOCUS_SS} }}"


def _double_spin_ss() -> str:
    return f"QDoubleSpinBox {{ {_INPUT_SS} }} QDoubleSpinBox:focus {{ {_FOCUS_SS} }}"


def _list_ss() -> str:
    P = active_palette()
    return (
        f"QListWidget {{ background: {P.SURFACE}; border: 1px solid {P.OVERLAY2};"
        f" border-radius: 3px; outline: none; }}"
        f" QListWidget::item {{ padding: 3px 6px; color: {P.TEXT}; }}"
        f" QListWidget::item:selected {{ background: {P.OVERLAY}; }}"
    )


def _time_ss() -> str:
    return f"QTimeEdit {{ {_INPUT_SS} }} QTimeEdit:focus {{ {_FOCUS_SS} }}"


def _date_ss() -> str:
    P = active_palette()
    return (
        f"QDateEdit {{ {_INPUT_SS} border: 1px solid {P.OVERLAY2}; border-radius: 3px; }}"
        f" QDateEdit:focus {{ {_FOCUS_SS} border: 1px solid {P.BLUE}; }}"
        f" QDateEdit::drop-down {{ border: none; }}"
    )


def _day_pill_ss() -> str:
    P = active_palette()
    return (
        f"QPushButton {{ background: {P.OVERLAY}; color: {P.MUTED}; "
        f"border: 1px solid {P.OVERLAY2}; border-radius: 4px; outline: none; font-weight: 600;"
        f" padding: 0; }}"
        f"QPushButton:checked {{ background: {P.BLUE}; color: {P.BG}; "
        f"border: 1px solid {P.BLUE}; }}"
        f"QPushButton:hover:!checked {{ background: {P.OVERLAY2}; color: {P.TEXT}; }}"
        f"QPushButton:focus {{ outline: none; }}"
    )


def _nav_icon(svg_body: str, size: int = 14) -> QIcon:
    """Render an inline SVG snippet to a QIcon for nav-tree use."""
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 16 16">'
        f"{svg_body}"
        f"</svg>"
    )
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    renderer.render(p)
    p.end()
    return QIcon(px)


_NAV_SVG: dict[str, str] = {
    "General": (
        '<line x1="2" y1="4"  x2="14" y2="4"  stroke="{c}" stroke-width="1.5" stroke-linecap="round"/>'
        '<line x1="2" y1="8"  x2="14" y2="8"  stroke="{c}" stroke-width="1.5" stroke-linecap="round"/>'
        '<line x1="2" y1="12" x2="14" y2="12" stroke="{c}" stroke-width="1.5" stroke-linecap="round"/>'
    ),
    "Strategy Info": (
        '<circle cx="8" cy="8" r="6.5" stroke="{c}" stroke-width="1.5" fill="none"/>'
        '<line x1="8" y1="7.5" x2="8" y2="11.5" stroke="{c}" stroke-width="1.5" stroke-linecap="round"/>'
        '<circle cx="8" cy="5.2" r="0.9" fill="{c}"/>'
    ),
    "Trigger": (
        '<polygon points="9.5,1 4.5,8.5 8,8.5 6.5,15 11.5,7.5 8,7.5" fill="{c}"/>'
    ),
    "Settings": (
        '<line x1="2"  y1="5"  x2="14" y2="5"  stroke="{c}" stroke-width="1.5" stroke-linecap="round"/>'
        '<circle cx="6"  cy="5"  r="2" fill="{c}"/>'
        '<line x1="2"  y1="11" x2="14" y2="11" stroke="{c}" stroke-width="1.5" stroke-linecap="round"/>'
        '<circle cx="10" cy="11" r="2" fill="{c}"/>'
    ),
    "Scheduler": (
        '<rect x="1.5" y="3.5" width="13" height="10.5" rx="1.5"'
        ' stroke="{c}" stroke-width="1.5" fill="none"/>'
        '<line x1="5"   y1="1.5" x2="5"    y2="5"   stroke="{c}" stroke-width="1.5" stroke-linecap="round"/>'
        '<line x1="11"  y1="1.5" x2="11"   y2="5"   stroke="{c}" stroke-width="1.5" stroke-linecap="round"/>'
        '<line x1="1.5" y1="7"   x2="14.5" y2="7"   stroke="{c}" stroke-width="1.5"/>'
    ),
    "Execution": (
        '<polygon points="3.5,2 13.5,8 3.5,14" fill="{c}"/>'
    ),
    "Risk": (
        '<path d="M8,1.5 L14,4 L14,8.5 C14,12 11.5,14.5 8,15 C4.5,14.5 2,12 2,8.5 L2,4 Z"'
        ' stroke="{c}" stroke-width="1.5" fill="none" stroke-linejoin="round"/>'
        '<line x1="8" y1="6" x2="8" y2="9.5" stroke="{c}" stroke-width="1.5" stroke-linecap="round"/>'
        '<circle cx="8" cy="11.5" r="0.9" fill="{c}"/>'
    ),
}


def _section_label(text: str) -> QLabel:
    P = active_palette()
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {P.SUBTEXT}; font-weight: 600; font-size: 11px; letter-spacing: 0.5px;")
    return lbl


# ── Custom title bar ──────────────────────────────────────────────────────────

class _TitleBar(QWidget):
    """Frameless drag-to-move title bar."""

    def __init__(self, title: str, window: QDialog) -> None:
        super().__init__(window)
        self._win = window
        self._drag = QPoint()
        self.setObjectName("title_bar")
        self.setFixedHeight(40)

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 0, 4, 0)
        row.setSpacing(0)

        lbl = QLabel(title)
        lbl.setObjectName("top_brand")
        row.addWidget(lbl)
        row.addStretch()

        P = active_palette()
        cls_btn = QPushButton("✕")
        cls_btn.setStyleSheet(_BTN_STYLE.format(fg=P.SUBTEXT, hover="#c0392b"))
        cls_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        cls_btn.clicked.connect(window.close)
        row.addWidget(cls_btn)

    def mousePressEvent(self, ev: QMouseEvent) -> None:  # type: ignore[override]
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag = ev.globalPosition().toPoint() - self._win.frameGeometry().topLeft()
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev: QMouseEvent) -> None:  # type: ignore[override]
        if ev.buttons() & Qt.MouseButton.LeftButton and not self._drag.isNull():
            self._win.move(ev.globalPosition().toPoint() - self._drag)
        super().mouseMoveEvent(ev)


# ── Condition selector popup ──────────────────────────────────────────────────

class _ConditionSelectorDialog(QDialog):
    """Popup to pick an indicator and configure its parameters."""

    condition_built = pyqtSignal(str)

    def __init__(self, slot_label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        P = active_palette()
        self._slot = slot_label
        self._inputs: dict[str, QWidget] = {}

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setMinimumWidth(380)

        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        root.addWidget(_TitleBar("Select trigger condition", self))

        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(16, 12, 16, 16)
        bl.setSpacing(10)

        bl.addWidget(QLabel(f"Select Technical Indicator for {slot_label}:"))

        self._ind_combo = QComboBox()
        self._ind_combo.addItems(_INDICATOR_NAMES)
        self._ind_combo.setFixedHeight(C.INPUT_H)
        self._ind_combo.setStyleSheet(_combo_ss())
        self._ind_combo.currentTextChanged.connect(self._refresh_params)
        bl.addWidget(self._ind_combo)

        self._param_widget = QWidget()
        self._param_form = QFormLayout(self._param_widget)
        self._param_form.setSpacing(8)
        self._param_form.setContentsMargins(0, 0, 0, 0)
        bl.addWidget(self._param_widget)

        self._err_lbl = QLabel("")
        self._err_lbl.setStyleSheet(f"color: {P.RED}; font-size: 9pt;")
        bl.addWidget(self._err_lbl)

        add_btn = QPushButton(f"Add {slot_label}")
        add_btn.setFixedHeight(C.BTN_H)
        add_btn.clicked.connect(self._on_add)
        bl.addWidget(add_btn)

        root.addWidget(body)
        self._refresh_params(self._ind_combo.currentText())

    def _clear_params(self) -> None:
        while self._param_form.count():
            item = self._param_form.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self._inputs.clear()

    def _refresh_params(self, name: str) -> None:
        self._clear_params()
        symbol_combo: QComboBox | None = None

        for ind in _INDICATOR_DATA:
            if ind["name"] != name:
                continue
            for param in ind["parameters"]:
                w: QWidget
                if param["Type"] == "EditBox":
                    le = QLineEdit()
                    le.setFixedHeight(C.INPUT_H)
                    le.setStyleSheet(_line_ss())
                    if param["Datatype"] == "int":
                        le.setValidator(QIntValidator())
                    elif param["Datatype"] == "float":
                        le.setValidator(QDoubleValidator())
                    w = le
                else:
                    cb = QComboBox()
                    cb.setFixedHeight(C.INPUT_H)
                    cb.setStyleSheet(_combo_ss())
                    if param["name"] in ("Symbol Type", "Underlying Type"):
                        cb.addItems(param["Datatype"])
                        symbol_combo = cb
                    elif param["name"] == "Timeframe" and symbol_combo is not None:
                        sc = symbol_combo
                        opts: list[str] = param["Datatype"]

                        def _fill_tf(
                            _cb: QComboBox = cb,
                            _opts: list[str] = opts,
                            _sc: QComboBox = sc,
                        ) -> None:
                            _cb.clear()
                            _cb.addItems(["60", "30"] if _sc.currentText() == "RSP" else _opts)

                        sc.currentTextChanged.connect(lambda _, f=_fill_tf: f())
                        _fill_tf()
                    else:
                        cb.addItems(param["Datatype"])
                    w = cb

                self._inputs[param["name"]] = w
                self._param_form.addRow(f"{param['name']}:", w)
            break

    def _on_add(self) -> None:
        parts: list[str] = []
        for pname, w in self._inputs.items():
            if isinstance(w, QLineEdit):
                val = w.text().strip()
                if not val:
                    self._err_lbl.setText(f"'{pname}' is required.")
                    return
                parts.append(val)
            elif isinstance(w, QComboBox):
                parts.append(f"'{w.currentText()}'")

        fn = f"{self._ind_combo.currentText()}({', '.join(parts)})"
        self._err_lbl.setText("")
        self.condition_built.emit(fn)
        self.accept()


# ── Condition bubble ───────────────────────────────────────────────────────────

class _CondBubble(QWidget):
    """Compact removable badge showing a configured indicator expression."""

    cleared = pyqtSignal()

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        P = active_palette()
        short = text if len(text) <= 26 else text[:23] + "…"

        lbl = QLabel(short)
        lbl.setToolTip(text)
        lbl.setStyleSheet(
            f"color: {P.BLUE}; font-size: 8pt; background: transparent; border: none;"
        )

        x_btn = QPushButton("×")
        x_btn.setFixedWidth(16)
        x_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        x_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {P.MUTED}; border: none;"
            f" font-size: 10pt; padding: 0; outline: none; }}"
            f"QPushButton:hover {{ color: {P.RED}; }}"
            f"QPushButton:focus {{ outline: none; }}"
        )
        x_btn.clicked.connect(self.cleared.emit)

        row = QHBoxLayout(self)
        row.setContentsMargins(8, 3, 5, 3)
        row.setSpacing(4)
        row.addWidget(lbl)
        row.addWidget(x_btn)

        self.setStyleSheet(
            f"background: {P.BLUE}1a; border: 1px solid {P.BLUE}66; border-radius: 4px;"
        )


# ── Page: Strategy Info ───────────────────────────────────────────────────────

class _StrategyInfoPage(QScrollArea):
    """Strategy name, scope, mode and capital allocation."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setStyleSheet("QScrollArea { border: none; }")

        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(20, 16, 20, 16)
        bl.setSpacing(18)

        bl.addWidget(_section_label("STRATEGY INFO"))

        form = QFormLayout()
        form.setSpacing(10)
        form.setContentsMargins(0, 0, 0, 0)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. BOSS_LNG_v1")
        self._name_edit.setFixedHeight(C.INPUT_H)
        self._name_edit.setStyleSheet(_line_ss())
        form.addRow("Name:", self._name_edit)

        self._symbol_mode = QComboBox()
        self._symbol_mode.addItems(["All S&P 500", "Include Only", "Exclude These"])
        self._symbol_mode.setFixedHeight(C.INPUT_H)
        self._symbol_mode.setStyleSheet(_combo_ss())
        form.addRow("Scope:", self._symbol_mode)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["Disabled", "Manual", "Auto"])
        self._mode_combo.setFixedHeight(C.INPUT_H)
        self._mode_combo.setStyleSheet(_combo_ss())
        form.addRow("Mode:", self._mode_combo)

        self._capital_spin = QSpinBox()
        self._capital_spin.setRange(5, 100)
        self._capital_spin.setSingleStep(5)
        self._capital_spin.setValue(25)
        self._capital_spin.setSuffix(" %")
        self._capital_spin.setFixedHeight(C.INPUT_H)
        self._capital_spin.setStyleSheet(_spin_ss())
        form.addRow("Capital Max:", self._capital_spin)

        bl.addLayout(form)

        # Stock picker — visible only when scope is Include Only or Exclude These
        self._picker_panel = QWidget()
        picker_vl = QVBoxLayout(self._picker_panel)
        picker_vl.setContentsMargins(0, 0, 0, 0)
        picker_vl.setSpacing(6)

        search_row = QHBoxLayout()
        search_row.setSpacing(6)
        self._stock_search = QComboBox()
        self._stock_search.setEditable(True)
        self._stock_search.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._stock_search.setFixedHeight(C.INPUT_H)
        self._stock_search.setStyleSheet(_combo_ss())
        self._stock_search.lineEdit().setPlaceholderText("Search symbol…")
        try:
            from us_swing.universe.store import load_sp500
            for rec in sorted(load_sp500(), key=lambda r: r.symbol):
                self._stock_search.addItem(rec.symbol)
        except Exception:
            pass
        completer = self._stock_search.completer()
        if completer is not None:
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._stock_add_btn = QPushButton("Add")
        self._stock_add_btn.setFixedHeight(C.BTN_H)
        self._stock_add_btn.setFixedWidth(54)
        search_row.addWidget(self._stock_search, 1)
        search_row.addWidget(self._stock_add_btn)
        picker_vl.addLayout(search_row)

        self._stock_list = QListWidget()
        self._stock_list.setFixedHeight(110)
        self._stock_list.setStyleSheet(_list_ss())
        picker_vl.addWidget(self._stock_list)

        self._stock_remove_btn = QPushButton("Remove Selected")
        self._stock_remove_btn.setFixedHeight(C.BTN_H)
        picker_vl.addWidget(self._stock_remove_btn)

        bl.addWidget(self._picker_panel)
        bl.addStretch()
        self.setWidget(body)

        self._symbol_mode.currentIndexChanged.connect(self._update_picker_visibility)
        self._stock_add_btn.clicked.connect(self._add_stock)
        self._stock_remove_btn.clicked.connect(self._remove_stock)
        self._update_picker_visibility(0)

    def _update_picker_visibility(self, idx: int) -> None:
        self._picker_panel.setVisible(idx != 0)

    def _add_stock(self) -> None:
        symbol = self._stock_search.currentText().strip().upper()
        if not symbol:
            return
        existing = {self._stock_list.item(r).text() for r in range(self._stock_list.count())}
        if symbol not in existing:
            self._stock_list.addItem(symbol)
        self._stock_search.clearEditText()

    def _remove_stock(self) -> None:
        for item in self._stock_list.selectedItems():
            self._stock_list.takeItem(self._stock_list.row(item))


# ── Page: Scheduler ───────────────────────────────────────────────────────────

class _SchedulerPage(QScrollArea):
    """Trading schedule — times, dates, active days."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        P = active_palette()
        self.setWidgetResizable(True)
        self.setStyleSheet("QScrollArea { border: none; }")

        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(20, 16, 20, 16)
        bl.setSpacing(18)

        # ── Time Range ────────────────────────────────────────────────────────
        bl.addWidget(_section_label("TIME RANGE"))

        time_row = QHBoxLayout()
        time_row.setSpacing(12)

        start_time_col = QVBoxLayout()
        start_time_col.setSpacing(4)
        _st_lbl = QLabel("Start")
        _st_lbl.setStyleSheet(f"color: {P.MUTED}; font-size: 11px;")
        self._start_time = QTimeEdit(QTime(9, 30))
        self._start_time.setDisplayFormat("HH:mm")
        self._start_time.setFixedHeight(C.INPUT_H)
        self._start_time.setMinimumWidth(120)
        self._start_time.setStyleSheet(_time_ss())
        start_time_col.addWidget(_st_lbl)
        start_time_col.addWidget(self._start_time)

        end_time_col = QVBoxLayout()
        end_time_col.setSpacing(4)
        _et_lbl = QLabel("End")
        _et_lbl.setStyleSheet(f"color: {P.MUTED}; font-size: 11px;")
        self._end_time = QTimeEdit(QTime(15, 30))
        self._end_time.setDisplayFormat("HH:mm")
        self._end_time.setFixedHeight(C.INPUT_H)
        self._end_time.setMinimumWidth(120)
        self._end_time.setStyleSheet(_time_ss())
        end_time_col.addWidget(_et_lbl)
        end_time_col.addWidget(self._end_time)

        time_row.addLayout(start_time_col)
        time_row.addLayout(end_time_col)
        time_row.addStretch()
        bl.addLayout(time_row)

        # ── Date Range ────────────────────────────────────────────────────────
        bl.addWidget(_section_label("DATE RANGE"))

        date_row = QHBoxLayout()
        date_row.setSpacing(12)
        today = QDate.currentDate()

        start_date_col = QVBoxLayout()
        start_date_col.setSpacing(4)
        _sd_lbl = QLabel("Start")
        _sd_lbl.setStyleSheet(f"color: {P.MUTED}; font-size: 11px;")
        self._start_date = QDateEdit(today)
        self._start_date.setDisplayFormat("yyyy-MM-dd")
        self._start_date.setCalendarPopup(True)
        self._start_date.setFixedHeight(C.INPUT_H)
        self._start_date.setMinimumWidth(160)
        self._start_date.setStyleSheet(_date_ss())
        start_date_col.addWidget(_sd_lbl)
        start_date_col.addWidget(self._start_date)

        end_date_col = QVBoxLayout()
        end_date_col.setSpacing(4)
        _ed_lbl = QLabel("End")
        _ed_lbl.setStyleSheet(f"color: {P.MUTED}; font-size: 11px;")
        self._end_date = QDateEdit(today.addMonths(6))
        self._end_date.setDisplayFormat("yyyy-MM-dd")
        self._end_date.setCalendarPopup(True)
        self._end_date.setFixedHeight(C.INPUT_H)
        self._end_date.setMinimumWidth(160)
        self._end_date.setStyleSheet(_date_ss())
        end_date_col.addWidget(_ed_lbl)
        end_date_col.addWidget(self._end_date)

        date_row.addLayout(start_date_col)
        date_row.addLayout(end_date_col)
        date_row.addStretch()
        bl.addLayout(date_row)

        # ── Days of Week ──────────────────────────────────────────────────────
        bl.addWidget(_section_label("DAYS OF WEEK"))

        days_row = QHBoxLayout()
        days_row.setSpacing(6)
        self._day_checks: dict[str, QPushButton] = {}
        for day in _DAYS:
            btn = QPushButton(_DAY_LABELS[day])
            btn.setCheckable(True)
            btn.setChecked(True)
            btn.setFixedWidth(62)
            btn.setStyleSheet(_day_pill_ss())
            self._day_checks[day] = btn
            days_row.addWidget(btn)
        days_row.addStretch()
        bl.addLayout(days_row)

        bl.addStretch()
        self.setWidget(body)


# ── Page: Triggers ────────────────────────────────────────────────────────────

class _TriggersPage(QWidget):
    """Progressive condition builder — chain elements revealed one by one."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cond1_fn = ""
        self._cond2_fn = ""
        self.entry_condition = ""
        self.exit_condition = ""

        # Persistent operator widgets — reparented into chain row as needed
        P = active_palette()
        _pill_ss = (
            f"QComboBox {{ background: {P.OVERLAY}; color: {P.TEXT};"
            f" border: 1px solid {P.OVERLAY2}; border-radius: {C.INPUT_H // 2}px;"
            f" padding: 0 8px; font-weight: bold; outline: none; }}"
            f"QComboBox:hover {{ border-color: {P.BLUE}; color: {P.BLUE}; }}"
            f"QComboBox:focus {{ outline: none; }}"
            f"QComboBox::drop-down {{ border: none; width: 0px; }}"
            f"QComboBox::down-arrow {{ width: 0px; height: 0px; }}"
        )

        self._relop = QComboBox()
        self._relop.addItems([">", "<", ">=", "<=", "==", "!="])
        self._relop.setFixedWidth(44)
        self._relop.setStyleSheet(_pill_ss)

        self._logical = QComboBox()
        self._logical.addItems(["&", "||"])
        self._logical.setFixedWidth(44)
        self._logical.setStyleSheet(_pill_ss)

        # Persistent add buttons
        self._add_c1 = self._make_plus_btn("Add Condition 1")
        self._add_c1.clicked.connect(lambda: self._open_selector("Condition 1", self._add_c1))
        self._add_c2 = self._make_plus_btn("Add Condition 2")
        self._add_c2.clicked.connect(lambda: self._open_selector("Condition 2", self._add_c2))

        # Dynamic bubble references (created fresh on each rebuild)
        self._c1_bubble: _CondBubble | None = None
        self._c2_bubble: _CondBubble | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(12)

        root.addWidget(_section_label("TRIGGER CONDITION"))

        # Chain row
        self._chain_container = QWidget()
        self._chain_row = QHBoxLayout(self._chain_container)
        self._chain_row.setContentsMargins(0, 4, 0, 4)
        self._chain_row.setSpacing(8)
        self._chain_row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(self._chain_container)

        self._rebuild_chain()

        # Action row
        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self._compile_btn = QPushButton("Compile")
        self._compile_btn.setFixedHeight(C.BTN_H)
        self._compile_btn.setFixedWidth(80)
        self._compile_btn.clicked.connect(self._on_compile)
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setFixedHeight(C.BTN_H)
        self._clear_btn.setFixedWidth(80)
        self._clear_btn.clicked.connect(self._on_clear)
        action_row.addWidget(self._compile_btn)
        action_row.addWidget(self._clear_btn)
        action_row.addStretch()
        root.addLayout(action_row)

        # Compiled output
        out_hdr = QLabel("Compiled Conditions:")
        out_hdr.setStyleSheet(f"color: {P.MUTED}; font-size: 8pt;")
        root.addWidget(out_hdr)
        self._output = QTextEdit()
        self._output.setReadOnly(True)
        self._output.setFixedHeight(52)
        self._output.setPlaceholderText("Compiled conditions appear here…")
        root.addWidget(self._output)

        # Entry / exit assign buttons
        assign_row = QHBoxLayout()
        assign_row.setSpacing(8)
        self._entry_btn = QPushButton("Entry")
        self._entry_btn.setObjectName("buy_btn")
        self._entry_btn.setFixedHeight(C.BTN_H)
        self._entry_btn.setFixedWidth(82)
        self._entry_btn.clicked.connect(self._on_set_entry)
        self._exit_btn = QPushButton("Exit")
        self._exit_btn.setObjectName("danger_btn")
        self._exit_btn.setFixedHeight(C.BTN_H)
        self._exit_btn.setFixedWidth(82)
        self._exit_btn.clicked.connect(self._on_set_exit)
        assign_row.addWidget(self._entry_btn)
        assign_row.addWidget(self._exit_btn)
        assign_row.addStretch()
        root.addLayout(assign_row)

        # Entry / exit condition displays
        entry_hdr = QLabel("Entry Condition:")
        entry_hdr.setStyleSheet(f"color: {P.MUTED}; font-size: 8pt;")
        self._entry_display = QLabel("—")
        self._entry_display.setWordWrap(True)
        self._entry_display.setStyleSheet(f"color: {P.GREEN}; font-size: 8pt;")
        exit_hdr = QLabel("Exit Condition:")
        exit_hdr.setStyleSheet(f"color: {P.MUTED}; font-size: 8pt;")
        self._exit_display = QLabel("—")
        self._exit_display.setWordWrap(True)
        self._exit_display.setStyleSheet(f"color: {P.RED}; font-size: 8pt;")
        root.addWidget(entry_hdr)
        root.addWidget(self._entry_display)
        root.addSpacing(2)
        root.addWidget(exit_hdr)
        root.addWidget(self._exit_display)

        self._err_lbl = QLabel("")
        self._err_lbl.setStyleSheet(f"color: {P.RED}; font-size: 9pt;")
        root.addWidget(self._err_lbl)
        root.addStretch()

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _plus_icon(color: str) -> QIcon:
        px = QPixmap(14, 14)
        px.fill(Qt.GlobalColor.transparent)
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(color), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(7, 2, 7, 12)
        p.drawLine(2, 7, 12, 7)
        p.end()
        return QIcon(px)

    @staticmethod
    def _make_plus_btn(tooltip: str = "") -> QPushButton:
        P = active_palette()
        btn = QPushButton()
        btn.setFixedWidth(44)
        btn.setIconSize(QSize(14, 14))
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setToolTip(tooltip)
        btn.setIcon(_TriggersPage._plus_icon(P.SUBTEXT))
        btn.setStyleSheet(
            f"QPushButton {{ background: {P.OVERLAY}; color: {P.SUBTEXT};"
            f" border: 1px solid {P.OVERLAY2}; border-radius: 14px;"
            f" font-size: 9pt; outline: none; }}"
            f"QPushButton:hover {{ background: {P.OVERLAY2}; color: {P.BLUE};"
            f" border-color: {P.BLUE}; }}"
            f"QPushButton:pressed {{ background: {P.BLUE}44; color: {P.BLUE}; }}"
            f"QPushButton:focus {{ outline: none; }}"
        )
        btn.enterEvent = lambda _e, b=btn: b.setIcon(  # type: ignore[method-assign]
            _TriggersPage._plus_icon(active_palette().BLUE)
        )
        btn.leaveEvent = lambda _e, b=btn: b.setIcon(  # type: ignore[method-assign]
            _TriggersPage._plus_icon(active_palette().SUBTEXT)
        )
        return btn

    def _rebuild_chain(self) -> None:
        """Clear and rebuild chain row from current condition state."""
        while self._chain_row.count():
            item = self._chain_row.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()

        for attr in ("_c1_bubble", "_c2_bubble"):
            b: _CondBubble | None = getattr(self, attr)
            if b is not None:
                b.deleteLater()
            setattr(self, attr, None)

        if not self._cond1_fn:
            self._chain_row.addWidget(self._add_c1)
            self._add_c1.show()
        else:
            self._c1_bubble = _CondBubble(self._cond1_fn, self)
            self._c1_bubble.cleared.connect(self._clear_cond1)
            self._chain_row.addWidget(self._c1_bubble)
            self._c1_bubble.show()
            self._chain_row.addWidget(self._relop)
            self._relop.show()
            if not self._cond2_fn:
                self._chain_row.addWidget(self._add_c2)
                self._add_c2.show()
            else:
                self._c2_bubble = _CondBubble(self._cond2_fn, self)
                self._c2_bubble.cleared.connect(self._clear_cond2)
                self._chain_row.addWidget(self._c2_bubble)
                self._c2_bubble.show()
                self._chain_row.addWidget(self._logical)
                self._logical.show()

        self._chain_row.addStretch()

    # ── Selector ───────────────────────────────────────────────────────────────

    def _open_selector(self, slot: str, btn: QPushButton) -> None:
        dlg = _ConditionSelectorDialog(slot, self)
        if slot == "Condition 1":
            dlg.condition_built.connect(self._set_cond1)
        else:
            dlg.condition_built.connect(self._set_cond2)
        dlg.move(btn.mapToGlobal(QPoint(btn.width(), 0)))
        dlg.exec()

    def _set_cond1(self, fn: str) -> None:
        self._cond1_fn = fn
        self._rebuild_chain()

    def _set_cond2(self, fn: str) -> None:
        self._cond2_fn = fn
        self._rebuild_chain()

    def _clear_cond1(self) -> None:
        self._cond1_fn = ""
        self._cond2_fn = ""
        self._rebuild_chain()

    def _clear_cond2(self) -> None:
        self._cond2_fn = ""
        self._rebuild_chain()

    # ── Compile / assign ───────────────────────────────────────────────────────

    def _on_compile(self) -> None:
        if not self._cond1_fn or not self._cond2_fn:
            self._err_lbl.setText("Set both conditions before compiling.")
            return
        rel = self._relop.currentText()
        log = {"&": "AND", "||": "OR"}.get(self._logical.currentText(), "AND")
        clause = f"({self._cond1_fn}) {rel} ({self._cond2_fn})"
        existing = self._output.toPlainText().strip()
        self._output.setPlainText(f"{existing} {log} {clause}" if existing else clause)
        self._err_lbl.setText("")
        self._cond1_fn = ""
        self._cond2_fn = ""
        self._rebuild_chain()

    def _on_clear(self) -> None:
        self._cond1_fn = ""
        self._cond2_fn = ""
        self._rebuild_chain()
        self._output.clear()
        self._err_lbl.setText("")

    def _on_set_entry(self) -> None:
        cond = self._output.toPlainText().strip()
        if not cond:
            self._err_lbl.setText("Compile a condition first.")
            return
        self.entry_condition = cond
        self._entry_display.setText(cond)
        self._on_clear()

    def _on_set_exit(self) -> None:
        cond = self._output.toPlainText().strip()
        if not cond:
            self._err_lbl.setText("Compile a condition first.")
            return
        self.exit_condition = cond
        self._exit_display.setText(cond)
        self._on_clear()

    # ── Public API ────────────────────────────────────────────────────────────

    def get_entry(self) -> str:
        return self.entry_condition

    def get_exit(self) -> str:
        return self.exit_condition

    def set_entry(self, val: str) -> None:
        self.entry_condition = val
        self._entry_display.setText(val if val else "—")

    def set_exit(self, val: str) -> None:
        self.exit_condition = val
        self._exit_display.setText(val if val else "—")


# ── Page: Settings ────────────────────────────────────────────────────────────

class _SettingsPage(QScrollArea):
    """Execution settings — auto trade mode, trade type, evaluation cadence."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setStyleSheet("QScrollArea { border: none; }")

        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(20, 16, 20, 16)
        bl.setSpacing(18)

        bl.addWidget(_section_label("EXECUTION"))

        exec_form = QFormLayout()
        exec_form.setSpacing(12)
        exec_form.setContentsMargins(0, 0, 0, 0)

        self._auto_trade = QCheckBox("Enable automatic order submission")
        exec_form.addRow("Auto Trade:", self._auto_trade)

        self._trade_type_combo = QComboBox()
        self._trade_type_combo.addItems(["Intraday", "Positional"])
        self._trade_type_combo.setFixedWidth(160)
        self._trade_type_combo.setStyleSheet("QComboBox { outline: none; } QComboBox:focus { outline: none; }")
        exec_form.addRow("Trade Type:", self._trade_type_combo)

        bl.addLayout(exec_form)

        bl.addWidget(_section_label("EXECUTION SETTINGS"))

        cadence_form = QFormLayout()
        cadence_form.setSpacing(12)
        cadence_form.setContentsMargins(0, 0, 0, 0)

        self._minute_close = QSpinBox()
        self._minute_close.setRange(0, 1440)
        self._minute_close.setValue(1)
        self._minute_close.setFixedHeight(C.INPUT_H)
        self._minute_close.setFixedWidth(160)
        self._minute_close.setStyleSheet(_spin_ss())
        self._minute_close.setToolTip(
            "Evaluation cadence in minutes. 0 = use Rate/Delay only.\n"
            "Example: 1 = every minute boundary; 5 = every 5-min boundary."
        )
        cadence_form.addRow("Minute Close:", self._minute_close)

        self._exec_rate = QSpinBox()
        self._exec_rate.setRange(0, 3600)
        self._exec_rate.setValue(1)
        self._exec_rate.setSuffix(" s")
        self._exec_rate.setFixedHeight(C.INPUT_H)
        self._exec_rate.setFixedWidth(160)
        self._exec_rate.setStyleSheet(_spin_ss())
        self._exec_rate.setToolTip(
            "Delay-after-boundary in seconds when Minute Close > 0.\n"
            "When Minute Close = 0, this is the pure polling interval."
        )
        cadence_form.addRow("Rate/Delay in Sec:", self._exec_rate)

        self._rex_count = QSpinBox()
        self._rex_count.setRange(0, 100)
        self._rex_count.setValue(0)
        self._rex_count.setFixedHeight(C.INPUT_H)
        self._rex_count.setFixedWidth(160)
        self._rex_count.setStyleSheet(_spin_ss())
        self._rex_count.setToolTip(
            "Re-execution count: extra entries per stock beyond the first.\n"
            "Default 0 = first entry only. 5 = first entry plus 5 re-entries.\n"
            "Use Reset Strategy to clear counters and re-enable entries."
        )
        cadence_form.addRow("Rex Count:", self._rex_count)

        bl.addLayout(cadence_form)
        bl.addStretch()
        self.setWidget(body)


# ── Page: Risk ────────────────────────────────────────────────────────────────

class _RiskPage(QScrollArea):
    """Risk settings — target and stop loss."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setStyleSheet("QScrollArea { border: none; }")

        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(20, 16, 20, 16)
        bl.setSpacing(20)

        # ── Target ────────────────────────────────────────────────────────────
        bl.addWidget(_section_label("TARGET"))

        self._target_enabled = QCheckBox("Enable target")
        bl.addWidget(self._target_enabled)

        target_form = QFormLayout()
        target_form.setSpacing(10)
        target_form.setContentsMargins(0, 0, 0, 0)

        self._target_type = QComboBox()
        self._target_type.addItems(["Fixed", "Trailing"])
        self._target_type.setFixedHeight(C.INPUT_H)
        self._target_type.setStyleSheet(_combo_ss())
        target_form.addRow("Type:", self._target_type)

        self._target_value = QDoubleSpinBox()
        self._target_value.setRange(0.1, 100.0)
        self._target_value.setSingleStep(0.5)
        self._target_value.setDecimals(1)
        self._target_value.setValue(2.0)
        self._target_value.setSuffix(" %")
        self._target_value.setFixedHeight(C.INPUT_H)
        self._target_value.setStyleSheet(_double_spin_ss())
        target_form.addRow("Value:", self._target_value)

        self._target_controls = QWidget()
        self._target_controls.setLayout(target_form)
        bl.addWidget(self._target_controls)

        # ── Stop Loss ─────────────────────────────────────────────────────────
        bl.addWidget(_section_label("STOP LOSS"))

        self._sl_enabled = QCheckBox("Enable stop loss")
        bl.addWidget(self._sl_enabled)

        sl_form = QFormLayout()
        sl_form.setSpacing(10)
        sl_form.setContentsMargins(0, 0, 0, 0)

        self._sl_type = QComboBox()
        self._sl_type.addItems(["Fixed", "Trailing"])
        self._sl_type.setFixedHeight(C.INPUT_H)
        self._sl_type.setStyleSheet(_combo_ss())
        sl_form.addRow("Type:", self._sl_type)

        self._sl_value = QDoubleSpinBox()
        self._sl_value.setRange(0.1, 100.0)
        self._sl_value.setSingleStep(0.5)
        self._sl_value.setDecimals(1)
        self._sl_value.setValue(1.0)
        self._sl_value.setSuffix(" %")
        self._sl_value.setFixedHeight(C.INPUT_H)
        self._sl_value.setStyleSheet(_double_spin_ss())
        sl_form.addRow("Value:", self._sl_value)

        self._sl_controls = QWidget()
        self._sl_controls.setLayout(sl_form)
        bl.addWidget(self._sl_controls)

        bl.addStretch()
        self.setWidget(body)

        self._target_enabled.toggled.connect(self._target_controls.setEnabled)
        self._sl_enabled.toggled.connect(self._sl_controls.setEnabled)
        self._target_controls.setEnabled(False)
        self._sl_controls.setEnabled(False)


# ── Main dialog ───────────────────────────────────────────────────────────────

_PAGE_STRATEGY_INFO = 0
_PAGE_TRIGGER = 1
_PAGE_SCHEDULER = 2
_PAGE_EXECUTION = 3
_PAGE_RISK = 4

def _nav_ss() -> str:
    P = active_palette()
    return (
        "QTreeWidget {{ border: none; font-size: 9pt; }}"
        " QTreeWidget::item {{ padding: 5px 8px 5px 4px; }}"
        " QTreeWidget::item:selected {{ background: {sel}; color: {txt}; border: none; }}"
    ).format(sel=P.OVERLAY, txt=P.TEXT)


def _nav_item(label: str) -> QTreeWidgetItem:
    item = QTreeWidgetItem([label])
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


class StrategyBuilderDialog(QDialog):
    """Frameless strategy builder — collapsible General / Settings sidebar."""

    strategy_saved = pyqtSignal(object)

    def __init__(
        self,
        parent: QWidget | None = None,
        existing: StrategyConfig | None = None,
        existing_names: set[str] | None = None,
    ) -> None:
        super().__init__(parent)
        self._existing = existing
        self._existing_names = existing_names or set()
        self._edit_mode = existing is not None

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setMinimumSize(780, 480)

        root_lay = QVBoxLayout(self)
        root_lay.setSpacing(0)
        root_lay.setContentsMargins(0, 0, 0, 0)

        title = "Edit Strategy" if self._edit_mode else "Add Strategy"
        root_lay.addWidget(_TitleBar(title, self))

        # ── Body ─────────────────────────────────────────────────────────────
        body = QWidget()
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(8, 8, 8, 8)
        body_lay.setSpacing(8)

        # ── Left: nav frame ──────────────────────────────────────────────────
        nav_frame = QFrame()
        nav_frame.setObjectName("nav_frame")
        P = active_palette()
        nav_frame.setStyleSheet(
            f"QFrame#nav_frame {{ border: 1px solid {P.OVERLAY}; border-radius: 4px; }}"
        )
        nav_frame_lay = QVBoxLayout(nav_frame)
        nav_frame_lay.setContentsMargins(0, 0, 0, 0)
        nav_frame_lay.setSpacing(0)

        self._nav = QTreeWidget()
        self._nav.setHeaderHidden(True)
        self._nav.setFixedWidth(175)
        self._nav.setRootIsDecorated(True)
        self._nav.setIndentation(16)
        self._nav.setStyleSheet(_nav_ss())

        # ── Tree: General ▼ (Strategy Info, Trigger)
        general_root = _nav_item("General")
        info_item = _nav_item("Strategy Info")
        trigger_item = _nav_item("Trigger")
        general_root.addChildren([info_item, trigger_item])

        # ── Tree: Settings ▼ (Scheduler, Execution, Risk)
        settings_root = _nav_item("Settings")
        sched_item = _nav_item("Scheduler")
        exec_item = _nav_item("Execution")
        risk_item = _nav_item("Risk")
        settings_root.addChildren([sched_item, exec_item, risk_item])

        # ── Nav icons
        for _item, _label in [
            (general_root, "General"), (info_item, "Strategy Info"),
            (trigger_item, "Trigger"), (settings_root, "Settings"),
            (sched_item, "Scheduler"), (exec_item, "Execution"),
            (risk_item, "Risk"),
        ]:
            svg_body = _NAV_SVG.get(_label, "")
            if svg_body:
                _item.setIcon(0, _nav_icon(svg_body.format(c=P.SUBTEXT)))

        self._nav.addTopLevelItem(general_root)
        self._nav.addTopLevelItem(settings_root)
        general_root.setExpanded(True)
        settings_root.setExpanded(True)

        # Maps each leaf item (by id) → stack page index; QTreeWidgetItem is not hashable in PyQt6
        self._page_map: dict[int, int] = {
            id(info_item): _PAGE_STRATEGY_INFO,
            id(trigger_item): _PAGE_TRIGGER,
            id(sched_item): _PAGE_SCHEDULER,
            id(exec_item): _PAGE_EXECUTION,
            id(risk_item): _PAGE_RISK,
        }
        # Reverse map for _go_to
        self._idx_item: dict[int, QTreeWidgetItem] = {
            _PAGE_STRATEGY_INFO: info_item,
            _PAGE_TRIGGER: trigger_item,
            _PAGE_SCHEDULER: sched_item,
            _PAGE_EXECUTION: exec_item,
            _PAGE_RISK: risk_item,
        }

        self._nav.setCurrentItem(info_item)
        self._nav.currentItemChanged.connect(self._on_nav_changed)
        nav_frame_lay.addWidget(self._nav)

        # ── Right: content frame ─────────────────────────────────────────────
        right_frame = QFrame()
        right_frame.setObjectName("right_frame")
        right_frame.setStyleSheet(
            f"QFrame#right_frame {{ border: 1px solid {P.OVERLAY}; border-radius: 4px; }}"
        )
        right_lay = QVBoxLayout(right_frame)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(0)

        # Stacked pages (order matches _PAGE_* constants)
        self._stack = QStackedWidget()
        self._info_page = _StrategyInfoPage()
        self._triggers_page = _TriggersPage()
        self._sched_page = _SchedulerPage()
        self._exec_page = _SettingsPage()
        self._risk_page = _RiskPage()

        self._stack.addWidget(self._info_page)
        self._stack.addWidget(self._triggers_page)
        self._stack.addWidget(self._sched_page)
        self._stack.addWidget(self._exec_page)
        self._stack.addWidget(self._risk_page)

        # Footer strip
        ftr = QFrame()
        ftr.setObjectName("ftr_frame")
        ftr.setFixedHeight(50)
        ftr.setStyleSheet(
            f"QFrame#ftr_frame {{ border: none; border-top: 1px solid {P.OVERLAY};"
            f" border-bottom-left-radius: 4px; border-bottom-right-radius: 4px; }}"
        )
        ftr_lay = QHBoxLayout(ftr)
        ftr_lay.setContentsMargins(14, 0, 14, 0)
        ftr_lay.setSpacing(10)

        self._err_lbl = QLabel("")
        self._err_lbl.setStyleSheet(
            f"color: {P.RED}; font-size: 9pt; border: none; background: transparent;"
        )
        self._err_lbl.setWordWrap(True)
        ftr_lay.addWidget(self._err_lbl, 1)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(C.BTN_H)
        cancel_btn.setFixedWidth(80)
        cancel_btn.clicked.connect(self.close)

        self._save_btn = QPushButton("Save" if self._edit_mode else "Add")
        self._save_btn.setObjectName("buy_btn")
        self._save_btn.setFixedHeight(C.BTN_H)
        self._save_btn.setFixedWidth(80)
        self._save_btn.clicked.connect(self._on_save)

        ftr_lay.addWidget(cancel_btn)
        ftr_lay.addWidget(self._save_btn)

        right_lay.addWidget(self._stack, 1)
        right_lay.addWidget(ftr)

        body_lay.addWidget(nav_frame)
        body_lay.addWidget(right_frame, 1)

        root_lay.addWidget(body, 1)

        if self._existing is not None:
            self._populate(self._existing)

    # ── Navigation ─────────────────────────────────────────────────────────────

    def _on_nav_changed(self, current: QTreeWidgetItem, _prev: QTreeWidgetItem) -> None:
        idx = self._page_map.get(id(current))
        if idx is not None:
            self._stack.setCurrentIndex(idx)

    def _go_to(self, page_idx: int) -> None:
        self._stack.setCurrentIndex(page_idx)
        item = self._idx_item.get(page_idx)
        if item:
            self._nav.setCurrentItem(item)

    # ── Populate ───────────────────────────────────────────────────────────────

    def _populate(self, cfg: StrategyConfig) -> None:
        i = self._info_page
        i._name_edit.setText(cfg.name)
        _scope_map = {"all": 0, "include": 1, "exclude": 2}
        i._symbol_mode.setCurrentIndex(_scope_map.get(cfg.symbol_mode, 0))
        i._stock_list.clear()
        stocks = cfg.symbols_include if cfg.symbol_mode == "include" else cfg.symbols_exclude
        for s in stocks:
            i._stock_list.addItem(s)
        i._mode_combo.setCurrentText(cfg.mode.capitalize())
        i._capital_spin.setValue(cfg.capital_max)

        sc = self._sched_page
        sc._start_time.setTime(QTime.fromString(cfg.start_time, "HH:mm"))
        sc._end_time.setTime(QTime.fromString(cfg.end_time, "HH:mm"))
        sc._start_date.setDate(QDate.fromString(cfg.start_date, "yyyy-MM-dd"))
        sc._end_date.setDate(QDate.fromString(cfg.end_date, "yyyy-MM-dd"))
        for day, cb in sc._day_checks.items():
            cb.setChecked(day in cfg.days)

        self._triggers_page.set_entry(cfg.entry_condition)
        self._triggers_page.set_exit(cfg.exit_condition)

        e = self._exec_page
        e._auto_trade.setChecked(cfg.auto_trade)
        e._trade_type_combo.setCurrentText(cfg.trade_type)
        e._minute_close.setValue(cfg.minute_close)
        e._exec_rate.setValue(cfg.execution_rate_sec)
        e._rex_count.setValue(cfg.rex_count)

        r = self._risk_page
        r._target_enabled.setChecked(cfg.target_enabled)
        r._target_type.setCurrentText(cfg.target_type.capitalize())
        r._target_value.setValue(cfg.target_value)
        r._sl_enabled.setChecked(cfg.stoploss_enabled)
        r._sl_type.setCurrentText(cfg.stoploss_type.capitalize())
        r._sl_value.setValue(cfg.stoploss_value)

    # ── Save ───────────────────────────────────────────────────────────────────

    def _on_save(self) -> None:
        i = self._info_page
        name = i._name_edit.text().strip()
        if not name:
            self._err_lbl.setText("Strategy name is required.")
            self._go_to(_PAGE_STRATEGY_INFO)
            return

        orig = self._existing.name if self._existing else None
        if name != orig and name in self._existing_names:
            self._err_lbl.setText(f"Name '{name}' already exists.")
            self._go_to(_PAGE_STRATEGY_INFO)
            return

        entry = self._triggers_page.get_entry()
        exit_ = self._triggers_page.get_exit()
        if not entry or not exit_:
            self._err_lbl.setText("Entry and exit conditions must both be set.")
            self._go_to(_PAGE_TRIGGER)
            return

        sc = self._sched_page
        e = self._exec_page
        r = self._risk_page

        # Edits preserve the live run_state so Running cycles keep their state.
        # New strategies: Auto mode arms immediately, Manual waits for Play.
        new_mode = i._mode_combo.currentText().lower()
        run_state = (
            self._existing.run_state
            if self._existing is not None
            else ("RUNNING" if new_mode == "auto" else "STOPPED")
        )

        cfg = StrategyConfig(
            name=name,
            strategy_type=self._existing.strategy_type if self._existing else "",
            symbol_mode={"All S&P 500": "all", "Include Only": "include", "Exclude These": "exclude"}[i._symbol_mode.currentText()],
            symbols_include=[i._stock_list.item(r).text() for r in range(i._stock_list.count())] if i._symbol_mode.currentIndex() == 1 else [],
            symbols_exclude=[i._stock_list.item(r).text() for r in range(i._stock_list.count())] if i._symbol_mode.currentIndex() == 2 else [],
            mode=i._mode_combo.currentText().lower(),
            capital_max=i._capital_spin.value(),
            start_time=sc._start_time.time().toString("HH:mm"),
            end_time=sc._end_time.time().toString("HH:mm"),
            start_date=sc._start_date.date().toString("yyyy-MM-dd"),
            end_date=sc._end_date.date().toString("yyyy-MM-dd"),
            days=[d for d, cb in sc._day_checks.items() if cb.isChecked()],
            entry_condition=entry,
            exit_condition=exit_,
            auto_trade=e._auto_trade.isChecked(),
            trade_type=e._trade_type_combo.currentText(),
            minute_close=e._minute_close.value(),
            execution_rate_sec=e._exec_rate.value(),
            rex_count=e._rex_count.value(),
            target_enabled=r._target_enabled.isChecked(),
            target_type=r._target_type.currentText().lower(),
            target_value=r._target_value.value(),
            stoploss_enabled=r._sl_enabled.isChecked(),
            stoploss_type=r._sl_type.currentText().lower(),
            stoploss_value=r._sl_value.value(),
            run_state=run_state,
        )

        self._err_lbl.setText("")
        self.strategy_saved.emit(cfg)
        self.close()
