"""Unit tests: core/stock_context — earnings, sector, regime and prompt text.
Refs: UT-SCR-018.002.M36.T01 – T03, UT-SCR-018.003.M37.T01, UT-SCR-018.004.M35.T01 – T02,
      UT-SCR-018.005.M37.T01, UT-SCR-018.006.M37.T01
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from us_swing.core.stock_context import (
    SECTOR_BENCHMARK,
    SECTOR_ETFS,
    EarningsLookup,
    StockContext,
    build_context,
    context_text,
    earnings_level,
    market_regime,
)

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
