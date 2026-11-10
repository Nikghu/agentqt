"""Tests for AI Desk → Team at work (MD-GUI-035.001.M01, .006.M03, .007.M04).
Employee names are made up."""
from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from tests.gui.team_fixtures import NOW, desk
from us_swing.gui.ai_desk_team import TeamAtWork


def _page(qtbot: QtBot, home: Path) -> TeamAtWork:
    page = TeamAtWork(home, clock=lambda: NOW)
    qtbot.addWidget(page)
    page.refresh()
    return page


def test_live_tab(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-035.002.M01.T01: run bar, Right now, pipeline states and the view switch."""
    desk(tmp_path, finished=False)
    page = _page(qtbot, tmp_path)
    assert page.run_label.text().startswith("Evening run #1 · Mon 09 Nov · 16:25 ET (02:55 IST)")
    assert page.chips["calls"].text() == "LLM calls 2"
    assert page.chips["done"].text() == "Done 1 of 3"
    assert "Beta is working" in page.now_label.text()
    cards = page.pipeline._cards
    assert (cards["emp-a"].state_key, cards["emp-b"].state_key, cards["emp-c"].state_key) == (
        "done", "working", "waiting")
    assert cards["data"].state_key == "done" and not cards["emp-b"].busy.isHidden()
    assert page.live.currentIndex() == 0
    page._views.button(1).click()  # type: ignore[union-attr]
    assert page.live.currentIndex() == 1


def test_follow_live_and_wheel(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-035.008.M04.T01: Follow live picks the worker; a wheel step picks by hand."""
    desk(tmp_path, finished=False)
    page = _page(qtbot, tmp_path)
    assert page.wheel.current() == "emp-b"
    assert page.profile.name_label.text() == "Beta"
    page.wheel.step(1)
    assert page.wheel.current() == "emp-c"
    assert page.profile.name_label.text() == "Gamma"
    assert not page.follow_btn.isChecked()
    assert page.team_label.text() == "Team · 3 of 4"


def test_event_log(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-035.006.M03.T01: events with their calls; Problems filter; a call picks."""
    desk(tmp_path, finished=True)
    page = _page(qtbot, tmp_path)
    page._tabs.button(1).click()  # type: ignore[union-attr]
    tree = page.log.tree
    names = [tree.topLevelItem(i).text(1) for i in range(tree.topLevelItemCount())]  # type: ignore[union-attr]
    assert names == ["Evening run", "Chat question"]
    evening = tree.topLevelItem(0)
    assert evening is not None and evening.childCount() == 3
    assert evening.child(1).text(5) == "answer missing a field"  # type: ignore[union-attr]
    first = evening.child(0)
    assert first is not None
    page.log._on_click(first, 0)
    assert page.profile.name_label.text() == "Alpha"
    page.log.set_filter("Problems")
    assert tree.topLevelItemCount() == 1


def test_scorecard_tab(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-035.007.M04.T01: one row per employee plus the total; a row click picks."""
    desk(tmp_path, finished=True)
    page = _page(qtbot, tmp_path)
    page._tabs.button(2).click()  # type: ignore[union-attr]
    table = page.scores
    assert table.rowCount() == 5
    assert table.item(4, 0).text() == "Team total"  # type: ignore[union-attr]
    assert table.item(1, 4).text() == "50%"  # type: ignore[union-attr]
    assert table.item(1, 6).text() == "50%"  # type: ignore[union-attr]
    table._on_click(3, 0)
    assert page.profile.name_label.text() == "Delta"
    assert page.wheel.current() == "emp-d"


def test_empty_desk(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-035.009.M01.T01: no desk data: the page opens with plain notes."""
    page = _page(qtbot, tmp_path)
    assert page.run_label.text() == "No desk run yet"
    assert "has not run yet" in page.now_label.text()
    for tab in (1, 2, 0):
        page._tabs.button(tab).click()  # type: ignore[union-attr]
    assert page.log.empty.isVisibleTo(page.log)


def test_log_strip_days_and_filters(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-035.006.M03.T02: day strip picks an event; filters; paging to the day before."""
    desk(tmp_path, finished=True)
    page = _page(qtbot, tmp_path)
    page.resize(1400, 900)
    page._tabs.button(1).click()  # type: ignore[union-attr]
    log = page.log
    log.strip.resize(1000, 64)
    log.strip.grab()
    chat = next(e for e in log._events if e.kind == "chat_question")
    x = log.strip._x(chat.created)
    assert log.strip._hit(x) is chat and log.strip._hit(-50) is None
    log.open_event(chat.id)
    current = log.tree.currentItem()
    assert current is not None and current.text(1) == "Chat question" and current.isExpanded()
    log.set_filter("Urgent")
    assert log.tree.topLevelItemCount() == 1
    log.set_filter("With AI work")
    assert log.tree.topLevelItemCount() == 2
    with qtbot.waitSignal(log.day_changed) as moved:
        log.prev_btn.click()
    assert str(moved.args[0]) == "2026-11-08"
    assert log.day.isoformat() == "2026-11-08"
    assert log.empty.isVisibleTo(log) and log.next_btn.isEnabled()


def test_wheel_inputs_and_peek(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-035.008.M04.T02: wheel keys, scroll and paint; Prompt and Answer show text."""
    from PyQt6.QtCore import QPoint, QPointF, Qt
    from PyQt6.QtGui import QWheelEvent

    desk(tmp_path, finished=False)
    page = _page(qtbot, tmp_path)
    wheel = page.wheel
    wheel.resize(320, 260)
    wheel.grab()
    qtbot.keyClick(wheel, Qt.Key.Key_Up)
    assert wheel.current() == "emp-a"
    scroll = QWheelEvent(QPointF(10, 10), QPointF(10, 10), QPoint(0, 0), QPoint(0, -120),
                         Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                         Qt.ScrollPhase.NoScrollPhase, False)
    wheel.wheelEvent(scroll)
    assert wheel.current() == "emp-b"
    qtbot.mouseClick(wheel, Qt.MouseButton.LeftButton, pos=QPoint(100, 130 + 52))
    assert wheel.current() == "emp-c"
    page.select_member("emp-b")
    page.profile.prompt_btn.click()
    assert page.profile.peek.toPlainText() == "the prompt"
    page.profile.answer_btn.click()
    assert not page.profile.prompt_btn.isChecked()
    assert page.profile.peek.toPlainText() == "answer missing a field"
    page.select_member("emp-c")
    assert page.profile.peek.toPlainText() == "No call in this run"
    page.profile.answer_btn.click()
    assert page.profile.peek.isHidden()
    page.timeline.resize(900, 300)
    page.timeline.grab()
    page.pipeline.grab()


def test_alert_banner_and_feed(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-035.010.M01.T01: an open alert shows as a banner and an AI feed card."""
    from us_swing.core.desk_alerts import raise_alert
    from us_swing.core.desk_feed import feed_cards

    desk(tmp_path, finished=True)
    page = _page(qtbot, tmp_path)
    assert page.alert_banner.isHidden()
    raise_alert(tmp_path, "run_failed", "", 1, "Run 1: 3 LLM call(s), none valid", NOW,
                lambda _text: False)
    page.refresh()
    assert not page.alert_banner.isHidden()
    assert "No employee gave a valid answer" in page.alert_banner.text()
    cards = [c for c in feed_cards(tmp_path, NOW) if c.subject == "No employee gave a valid answer"]
    assert len(cards) == 1 and "What to do:" in cards[0].text
