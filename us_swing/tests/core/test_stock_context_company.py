"""Unit tests: core/stock_context — company facts, their levels and the bull vs bear review.
Refs: UT-SCR-020.002.M41.T01 – T03, UT-SCR-020.003.M37.T01, UT-SCR-020.004.M37.T01,
      UT-SCR-020.005.M37.T01, UT-SCR-020.006.M37.T01, UT-SCR-020.007.M42.T01,
      UT-SCR-020.008.M42.T01 – T02
"""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from us_swing.core.notifications import AiAnswer
from us_swing.core.stock_context import (
    AnalystChange,
    CompanyFacts,
    CompanyLookup,
    Headline,
    Research,
    apply_news_tone,
    build_context,
    context_text,
    review_facts,
    review_picks,
    surprise_level,
)
from us_swing.core.stock_context._review import parse_review

TODAY = date(2026, 11, 18)
_INFO = {"revenueGrowth": 0.62, "profitMargins": 0.55, "trailingPE": 48.0,
         "debtToEquity": 16.97, "shortPercentOfFloat": 0.0121, "shortRatio": 2.7,
         "targetMeanPrice": 0.0, "currentPrice": 150.0}


def _days_ago(n: int) -> str:
    return (TODAY - timedelta(days=n)).isoformat()


class _Fetch:
    def __init__(self, fail: bool = False) -> None:
        self.calls: list[tuple[str, str]] = []
        self.fail = fail

    def __call__(self, symbol: str, part: str) -> Any:
        self.calls.append((symbol, part))
        if self.fail:
            raise ConnectionError("down")
        return {"info": _INFO, "eps": 0.0836,
                "changes": [{"day": _days_ago(2), "firm": "UBS", "action": "down",
                             "grade": "Neutral", "target": 0}]}[part]


def test_only_needed_parts_once_a_day(tmp_path: Path) -> None:
    """UT-SCR-020.002.M41.T01: Only needed parts fetched, once a day."""
    fetch = _Fetch()
    lookup = CompanyLookup(tmp_path / "c.json", fetch)
    lookup.facts(["NVDA"], ["analysts"], TODAY)
    again = lookup.facts(["NVDA"], ["analysts"], TODAY)
    assert sorted(fetch.calls) == [("NVDA", "changes"), ("NVDA", "info")]
    assert again["NVDA"].changes[0].firm == "UBS"
    assert lookup.facts(["NVDA"], [], TODAY) == {}


def test_failed_part_gives_no_facts(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-SCR-020.002.M41.T02: Failed part gives no facts."""
    fetch = _Fetch(fail=True)
    lookup = CompanyLookup(tmp_path / "c.json", fetch)
    with caplog.at_level(logging.WARNING):
        facts = lookup.facts(["NVDA"], ["surprise"], TODAY)
    assert facts["NVDA"] == CompanyFacts()
    assert "[Screener] Company data lookup failed for 1 part(s)" in caplog.text
    lookup.facts(["NVDA"], ["surprise"], TODAY)
    assert len(fetch.calls) == 2


def test_yahoo_values_converted(tmp_path: Path) -> None:
    """UT-SCR-020.002.M41.T03: Yahoo values converted."""
    lookup = CompanyLookup(tmp_path / "c.json", _Fetch())
    facts = lookup.facts(["NVDA"], ["surprise", "fundamentals", "short", "analysts"], TODAY)
    nvda = facts["NVDA"]
    assert nvda.debt_to_equity == 0.17
    assert nvda.short_pct == 1.21
    assert nvda.eps_surprise_pct == 8.36
    assert nvda.target_mean is None
    assert nvda.changes[0].target is None


def _ctx(facts: CompanyFacts, kinds: list[str]) -> Any:
    contexts, _ = build_context(["X"], kinds, {}, {}, {}, TODAY, company={"X": facts})
    return contexts["X"]


def test_surprise_levels_and_flag() -> None:
    """UT-SCR-020.003.M37.T01: Surprise levels and flag."""
    assert [surprise_level(p) for p in (1.5, 0.5, -1.0, None)] == ["green", "neutral",
                                                                   "neutral", ""]
    ctx = _ctx(CompanyFacts(eps_surprise_pct=-3.5), ["surprise"])
    assert ctx.surprise_level == "red"
    assert ctx.flags == ("EPS miss -3.5%",)


def test_short_flag_and_no_fundamentals_flag() -> None:
    """UT-SCR-020.004.M37.T01: Short flag; fundamentals no flag."""
    assert _ctx(CompanyFacts(short_pct=20.0), ["short"]).short_level == "neutral"
    ctx = _ctx(CompanyFacts(short_pct=24.0, pe=3.0, revenue_growth_pct=-40.0),
               ["short", "fundamentals"])
    assert ctx.short_level == "red"
    assert ctx.flags == ("High short interest (24% of float)",)
    assert ctx.pe == 3.0
    assert _ctx(CompanyFacts(short_pct=24.0), ["fundamentals"]).flags == ()


def test_analyst_levels_and_flag() -> None:
    """UT-SCR-020.005.M37.T01: Analyst levels and flag."""
    down = AnalystChange(_days_ago(2), "UBS", "down")
    down2 = AnalystChange(_days_ago(5), "Citi", "down")
    up = AnalystChange(_days_ago(1), "Jefferies", "up")
    old = AnalystChange(_days_ago(40), "Old", "down")
    one = _ctx(CompanyFacts(changes=(down, old)), ["analysts"])
    assert (one.analyst_level, one.flags) == ("red", ("1 downgrade",))
    assert [c.firm for c in one.analyst_changes] == ["UBS"]
    assert _ctx(CompanyFacts(changes=(down, down2)), ["analysts"]).flags == ("2 downgrades",)
    green = _ctx(CompanyFacts(changes=(up,), target_mean=172.0, price=150.0), ["analysts"])
    assert (green.analyst_level, green.analyst_target_pct) == ("green", 14.7)
    many = tuple(AnalystChange(_days_ago(10 + i), f"F{i}", "main") for i in range(8))
    assert len(_ctx(CompanyFacts(changes=many), ["analysts"]).analyst_changes) == 5


def test_company_facts_in_context_block() -> None:
    """UT-SCR-020.006.M37.T01: Company facts in the context block."""
    facts = CompanyFacts(eps_surprise_pct=6.2, revenue_growth_pct=62.0, margin_pct=55.0,
                         pe=48.0, debt_to_equity=0.4, short_pct=1.1, days_to_cover=1.3,
                         target_mean=172.0, price=150.0,
                         changes=(AnalystChange(_days_ago(2), "UBS", "down"),))
    ctx = _ctx(facts, ["surprise", "fundamentals", "short", "analysts"])
    line = context_text({"NVDA": ctx}, "").splitlines()[1]
    assert line == (
        "NVDA | last EPS beat +6.2% (green) | revenue growth +62%, margin 55%, P/E 48.0, "
        "debt/equity 0.40 | short 1.1% of float, 1.3 days to cover (neutral) | "
        "analysts 30d: 0 up, 1 down; average target +15% (red) | flags: 1 downgrade"
    )


def test_blind_facts_three_at_a_time() -> None:
    """UT-SCR-020.007.M42.T01: Blind facts, 3 at a time, no tools."""
    news = (Headline("Probe opened", "Reuters", "2026-11-17T12:00:00Z", "https://r.test"),)
    contexts, _ = build_context(["NVDA"], ["news", "surprise"], {}, {}, {}, TODAY,
                                headlines={"NVDA": news},
                                company={"NVDA": CompanyFacts(eps_surprise_pct=-3.5)})
    raw = contexts["NVDA"]
    toned = apply_news_tone(raw, -0.6)
    assert "Negative news" in toned.flags
    facts = review_facts("NVDA", TODAY, "close 151.20", raw,
                         Research("Export rules may cut sales.", (), "export rules"))
    assert "Price: close 151.20" in facts
    assert "  11-17 · Reuters · Probe opened" in facts
    assert "Web research: Export rules may cut sales. Risk: export rules" in facts
    assert "Red flags: EPS miss -3.5%" in facts
    assert "Negative news" not in facts and "-0.6" not in facts

    running, peak = [0], [0]
    lock = threading.Lock()
    seen: list[Any] = []

    def fake_ask(config: Any, instruction: str, text: str, timeout_s: float = 90.0) -> AiAnswer:
        with lock:
            running[0] += 1
            peak[0] = max(peak[0], running[0])
            seen.append(config)
        time.sleep(0.05)
        with lock:
            running[0] -= 1
        return AiAnswer(text=json.dumps({"bull": ["a"], "bear": ["b"], "verdict": "Long",
                                         "confidence": "high"}))

    runs = review_picks({f"S{i}": facts for i in range(5)}, "claude-sonnet-5-5", ask=fake_ask)
    assert peak[0] == 3
    assert all(c.claude_tools == () and c.claude_model == "claude-sonnet-5-5" for c in seen)
    assert [r.review.verdict for r in runs.values() if r.review] == ["Long"] * 5


def test_reply_read() -> None:
    """UT-SCR-020.008.M42.T01: Reply read."""
    review = parse_review('Here: {"bull": ["a", "b", "c", "d"], "bear": [], '
                          '"verdict": "wait", "confidence": "odd", "summary": "s"}')
    assert review is not None
    assert review.bull == ("a", "b", "c")
    assert (review.verdict, review.confidence) == ("Wait", "low")


def test_bad_reply_skipped(caplog: pytest.LogCaptureFixture) -> None:
    """UT-SCR-020.008.M42.T02: Bad reply skipped."""
    answers = {"A": AiAnswer(error="timed out"), "B": AiAnswer(text="no json"),
               "C": AiAnswer(text='{"verdict": "Buy"}'),
               "D": AiAnswer(text='{"verdict": "Short", "bull": [], "bear": ["x"]}')}

    def fake_ask(config: Any, instruction: str, text: str, timeout_s: float = 90.0) -> AiAnswer:
        return answers[text]

    with caplog.at_level(logging.WARNING):
        runs = review_picks({s: s for s in answers}, "m", ask=fake_ask)
    assert [s for s, r in runs.items() if r.review] == ["D"]
    assert runs["A"].reply == "timed out"
    assert "[Screener] Bull vs bear review failed for 3 of 4 stock(s)" in caplog.text
