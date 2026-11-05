"""
Module: MD-GUI-034.004.M04 — Floor AI feed column
Parent SRD: SRD-GUI-034.004
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from us_swing.gui.floor_sample import SAMPLE_TAG, sample_feed_items
from us_swing.gui.icons import icon_button, set_icon
from us_swing.gui.theme import C

_OPEN_WIDTH = 300
_FOLDED_WIDTH = 40


class AiFeedColumn(QWidget):
    """Foldable list of AI desk notes; approval items show Approve and Reject buttons."""

    folded_changed = pyqtSignal(bool)

    def __init__(self, folded: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._folded = folded
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)
        head = QHBoxLayout()
        head.setSpacing(6)
        self._title = QLabel("AI feed")
        self._title.setObjectName("view_head")
        self._tag = QLabel(SAMPLE_TAG)
        self._tag.setStyleSheet(f"color: {C.MUTED};")
        self._fold_btn = icon_button("panel-left-open", "neutral", "Fold the AI feed")
        self._fold_btn.clicked.connect(self._toggle)  # button → clicked → column → _toggle
        head.addWidget(self._title)
        head.addWidget(self._tag)
        head.addStretch(1)
        head.addWidget(self._fold_btn)
        outer.addLayout(head)
        self._body = QScrollArea()
        self._body.setWidgetResizable(True)
        self._body.setFrameShape(QFrame.Shape.NoFrame)
        holder = QWidget()
        items = QVBoxLayout(holder)
        items.setContentsMargins(0, 0, 0, 0)
        items.setSpacing(6)
        for item in sample_feed_items():
            items.addWidget(self._item_card(item))
        items.addStretch(1)
        self._body.setWidget(holder)
        outer.addWidget(self._body, 1)
        self.set_folded(folded)

    def is_folded(self) -> bool:
        """Return True when only the unfold button shows."""
        return self._folded

    def set_folded(self, folded: bool) -> None:
        """Fold or unfold the column; emits ``folded_changed`` when the state changes."""
        changed = folded != self._folded
        self._folded = folded
        for widget in (self._title, self._tag, self._body):
            widget.setVisible(not folded)
        set_icon(self._fold_btn, "panel-left-open" if folded else "panel-left-close")
        tip = "Show the AI feed" if folded else "Fold the AI feed"
        self._fold_btn.setToolTip(tip)
        self._fold_btn.setAccessibleName(tip)
        self.setFixedWidth(_FOLDED_WIDTH if folded else _OPEN_WIDTH)
        if changed:
            self.folded_changed.emit(folded)

    def _toggle(self) -> None:
        self.set_folded(not self._folded)

    @staticmethod
    def _item_card(item: dict[str, str]) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background: {C.OVERLAY}; border-radius: 6px; }}"
            " QLabel { background: transparent; }"
        )
        box = QVBoxLayout(frame)
        box.setContentsMargins(10, 8, 10, 8)
        box.setSpacing(4)
        who = QLabel(f"{item['author']}  {item['time']}")
        who.setStyleSheet(f"color: {C.MUTED};")
        text = QLabel(item["text"])
        text.setWordWrap(True)
        box.addWidget(who)
        box.addWidget(text)
        if item["kind"] == "approval":
            row = QHBoxLayout()
            row.setSpacing(6)
            approve = QPushButton("Approve")
            reject = QPushButton("Reject")
            set_icon(approve, "check", "add")
            set_icon(reject, "x", "danger")
            row.addWidget(approve)
            row.addWidget(reject)
            row.addStretch(1)
            box.addLayout(row)
        frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        return frame
