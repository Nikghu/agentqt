"""Widgets made at start-up never flash as their own tiny window (ISS-GUI-0020)."""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from types import SimpleNamespace

from PyQt6.QtCore import QEvent, QObject
from PyQt6.QtWidgets import QApplication, QWidget

from tests.gui.test_screener_views import _FakeChart
from tests.gui.test_sidebar_shell import _ITEMS, _StubService
from tests.screener.conftest import make_composite_preset
from us_swing.gui.screener_panel import _PresetBuilderDialog
from us_swing.gui.screener_views import ListDetailView
from us_swing.gui.sidebar import Sidebar


class _ShowSpy(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.windows: list[str] = []

    def eventFilter(self, obj: QObject | None, event: QEvent | None) -> bool:  # noqa: N802
        if (event is not None and event.type() == QEvent.Type.Show
                and isinstance(obj, QWidget) and obj.isWindow()):
            self.windows.append(f"{type(obj).__name__} {obj.objectName()!r}")
        return False


@contextmanager
def _no_window_shown() -> Iterator[None]:
    app = QApplication.instance()
    assert app is not None
    spy = _ShowSpy()
    app.installEventFilter(spy)
    try:
        yield
    finally:
        app.removeEventFilter(spy)
    assert spy.windows == []


def _build(qtbot, make: Callable[[], QWidget]) -> QWidget:  # type: ignore[no-untyped-def]
    with _no_window_shown():
        widget = make()
    qtbot.addWidget(widget)
    return widget


def test_sidebar_rows_no_stray_window(qtbot) -> None:  # type: ignore[no-untyped-def]
    """UT-GUI-000.010.M01.T01: building the sidebar shows no row label as its own window."""
    _build(qtbot, lambda: Sidebar(_StubService(viewing=1), _ITEMS))  # type: ignore[arg-type]


def test_list_detail_chart_no_stray_window(qtbot) -> None:  # type: ignore[no-untyped-def]
    """UT-GUI-000.010.M01.T02: the list view chart box never shows as its own window."""
    view = _build(qtbot, lambda: ListDetailView(_FakeChart))
    assert isinstance(view, ListDetailView) and not view.chart_slot.isHidden()


def test_preset_dialog_save_as_no_stray_window(qtbot) -> None:  # type: ignore[no-untyped-def]
    """UT-GUI-000.010.M01.T03: editing a preset shows no Save As button as its own window."""
    preset = make_composite_preset()
    dlg = _build(qtbot, lambda: _PresetBuilderDialog(
        mgr=SimpleNamespace(), user_id="u1", preset=preset))
    assert not dlg._save_as_btn.isHidden()  # type: ignore[attr-defined]
