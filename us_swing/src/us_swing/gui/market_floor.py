"""
Module: MD-GUI-034.004.M04 — Market Floor workspace
Parent SRD: SRD-GUI-034.004
"""
from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import (
    QAbstractItemView,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from us_swing.core.desk_contract import FloorData, ProductDescriptor
from us_swing.gui.cards import GAP, card, gutter
from us_swing.gui.desk_control import DeskBar, DeskPoller
from us_swing.gui.floor_feed import AiFeedColumn
from us_swing.gui.floor_layouts import TAB_NAMES, LayoutStore
from us_swing.gui.floor_sample import SAMPLE_TAG, SampleFloorData
from us_swing.gui.theme import C

_GRID_COLUMNS = 12
_ROW_PX = 28


_WIDE_COLUMNS = ("headline", "trigger", "event", "setup")


def _tab_label(name: str) -> str:
    """Return ``name`` as tab text; Qt reads a single & as a mnemonic, so double it."""
    return name.replace("&", "&&")


class MarketFloorWorkspace(QWidget):
    """Market Floor page: five tabs of panels and a foldable AI feed (SRD-GUI-034.004)."""

    def __init__(
        self,
        poller: DeskPoller,
        data: FloorData | None = None,
        store: LayoutStore | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._data: FloorData = data or SampleFloorData()
        self._store = store or LayoutStore()
        self._products = {p.id: p for p in self._data.products()}
        layout = self._store.load(self._store.last())

        gutter(self)
        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(GAP)
        left = QVBoxLayout()
        left.setSpacing(GAP)
        left.addWidget(card(self._build_top(poller)))
        self.tabs = QTabWidget()
        for name in TAB_NAMES:
            self.tabs.addTab(self._build_tab(layout[name]), _tab_label(name))
        left.addWidget(card(self.tabs), 1)
        main.addLayout(left, 1)
        self.feed = AiFeedColumn(self._store.feed_folded())
        # feed → folded_changed → store → set_feed_folded
        self.feed.folded_changed.connect(self._store.set_feed_folded)
        main.addWidget(card(self.feed))

    def tab_names(self) -> list[str]:
        """Return the tab titles in order."""
        return [self.tabs.tabText(i).replace("&&", "&") for i in range(self.tabs.count())]

    def panel_cards(self) -> list[QWidget]:
        """Return every panel card across all tabs."""
        return self.findChildren(QWidget, "floor_panel")

    @staticmethod
    def _build_top(poller: DeskPoller) -> QWidget:
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(14, 10, 14, 10)
        title = QLabel("Market Floor")
        title.setObjectName("page_title")
        row.addWidget(title)
        row.addStretch(1)
        row.addWidget(DeskBar(poller))
        return box

    def _build_tab(self, panels: list[dict[str, Any]]) -> QWidget:
        """Build one tab; step (b) replaces this with the draggable grid."""
        page = QWidget()
        grid = QGridLayout(page)
        grid.setContentsMargins(GAP, GAP, GAP, GAP)
        grid.setSpacing(GAP)
        for col in range(_GRID_COLUMNS):
            grid.setColumnStretch(col, 1)
        for spec in panels:
            try:
                frame = self._build_panel(spec)
                pos = (int(spec["y"]), int(spec["x"]), int(spec["h"]), int(spec["w"]))
            except (KeyError, TypeError, ValueError):
                frame, pos = self._missing_card(), (0, 0, 1, _GRID_COLUMNS)
            grid.addWidget(frame, *pos)
        return page

    @staticmethod
    def _missing_card() -> QWidget:
        frame = QWidget()
        frame.setObjectName("floor_panel")
        box = QVBoxLayout(frame)
        title = QLabel("Missing product")
        title.setObjectName("view_head")
        box.addWidget(title)
        return card(frame)

    def _build_panel(self, spec: dict[str, Any]) -> QWidget:
        product = self._products.get(str(spec["product"]))
        frame = QWidget()
        frame.setObjectName("floor_panel")
        box = QVBoxLayout(frame)
        box.setContentsMargins(8, 6, 8, 6)
        box.setSpacing(4)
        head = QHBoxLayout()
        title = QLabel(product.title if product else "Missing product")
        title.setObjectName("view_head")
        head.addWidget(title)
        head.addStretch(1)
        if product is None or product.sample:
            tag = QLabel(SAMPLE_TAG)
            tag.setStyleSheet(f"color: {C.MUTED};")
            head.addWidget(tag)
        box.addLayout(head)
        if product is None:
            box.addWidget(QLabel(f"No data for {spec['product']}"), 1)
        else:
            rows = self._data.rows(product.id, spec.get("filters", {}))
            box.addWidget(self._card_body(rows) if spec["view"] == "card"
                          else self._table_body(product, rows), 1)
        return card(frame)

    @staticmethod
    def _table_body(product: ProductDescriptor, rows: list[dict[str, Any]]) -> QTableWidget:
        table = QTableWidget(len(rows), len(product.columns))
        table.setHorizontalHeaderLabels([c.replace("_", " ").title() for c in product.columns])
        table.verticalHeader().setVisible(False)  # type: ignore[union-attr]
        table.verticalHeader().setDefaultSectionSize(_ROW_PX)  # type: ignore[union-attr]
        table.horizontalHeader().setStretchLastSection(True)  # type: ignore[union-attr]
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        for r, row in enumerate(rows):
            for c, name in enumerate(product.columns):
                table.setItem(r, c, QTableWidgetItem(str(row.get(name, ""))))
        table.resizeColumnsToContents()
        header = table.horizontalHeader()
        cols = list(product.columns)
        wide = next((cols.index(n) for n in _WIDE_COLUMNS if n in cols), len(cols) - 1)
        if header is not None and wide >= 0:
            header.setStretchLastSection(False)
            header.setSectionResizeMode(wide, QHeaderView.ResizeMode.Stretch)
        return table

    @staticmethod
    def _card_body(rows: list[dict[str, Any]]) -> QWidget:
        body = QWidget()
        lines = QVBoxLayout(body)
        lines.setContentsMargins(4, 4, 4, 4)
        lines.setSpacing(6)
        for row in rows:
            for key, value in row.items():
                lines.addWidget(QLabel(f"{key.replace('_', ' ').title()}: {value}"))
        lines.addStretch(1)
        return body
