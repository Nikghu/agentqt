"""
Module: MD-GUI-034.006.M06 — Floor panel
Parent SRD: SRD-GUI-034.006
Also: SRD-GUI-034.047–.052 — painted views, idea cell delegates, view fallback

One Market Floor panel: title row, body for the chosen view, link group dot and the bus that
carries a clicked symbol to other panels of the same group.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from us_swing.core.desk_contract import FloorData, ProductDescriptor
from us_swing.gui.floor_charts import ScoreDelegate, SideDelegate, view_body
from us_swing.gui.floor_grid_model import PanelSpec
from us_swing.gui.floor_sample import SAMPLE_TAG
from us_swing.gui.icons import icon_button
from us_swing.gui.theme import C

ROW_PX = 28
LINK_GROUPS = ("A", "B", "C")
_WIDE_COLUMNS = ("headline", "why", "trigger", "event", "setup")
_GRIP = 14


def _flat_btn() -> str:
    return (
        "QPushButton { background: transparent; border: none; padding: 0; outline: none; }"
        f"QPushButton:hover {{ background: {C.OVERLAY}; }}"
        "QPushButton:focus { outline: none; }"
    )


def _group_colour(group: str | None) -> str:
    colours: dict[str, str] = {"A": C.BLUE, "B": C.GREEN, "C": C.MAUVE}
    return str(colours.get(group or "", C.MUTED))


class LinkBus(QObject):
    """Carries a selected symbol to every panel of a link group."""

    symbol_selected = pyqtSignal(str, str, object)  # group, symbol, sender

    def publish(self, group: str, symbol: str, sender: object) -> None:
        """Announce ``symbol`` for ``group``; ``sender`` is skipped by its own handler."""
        self.symbol_selected.emit(group, symbol, sender)


def table_body(product: ProductDescriptor, rows: list[dict[str, Any]]) -> QTableWidget:
    """Return a read-only table of ``rows`` with one wide column stretched."""
    table = QTableWidget(len(rows), len(product.columns))
    table.setHorizontalHeaderLabels([c.replace("_", " ").title() for c in product.columns])
    vertical = table.verticalHeader()
    if vertical is not None:
        vertical.setVisible(False)
        vertical.setDefaultSectionSize(ROW_PX)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    for r, row in enumerate(rows):
        for c, name in enumerate(product.columns):
            table.setItem(r, c, QTableWidgetItem(str(row.get(name, ""))))
    table.resizeColumnsToContents()
    _add_idea_delegates(table, product.columns)
    header = table.horizontalHeader()
    cols = list(product.columns)
    wide = next((cols.index(n) for n in _WIDE_COLUMNS if n in cols), len(cols) - 1)
    if header is not None and wide >= 0:
        header.setStretchLastSection(False)
        header.setSectionResizeMode(wide, QHeaderView.ResizeMode.Stretch)
    return table


def _add_idea_delegates(table: QTableWidget, columns: tuple[str, ...]) -> None:
    """Draw score as a bar and side as a label when a table has both columns."""
    if "score" not in columns or "side" not in columns:
        return
    table.setItemDelegateForColumn(columns.index("score"), ScoreDelegate(table))
    table.setItemDelegateForColumn(columns.index("side"), SideDelegate(table))
    table.setColumnWidth(columns.index("score"), 110)


def card_body(rows: list[dict[str, Any]]) -> QWidget:
    """Return label lines for ``rows``."""
    body = QWidget()
    lines = QVBoxLayout(body)
    lines.setContentsMargins(4, 4, 4, 4)
    lines.setSpacing(6)
    for row in rows:
        for key, value in row.items():
            lines.addWidget(QLabel(f"{key.replace('_', ' ').title()}: {value}"))
    lines.addStretch(1)
    return body


class PanelFrame(QFrame):
    """A panel on the grid; it shows one product in a table, card or chart view."""

    symbol_clicked = pyqtSignal(str)
    settings_requested = pyqtSignal()
    removed = pyqtSignal()

    def __init__(
        self,
        spec: PanelSpec,
        product: ProductDescriptor | None,
        data: FloorData,
        bus: LinkBus | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.spec = spec
        self._product = product
        self._data = data
        self._bus = bus
        self._symbol = ""
        self._body: QWidget | None = None
        self.setObjectName("floor_panel")
        self.setStyleSheet(
            f"QFrame#floor_panel {{ background: {C.SURFACE}; border: 1px solid {C.OVERLAY};"
            " border-radius: 6px; }"
        )
        self._box = QVBoxLayout(self)
        self._box.setContentsMargins(8, 6, 8, 6)
        self._box.setSpacing(4)
        self._build_title()
        self.grip = QLabel("◢", self)
        self.grip.setStyleSheet(f"color: {C.MUTED}; background: transparent; border: none;")
        self.grip.setFixedWidth(_GRIP)
        self.grip.setCursor(Qt.CursorShape.SizeFDiagCursor)
        for handle, kind in ((self.title_bar, "move"), (self.grip, "resize")):
            handle.setProperty("floor_handle", kind)
            handle.setProperty("panel_id", spec.id)
        if product is not None and product.views and spec.view not in product.views:
            spec.view = product.views[0]
        self.set_edit(False)
        self._rebuild_body()
        if bus is not None:
            # bus → symbol_selected → this frame → _on_bus
            bus.symbol_selected.connect(self._on_bus)

    def _build_title(self) -> None:
        self.title_bar = QWidget()
        self.title_bar.setStyleSheet("background: transparent; border: none;")
        head = QHBoxLayout(self.title_bar)
        head.setContentsMargins(0, 0, 0, 0)
        title = QLabel(self._product.title if self._product else "Missing product")
        title.setObjectName("view_head")
        head.addWidget(title)
        head.addStretch(1)
        if self._product is None or self._product.sample:
            tag = QLabel(SAMPLE_TAG)
            tag.setStyleSheet(f"color: {C.MUTED};")
            head.addWidget(tag)
        self._dot = QLabel("●")
        head.addWidget(self._dot)
        self._gear = icon_button("settings", "neutral", "Panel settings")
        self._gear.setFixedWidth(28)
        self._gear.setStyleSheet(_flat_btn())
        # gear → clicked → this frame → settings_requested
        self._gear.clicked.connect(self.settings_requested)
        head.addWidget(self._gear)
        self._close = icon_button("x", "danger", "Remove panel")
        self._close.setFixedWidth(28)
        self._close.setStyleSheet(_flat_btn())
        # close → clicked → this frame → removed
        self._close.clicked.connect(self.removed)
        head.addWidget(self._close)
        self._box.addWidget(self.title_bar)
        self._update_dot()

    def _update_dot(self) -> None:
        group = self.spec.link
        self._dot.setVisible(bool(group))
        self._dot.setToolTip(f"Link group {group}" if group else "")
        self._dot.setStyleSheet(f"color: {_group_colour(group)};")

    def set_edit(self, on: bool) -> None:
        """Show the remove button and resize grip only in edit mode."""
        self._close.setVisible(on)
        self.grip.setVisible(on)
        self.title_bar.setCursor(
            Qt.CursorShape.SizeAllCursor if on else Qt.CursorShape.ArrowCursor
        )
        self.grip.raise_()

    def resizeEvent(self, event: Any) -> None:  # noqa: N802
        """Keep the grip in the bottom-right corner."""
        super().resizeEvent(event)
        self.grip.move(self.width() - _GRIP - 2, self.height() - self.grip.sizeHint().height() - 2)
        self.grip.raise_()

    def set_view(self, view: str) -> None:
        """Switch the body to ``view`` (table, card or chart)."""
        self.spec.view = view
        self._rebuild_body()

    def apply_settings(self, view: str, filters: Mapping[str, str], link: str | None) -> None:
        """Apply new view, filters and link group, then rebuild the body."""
        self.spec.view = view
        self.spec.filters = dict(filters)
        self.spec.link = link
        self._update_dot()
        self._rebuild_body()

    def set_symbol(self, symbol: str) -> None:
        """Show ``symbol``: select its table row or name it on the chart; cards ignore it."""
        self._symbol = symbol
        body = self._body
        if isinstance(body, QTableWidget):
            self._select_row(body, symbol)
        elif self.spec.view == "chart" and body is not None:
            label = body.findChild(QLabel, "chart_symbol")
            if label is not None:
                label.setText(symbol)

    def _select_row(self, table: QTableWidget, symbol: str) -> None:
        cols = list(self._product.columns) if self._product else []
        if "symbol" not in cols:
            return
        col = cols.index("symbol")
        table.clearSelection()
        for r in range(table.rowCount()):
            item = table.item(r, col)
            if item is not None and item.text() == symbol:
                table.selectRow(r)
                return

    def _rebuild_body(self) -> None:
        if self._body is not None:
            self._box.removeWidget(self._body)
            self._body.setParent(None)
            self._body.deleteLater()
        self._body = self._make_body()
        self._box.addWidget(self._body, 1)
        self.grip.raise_()
        if self._symbol:
            self.set_symbol(self._symbol)

    def _make_body(self) -> QWidget:
        product = self._product
        if product is None:
            return QLabel(f"No data for {self.spec.product}")
        if self.spec.view == "chart":
            return self._chart_body()
        rows = self._data.rows(product.id, self.spec.filters)
        painted = view_body(self.spec.view, rows)
        if painted is not None:
            return painted
        if self.spec.view == "card":
            return card_body(rows)
        table = table_body(product, rows)
        if "symbol" in product.columns:
            # table → cellClicked → this frame → _on_cell
            table.cellClicked.connect(self._on_cell)
        return table

    def _chart_body(self) -> QWidget:
        body = QWidget()
        lines = QVBoxLayout(body)
        symbol = QLabel(self._symbol)
        symbol.setObjectName("chart_symbol")
        symbol.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note = QLabel("Chart comes later")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setStyleSheet(f"color: {C.MUTED};")
        lines.addStretch(1)
        lines.addWidget(symbol)
        lines.addWidget(note)
        lines.addStretch(1)
        return body

    def _on_cell(self, row: int, _col: int) -> None:
        body = self._body
        if not isinstance(body, QTableWidget) or self._product is None:
            return
        item = body.item(row, list(self._product.columns).index("symbol"))
        if item is None:
            return
        self._symbol = item.text()
        self.symbol_clicked.emit(self._symbol)
        if self._bus is not None and self.spec.link:
            self._bus.publish(self.spec.link, self._symbol, self)

    def _on_bus(self, group: str, symbol: str, sender: object) -> None:
        if group == self.spec.link and sender is not self:
            self.set_symbol(symbol)
