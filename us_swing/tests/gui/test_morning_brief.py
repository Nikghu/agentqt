"""Unit tests for the Morning brief builder (MD-INF-012.003.M03)."""
from __future__ import annotations

import datetime
from typing import Any

import pandas as pd
import pytest

from us_swing.core.notifications import AiAnswer, AiConfig, MarketQuote, MorningBriefEvent
from us_swing.gui import morning_brief


def test_quote_from_extended_bars() -> None:
    """UT-INF-012.003.M03.T01: last pre-market bar against the official previous close."""
    index = pd.DatetimeIndex([
        "2026-11-04 15:55", "2026-11-04 19:55", "2026-11-05 04:00", "2026-11-05 08:55",
    ]).tz_localize("America/New_York")
    bars = pd.DataFrame({"Close": [99.9, 100.5, 100.2, 101.0]}, index=index)
    daily = pd.DataFrame(
        {"Close": [98.0, 100.0, 100.7]},
        index=pd.DatetimeIndex(["2026-11-03", "2026-11-04", "2026-11-05"])
        .tz_localize("America/New_York"),
    )
    today = datetime.date(2026, 11, 5)

    quote = morning_brief.quote_from_bars("SPY", bars, daily, today)

    assert quote is not None
    assert quote.last == 101.0 and quote.change_pct == pytest.approx(1.0)
    assert quote.as_of == ""
    stale = morning_brief.quote_from_bars("VIX", bars.iloc[:2], daily, today)
    assert stale is not None and stale.as_of == "last close"
    assert stale.change_pct == pytest.approx((100.5 / 98 - 1) * 100)
    assert morning_brief.quote_from_bars("SPY", bars, daily.iloc[2:], today) is None


@pytest.mark.parametrize(
    ("answer", "kept"),
    [
        (AiAnswer(text="SPY is up 1.00% before the open.", provider="claude"), True),
        (AiAnswer(text="SPY may reach 800 today.", provider="claude"), False),
        (AiAnswer(error="Claude Code CLI: not installed"), False),
        (None, False),
    ],
)
def test_ai_comment_kept_or_dropped(
    monkeypatch: pytest.MonkeyPatch, answer: AiAnswer | None, kept: bool,
) -> None:
    """UT-INF-012.004.M03.T01: AI note kept only when it answers with fact numbers."""
    calls: list[Any] = []
    monkeypatch.setattr(morning_brief, "fetch_quotes",
                        lambda _s, _t: {"SPY": MarketQuote("SPY", 101.0, 1.0),
                                        "^VIX": MarketQuote("VIX", 16.0, 1.0, "last close"),
                                        "QQQ": MarketQuote("QQQ", 1.0, 0.0, "last close")})
    monkeypatch.setattr(morning_brief, "ask_ai",
                        lambda *a: calls.append(a) or answer)

    brief = morning_brief.build_brief(MorningBriefEvent(), None if answer is None else AiConfig())

    assert brief.quotes == (MarketQuote("SPY", 101.0, 1.0),)
    assert brief.vix is not None and brief.vix.as_of == "last close"
    assert (brief.ai_comment != "") is kept
    assert bool(calls) is (answer is not None)


def test_send_async_publishes_basic_brief_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-INF-012.004.M03.T01: a failing build still publishes the basic brief."""
    def _boom(*_a: Any) -> MorningBriefEvent:
        raise RuntimeError("network down")

    monkeypatch.setattr(morning_brief, "build_brief", _boom)
    sent: list[object] = []
    base = MorningBriefEvent(open_count=1)

    morning_brief.send_brief_async(base, None, lambda e: sent.append(e) or True).join(5)

    assert sent == [base]
