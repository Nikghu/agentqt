"""
Module: MD-MKT-002.006.M03 — market/rs.py
Parent SRD: SRD-MKT-002.006

Pure stock relative strength rules: 40/20/20/20 score, 1–99 rating and rank inside
the sector (DD-MKT-002.001.D01).
"""
from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

WEIGHTS = {63: 0.4, 126: 0.2, 189: 0.2, 252: 0.2}
YEAR = 252
MIN_PRESENT = 0.95
GAP_FILL = 5


def rs_scores(closes: pd.DataFrame) -> pd.DataFrame:
    """Return the RS score per day and stock; NaN without 95% of the past 252 days.

    A missing close on a look-back day uses the last close up to 5 days before it,
    so one missing day does not drop a stock.
    """
    filled = closes.ffill(limit=GAP_FILL)
    score = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
    for n, w in WEIGHTS.items():
        score += w * (closes / filled.shift(n) - 1)
    present = closes.notna().rolling(YEAR, min_periods=YEAR).sum()
    enough = present >= MIN_PRESENT * YEAR
    return score.where(enough & closes.notna())


def rs_table(scores: pd.DataFrame, sector_of: Mapping[str, str]) -> pd.DataFrame:
    """Return one row per scored (date, symbol): sector, score, rating, sector rank and size."""
    pct = scores.rank(axis=1, pct=True)
    rating = pd.DataFrame(np.ceil(pct.to_numpy() * 99), index=pct.index,
                          columns=pct.columns).clip(1, 99)
    sector_rank = pd.DataFrame(np.nan, index=scores.index, columns=scores.columns)
    sector_size = sector_rank.copy()
    for sector in set(sector_of.values()):
        cols = [s for s, sec in sector_of.items() if sec == sector and s in scores.columns]
        if not cols:
            continue
        part = scores[cols]
        sector_rank[cols] = part.rank(axis=1, ascending=False, method="min")
        size = part.notna().sum(axis=1)
        sector_size[cols] = np.repeat(size.to_numpy()[:, None], len(cols), axis=1)
    parts = {"score": scores, "rs_rating": rating, "sector_rank": sector_rank,
             "sector_size": sector_size}
    table = pd.concat({k: v.stack() for k, v in parts.items()}, axis=1)
    table = table.dropna(subset=["score"])
    table.index = table.index.set_names(["date", "symbol"])
    table["sector"] = [sector_of.get(sym, "") for sym in table.index.get_level_values("symbol")]
    return table
