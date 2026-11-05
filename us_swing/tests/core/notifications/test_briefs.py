"""Unit tests for daily brief timing and text (MD-INF-012.002.M01, MD-INF-012.003.M02)."""
from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from us_swing.core.notifications import (
    DayEndPnLEvent,
    MarketQuote,
    MorningBriefEvent,
    TradeLine,
    default_registry,
)
from us_swing.core.notifications._briefs import (
    MORNING_BRIEF,
    SendLog,
    brief_due,
    brief_facts,
    day_end_due,
    numbers_ok,
)
from us_swing.data.market_calendar import ET

THU = datetime.date(2026, 11, 5)


def _at(day: datetime.date, hour: int, minute: int = 0) -> datetime.datetime:
    return datetime.datetime(day.year, day.month, day.day, hour, minute, tzinfo=ET)


def test_brief_due_once_in_premarket() -> None:
    """UT-INF-012.002.M01.T01: brief due in pre-market until sent that day."""
    assert brief_due(_at(THU, 7), None)
    assert brief_due(_at(THU, 7), THU - datetime.timedelta(days=1))
    assert not brief_due(_at(THU, 7), THU)


@pytest.mark.parametrize("moment", [
    _at(datetime.date(2026, 11, 7), 7),   # Saturday
    _at(THU, 10),                          # market open
    _at(THU, 3, 59),                       # before pre-market
    _at(datetime.date(2026, 11, 26), 7),  # Thanksgiving
])
def test_brief_not_due_outside_premarket(moment: datetime.datetime) -> None:
    """UT-INF-012.002.M01.T02: no brief on weekends, holidays or outside pre-market."""
    assert not brief_due(moment, None)


def test_send_log_survives_restart(tmp_path: Path) -> None:
    """UT-INF-012.002.M01.T03: the sent day is read back by a new log; bad file is empty."""
    path = tmp_path / "notify_state.json"
    SendLog(path).mark(1, MORNING_BRIEF, THU)

    assert SendLog(path).last_sent(1, MORNING_BRIEF) == THU
    assert SendLog(path).last_sent(2, MORNING_BRIEF) is None

    path.write_text("{not json", encoding="utf-8")
    assert SendLog(path).last_sent(1, MORNING_BRIEF) is None


def test_number_check() -> None:
    """UT-INF-012.004.M01.T01: AI comment may only use numbers from the facts."""
    facts = "SPY: 767.11, +0.42% vs previous close\nOpen trades: 3, unrealized P&L +1,412 USD"
    assert numbers_ok("SPY is up 0.42% at 767.11 with 3 trades worth 1412 USD.", facts)
    assert not numbers_ok("SPY may reach 780 today.", facts)


def test_day_end_due_from_1605() -> None:
    """UT-INF-012.005.M01.T01: day-end due from 16:05 ET, once per day."""
    assert not day_end_due(_at(THU, 16, 2), None)
    assert day_end_due(_at(THU, 16, 6), None)
    assert not day_end_due(_at(THU, 16, 6), THU)
    assert day_end_due(_at(THU, 21), None)
    assert not day_end_due(_at(datetime.date(2026, 11, 7), 17), None)


def _brief(**kw: object) -> MorningBriefEvent:
    base: dict[str, object] = dict(
        session_date="Thu 05 Nov 2026",
        quotes=(MarketQuote("SPY", 767.11, 0.42), MarketQuote("QQQ", 685.36, -0.53)),
        vix=MarketQuote("VIX", 16.73, 0.96),
        open_trades=(TradeLine("AAPL", 300.0), TradeLine("MSFT", -40.0)),
        open_count=2, unrealized=260.0, signals=("NVDA", "CRWD"),
        screener_time="2026-11-04 09:12", screener_top=("AMD", "PLTR"),
        ai_comment="Calm open expected.",
    )
    base.update(kw)
    return MorningBriefEvent(**base)  # type: ignore[arg-type]


def test_morning_brief_text() -> None:
    """UT-INF-012.003.M02.T01: brief shows market, trades, signals, screener and AI note."""
    text = default_registry().render(_brief()).text

    assert text.startswith("USSwing · Morning brief · Thu 05 Nov 2026")
    for part in ("SPY 767.11  +0.42%", "QQQ 685.36  −0.53%", "VIX 16.73",
                 "Open trades: 2 · Unrealized +$260", "MSFT −$40",
                 "Waiting signals: NVDA, CRWD", "Screener (2026-11-04 09:12): AMD, PLTR",
                 "AI note", "Calm open expected."):
        assert part in text
    assert "Open trade MSFT: -40 USD" in brief_facts(_brief())


def test_morning_brief_without_data() -> None:
    """UT-INF-012.003.M02.T02: each empty part says so."""
    text = default_registry().render(MorningBriefEvent()).text
    for part in ("Market data not available", "Open trades: none",
                 "Waiting signals: none", "Screener: no recent run"):
        assert part in text
    assert "AI note" not in text


def test_day_end_v2_text() -> None:
    """UT-INF-012.005.M02.T01: day-end lists trades, win rate, best and worst."""
    event = DayEndPnLEvent(
        realized=80.0, unrealized=412.0, trade_count=2, session_date="Thu 05 Nov 2026",
        trades=(TradeLine("AAPL", 120.0, 2.4), TradeLine("MSFT", -40.0, -0.8)),
    )
    text = default_registry().render(event).text

    for part in ("Day-end report · Thu 05 Nov 2026", "Realized +$80 · Unrealized +$412",
                 "Trades closed: 2 · Win rate 50%", "AAPL +$120 (+2.40%)",
                 "MSFT −$40 (−0.80%)", "Best AAPL +$120", "Worst MSFT −$40"):
        assert part in text
    assert "No trades closed today" in default_registry().render(DayEndPnLEvent()).text
