"""Tests for the sidebar workspace shell (FO-GUI-018)."""
from __future__ import annotations

import datetime
from types import SimpleNamespace

import pytest
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QMessageBox, QWidget

from us_swing.data.market_calendar import ET
from us_swing.data.models import ConnectionStatus
from us_swing.gui.main_window import _MiniState
from us_swing.gui.reveal import RevealController
from us_swing.gui.sidebar import Sidebar, market_text
from us_swing.gui.theme import active_palette

_ITEMS = [("layout-dashboard", "Dashboard"), ("filter", "Screener"), ("zap", "Execution"),
          ("chart-candlestick", "Chart"), ("settings", "Settings")]


class _StubService(QObject):
    viewing_changed = pyqtSignal()
    positions_updated = pyqtSignal()
    account_updated = pyqtSignal()
    feed_status_changed = pyqtSignal(str)
    internet_status_changed = pyqtSignal(bool)
    market_status_updated = pyqtSignal()

    def __init__(self, viewing: int | None = None) -> None:
        super().__init__()
        self.viewing = viewing
        self.connection_status = ConnectionStatus.DISCONNECTED
        self.online = True
        self.calls: list[str] = []
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

    def is_internet_online(self) -> bool:
        return self.online

    def get_system_config(self) -> SimpleNamespace:
        return SimpleNamespace(ibkr_host="127.0.0.1", ibkr_port=7497)

    def connect_feed(self) -> None:
        self.calls.append("connect")

    def disconnect_feed(self) -> None:
        self.calls.append("disconnect")

    def set_feed(self, status: ConnectionStatus, online: bool = True) -> None:
        self.connection_status = status
        self.online = online
        self.feed_status_changed.emit(status.value)


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


def test_connections_live_rows(sidebar):
    """UT-GUI-018.008.M04.T01: Live rows."""
    sidebar._footer._svc.set_feed(ConnectionStatus.CONNECTED)
    conn = sidebar._conn
    assert conn._net_val.text() == "Online"
    assert "Live" in conn._feed_val.text()
    assert conn._feed_sub.text() == "127.0.0.1:7497"
    assert conn._power.toolTip() == "Disconnect"


def test_connections_offline_rows(sidebar):
    """UT-GUI-018.008.M04.T02: Offline rows."""
    sidebar._footer._svc.set_feed(ConnectionStatus.DISCONNECTED, online=False)
    conn = sidebar._conn
    assert conn._net_val.text() == "Offline"
    assert "Not connected" in conn._feed_val.text()
    assert conn._power.toolTip() == "Connect"


def test_power_button_connects_and_disconnects(sidebar, monkeypatch):
    """UT-GUI-018.008.M04.T03: Power button connects and disconnects."""
    svc = sidebar._footer._svc
    monkeypatch.setattr(
        QMessageBox, "question", lambda *_a, **_k: QMessageBox.StandardButton.Yes
    )
    sidebar._conn._power.click()
    svc.set_feed(ConnectionStatus.CONNECTED)
    sidebar._conn._power.click()
    assert svc.calls == ["connect", "disconnect"]


def test_power_button_off_during_probe(sidebar):
    """UT-GUI-018.008.M04.T04: Button off during probe."""
    sidebar._footer._svc.set_feed(ConnectionStatus.RECONNECTING)
    assert not sidebar._conn._power.isEnabled()
    assert "Connecting…" in sidebar._conn._feed_val.text()


def test_retry_shows_attempt_and_countdown(sidebar):
    """UT-GUI-018.009.M04.T01: Retry shows attempt and countdown."""
    conn = sidebar._conn
    sidebar.set_feed_retry(3, 10, 45_000)
    assert "Attempt 3 of 10" in conn._feed_val.text()
    assert conn._feed_sub.text() == "Next try in 45 s"
    assert conn._power.toolTip() == "Try now"
    sidebar.clear_feed_retry()
    assert "Not connected" in conn._feed_val.text()
    assert not conn._retry_timer.isActive()


def test_market_open_counts_to_close():
    """UT-GUI-018.010.M04.T01: Open market counts to close."""
    now = datetime.datetime(2026, 10, 21, 13, 46, tzinfo=ET)
    assert market_text(now) == ("open", "Open", "closes in 2h 14m")


def test_market_skips_weekend_and_holiday():
    """UT-GUI-018.010.M04.T02: Weekend and holiday skipped."""
    friday = datetime.datetime(2026, 10, 23, 17, 0, tzinfo=ET)
    assert market_text(friday) == ("after_hours", "After hours", "opens in 2d 16h")
    before_thanksgiving = datetime.datetime(2026, 11, 25, 20, 30, tzinfo=ET)
    assert market_text(before_thanksgiving)[2] == "opens in 1d 13h"
    before_dst_end = datetime.datetime(2026, 10, 30, 17, 0, tzinfo=ET)
    assert market_text(before_dst_end)[2] == "opens in 2d 17h"


def test_mini_shows_plug_with_worst_status(sidebar):
    """UT-GUI-018.011.M04.T01: Mini shows plug with worst status."""
    sidebar._footer._svc.set_feed(ConnectionStatus.DISCONNECTED, online=False)
    sidebar.set_mini(True)
    conn = sidebar._conn
    assert conn._full.isHidden()
    assert not conn._plug.isHidden()
    assert conn._badge.property("colour") == active_palette().RED
    tip = conn._plug.toolTip().splitlines()
    assert [line.split(":")[0] for line in tip] == ["Internet", "IBKR Feed", "Market"]
