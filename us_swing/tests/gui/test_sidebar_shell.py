"""Tests for the sidebar workspace shell (FO-GUI-018)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QWidget

from us_swing.gui.main_window import _MiniState
from us_swing.gui.reveal import RevealController
from us_swing.gui.sidebar import Sidebar

_ITEMS = [("layout-dashboard", "Dashboard"), ("filter", "Screener"), ("zap", "Execution"),
          ("chart-candlestick", "Chart"), ("settings", "Settings")]


class _StubService(QObject):
    viewing_changed = pyqtSignal()
    positions_updated = pyqtSignal()
    account_updated = pyqtSignal()

    def __init__(self, viewing: int | None = None) -> None:
        super().__init__()
        self.viewing = viewing
        self.users = [SimpleNamespace(
            username="trader", mode="live", ibkr_client_id=7,
            risk_config=SimpleNamespace(risk_per_trade_pct=1.5),
        )]

    def get_viewing_uid(self) -> int | None:
        return self.viewing

    def get_users(self) -> list[SimpleNamespace]:
        return self.users

    def get_user_by_id(self, uid: int) -> SimpleNamespace | None:
        return self.users[0] if uid == 1 else None

    def effective_capital(self) -> float:
        return 25_000.0

    def margin_available(self) -> float:
        return 18_500.0


@pytest.fixture()
def sidebar(qtbot):
    widget = Sidebar(_StubService(viewing=1), _ITEMS)  # type: ignore[arg-type]
    qtbot.addWidget(widget)
    return widget


def test_nav_click_requests_page(qtbot, sidebar):
    """UT-GUI-018.001.M01.T01: Nav click asks for that screen."""
    with qtbot.waitSignal(sidebar.page_requested) as blocker:
        sidebar._nav[2].click()
    assert blocker.args == [2]
    assert sidebar._nav[2].isChecked()


def test_mini_hides_labels_keeps_tooltips(sidebar):
    """UT-GUI-018.002.M01.T01: Mini mode hides labels, keeps tooltips."""
    sidebar.set_mini(True)
    assert all(btn.text() == "" for btn in sidebar._nav)
    assert [btn.toolTip() for btn in sidebar._nav] == [label for _, label in _ITEMS]
    sidebar.set_mini(False)
    assert sidebar._nav[0].text() == "Dashboard"


def test_footer_shows_user_details(sidebar):
    """UT-GUI-018.004.M01.T01: Footer shows user details."""
    footer = sidebar._footer
    assert "trader" in footer._scope.text()
    details = footer._details.text()
    for part in ("LIVE", "#7", "1.5%", "$25,000", "$18,500"):
        assert part in details


def test_footer_all_users_and_missing_user(qtbot):
    """UT-GUI-018.004.M01.T02: Footer handles All Users and missing user."""
    svc = _StubService(viewing=None)
    widget = Sidebar(svc, _ITEMS)  # type: ignore[arg-type]
    qtbot.addWidget(widget)
    assert "All Users" in widget._footer._scope.text()
    assert "1 accounts" in widget._footer._scope.text()
    svc.viewing = 99
    svc.viewing_changed.emit()
    assert "All Users" in widget._footer._scope.text()


def _reveal_with_widget(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    reveal = RevealController()
    reveal.register("x", widget, 0, 200, start_open=False)
    return reveal, widget


def test_reveal_animates_and_reports(qtbot):
    """UT-GUI-018.006.M02.T01: Reveal animates and reports."""
    reveal, widget = _reveal_with_widget(qtbot)
    seen: list[tuple[str, bool]] = []
    reveal.revealed.connect(lambda n, s: seen.append((n, s)))
    with qtbot.waitSignal(reveal.revealed, timeout=2000):
        reveal.reveal_requested.emit("x", True)
    assert widget.width() == 200
    assert seen == [("x", True)]


def test_reveal_unknown_name_ignored(qtbot):
    """UT-GUI-018.006.M02.T02: Unknown name is ignored."""
    reveal, _ = _reveal_with_widget(qtbot)
    with qtbot.assertNotEmitted(reveal.revealed, wait=300):
        reveal.reveal_requested.emit("nope", True)


def test_reveal_restart_mid_animation(qtbot):
    """UT-GUI-018.006.M02.T03: Request during animation restarts from current size."""
    reveal, widget = _reveal_with_widget(qtbot)
    seen: list[bool] = []
    reveal.revealed.connect(lambda _n, s: seen.append(s))
    reveal.reveal_requested.emit("x", True)
    qtbot.wait(60)
    with qtbot.waitSignal(reveal.revealed, timeout=2000):
        reveal.reveal_requested.emit("x", False)
    assert widget.width() == 0
    assert seen[-1] is False
    assert not reveal.is_open("x")


def test_wide_page_auto_shrinks_and_restores():
    """UT-GUI-018.002.M03.T01: Wide screen auto-shrinks and restores."""
    state = _MiniState(user_mini=False)
    state.set_page(2)
    assert state.want_mini()
    state.set_page(0)
    assert not state.want_mini()


def test_auto_restore_keeps_user_choice():
    """UT-GUI-018.002.M03.T02: Auto restore keeps user's mini choice."""
    state = _MiniState(user_mini=True)
    state.set_page(2)
    state.set_page(0)
    assert state.want_mini()
