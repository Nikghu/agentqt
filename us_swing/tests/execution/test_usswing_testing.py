"""
Module: MD-EXE-022.015.M06 — tests
Parent SRD: SRD-EXE-022.015, SRD-EXE-022.016

The ``usswing.testing`` kit and the ``indicator check`` command line.
"""
from __future__ import annotations

import io
import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd
import pytest

from tests.execution.plugin_helpers import SWING_PLUS, swing_plus_source, write_plugin
from usswing import testing

from us_swing.core.indicator_plugins import builtin_names, check_file
from us_swing.core.indicator_plugins._cli import run_indicator_command

_DAYS = ("2026-11-16", "2026-11-17", "2026-11-18")
_BARS_PER_DAY = 130


def _candle_db(path: Path, symbol: str = "AAPL") -> Path:
    """A candle file shaped like the tool's: 3 market days of 3m candles plus daily ones."""
    with closing(sqlite3.connect(path)) as conn:
        for table in ("price_3m", "price_1d"):
            conn.execute(f"CREATE TABLE {table} (symbol TEXT, datetime TEXT, open REAL, "
                         "high REAL, low REAL, close REAL, volume INTEGER)")
        rows = []
        for day in _DAYS:
            start = pd.Timestamp(f"{day} 14:30")
            for i in range(_BARS_PER_DAY):
                price = 100 + (i % 17) * 0.3
                rows.append((symbol, (start + pd.Timedelta(minutes=3 * i)).isoformat(),
                             price, price + 0.5, price - 0.5, price, 1000))
        conn.executemany("INSERT INTO price_3m VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
        conn.executemany("INSERT INTO price_1d VALUES (?, ?, ?, ?, ?, ?, ?)",
                         [(symbol, f"{day}T00:00:00", 100, 101, 99, 100, 5000) for day in _DAYS])
        conn.commit()
    return path


@pytest.fixture
def db(tmp_path: Path) -> Path:
    return _candle_db(tmp_path / "candles.db")


def test_load_candles_read_only(db: Path) -> None:
    """UT-EXE-022.015.M06.T01: Load candles read-only."""
    frames = testing.load_candles("AAPL", ["3m"], days=2, db_path=db)

    three = frames["3m"]
    days = three["datetime"].dt.tz_convert("America/New_York").dt.date.astype(str)
    assert sorted(set(days)) == ["2026-11-17", "2026-11-18"]
    assert len(three) == 2 * _BARS_PER_DAY
    assert list(three.columns) == ["datetime", "open", "high", "low", "close", "volume"]
    with closing(testing.connect(db)) as conn, pytest.raises(sqlite3.OperationalError):
        conn.execute("DELETE FROM price_3m")


def test_run_gives_values_and_debug_table(db: Path) -> None:
    """UT-EXE-022.015.M06.T02: Run gives values and a debug table."""
    spec = check_file(SWING_PLUS, builtin_names=builtin_names()).spec
    assert spec is not None
    candles = testing.load_candles("AAPL", ["3m"], days=3, db_path=db)

    result = testing.run(spec.indicator_class, candles, {"Candles": 10})
    table = result.table()

    assert list(table.columns) == ["time", "value", "Swing high", "Swing low"]
    assert len(table) == 3 * _BARS_PER_DAY
    assert table["value"].iloc[:10].isna().all() and not table["value"].iloc[10:].isna().any()


def test_command_line_check_passes(db: Path, tmp_path: Path) -> None:
    """UT-EXE-022.016.M06.T01: Command line check passes."""
    trace = tmp_path / "t.csv"
    out = io.StringIO()

    code = run_indicator_command(["check", str(SWING_PLUS), "--symbols", "AAPL",
                                  "--trace", str(trace), "--db", str(db)], out)

    text = out.getvalue()
    assert code == 0
    assert "✔ SWING_PLUS 1.0 passed" in text and "✔ AAPL:" in text
    table = pd.read_csv(trace)
    assert list(table.columns)[:3] == ["symbol", "time", "value"]
    assert set(table["symbol"]) == {"AAPL"}


def test_command_line_check_refuses(db: Path, tmp_path: Path) -> None:
    """UT-EXE-022.016.M06.T02: Command line check refuses."""
    broken = write_plugin(tmp_path, "bad.py", swing_plus_source(('    version = "1.0"\n', "")))
    out = io.StringIO()

    code = run_indicator_command(["check", str(broken), "--db", str(db)], out)

    assert code == 1
    first = out.getvalue().splitlines()[0]
    assert first.startswith("✘") and "version" in first
