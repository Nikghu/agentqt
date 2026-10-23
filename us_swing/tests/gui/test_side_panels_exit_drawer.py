"""Tests for the side panels and Exit drawer (FO-GUI-019)."""
from __future__ import annotations

import datetime

import pytest
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QTableWidget

from us_swing.gui._types import OpenPosition
from us_swing.gui.dashboard_panel import _ExitForm, _SquareOffForm
from us_swing.gui.main_window import _MiniState
from us_swing.gui.side_panels import IconStrip, PositionDetails


def _pos(symbol: str = "NVDA", qty: int = 85, avg: float = 138.20, cur: float = 142.90) -> OpenPosition:
    return OpenPosition(
        symbol=symbol, user_id=1, quantity=qty, average_price=avg, stop_loss=132.50,
        target_price=155.00, mode="paper", trailing_stop=False, filled_quantity=qty,
        total_quantity=qty, current_price=cur, strategy_id="", trade_id="",
        entry_time=datetime.datetime(2026, 10, 23, 9, 35), direction="LONG",
    )


class _StubService(QObject):
    positions_updated = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.positions = [_pos()]

    def get_positions(self) -> list[OpenPosition]:
        return self.positions


@pytest.fixture()
def strip(qtbot):
    widget = IconStrip()
    qtbot.addWidget(widget)
    return widget


def test_strip_button_toggles_panel(qtbot, strip):
    """UT-GUI-019.001.M01.T01: Strip button toggles its panel."""
    seen: list[tuple[str, bool]] = []
    strip.panel_toggled.connect(lambda n, on: seen.append((n, on)))
    strip._buttons["watch"].click()
    strip._buttons["watch"].click()
    assert seen == [("watch", True), ("watch", False)]


def test_log_badge_counts_warnings_while_hidden(strip):
    """UT-GUI-019.001.M01.T02: Log badge counts warnings only while hidden."""
    strip.count_warning("WARNING")
    strip.count_warning("INFO")
    strip.count_warning("ERROR")
    assert strip.unseen == 2
    assert strip._badge.text() == "2"
    strip.set_checked("log", True)
    assert strip.unseen == 0
    assert strip._badge.isHidden()


def test_details_shows_position(qtbot):
    """UT-GUI-019.003.M01.T01: Details shows the position."""
    details = PositionDetails(_StubService())  # type: ignore[arg-type]
    qtbot.addWidget(details)
    details.show_position(_pos(), "trader")
    assert "NVDA" in details._symbol.text()
    assert details._values["Quantity"].text() == "85"
    assert details._values["Avg entry"].text() == "$138.20"
    assert "+399.50" in details._values["Unrealised P&L"].text()
    assert details._exit_btn.isEnabled()


def test_details_without_selection(qtbot):
    """UT-GUI-019.003.M01.T02: Details with no selection."""
    details = PositionDetails(_StubService())  # type: ignore[arg-type]
    qtbot.addWidget(details)
    details.show_position(None)
    assert not details._hint.isHidden()
    assert not details._exit_btn.isEnabled()
    assert not details._chart_btn.isEnabled()


@pytest.fixture()
def exit_form(qtbot):
    form = _ExitForm(_pos(), "trader")
    qtbot.addWidget(form)
    seen: list[tuple[str, dict]] = []
    form.submitted.connect(lambda a, p: seen.append((a, p)))
    return form, seen


def test_market_exit_needs_review_then_confirm(exit_form):
    """UT-GUI-019.006.M02.T01: Market exit sends only after Review and Confirm."""
    form, seen = exit_form
    form._confirm_btn.click()
    assert seen == []
    assert "Sell 85 NVDA at market" in form._review_lbl.text()
    form._confirm_btn.click()
    assert len(seen) == 1
    action, params = seen[0]
    assert action == "full_close"
    assert params["qty"] == 85 and params["order_type"] == "MKT"


def test_confirm_twice_sends_once(exit_form):
    """UT-GUI-019.006.M02.T04: A double-click on Confirm sends only one request."""
    form, seen = exit_form
    form._confirm_btn.click()
    form._on_confirm()
    form._on_confirm()
    assert len(seen) == 1
    assert not form.isEnabled()


def test_stop_tab_returns_same_params(exit_form):
    """UT-GUI-019.006.M02.T02: Stop tab returns the same params as the old dialog."""
    form, seen = exit_form
    form._tabs.setCurrentIndex(3)
    form._sl_price.setValue(132.5)
    form._trailing_chk.setChecked(False)
    form._confirm_btn.click()
    form._confirm_btn.click()
    assert seen == [("set_stop_loss",
                     {"price": 132.5, "trailing": False, "trail_by": "", "trail_val": 0.0})]


def test_cancel_and_back_send_nothing(qtbot, exit_form):
    """UT-GUI-019.006.M02.T03: Cancel and Back send nothing."""
    form, seen = exit_form
    form._confirm_btn.click()
    form._back_btn.click()
    assert form._confirm_btn.text() == "Review"
    assert form._tabs.isEnabled()
    with qtbot.waitSignal(form.cancelled):
        form._cancel_btn.click()
    assert seen == []


def test_square_off_list_and_confirm(qtbot):
    """UT-GUI-019.007.M02.T01: Square-off list shows all positions and confirms."""
    positions = [_pos("NVDA"), _pos("AAPL", 120, 228.4, 233.15), _pos("AMD", 60, 156.75, 154.2)]
    form = _SquareOffForm(positions, "all users")
    qtbot.addWidget(form)
    seen: list[str] = []
    form.submitted.connect(lambda a, _p: seen.append(a))
    assert form.findChild(QTableWidget).rowCount() == 3
    form._confirm_btn.click()
    assert seen == []
    form._confirm_btn.click()
    assert seen == ["square_off_all"]


def test_right_panel_shrinks_sidebar():
    """UT-GUI-019.002.M03.T01: Opening the right panel shrinks the sidebar and closing restores it."""
    state = _MiniState(user_mini=False)
    state.panel_open = True
    assert state.want_mini()
    state.panel_open = False
    assert not state.want_mini()
