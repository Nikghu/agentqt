"""Tests for MD-BKT-002.080.M14 — backtest/steps/recorded.py and the saved-list service path."""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from us_swing.backtest.cache import StepCache
from us_swing.backtest.results import ResultsStore
from us_swing.backtest.service import BacktestService
from us_swing.backtest.steps.recorded import load_lists, saved_days, trade_day
from us_swing.backtest.store import BacktestStore
from tests.backtest.conftest import Record, plan_for, rsi_preset

_NAMES = ("AAPL", "MSFT", "NVDA")
_SESSIONS = [date(2025, 3, d) for d in (3, 4, 5, 6, 7)]


def _save(base: Path, day: str, stamp: str, results: dict[str, Any]) -> None:
    folder = base / "preset_p1"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{day}.json").write_text(json.dumps(
        {"preset_id": "p1", "run_timestamp": stamp, "results": results}), encoding="utf-8")


def _pick(score: float, passed: bool = True) -> dict[str, Any]:
    return {"passed": passed, "score": score}


def test_trade_day() -> None:
    """UT-BKT-002.081.M14.T01: Before 09:30 ET trades that day; later trades the next day."""
    assert trade_day(pd.Timestamp("2026-10-29T13:00:48Z")) == date(2026, 10, 29)
    assert trade_day(pd.Timestamp("2026-09-08T13:52:45Z")) == date(2026, 9, 9)


def test_load_lists(tmp_path: Path) -> None:
    """UT-BKT-002.080.M14.T01: Passed stocks in the list, ranked by score; newer list wins."""
    _save(tmp_path, "2025-03-03", "2025-03-03T13:00:00Z",
          {"AAPL": _pick(0.5), "MSFT": _pick(0.9), "NVDA": _pick(0.7, passed=False),
           "TSLA": _pick(1.0)})
    _save(tmp_path, "2025-03-01", "2025-03-01T15:00:00Z", {"AAPL": _pick(0.1)})  # Saturday
    _save(tmp_path, "2025-03-02", "2025-03-02T15:00:00Z", {"NVDA": _pick(0.2)})  # newer, Mon

    frame = load_lists("p1", _SESSIONS, set(_NAMES), tmp_path)

    monday = frame[frame["date"] == date(2025, 3, 3)]
    assert list(monday["symbol"]) == ["MSFT", "AAPL"]
    assert list(monday["rank"]) == [1, 2]
    assert saved_days("p1", tmp_path) == [date(2025, 3, 1), date(2025, 3, 2), date(2025, 3, 3)]


def test_load_lists_skips_bad_and_old(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-BKT-002.080.M14.T02: Bad files and lists far before the period are left out."""
    _save(tmp_path, "2025-01-10", "2025-01-10T13:00:00Z", {"AAPL": _pick(1.0)})
    (tmp_path / "preset_p1" / "2025-03-04.json").write_text("{bad", encoding="utf-8")

    frame = load_lists("p1", _SESSIONS, set(_NAMES), tmp_path)

    assert frame.empty
    assert "could not be read" in caplog.text
    assert load_lists("other", _SESSIONS, set(_NAMES), tmp_path).empty
    assert saved_days("other", tmp_path) == []


def _service(store: BacktestStore, tmp_path: Path) -> BacktestService:
    records = [Record(s, "Information Technology", 1e9) for s in _NAMES]
    return BacktestService(store, StepCache(tmp_path / "cache"),
                           ResultsStore(tmp_path / "results.db"), lambda: records,
                           lambda _p, _u: rsi_preset(0, 100), screener_results=tmp_path / "sr")


def test_service_uses_saved_lists(store: BacktestStore, tmp_path: Path) -> None:
    """UT-BKT-002.081.M05.T01: Data check counts sessions with a list; Step 1 uses them."""
    _save(tmp_path / "sr", "2025-03-04", "2025-03-04T12:00:00Z", {"NVDA": _pick(0.8)})
    svc = _service(store, tmp_path)
    plan = plan_for(date(2025, 3, 3), date(2025, 3, 7), _NAMES)
    plan = replace(plan, screener=replace(plan.screener, preset_id="p1", recorded=True))

    est = svc.estimate(plan, "1")
    daily = svc.run_stocks(plan, "1", workers=0)

    assert (est.recorded, est.days_cached, est.days_total, est.errors) == (True, 1, 5, [])
    assert len(daily.days) == 5
    assert daily.frame.to_dict("records") == [
        {"date": date(2025, 3, 4), "symbol": "NVDA", "score": 0.8, "rank": 1}]


def test_service_without_saved_lists(store: BacktestStore, tmp_path: Path) -> None:
    """UT-BKT-002.081.M05.T02: No saved list in the period stops the run with a message."""
    svc = _service(store, tmp_path)
    plan = plan_for(date(2025, 3, 3), date(2025, 3, 7), _NAMES)
    plan = replace(plan, screener=replace(plan.screener, preset_id="p1", recorded=True))

    est = svc.estimate(plan, "1")

    assert est.errors == ["No saved screener list for this preset in the period"]
