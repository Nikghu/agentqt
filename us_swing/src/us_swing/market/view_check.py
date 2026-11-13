"""
Module: MD-MKT-012.007.M04 — market/view_check.py
Parent SRD: SRD-MKT-012.007
Also: SRD-MKT-012.008 (note scores and statuses after the check)

Desk step "View check" (AI Desk v3 M3): an employee's view on a stock is checked against the
daily closes 10 trading days after it was made. Right at 1% or more its way, wrong at 1% or
more the other way, else neutral. Then the notes are reviewed. Runs only while Memory v2 is on.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from us_swing.core.desk_ai_settings import load_settings
from us_swing.core.desk_contract import StepContext, desk_home
from us_swing.core.desk_memory import VIEW_DAYS, Memory, open_views_due, review, score_view
from us_swing.market.candles import CANDLE_DB, CandleReader

log = logging.getLogger(__name__)


def view_move(view: Memory, closes: pd.Series) -> float | None:
    """Percent move from the close of the view's day to the 10th close after it.

    ``None`` when the start or the end close is not there yet.
    """
    series = closes.dropna()
    day = pd.Timestamp(view.made)
    before = series[series.index <= day]
    after = series[series.index > day]
    if before.empty or len(after) < VIEW_DAYS:
        return None
    start = float(before.iloc[-1])
    end = float(after.iloc[VIEW_DAYS - 1])
    if start <= 0:
        return None
    return (end - start) / start * 100


class ViewCheckStep:
    """Checks due employee views against daily closes on each desk run."""

    name = "View check"

    def __init__(self, candles: Path = CANDLE_DB) -> None:
        """Set the candle file; injectable for tests."""
        self._candles = candles

    def __call__(self, ctx: StepContext) -> None:
        """Check the due views and review the notes; a failure never stops the run."""
        home = ctx.home or desk_home()
        if not load_settings(home).memory_v2_on:
            return
        try:
            self._check(home, ctx.started_at.date().isoformat())
            review(home, ctx.started_at)
        except Exception:  # noqa: BLE001 — a view check must never fail the run
            log.exception("[Memory] Could not check the views")

    def _check(self, home: Path, today: str) -> None:
        views = open_views_due(home, today)
        if not views:
            return
        try:
            bars = CandleReader(self._candles, home).read({v.symbol for v in views})
        except FileNotFoundError:
            log.warning("[Memory] No candle file yet; views are checked on a later run")
            return
        done = {"right": 0, "wrong": 0, "neutral": 0}
        for view in views:
            if view.symbol not in bars.closes.columns:
                log.debug("[Memory] No closes for %s yet", view.symbol)
                continue
            move = view_move(view, bars.closes[view.symbol])
            if move is None:
                continue
            result = score_view(home, view.id, move, today)
            if result:
                done[result] += 1
        checked = sum(done.values())
        if checked:
            log.info("[Memory] Checked %d view(s): %d right, %d wrong", checked, done["right"],
                     done["wrong"])
