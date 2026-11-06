"""Tests for MD-MKT-006.001.M02 — market/news_step.py (News desk step)."""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import pytest

from tests.market.news_support import Item, getter, rss
from tests.market.p5b_support import Env, listed, query, set_ideas
from us_swing.core.desk_contract import StepContext
from us_swing.market.news_step import NEWS_BUDGET_S, NewsStep
from us_swing.market.store import MarketStore, NewsItemRow

NOW = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)
IDEAS = listed("long", "LNG", 2) + listed("short", "SHT", 1)


def _ago(**kw: float) -> datetime:
    return NOW - timedelta(**kw)


def _run(env: Env, get: object, clock: datetime = NOW) -> None:
    step = NewsStep(get, lambda: clock)  # type: ignore[arg-type]
    step(StepContext(1, "manual", datetime.now(UTC), env.home))


def _stock_feed(prefix: str) -> str:
    return rss([(f"{prefix} headline", f"https://x/{prefix}", _ago(hours=5))])


def _count(env: Env, where: str = "1=1") -> int:
    return int(query(env.home, f"SELECT COUNT(*) FROM news_items WHERE {where}")[0][0])  # noqa: S608


def test_stock_headlines_kept(p5b: Env) -> None:
    """UT-MKT-006.001.M02.T01: three listed ideas give rows for each with the ideas day."""
    set_ideas(p5b, IDEAS)
    get = getter({s: _stock_feed(s) for s in ("LNG01", "LNG02", "SHT01")})
    _run(p5b, get)
    rows = query(p5b.home, "SELECT symbol, date FROM news_items ORDER BY symbol")
    assert rows == [("LNG01", p5b.day), ("LNG02", p5b.day), ("SHT01", p5b.day)]


def test_one_stock_fails(p5b: Env, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-006.001.M02.T02: a failing stock feed is logged; the others are kept; no raise."""
    set_ideas(p5b, IDEAS)
    get = getter({s: _stock_feed(s) for s in ("LNG01", "LNG02", "SHT01")}, fail_stock=["LNG02"])
    with caplog.at_level(logging.INFO):
        _run(p5b, get)
    symbols = {r[0] for r in query(p5b.home, "SELECT symbol FROM news_items")}
    assert symbols == {"LNG01", "SHT01"}
    assert any("[News] Could not read" in r.getMessage() for r in caplog.records)


def test_window_and_cap(p5b: Env) -> None:
    """UT-MKT-006.001.M02.T03: 14 items, 2 older than 3 days, keep the 10 newest within 3 days."""
    set_ideas(p5b, listed("long", "LNG", 1))
    items: list[Item] = [(f"Fresh {i}", f"https://x/{i}", _ago(hours=i + 1)) for i in range(12)]
    items += [(f"Old {i}", f"https://x/o{i}", _ago(days=4 + i)) for i in range(2)]
    _run(p5b, getter({"LNG01": rss(items)}))
    titles = [r[0] for r in query(p5b.home, "SELECT title FROM news_items WHERE symbol = 'LNG01' "
                                            "ORDER BY published DESC")]
    assert titles == [f"Fresh {i}" for i in range(10)]


def test_market_headlines(p5b: Env) -> None:
    """UT-MKT-006.002.M02.T01: 3 feeds, 50 items: at most 30 market rows, all within 24 hours."""
    set_ideas(p5b, IDEAS)
    feeds = {"100003114": 17, "20910258": 17, "SPY": 16}
    market = {key: rss([(f"{key} item {i}", f"https://m/{key}/{i}", _ago(hours=0.5 + 2 * i))
                        for i in range(n)]) for key, n in feeds.items()}
    _run(p5b, getter(market=market))
    rows = query(p5b.home, "SELECT published, symbol FROM news_items")
    assert len(rows) == 30 and {r[1] for r in rows} == {""}
    cutoff = (NOW - timedelta(hours=24)).isoformat(timespec="seconds")
    assert all(r[0] >= cutoff for r in rows)


def test_all_feeds_fail(p5b: Env, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-006.002.M02.T02: every feed failing gives 0 market rows and a log line."""
    set_ideas(p5b, IDEAS)
    with caplog.at_level(logging.INFO):
        _run(p5b, getter(fail_all=True))
    assert _count(p5b, "symbol = ''") == 0
    assert any("3 feed(s) failed" in r.getMessage() for r in caplog.records)


def test_kept_once(p5b: Env) -> None:
    """UT-MKT-006.003.M02.T01: a second run with the same title and a new link adds no row."""
    set_ideas(p5b, listed("long", "LNG", 1))
    _run(p5b, getter({"LNG01": rss([("Same title", "https://x/a", _ago(hours=2))])}))
    _run(p5b, getter({"LNG01": rss([("Same title", "https://x/b", _ago(hours=2))])}))
    assert _count(p5b, "symbol = 'LNG01'") == 1


def test_old_rows_deleted(p5b: Env) -> None:
    """UT-MKT-006.003.M02.T02: a 31-day-old row is deleted; a 29-day-old row stays."""
    set_ideas(p5b, listed("long", "LNG", 1))
    store = MarketStore(p5b.home)
    stamp = NOW.isoformat(timespec="seconds")
    store.add_news([
        NewsItemRow(p5b.day, "OLD", "S", (NOW - timedelta(days=d)).isoformat(timespec="seconds"),
                    f"Row {d}", f"https://o/{d}", stamp) for d in (31, 29)])
    store.close()
    _run(p5b, getter())
    assert [r[0] for r in query(p5b.home, "SELECT title FROM news_items")] == ["Row 29"]


def test_run_log_line(p5b: Env, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-006.012.M02.T01: one run with one failed feed writes one [News] line with counts."""
    set_ideas(p5b, IDEAS)
    get = getter({"LNG01": _stock_feed("LNG01")}, fail_market=["20910258"])
    with caplog.at_level(logging.INFO):
        _run(p5b, get)
    lines = [r.getMessage() for r in caplog.records if "feed(s) failed" in r.getMessage()]
    assert lines == ["[News] Headlines for 1 of 3 stock(s), 0 market headline(s), 1 new, "
                     "1 feed(s) failed, 0 old row(s) deleted"]


def test_headline_redated(p5b: Env) -> None:
    """UT-MKT-006.003.M02.T03: a known headline moves to the new day; only new rows are counted."""
    stamp = NOW.isoformat(timespec="seconds")
    first = NewsItemRow("2026-11-04", "AAA", "S", stamp, "Story", "https://a/1", "old")
    again = NewsItemRow("2026-11-05", "AAA", "S", stamp, "Story", "https://a/2", "new")
    store = MarketStore(p5b.home)
    assert store.add_news([first]) == 1
    assert store.add_news([again]) == 0
    store.close()
    assert query(p5b.home, "SELECT date, fetched FROM news_items") == [("2026-11-05", "new")]


def test_linkless_headlines_kept(p5b: Env) -> None:
    """UT-MKT-006.003.M02.T04: two headlines without a link but with different titles both stay."""
    stamp = NOW.isoformat(timespec="seconds")
    store = MarketStore(p5b.home)
    rows = [NewsItemRow(p5b.day, "AAA", "S", stamp, t, None, stamp) for t in ("One", "Two")]
    assert store.add_news(rows) == 2
    store.close()
    assert query(p5b.home, "SELECT COUNT(*), COUNT(link) FROM news_items") == [(2, 0)]


def test_step_never_raises(p5b: Env, caplog: pytest.LogCaptureFixture,
                           monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-MKT-006.001.M02.T05: any error inside the run is logged with [News]; no raise."""
    set_ideas(p5b, IDEAS)

    def boom(get: object) -> None:
        raise RuntimeError("unexpected")

    monkeypatch.setattr("us_swing.market.news_step.fetch_market", boom)
    with caplog.at_level(logging.INFO):
        _run(p5b, getter())
    assert any(r.getMessage().startswith("[News]") for r in caplog.records)


def test_time_budget(p5b: Env, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-006.001.M02.T04: after the time budget no more stocks are fetched; it is logged."""
    set_ideas(p5b, IDEAS)
    ticks = iter(range(0, 10_000, int(NEWS_BUDGET_S) + 10))
    seen: list[str] = []
    base = getter({s: _stock_feed(s) for s in ("LNG01", "LNG02", "SHT01")})

    def get(url: str) -> str:
        seen.append(url)
        return base(url)

    step = NewsStep(get, lambda: NOW, lambda: float(next(ticks)))
    with caplog.at_level(logging.INFO):
        step(StepContext(1, "manual", datetime.now(UTC), p5b.home))
    stocks = [u for u in seen if "headline?s=" in u and "SPY" not in u]
    assert len(stocks) < 3
    assert any("[News] Time limit reached" in r.getMessage() and "not fetched" in r.getMessage()
               for r in caplog.records)
