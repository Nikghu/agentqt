"""
Module: MD-EXE-011.001.M02 — _StrategyContext + StrategyRunState plumbing
Parent SRD: SRD-EXE-011.002, .004, .005, .010, SRD-EXE-013.001 — .008
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from us_swing.execution import ExecutionEnums

if TYPE_CHECKING:
    from us_swing.gui.strategy_builder_dialog import StrategyConfig


_ET = ZoneInfo("America/New_York")

_DAY_NAMES = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


def _parse_hhmm(text: str) -> time:
    hh, mm = text.split(":")
    return time(int(hh), int(mm))


def _parse_date(text: str) -> date:
    return datetime.strptime(text, "%Y-%m-%d").date()


@dataclass
class _StrategyContext:
    cfg: StrategyConfig
    run_state: ExecutionEnums.StrategyRunState = ExecutionEnums.StrategyRunState.STOPPED
    in_flight: set[str] = field(default_factory=set)
    cycle_locks: dict[str, asyncio.Lock] = field(default_factory=dict)
    last_eval_at: datetime | None = None
    capital_warned: bool = False
    margin_warned: bool = False

    @property
    def name(self) -> str:
        return self.cfg.name

    def accepts(self, symbol: str) -> bool:
        mode = self.cfg.symbol_mode
        if mode == "all":
            return True
        if mode == "include":
            return symbol in self.cfg.symbols_include
        if mode == "exclude":
            return symbol not in self.cfg.symbols_exclude
        return False

    def within_schedule(self, now_et: datetime | None = None) -> bool:
        now = now_et if now_et is not None else datetime.now(_ET)
        if now.tzinfo is None:
            now = now.replace(tzinfo=_ET)
        elif now.tzinfo is not _ET:
            now = now.astimezone(_ET)

        start_t = _parse_hhmm(self.cfg.start_time)
        end_t = _parse_hhmm(self.cfg.end_time)
        if not (start_t <= now.time() < end_t):
            return False

        start_d = _parse_date(self.cfg.start_date)
        end_d = _parse_date(self.cfg.end_date)
        if not (start_d <= now.date() <= end_d):
            return False

        weekday = _DAY_NAMES[now.weekday()]
        if weekday not in self.cfg.days:
            return False

        return True

    def lock_for(self, symbol: str) -> asyncio.Lock:
        lock = self.cycle_locks.get(symbol)
        if lock is None:
            lock = asyncio.Lock()
            self.cycle_locks[symbol] = lock
        return lock
