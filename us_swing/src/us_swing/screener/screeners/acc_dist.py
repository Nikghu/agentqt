"""Module: MD-SCR-017.001.M32 — screeners/acc_dist.py
Parent SRD: SRD-SCR-017.001–.012

AccDistScreener: reads the volume behind recent rallies and drops on daily bars.

Accumulation = rallies on high volume, drops on low volume (near the range low).
Distribution = rallies on low volume, drops on high volume (near the range high).
Score = mean of rally match % and drop match %.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt

from us_swing.core.indicator_rules import BarArrays
from us_swing.core.indicator_rules._ta import volume_ratio
from us_swing.screener.base import ScreenerValidationError

_log = logging.getLogger(__name__)

ACCUMULATION = "accumulation"
DISTRIBUTION = "distribution"
MODES = (ACCUMULATION, DISTRIBUTION)

# key → (default, min, max); a bool default marks an on/off setting.
SETTINGS: dict[str, tuple[Any, float, float]] = {
    "lookback": (20, 5, 120),
    "volume_period": (20, 5, 100),
    "high_factor": (1.2, 1.0, 5.0),
    "low_factor": (0.9, 0.1, 1.0),
    "min_move_pct": (0.5, 0.0, 10.0),
    "min_rally_days": (3, 1, 60),
    "min_drop_days": (3, 1, 60),
    "min_ud_ratio": (1.3, 1.0, 5.0),
    "max_ud_ratio": (0.8, 0.1, 1.0),
    "location_filter": (True, 0, 1),
    "range_period": (126, 20, 260),
    "zone_pct": (25.0, 5.0, 50.0),
    "close_position": (True, 0, 1),
    "close_zone_pct": (30.0, 10.0, 50.0),
    "min_score": (0.6, 0.0, 1.0),
}


def default_config() -> dict[str, Any]:
    """Return a config dict with every setting at its default."""
    return {"mode": ACCUMULATION, **{k: d for k, (d, _, _) in SETTINGS.items()}}


def read_config(config: dict[str, Any]) -> dict[str, Any]:
    """Merge ``config`` over the defaults and check every value.

    Raises:
        ScreenerValidationError: If the mode is unknown or a value is out of range.
    """
    cfg = default_config()
    cfg.update({k: v for k, v in config.items() if k in cfg})
    if cfg["mode"] not in MODES:
        raise ScreenerValidationError(f"Accumulation / Distribution: unknown mode '{cfg['mode']}'")
    for key, (default, lo, hi) in SETTINGS.items():
        if isinstance(default, bool):
            cfg[key] = bool(cfg[key])
            continue
        value = float(cfg[key])
        if not lo <= value <= hi:
            raise ScreenerValidationError(
                f"Accumulation / Distribution: '{key}' must be {lo}–{hi}, got {value}"
            )
        cfg[key] = int(value) if isinstance(default, int) else value
    return cfg


@dataclass(frozen=True, slots=True)
class _Result:
    passed: bool
    score: float
    rally_vol: float
    drop_vol: float
    ud_ratio: float


def _close_in_zone(a: BarArrays, n: int, zone: float, top: bool) -> npt.NDArray[np.bool_]:
    high, low, close = a.high[-n:], a.low[-n:], a.close[-n:]
    span = high - low
    pos = np.divide(close - low, span, out=np.full(n, 0.5), where=span > 0)
    return np.asarray(pos >= 1.0 - zone if top else pos <= zone, dtype=np.bool_)


def _near_range_edge(a: BarArrays, cfg: dict[str, Any], bottom: bool) -> bool:
    n = min(cfg["range_period"], len(a.close))
    lo, hi = a.low[-n:].min(), a.high[-n:].max()
    if hi <= lo:
        return False
    pos = (a.close[-1] - lo) / (hi - lo)
    zone = cfg["zone_pct"] / 100.0
    return bool(pos <= zone if bottom else pos >= 1.0 - zone)


def _evaluate(a: BarArrays, cfg: dict[str, Any]) -> _Result:
    acc = cfg["mode"] == ACCUMULATION
    n = cfg["lookback"]
    change = np.diff(a.close[-n - 1:]) / a.close[-n - 1:-1] * 100.0
    ratio = volume_ratio(a.volume, cfg["volume_period"])[-n:]
    rally = (change > 0) & (change >= cfg["min_move_pct"])
    drop = (change < 0) & (change <= -cfg["min_move_pct"])

    high = ratio >= cfg["high_factor"]
    low = ratio <= cfg["low_factor"]
    zone = cfg["close_zone_pct"] / 100.0
    strong = _close_in_zone(a, n, zone, top=acc) if cfg["close_position"] else np.ones(n, bool)
    rally_hit = rally & (high & strong if acc else low)
    drop_hit = drop & (low if acc else high & strong)

    n_rally, n_drop = int(rally.sum()), int(drop.sum())
    rally_pct = rally_hit.sum() / n_rally if n_rally else 0.0
    drop_pct = drop_hit.sum() / n_drop if n_drop else 0.0
    score = round(float(rally_pct + drop_pct) / 2.0, 4)

    vol = a.volume[-n:]
    rally_mean = float(vol[rally].mean()) if n_rally else 0.0
    drop_mean = float(vol[drop].mean()) if n_drop else 0.0
    ud = rally_mean / drop_mean if drop_mean > 0 else 0.0
    rally_vol = float(np.nanmean(ratio[rally])) if n_rally else 0.0
    drop_vol = float(np.nanmean(ratio[drop])) if n_drop else 0.0

    passed = (
        score >= cfg["min_score"]
        and n_rally >= cfg["min_rally_days"]
        and n_drop >= cfg["min_drop_days"]
        and (ud >= cfg["min_ud_ratio"] if acc else 0 < ud <= cfg["max_ud_ratio"])
        and (not cfg["location_filter"] or _near_range_edge(a, cfg, bottom=acc))
    )
    return _Result(passed, score, round(rally_vol, 2), round(drop_vol, 2), round(ud, 2))


class AccDistScreener:
    """MD-SCR-017.001.M32 — accumulation / distribution volume screener."""

    screener_id: str = "acc_dist"
    screener_type: str = "acc_dist"
    name: str = "Accumulation / Distribution"

    def _run(
        self, symbols: list[str], bars: dict[str, list[Any]], config: dict[str, Any]
    ) -> dict[str, _Result]:
        cfg = read_config(config)
        need = cfg["lookback"] + cfg["volume_period"] + 1
        out: dict[str, _Result] = {}
        for sym in symbols:
            sym_bars = bars.get(sym, [])
            if len(sym_bars) < need:
                continue
            out[sym] = _evaluate(BarArrays.from_bars(sym_bars), cfg)
        return out

    def apply(
        self,
        symbols: list[str],
        bars: dict[str, list[Any]],
        config: dict[str, Any],
    ) -> dict[str, tuple[bool, float]]:
        """Screen symbols for accumulation or distribution.

        Args:
            symbols: Symbols to screen.
            bars: Map of symbol → list[OHLCVBar] (oldest first).
            config: Settings; missing keys use ``default_config()``.

        Returns:
            dict mapping symbol → (passed, score). Symbols with too few bars are omitted.

        Raises:
            ScreenerValidationError: If a setting is invalid.
        """
        results = {s: (r.passed, r.score) for s, r in self._run(symbols, bars, config).items()}
        _log.debug(
            "[Screener] Accumulation / Distribution screened %d stock(s), %d passed",
            len(symbols), sum(1 for p, _ in results.values() if p),
        )
        return results

    def screen_detailed(
        self,
        symbols: list[str],
        bars: dict[str, list[Any]],
        config: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """Return rally volume ×, drop volume × and up/down ratio per symbol."""
        return {
            s: {"RallyVol": r.rally_vol, "DropVol": r.drop_vol, "UD": r.ud_ratio}
            for s, r in self._run(symbols, bars, config).items()
        }

    def batch_features(
        self,
        symbols: list[str],
        bars: dict[str, list[Any]],
    ) -> dict[str, dict[str, Any]]:
        return {}
