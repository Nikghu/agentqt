"""Tests for MD-MKT-006.001.M01 — market/news.py (feed reading)."""
from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx
import pytest

from tests.market.news_support import getter, rss
from us_swing.market.news import fetch_market, fetch_symbol, parse_feed, symbol_url

T0 = datetime(2026, 11, 5, 14, 30, tzinfo=UTC)


def test_parse_three_items() -> None:
    """UT-MKT-006.001.M01.T01: three items give three headlines with title, link and UTC time."""
    text = rss([("Alpha beats", "https://x/1", T0), ("Beta up", "https://x/2", T0),
                ("Gamma <news> & more", "https://x/3", T0)])
    heads = parse_feed(text, "AAA", "Yahoo Finance")
    assert [h.title for h in heads] == ["Alpha beats", "Beta up", "Gamma <news> & more"]
    assert heads[0].link == "https://x/1" and heads[0].symbol == "AAA"
    assert heads[0].source == "Yahoo Finance"
    assert heads[0].published == T0 and heads[0].published.tzinfo is not None


def test_bad_feed_never_raises() -> None:
    """UT-MKT-006.001.M01.T02: broken XML, a timeless item and an HTTP error never raise."""
    assert parse_feed("<rss><channel><item>", "AAA", "S") == []
    heads = parse_feed(rss([("No time", "https://x/1", None), ("Has time", "https://x/2", T0)]),
                       "AAA", "S")
    assert [h.title for h in heads] == ["Has time"]
    assert fetch_symbol("AAA", getter(fail_all=True)) is None
    assert fetch_market(getter(fail_all=True)) == ([], 3)


def test_symbol_with_dot() -> None:
    """UT-MKT-006.001.M01.T03: BRK.B asks the feed for BRK-B."""
    assert "s=BRK-B&" in symbol_url("BRK.B")
    seen: list[str] = []

    def get(url: str) -> str:
        seen.append(url)
        return rss([])

    assert fetch_symbol("BRK.B", get) == []
    assert "s=BRK-B&" in seen[0]


@pytest.mark.parametrize(("error", "text"), [
    (httpx.ReadTimeout("slow"), "timed out"),
    (httpx.HTTPStatusError("bad", request=httpx.Request("GET", "https://x"),
                           response=httpx.Response(404, request=httpx.Request("GET", "https://x"))),
     "HTTP 404"),
    (httpx.ConnectError("refused"), "connection failed"),
])
def test_failure_log_is_plain(error: Exception, text: str,
                              caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-006.001.M01.T04: a failed feed logs a plain [News] line, never raises."""
    def get(url: str) -> str:
        raise error

    with caplog.at_level(logging.INFO):
        assert fetch_symbol("AAA", get) is None
    assert [r.getMessage() for r in caplog.records] == [
        f"[News] Could not read Yahoo Finance for AAA ({text})"]
