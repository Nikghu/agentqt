"""Tests for MD-MKT-021.001.M01 (market/table_tools.py)."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path

import pytest

from tests.market.conftest import write_candles
from us_swing.core.desk_contract import DB_NAME
from us_swing.market import table_tools
from us_swing.market.score import NO_SETUP
from us_swing.market.store import MarketStore, ScoreRow, StockRsRow, TopupRow
from us_swing.market.table_tools import (
    FEW_BARS,
    NO_BARS,
    NO_EARNINGS,
    NO_RS,
    NO_SETUP_REASON,
    NOT_SCORED,
    atr_pct,
    daily_close,
    earnings,
    rs_rank,
    setup,
)

DAY = "2026-11-06"


def put_rs(home: Path, rows: list[tuple[str, str, int]]) -> None:
    """Write stock_rs rows given as (date, symbol, rating)."""
    store = MarketStore(home)
    store.write_sector_days(
        [], [StockRsRow(d, s, "Tech", 1.0, r, 1, 10) for d, s, r in rows])
    store.close()


def put_scores(
    home: Path, rows: list[tuple[str, str, float, str, float | None, float | None]]
) -> None:
    """Write stock_score rows given as (symbol, side, score, setup, trigger, stop)."""
    store = MarketStore(home)
    store.write_idea_days(
        [DAY],
        [ScoreRow(DAY, s, side, sc, 0, 0, 0, 0, 0, 0, name, trg, stp)
         for s, side, sc, name, trg, stp in rows],
        [], [])
    store.close()


def put_topup(home: Path, symbol: str, day: str, close: float) -> None:
    """Write one desk-copy daily bar."""
    store = MarketStore(home)
    store.write_topup([TopupRow(symbol, day, close, close, close, close, 1, "2026-01-01")])
    store.close()


@pytest.fixture
def candles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Callable[[dict[str, Sequence[float]]], Path]:
    """Write a candles.db and point the tools at it."""

    def make(series: dict[str, Sequence[float]]) -> Path:
        path = tmp_path / "candles.db"
        write_candles(path, series)
        monkeypatch.setattr(table_tools, "CANDLE_DB", path)
        return path

    return make


@pytest.fixture
def home(tmp_path: Path) -> Path:
    """An empty desk home folder."""
    folder = tmp_path / "desk"
    folder.mkdir()
    return folder


def fake_earnings(
    monkeypatch: pytest.MonkeyPatch, dates: dict[str, date | None]
) -> None:
    """Replace the Yahoo earnings lookup."""
    monkeypatch.setattr(table_tools, "next_earnings", lambda symbols: dates)


def test_daily_close_two_symbols(candles: Callable[..., Path], home: Path) -> None:
    """UT-MKT-021.001.M01.T01: Last close of two symbols."""
    candles({"AAA": [10.0, 11.234], "BBB": [20.0, 21.0, 22.567]})
    result = daily_close(home, ["AAA", "BBB"])
    assert result.rows == [{"symbol": "AAA", "close": 11.23}, {"symbol": "BBB", "close": 22.57}]
    assert result.missing == {}
    assert not result.is_error


def test_daily_close_no_bars(candles: Callable[..., Path], home: Path) -> None:
    """UT-MKT-021.001.M01.T02: A symbol with no bars is missing, the other keeps its row."""
    candles({"AAA": [10.0, 12.0]})
    result = daily_close(home, ["AAA", "ZZZ"])
    assert result.rows == [{"symbol": "AAA", "close": 12.0}]
    assert result.missing == {"ZZZ": NO_BARS}


def test_daily_close_topup_newer(candles: Callable[..., Path], home: Path) -> None:
    """UT-MKT-021.001.M01.T03: A newer bar only in the desk copy gives the top-up close."""
    candles({"AAA": [10.0, 12.0]})
    put_topup(home, "AAA", "2025-01-10", 15.5)
    result = daily_close(home, ["AAA"])
    assert result.rows == [{"symbol": "AAA", "close": 15.5}]


def test_rs_rank_latest_day(home: Path) -> None:
    """UT-MKT-021.002.M01.T01: RS rank is the rating of the latest day, as an int."""
    put_rs(home, [("2026-11-05", "AAA", 50), (DAY, "AAA", 88)])
    result = rs_rank(home, ["AAA"])
    assert result.rows == [{"symbol": "AAA", "rs_rank": 88}]
    assert isinstance(result.rows[0]["rs_rank"], int)
    assert result.missing == {}


def test_rs_rank_missing_symbol_and_no_db(home: Path, tmp_path: Path) -> None:
    """UT-MKT-021.002.M01.T02: Unknown symbol and no desk.db are missing, with no error."""
    put_rs(home, [(DAY, "AAA", 70)])
    result = rs_rank(home, ["AAA", "ZZZ"])
    assert result.missing == {"ZZZ": NO_RS}
    empty = tmp_path / "nodb"
    empty.mkdir()
    bare = rs_rank(empty, ["AAA", "BBB"])
    assert bare.rows == []
    assert bare.missing == {"AAA": NO_RS, "BBB": NO_RS}
    assert not bare.is_error


def test_atr_pct_constant_range(candles: Callable[..., Path], home: Path) -> None:
    """UT-MKT-021.003.M01.T01: A fixed 2.00 range on close 100 gives 2.0 percent."""
    candles({"AAA": [100.0] * 20})
    result = atr_pct(home, ["AAA"])
    assert result.rows == [{"symbol": "AAA", "atr_pct": 2.0}]
    assert result.missing == {}


def test_atr_pct_few_bars(candles: Callable[..., Path], home: Path) -> None:
    """UT-MKT-021.003.M01.T02: Ten bars are too few, so the symbol is missing."""
    candles({"AAA": [100.0] * 10})
    result = atr_pct(home, ["AAA"])
    assert result.rows == []
    assert result.missing == {"AAA": FEW_BARS}


def test_setup_better_side_and_tie(home: Path) -> None:
    """UT-MKT-021.004.M01.T01: Higher score picks the side; a tie picks long."""
    put_scores(home, [
        ("AAA", "long", 70, "Breakout", 51.0, 47.0),
        ("AAA", "short", 40, "Breakdown", 40.0, 44.0),
        ("BBB", "short", 60, "Breakdown", 30.0, 33.0),
        ("BBB", "long", 60, "Pullback", 31.0, 28.0),
    ])
    result = setup(home, ["AAA", "BBB"])
    assert result.rows == [
        {"symbol": "AAA", "side": "long", "setup": "Breakout", "trigger": 51.0, "stop": 47.0},
        {"symbol": "BBB", "side": "long", "setup": "Pullback", "trigger": 31.0, "stop": 28.0},
    ]
    assert result.missing == {}


def test_setup_no_setup_row(home: Path) -> None:
    """UT-MKT-021.004.M01.T02: A best row with no setup shows none and empty levels."""
    put_scores(home, [("AAA", "long", 70, NO_SETUP, 51.0, 47.0)])
    result = setup(home, ["AAA"])
    assert result.rows == [
        {"symbol": "AAA", "side": "long", "setup": "none", "trigger": None, "stop": None}]
    assert result.missing == {"AAA.trigger": NO_SETUP_REASON, "AAA.stop": NO_SETUP_REASON}


def test_setup_not_scored(home: Path) -> None:
    """UT-MKT-021.004.M01.T03: A symbol with no score row is missing."""
    put_scores(home, [("AAA", "long", 70, "Breakout", 51.0, 47.0)])
    result = setup(home, ["AAA", "ZZZ"])
    assert [r["symbol"] for r in result.rows] == ["AAA"]
    assert result.missing == {"ZZZ": NOT_SCORED}


def test_earnings_over_weekend(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-MKT-021.005.M01.T01: Friday data day to next Tuesday is 2 trading days."""
    put_rs(home, [(DAY, "AAA", 70)])
    fake_earnings(monkeypatch, {"AAA": date(2026, 11, 10)})
    result = earnings(home, ["AAA"])
    assert result.rows == [{"symbol": "AAA", "earn_days": 2}]


def test_earnings_no_date_or_past(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-MKT-021.005.M01.T02: No date and a date before the data day are both missing."""
    put_rs(home, [(DAY, "AAA", 70)])
    fake_earnings(monkeypatch, {"AAA": None, "BBB": date(2026, 11, 2)})
    result = earnings(home, ["AAA", "BBB"])
    assert result.rows == []
    assert result.missing == {"AAA": NO_EARNINGS, "BBB": NO_EARNINGS}


def test_earnings_flag_only_when_near(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-MKT-021.005.M01.T03: Only the symbol 2 trading days out gets a flag."""
    put_rs(home, [(DAY, "AAA", 70)])
    fake_earnings(monkeypatch, {"AAA": date(2026, 11, 10), "BBB": date(2026, 11, 19)})
    result = earnings(home, ["AAA", "BBB"])
    assert result.rows[1] == {"symbol": "BBB", "earn_days": 9}
    assert result.flags == {"AAA": "earnings in 2 trading days"}


def test_all_tools_read_only(
    candles: Callable[..., Path], home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """UT-MKT-021.006.M01.T01: All five tools succeed and leave every file unchanged."""
    path = candles({"AAA": [100.0] * 20})
    put_rs(home, [(DAY, "AAA", 70)])
    put_scores(home, [("AAA", "long", 70, "Breakout", 51.0, 47.0)])
    fake_earnings(monkeypatch, {"AAA": date(2026, 11, 10)})
    desk = home / DB_NAME
    before = (path.read_bytes(), desk.read_bytes())
    for tool in (daily_close, rs_rank, atr_pct, setup, earnings):
        result = tool(home, ["AAA"])
        assert not result.is_error
        assert len(result.rows) == 1
    assert (path.read_bytes(), desk.read_bytes()) == before


def test_empty_symbols_open_nothing(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-MKT-021.006.M01.T02: No symbols gives an empty result without opening a file."""
    monkeypatch.setattr(table_tools, "CANDLE_DB", home / "missing.db")
    for tool in (daily_close, rs_rank, atr_pct, setup, earnings):
        result = tool(home, [])
        assert result.rows == []
        assert result.missing == {}
        assert result.flags == {}
    assert not (home / DB_NAME).exists()


def test_missing_candle_file_raises(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-MKT-021.006.M01.T03: A missing candle file raises, with no made-up row."""
    monkeypatch.setattr(table_tools, "CANDLE_DB", home / "missing.db")
    with pytest.raises(FileNotFoundError, match="^the candle database was not found$"):
        daily_close(home, ["AAA"])


def test_null_score(home: Path) -> None:
    """UT-MKT-021.004.M01.T04: A row with no score never wins and never fails the tool."""
    put_scores(home, [("AAA", "long", None, "flag", 10.0, 9.0),  # type: ignore[list-item]
                      ("AAA", "short", 40.0, "flag", 8.0, 9.5)])
    assert setup(home, ["AAA"]).rows == [
        {"symbol": "AAA", "side": "short", "setup": "flag", "trigger": 8.0, "stop": 9.5}]
