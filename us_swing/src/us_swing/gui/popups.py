"""
Module: MD-GUI-000.009.M01 — Frameless popups
Parent SRD: SRD-GUI-000.009

Confirm and message popups in the app's frameless style, used instead of the
native ``QMessageBox``.
"""
from __future__ import annotations

from typing import Literal

from PyQt6.QtWidgets import QDialog, QWidget

from us_swing.gui.theme import C

_ACCENTS = {"info": "BLUE", "warning": "YELLOW", "error": "RED"}


def confirm(parent: QWidget | None, title: str, text: str, *, confirm_text: str = "Yes",
            danger: bool = False) -> bool:
    """Ask a Yes / Cancel question; True only when the confirm button is pressed.

    Args:
        parent: Window the popup belongs to.
        title: Short title shown in the popup's title bar.
        text: First line is the question; further lines are muted detail.
        confirm_text: Label of the confirm button.
        danger: Red accent for deletes and other actions that cannot be undone.
    """
    # Imported here: the module pulls in the execution package.
    from us_swing.gui.active_cycles_panel import _ConfirmDialog

    dialog = _ConfirmDialog(title.upper(), text, confirm_text=confirm_text,
                            accent=C.RED if danger else C.BLUE, parent=parent)
    return dialog.exec() == QDialog.DialogCode.Accepted


def notify(parent: QWidget | None, title: str, text: str,
           kind: Literal["info", "warning", "error"] = "info") -> None:
    """Show a message with one OK button and wait until it is closed.

    Args:
        parent: Window the popup belongs to.
        title: Short title shown in the popup's title bar.
        text: First line is the message; further lines are muted detail.
        kind: Accent colour — blue info, yellow warning, red error.
    """
    from us_swing.gui.active_cycles_panel import _ConfirmDialog

    dialog = _ConfirmDialog(title.upper(), text, confirm_text="OK",
                            accent=getattr(C, _ACCENTS[kind]), show_cancel=False, parent=parent)
    dialog.exec()
