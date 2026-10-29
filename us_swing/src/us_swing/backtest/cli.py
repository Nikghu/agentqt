"""
Module: MD-BKT-002.009.M06 — backtest/cli.py
Parent SRD: SRD-BKT-002.009

Command line: ``python -m us_swing.backtest.cli estimate|run PLAN``.
``run`` does Step 1, then Step 2 when the plan lists strategies.
"""
from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from us_swing.backtest.cache import StepCache
from us_swing.backtest.results import ResultsStore
from us_swing.backtest.service import BacktestService
from us_swing.backtest.spec import RunPlan
from us_swing.backtest.steps.stocks import StepRefused
from us_swing.backtest.store import BacktestStore
from us_swing.core.backtest_bridge import load_preset_dict, load_strategies, load_universe


def _default_service() -> BacktestService:
    return BacktestService(BacktestStore(), StepCache(), ResultsStore(),
                           load_universe, load_preset_dict, load_strategies)


def main(argv: Sequence[str] | None = None, service: BacktestService | None = None) -> int:
    """Run the command line; returns the process exit code."""
    parser = argparse.ArgumentParser(prog="us_swing.backtest.cli")
    parser.add_argument("command", choices=("estimate", "run"))
    parser.add_argument("plan", type=Path, help="run plan JSON file")
    parser.add_argument("--user", default="admin", help="user id for preset access")
    parser.add_argument("--workers", type=int, default=4, help="worker processes (0 = none)")
    args = parser.parse_args(argv)

    plan = RunPlan.from_json(args.plan.read_text(encoding="utf-8"))
    svc = service or _default_service()
    est = svc.estimate(plan, args.user)
    print(f"{len(est.symbols)} stocks · {len(est.missing_1d)} missing 1d · "
          f"{len(est.missing_3m)} missing 3m candles")
    if not est.benchmark_ok:
        print("SPY has no 1d candles in the backtest store")
    print(f"Step 1: {est.days_cached} of {est.days_total} days cached")
    for message in est.errors:
        print(f"Error: {message}")
    if est.errors:
        return 1
    if args.command == "estimate":
        return 0

    def show(done: int, total: int) -> None:
        print(f"\rDays {done} of {total}", end="", flush=True)

    try:
        result = svc.run_stocks(plan, args.user, workers=args.workers, progress=show)
    except (StepRefused, ValueError) as exc:
        print(f"\nError: {exc}")
        return 1
    frame = result.frame
    print(f"\n{len(result.days)} days · {len(frame)} passes in total")
    if not frame.empty:
        last = frame[frame["date"] == frame["date"].max()].head(5)
        print(f"Top 5 on {last['date'].iloc[0]}: "
              + ", ".join(f"{r.symbol} {r.score:.2f}" for r in last.itertuples()))
    if not plan.strategies:
        return 0
    try:
        found = svc.run_signals(
            plan, result, workers=args.workers,
            progress=lambda d, t: print(f"\rStocks {d} of {t}", end="", flush=True),
        )
    except ValueError as exc:
        print(f"\nError: {exc}")
        return 1
    print()
    for name, group in found.groupby("strategy"):
        entries = int((group["kind"] == "entry").sum())
        print(f"{name}: {entries} entry and {len(group) - entries} exit periods "
              f"on {group['symbol'].nunique()} stocks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
