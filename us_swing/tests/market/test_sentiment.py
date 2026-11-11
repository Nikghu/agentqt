"""Tests for sentiment research (FO-MKT-017, Autonomous desk step F skill 3)."""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from tests.market.p5b_support import Env, FakeCtx
from tests.market.test_lead_brief import _stage
from us_swing.core.desk_research import StepResult, Ticket
from us_swing.core.desk_steps import DEFAULT_EMPLOYEE_PACKAGES, SKILL_PATHS
from us_swing.core.desk_watch import OpenTrade, write_open_trades
from us_swing.data.market_calendar import ET
from us_swing.desk.registry import default_folders, load_employee
from us_swing.market.sentiment import Card, SentimentJudge, SentimentSkill, StockChoice
from us_swing.market.sentiment_cards import CardRow, cards_block, save_cards
from us_swing.market.sentiment_news import Gathered, gather_news
from us_swing.market.store import MarketStore, NewsItemRow

NOW = datetime(2026, 11, 11, 12, 0, tzinfo=ET)
UTC_NOW = NOW.astimezone(UTC)
A, B, C = "long|AAA", "short|BBB", "long|CCC"


def _idea(home: Path, day: str, side: str, sym: str, status: str) -> None:
    con = sqlite3.connect(home / "desk.db")
    with con:
        con.execute("INSERT INTO ideas VALUES (?, ?, ?, ?, 1, 64, 'Tech', 'Pullback', 100, 98)",
                    (day, side, sym, status))
    con.close()


@pytest.fixture
def home(tmp_path: Path) -> Path:
    MarketStore(tmp_path).close()
    _idea(tmp_path, "2026-11-10", "long", "AAA", "list")
    _idea(tmp_path, "2026-11-10", "short", "BBB", "watch")
    _idea(tmp_path, "2026-11-10", "long", "NON", "none")
    _idea(tmp_path, "2026-11-09", "long", "OLD", "list")
    write_open_trades(tmp_path, [OpenTrade("CCC", "long", 50, 48, None, "Swing")], NOW)
    return tmp_path


def _ticket(state: dict[str, Any] | None = None) -> Ticket:
    return Ticket(
        id=11, kind="sentiment", topic="Watch ideas news", goal="Check news on watch ideas",
        done_test="Every chosen stock has a tone", token_cap=8_000, step_cap=8,
        time_cap_min=60, raised_by="l-1", raised_by_name="Lead A", status="running",
        made="2026-11-11T09:00:00-05:00", approved_by="auto", approved=None, started=None,
        ended=None, tokens=0, steps=0, biggest=0, quiet_steps=0, last_call="",
        state=json.dumps(state or {}), result="", end_reason="", gain=None, updated=None)


def _fake_gather(home: Path, stocks: Any, labels: Any) -> Gathered:
    return Gathered([f"{s} (x): 2026-11-10 Some headline" for s in stocks],
                    {s: 1 for s in stocks}, 1)


def _skill() -> SentimentSkill:
    return SentimentSkill(lambda: NOW, _fake_gather)


def _judge_state(stocks: list[str] | None = None) -> dict[str, Any]:
    stocks = stocks or [A, B]
    return {"phase": "judge", "stocks": stocks, "records": [f"{s}: x" for s in stocks],
            "counts": {s: 2 for s in stocks}}


def _judge(*cards: tuple[str, str]) -> SentimentJudge:
    return SentimentJudge(cards=[Card(stock=s, tone=t, reason="From the headlines")  # type: ignore[arg-type]
                                 for s, t in cards], summary="One stock has bad news.")


def _cards(home: Path) -> list[Any]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute("SELECT side, symbol, tone, headlines, ticket_id FROM "
                           "sentiment_cards ORDER BY id").fetchall()
    finally:
        con.close()


def _run(ctx: FakeCtx, skill: SentimentSkill) -> list[StepResult]:
    out: list[StepResult] = []
    state: dict[str, Any] = {}
    for answer in (StockChoice(stocks=[A, B]), None, _judge((A, "against"), (B, "neutral"))):
        ctx.answer = answer
        res = skill.step(ctx, _ticket(state))
        assert res is not None
        out.append(res)
        state = res.state or state
    return out


# ---------------- steps and pick ----------------

def test_three_steps(home: Path) -> None:
    """UT-MKT-017.001.M01.T01: Pick, gather and judge end the ticket done."""
    steps = _run(FakeCtx(home, None), _skill())
    assert [s.call for s in steps] == ["pick", "gather", "judge"]
    assert [s.outcome for s in steps] == ["go", "go", "done"]


def test_no_answer(home: Path) -> None:
    """UT-MKT-017.001.M01.T02: No pick answer gives an empty note and outcome go."""
    res = _skill().step(FakeCtx(home, None), _ticket())
    assert res is not None and res.note == "" and res.outcome == "go"


def test_pick_list(home: Path) -> None:
    """UT-MKT-017.002.M01.T01: Listed and watch ideas of the latest day and open trades."""
    ctx = FakeCtx(home, None)
    _skill().step(ctx, _ticket())
    text = ctx.asked[0]
    assert "long|AAA: list idea" in text and "short|BBB: watch idea" in text
    assert "long|CCC: open trade, Swing" in text
    assert "NON" not in text and "OLD" not in text


def test_too_many() -> None:
    """UT-MKT-017.002.M01.T02: 31 stocks is not a valid answer."""
    with pytest.raises(ValidationError):
        StockChoice(stocks=[f"long|S{i}" for i in range(31)])


def test_unknown_dropped(home: Path) -> None:
    """UT-MKT-017.003.M01.T01: Only known stocks are kept."""
    res = _skill().step(FakeCtx(home, StockChoice(stocks=[A, "long|ZZZ"])), _ticket())
    assert res is not None and res.state["stocks"] == [A]


def test_nothing_left(home: Path, tmp_path_factory: pytest.TempPathFactory) -> None:
    """UT-MKT-017.003.M01.T02: Only unknown stocks, or nothing to choose, fails."""
    res = _skill().step(FakeCtx(home, StockChoice(stocks=["long|ZZZ"])), _ticket())
    assert res is not None and res.outcome == "failed"
    empty = tmp_path_factory.mktemp("empty")
    res = _skill().step(FakeCtx(empty, StockChoice(stocks=[A])), _ticket())
    assert res is not None and res.outcome == "failed"


# ---------------- headlines ----------------

def _news(home: Path, sym: str, age: timedelta, title: str) -> None:
    when = (UTC_NOW - age).isoformat(timespec="seconds")
    store = MarketStore(home)
    store.add_news([NewsItemRow("2026-11-10", sym, "Yahoo Finance", when, title, None, when)])
    store.close()


def _rss(*titles: str) -> str:
    items = "".join(f"<item><title>{t}</title><link>https://x/{i}</link>"
                    f"<pubDate>Wed, 11 Nov 2026 1{i}:00:00 GMT</pubDate></item>"
                    for i, t in enumerate(titles))
    return f"<?xml version='1.0'?><rss version='2.0'><channel>{items}</channel></rss>"


def test_stored_first(home: Path) -> None:
    """UT-MKT-017.004.M02.T01: A headline from yesterday means no fetch."""
    _news(home, "AAA", timedelta(days=1), "AAA wins a contract")
    calls: list[str] = []
    got = gather_news(home, [A], {A: "list idea"}, UTC_NOW, lambda url: calls.append(url) or "")
    assert calls == [] and got.fetched == 0
    assert "AAA wins a contract" in got.records[0] and got.counts[A] == 1


def test_gap_fetched(home: Path) -> None:
    """UT-MKT-017.004.M02.T02: Only an old headline means one fetch, stored for later."""
    _news(home, "AAA", timedelta(days=5), "Old story")
    calls: list[str] = []

    def get(url: str) -> str:
        calls.append(url)
        return _rss("AAA beats estimates", "AAA raises guidance")

    got = gather_news(home, [A], {}, UTC_NOW, get)
    assert len(calls) == 1 and got.fetched == 1 and got.counts[A] == 3
    store = MarketStore(home)
    try:
        assert len(store.read_frame("SELECT * FROM news_items WHERE symbol = 'AAA'")) == 3
    finally:
        store.close()


def test_headline_limits(home: Path) -> None:
    """UT-MKT-017.004.M02.T03: 5 newest shown, 9-day-old left out, no fetch after budget."""
    for i in range(8):
        _news(home, "AAA", timedelta(hours=i + 1), f"Story {i}")
    _news(home, "BBB", timedelta(days=9), "Very old")
    ticks = iter([0.0, 100.0])
    calls: list[str] = []
    got = gather_news(home, [A, B], {}, UTC_NOW, lambda url: calls.append(url) or "",
                      lambda: next(ticks, 100.0))
    assert got.counts[A] == 5 and "Story 0" in got.records[0] and "Story 7" not in got.records[0]
    assert calls == [] and got.records[1].endswith("no news")


def test_feed_fails(home: Path) -> None:
    """UT-MKT-017.004.M02.T04: A failed feed leaves the stock with no news."""
    def get(url: str) -> str:
        raise OSError("timed out")

    got = gather_news(home, [C], {}, UTC_NOW, get)
    assert got.records == [f"{C} (stock): no news"] and got.fetched == 0


# ---------------- judge and cards ----------------

def test_answer_limits() -> None:
    """UT-MKT-017.005.M01.T01: An unknown tone or a long reason is not valid."""
    with pytest.raises(ValidationError):
        Card(stock=A, tone="bullish", reason="ok ok")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        Card(stock=A, tone="neutral", reason="x" * 151)


def test_all_tones(home: Path) -> None:
    """UT-MKT-017.005.M01.T02: All four tones are kept."""
    stocks = [A, B, C, "long|DDD"]
    reply = _judge((A, "supports"), (B, "neutral"), (C, "against"), ("long|DDD", "none"))
    _skill().step(FakeCtx(home, reply), _ticket(_judge_state(stocks)))
    assert [r[2] for r in _cards(home)] == ["supports", "neutral", "against", "none"]


def test_cards_saved(home: Path) -> None:
    """UT-MKT-017.006.M03.T01: Each judged stock gets a card with count and ticket id."""
    _skill().step(FakeCtx(home, _judge((A, "against"), (B, "neutral"))),
                  _ticket(_judge_state()))
    assert _cards(home) == [("long", "AAA", "against", 2, 11), ("short", "BBB", "neutral", 2, 11)]


def test_unknown_card_and_scores(home: Path) -> None:
    """UT-MKT-017.006.M03.T02: A card for an unchosen stock is dropped; news tags unchanged."""
    con = sqlite3.connect(home / "desk.db")
    with con:
        con.execute("INSERT INTO news_tags (date, side, symbol, tone, final_score) VALUES "
                    "('2026-11-10', 'long', 'AAA', 'positive', 70)")
    con.close()
    _skill().step(FakeCtx(home, _judge((A, "against"), ("long|ZZZ", "against"))),
                  _ticket(_judge_state([A])))
    assert [r[1] for r in _cards(home)] == ["AAA"]
    con = sqlite3.connect(home / "desk.db")
    assert con.execute("SELECT tone, final_score FROM news_tags").fetchall() == [("positive", 70)]
    con.close()


def test_lead_sees_cards(p5b: Env) -> None:
    """UT-MKT-017.007.M03.T01: The lead's facts show a 2-day-old card for a passed idea."""
    skill = _stage(p5b)
    day = (datetime.fromisoformat(p5b.day) - timedelta(days=2)).date().isoformat()
    save_cards(p5b.home, day, 5, [CardRow("long", "LNG01", "against", "Recall news", 3)], day)
    text = skill.facts(p5b.home).text
    assert f"long LNG01: against, Recall news ({day}, 3 headlines)" in text


def test_card_limits(tmp_path: Path) -> None:
    """UT-MKT-017.007.M03.T02: Old cards left out, newest per stock only, 30 lines at most."""
    save_cards(tmp_path, "2026-11-01", 1, [CardRow("long", "AAA", "against", "old", 1)], "x")
    save_cards(tmp_path, "2026-11-08", 2, [CardRow("long", "BBB", "neutral", "first", 1)], "x")
    save_cards(tmp_path, "2026-11-10", 3, [CardRow("long", "BBB", "supports", "newer", 1)], "x")
    block = cards_block(tmp_path, [("long", "AAA"), ("long", "BBB")], "2026-11-11")
    assert "AAA" not in block and "newer" in block and "first" not in block
    weekend = cards_block(tmp_path, [("long", "BBB")], "2026-11-06")
    assert "newer" in weekend
    assert cards_block(tmp_path, [("long", "BBB")], "not a day") == ""
    save_cards(tmp_path, "2026-11-10", 4, [CardRow("long", f"S{i:02d}", "none", "n", 0)
                                           for i in range(35)], "x")
    block = cards_block(tmp_path, [("long", f"S{i:02d}") for i in range(35)], "2026-11-11")
    assert len(block.splitlines()) == 31


def test_no_cards(tmp_path: Path, p5b: Env) -> None:
    """UT-MKT-017.007.M03.T03: No table or no matching card gives an empty block."""
    assert cards_block(tmp_path, [("long", "AAA")], "2026-11-11") == ""
    skill = _stage(p5b)
    before = skill.facts(p5b.home).text
    save_cards(p5b.home, p5b.day, 5, [CardRow("long", "NOTANIDEA", "against", "x", 1)], "x")
    assert skill.facts(p5b.home).text == before


def test_gain_yes(home: Path) -> None:
    """UT-MKT-017.008.M01.T01: One card against makes the gain yes; result lists tones."""
    res = _skill().step(FakeCtx(home, _judge((A, "against"), (B, "supports"))),
                        _ticket(_judge_state()))
    assert res is not None and res.gain is True and res.outcome == "done"
    assert "Summary: One stock has bad news." in res.note
    assert f"{A}: against, From the headlines" in res.note


def test_gain_no(home: Path) -> None:
    """UT-MKT-017.008.M01.T02: Supports and neutral only make the gain no; still done."""
    res = _skill().step(FakeCtx(home, _judge((A, "supports"), (B, "neutral"))),
                        _ticket(_judge_state()))
    assert res is not None and res.gain is False and res.outcome == "done"


# ---------------- employee and logs ----------------

def test_default_employee() -> None:
    """UT-MKT-017.009.M01.T01: emp-015 ships with skill sentiment and a loadable path."""
    folders = {f.name: f for f in default_folders(DEFAULT_EMPLOYEE_PACKAGES)}
    hire = load_employee(folders["emp-015"], SKILL_PATHS)
    assert hire is not None
    assert (hire.spec.level, hire.spec.skill, hire.spec.trigger) == (
        "expert", "sentiment", ("research_done",))
    assert isinstance(hire.skill, SentimentSkill)


def test_never_wakes(tmp_path: Path) -> None:
    """UT-MKT-017.009.M01.T02: Events never wake the sentiment employee."""
    skill = _skill()
    facts = skill.facts(tmp_path)
    assert not facts.fresh and skill.act(FakeCtx(tmp_path, None), facts) == []


def test_logs(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-017.010.M01.T01: Steps log stock count, fetched count and against count."""
    caplog.set_level(logging.INFO, logger="us_swing.market.sentiment")
    _run(FakeCtx(home, None), _skill())
    assert "[Research] Ticket 11 will judge 2 stock(s)" in caplog.text
    assert "[Research] Ticket 11 gathered 2 headline(s), 1 stock(s) fetched" in caplog.text
    assert "[Research] Ticket 11 judged 2 stock(s), 1 against their side" in caplog.text
