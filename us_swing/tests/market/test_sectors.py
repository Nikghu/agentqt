"""Tests for MD-MKT-002.001.M01–M04: member sectors, sector rules, stock RS and the store."""
from __future__ import annotations

import logging
import math
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tests.market.conftest import bdays
from us_swing.market.candles import member_sectors
from us_swing.market.rs import rs_scores, rs_table
from us_swing.market.sectors import quadrant, sector_lines, sector_table
from us_swing.market.store import MarketStore, SectorRow, StockRsRow


def _growth(n: int, rate: float) -> list[float]:
    return [100 * (1 + rate) ** t for t in range(n)]


def test_sector_map_from_list() -> None:
    """UT-MKT-002.001.M01.T01: Sector map from list; the IBKR form is matched."""
    rows = [("AAA", "AAA", "Tech"), ("BRK.B", "BRK B", "Financials"), ("CCC", "CCC", "Tech"),
            ("SPY", "SPY", "Fund")]
    found = member_sectors({"AAA", "BRK B", "CCC", "SPY"}, lambda: rows)
    assert found.sectors == {"AAA": "Tech", "BRK B": "Financials", "CCC": "Tech"}
    assert found.listed == 3


def test_stock_without_sector_left_out(caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-002.001.M01.T02: A stock without a sector is left out and logged."""
    rows = [("AAA", "AAA", "Tech"), ("BBB", "BBB", " ")]
    with caplog.at_level(logging.INFO):
        found = member_sectors({"AAA", "BBB"}, lambda: rows)
    assert found.sectors == {"AAA": "Tech"}
    assert "1 stock(s) have no sector" in caplog.text


def test_equal_weight_line() -> None:
    """UT-MKT-002.002.M02.T01: Equal-weight line: +10% and 0% gives 100 then 105."""
    closes = pd.DataFrame({"A": [100.0, 110.0], "B": [50.0, 50.0]}, index=bdays(2))
    lines, counts = sector_lines(closes, {"A": "X", "B": "X"})
    assert lines["X"].tolist() == pytest.approx([100.0, 105.0])
    assert counts["X"].tolist() == [2, 2]


def test_missing_bar_left_out() -> None:
    """UT-MKT-002.002.M02.T02: A member with no bar on day 2 is left out of that day's average."""
    closes = pd.DataFrame({"A": [100.0, 110.0], "B": [100.0, np.nan], "C": [100.0, 100.0]},
                          index=bdays(2))
    lines, counts = sector_lines(closes, {"A": "X", "B": "X", "C": "X"})
    assert lines["X"].iloc[-1] == pytest.approx(105.0)
    assert counts["X"].tolist() == [3, 2]


def _lines(n: int, rates: dict[str, float]) -> pd.DataFrame:
    return pd.DataFrame({k: _growth(n, r) for k, r in rates.items()}, index=bdays(n))


def test_rank_by_relative_moves() -> None:
    """UT-MKT-002.003.M02.T01: With a flat SPY the fastest sector ranks 1."""
    lines = _lines(130, {"Slow": 0.0005, "Fast": 0.002, "Mid": 0.001})
    spy = pd.Series(100.0, index=lines.index)
    last = sector_table(lines, spy).xs(lines.index[-1], level="date")
    assert last["rank"].to_dict() == {"Fast": 1, "Mid": 2, "Slow": 3}
    assert last.loc["Fast", "rel_1m"] == pytest.approx(1.002 ** 21 - 1)


def test_too_short_for_six_months() -> None:
    """UT-MKT-002.003.M02.T02: With 100 days there is no 6-month move and no rank."""
    lines = _lines(100, {"A": 0.001, "B": 0.002})
    last = sector_table(lines, pd.Series(100.0, index=lines.index)).xs(lines.index[-1],
                                                                        level="date")
    assert last["rel_6m"].isna().all()
    assert last["rank"].isna().all()


def test_ratio_and_momentum_above_100() -> None:
    """UT-MKT-002.004.M02.T01: A sector speeding away from SPY has ratio and momentum above 100."""
    idx = bdays(120)
    t = np.arange(120)
    lines = pd.DataFrame({"A": 100 * np.exp(0.00005 * t ** 2)}, index=idx)
    last = sector_table(lines, pd.Series(100.0, index=idx)).xs(idx[-1], level="date")
    assert last.loc["A", "rs_ratio"] > 100
    assert last.loc["A", "rs_momentum"] > 100
    assert last.loc["A", "quadrant"] == "Leading"


def test_same_as_spy() -> None:
    """UT-MKT-002.004.M02.T02: A line equal to SPY has ratio 100 and momentum 100."""
    idx = bdays(120)
    spy = pd.Series(_growth(120, 0.001), index=idx)
    last = sector_table(pd.DataFrame({"A": spy}), spy).xs(idx[-1], level="date")
    assert last.loc["A", "rs_ratio"] == pytest.approx(100.0)
    assert last.loc["A", "rs_momentum"] == pytest.approx(100.0)


def test_four_quadrants() -> None:
    """UT-MKT-002.005.M02.T01: Four ratio and momentum pairs give the four quadrants."""
    assert quadrant(102, 101) == "Leading"
    assert quadrant(102, 99) == "Weakening"
    assert quadrant(98, 99) == "Lagging"
    assert quadrant(98, 101) == "Improving"


def test_exactly_100_is_leading() -> None:
    """UT-MKT-002.005.M02.T02: Ratio 100 and momentum 100 is Leading."""
    assert quadrant(100.0, 100.0) == "Leading"


def test_missing_value_no_quadrant() -> None:
    """UT-MKT-002.005.M02.T03: A missing ratio gives no quadrant."""
    assert quadrant(math.nan, 101) is None
    assert quadrant(None, 101) is None


def _rs_closes(n: int, rates: dict[str, float]) -> pd.DataFrame:
    return pd.DataFrame({k: _growth(n, r) for k, r in rates.items()}, index=bdays(n))


def test_score_and_rating() -> None:
    """UT-MKT-002.006.M03.T01: Score follows the formula; the best is 99, the worst 20."""
    rates = {"A": 0.0001, "B": 0.0002, "C": 0.0003, "D": 0.0004, "E": 0.0005}
    scores = rs_scores(_rs_closes(260, rates))
    k = 1.0005
    expected = 0.4 * (k ** 63 - 1) + 0.2 * (k ** 126 - 1) + 0.2 * (k ** 189 - 1) \
        + 0.2 * (k ** 252 - 1)
    assert scores["E"].iloc[-1] == pytest.approx(expected)
    table = rs_table(scores, dict.fromkeys(rates, "X"))
    last = table.xs(scores.index[-1], level="date")
    assert last.loc["E", "rs_rating"] == 99
    assert last.loc["A", "rs_rating"] == 20


def test_short_history_no_score() -> None:
    """UT-MKT-002.006.M03.T02: A stock with 200 bars gets no score and no rating."""
    closes = _rs_closes(260, {"A": 0.001, "B": 0.002})
    closes.iloc[:60, 1] = np.nan
    scores = rs_scores(closes)
    assert math.isnan(scores["B"].iloc[-1])
    last = rs_table(scores, {"A": "X", "B": "X"}).xs(scores.index[-1], level="date")
    assert list(last.index) == ["A"]
    assert last.loc["A", "rs_rating"] == 99


def test_rank_inside_sector() -> None:
    """UT-MKT-002.007.M03.T01: Three stocks in one sector rank 1, 2, 3 with size 3."""
    rates = {"A": 0.0003, "B": 0.0001, "C": 0.0002, "Z": 0.003}
    scores = rs_scores(_rs_closes(260, rates))
    sector_of = {"A": "X", "B": "X", "C": "X", "Z": "Y"}
    last = rs_table(scores, sector_of).xs(scores.index[-1], level="date")
    assert last.loc[["A", "C", "B"], "sector_rank"].tolist() == [1, 2, 3]
    assert set(last.loc[["A", "B", "C"], "sector_size"]) == {3}
    assert last.loc["Z", "sector_rank"] == 1
    assert last.loc["Z", "sector"] == "Y"


def test_unrated_stock_no_sector_rank() -> None:
    """UT-MKT-002.007.M03.T02: A stock without a score gets no sector rank and is not counted."""
    closes = _rs_closes(260, {"A": 0.001, "B": 0.002})
    closes.iloc[:100, 0] = np.nan
    last = rs_table(rs_scores(closes), {"A": "X", "B": "X"}).xs(closes.index[-1], level="date")
    assert "A" not in last.index
    assert last.loc["B", "sector_size"] == 1


def _sector(day: str, sector: str = "Tech") -> SectorRow:
    return SectorRow(day, sector, 101.0, 0.01, 0.02, None, 1, 100.5, 99.5, "Weakening", 60)


def _stock(day: str, symbol: str) -> StockRsRow:
    return StockRsRow(day, symbol, "Tech", 0.25, 90, 1, 2)


def _rows(home: Path, sql: str) -> list[tuple[object, ...]]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def test_sector_rows_round_trip(tmp_path: Path) -> None:
    """UT-MKT-002.008.M04.T01: Rows read back as written; re-writing a day replaces it."""
    store = MarketStore(tmp_path)
    store.write_sector_days([_sector("2026-11-04"), _sector("2026-11-05")],
                            [_stock("2026-11-04", "AAA"), _stock("2026-11-05", "AAA"),
                             _stock("2026-11-05", "BBB")])
    assert store.stored_sector_dates() == {"2026-11-04", "2026-11-05"}
    store.write_sector_days([_sector("2026-11-05", "Energy")], [_stock("2026-11-05", "CCC")])
    store.close()
    assert _rows(tmp_path, "SELECT * FROM sector_daily ORDER BY date") == [
        ("2026-11-04", "Tech", 101.0, 0.01, 0.02, None, 1, 100.5, 99.5, "Weakening", 60),
        ("2026-11-05", "Energy", 101.0, 0.01, 0.02, None, 1, 100.5, 99.5, "Weakening", 60),
    ]
    assert _rows(tmp_path, "SELECT date, symbol FROM stock_rs ORDER BY date, symbol") == [
        ("2026-11-04", "AAA"), ("2026-11-05", "CCC"),
    ]


def test_row_without_date_rejected(tmp_path: Path) -> None:
    """UT-MKT-002.008.M04.T02: A sector row with an empty date raises and writes nothing."""
    store = MarketStore(tmp_path)
    with pytest.raises(ValueError, match="without a date"):
        store.write_sector_days([_sector("2026-11-04"), _sector("")], [])
    assert store.stored_sector_dates() == set()
    store.close()
