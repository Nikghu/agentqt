"""
Module: MD-GUI-015.003.M04 — Indicator Library Tree
Parent SRD: SRD-GUI-015.003
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from enum import Enum
from typing import Protocol

from PyQt6.QtCore import (
    QMimeData,
    QModelIndex,
    QObject,
    QSortFilterProxyModel,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QPainter, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTreeView,
    QWidget,
)

from us_swing.core.indicator_rules import CATALOGUE, Category
from us_swing.gui.theme import C

MIME_INDICATOR = "application/x-usswing-indicator-id"

IdRole = Qt.ItemDataRole.UserRole + 1
InUseRole = Qt.ItemDataRole.UserRole + 2

_IN_USE_TEXT = "in use"


class LibraryEntry(Protocol):
    """What the tree needs from a catalogue entry (indicator or price action pattern)."""

    @property
    def id(self) -> str: ...
    @property
    def name(self) -> str: ...
    @property
    def category(self) -> Enum: ...
    @property
    def description(self) -> str: ...
    @property
    def available(self) -> bool: ...
    @property
    def unavailable_reason(self) -> str: ...


def _category_text(category: Enum, used: int, total: int) -> str:
    return f"{str(category.value).upper()}   {used} / {total}"


class LibraryTreeModel(QStandardItemModel):
    """Catalogue grouped by category, with per-entry usage flags."""

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        entries: Sequence[LibraryEntry] = CATALOGUE,
        categories: Iterable[Enum] = Category,
    ) -> None:
        super().__init__(parent)
        self._entries = entries
        self._categories = list(categories)
        self._items: dict[str, QStandardItem] = {}
        self._category_items: dict[Enum, QStandardItem] = {}
        self._totals: dict[Enum, int] = {}
        self._specs: dict[str, LibraryEntry] = {}
        self._build()

    def _build(self) -> None:
        root = self.invisibleRootItem()
        assert root is not None
        for category in self._categories:
            specs = [s for s in self._entries if s.category is category]
            if not specs:
                continue
            cat_item = QStandardItem(_category_text(category, 0, len(specs)))
            cat_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            cat_item.setForeground(QColor(C.SUBTEXT))
            self._category_items[category] = cat_item
            self._totals[category] = len(specs)
            for spec in specs:
                item = QStandardItem(spec.name)
                item.setData(spec.id, IdRole)
                item.setData(False, InUseRole)
                if spec.available:
                    item.setFlags(
                        Qt.ItemFlag.ItemIsEnabled
                        | Qt.ItemFlag.ItemIsSelectable
                        | Qt.ItemFlag.ItemIsDragEnabled
                    )
                    item.setToolTip(spec.description)
                else:
                    item.setFlags(Qt.ItemFlag.NoItemFlags)
                    item.setForeground(QColor(C.MUTED))
                    item.setToolTip(spec.unavailable_reason)
                cat_item.appendRow(item)
                self._items[spec.id] = item
                self._specs[spec.id] = spec
            root.appendRow(cat_item)

    def find_item(self, indicator_id: str) -> QStandardItem | None:
        return self._items.get(indicator_id)

    def set_usage(self, counts: Mapping[str, int]) -> None:
        """Mark indicators that have at least one rule and refresh category counts."""
        used_per_category: dict[Enum, int] = dict.fromkeys(self._category_items, 0)
        for indicator_id, item in self._items.items():
            in_use = counts.get(indicator_id, 0) > 0
            item.setData(in_use, InUseRole)
            if in_use:
                used_per_category[self._specs[indicator_id].category] += 1
        for category, cat_item in self._category_items.items():
            cat_item.setText(
                _category_text(category, used_per_category[category], self._totals[category])
            )

    def mimeTypes(self) -> list[str]:
        return [MIME_INDICATOR]

    def mimeData(self, indexes: Iterable[QModelIndex]) -> QMimeData | None:
        ids = [i.data(IdRole) for i in indexes if i.data(IdRole)]
        if not ids:
            return None
        mime = QMimeData()
        mime.setData(MIME_INDICATOR, str(ids[0]).encode("utf-8"))
        return mime


class LibraryFilterProxy(QSortFilterProxyModel):
    """Case-insensitive name filter that keeps categories having a matching child."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.setRecursiveFilteringEnabled(True)
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setFilterRole(Qt.ItemDataRole.DisplayRole)

    def _matches(self, text: str) -> bool:
        return self.filterRegularExpression().match(text).hasMatch()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        if model is None:
            return True
        index = model.index(source_row, 0, source_parent)
        if not source_parent.isValid():
            return any(
                self._matches(str(model.index(r, 0, index).data() or ""))
                for r in range(model.rowCount(index))
            )
        return self._matches(str(index.data() or ""))


class LibraryItemDelegate(QStyledItemDelegate):
    """Default item painting plus a right-aligned "in use" tag."""

    def paint(
        self, painter: QPainter | None, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        super().paint(painter, option, index)
        if painter is None:
            return
        if not index.data(InUseRole):
            return
        painter.save()
        painter.setPen(QColor(C.BLUE))
        painter.drawText(
            option.rect.adjusted(0, 0, -8, 0),
            int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
            _IN_USE_TEXT,
        )
        painter.restore()


class LibraryTreeView(QTreeView):
    """Drag-only tree of catalogue indicators."""

    indicator_activated = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setDragEnabled(True)
        self.setAcceptDrops(False)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setIndentation(14)
        self.setItemDelegate(LibraryItemDelegate(self))
        # view → doubleClicked → view → _on_double_clicked
        self.doubleClicked.connect(self._on_double_clicked)

    def _on_double_clicked(self, index: QModelIndex) -> None:
        indicator_id = index.data(IdRole)
        if indicator_id and index.flags() & Qt.ItemFlag.ItemIsEnabled:
            self.indicator_activated.emit(str(indicator_id))
