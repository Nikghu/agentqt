"""
Module: MD-EXE-019.002.M02 — execution/trade_cycle/_pnl_history.py
Parent SRD: SRD-EXE-019.002

Pure summary of a strategy's realized P&L history, built from its closed
trade cycles in close order.  No I/O.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from us_swing.execution.trade_cycle._dto import CycleSnapshot


@dataclass(frozen=True, slots=True)
class PnlPoint:
    """One closed trade on the running-total line."""

    closed_at: str
    symbol: str
    pnl: float
    cumulative: float


@dataclass(frozen=True, slots=True)
class StrategyPnlSummary:
    """Realized P&L history of one strategy.

    ``max_drawdown`` is ≤ 0: the largest fall of the running total from a
    previous peak.  ``dd_start`` is the peak point index (-1 = the zero
    start) and ``dd_end`` the lowest point index; both -1 when there is no
    drawdown.
    """

    points: tuple[PnlPoint, ...] = ()
    total: float = 0.0
    trades: int = 0
    wins: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    max_drawdown: float = 0.0
    dd_start: int = -1
    dd_end: int = -1
    today: float = 0.0


def summarise(
    cycles: Iterable[CycleSnapshot],
    today_start_iso: str,
    today_end_iso: str,
) -> StrategyPnlSummary:
    """Build the summary from closed cycles already in close order.

    Args:
        cycles: Closed cycles of one strategy, oldest first.
        today_start_iso: UTC ISO start of today (inclusive).
        today_end_iso: UTC ISO end of today (exclusive).

    Returns:
        The summary; cycles without ``realized_pnl_usd`` are skipped.
    """
    points: list[PnlPoint] = []
    cumulative = peak = 0.0
    peak_idx = -1
    max_dd = 0.0
    dd_start = dd_end = -1
    today = 0.0
    for c in cycles:
        if c.realized_pnl_usd is None:
            continue
        pnl = float(c.realized_pnl_usd)
        cumulative += pnl
        closed_at = c.closed_at or ""
        points.append(PnlPoint(closed_at, c.symbol, pnl, cumulative))
        idx = len(points) - 1
        if cumulative > peak:
            peak, peak_idx = cumulative, idx
        elif cumulative - peak < max_dd:
            max_dd = cumulative - peak
            dd_start, dd_end = peak_idx, idx
        if today_start_iso <= closed_at < today_end_iso:
            today += pnl

    if not points:
        return StrategyPnlSummary()
    wins = [p.pnl for p in points if p.pnl > 0]
    losses = [p.pnl for p in points if p.pnl < 0]
    return StrategyPnlSummary(
        points=tuple(points),
        total=cumulative,
        trades=len(points),
        wins=len(wins),
        win_rate=len(wins) / len(points),
        avg_win=sum(wins) / len(wins) if wins else 0.0,
        avg_loss=sum(losses) / len(losses) if losses else 0.0,
        max_drawdown=max_dd,
        dd_start=dd_start,
        dd_end=dd_end,
        today=today,
    )


__all__ = ["PnlPoint", "StrategyPnlSummary", "summarise"]
