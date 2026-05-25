"""
Module: MD-EXE-010.001.M01 — Strategy Runner
Parent SRD: SRD-EXE-010.001
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from us_swing.execution.strategy_engine._evaluator import (
    ConditionEvaluator as _EngineEvaluator,
    EvaluatorError,
)
log = logging.getLogger(__name__)

_INTRADAY_DB_PATH: Path = Path.home() / ".usswing" / "candles.db"
_POLL_INTERVAL_MS: int = 30_000
_TF_TABLE: dict[str, str] = {"3m": "price_3m", "15m": "price_15m"}


# ── DataFrame candle loader ───────────────────────────────────────────────────

def _load_candles_df(
    symbol: str,
    db_path: Path,
    limit: int = 200,
) -> dict[str, pd.DataFrame]:
    """Load 3m and 15m bars for *symbol* from SQLite as DataFrames."""
    if not db_path.exists():
        return {}
    result: dict[str, pd.DataFrame] = {}
    try:
        with sqlite3.connect(str(db_path)) as conn:
            for tf, table in _TF_TABLE.items():
                cur = conn.execute(
                    f"SELECT datetime, open, high, low, close, volume"  # noqa: S608
                    f" FROM {table} WHERE symbol = ?"
                    f" ORDER BY datetime ASC LIMIT ?",
                    (symbol, limit),
                )
                rows = cur.fetchall()
                if rows:
                    result[tf] = pd.DataFrame(
                        rows,
                        columns=["datetime", "open", "high", "low", "close", "volume"],
                    )
    except Exception:
        log.warning("[Strategy] Failed to load candle frames for %s", symbol)
    return result


# ── Scope helper ─────────────────────────────────────────────────────────────

def _apply_scope(all_symbols: list[str], config: Any) -> list[str]:
    if config.symbol_mode == "include":
        inc: set[str] = set(config.symbols_include)
        return [s for s in all_symbols if s in inc]
    if config.symbol_mode == "exclude":
        exc: set[str] = set(config.symbols_exclude)
        return [s for s in all_symbols if s not in exc]
    return list(all_symbols)


# ── StrategyRunWorker ─────────────────────────────────────────────────────────

class StrategyRunWorker(QThread):
    """Background polling thread that drives the Active → Running → Active state machine."""

    status_changed = pyqtSignal(str, str)   # (strategy_name, new_status)
    symbols_changed = pyqtSignal(str, list) # (strategy_name, running_symbols)

    def __init__(
        self,
        config: Any,
        get_filtered_symbols: Callable[[], list[str]],
        db_path: Path = _INTRADAY_DB_PATH,
        poll_interval_ms: int = _POLL_INTERVAL_MS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._get_filtered_symbols = get_filtered_symbols
        self._db_path = db_path
        self._poll_interval_ms = poll_interval_ms
        self._state: str = "Active"
        self._running_symbols: list[str] = []

    def run(self) -> None:
        self._evaluator = _EngineEvaluator()
        while not self.isInterruptionRequested():
            self._tick()
            self._sleep_interruptible(self._poll_interval_ms)

    def _tick(self) -> None:
        if self._state == "Active":
            self._check_entry()
        elif self._state == "Running":
            self._check_exit()

    def _check_entry(self) -> None:
        try:
            symbols = self._get_filtered_symbols()
        except Exception:
            log.warning("[Strategy] Failed to retrieve filtered symbols for %s", self._config.name)
            return

        entry_expr: str = self._config.entry_condition
        entered: list[str] = []
        for s in symbols:
            candles = _load_candles_df(s, self._db_path)
            try:
                if self._evaluator.evaluate(entry_expr, candles, s):
                    entered.append(s)
            except EvaluatorError:
                log.warning("[Strategy] Entry condition failed for %s — expr: %.120s", s, entry_expr)
        if entered:
            self._running_symbols = entered
            self._state = "Running"
            self.status_changed.emit(self._config.name, "Running")
            self.symbols_changed.emit(self._config.name, list(entered))
            log.info(
                "[Strategy] %s entered Running — %d stock(s) matched entry",
                self._config.name, len(entered),
            )

    def _check_exit(self) -> None:
        exit_expr: str = self._config.exit_condition
        still_running: list[str] = []
        for s in self._running_symbols:
            candles = _load_candles_df(s, self._db_path)
            try:
                exited = self._evaluator.evaluate(exit_expr, candles, s)
            except EvaluatorError:
                log.warning("[Strategy] Exit condition failed for %s — expr: %.120s", s, exit_expr)
                exited = False
            if not exited:
                still_running.append(s)
        if len(still_running) < len(self._running_symbols):
            exited_count = len(self._running_symbols) - len(still_running)
            log.info(
                "[Strategy] %s — %d stock(s) exited position",
                self._config.name, exited_count,
            )
        self._running_symbols = still_running
        if not self._running_symbols:
            self._state = "Active"
            self.status_changed.emit(self._config.name, "Active")
            self.symbols_changed.emit(self._config.name, [])
            log.info("[Strategy] %s returned to Active — all positions exited", self._config.name)

    def _sleep_interruptible(self, ms: int) -> None:
        elapsed = 0
        while elapsed < ms and not self.isInterruptionRequested():
            QThread.msleep(100)
            elapsed += 100

    def request_stop(self) -> None:
        self.requestInterruption()
