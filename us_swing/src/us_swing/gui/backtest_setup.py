"""
Module: MD-GUI-031.071.M10 — Backtest setup window
Parent SRD: SRD-GUI-031.071, SRD-GUI-031.074

Frameless modal window around the builder pages: side menu (each section with its
value and a ✓ / ! mark), one section at a time on the right, and a footer with the
data check line, Cancel, Save and Run. Cancel, Esc and ✕ put the old plan back.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from us_swing.backtest.service import Estimate
from us_swing.backtest.spec import RunPlan
from us_swing.gui.backtest_builder import SECTIONS, BacktestBuilder
from us_swing.gui.icons import set_icon
from us_swing.gui.scheduler_dialog import _DialogTitleBar
from us_swing.gui.screener_views import PresetItem

OK, WARN = "✓", "!"
_ERROR_WORDS = {
    "run": ("date",),
    "stocks": ("sector", "stock name", "stock list"),
    "screener": ("screener", "preset", "rs rule", "weekly", "ai ranking", "saved"),
    "strategies": ("strateg",),
    "account": ("capital", "loss", "grow"),
}


def section_marks(est: Estimate | None) -> dict[str, str]:
    """✓ or ! per section: ! for missing candles (Stocks) or an error naming the section."""
    marks = dict.fromkeys(_ERROR_WORDS, OK)
    if est is None:
        return marks
    if est.missing_1d or est.missing_3m:
        marks["stocks"] = WARN
    for error in est.errors:
        low = error.lower()
        for key, words in _ERROR_WORDS.items():
            if any(w in low for w in words):
                marks[key] = WARN
    return marks


class BacktestSetupDialog(QDialog):
    """SRD-GUI-031.071 / .074 — the Backtest setup window."""

    run_requested = pyqtSignal()

    def __init__(self, builder: BacktestBuilder, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Backtest setup")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumSize(860, 600)
        self._builder = builder
        self._snapshot: RunPlan | None = None
        self._marks = section_marks(None)

        self.nav = QListWidget()
        self.nav.setObjectName("preset_list")
        self.nav.setFixedWidth(250)
        self._items: dict[str, PresetItem] = {}
        self.stack = QStackedWidget()
        for key, name in SECTIONS:
            row = PresetItem(name, "")
            item = QListWidgetItem()
            item.setSizeHint(row.sizeHint())
            self.nav.addItem(item)
            self.nav.setItemWidget(item, row)
            self._items[key] = row
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidget(builder.pages[key])
            self.stack.addWidget(scroll)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)

        self.check_label = QLabel("")
        self.check_label.setObjectName("details_key")
        self.check_label.setWordWrap(True)
        self.cancel_btn = QPushButton("Cancel")
        self.save_btn = QPushButton("Save")
        self.run_btn = QPushButton("Run")
        self.run_btn.setObjectName("run_btn")
        set_icon(self.run_btn, "play", "inverse")
        for btn in (self.cancel_btn, self.save_btn, self.run_btn):
            btn.setFixedWidth(90)
        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self.accept)
        self.run_btn.clicked.connect(self._on_run)

        footer = QFrame()
        footer.setObjectName("dialog_footer")
        foot = QHBoxLayout(footer)
        foot.setContentsMargins(12, 8, 12, 8)
        foot.setSpacing(8)
        foot.addWidget(self.check_label, 1)
        foot.addWidget(self.cancel_btn)
        foot.addWidget(self.save_btn)
        foot.addWidget(self.run_btn)

        middle = QHBoxLayout()
        middle.setContentsMargins(10, 10, 10, 10)
        middle.setSpacing(12)
        middle.addWidget(self.nav)
        middle.addWidget(self.stack, 1)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        title_bar = _DialogTitleBar("Backtest setup", self)
        # A minimised application-modal window would leave the main window locked.
        title_bar._btn_min.hide()
        root.addWidget(title_bar)
        root.addLayout(middle, 1)
        root.addWidget(footer)

        # builder → changed → side menu values
        builder.changed.connect(self.refresh_nav)
        self.refresh_nav()

    def open_at(self, section: str | None = None) -> None:
        """Show the window centred on its parent; Cancel goes back to this plan."""
        if section is not None:
            self.nav.setCurrentRow([k for k, _ in SECTIONS].index(section))
        self._snapshot = self._builder.plan()
        parent = self.parentWidget()
        if parent is not None:
            centre = parent.frameGeometry().center()
            self.move(centre.x() - self.width() // 2, centre.y() - self.height() // 2)
        self.show()
        self.raise_()
        self.activateWindow()

    def set_check(self, text: str, est: Estimate | None, can_run: bool) -> None:
        """Data check line, ✓ / ! marks and the Run button state."""
        self.check_label.setText(text)
        self._marks = section_marks(est)
        self.run_btn.setEnabled(can_run)
        self.refresh_nav()

    def refresh_nav(self) -> None:
        """Each menu item shows its mark and current value."""
        values = self._builder.summaries()
        for key, name in SECTIONS:
            self._items[key].name_lbl.setText(f"{name}   {self._marks[key]}")
            self._items[key].set_meta(values[key])

    def mark(self, key: str) -> str:
        """The ✓ or ! shown for a section."""
        return self._marks[key]

    def _on_run(self) -> None:
        self.accept()
        self.run_requested.emit()

    def reject(self) -> None:
        """Cancel, Esc and ✕ put the plan from before the window opened back."""
        if self._snapshot is not None:
            self._builder.load_plan(self._snapshot)
        super().reject()
