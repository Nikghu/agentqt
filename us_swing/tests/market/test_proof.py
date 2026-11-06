"""Tests for FO-MKT-004 — market/proof_data.py, market/proof.py and the proof tables."""
from __future__ import annotations

import logging
import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from tests.market.conftest import START, bdays, write_candles
from us_swing.core.desk_contract import StepContext
from us_swing.market import proof
from us_swing.market.idea_step import IdeaStep
from us_swing.market.proof import (
    FAIL,
    PASS,
    THIN,
    forward_returns,
    group_stats,
    history_note,
    replay,
    run_proof,
    verdict,
)
from us_swing.market.proof_data import daily_symbols, history_years, read_daily
from us_swing.market.sector_step import SectorStep
from us_swing.market.step import RegimeStep
from us_swing.market.store import MarketStore, ProofRunRow, ProofStatRow

N = 300
SECTORS = {f"M{i}": ("Tech", "Energy", "Health Care")[i % 3] for i in range(9)}
TRIPLES = [(s, s, sec) for s, sec in SECTORS.items()]


def _closes(n: int, seed: int) -> list[float]:
    rng = np.random.default_rng(seed)
    return list(100 * np.exp(np.cumsum(rng.normal(0.0005, 0.01, n))))


def _series(n: int = N) -> dict[str, Sequence[float]]:
    out: dict[str, Sequence[float]] = {"SPY": _closes(n, 0)}
    for i, sym in enumerate(SECTORS):
        out[sym] = _closes(n, i + 1)
    return out


def write_daily(root: Path, series: dict[str, Sequence[float]], volume: float = 1e6,
                skip: dict[str, set[pd.Timestamp]] | None = None) -> None:
    """Write Backtest Data daily files with the same bars as ``write_candles``."""
    folder = root / "1d"
    folder.mkdir(parents=True, exist_ok=True)
    for sym, closes in series.items():
        days = bdays(len(closes), START)
        df = pd.DataFrame({"ts": days, "open": closes, "high": np.array(closes) * 1.01,
                           "low": np.array(closes) * 0.99, "close": closes,
                           "volume": volume})
        if skip and sym in skip:
            df = df[~df["ts"].isin(list(skip[sym]))]
        df.to_parquet(folder / f"{sym}.parquet", index=False)


def _replayed(root: Path) -> pd.DataFrame:
    pb = read_daily([*SECTORS, "SPY"], root)
    assert pb is not None
    inp, _ = proof._inputs(pb, dict(SECTORS))
    return replay(inp, proof._ready_days(inp, len(SECTORS)))


def _vix(_start: object) -> pd.DataFrame:
    return pd.DataFrame({"vix": 15.0, "vix3m": 17.0}, index=bdays(N + 5))


# ---------------- M01 proof_data ----------------

def test_daily_files_read(tmp_path: Path) -> None:
    """UT-MKT-004.001.M01.T01: Daily files are read into wide frames by day and symbol."""
    write_daily(tmp_path, {"SPY": [1.0, 2.0, 3.0], "A": [4.0, 5.0, 6.0], "B": [7.0, 8.0, 9.0],
                           "C": [1.0, 1.0, 1.0]})
    assert daily_symbols(tmp_path) == {"SPY", "A", "B", "C"}
    pb = read_daily(["SPY", "A", "B", "C", "MISSING"], tmp_path)
    assert pb is not None
    assert list(pb.bars.closes.columns) == ["SPY", "A", "B", "C"]
    assert list(pb.bars.closes.index) == list(bdays(3))
    assert pb.opens["A"].tolist() == [4.0, 5.0, 6.0]
    assert pb.bars.highs["B"].iloc[0] == pytest.approx(7.07)
    assert pb.bars.volumes["C"].iloc[2] == 1e6


def test_no_backtest_folder(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-004.001.M01.T02: Without the Backtest Data folder nothing is read."""
    assert daily_symbols(tmp_path / "none") == set()
    with caplog.at_level(logging.WARNING):
        assert read_daily(["SPY"], tmp_path / "none") is None
    assert "[Proof]" in caplog.text


def test_stock_missing_a_day(tmp_path: Path) -> None:
    """UT-MKT-004.001.M01.T03: A missing bar is NaN; the other days are kept."""
    gap = bdays(5)[2]
    write_daily(tmp_path, {"SPY": [1.0] * 5, "A": [2.0] * 5}, skip={"A": {gap}})
    pb = read_daily(["SPY", "A"], tmp_path)
    assert pb is not None
    assert pb.bars.closes["A"].isna().tolist() == [False, False, True, False, False]
    assert history_years(pb.bars.closes.index) == pytest.approx(6 / 365.25)


# ---------------- M02 replay ----------------

def test_replay_matches_desk_step(tmp_path: Path) -> None:
    """UT-MKT-004.002.M02.T01: Replayed scores, setups and statuses equal the IdeaStep rows."""
    series = _series()
    candles, home = tmp_path / "candles.db", tmp_path / "desk"
    write_candles(candles, series, volume=1e6)
    write_daily(tmp_path / "bt", series)
    last = bdays(N)[-1].date()
    steps = [RegimeStep(candles, _vix, lambda: [(s, s) for s in SECTORS], lambda: last),
             SectorStep(candles, lambda: TRIPLES),
             IdeaStep(candles, lambda: TRIPLES, lambda syms: dict.fromkeys(syms))]
    for step in steps:
        step(StepContext(1, "manual", datetime.now(UTC), home))
    con = sqlite3.connect(home / "desk.db")
    desk = {(d, s, sd): (score, setup) for d, s, sd, score, setup in con.execute(
        "SELECT date, symbol, side, score, setup FROM stock_score")}
    status = {(d, s, sd): st for d, s, sd, st in con.execute(
        "SELECT date, symbol, side, status FROM ideas")}
    con.close()
    got = _replayed(tmp_path / "bt")
    mine = {(ts.date().isoformat(), sym, side): row
            for (ts, sym, side), row in zip(got.index, got.to_dict("records"), strict=True)}
    assert len(desk) > 100 and status
    assert set(mine) == set(desk)
    for key, (score, setup) in desk.items():
        assert mine[key]["score"] == pytest.approx(score)
        assert mine[key]["setup"] == setup
        assert mine[key]["status"] == status.get(key, "none")


def test_no_look_ahead(tmp_path: Path) -> None:
    """UT-MKT-004.002.M02.T02: Changing every bar after day d leaves scores up to d the same."""
    series = _series()
    write_daily(tmp_path / "a", series)
    cut = N - 20
    changed = {s: [*c[:cut], *(np.array(c[cut:]) * 1.3)] for s, c in series.items()}
    write_daily(tmp_path / "b", changed)
    a, b = _replayed(tmp_path / "a"), _replayed(tmp_path / "b")
    day = bdays(N)[cut - 1]
    keep_a = a[a.index.get_level_values("date") <= day]
    keep_b = b[b.index.get_level_values("date") <= day]
    assert len(keep_a) > 0
    pd.testing.assert_frame_equal(keep_a, keep_b)


def test_no_earnings_watch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-MKT-004.002.M02.T03: Past days get no earnings dates; Watch comes from the regime."""
    write_daily(tmp_path, _series())
    seen: list[Any] = []
    real = proof.pick_ideas

    def spy(*args: Any) -> Any:
        seen.append(args[3])
        return real(*args)

    monkeypatch.setattr(proof, "pick_ideas", spy)
    got = _replayed(tmp_path)
    assert seen and all(e is None for e in seen)
    assert set(got["status"]) <= {"list", "watch", "none"}


def test_thin_day_not_scored(tmp_path: Path) -> None:
    """UT-MKT-004.002.M02.T04: A day with data for under 80% of members is not scored."""
    thin = bdays(N)[-5]
    write_daily(tmp_path, _series(), skip={s: {thin} for s in ("M0", "M1", "M2")})
    days = set(_replayed(tmp_path).index.get_level_values("date"))
    assert thin not in days
    assert bdays(N)[-4] in days


# ---------------- M02 forward returns ----------------

def _one(day: int, side: str = "long", score: float = 75.0) -> pd.DataFrame:
    idx = pd.MultiIndex.from_tuples([(bdays(30)[day], "A", side)],
                                    names=["date", "symbol", "side"])
    return pd.DataFrame({"score": [score], "setup": ["Flat base"], "status": ["list"]},
                        index=idx)


def _bars() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    days = bdays(30)
    opens = pd.DataFrame({"A": 100.0}, index=days)
    closes = pd.DataFrame({"A": 100.0}, index=days)
    closes.iloc[6:, 0] = 110.0
    spy = pd.DataFrame({"open": 100.0, "close": 100.0}, index=days)
    spy.iloc[6:, 1] = 105.0
    return opens, closes, spy


def test_long_forward_return() -> None:
    """UT-MKT-004.003.M02.T01: Entry at next open 100, exit at t+5 close 110, SPY +5%."""
    opens, closes, spy = _bars()
    out = forward_returns(_one(1), opens, closes, spy)
    assert out["ret_5"].iloc[0] == pytest.approx(0.10)
    assert out["vs_5"].iloc[0] == pytest.approx(0.05)


def test_short_forward_return() -> None:
    """UT-MKT-004.003.M02.T02: The short side is minus the long side."""
    opens, closes, spy = _bars()
    out = forward_returns(_one(1, "short"), opens, closes, spy)
    assert out["ret_5"].iloc[0] == pytest.approx(-0.10)
    assert out["vs_5"].iloc[0] == pytest.approx(-0.05)


def test_end_of_data() -> None:
    """UT-MKT-004.003.M02.T03: 10 sessions before the end there is no 20-day sample."""
    opens, closes, spy = _bars()
    out = forward_returns(_one(19), opens, closes, spy)
    assert out["ret_5"].notna().iloc[0] and out["ret_10"].notna().iloc[0]
    assert out["ret_20"].isna().iloc[0]


def test_missing_exit_bar() -> None:
    """UT-MKT-004.003.M02.T04: A missing exit close gives no sample for that horizon."""
    opens, closes, spy = _bars()
    closes.iloc[11, 0] = np.nan
    out = forward_returns(_one(1), opens, closes, spy)
    assert out["ret_10"].isna().iloc[0]
    assert out["ret_5"].notna().iloc[0]


# ---------------- M02 groups and pass rule ----------------

def _frame(scores: Sequence[float], vs: Sequence[float], side: str = "long",
           setups: Sequence[str] | None = None,
           statuses: Sequence[str] | None = None) -> pd.DataFrame:
    n = len(scores)
    days = bdays(n)
    idx = pd.MultiIndex.from_arrays([days, [f"S{i}" for i in range(n)], [side] * n],
                                    names=["date", "symbol", "side"])
    data: dict[str, Any] = {"score": list(scores), "setup": list(setups or ["Flat base"] * n),
                            "status": list(statuses or ["none"] * n)}
    for h in proof.HORIZONS:
        data[f"ret_{h}"] = list(vs)
        data[f"vs_{h}"] = list(vs)
    return pd.DataFrame(data, index=idx)


def test_band_edges() -> None:
    """UT-MKT-004.004.M02.T01: Band edges put 40 in 40-50, 70 in 70-80 and 80+ in 80+."""
    stats = group_stats(_frame([39.9, 40, 70, 80, 100], [0.01] * 5))
    bands = {(s.grp, s.n) for s in stats if s.kind == "band" and s.horizon == 10}
    assert bands == {("under 40", 1), ("40-50", 1), ("70-80", 1), ("80+", 2)}


def test_setup_and_status_groups() -> None:
    """UT-MKT-004.004.M02.T02: One group per setup and status with counts and averages."""
    frame = _frame([65, 65, 65, 65], [0.02, -0.01, 0.03, 0.0],
                   setups=["Flat base", "Flat base", "No setup", "Pullback"],
                   statuses=["list", "watch", "none", "none"])
    stats = {(s.kind, s.grp): s for s in group_stats(frame) if s.horizon == 5}
    flat = stats[("setup", "Flat base")]
    assert (flat.n, flat.days, flat.win_rate) == (2, 2, 0.5)
    assert flat.avg_ret == pytest.approx(0.005)
    assert flat.avg_vs_spy == pytest.approx(0.005)
    assert {g for k, g in stats if k == "status"} == {"list", "watch", "none"}
    assert stats[("status", "none")].win_rate == 0.5


def test_empty_group_left_out() -> None:
    """UT-MKT-004.004.M02.T03: A band with no stock-days has no row."""
    stats = group_stats(_frame([10, 45, 55], [0.01] * 3))
    assert "80+" not in {s.grp for s in stats if s.kind == "band"}
    assert {s.grp for s in stats if s.kind == "band"} == {"under 40", "40-50", "50-60"}


def test_side_passes() -> None:
    """UT-MKT-004.005.M02.T01: 70+ beats SPY and beats under-40 stocks: pass."""
    frame = _frame([75] * 150 + [20] * 150, [0.02] * 150 + [-0.01] * 150)
    result, top, low = verdict(frame, "long")
    assert (result, top, low) == (PASS, pytest.approx(0.02), pytest.approx(-0.01))


def test_side_fails() -> None:
    """UT-MKT-004.005.M02.T02: 70+ below SPY on average: fail."""
    frame = _frame([75] * 150 + [20] * 150, [-0.005] * 150 + [-0.01] * 150)
    assert verdict(frame, "long")[0] == FAIL
    assert verdict(frame, "short")[0] == THIN


def test_too_few_samples() -> None:
    """UT-MKT-004.005.M02.T03: 99 stock-days at 70+ is not enough data."""
    frame = _frame([75] * 99 + [20] * 150, [0.02] * 99 + [-0.01] * 150)
    assert verdict(frame, "long") == (THIN, None, None)


def test_run_stores_and_reports(tmp_path: Path) -> None:
    """UT-MKT-004.006.M02.T01: Each run adds a proof_run row with stats; a report is returned."""
    write_daily(tmp_path / "bt", _series())
    home = tmp_path / "desk"
    report = run_proof(home, tmp_path / "bt", lambda: TRIPLES)
    assert report is not None and "LONG - result" in report and "SHORT - result" in report
    assert run_proof(home, tmp_path / "bt", lambda: TRIPLES) is not None
    store = MarketStore(home)
    found = store.latest_proof()
    store.close()
    assert found is not None
    run_id, run, stats = found
    assert run_id == 2
    assert (run.stocks, run.data_first) == (9, bdays(1)[0].date().isoformat())
    assert {(s.side, s.kind, s.horizon) for s in stats} >= {
        (side, kind, h) for side in ("long", "short") for kind in ("band", "setup", "status")
        for h in (5, 10, 20)}


def test_run_without_data(tmp_path: Path) -> None:
    """UT-MKT-004.001.M02.T01: With no daily files nothing is tested or written."""
    assert run_proof(tmp_path / "desk", tmp_path / "bt", lambda: TRIPLES) is None
    assert not (tmp_path / "desk" / "desk.db").exists()


def test_short_history_reminder() -> None:
    """UT-MKT-004.007.M02.T01: Under 5 years the report ends with the download reminder."""
    run = ProofRunRow("now", "2023-08-01", "2026-10-15", "2024-08-01", "2026-10-15", 3.2, 9,
                      100, PASS, FAIL, 1.0)
    text = proof.report_text(run, [])
    assert text.endswith(history_note(3.2, "2023-08-01") or "missing")
    assert "Settings > Backtest Data" in text and "3.2 years" in text


def test_long_history_no_reminder() -> None:
    """UT-MKT-004.007.M02.T02: With 6 years there is no reminder."""
    assert history_note(6.0, "2020-01-02") is None
    run = ProofRunRow("now", "2020-01-02", "2026-01-02", "2021-01-02", "2026-01-02", 6.0, 9,
                      100, PASS, PASS, 1.0)
    assert "Backtest Data" not in proof.report_text(run, [])


# ---------------- M03 store ----------------

def test_proof_round_trip(tmp_path: Path) -> None:
    """UT-MKT-004.006.M03.T01: A written run and its stats read back as the latest run."""
    store = MarketStore(tmp_path)
    run = ProofRunRow("2026-11-06T10:00:00+00:00", "2024-01-02", "2026-11-04", "2025-01-31",
                      "2026-11-04", 2.84, 503, 443, PASS, FAIL, 21.0)
    stats = [ProofStatRow("long", "band", "80+", 10, 462, 120, 0.52, 0.004, 0.0025),
             ProofStatRow("short", "setup", "Breakdown", 5, 12, 10, 0.5, 0.01, 0.0)]
    store.write_proof(run, stats)
    assert store.write_proof(run, stats[:1]) == 2
    found = store.latest_proof()
    store.close()
    assert found == (2, run, stats[:1])


def test_no_runs_yet(tmp_path: Path) -> None:
    """UT-MKT-004.006.M03.T02: An empty desk.db has no latest proof."""
    store = MarketStore(tmp_path)
    assert store.latest_proof() is None
    store.close()
