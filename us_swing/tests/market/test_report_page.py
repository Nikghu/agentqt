"""Tests for MD-MKT-007.001.M02 — market/report_page.py and MD-MKT-007.004.M03 (``canvas_pages``).

Employee names here are made up: no skill may depend on who uses it.
"""
from __future__ import annotations

import logging
import sqlite3

import pytest
from pydantic import ValidationError

from tests.market.p5b_support import Env, FakeCtx, execute, listed, query, set_ideas
from us_swing.core.desk_agents import FeedItem
from us_swing.desk.recorder import Recorder
from us_swing.market.report_page import ReportPage, ReportPageSkill
from us_swing.market.store import LeadPickRow, MarketStore

BRIEF = "Breadth is narrow but improving. Two long picks look ready for tomorrow."
BODY = "<style>body { color: #ddd; }</style><h1>Evening report</h1>" + "<p>Calm day.</p>" * 20


def _page(html: str = BODY, title: str = "Evening report") -> ReportPage:
    return ReportPage.model_validate({"title": title, "html": html})


def _stage(env: Env, brief: bool = True) -> ReportPageSkill:
    set_ideas(env, listed("long", "LNG", 2))
    store = MarketStore(env.home)
    store.replace_day("lead_picks", env.day, [LeadPickRow(env.day, "long", "LNG01", 1,
                                                          "Clean breakout on volume")])
    store.close()
    if brief:
        recorder = Recorder(env.home)
        recorder.add_briefs([FeedItem("evening", BRIEF, env.day)], "emp-x", "Made Up Lead")
        recorder.close()
    return ReportPageSkill(env.candles)


def _pages(env: Env) -> list[tuple[str, int, str]]:
    return query(env.home, "SELECT date, version, title FROM canvas_pages ORDER BY id")


def test_report_facts(p5b: Env) -> None:
    """UT-MKT-007.001.M02.T01: facts hold the evening brief, the picks and the views; fresh."""
    facts = _stage(p5b).facts(p5b.home)
    assert facts.fresh and facts.data_day == p5b.day
    for part in (BRIEF, "LNG01", "Clean breakout on volume", "Regime view", "Sector view",
                 "News review", "No scripts"):
        assert part in facts.text


def test_no_lead_brief(p5b: Env) -> None:
    """UT-MKT-007.001.M02.T02: without the day's evening brief the facts are stale."""
    facts = _stage(p5b, brief=False).facts(p5b.home)
    assert not facts.fresh
    assert p5b.day in facts.why_stale and "lead brief" in facts.why_stale


def test_no_briefs_table(p5b: Env) -> None:
    """UT-MKT-007.001.M02.T03: a desk.db without the briefs table is stale, not an error."""
    skill = _stage(p5b, brief=False)
    execute(p5b.home, "DROP TABLE IF EXISTS briefs")
    facts = skill.facts(p5b.home)
    assert not facts.fresh


def test_runs_after_lead_brief() -> None:
    """UT-MKT-007.001.M02.T04: the skill needs only the lead brief."""
    assert ReportPageSkill.needs == ("lead_brief",)
    assert ReportPageSkill.key == "report_page"


def test_valid_answer() -> None:
    """UT-MKT-007.002.M02.T01: a short title and a 2 KB page pass the schema."""
    page = _page("<p>" + "x" * 2000 + "</p>", "Evening report 6 Nov")
    assert page.title == "Evening report 6 Nov"


@pytest.mark.parametrize("data", [
    {"title": "T" * 81, "html": BODY},
    {"title": "Evening", "html": "<p>" + "x" * 43 + "</p>"},
    {"title": "Evening", "html": "<p>" + "x" * 200_000 + "</p>"},
    {"title": "Evening", "html": BODY, "script": "x"},
])
def test_bad_answer(data: dict[str, str]) -> None:
    """UT-MKT-007.002.M02.T02: long title, short or huge page and extra fields are refused."""
    with pytest.raises(ValidationError):
        ReportPage.model_validate(data)


def test_versions(p5b: Env) -> None:
    """UT-MKT-007.004.M03.T01: versions count up per day and start at 1 on a new day."""
    store = MarketStore(p5b.home)
    try:
        assert store.add_page("2026-11-05", "A", "<p>a</p>", "2026-11-05T21:00:00+00:00") == 1
        assert store.add_page("2026-11-05", "B", "<p>b</p>", "2026-11-05T22:00:00+00:00") == 2
        assert store.add_page("2026-11-06", "C", "<p>c</p>", "2026-11-06T21:00:00+00:00") == 1
    finally:
        store.close()
    assert _pages(p5b) == [("2026-11-05", 1, "A"), ("2026-11-05", 2, "B"),
                           ("2026-11-06", 1, "C")]


def test_append_only(p5b: Env) -> None:
    """UT-MKT-007.004.M03.T02: UPDATE and DELETE on canvas_pages are refused."""
    store = MarketStore(p5b.home)
    store.add_page("2026-11-05", "A", "<p>a</p>", "2026-11-05T21:00:00+00:00")
    store.close()
    for sql in ("UPDATE canvas_pages SET title = 'Z'", "DELETE FROM canvas_pages"):
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            execute(p5b.home, sql)
    assert _pages(p5b) == [("2026-11-05", 1, "A")]


def test_no_answer(p5b: Env) -> None:
    """UT-MKT-007.005.M02.T01: without an answer no page is stored and no brief is posted."""
    skill = _stage(p5b)
    items = skill.act(FakeCtx(p5b.home, None), skill.facts(p5b.home))
    assert items == [] and _pages(p5b) == []


def test_empty_after_cleaning(p5b: Env, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-007.005.M02.T02: a page that is only script and iframe is not stored."""
    skill = _stage(p5b)
    bad = _page("<script>" + "x" * 300 + "</script><iframe src=\"https://x\"></iframe>")
    with caplog.at_level(logging.WARNING, logger="us_swing.market.report_page"):
        items = skill.act(FakeCtx(p5b.home, bad), skill.facts(p5b.home))
    assert items == [] and _pages(p5b) == []
    assert any(r.message.startswith("[Report]") for r in caplog.records)


def test_last_good_version_stays(p5b: Env) -> None:
    """UT-MKT-007.005.M02.T03: a failed answer leaves the saved version as it was."""
    skill = _stage(p5b)
    facts = skill.facts(p5b.home)
    skill.act(FakeCtx(p5b.home, _page()), facts)
    skill.act(FakeCtx(p5b.home, None), facts)
    assert _pages(p5b) == [(p5b.day, 1, "Evening report")]


def test_feed_brief(p5b: Env) -> None:
    """UT-MKT-007.006.M02.T01: a saved page posts one info brief; the stored html is clean."""
    skill = _stage(p5b)
    page = _page(BODY + "<p onclick=\"x()\">Click</p>")
    items = skill.act(FakeCtx(p5b.home, page), skill.facts(p5b.home))
    assert items == [FeedItem("info", "Report page ready: Evening report (version 1)", p5b.day)]
    (html,) = query(p5b.home, "SELECT html FROM canvas_pages")[0]
    assert "onclick" not in html and "<p>Click</p>" in html


def test_run_log(p5b: Env, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-007.008.M02.T01: one [Report] line with day, version, sizes and items removed."""
    skill = _stage(p5b)
    page = _page(BODY + "<script>bad()</script>")
    with caplog.at_level(logging.INFO, logger="us_swing.market.report_page"):
        skill.act(FakeCtx(p5b.home, page), skill.facts(p5b.home))
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("[Report]")]
    assert len(lines) == 1
    assert p5b.day in lines[0] and "version 1" in lines[0] and "1 item(s) removed" in lines[0]
    assert "KB written" in lines[0] and "KB kept" in lines[0]
