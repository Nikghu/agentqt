"""Tests for MD-MKT-006.005.M04 — market/news_review.py (news review skill)."""
from __future__ import annotations

import logging
from datetime import date

import pytest
from pydantic import ValidationError

from tests.market.p5b_support import Env, FakeCtx, Idea, execute, listed, query, set_ideas
from us_swing.core import econ_calendar
from us_swing.core.desk_agents import Facts
from us_swing.market import news_review
from us_swing.market.news_review import NewsReview, NewsReviewSkill, news_points
from us_swing.market.store import MarketStore, NewsItemRow, NewsTagRow

NOTE = "CPI is due next week; headlines are mostly calm and about earnings."
IDEAS: list[Idea] = listed("long", "LNG", 2) + listed("short", "SHT", 1)
ONE_SCORE_70: list[Idea] = [("long", "LNG10", "list", 10, "Tech", 50.0, 47.0)]


def _tag(symbol: str, tone: str = "positive", side: str = "long") -> dict[str, str]:
    return {"side": side, "symbol": symbol, "tone": tone, "reason": "Plain reason here"}


def _review(*tags: dict[str, str], market: str = NOTE) -> NewsReview:
    return NewsReview.model_validate({"tags": list(tags), "market": market})


def _news(env: Env, rows: list[tuple[str, str, str]], day: str = "") -> None:
    """Add headlines (symbol, title, published) for the ideas day."""
    store = MarketStore(env.home)
    store.add_news([NewsItemRow(day or env.day, s, "Src", p, t, f"https://x/{i}", p)
                    for i, (s, t, p) in enumerate(rows)])
    store.close()


def _stage(env: Env, ideas: list[Idea] = IDEAS) -> NewsReviewSkill:
    set_ideas(env, ideas)
    _news(env, [("LNG01", "Alpha raises guidance", "2026-11-05T14:00:00+00:00"),
                ("", "Stocks drift higher", "2026-11-05T15:00:00+00:00")])
    return NewsReviewSkill(env.candles)


def _move_day(env: Env, day: str) -> None:
    for table in ("ideas", "stock_score"):
        execute(env.home, f"UPDATE {table} SET date = ? WHERE date = ?",  # noqa: S608
                (day, env.day))


def _tags(env: Env) -> dict[str, tuple[str, float, float]]:
    return {r[0]: (r[1], r[2], r[3]) for r in query(
        env.home, "SELECT symbol, tone, points, final_score FROM news_tags")}


def test_facts_hold_news(p5b: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-MKT-006.005.M04.T01: facts hold ideas, headlines, market lines and events; fresh."""
    monkeypatch.setattr(news_review, "events_between", lambda a, b: econ_calendar.events_between(
        date(2026, 11, 9), date(2026, 11, 13)))
    facts = _stage(p5b).facts(p5b.home)
    assert facts.fresh and facts.data_day == p5b.day
    for part in ("LNG01", "SHT01", "Alpha raises guidance", "Stocks drift higher",
                 "CPI inflation report", "2026-11-05"):
        assert part in facts.text


def test_stale_news(p5b: Env) -> None:
    """UT-MKT-006.005.M04.T02: news older than the ideas day is stale and both days are named."""
    set_ideas(p5b, IDEAS)
    _news(p5b, [("LNG01", "Old story", "2020-01-02T10:00:00+00:00")], day="2020-01-02")
    facts = NewsReviewSkill(p5b.candles).facts(p5b.home)
    assert not facts.fresh
    assert "2020-01-02" in facts.why_stale and p5b.day in facts.why_stale


def test_no_stock_headlines(p5b: Env) -> None:
    """UT-MKT-006.005.M04.T03: ideas but no stock headlines are fresh; facts say no headlines."""
    set_ideas(p5b, IDEAS)
    _news(p5b, [("", "Market only", "2026-11-05T15:00:00+00:00")])
    facts = NewsReviewSkill(p5b.candles).facts(p5b.home)
    assert facts.fresh
    assert "(no headlines)" in facts.text and "no headlines for any idea" in facts.text


def test_valid_answer() -> None:
    """UT-MKT-006.006.M04.T01: two tags and a 200-character note make a NewsReview."""
    review = _review(_tag("LNG01"), _tag("SHT01", "negative", "short"), market="n" * 200)
    assert isinstance(review, NewsReview) and len(review.tags) == 2


def test_bad_answer_refused() -> None:
    """UT-MKT-006.006.M04.T02: tone great, a 130-character reason and a 500-character note fail."""
    with pytest.raises(ValidationError):
        _review(_tag("LNG01", "great"))
    with pytest.raises(ValidationError):
        _review({**_tag("LNG01"), "reason": "r" * 130})
    with pytest.raises(ValidationError):
        _review(_tag("LNG01"), market="n" * 500)


def test_unknown_or_repeated_idea(p5b: Env, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-006.006.M04.T03: an unlisted stock and a repeated tag are dropped; one log line."""
    skill = _stage(p5b)
    answer = _review(_tag("ZZZ"), _tag("LNG01", "positive"), _tag("LNG01", "negative"))
    with caplog.at_level(logging.INFO):
        skill.act(FakeCtx(p5b.home, answer), skill.facts(p5b.home))
    assert _tags(p5b)["LNG01"][0] == "positive" and "ZZZ" not in _tags(p5b)
    lines = [r for r in caplog.records if "News review named" in r.getMessage()]
    assert len(lines) == 1 and "2 stock(s)" in lines[0].getMessage()


def test_points_table() -> None:
    """UT-MKT-006.007.M04.T01: with no event next day the points are 10, 6, 6 and 2."""
    day = date(2026, 11, 12)
    assert [news_points(t, day) for t in ("positive", "neutral", "none", "negative")] == [
        10.0, 6.0, 6.0, 2.0]


def test_high_event_next_day() -> None:
    """UT-MKT-006.007.M04.T02: the day before CPI takes 3 points off, never below 0."""
    day = date(2026, 11, 9)
    assert news_points("positive", day) == 7.0
    assert news_points("negative", day) == 0.0


def test_medium_event_only() -> None:
    """UT-MKT-006.007.M04.T03: the day before PCE and GDP changes nothing."""
    assert news_points("neutral", date(2026, 11, 24)) == 6.0
    assert news_points("positive", date(2026, 11, 24)) == 10.0


def test_final_score_stored(p5b: Env) -> None:
    """UT-MKT-006.008.M04.T01: score 70 with a positive tone stores final 73.0; ideas unchanged."""
    skill = _stage(p5b, ONE_SCORE_70)
    before = query(p5b.home, "SELECT * FROM ideas ORDER BY symbol")
    skill.act(FakeCtx(p5b.home, _review(_tag("LNG10"))), skill.facts(p5b.home))
    assert _tags(p5b)["LNG10"] == ("positive", 10.0, 73.0)
    assert query(p5b.home, "SELECT * FROM ideas ORDER BY symbol") == before


def test_no_answer_keeps_code_rows(p5b: Env) -> None:
    """UT-MKT-006.008.M04.T02: no answer the day before CPI: tone none, points 3, no feed item."""
    skill = _stage(p5b, ONE_SCORE_70)
    _move_day(p5b, "2026-11-09")
    items = skill.act(FakeCtx(p5b.home, None), Facts("", "2026-11-09", True))
    assert items == []
    assert query(p5b.home, "SELECT date, tone, points, final_score FROM news_tags") == [
        ("2026-11-09", "none", 3.0, 66.0)]


def test_rerun_replaces(p5b: Env) -> None:
    """UT-MKT-006.008.M05.T01: writing the tags twice for one day leaves one set of rows."""
    skill = _stage(p5b)
    ctx = FakeCtx(p5b.home, _review(_tag("LNG01")))
    skill.act(ctx, skill.facts(p5b.home))
    skill.act(ctx, skill.facts(p5b.home))
    assert len(query(p5b.home, "SELECT * FROM news_tags")) == 3
    store = MarketStore(p5b.home)
    row = NewsTagRow(p5b.day, "long", "LNG01", "neutral", "Reason", 6.0, 70.0)
    store.replace_day("news_tags", p5b.day, [row])
    store.replace_day("news_tags", p5b.day, [row])
    store.close()
    assert len(query(p5b.home, "SELECT * FROM news_tags")) == 1


def test_market_note_in_feed(p5b: Env) -> None:
    """UT-MKT-006.009.M04.T01: a valid answer gives one info feed item with the market note."""
    skill = _stage(p5b)
    items = skill.act(FakeCtx(p5b.home, _review(_tag("LNG01"))), skill.facts(p5b.home))
    assert [(i.kind, i.text, i.data_day) for i in items] == [("info", NOTE, p5b.day)]


def test_no_note_without_answer(p5b: Env) -> None:
    """UT-MKT-006.009.M04.T02: no answer gives no feed item."""
    skill = _stage(p5b)
    assert skill.act(FakeCtx(p5b.home, None), skill.facts(p5b.home)) == []


def test_earlier_tags_kept(p5b: Env) -> None:
    """UT-MKT-006.008.M04.T03: a failed second ask leaves the earlier real tags of the day."""
    skill = _stage(p5b)
    skill.act(FakeCtx(p5b.home, _review(_tag("LNG01", "negative"))), skill.facts(p5b.home))
    skill.act(FakeCtx(p5b.home, None), skill.facts(p5b.home))
    tags = _tags(p5b)
    assert tags["LNG01"][0] == "negative" and tags["LNG02"][0] == "none"
    assert len(tags) == 3
