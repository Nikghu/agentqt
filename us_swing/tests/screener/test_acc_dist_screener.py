"""Tests for AccDistScreener (MD-SCR-017.001.M32).

Refs: UT-SCR-017.001–.012.M32 (FO-SCR-015)
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from us_swing.screener.base import ScreenerValidationError
from us_swing.screener.screeners.acc_dist import (
    AccDistScreener,
    default_config,
    read_config,
)

# 20 lookback days: 8 rallies (R), 7 drops (D), 5 flat days (F).
_DAYS = "RDRFDRDRFDRDFRDRFDRF"
_HIGH, _LOW, _NORMAL = 1_500_000.0, 600_000.0, 1_050_000.0


def _bar(open_: float, close: float, volume: float, close_at_extreme: bool = True) -> Any:
    top, bottom = max(open_, close) * 1.002, min(open_, close) * 0.998
    if not close_at_extreme:
        top, bottom = max(open_, close) * 1.02, min(open_, close) * 0.98
    return SimpleNamespace(open=open_, high=top, low=bottom, close=close, volume=volume)


def _bars(
    start: float = 150.0,
    rally_vol: float = _HIGH,
    drop_vol: float = _LOW,
    rally_close_low: bool = False,
) -> list[Any]:
    """106 bars from ``start`` to 100, then the 20 lookback days."""
    bars = []
    prices = np.linspace(start, 100.0, 107)
    for o, c in zip(prices[:-1], prices[1:]):
        bars.append(_bar(o, c, 1_000_000.0))
    price, rallies, drops = 100.0, 0, 0
    for day in _DAYS:
        if day == "R":
            rallies += 1
            new, vol = price * 1.015, rally_vol if rallies <= 6 else _NORMAL
            bar = _bar(price, new, vol)
            if rally_close_low:
                bar.high = new * 1.03
        elif day == "D":
            drops += 1
            new, vol = price * 0.99, drop_vol if drops <= 6 else _NORMAL
            bar = _bar(price, new, vol)
        else:
            new = price
            bar = _bar(price, new, _NORMAL)
        bars.append(bar)
        price = new
    return bars


def _run(bars: list[Any], **cfg: Any) -> tuple[bool, float]:
    return AccDistScreener().apply(["XYZ"], {"XYZ": bars}, cfg)["XYZ"]


def test_registered() -> None:
    """UT-SCR-017.001.M32.T01: Screener is registered as acc_dist."""
    import inspect

    import us_swing.screener as screener_pkg

    assert 'register("acc_dist", AccDistScreener)' in inspect.getsource(screener_pkg)
    assert AccDistScreener.name == "Accumulation / Distribution"


def test_defaults() -> None:
    """UT-SCR-017.002.M32.T01: Empty config reads as the defaults with int and float types."""
    cfg = read_config({})
    assert cfg == default_config()
    assert cfg["mode"] == "accumulation"
    assert isinstance(cfg["lookback"], int) and cfg["lookback"] == 20
    assert cfg["range_period"] == 126 and cfg["location_filter"] is True


@pytest.mark.parametrize(
    ("key", "value"),
    [("mode", "sideways"), ("lookback", 2), ("high_factor", 9.0), ("min_score", 1.5)],
)
def test_bad_setting_raises(key: str, value: Any) -> None:
    """UT-SCR-017.003.M32.T01: Bad mode or out-of-range value raises naming the key."""
    with pytest.raises(ScreenerValidationError, match=str(value) if key == "mode" else key):
        read_config({key: value})


def test_min_move_makes_small_days_flat() -> None:
    """UT-SCR-017.004.M32.T01: Moves under the minimum move % are flat and not scored."""
    passed, score = _run(_bars(), min_move_pct=2.0)
    assert (passed, score) == (False, 0.0)


def test_accumulation_passes() -> None:
    """UT-SCR-017.006.M32.T01: Rallies on high volume, drops on low volume pass Accumulation."""
    passed, score = _run(_bars())
    assert passed is True
    assert score == pytest.approx((6 / 8 + 6 / 7) / 2, abs=1e-3)


def test_same_bars_fail_distribution() -> None:
    """UT-SCR-017.006.M32.T02: Accumulation bars fail Distribution."""
    passed, score = _run(_bars(), mode="distribution", location_filter=False)
    assert passed is False
    assert score < 0.6


def test_distribution_passes() -> None:
    """UT-SCR-017.006.M32.T03: Rallies on low volume, drops on high volume near the top pass."""
    bars = _bars(start=50.0, rally_vol=_LOW, drop_vol=_HIGH)
    passed, score = _run(bars, mode="distribution")
    assert passed is True
    assert score == pytest.approx((6 / 8 + 6 / 7) / 2, abs=1e-3)


def test_ud_ratio_and_details() -> None:
    """UT-SCR-017.008.M32.T01: Detailed output shows relative volumes and up/down ratio."""
    details = AccDistScreener().screen_detailed(["XYZ"], {"XYZ": _bars()}, {})["XYZ"]
    assert set(details) == {"RallyVol", "DropVol", "UD"}
    assert details["RallyVol"] > 1.2 > 0.9 > details["DropVol"]
    assert details["UD"] >= 1.3


def test_ud_ratio_limit_blocks_pass() -> None:
    """UT-SCR-017.008.M32.T02: Up/down ratio under the minimum fails Accumulation."""
    passed, _ = _run(_bars(), min_ud_ratio=5.0)
    assert passed is False


def test_location_filter() -> None:
    """UT-SCR-017.009.M32.T01: Near the range high fails Accumulation unless the filter is off."""
    bars = _bars(start=50.0)
    assert _run(bars)[0] is False
    assert _run(bars, location_filter=False)[0] is True


def test_close_position_check() -> None:
    """UT-SCR-017.010.M32.T01: Rallies closing low in the candle stop counting when the check is on."""
    bars = _bars(rally_close_low=True)
    on_passed, on_score = _run(bars)
    off_passed, off_score = _run(bars, close_position=False)
    assert on_passed is False and on_score < off_score
    assert off_passed is True


def test_min_days_and_short_history() -> None:
    """UT-SCR-017.011.M32.T01: Too few rally days fails; too few bars omits the symbol."""
    assert _run(_bars(), min_rally_days=9)[0] is False
    short = _bars()[-30:]
    assert AccDistScreener().apply(["XYZ"], {"XYZ": short}, {}) == {}
