"""Tests for MD-GUI-034.053.M31 and MD-GUI-034.054.M32 (AI feed cards).
Employee names here are made up."""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from pytestqt.qtbot import QtBot

from tests.gui.test_ai_desk_trades import FRI, SAT, _Sink
from tests.gui.test_market_floor import _write_briefs
from tests.market.test_desk_trades import _seed
from us_swing.core.desk_chat import add_reply, ask_question
from us_swing.core.desk_contract import DB_NAME, DeskState, DeskStatus
from us_swing.core.desk_feed import FeedCard, feed_cards
from us_swing.core.desk_floor import DeskFloorData
from us_swing.gui.desk_control import DeskPoller
from us_swing.gui.floor_feed import CUT_CHARS, AiFeedColumn, FeedCardWidget
from us_swing.gui.floor_layouts import LayoutStore
from us_swing.gui.floor_sample import SampleFloorData
from us_swing.gui.market_floor import MarketFloorWorkspace


def _failed_run(home: Path) -> None:
    from us_swing.desk.store import DeskStore

    store = DeskStore(home)
    run = store.start_run("evening", datetime(2026, 11, 6, 21, 0, tzinfo=UTC))
    store.end_run(run, "failed", datetime(2026, 11, 6, 21, 5, tzinfo=UTC), "Web search timed out")
    ok = store.start_run("event", datetime(2026, 11, 6, 22, 0, tzinfo=UTC))
    store.end_run(ok, "ok", datetime(2026, 11, 6, 22, 1, tzinfo=UTC))
    store.close()


def _desk(home: Path) -> None:
    _seed(home, FRI, [("long", "AAA", 100.0, 95.0, "pass"), ("short", "BBB", 50.0, 52.0, "pass")])
    _write_briefs(home)
    qid = ask_question(home, "Why AAA?", datetime(2026, 11, 6, 19, 0, tzinfo=UTC))
    add_reply(home, qid, "AAA leads its sector.", True, datetime(2026, 11, 6, 19, 1, tzinfo=UTC))
    _failed_run(home)


def _column(qtbot: QtBot, cards: list[FeedCard] | None, home: Path | None = None,
            sink: _Sink | None = None) -> AiFeedColumn:
    feed = AiFeedColumn()
    qtbot.addWidget(feed)
    feed.context.home, feed.context.sink = home, sink  # type: ignore[assignment]
    feed.context.clock = lambda: SAT
    feed.set_cards(cards)
    return feed


def test_card_look(qtbot: QtBot) -> None:
    """UT-GUI-034.053.M31.T01: Ask label, ET time with IST tooltip, long text cut until More."""
    from PyQt6.QtWidgets import QLabel

    text = "word " * 80
    card = FeedCard("ask", "Lead", "Trade pick", datetime(2026, 11, 7, 14, 40, tzinfo=UTC), text)
    feed = _column(qtbot, [card])
    widget = feed.shown_cards()[0]
    assert widget.findChild(QLabel, "feed_kind").text() == "ASK"  # type: ignore[union-attr]
    when = widget.findChild(QLabel, "feed_time")
    assert when.text() == "09:40 ET" and when.toolTip().endswith("IST")  # type: ignore[union-attr]
    assert widget.text.text().endswith("…") and len(widget.text.text()) <= CUT_CHARS + 1
    widget.more_btn.click()
    assert widget.text.text() == text and widget.more_btn.text() == "Less"


def test_cards_from_desk(tmp_path: Path) -> None:
    """UT-GUI-034.054.M32.T01: briefs, picks, lead reply and failed run become cards."""
    _desk(tmp_path)
    cards = feed_cards(tmp_path, SAT)
    kinds = [c.kind for c in cards]
    assert kinds[:2] == ["ask", "ask"]
    assert {c.symbol for c in cards[:2]} == {"AAA", "BBB"} and cards[0].pick is not None
    assert kinds.count("result") == 3 and kinds.count("answer") == 1
    desk = [c for c in cards if c.kind == "desk"]
    assert len(desk) == 1 and desk[0].text == "Web search timed out"
    answer = next(c for c in cards if c.kind == "answer")
    assert answer.text == "AAA leads its sector." and answer.ref == "chat"


def test_no_desk_gives_sample(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.054.M32.T02: an empty desk gives no cards and the page shows sample cards."""
    assert feed_cards(tmp_path, SAT) == []
    data = DeskFloorData(SampleFloorData(), tmp_path)
    assert data.feed_cards(SAT) is None
    page = MarketFloorWorkspace(DeskPoller(tmp_path), data, LayoutStore(tmp_path / "l.json"))
    qtbot.addWidget(page)
    assert page.feed.shown_cards() and page.feed._sample


def test_filter_tabs(qtbot: QtBot) -> None:
    """UT-GUI-034.055.M31.T01: Asks shows its count; each tab shows only its cards."""
    cards = [FeedCard(k, "S", "x", None, k) for k in ("ask", "result", "answer", "desk")]
    feed = _column(qtbot, cards)
    assert feed.filter_btns["Asks"].text() == "Asks 1"
    assert len(feed.shown_cards()) == 4
    for name, kind in (("Asks", "ask"), ("Ideas", "result"), ("Alerts", "desk")):
        feed.filter_btns[name].click()
        assert [w.card.kind for w in feed.shown_cards()] == [kind]


def test_approve_and_reject(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.056.M31.T01: Approve sends the pick; Reject records; both emit decided."""
    _seed(tmp_path, FRI, [("long", "AAA", 100.0, 95.0, "pass"),
                          ("short", "BBB", 50.0, 52.0, "pass")])
    sink = _Sink()
    feed = _column(qtbot, feed_cards(tmp_path, SAT), tmp_path, sink)
    by_symbol = {w.card.symbol: w for w in feed.shown_cards() if w.card.ref == "pick"}
    with qtbot.waitSignal(feed.decided):
        by_symbol["AAA"].approve_btn.click()  # type: ignore[union-attr]
    with qtbot.waitSignal(feed.decided):
        by_symbol["BBB"].reject_btn.click()  # type: ignore[union-attr]
    assert sink.sent == ["AAA"]
    con = sqlite3.connect(tmp_path / DB_NAME)
    rows = con.execute("SELECT subject, decision FROM approvals WHERE kind = 'trade'").fetchall()
    con.close()
    assert sorted(rows) == [(f"{FRI}:long:AAA", "approve"), (f"{FRI}:short:BBB", "reject")]
    assert [c.symbol for c in feed_cards(tmp_path, SAT) if c.kind == "ask"] == []


def test_rebuild_inside_click(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.056.M31.T01: a rebuild run straight from Approve does not break the feed."""
    _seed(tmp_path, FRI, [("long", "AAA", 100.0, 95.0, "pass")])
    feed = _column(qtbot, feed_cards(tmp_path, SAT), tmp_path, _Sink())
    feed.decided.connect(lambda: feed.set_cards(feed_cards(tmp_path, SAT)))
    card = next(w for w in feed.shown_cards() if w.card.ref == "pick")
    card.approve_btn.click()  # type: ignore[union-attr]
    qtbot.wait(20)
    assert feed.shown_cards() == [] and feed.filter_btns["Asks"].text() == "Asks"


def test_open_buttons(qtbot: QtBot) -> None:
    """UT-GUI-034.056.M31.T02: Open in Charts, Open Hiring and Open chat emit their targets."""
    from PyQt6.QtWidgets import QPushButton

    cards = [FeedCard("ask", "Lead", "x", None, "t", "AAA", "pick"),
             FeedCard("ask", "Hiring", "x", None, "t", ref="hire"),
             FeedCard("answer", "Lead", "x", None, "t", ref="chat")]
    feed = _column(qtbot, cards)
    charts: list[str] = []
    sections: list[str] = []
    feed.chart_requested.connect(charts.append)
    feed.section_requested.connect(sections.append)
    for widget in feed.shown_cards():
        for button in widget.findChildren(QPushButton):
            if button.text().startswith("Open"):
                button.click()
    assert charts == ["AAA"] and sections == ["Hiring", "Command"]
    pick = feed.shown_cards()[0]
    assert not pick.approve_btn.isEnabled()  # type: ignore[union-attr]


def test_live_dot_and_footer(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.057.M31.T01: the dot follows the desk state; the footer opens Command."""
    poller = DeskPoller(tmp_path)
    page = MarketFloorWorkspace(poller, SampleFloorData(), LayoutStore(tmp_path / "l.json"))
    qtbot.addWidget(page)
    poller.status_changed.emit(DeskStatus(DeskState.SLEEPING))
    assert page.feed.live_dot.property("live") is True
    poller.status_changed.emit(DeskStatus(DeskState.OFF))
    assert page.feed.live_dot.property("live") is False
    sections: list[str] = []
    page.desk_section_requested.connect(sections.append)
    page.feed.talk_btn.click()
    assert sections == ["Command"]


class _Counting(DeskFloorData):
    reads = 0

    def feed_cards(self, now: datetime | None = None) -> list[FeedCard] | None:
        type(self).reads += 1
        return super().feed_cards(now)


def test_feed_reloads(qtbot: QtBot, tmp_path: Path) -> None:
    """UT-GUI-034.058.M31.T01: the feed is read again after a decision and when shown."""
    _Counting.reads = 0
    page = MarketFloorWorkspace(DeskPoller(tmp_path), _Counting(SampleFloorData(), tmp_path),
                                LayoutStore(tmp_path / "l.json"))
    qtbot.addWidget(page)
    base = _Counting.reads
    page.feed.decided.emit()
    assert _Counting.reads == base + 1
    page.show()
    qtbot.waitExposed(page)
    assert _Counting.reads >= base + 2
    assert isinstance(page.feed.shown_cards()[0], FeedCardWidget)
