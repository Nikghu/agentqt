"""
Module: MD-GUI-034.006.M06 — Floor dialogs
Parent SRD: SRD-GUI-034.006
Also: MD-GUI-034.042.M37 — Ask the desk for new data box (SRD-GUI-034.042)

Frameless dialogs of the Market Floor: product catalog, panel settings and a name prompt.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QWidget,
)

from us_swing.core.desk_contract import ProductDescriptor
from us_swing.core.desk_data_asks import MAX_REQUEST
from us_swing.gui.floor_panel import LINK_GROUPS
from us_swing.gui.floor_sample import SAMPLE_TAG
from us_swing.gui.frameless_dialog import FramelessDialog

ANY = "Any"
NO_LINK = "None"
ASK_SENT = "Sent. The new panel will wait for you in AI Desk → Command."
_FIELD_QSS = (
    "QComboBox, QLineEdit { outline: none; }"
    " QComboBox:focus, QLineEdit:focus { outline: none; }"
)


def _button_row(dialog: FramelessDialog, ok_text: str) -> QPushButton:
    row = QHBoxLayout()
    row.addStretch(1)
    cancel = QPushButton("Cancel")
    cancel.setFixedWidth(80)
    # cancel → clicked → dialog → reject
    cancel.clicked.connect(dialog.reject)
    ok = QPushButton(ok_text)
    ok.setFixedWidth(80)
    ok.setDefault(True)
    # ok → clicked → dialog → accept
    ok.clicked.connect(dialog.accept)
    row.addWidget(cancel)
    row.addWidget(ok)
    dialog.content_layout().addLayout(row)
    return ok


class CatalogDialog(FramelessDialog):
    """Lists the available products; ``chosen()`` returns the selected one after Add.

    With ``ask`` given, a box below the list sends a data request to the desk; ``ask`` returns
    an empty string when the request was sent, else the reason it was not.
    """

    def __init__(self, products: Sequence[ProductDescriptor], parent: QWidget | None = None,
                 ask: Callable[[str], str] | None = None):
        super().__init__("Add Panel", min_width=380, parent=parent)
        self._ask = ask
        self._products = list(products)
        self.list = QListWidget()
        for product in self._products:
            tag = f"  ·  {SAMPLE_TAG}" if product.sample else ""
            item = QListWidgetItem(f"{product.title}  ·  {product.kind}{tag}")
            item.setData(Qt.ItemDataRole.UserRole, product.id)
            self.list.addItem(item)
        if self._products:
            self.list.setCurrentRow(0)
        # list → itemDoubleClicked → dialog → accept
        self.list.itemDoubleClicked.connect(lambda _item: self.accept())
        self.content_layout().addWidget(self.list, 1)
        self._ask_row()
        self.add_button = _button_row(self, "Add")
        # ask box → textChanged → dialog → Enter sends the request while the box has text
        self.ask_box.textChanged.connect(self._ask_default)

    def _ask_default(self, text: str) -> None:
        has_text = bool(text.strip())
        if has_text:
            self.ask_note.hide()
        self.ask_button.setEnabled(has_text)
        self.ask_button.setDefault(has_text)
        self.add_button.setDefault(not has_text)

    def _ask_row(self) -> None:
        self.ask_box = QLineEdit()
        self.ask_box.setMaxLength(MAX_REQUEST)
        self.ask_box.setPlaceholderText("Ask the desk for new data")
        self.ask_box.setStyleSheet(_FIELD_QSS)
        self.ask_button = QPushButton("Ask")
        self.ask_button.setFixedWidth(80)
        self.ask_button.setEnabled(False)
        self.ask_note = QLabel("")
        self.ask_note.setWordWrap(True)
        self.ask_note.hide()
        # Ask → clicked → dialog → send request
        self.ask_button.clicked.connect(self._send_ask)
        row = QHBoxLayout()
        row.addWidget(self.ask_box, 1)
        row.addWidget(self.ask_button)
        self.content_layout().addLayout(row)
        self.content_layout().addWidget(self.ask_note)
        for widget in (self.ask_box, self.ask_button):
            widget.setVisible(self._ask is not None)

    def _send_ask(self) -> None:
        text = self.ask_box.text().strip()
        if self._ask is None or not text:
            return
        why = self._ask(text)
        if not why:
            self.ask_box.clear()
        self.ask_note.setText(why or ASK_SENT)
        self.ask_note.show()

    def chosen(self) -> ProductDescriptor | None:
        """Return the selected product, or ``None`` when nothing is selected."""
        row = self.list.currentRow()
        return self._products[row] if 0 <= row < len(self._products) else None


class PanelSettingsDialog(FramelessDialog):
    """Edits view, filters and link group of one panel."""

    def __init__(
        self,
        product: ProductDescriptor,
        view: str,
        filters: dict[str, str],
        link: str | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Panel Settings", min_width=340, extra_qss=_FIELD_QSS, parent=parent)
        form = QFormLayout()
        self.view_combo = QComboBox()
        self.view_combo.addItems(list(product.views))
        self.view_combo.setCurrentText(view)
        form.addRow(QLabel("View"), self.view_combo)
        self.filter_combos: dict[str, QComboBox] = {}
        for name, options in product.filters.items():
            combo = QComboBox()
            combo.addItems([ANY, *options])
            combo.setCurrentText(filters.get(name, ANY))
            self.filter_combos[name] = combo
            form.addRow(QLabel(name.replace("_", " ").title()), combo)
        self.link_combo = QComboBox()
        self.link_combo.addItems([NO_LINK, *LINK_GROUPS])
        self.link_combo.setCurrentText(link or NO_LINK)
        form.addRow(QLabel("Link group"), self.link_combo)
        self.content_layout().addLayout(form)
        _button_row(self, "Apply")

    def result_settings(self) -> tuple[str, dict[str, str], str | None]:
        """Return (view, filters without Any, link group or ``None``)."""
        filters = {
            name: combo.currentText()
            for name, combo in self.filter_combos.items()
            if combo.currentText() != ANY
        }
        link = self.link_combo.currentText()
        return self.view_combo.currentText(), filters, None if link == NO_LINK else link


class NameDialog(FramelessDialog):
    """Asks for a short name (used by Save as)."""

    def __init__(self, title: str = "Save Layout", parent: QWidget | None = None) -> None:
        super().__init__(title, min_width=320, extra_qss=_FIELD_QSS, parent=parent)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Name")
        self.content_layout().addWidget(self.edit)
        self.save_button = _button_row(self, "Save")
        self.save_button.setEnabled(False)
        # edit → textChanged → dialog → enable Save only for a non-empty name
        self.edit.textChanged.connect(lambda: self.save_button.setEnabled(bool(self.name())))

    def name(self) -> str:
        """Return the typed name without surrounding spaces."""
        return self.edit.text().strip()
