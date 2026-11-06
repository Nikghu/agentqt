"""
Module: MD-GUI-034.004.M04 — Floor AI feed column
Parent SRD: SRD-GUI-034.004
Also: MD-GUI-034.015.M14 — real briefs from the desk (SRD-GUI-034.015)
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
        outer.addWidget(self._body, 1)
        self.set_items(None)
        self.set_folded(folded)

    def set_items(self, items: list[dict[str, str]] | None) -> None:
        """Show ``items`` (newest first); ``None`` shows the sample items with the Sample tag."""
        sample = items is None
        holder = QWidget()
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        for item in sample_feed_items() if items is None else items:
            layout.addWidget(self._item_card(item))
        layout.addStretch(1)
        self._body.setWidget(holder)
        self._sample = sample
        self._tag.setVisible(sample and not self._folded)

    def is_folded(self) -> bool:
        """Return True when only the unfold button shows."""
        return self._folded

    def set_folded(self, folded: bool) -> None:
        """Fold or unfold the column; emits ``folded_changed`` when the state changes."""
        changed = folded != self._folded
        self._folded = folded
        for widget in (self._title, self._body):
            widget.setVisible(not folded)
        self._tag.setVisible(self._sample and not folded)
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
        who.setTextFormat(Qt.TextFormat.PlainText)
        text = QLabel(item["text"])
        text.setTextFormat(Qt.TextFormat.PlainText)
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
