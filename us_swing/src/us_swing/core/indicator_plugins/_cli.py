"""
Module: MD-EXE-022.015.M06 — indicator check command
Parent SRD: SRD-EXE-022.016

``USSwing.exe indicator check <file> [--symbols A,B] [--days N] [--trace out.csv]``
runs the same check as Import on the saved candles, prints the result and can save
the value and debug table as CSV. Exit code 0 means the file passed, 1 means refused.
"""
from __future__ import annotations

import argparse
import sqlite3
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path
from typing import TextIO

import pandas as pd

from usswing import testing

from us_swing.core.indicator_plugins._check import StockFrames, check_file
from us_swing.core.indicator_plugins._registry import builtin_names

PROBE_STOCKS = 3
_OK, _BAD, _NOTE = "✔", "✘", "!"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="USSwing indicator",
                                     description="Check a custom indicator file.")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="check one indicator file")
    check.add_argument("file", type=Path, help="the indicator .py file")
    check.add_argument("--symbols", default="",
                       help="stocks to run on, for example AAPL,MSFT (default: 3 stocks "
                            "with the most 3m candles)")
    check.add_argument("--days", type=int, default=30, help="market days of candles (30)")
    check.add_argument("--trace", type=Path, help="save the value and debug table as CSV")
    check.add_argument("--db", type=Path, help=argparse.SUPPRESS)
    return parser


def run_indicator_command(argv: Sequence[str], out: TextIO) -> int:
    """Run ``indicator <command>``; returns the process exit code."""
    args = _parser().parse_args(list(argv))
    return _check(args.file, args.symbols, args.days, args.trace, args.db, out)


def top_symbols(db_path: Path | None, count: int = PROBE_STOCKS) -> list[str]:
    """The stocks with the most 3m candles."""
    with closing(testing.connect(db_path)) as conn:
        rows = conn.execute("SELECT symbol FROM price_3m GROUP BY symbol "
                            "ORDER BY COUNT(*) DESC, symbol LIMIT ?", (count,)).fetchall()
    return [row[0] for row in rows]


def _stocks(symbols: list[str], days: int, db_path: Path | None) -> list[StockFrames]:
    stocks: list[StockFrames] = []
    for symbol in symbols:
        frames = testing.load_candles(symbol, testing.TIMEFRAMES, days, db_path=db_path)
        kept = {tf: frame for tf, frame in frames.items() if not frame.empty}
        if kept:
            stocks.append((symbol, kept))
    return stocks


def _check(file: Path, symbols_text: str, days: int, trace: Path | None,
           db_path: Path | None, out: TextIO) -> int:
    if not file.is_file():
        print(f"{_BAD} No file at {file}", file=out)
        return 1
    try:
        symbols = ([s.strip().upper() for s in symbols_text.split(",") if s.strip()]
                   or top_symbols(db_path))
        stocks = _stocks(symbols, days, db_path)
    except (OSError, sqlite3.Error, ValueError) as exc:
        print(f"{_BAD} Could not read the saved candles: {exc}", file=out)
        return 1
    if not stocks:
        print(f"{_BAD} No saved candles for {', '.join(symbols) or 'any stock'}", file=out)
        return 1

    report = check_file(file, builtin_names=builtin_names(), candle_probe=lambda: stocks)
    if not report.ok or report.spec is None:
        for reason in report.reasons:
            print(f"{_BAD} {reason}", file=out)
        print(f"{file.name} was refused: {len(report.reasons)} problem(s)", file=out)
        return 1

    spec = report.spec
    print(f"{_OK} {spec.name} {spec.version} passed the file checks", file=out)
    for note in report.notes:
        print(f"{_NOTE} {note}", file=out)
    tables: list[pd.DataFrame] = []
    for symbol, frames in stocks:
        result = testing.run(spec.indicator_class, frames)
        last = result.values.dropna()
        shown = f"last value {last.iloc[-1]:g}" if not last.empty else "no value yet"
        print(f"{_OK} {symbol}: {len(result.values)} {result.main_timeframe} candles, {shown}",
              file=out)
        tables.append(result.table().assign(symbol=symbol))
    print(f"{file.name} passed on {len(stocks)} stock(s)", file=out)
    if trace is not None:
        table = pd.concat(tables, ignore_index=True)
        table = table[["symbol", *[c for c in table.columns if c != "symbol"]]]
        table.to_csv(trace, index=False)
        print(f"Saved the table to {trace}", file=out)
    return 0
