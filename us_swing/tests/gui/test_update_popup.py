"""Tests for the sidebar Updates item and its popup (SRD-GUI-027.005)."""
from __future__ import annotations

import datetime
from typing import Any

import pytest
import update_dialog
import updater_stub

from us_swing import __version__
from us_swing.gui.update_popup import UpdatePopup, checked_text


@pytest.fixture()
def popup(qtbot: Any) -> UpdatePopup:
    widget = UpdatePopup()
    qtbot.addWidget(widget)
    return widget


def _info() -> updater_stub.UpdateInfo:
    return updater_stub.UpdateInfo({}, "9.9.9", "https://x/setup.exe", "", "")


def test_version_and_last_check_text(popup: UpdatePopup, monkeypatch: Any) -> None:
    """UT-GUI-027.005.M07.T01: the popup shows the installed version and last check time."""
    stamp = datetime.datetime(2026, 10, 25, 9, 14).timestamp()
    monkeypatch.setattr(updater_stub, "last_check_time", lambda: stamp)

    popup.refresh()

    assert popup._version.text() == f"Installed v{__version__} · last checked 25 Oct 09:14"


def test_never_checked() -> None:
    """UT-GUI-027.005.M07.T02: no stamp reads "not checked yet"."""
    assert checked_text(None) == "not checked yet"


def test_update_found_emits_and_opens_dialog(
    popup: UpdatePopup, qtbot: Any, monkeypatch: Any
) -> None:
    """UT-GUI-027.005.M07.T03: a found update emits once and opens the update dialog."""
    opened: list[str] = []

    class _Dialog:
        def __init__(self, info: updater_stub.UpdateInfo) -> None:
            opened.append(info.remote_version)

        def exec(self) -> int:
            return 0

    monkeypatch.setattr(update_dialog, "_UpdateDialog", _Dialog)
    popup._check_btn.setEnabled(False)

    with qtbot.waitSignal(popup.update_found, timeout=500):
        popup._on_found(_info())

    assert opened == ["9.9.9"]
    assert popup._check_btn.isEnabled()


def test_failed_check_shows_note(popup: UpdatePopup, qtbot: Any) -> None:
    """UT-GUI-027.005.M07.T04: a failed check shows the reason and finds no update."""
    found: list[bool] = []
    popup.update_found.connect(lambda: found.append(True))
    popup._check_btn.setEnabled(False)

    popup._on_failed("timeout")

    assert popup._note.text() == "Could not check for updates — timeout"
    assert not popup._note.isHidden()
    assert popup._check_btn.isEnabled()
    assert found == []
