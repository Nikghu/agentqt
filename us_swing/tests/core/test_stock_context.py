"""Unit tests: core/stock_context — earnings, sector, regime and prompt text.
Refs: UT-SCR-018.002.M36.T01 – T03, UT-SCR-018.003.M37.T01, UT-SCR-018.004.M35.T01 – T02,
      UT-SCR-019.002.M38.T01 – T03, UT-SCR-019.003.M37.T01, UT-SCR-019.004.M37.T01,
      UT-SCR-019.005.M39.T01, UT-SCR-019.006.M39.T01,
      UT-SCR-018.005.M37.T01, UT-SCR-018.006.M37.T01
"""
from __future__ import annotations

import json
import threading
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from us_swing.core.notifications import AiAnswer
from us_swing.core.stock_context import (
    SECTOR_BENCHMARK,
    SECTOR_ETFS,
    EarningsLookup,
    Headline,
    NewsLookup,
    StockContext,
    apply_news_tone,
    build_context,
    context_text,
    earnings_level,
    market_regime,
    news_level,
    research_picks,
)
from us_swing.core.stock_context._news import _parse_yahoo_item

TODAY = date(2026, 11, 18)


def _dates(n: int) -> list[str]:
    return [(TODAY - timedelta(days=n - i)).isoformat() for i in range(n)]


def _sector_closes() -> dict[str, dict[str, float]]:
    """RSP flat; sector i (0-based, in SECTOR_ETFS order) moves +(5 - i)% over 21 days."""
    days = _dates(30)
    closes = {SECTOR_BENCHMARK: {d: 100.0 for d in days}}
    for i, (etf, _name) in enumerate(SECTOR_ETFS):
        closes[etf] = {d: 100.0 for d in days}
        closes[etf][days[-1]] = 100.0 + (5 - i)
    return closes


def test_one_fetch_per_stock_per_day(tmp_path: Path) -> None:
    """UT-SCR-018.002.M36.T01: One fetch per stock per day."""
    calls: list[str] = []

    def fetch(symbol: str) -> list[date]:
        calls.append(symbol)
        return [TODAY + timedelta(days=23)]

    lookup = EarningsLookup(tmp_path / "earnings.json", fetch)
    first = lookup.next_dates(["NVDA", "JCI"], TODAY)
    again = EarningsLookup(tmp_path / "earnings.json", fetch).next_dates(["NVDA", "JCI"], TODAY)
    assert first == again == {"NVDA": TODAY + timedelta(days=23), "JCI": TODAY + timedelta(days=23)}
    assert len(calls) == 2
    lookup.next_dates(["NVDA"], TODAY + timedelta(days=1))
    assert len(calls) == 3


def test_failed_lookup_gives_none_and_retries(tmp_path: Path) -> None:
    """UT-SCR-018.002.M36.T02: Failed lookup gives None and retries next run."""
    calls: list[str] = []

    def fetch(symbol: str) -> list[date]:
        calls.append(symbol)
        if symbol == "COF":
            raise ConnectionError("timed out")
        return [TODAY + timedelta(days=3)]

    lookup = EarningsLookup(tmp_path / "earnings.json", fetch)
    assert lookup.next_dates(["NVDA", "COF"], TODAY) == {
        "NVDA": TODAY + timedelta(days=3), "COF": None,
    }
    lookup.next_dates(["NVDA", "COF"], TODAY)
    assert calls == ["NVDA", "COF", "COF"]


def test_only_dates_on_or_after_today(tmp_path: Path) -> None:
    """UT-SCR-018.002.M36.T03: Only dates on or after today."""
    answers = {"A": [TODAY - timedelta(days=1), TODAY + timedelta(days=20)], "B": []}
    lookup = EarningsLookup(tmp_path / "earnings.json", lambda s: answers[s])
    assert lookup.next_dates(["A", "B"], TODAY) == {"A": TODAY + timedelta(days=20), "B": None}


def test_earnings_level_boundaries() -> None:
    """UT-SCR-018.003.M37.T01: Earnings level boundaries."""
    assert [earnings_level(d) for d in (0, 5, 6, 10, 11, None)] == [
        "red", "red", "yellow", "yellow", "green", "",
    ]
    earnings = {"A": TODAY + timedelta(days=3), "B": TODAY + timedelta(days=8)}
    contexts, _ = build_context(["A", "B"], ["earnings"], {}, {}, earnings, TODAY)
    assert contexts["A"].flags == ("Earnings in 3 days",)
    assert contexts["B"].flags == ()
    assert contexts["B"].earnings_level == "yellow"


def test_sector_rank_and_levels() -> None:
    """UT-SCR-018.004.M35.T01: Sector rank and levels."""
    sectors = {"FIN": "Financials", "IND": "Industrials", "UTL": "Utilities"}
    contexts, _ = build_context(
        list(sectors), ["sector"], sectors, _sector_closes(), {}, TODAY,
    )
    fin, ind, utl = contexts["FIN"], contexts["IND"], contexts["UTL"]
    assert (fin.sector, fin.sector_rank, fin.sector_count, fin.sector_level) == (
        "Financials", 2, 11, "green",
    )
    assert fin.sector_move_pct is not None and round(fin.sector_move_pct, 1) == 4.0
    assert (ind.sector_rank, ind.sector_level, ind.flags) == (7, "neutral", ())
    assert (utl.sector_rank, utl.sector_level) == (9, "red")
    assert utl.flags == ("Weak sector (#9 of 11)",)


def test_unknown_sector_or_missing_closes() -> None:
    """UT-SCR-018.004.M35.T02: Unknown sector or missing closes."""
    closes = _sector_closes()
    del closes["XLK"]
    sectors = {"BTC": "Crypto", "MSFT": "Information Technology"}
    contexts, _ = build_context(list(sectors), ["sector"], sectors, closes, {}, TODAY)
    for ctx in contexts.values():
        assert ctx.sector_rank is None and ctx.sector_level == "" and ctx.flags == ()


def test_market_regime() -> None:
    """UT-SCR-018.005.M37.T01: Market regime."""
    days = _dates(210)
    rising = {d: 100.0 + i for i, d in enumerate(days)}
    falling = {d: 300.0 - i for i, d in enumerate(days)}
    between = dict(rising)
    between[days[-1]] = 260.0
    short = {d: 100.0 for d in days[:150]}
    assert market_regime(rising) == "risk-on"
    assert market_regime(falling) == "risk-off"
    assert market_regime(between) == "mixed"
    assert market_regime(short) == ""


def test_prompt_text_lists_stocks_and_market() -> None:
    """UT-SCR-018.006.M37.T01: Prompt text lists each stock and the market."""
    contexts = {
        "NVDA": StockContext(earnings_days=23, earnings_level="green", sector="Technology",
                             sector_rank=2, sector_count=11, sector_move_pct=3.4,
                             sector_level="green", market="risk-on"),
        "COF": StockContext(earnings_days=3, earnings_level="red", market="risk-on",
                            flags=("Earnings in 3 days",)),
    }
    lines = context_text(contexts, "risk-on").splitlines()
    assert lines[0].startswith("=== STOCK CONTEXT") and "risk-on" in lines[0]
    assert lines[1] == (
        "NVDA | earnings in 23 days (green) | Technology #2 of 11, +3.4% vs RSP (green)"
        " | flags: none"
    )
    assert lines[2] == "COF | earnings in 3 days (red) | flags: Earnings in 3 days"


# ── Phase 2: news and web research (FO-SCR-017) ───────────────────────────────

NOW = datetime(2026, 11, 18, 15, 0, tzinfo=timezone.utc)


def _headline(hours_ago: float, title: str = "t") -> Headline:
    when = (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return Headline(title=title, source="Reuters", published=when, url="https://x.test/a")


def test_newest_eight_from_last_five_days(tmp_path: Path) -> None:
    """UT-SCR-019.002.M38.T01: Newest 8 from last 5 days, one fetch a day."""
    items = [_headline(h, f"h{h}") for h in (1, 2, 3, 5, 8, 13, 21, 34, 55, 130, 150, 200)]
    calls: list[str] = []

    def fetch(symbol: str) -> list[Headline]:
        calls.append(symbol)
        return list(reversed(items))

    lookup = NewsLookup(tmp_path / "news.json", fetch)
    got = lookup.headlines(["NVDA"], NOW)["NVDA"]
    assert [h.title for h in got] == ["h1", "h2", "h3", "h5", "h8", "h13", "h21", "h34"]
    assert NewsLookup(tmp_path / "news.json", fetch).headlines(["NVDA"], NOW)["NVDA"] == got
    assert calls == ["NVDA"]


def test_failed_news_lookup_gives_nothing(tmp_path: Path) -> None:
    """UT-SCR-019.002.M38.T02: Failed lookup gives no headlines."""
    calls: list[str] = []

    def fetch(symbol: str) -> list[Headline]:
        calls.append(symbol)
        raise RuntimeError("YAHOO! FINANCE IS CURRENTLY DOWN!")

    lookup = NewsLookup(tmp_path / "news.json", fetch)
    assert lookup.headlines(["COF"], NOW) == {"COF": []}
    lookup.headlines(["COF"], NOW)
    assert calls == ["COF", "COF"]


def test_both_yahoo_formats_read() -> None:
    """UT-SCR-019.002.M38.T03: Both Yahoo formats read."""
    new = {"id": "1", "content": {"title": "Chip orders beat", "pubDate": "2026-11-17T12:30:00Z",
                                  "provider": {"displayName": "Reuters"},
                                  "canonicalUrl": {"url": "https://r.test/1"}}}
    old = {"title": "Chip orders beat", "publisher": "Reuters", "link": "https://r.test/1",
           "providerPublishTime": int(datetime(2026, 11, 17, 12, 30, tzinfo=timezone.utc)
                                      .timestamp())}
    expected = Headline("Chip orders beat", "Reuters", "2026-11-17T12:30:00Z", "https://r.test/1")
    assert _parse_yahoo_item(new) == expected
    assert _parse_yahoo_item(old) == expected
    assert _parse_yahoo_item({"content": {}}) is None


def test_headlines_in_context_block() -> None:
    """UT-SCR-019.003.M37.T01: Headlines in the context block."""
    news = {"NVDA": [_headline(2, "Orders beat"), _headline(30, "Probe opened")]}
    contexts, regime = build_context(["NVDA"], ["news"], {}, {}, {}, TODAY, headlines=news)
    assert len(contexts["NVDA"].news) == 2
    lines = context_text(contexts, regime).splitlines()
    assert lines[1] == "NVDA | flags: none"
    assert lines[2] == "  news 11-18 · Reuters · Orders beat"
    assert lines[3] == "  news 11-17 · Reuters · Probe opened"


def test_news_level_boundaries_and_flag() -> None:
    """UT-SCR-019.004.M37.T01: News level boundaries and flag."""
    assert [news_level(t) for t in (-0.3, -0.1, 0.0, 0.3, None)] == [
        "red", "yellow", "neutral", "green", ""]
    base = StockContext(news=(_headline(1),), flags=("Earnings in 3 days",))
    red = apply_news_tone(base, -0.6)
    assert (red.news_tone, red.news_level) == (-0.6, "red")
    assert red.flags == ("Earnings in 3 days", "Negative news")
    assert apply_news_tone(base, 0.4).flags == ("Earnings in 3 days",)
    assert apply_news_tone(base, None) == base


def test_research_three_at_a_time_web_search_only() -> None:
    """UT-SCR-019.005.M39.T01: Research runs 3 at a time with only web search."""
    lock = threading.Lock()
    running = {"now": 0, "max": 0}
    seen: list[Any] = []

    def ask(config: Any, instruction: str, facts: str, timeout_s: float = 90.0) -> AiAnswer:
        with lock:
            running["now"] += 1
            running["max"] = max(running["max"], running["now"])
            seen.append(config)
        time.sleep(0.05)
        with lock:
            running["now"] -= 1
        body = {"summary": " ".join(["word"] * 80), "risk": "",
                "sources": [f"https://s.test/{i}" for i in range(5)]}
        return AiAnswer(text="Here you go:\n" + json.dumps(body), provider="claude")

    result = research_picks(["A", "B", "C", "D", "E"], "claude-haiku-5-5", TODAY, ask=ask)
    assert set(result) == {"A", "B", "C", "D", "E"}
    assert running["max"] == 3
    assert all(c.claude_tools == ("WebSearch",) and c.claude_model == "claude-haiku-5-5"
               for c in seen)
    assert len(result["A"].summary.split()) == 60 and len(result["A"].sources) == 3


def test_failed_research_skipped() -> None:
    """UT-SCR-019.006.M39.T01: Failed or unreadable research skipped."""
    answers = {
        "A": AiAnswer(error="Claude Code CLI: no answer in 180 seconds"),
        "B": AiAnswer(text="I could not find anything useful."),
        "C": AiAnswer(text=json.dumps({"summary": "Offering priced", "risk": "share offering",
                                       "sources": ["https://s.test/c"]})),
    }

    def ask(config: Any, instruction: str, facts: str, timeout_s: float = 90.0) -> AiAnswer:
        return answers[facts.split()[1]]

    result = research_picks(["A", "B", "C"], "m", TODAY, ask=ask)
    assert list(result) == ["C"]
    assert result["C"].risk == "share offering"
