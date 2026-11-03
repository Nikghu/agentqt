"""
Module: MD-EXE-011.027.M01 — tests
Parent SRD: SRD-EXE-011.027
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from us_swing.core.market_structure import (
    MIN_LTF_BARS,
    BossSt,
    BossStParams,
    bars_from_frame,
    boss_st,
    break_ok,
    swings,
)

_PARAMS = BossStParams(swing_lookback=2, min_break_atr=0.0)


def boss_frames(seed: int = 5, n: int = 640, col: str = "ts") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Random-walk 15m bars and the 30m bars built from them."""
    rng = np.random.default_rng(seed)
    stamps = pd.date_range("2026-01-05 14:30", periods=n, freq="15min", tz="UTC")
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    ltf = pd.DataFrame({
        col: stamps, "open": close, "high": close + rng.uniform(0.05, 0.8, n),
        "low": close - rng.uniform(0.05, 0.8, n), "close": close, "volume": 1.0,
    })
    htf = ltf.groupby(np.arange(n) // 2).agg(
        **{col: (col, "first")}, open=("open", "first"), high=("high", "max"),
        low=("low", "min"), close=("close", "last"), volume=("volume", "sum"),
    )
    return ltf, htf.reset_index(drop=True)


def _run(ltf: pd.DataFrame, htf: pd.DataFrame, params: BossStParams = _PARAMS) -> BossSt:
    return boss_st(bars_from_frame(ltf, 15), bars_from_frame(htf, 30), params)


@pytest.fixture(scope="module")
def result() -> BossSt:
    return _run(*boss_frames())


def _changes(state: np.ndarray, before: float, after: float) -> np.ndarray:
    prev = np.concatenate(([np.nan], state[:-1]))
    return np.flatnonzero((prev == before) & (state == after))


def test_swing_pivots_are_causal() -> None:
    """UT-EXE-011.027.M01.T01: Swing pivots are causal."""
    highs = np.array([1.0, 2.0, 3.0, 5.0, 3.0, 2.0, 1.0])

    swing_high = swings(highs, 2, high=True)
    swing_low = swings(6.0 - highs, 2, high=False)

    assert swing_high[5] == 5.0
    assert np.isnan(np.delete(swing_high, 5)).all()
    assert swing_low[5] == 1.0
    assert np.isnan(swings(highs[:5], 2, high=True)).all()


def test_long_entries_meet_long_rules(result: BossSt) -> None:
    """UT-EXE-011.027.M01.T02: Every long entry meets all long rules."""
    ltf, _htf = boss_frames()
    entries = _changes(result.state, 0.0, 1.0)

    assert len(entries) >= 2
    for i in entries:
        assert result.choch_htf[i] == 1 and result.bos[i] == 1
        assert ltf["close"].iloc[i] > result.ema[i] and result.st_dir[i] == 1


def test_short_entries_and_exits_meet_rules(result: BossSt) -> None:
    """UT-EXE-011.027.M01.T03: Every short entry and every exit meets its rule."""
    ltf, _htf = boss_frames()
    shorts = _changes(result.state, 0.0, -1.0)

    assert len(shorts) >= 2
    for i in shorts:
        assert result.choch_htf[i] == -1 and result.bos[i] == -1
        assert ltf["close"].iloc[i] < result.ema[i] and result.st_dir[i] == -1
    for i in _changes(result.state, 1.0, 0.0):
        assert result.choch[i] == -1 or result.st_dir[i] == -1
    for i in _changes(result.state, -1.0, 0.0):
        assert result.choch[i] == 1 or result.st_dir[i] == 1


def test_fresh_only_on_change_bars(result: BossSt) -> None:
    """UT-EXE-011.027.M01.T04: Fresh is the state only on change bars."""
    state, fresh = result.state[MIN_LTF_BARS:], result.fresh[MIN_LTF_BARS:]
    prev = result.state[MIN_LTF_BARS - 1:-1]

    np.testing.assert_array_equal(fresh, np.where(state != prev, state, 0.0))
    assert np.count_nonzero(fresh) >= 4


def test_no_look_ahead(result: BossSt) -> None:
    """UT-EXE-011.027.M01.T05: Values on a cut frame equal the full run up to the cut."""
    ltf, htf = boss_frames()
    for cut in (250, 400, 517):
        last_close = ltf["ts"].iloc[cut - 1] + pd.Timedelta(minutes=15)
        htf_cut = htf[htf["ts"] + pd.Timedelta(minutes=30) <= last_close]
        part = _run(ltf.iloc[:cut], htf_cut)

        np.testing.assert_array_equal(part.state, result.state[:cut])
        np.testing.assert_array_equal(part.fresh, result.fresh[:cut])


def test_atr_gate() -> None:
    """UT-EXE-011.027.M01.T06: ATR 0 lets every break count; ATR 5 blocks all."""
    ltf, htf = boss_frames()

    assert break_ok(bars_from_frame(ltf, 15), 0.0).all()
    blocked = _run(ltf, htf, BossStParams(2, 5.0))
    assert np.nan_to_num(blocked.state).tolist() == [0.0] * len(ltf)


def test_too_little_history_is_nan() -> None:
    """UT-EXE-011.027.M01.T07: NaN on every bar that lacks history."""
    ltf, htf = boss_frames()

    assert np.isnan(_run(ltf.iloc[:150], htf).state).all()
    assert np.isnan(_run(ltf, htf.iloc[:3]).state).all()
    assert np.isnan(_run(ltf, htf).state[:MIN_LTF_BARS - 1]).all()
