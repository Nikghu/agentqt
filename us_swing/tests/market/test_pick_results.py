"""Tests for MD-MKT-009.001.M01 (paper rule and step), MD-MKT-009.004.M02 (pick_results table)
and MD-MKT-009.001.M06 (step order)."""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from tests.market.conftest import write_candles
from tests.market.test_desk_trades import _seed
from us_swing.core.desk_contract import DB_NAME, StepContext
from us_swing.core.desk_steps import STEP_PATHS, load_steps
from us_swing.data.market_calendar import ET
from us_swing.market.pick_results import Bar, PickResultsStep, paper_result
from us_swing.market.store import MarketStore, PickResultRow


def _bars(*hl: tuple[float, float], close: float = 100.0) -> list[Bar]:
    return [Bar(f"2026-01-{i + 1:02d}", h, lo, close) for i, (h, lo) in enumerate(hl)]


def _quiet(n: int, close: float = 100.0) -> list[tuple[float, float]]:
    return [(close + 1, close - 1)] * n


def _ctx(home: Path) -> StepContext:
    return StepContext(1, "evening", datetime(2025, 3, 1, 17, 0, tzinfo=ET), home)


def _rows(home: Path) -> list[tuple[str, str, str]]:
    con = sqlite3.connect(home / DB_NAME)
    try:
        return con.execute("SELECT date, symbol, status FROM pick_results ORDER BY date").fetchall()
    finally:
        con.close()


def test_step_scores_every_pick(tmp_path: Path) -> None:
    """UT-MKT-009.001.M01.T01: one paper result row per lead pick."""
    candles = tmp_path / "candles.db"
    write_candles(candles, {"AAA": [100.0] * 40, "BBB": [50.0] * 40})
    _seed(tmp_path, "2025-01-02", [("long", "AAA", 100.5, 95.0, "pass")])
    _seed(tmp_path, "2025-01-03", [("long", "BBB", 50.2, 48.0, "pass")])
    PickResultsStep(candles)(_ctx(tmp_path))
    assert [(d, s) for d, s, _ in _rows(tmp_path)] == [("2025-01-02", "AAA"), ("2025-01-03", "BBB")]


def test_no_candle_file(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-009.001.M01.T02: no candle file warns once and writes nothing."""
    _seed(tmp_path, "2025-01-02", [("long", "AAA", 100.5, 95.0, "pass")])
    with caplog.at_level(logging.WARNING):
        PickResultsStep(tmp_path / "missing.db")(_ctx(tmp_path))
    assert "[Results] No candle file yet" in caplog.text
    assert _rows(tmp_path) == []


def test_long_entry() -> None:
    """UT-MKT-009.002.M01.T01: a long enters on the first bar whose high reaches the trigger."""
    res = paper_result("long", 100.0, 95.0, 110.0, _bars((99, 98), (99, 98), (101, 99), *_quiet(3)))
    assert res is not None and (res.entry_day, res.entry) == ("2026-01-03", 100.0)


def test_no_fill() -> None:
    """UT-MKT-009.002.M01.T02: a trigger reached only after 5 bars is no fill."""
    res = paper_result("long", 100.0, 95.0, 110.0, _bars(*[(99, 98)] * 5, (101, 99)))
    assert res is not None and res.status == "no_fill" and res.entry is None


def test_short_entry() -> None:
    """UT-MKT-009.002.M01.T03: a short enters on the first bar whose low reaches the trigger."""
    res = paper_result("short", 50.0, 52.0, 46.0, _bars((51, 49), *_quiet(3, 50.0)))
    assert res is not None and (res.entry_day, res.entry) == ("2026-01-01", 50.0)


def test_target() -> None:
    """UT-MKT-009.003.M01.T01: reaching the target ends the pick at 2R."""
    res = paper_result("long", 100.0, 95.0, 110.0, _bars((101, 99), (111, 100)))
    assert res is not None and (res.status, res.exit, res.r) == ("target", 110.0, 2.0)


def test_stop() -> None:
    """UT-MKT-009.003.M01.T02: reaching the stop ends the pick at -1R."""
    res = paper_result("long", 100.0, 95.0, 110.0, _bars((101, 99), (100, 94)))
    assert res is not None and (res.status, res.exit, res.r) == ("stop", 95.0, -1.0)


def test_stop_and_target_one_day() -> None:
    """UT-MKT-009.003.M01.T03: stop wins when both are reached on one bar."""
    res = paper_result("long", 100.0, 95.0, 110.0, _bars((101, 99), (111, 94)))
    assert res is not None and res.status == "stop"


def test_time_exit_and_open() -> None:
    """UT-MKT-009.003.M01.T04: 10 quiet bars end at the close; fewer bars stay open."""
    done = paper_result("long", 100.0, 95.0, 110.0, _bars((101, 99), *_quiet(12, 102.0), close=102.0))
    assert done is not None and (done.status, done.exit_day, done.exit, done.r) == (
        "time", "2026-01-10", 102.0, 0.4)
    still = paper_result("long", 100.0, 95.0, 110.0, _bars((101, 99), *_quiet(3), close=101.0))
    assert still is not None and (still.status, still.exit_day, still.exit) == ("open", None, 101.0)


def test_bad_levels() -> None:
    """UT-MKT-009.003.M01.T05: levels on the wrong side are not scored."""
    assert paper_result("long", 100.0, 101.0, 110.0, _bars((101, 99))) is None
    assert paper_result("short", 50.0, 52.0, 51.0, _bars((51, 49))) is None


def _row(symbol: str, status: str = "open") -> PickResultRow:
    return PickResultRow("2025-01-02", "long", symbol, status, None, None, None, None, None)


def test_rows_replaced(tmp_path: Path) -> None:
    """UT-MKT-009.004.M02.T01: replacing the rows twice leaves no duplicates."""
    store = MarketStore(tmp_path)
    try:
        store.replace_pick_results([_row("AAA"), _row("BBB")])
        store.replace_pick_results([_row("AAA"), _row("BBB")])
    finally:
        store.close()
    assert len(_rows(tmp_path)) == 2


def test_bad_status(tmp_path: Path) -> None:
    """UT-MKT-009.004.M02.T02: an unknown status is refused and nothing changes."""
    store = MarketStore(tmp_path)
    try:
        store.replace_pick_results([_row("AAA")])
        with pytest.raises(ValueError):
            store.replace_pick_results([_row("BBB", "won")])
    finally:
        store.close()
    assert [s for _, s, _ in _rows(tmp_path)] == ["AAA"]


def test_step_order() -> None:
    """UT-MKT-009.001.M06.T01: Pick results runs after Ideas and News, before AI employees."""
    names = [s.name for s in load_steps(STEP_PATHS)]
    assert names.index("Ideas") < names.index("News") < names.index("Pick results")
    assert names.index("Pick results") + 1 == names.index("AI employees")


def test_logs(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-009.008.M01.T01: the step logs how many picks it worked out and how many are open."""
    candles = tmp_path / "candles.db"
    write_candles(candles, {"AAA": [100.0] * 3})
    _seed(tmp_path, "2025-01-01", [("long", "AAA", 100.5, 95.0, "pass")])
    with caplog.at_level(logging.INFO, logger="us_swing.market.pick_results"):
        PickResultsStep(candles)(_ctx(tmp_path))
    assert "[Results] 1 pick(s) worked out, 1 still open" in caplog.text
