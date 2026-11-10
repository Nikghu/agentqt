"""Tests for MD-MKT-001.013.M06 — market/candle_check.py, and the desk copy in
MD-MKT-001.001.M01 (candles.py) and MD-MKT-001.007.M04 (store.py)."""
from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterable
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from us_swing.core.desk_contract import StepContext
from us_swing.core.desk_steps import STEP_PATHS
from us_swing.market.candle_check import (
    CandleCheckError,
    CandleCheckStep,
    last_closed_day,
    topup_rows,
)
from us_swing.market.candles import CandleReader
from us_swing.market.regime_view import latest_spy_day
from us_swing.market.store import MarketStore, TopupRow

NY = ZoneInfo("America/New_York")
WED_0830 = datetime(2026, 11, 11, 8, 30, tzinfo=NY)
DAYS = pd.bdate_range(end="2026-11-10", periods=30)
TUE, MON = "2026-11-10", "2026-11-09"
MEMBERS = [f"S{i:03d}" for i in range(100)]


class FakeSend:
    """Records alert messages instead of sending them."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    def __call__(self, text: str) -> bool:
        self.sent.append(text)
        return True


def _candles(path: Path, last: dict[str, str] | None = None,
             symbols: Iterable[str] = (*MEMBERS, "SPY")) -> Path:
    """Write daily bars to ``TUE`` (or the symbol's own last day); close 100, volume 1000."""
    last = last or {}
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE price_1d (symbol TEXT, datetime TEXT, open REAL, high REAL, "
                "low REAL, close REAL, volume REAL)")
    for sym in symbols:
        con.executemany("INSERT INTO price_1d VALUES (?, ?, 100, 101, 99, 100, 1000)",
                        [(sym, d.isoformat()) for d in DAYS if d.date().isoformat()
                         <= last.get(sym, TUE)])
    con.commit()
    con.close()
    return path


def _yahoo(close: float = 100.0, volume: float = 2000.0) -> pd.DataFrame:
    return pd.DataFrame({"open": close, "high": close + 1, "low": close - 1, "close": close,
                         "volume": volume}, index=DAYS)


class FakeFetch:
    """Yahoo stand-in: gives bars for the asked stocks, or none at all."""

    def __init__(self, empty: bool = False) -> None:
        self.calls: list[list[str]] = []
        self._empty = empty

    def __call__(self, symbols: list[str], _start: date, _end: date) -> dict[str, pd.DataFrame]:
        self.calls.append(symbols)
        return {} if self._empty else {s: _yahoo() for s in symbols}


def _step(candles: Path, fetch: FakeFetch, send: FakeSend | None = None,
          now: datetime = WED_0830) -> CandleCheckStep:
    return CandleCheckStep(candles, fetch, lambda: [(s, s) for s in MEMBERS], lambda: now,
                           send or FakeSend())


def _ctx(home: Path) -> StepContext:
    return StepContext(7, "morning", WED_0830, home)


def _copy(home: Path) -> list[tuple[str, str, int]]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute("SELECT symbol, date, volume FROM candle_topup ORDER BY symbol").fetchall()
    finally:
        con.close()


def test_target_day() -> None:
    """UT-MKT-001.013.M06.T01: Target day (SRD-MKT-001.013)."""
    assert last_closed_day(WED_0830) == date(2026, 11, 10)
    assert last_closed_day(datetime(2026, 11, 11, 16, 5, tzinfo=NY)) == date(2026, 11, 11)
    assert last_closed_day(datetime(2026, 11, 16, 8, 30, tzinfo=NY)) == date(2026, 11, 13)


def test_up_to_date_no_fetch(tmp_path: Path) -> None:
    """UT-MKT-001.013.M06.T02: Up to date: no fetch (SRD-MKT-001.013)."""
    fetch = FakeFetch()
    _step(_candles(tmp_path / "candles.db"), fetch)(_ctx(tmp_path / "desk"))
    assert fetch.calls == [] and _copy(tmp_path / "desk") == []


def test_behind_stocks_filled(tmp_path: Path) -> None:
    """UT-MKT-001.014.M06.T01: Behind stocks filled into the desk copy (SRD-MKT-001.014)."""
    candles = _candles(tmp_path / "candles.db", {s: MON for s in MEMBERS[:3]})
    before = candles.read_bytes()
    _step(candles, FakeFetch())(_ctx(tmp_path / "desk"))
    assert _copy(tmp_path / "desk") == [(s, TUE, 1000) for s in MEMBERS[:3]]
    assert candles.read_bytes() == before


def test_volume_scaled() -> None:
    """UT-MKT-001.014.M06.T02: Volume scaled by the IBKR/Yahoo median (SRD-MKT-001.014)."""
    shared = DAYS[-4:-1]
    ibkr = pd.DataFrame({"close": 100.0, "volume": [500.0, 500.0, 600.0]}, index=shared)
    yahoo = _yahoo(volume=1000.0).loc[DAYS[-4:]]
    yahoo.loc[DAYS[-1], "volume"] = 1_000_000.0
    rows = topup_rows({"AAA": ibkr}, {"AAA": yahoo}, date(2026, 11, 10), "t")
    assert rows == [TopupRow("AAA", TUE, 100.0, 101.0, 99.0, 100.0, 500_000, "t")]


def test_mismatch_or_short_overlap_skipped() -> None:
    """UT-MKT-001.014.M06.T03: Price mismatch or short overlap skips the stock."""
    ibkr = pd.DataFrame({"close": 100.0, "volume": 1000.0}, index=DAYS[:-1])
    off = _yahoo()
    off.loc[DAYS[-3], "close"] = 102.0
    short = pd.DataFrame({"close": 100.0, "volume": 1000.0}, index=DAYS[-3:-1])
    rows = topup_rows({"OFF": ibkr, "SHORT": short}, {"OFF": off, "SHORT": _yahoo()},
                      date(2026, 11, 10), "t")
    assert rows == []


def _store_copy(home: Path, rows: list[TopupRow]) -> None:
    store = MarketStore(home)
    try:
        store.write_topup(rows)
    finally:
        store.close()


def test_reader_adds_copy_days(tmp_path: Path) -> None:
    """UT-MKT-001.015.M01.T01: Reader adds copy days candles.db lacks (SRD-MKT-001.015)."""
    candles = _candles(tmp_path / "candles.db", {"S000": MON}, ["S000"])
    home = tmp_path / "desk"
    _store_copy(home, [TopupRow("S000", TUE, 1, 2, 0.5, 105, 9, "t"),
                       TopupRow("NEW", TUE, 1, 2, 0.5, 7, 9, "t")])
    reader = CandleReader(candles, home)
    bars = reader.read(["S000"])
    assert bars.closes.index[-1] == pd.Timestamp(TUE) and bars.closes["S000"].iloc[-1] == 105
    assert reader.symbols() == {"S000", "NEW"}
    assert CandleReader(candles).read(["S000"]).closes.index[-1] == pd.Timestamp(MON)


def test_candles_db_wins(tmp_path: Path) -> None:
    """UT-MKT-001.015.M01.T02: candles.db wins over the copy (SRD-MKT-001.015)."""
    candles = _candles(tmp_path / "candles.db", symbols=["S000"])
    home = tmp_path / "desk"
    _store_copy(home, [TopupRow("S000", TUE, 1, 2, 0.5, 105, 9, "t")])
    assert CandleReader(candles, home).read(["S000"]).closes["S000"].iloc[-1] == 100


def test_copy_trimmed(tmp_path: Path) -> None:
    """UT-MKT-001.015.M04.T01: Copy rows trimmed once IBKR has the day (SRD-MKT-001.015)."""
    home = tmp_path / "desk"
    _store_copy(home, [TopupRow("S000", TUE, 1, 2, 0.5, 105, 9, "t")])
    candles = _candles(tmp_path / "candles.db")
    _step(candles, FakeFetch())(_ctx(home))
    assert _copy(home) == []


def test_latest_spy_day_sees_copy(tmp_path: Path) -> None:
    """UT-MKT-001.015.M01.T03: Latest SPY day sees the copy (SRD-MKT-001.015)."""
    candles = _candles(tmp_path / "candles.db", {"SPY": MON}, ["SPY"])
    home = tmp_path / "desk"
    _store_copy(home, [TopupRow("SPY", TUE, 1, 2, 0.5, 105, 9, "t")])
    store = MarketStore(home)
    try:
        assert latest_spy_day(candles) == MON
        assert latest_spy_day(candles, store) == TUE
    finally:
        store.close()


def test_still_behind_stops_run(tmp_path: Path) -> None:
    """UT-MKT-001.016.M06.T01: Still behind stops the run with an alert (SRD-MKT-001.016)."""
    candles = _candles(tmp_path / "candles.db", {s: MON for s in MEMBERS[:5]})
    send = FakeSend()
    with pytest.raises(CandleCheckError, match="5 of 101"):
        _step(candles, FakeFetch(empty=True), send)(_ctx(tmp_path / "desk"))
    assert len(send.sent) == 1 and "Candles not up to date" in send.sent[0]


def test_two_percent_rule_and_spy(tmp_path: Path) -> None:
    """UT-MKT-001.016.M06.T02: 2% rule and SPY (SRD-MKT-001.016)."""
    two = _candles(tmp_path / "two.db", {s: MON for s in MEMBERS[:2]})
    _step(two, FakeFetch(empty=True))(_ctx(tmp_path / "a"))
    spy = _candles(tmp_path / "spy.db", {"SPY": MON})
    with pytest.raises(CandleCheckError):
        _step(spy, FakeFetch(empty=True))(_ctx(tmp_path / "b"))


def test_no_candle_file(tmp_path: Path) -> None:
    """UT-MKT-001.016.M06.T03: No candle file (SRD-MKT-001.016)."""
    with pytest.raises(CandleCheckError):
        _step(tmp_path / "missing.db", FakeFetch())(_ctx(tmp_path / "desk"))


def test_check_logs_counts(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-001.017.M06.T01: Check logs the counts (SRD-MKT-001.017)."""
    candles = _candles(tmp_path / "candles.db", {s: MON for s in MEMBERS[:3]})

    def two_of_three(symbols: list[str], _s: date, _e: date) -> dict[str, pd.DataFrame]:
        return {s: _yahoo() for s in symbols[:2]}

    step = CandleCheckStep(candles, two_of_three, lambda: [(s, s) for s in MEMBERS],
                           lambda: WED_0830, FakeSend())
    with caplog.at_level(logging.INFO, logger="us_swing.market.candle_check"):
        step(_ctx(tmp_path / "desk"))
    assert any("3 stock(s) behind 2026-11-10, 2 filled from Yahoo Finance, 1 still behind"
               in r.getMessage() and r.getMessage().startswith("[Candles]")
               for r in caplog.records)


def test_candle_check_is_first_step() -> None:
    """UT-MKT-001.013.M06.T03: Candle check is the first desk step (SRD-MKT-001.013)."""
    assert STEP_PATHS[0] == "us_swing.market.candle_check:CandleCheckStep"


def test_utc_clock_default() -> None:
    """UT-MKT-001.013.M06.T01: The default clock is time-zone aware (SRD-MKT-001.013)."""
    step = CandleCheckStep(Path("x"))
    assert step._clock().tzinfo is UTC


def test_unsettled_copy_fetched_again(tmp_path: Path) -> None:
    """UT-MKT-001.015.M04.T02: A copy bar fetched before 16:30 ET of its day is fetched again."""
    home = tmp_path / "desk"
    early = datetime(2026, 11, 10, 16, 5, tzinfo=NY).astimezone(UTC).isoformat(timespec="seconds")
    _store_copy(home, [TopupRow("S000", TUE, 1, 2, 0.5, 90, 9, early)])
    candles = _candles(tmp_path / "candles.db", {"S000": MON})
    fetch = FakeFetch()
    _step(candles, fetch)(_ctx(home))
    assert fetch.calls == [["S000"]]
    assert _copy(home) == [("S000", TUE, 1000)]
