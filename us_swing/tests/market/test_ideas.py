"""Tests for MD-MKT-003.001.M01–M06: volume, money flow, setups, score, earnings and store."""
from __future__ import annotations

import math
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from tests.market.conftest import bdays, write_candles
from us_swing.market.candles import CandleReader
from us_swing.market.earnings import next_earnings
from us_swing.market.flow import MIN_DOLLAR_VOLUME, dollar_volume, money_flow
from us_swing.market.score import MarketInputs, pick_ideas, readiness_score, score_frame
from us_swing.market.setups import Bars, long_candidates, long_setups, short_candidates
from us_swing.market.store import IdeaRow, MarketStore, ReasonRow, ScoreRow


def _bars(closes: np.ndarray, spread: float | np.ndarray = 0.01,
          volume: float | np.ndarray = 1e6) -> Bars:
    idx = bdays(len(closes))
    c = pd.DataFrame({"A": closes}, index=idx)
    sp = pd.DataFrame({"A": np.broadcast_to(spread, len(closes))}, index=idx)
    v = pd.DataFrame({"A": np.broadcast_to(volume, len(closes)).astype(float)}, index=idx)
    return Bars(c, c * (1 + sp), c * (1 - sp), v)


def _match(candidates: list[Any], name: str) -> tuple[bool, float, float]:
    _, mask, trigger, stop = next(c for c in candidates if c[0] == name)
    return bool(mask["A"].iloc[-1]), float(trigger["A"].iloc[-1]), float(stop["A"].iloc[-1])


# ── M01 / M02: volume and liquidity ───────────────────────────────────────────

def test_volume_read(tmp_path: Path) -> None:
    """UT-MKT-003.001.M01.T01: Volume is read as a wide frame by date and symbol."""
    path = tmp_path / "candles.db"
    write_candles(path, {"AAA": [10.0, 11.0], "BBB": [5.0, 6.0]}, volume=250.0)
    bars = CandleReader(path).read(["AAA", "BBB"])
    assert list(bars.volumes.columns) == ["AAA", "BBB"]
    assert (bars.volumes == 250.0).all().all()


def test_liquid_stock_kept() -> None:
    """UT-MKT-003.001.M02.T01: Close 100 on 300k shares is 30M a day and is kept."""
    b = _bars(np.full(25, 100.0), volume=300_000.0)
    assert dollar_volume(b.closes, b.volumes)["A"].iloc[-1] == pytest.approx(30e6)
    assert dollar_volume(b.closes, b.volumes)["A"].iloc[-1] >= MIN_DOLLAR_VOLUME


def test_thin_stock_left_out() -> None:
    """UT-MKT-003.001.M02.T02: Close 10 on 1M shares is 10M a day and is left out."""
    b = _bars(np.full(25, 10.0), volume=1_000_000.0)
    assert dollar_volume(b.closes, b.volumes)["A"].iloc[-1] < MIN_DOLLAR_VOLUME


# ── M02: money flow ───────────────────────────────────────────────────────────

def _flow_bars(direction: int) -> Bars:
    n = 80
    closes = 100 * (1 + 0.01 * direction) ** np.arange(n)
    idx = bdays(n)
    c = pd.DataFrame({"A": closes}, index=idx)
    near, far = c, c * (1 - 0.02 * direction)
    highs, lows = (near, far) if direction > 0 else (far, near)
    v = pd.DataFrame({"A": np.linspace(1e6, 3e6, n)}, index=idx)
    return Bars(c, highs, lows, v)


def test_strong_buying() -> None:
    """UT-MKT-003.002.M02.T01: Up days on rising volume, closing at the high, give flow near 1."""
    b = _flow_bars(+1)
    flow, acc, dist = money_flow(b.closes, b.highs, b.lows, b.volumes)
    assert flow["A"].iloc[-1] > 0.95
    assert 1 - flow["A"].iloc[-1] < 0.05
    assert (acc["A"].iloc[-1], dist["A"].iloc[-1]) == (25, 0)


def test_heavy_selling() -> None:
    """UT-MKT-003.002.M02.T02: Down days on rising volume, closing at the low, give flow near 0."""
    b = _flow_bars(-1)
    flow, acc, dist = money_flow(b.closes, b.highs, b.lows, b.volumes)
    assert flow["A"].iloc[-1] < 0.05
    assert (acc["A"].iloc[-1], dist["A"].iloc[-1]) == (0, 25)


def test_flat_bar() -> None:
    """UT-MKT-003.002.M02.T03: High equal to low gives a money flow term of 0 and no error."""
    b = _bars(np.full(80, 50.0), spread=0.0)
    flow, _, _ = money_flow(b.closes, b.highs, b.lows, b.volumes)
    assert flow["A"].iloc[-1] == pytest.approx((0.5 + 0.5 + 1 / 3) / 3)


# ── M03: setups ───────────────────────────────────────────────────────────────

def _squeeze_bars() -> Bars:
    t_a, t_b = np.arange(200), np.arange(40)
    noisy = 100 * 1.003 ** t_a * (1 + 0.04 * (-1.0) ** t_a)
    calm = 100 * 1.003 ** 200 * 1.002 ** (t_b + 1)
    spread = np.r_[np.full(200, 0.02), np.full(40, 0.001)]
    return _bars(np.r_[noisy, calm], spread)


def test_squeeze_found() -> None:
    """UT-MKT-003.003.M03.T01: Uptrend then a narrow range is a Squeeze with 20-day levels."""
    b = _squeeze_bars()
    found, trigger, stop = _match(long_candidates(b), "Squeeze")
    assert found
    assert trigger == pytest.approx(b.highs["A"].iloc[-20:].max())
    assert stop == pytest.approx(b.lows["A"].iloc[-20:].min())
    assert long_setups(b).name["A"].iloc[-1] == "Squeeze"


def test_flat_base_found() -> None:
    """UT-MKT-003.003.M03.T02: Near the 52-week high with a 10% range is a Flat base."""
    rise = np.linspace(50, 100, 200)
    base = 95 + 4 * np.sin(np.arange(60) / 3)
    b = _bars(np.r_[rise, base[:-1], 99.0])
    found, trigger, _ = _match(long_candidates(b), "Flat base")
    assert found
    assert trigger == pytest.approx(b.highs["A"].iloc[-25:].max())


def test_pullback_found() -> None:
    """UT-MKT-003.003.M03.T03: An uptrend dipping to the 21-day average is a Pullback."""
    trend = 100 * 1.005 ** np.arange(200)
    dip = trend[-1] * np.array([0.99, 0.98, 0.975])
    b = _bars(np.r_[trend, dip], spread=0.002)
    found, trigger, stop = _match(long_candidates(b), "Pullback")
    assert found
    assert trigger == pytest.approx(b.highs["A"].iloc[-3:].max())
    assert stop == pytest.approx(b.lows["A"].iloc[-5:].min())


def test_no_long_setup_in_downtrend() -> None:
    """UT-MKT-003.003.M03.T04: A downtrend has no long setup and tightness 0."""
    b = _bars(100 * 0.995 ** np.arange(260))
    assert not any(_match(long_candidates(b), n)[0] for n in ("Squeeze", "Flat base", "Pullback"))
    result = long_setups(b)
    assert pd.isna(result.name["A"].iloc[-1])
    assert result.tightness["A"].iloc[-1] == 0.0


def test_failed_breakout_found() -> None:
    """UT-MKT-003.004.M03.T01: A close above the pivot, then back below, is a Failed breakout."""
    base = 100 * (1 + 0.005 * np.sin(np.arange(60)))
    b = _bars(np.r_[base, 104.0, 102.0, 100.0, 98.5, 97.0])
    found, _, stop = _match(short_candidates(b), "Failed breakout")
    assert found
    assert stop == pytest.approx(b.highs["A"].iloc[-10:].max())
    assert stop >= 104.0


def test_lower_highs_found() -> None:
    """UT-MKT-003.004.M03.T02: Falling 10-day highs under a falling 50-day are Lower highs."""
    t = np.arange(120)
    b = _bars(100 * 0.997 ** t * (1 + 0.02 * np.sin(2 * np.pi * t / 10)))
    found, trigger, _ = _match(short_candidates(b), "Lower highs")
    assert found
    assert trigger == pytest.approx(b.lows["A"].iloc[-10:].min())


def test_breakdown_found() -> None:
    """UT-MKT-003.004.M03.T03: A close under the 50-day on 2x volume is a Breakdown."""
    closes = np.r_[100 * 1.0005 ** np.arange(80), 95.0]
    volume = np.r_[np.full(80, 1e6), 2e6]
    b = _bars(closes, volume=volume)
    found, trigger, _ = _match(short_candidates(b), "Breakdown")
    assert found
    assert trigger == pytest.approx(b.lows["A"].iloc[-1])


def test_no_short_setup_in_uptrend() -> None:
    """UT-MKT-003.004.M03.T04: A steady uptrend has no short setup."""
    b = _bars(100 * 1.004 ** np.arange(200))
    names = ("Failed breakout", "Lower highs", "Breakdown")
    assert not any(_match(short_candidates(b), n)[0] for n in names)


# ── M04: score ────────────────────────────────────────────────────────────────

def _one(value: float) -> pd.DataFrame:
    return pd.DataFrame({"A": [value]})


def test_score_all_parts_full() -> None:
    """UT-MKT-003.005.M04.T01: All five parts at 1 give a score of 100."""
    parts = {k: _one(1.0) for k in ("rs", "flow", "setup", "sector", "regime")}
    assert readiness_score(parts, _one(0.0))["A"].iloc[0] == 100.0


def test_score_weights_and_scale() -> None:
    """UT-MKT-003.005.M04.T02: Score = (20rs + 20flow + 20setup + 15sector + 15regime) * 100/90."""
    values = {"rs": 0.8, "flow": 0.6, "setup": 0.5, "sector": 1.0, "regime": 0.5}
    expected = (20 * 0.8 + 20 * 0.6 + 20 * 0.5 + 15 * 1.0 + 15 * 0.5) * 100 / 90
    got = readiness_score({k: _one(v) for k, v in values.items()}, _one(0.0))["A"].iloc[0]
    assert got == pytest.approx(round(expected, 1))


def _inputs(n: int, closes: dict[str, np.ndarray], ratings: dict[str, float]) -> MarketInputs:
    idx = bdays(n)
    c = pd.DataFrame(closes, index=idx)
    v = pd.DataFrame(1e6, index=idx, columns=c.columns)
    rating = pd.DataFrame({s: r for s, r in ratings.items()}, index=idx)
    return MarketInputs(
        Bars(c, c * 1.01, c * 0.99, v), pd.Series(100.0, index=idx), rating,
        dict.fromkeys(c.columns, "Tech"),
        pd.DataFrame({"Tech": "Leading"}, index=idx), pd.DataFrame({"Tech": 1}, index=idx),
        pd.Series("Uptrend", index=idx),
    )


def test_missing_rating_not_scored() -> None:
    """UT-MKT-003.005.M04.T03: A stock without an RS rating that day gets no score."""
    n = 120
    inp = _inputs(n, {"A": np.full(n, 100.0), "B": np.full(n, 100.0)},
                  {"A": 80.0, "B": math.nan})
    table = score_frame(inp, [bdays(n)[-1]])
    assert set(table.index.get_level_values("symbol")) == {"A"}
    assert set(table.index.get_level_values("side")) == {"long", "short"}


def _extended_inputs(jump: float) -> MarketInputs:
    n = 120
    return _inputs(n, {"A": np.r_[np.full(n - 1, 100.0), 100.0 * (1 + jump)]}, {"A": 80.0})


def test_extended_long_penalty() -> None:
    """UT-MKT-003.006.M04.T01: A close 10% above the 20-day average loses 10 points."""
    table = score_frame(_extended_inputs(0.10), [bdays(120)[-1]])
    row = table.xs("long", level="side").iloc[0]
    assert row["penalty"] == 10.0
    reasons = pick_ideas(_day([{**_ROW, "penalty": 10.0, "extended": 0.10}]), "long",
                         date(2026, 11, 4))[0].reasons
    assert "10.0% above the 20-day average" in reasons


def test_score_floor() -> None:
    """UT-MKT-003.006.M04.T02: A raw score of 5 with a 10-point penalty is 0."""
    parts = {"rs": _one(0.25), "flow": _one(0.0), "setup": _one(0.0), "sector": _one(0.0),
             "regime": _one(0.0)}
    assert readiness_score(parts, _one(10.0))["A"].iloc[0] == 0.0


def test_not_extended_no_penalty() -> None:
    """UT-MKT-003.006.M04.T03: A close 5% above the 20-day average has no penalty."""
    table = score_frame(_extended_inputs(0.05), [bdays(120)[-1]])
    assert table.xs("long", level="side").iloc[0]["penalty"] == 0.0
    reasons = pick_ideas(_day([dict(_ROW)]), "long", date(2026, 11, 4))[0].reasons
    assert not any("20-day average" in r for r in reasons)


_ROW: dict[str, Any] = {
    "symbol": "A", "score": 75.0, "penalty": 0.0, "setup": "Squeeze", "trigger": 102.0,
    "stop": 95.0, "close": 100.0, "extended": 0.02, "rating": 90.0, "rs_extreme": True,
    "acc": 6.0, "dist": 1.0, "sector": "Tech", "quadrant": "Leading", "sector_rank": 2.0,
    "regime": "Uptrend",
}


def _day(rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(rows).set_index("symbol")


def test_top_ten_per_side() -> None:
    """UT-MKT-003.007.M04.T01: With 15 stocks at 60+, the 10 best are listed as ranks 1–10."""
    rows = [{**_ROW, "symbol": f"S{i:02d}", "score": 90.0 - i} for i in range(15)]
    ideas = pick_ideas(_day(rows), "long", date(2026, 11, 4))
    assert [i.symbol for i in ideas] == [f"S{i:02d}" for i in range(10)]
    assert [i.rank for i in ideas] == list(range(1, 11))
    assert {i.status for i in ideas} == {"list"}


def test_below_sixty_left_out() -> None:
    """UT-MKT-003.007.M04.T02: When the best score is 55 there are no ideas."""
    assert pick_ideas(_day([{**_ROW, "score": 55.0}]), "long", date(2026, 11, 4)) == []


def test_earnings_go_to_watch() -> None:
    """UT-MKT-003.007.M04.T03: Earnings in 3 trading days sends the idea to Watch."""
    ideas = pick_ideas(_day([dict(_ROW)]), "long", date(2026, 11, 4),
                       {"A": date(2026, 11, 9)})
    assert ideas[0].status == "watch"
    assert ideas[0].reasons[0] == "Earnings in 3 days"


def test_short_against_uptrend_to_watch() -> None:
    """UT-MKT-003.007.M04.T04: A short scoring 70 in an Uptrend goes to Watch."""
    ideas = pick_ideas(_day([{**_ROW, "score": 70.0}]), "short", date(2026, 11, 4))
    assert ideas[0].status == "watch"
    assert ideas[0].reasons[0] == "Against the Uptrend"


def test_reasons_in_plain_words() -> None:
    """UT-MKT-003.008.M04.T01: A listed idea has 1–5 reasons without codes or underscores."""
    reasons = pick_ideas(_day([dict(_ROW)]), "long", date(2026, 11, 4))[0].reasons
    assert 1 <= len(reasons) <= 5
    assert reasons[0] == "RS rating 90, RS line at a 3-month high"
    assert "6 accumulation and 1 distribution days in 25 sessions" in reasons
    assert "Squeeze, 2.0% below the trigger" in reasons
    assert not any("_" in r for r in reasons)


def test_no_false_reasons() -> None:
    """UT-MKT-003.008.M04.T02: An idea with no earnings and with the regime has no Watch reason."""
    ideas = pick_ideas(_day([dict(_ROW)]), "long", date(2026, 11, 4),
                       {"A": date(2026, 12, 20)})
    assert ideas[0].status == "list"
    assert not any("Earnings" in r or "Against" in r for r in ideas[0].reasons)


# ── M05: earnings ─────────────────────────────────────────────────────────────

def test_earnings_dates_read() -> None:
    """UT-MKT-003.009.M05.T01: The next earnings date is read per symbol."""
    calendars = {"AAA": {"Earnings Date": [date(2026, 11, 10)]}, "BBB": {}}
    got = next_earnings(["AAA", "BBB"], calendar=lambda s: calendars[s])
    assert got == {"AAA": date(2026, 11, 10), "BBB": None}


def test_yahoo_down() -> None:
    """UT-MKT-003.009.M05.T02: When Yahoo fails each symbol gets None and nothing raises."""

    def boom(_symbol: str) -> object:
        raise ConnectionError("down")

    assert next_earnings(["AAA", "BBB"], calendar=boom) == {"AAA": None, "BBB": None}


# ── M06: store ────────────────────────────────────────────────────────────────

def _rows(home: Path, sql: str) -> list[tuple[Any, ...]]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def _score_row(day: str, symbol: str) -> ScoreRow:
    return ScoreRow(day, symbol, "long", 70.0, 16.0, 12.0, 10.0, 15.0, 10.0, 0.0, "Squeeze",
                    102.0, None)


def test_idea_rows_round_trip(tmp_path: Path) -> None:
    """UT-MKT-003.010.M06.T01: Rows read back as written; re-writing a day replaces it."""
    store = MarketStore(tmp_path)
    store.write_idea_days(
        [],
        [_score_row("2026-11-04", "AAA"), _score_row("2026-11-05", "AAA")],
        [IdeaRow("2026-11-05", "long", "AAA", "list", 1, 70.0, "Tech", "Squeeze", 102.0, 95.0)],
        [ReasonRow("2026-11-05", "long", "AAA", 1, "RS rating 90")],
    )
    assert store.stored_idea_dates() == {"2026-11-04", "2026-11-05"}
    store.write_idea_days(["2026-11-05"], [_score_row("2026-11-05", "BBB")], [], [])
    store.close()
    assert _rows(tmp_path, "SELECT date, symbol, stop FROM stock_score ORDER BY date") == [
        ("2026-11-04", "AAA", None), ("2026-11-05", "BBB", None)]
    assert _rows(tmp_path, "SELECT COUNT(*) FROM ideas")[0][0] == 0
    assert _rows(tmp_path, "SELECT COUNT(*) FROM idea_reasons")[0][0] == 0


def test_idea_row_without_date(tmp_path: Path) -> None:
    """UT-MKT-003.010.M06.T02: An idea row with an empty date raises and writes nothing."""
    store = MarketStore(tmp_path)
    with pytest.raises(ValueError, match="without a date"):
        store.write_idea_days([], [_score_row("2026-11-04", "AAA")],
                              [IdeaRow("", "long", "AAA", "list", 1, 70.0, "Tech", "Squeeze",
                                       102.0, 95.0)], [])
    assert store.stored_idea_dates() == set()
    store.close()
