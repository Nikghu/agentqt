"""
Module: MD-MKT-002.002.M02 — market/sectors.py
Parent SRD: SRD-MKT-002.002

Pure sector rules: equal-weight sector lines, moves against SPY, rank, RS-ratio,
RS-momentum and rotation quadrant (DD-MKT-002.001.D01).
"""
from __future__ import annotations

import math
from collections.abc import Mapping

import pandas as pd

WINDOWS = {"rel_1m": 21, "rel_3m": 63, "rel_6m": 126}
RATIO_DAYS = 50
MOMENTUM_DAYS = 10


def sector_lines(
    closes: pd.DataFrame, sector_of: Mapping[str, str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return each sector's line (starts at 100) and its member count per day.

    Args:
        closes: Member closes, one column per symbol, aligned to SPY's days.
        sector_of: Symbol to sector; symbols not in ``closes`` are left out.
    """
    ret = closes / closes.shift(1) - 1
    lines: dict[str, pd.Series] = {}
    counts: dict[str, pd.Series] = {}
    for sector in sorted(set(sector_of.values())):
        cols = [s for s, sec in sector_of.items() if sec == sector and s in closes.columns]
        if not cols:
            continue
        daily = ret[cols].mean(axis=1, skipna=True).fillna(0.0)
        lines[sector] = 100 * (1 + daily).cumprod()
        counts[sector] = closes[cols].notna().sum(axis=1)
    return pd.DataFrame(lines, index=closes.index), pd.DataFrame(counts, index=closes.index)


def quadrant(ratio: float | None, momentum: float | None) -> str | None:
    """Return Leading, Weakening, Lagging or Improving; ``None`` when a value is missing."""
    if ratio is None or momentum is None or math.isnan(ratio) or math.isnan(momentum):
        return None
    if ratio >= 100:
        return "Leading" if momentum >= 100 else "Weakening"
    return "Improving" if momentum >= 100 else "Lagging"


def sector_table(lines: pd.DataFrame, spy: pd.Series) -> pd.DataFrame:
    """Return one row per (date, sector) with moves against SPY, rank, ratio and quadrant.

    Args:
        lines: Sector lines from ``sector_lines``.
        spy: SPY closes on the same days.
    """
    spy = spy.reindex(lines.index)
    parts: dict[str, pd.DataFrame] = {"line": lines}
    for name, n in WINDOWS.items():
        parts[name] = (lines / lines.shift(n) - 1).sub(spy / spy.shift(n) - 1, axis=0)
    mean_rel = (parts["rel_1m"] + parts["rel_3m"] + parts["rel_6m"]) / 3
    parts["rank"] = mean_rel.rank(axis=1, ascending=False, method="min")
    rs = lines.div(spy, axis=0)
    ratio = 100 * rs / rs.rolling(RATIO_DAYS).mean()
    parts["rs_ratio"] = ratio
    parts["rs_momentum"] = 100 * ratio / ratio.shift(MOMENTUM_DAYS)
    table = pd.concat({k: v.stack(future_stack=True) for k, v in parts.items()}, axis=1)
    table.index = table.index.set_names(["date", "sector"])
    table["quadrant"] = [
        quadrant(r, m) for r, m in zip(table["rs_ratio"], table["rs_momentum"], strict=True)
    ]
    return table
