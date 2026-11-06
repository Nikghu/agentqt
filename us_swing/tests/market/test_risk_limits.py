"""Tests for MD-MKT-005.011.M06 — market/risk_limits.py (hard risk limits)."""
from __future__ import annotations

from us_swing.market.risk_limits import ListedIdea, code_vetoes


def _idea(side: str = "long", symbol: str = "AAA", rank: int = 1, sector: str = "Technology",
          trigger: float | None = 50.0, stop: float | None = 47.0) -> ListedIdea:
    return ListedIdea(side, symbol, rank, sector, trigger, stop)


def test_within_limits() -> None:
    """UT-MKT-005.011.M06.T01: A long idea in an Uptrend with a 6% stop has no veto."""
    assert code_vetoes([_idea()], "Uptrend") == {}


def test_against_the_regime() -> None:
    """UT-MKT-005.011.M06.T02: Long in a Downtrend and short in an Uptrend are vetoed."""
    long_idea, short_idea = _idea("long", "LNG"), _idea("short", "SHT", stop=53.0)
    assert code_vetoes([long_idea], "Downtrend") == {
        ("long", "LNG"): "Long idea while the market is in a Downtrend"}
    assert code_vetoes([short_idea], "Uptrend") == {
        ("short", "SHT"): "Short idea while the market is in an Uptrend"}


def test_stop_distance() -> None:
    """UT-MKT-005.011.M06.T03: A stop 0.5% or 12% from the trigger is vetoed."""
    vetoes = code_vetoes([_idea(symbol="TIGHT", rank=1, trigger=100.0, stop=99.5),
                          _idea(symbol="WIDE", rank=2, trigger=100.0, stop=88.0)], "Choppy")
    assert set(vetoes) == {("long", "TIGHT"), ("long", "WIDE")}
    assert "0.5%" in vetoes[("long", "TIGHT")] and "12.0%" in vetoes[("long", "WIDE")]


def test_limits_exact() -> None:
    """UT-MKT-005.011.M06.T04: A stop at exactly 1% or 10% and a $5 trigger are not vetoed."""
    ideas = [_idea(symbol="ONE", rank=1, trigger=100.0, stop=99.0),
             _idea(symbol="TEN", rank=2, trigger=100.0, stop=90.0),
             _idea(symbol="FIVE", rank=3, trigger=5.0, stop=4.75)]
    assert code_vetoes(ideas, "Choppy") == {}


def test_low_trigger_and_missing_stop() -> None:
    """UT-MKT-005.011.M06.T05: A trigger of 4.9 and a missing stop are both vetoed."""
    vetoes = code_vetoes([_idea(symbol="CHEAP", rank=1, trigger=4.9, stop=4.7),
                          _idea(symbol="NOSTOP", rank=2, stop=None)], "Choppy")
    assert vetoes[("long", "CHEAP")] == "Trigger is below $5"
    assert vetoes[("long", "NOSTOP")] == "No trigger or stop"


def test_sector_cap() -> None:
    """UT-MKT-005.011.M06.T06: Ranks 1, 3, 4 pass; rank 2 breaks the stop, rank 5 is over cap."""
    ideas = [_idea(symbol=f"T{r}", rank=r, stop=40.0 if r == 2 else 47.0) for r in range(1, 6)]
    vetoes = code_vetoes(ideas, "Choppy")
    assert set(vetoes) == {("long", "T2"), ("long", "T5")}
    assert vetoes[("long", "T5")] == "Fourth idea in Technology on the long side"
