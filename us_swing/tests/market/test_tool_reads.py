"""Tests for MD-MKT-021.007.M02 — market/tool_reads.py: the read functions a built tool may call
in its sandbox (AI Desk v3 M7b). Stock names are made up."""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from us_swing.core.desk_contract import DB_NAME
from us_swing.market.tool_reads import reads

SYM = "ZZA"


def _daily_file(root: Path, symbol: str, days: int) -> list[str]:
    """Write ``days`` daily bars and return their dates."""
    start = datetime(2025, 1, 1)
    stamps = [start + timedelta(days=i) for i in range(days)]
    frame = pd.DataFrame({"ts": stamps, "open": [10.0 + i for i in range(days)],
                          "high": [11.0 + i for i in range(days)],
                          "low": [9.0 + i for i in range(days)],
                          "close": [10.5 + i for i in range(days)],
                          "volume": [1000.0 + i for i in range(days)]})
    (root / "1d").mkdir(parents=True, exist_ok=True)
    frame.to_parquet(root / "1d" / f"{symbol}.parquet")
    return [s.strftime("%Y-%m-%d") for s in stamps]


def _intraday_file(root: Path, minutes: int, year: int, stamps: list[datetime]) -> None:
    frame = pd.DataFrame({"ts": pd.to_datetime(stamps, utc=True),
                          "open": [1.0] * len(stamps), "high": [2.0] * len(stamps),
                          "low": [0.5] * len(stamps), "close": [1.5] * len(stamps),
                          "volume": [100.0] * len(stamps)})
    folder = root / f"{minutes}m" / SYM
    folder.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(folder / f"{year}.parquet")


def _stock_rs(home: Path) -> None:
    home.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(home / DB_NAME)
    try:
        con.execute("CREATE TABLE stock_rs (date TEXT, symbol TEXT, sector TEXT, score REAL, "
                    "rs_rating INTEGER, sector_rank INTEGER, sector_size INTEGER)")
        for n, day in enumerate(("2026-11-10", "2026-11-11", "2026-11-12")):
            con.execute("INSERT INTO stock_rs VALUES (?, ?, 'Tech', ?, ?, 3, 40)",
                        (day, SYM, 1.23456 + n, 70 + n))
            con.execute("INSERT INTO stock_rs VALUES (?, 'ZZB', 'Energy', 0.5, 20, 9, 22)",
                        (day,))
        con.commit()
    finally:
        con.close()


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_daily_bars(tmp_path: Path) -> None:
    """UT-MKT-021.007.M02.T01: 300 daily bars give the last 260, oldest first, as plain dicts."""
    days = _daily_file(tmp_path / "bt", SYM, 300)
    bars = reads(tmp_path / "desk", tmp_path / "bt")["daily_bars"](SYM, 260)
    assert len(bars) == 260
    assert [b["day"] for b in bars] == days[40:]
    assert set(bars[0]) == {"day", "open", "high", "low", "close", "volume"}
    assert bars[-1]["close"] == 10.5 + 299


def test_no_daily_file(tmp_path: Path) -> None:
    """UT-MKT-021.007.M02.T02: a stock with no daily file gives an empty list."""
    _daily_file(tmp_path / "bt", SYM, 5)
    assert reads(tmp_path / "desk", tmp_path / "bt")["daily_bars"]("ZZB") == []


def test_intraday_bars(tmp_path: Path) -> None:
    """UT-MKT-021.008.M02.T01: 30-minute bars of the last 2 New York days across a year end."""
    root = tmp_path / "bt"
    _intraday_file(root, 30, 2025, [datetime(2025, 12, 30, 14, 30, tzinfo=UTC),
                                    datetime(2025, 12, 31, 14, 30, tzinfo=UTC),
                                    datetime(2025, 12, 31, 15, 0, tzinfo=UTC)])
    _intraday_file(root, 30, 2026, [datetime(2026, 1, 2, 14, 30, tzinfo=UTC)])
    bars = reads(tmp_path / "desk", root)["intraday_bars"](SYM, 30, 2)
    assert [b["time"] for b in bars] == ["2025-12-31 09:30", "2025-12-31 10:00",
                                         "2026-01-02 09:30"]
    assert set(bars[0]) == {"time", "open", "high", "low", "close", "volume"}


@pytest.mark.parametrize(("minutes", "days", "why"), [
    (5, 10, "minutes must be 15 or 30"),
    (15.0, 10, "minutes must be 15 or 30"),
    (30, 0, "days must be 1 to 60"),
    (30, 61, "days must be 1 to 60"),
])
def test_intraday_bad_input(tmp_path: Path, minutes: object, days: object, why: str) -> None:
    """UT-MKT-021.008.M02.T02: bad minutes or days give a ValueError with the reason."""
    with pytest.raises(ValueError, match=why):
        reads(tmp_path / "desk", tmp_path / "bt")["intraday_bars"](SYM, minutes, days)


def test_desk_rows(tmp_path: Path) -> None:
    """UT-MKT-021.009.M02.T01: stock_rs rows of the last 2 dates, with date and menu columns."""
    home = tmp_path / "desk"
    _stock_rs(home)
    rows = reads(home, tmp_path / "bt")["desk_rows"]("stock_rs", SYM, 2)
    assert [r["date"] for r in rows] == ["2026-11-11", "2026-11-12"]
    assert set(rows[0]) == {"date", "symbol", "sector", "score", "rs_rating", "sector_rank",
                            "sector_size"}
    assert rows[0]["score"] == 2.2346 and rows[1]["rs_rating"] == 72


def test_desk_rows_bad_use(tmp_path: Path) -> None:
    """UT-MKT-021.009.M02.T02: an unknown source, sectors with a symbol and scores without one
    are refused; with no desk database the answer is empty."""
    read = reads(tmp_path / "desk", tmp_path / "bt")["desk_rows"]
    with pytest.raises(ValueError, match="unknown source news"):
        read("news", SYM)
    with pytest.raises(ValueError, match="sectors takes no symbol"):
        read("sectors", SYM)
    with pytest.raises(ValueError, match="scores needs a symbol"):
        read("scores")
    assert read("stock_rs", SYM) == []
    assert read("sectors") == []


def test_plain_and_read_only(tmp_path: Path) -> None:
    """UT-MKT-021.010.M02.T01: only plain values come back, the files stay as they were, and a
    lower-case name is upper-cased."""
    home, root = tmp_path / "desk", tmp_path / "bt"
    _stock_rs(home)
    _daily_file(root, SYM, 20)
    _intraday_file(root, 15, 2026, [datetime(2026, 1, 2, 14, 30, tzinfo=UTC)])
    files = [home / DB_NAME, root / "1d" / f"{SYM}.parquet", root / "15m" / SYM / "2026.parquet"]
    before = [_digest(f) for f in files]
    read = reads(home, root)
    got = (read["daily_bars"]("zza", 5) + read["intraday_bars"](" zza ", 15, 1)
           + read["desk_rows"]("stock_rs", "zza", 3))
    assert len(got) == 5 + 1 + 3
    assert all(isinstance(v, str | int | float) or v is None for row in got for v in row.values())
    assert [_digest(f) for f in files] == before
    assert set(read) == {"daily_bars", "intraday_bars", "desk_rows"}


@pytest.mark.parametrize("name", ["../x", "", "ABCDEFGHIJK", ".ZZA", "ZZ/A", 42])
def test_bad_symbol(tmp_path: Path, name: object) -> None:
    """UT-MKT-021.010.M02.T02: a bad stock name gives "bad symbol" before any file is read."""
    read = reads(tmp_path / "desk", tmp_path / "missing")
    for fn, args in (("daily_bars", (name,)), ("intraday_bars", (name,)),
                     ("desk_rows", ("stock_rs", name))):
        with pytest.raises(ValueError, match="bad symbol"):
            read[fn](*args)
