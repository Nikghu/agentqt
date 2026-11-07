"""
Module: MD-GUI-034.004.M04 — Market Floor workspace
Parent SRD: SRD-GUI-034.004
Also: MD-GUI-034.045.M28 — header chips, tidy toolbar, Fold feed, Reset tab (SRD-GUI-034.045–.046)
"""
from __future__ import annotations

import logging
from functools import partial

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from us_swing.core.desk_contract import DeskState, DeskStatus, FloorData
from us_swing.core.desk_floor import DeskFloorData
from us_swing.gui.cards import GAP, card, gutter
from us_swing.gui.desk_control import DeskPoller
from us_swing.gui.floor_dialogs import CatalogDialog, NameDialog, PanelSettingsDialog
from us_swing.gui.floor_feed import AiFeedColumn
from us_swing.gui.floor_grid import PanelGrid
from us_swing.gui.floor_grid_model import GridModel, PanelSpec
from us_swing.gui.floor_layouts import DEFAULT_NAME, TAB_NAMES, LayoutStore, default_layout
from us_swing.gui.floor_panel import LinkBus, PanelFrame
from us_swing.gui.floor_sample import SampleFloorData
from us_swing.gui.popups import confirm
from us_swing.gui.theme import C

_log = logging.getLogger(__name__)
_SAVE_DELAY_MS = 500
_CHIP_TONES = {"good": "GREEN", "warn": "YELLOW", "bad": "RED", "info": "SUBTEXT"}


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
        self._data: FloorData = data or DeskFloorData(SampleFloorData())
        self._was_running = poller.status.state is DeskState.RUNNING
        self._store = store or LayoutStore()
        self._products = {p.id: p for p in self._data.products()}
        self._grids: dict[str, PanelGrid] = {}
        self._buses = {tab: LinkBus(self) for tab in TAB_NAMES}
        self._name = self._store.last()
        self._edit = False
        self._busy = False
        self._confirm = confirm
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(_SAVE_DELAY_MS)
        # timer → timeout → this page → flush
        self._save_timer.timeout.connect(self.flush)
        # poller → status_changed → this page → _on_desk_status
        poller.status_changed.connect(self._on_desk_status)

        gutter(self)
        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(GAP)
        left = QVBoxLayout()
        left.setSpacing(GAP)
        left.addWidget(card(self._build_top()))
        self.tabs = QTabWidget()
        self._load_layout()
        left.addWidget(card(self.tabs), 1)
        main.addLayout(left, 1)
        self.feed = AiFeedColumn(self._store.feed_folded())
        # feed → folded_changed → store → set_feed_folded
        self.feed.folded_changed.connect(self._store.set_feed_folded)
        # feed → folded_changed → this page → _on_feed_folded
        self.feed.folded_changed.connect(self._on_feed_folded)
        self._on_feed_folded(self.feed.is_folded())
        self._reload_feed()
        main.addWidget(card(self.feed))
        self.set_edit(False)

    def _on_desk_status(self, status: DeskStatus) -> None:
        running = status.state is DeskState.RUNNING
        ended = self._was_running and not running
        self._was_running = running
        if ended:
            self.reload_panels()

    def reload_panels(self) -> None:
        """Rebuild every panel from fresh product data; layout and edit mode are kept."""
        self._products = {p.id: p for p in self._data.products()}
        for grid in self._grids.values():
            grid.set_model(grid.model)
        self._reload_feed()
        self._reload_chips()
        _log.info("[Floor] Panels refreshed after a desk run")

    def _reload_feed(self) -> None:
        feed = getattr(self._data, "feed", None)
        self.feed.set_items(feed() if callable(feed) else None)

    def _reload_chips(self) -> None:
        while (item := self._chips.takeAt(0)) is not None:
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        chips = getattr(self._data, "chips", None)
        for text, tone in chips() if callable(chips) else []:
            colour = getattr(C, _CHIP_TONES.get(tone, "SUBTEXT"))
            chip = QLabel(text)
            chip.setObjectName("floor_chip")
            chip.setStyleSheet(
                f"QLabel#floor_chip {{ color: {colour}; border: 1px solid {colour};"
                " border-radius: 9px; padding: 1px 8px; }"
            )
            self._chips.addWidget(chip)

    def chip_texts(self) -> list[str]:
        """Return the header chip texts in order."""
        return [lbl.text() for lbl in self.findChildren(QLabel, "floor_chip")
                if not lbl.isHidden()]

    def tab_names(self) -> list[str]:
        """Return the tab titles in order."""
        return [self.tabs.tabText(i).replace("&&", "&") for i in range(self.tabs.count())]

    def panel_cards(self) -> list[QWidget]:
        """Return every panel card across all tabs."""
        return self.findChildren(QWidget, "floor_panel")

    def grid(self, tab: str) -> PanelGrid:
        """Return the grid of tab ``tab``."""
        return self._grids[tab]

    def layout_name(self) -> str:
        """Return the name of the layout in use."""
        return self._name

    def is_edit(self) -> bool:
        """Return whether edit mode is on."""
        return self._edit

    def _build_top(self) -> QWidget:
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(14, 10, 14, 10)
        title = QLabel("Market Floor")
        title.setObjectName("page_title")
        row.addWidget(title)
        row.addSpacing(GAP * 3)
        self._chips = QHBoxLayout()
        self._chips.setSpacing(GAP + 2)
        row.addLayout(self._chips)
        self._reload_chips()
        row.addStretch(1)
        self.layout_combo = QComboBox()
        self.layout_combo.setFixedWidth(130)
        self.layout_combo.setToolTip("Layout")
        # layout combo → currentTextChanged → this page → _on_layout_picked
        self.layout_combo.currentTextChanged.connect(self._on_layout_picked)
        self.add_btn = QPushButton("Add panel")
        # add button → clicked → this page → _choose_product
        self.add_btn.clicked.connect(self._choose_product)
        self.reset_btn = QPushButton("Reset tab")
        # reset button → clicked → this page → reset_tab
        self.reset_btn.clicked.connect(self.reset_tab)
        self.save_as_btn = QPushButton("Save as…")
        # save as button → clicked → this page → _prompt_save_as
        self.save_as_btn.clicked.connect(self._prompt_save_as)
        self.delete_btn = QPushButton("Delete")
        # delete button → clicked → this page → delete_layout
        self.delete_btn.clicked.connect(self.delete_layout)
        self._edit_only = (self.add_btn, self.reset_btn, self.save_as_btn, self.delete_btn)
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setCheckable(True)
        self.edit_btn.setFixedWidth(64)
        self.edit_btn.setStyleSheet(
            f"QPushButton:checked {{ background: {C.BLUE}; color: {C.BG}; outline: none; }}"
            "QPushButton:focus { outline: none; }"
        )
        # edit button → toggled → this page → set_edit
        self.edit_btn.toggled.connect(self.set_edit)
        self.fold_btn = QPushButton("Fold feed")
        # fold button → clicked → this page → _toggle_feed
        self.fold_btn.clicked.connect(self._toggle_feed)
        for widget in (self.layout_combo, *self._edit_only, self.edit_btn, self.fold_btn):
            row.addWidget(widget)
        self._refresh_layout_combo()
        return box

    def _toggle_feed(self) -> None:
        self.feed.set_folded(not self.feed.is_folded())

    def _on_feed_folded(self, folded: bool) -> None:
        self.fold_btn.setText("Show feed" if folded else "Fold feed")

    def reset_tab(self) -> None:
        """Put the default panels back on the current tab and save."""
        tab = self._current_tab()
        if not self._confirm(self, "Reset Tab", f"Put the default panels back on {tab}?\n"
                             "Its current panels will be lost.", confirm_text="Reset",
                             danger=True):
            return
        grid = self._grids[tab]
        grid.set_model(GridModel([PanelSpec.from_dict(raw) for raw in default_layout()[tab]]))
        self._schedule_save()
        _log.info("[Floor] Tab %s reset to its default panels", tab)

    def _refresh_layout_combo(self) -> None:
        self._busy = True
        self.layout_combo.clear()
        self.layout_combo.addItems(self._store.names())
        self.layout_combo.setCurrentText(self._name)
        self._busy = False
        self.delete_btn.setEnabled(self._name != DEFAULT_NAME)

    def _load_layout(self) -> None:
        """Build all five tabs from the store's panels for the current layout."""
        index = self.tabs.currentIndex()
        while self.tabs.count():
            page = self.tabs.widget(0)
            self.tabs.removeTab(0)
            if page is not None:
                page.setParent(None)
                page.deleteLater()
        self._grids.clear()
        layout = self._store.load(self._name)
        for tab in TAB_NAMES:
            specs: list[PanelSpec] = []
            for raw in layout[tab]:
                try:
                    specs.append(PanelSpec.from_dict(raw))
                except (KeyError, TypeError, ValueError):
                    _log.warning("[Floor] A broken panel in tab %s was dropped", tab)
            grid = PanelGrid(partial(self._make_frame, tab))
            grid.set_edit(self._edit)
            grid.set_model(GridModel(specs))
            # grid → layout_changed → this page → _schedule_save
            grid.layout_changed.connect(self._schedule_save)
            self._grids[tab] = grid
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidget(grid)
            self.tabs.addTab(scroll, _tab_label(tab))
        if index >= 0:
            self.tabs.setCurrentIndex(index)

    def _make_frame(self, tab: str, spec: PanelSpec) -> PanelFrame:
        frame = PanelFrame(spec, self._products.get(spec.product), self._data, self._buses[tab])
        # frame → settings_requested → this page → _open_settings
        frame.settings_requested.connect(lambda: self._open_settings(frame))
        # frame → removed → this page → remove_panel
        frame.removed.connect(lambda: self.remove_panel(tab, spec.id))
        return frame

    def _current_tab(self) -> str:
        return TAB_NAMES[max(self.tabs.currentIndex(), 0)]

    def set_edit(self, on: bool) -> None:
        """Turn edit mode on or off for every tab."""
        self._edit = on
        self.edit_btn.setText("Done" if on else "Edit")
        for button in self._edit_only:
            button.setVisible(on)
        for grid in self._grids.values():
            grid.set_edit(on)

    def add_product(self, product_id: str, tab: str | None = None) -> PanelSpec | None:
        """Add a panel for ``product_id`` to ``tab`` (default: current tab) at a free spot."""
        product = self._products.get(product_id)
        if product is None:
            return None
        grid = self._grids[tab or self._current_tab()]
        spec = PanelSpec(grid.model.next_id(), product.id, product.views[0])
        grid.model.add(spec)
        grid.sync()
        self._schedule_save()
        return spec

    def remove_panel(self, tab: str, panel_id: str) -> None:
        """Remove panel ``panel_id`` from ``tab``."""
        grid = self._grids[tab]
        grid.model.remove(panel_id)
        grid.sync()
        self._schedule_save()

    def apply_panel_settings(
        self, frame: PanelFrame, view: str, filters: dict[str, str], link: str | None
    ) -> None:
        """Change a panel's view, filters and link group, then save."""
        frame.apply_settings(view, filters, link)
        self._schedule_save()

    def _choose_product(self) -> None:
        dialog = CatalogDialog(self._data.products(), self)
        if dialog.exec() and (product := dialog.chosen()) is not None:
            self.add_product(product.id)

    def _open_settings(self, frame: PanelFrame) -> None:
        product = self._products.get(frame.spec.product)
        if product is None:
            return
        dialog = PanelSettingsDialog(
            product, frame.spec.view, frame.spec.filters, frame.spec.link, self
        )
        if dialog.exec():
            self.apply_panel_settings(frame, *dialog.result_settings())

    def _schedule_save(self) -> None:
        self._save_timer.start()

    def flush(self) -> None:
        """Write the current layout to the store now."""
        self._save_timer.stop()
        self._store.save(self._name, {t: g.model.to_list() for t, g in self._grids.items()})

    def closeEvent(self, event: QCloseEvent | None) -> None:  # noqa: N802
        """Save pending changes on close."""
        self.flush()
        super().closeEvent(event)

    def save_layout_as(self, name: str) -> None:
        """Save the current panels under ``name`` and switch to it."""
        name = name.strip()
        if not name:
            return
        if name in self._store.names() and name != self._name and not self._confirm(
            self, "Overwrite Layout", f"Replace the layout {name}?\nIts panels will be lost.",
            confirm_text="Replace", danger=True,
        ):
            return
        self._name = name
        self.flush()
        self._store.set_last(name)
        self._refresh_layout_combo()
        _log.info("[Floor] Layout %s saved", name)

    def switch_layout(self, name: str) -> None:
        """Save pending changes, then show layout ``name`` in all tabs."""
        if name not in self._store.names():
            return
        self.flush()
        self._name = name
        self._store.set_last(name)
        self._load_layout()
        self._refresh_layout_combo()

    def delete_layout(self) -> None:
        """Delete the layout in use (never Default) and fall back to Default."""
        name = self._name
        if name == DEFAULT_NAME or not self._confirm(
            self, "Delete Layout", f"Delete the layout {name}?", confirm_text="Delete",
            danger=True,
        ):
            return
        self._save_timer.stop()
        if self._store.delete(name):
            self._name = DEFAULT_NAME
            self._load_layout()
            self._refresh_layout_combo()
            _log.info("[Floor] Layout %s deleted", name)

    def _on_layout_picked(self, name: str) -> None:
        if not self._busy and name and name != self._name:
            self.switch_layout(name)

    def _prompt_save_as(self) -> None:
        dialog = NameDialog(parent=self)
        if dialog.exec():
            self.save_layout_as(dialog.name())
