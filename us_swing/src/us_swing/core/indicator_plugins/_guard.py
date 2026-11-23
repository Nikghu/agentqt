"""
Module: MD-EXE-022.012.M05 — custom indicator failure guard
Parent SRD: SRD-EXE-022.012

Each live call of a custom indicator goes through the guard: an error, bad output
or a slow run counts as a failure and gives no signal (SRD-EXE-022.012); three
failures in a row tell the listeners to stop the strategies using it (.013).
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import TypeVar

_log = logging.getLogger(__name__)

TIME_LIMIT_S = 2.0
FAILURES_TO_STOP = 3

T = TypeVar("T")


class PluginCallError(Exception):
    """One custom indicator call failed (error, bad output or too slow)."""

    def __init__(self, plugin_name: str, message: str) -> None:
        super().__init__(message)
        self.plugin_name = plugin_name


class PluginGuard:
    """Times each call, counts failures in a row per indicator and calls back at the limit."""

    def __init__(self, clock: Callable[[], float] = time.perf_counter,
                 limit_s: float = TIME_LIMIT_S, failures_to_stop: int = FAILURES_TO_STOP) -> None:
        self._clock = clock
        self._limit_s = limit_s
        self._failures_to_stop = failures_to_stop
        self._lock = threading.Lock()
        self._counts: dict[str, int] = {}
        self._last_warned: dict[str, str] = {}
        self._listeners: list[Callable[[str], None]] = []

    def run(self, name: str, call: Callable[[], T], *, symbol: str = "", candle: str = "",
            passthrough: tuple[type[Exception], ...] = ()) -> T:
        """Run ``call`` for indicator ``name``.

        Raises:
            PluginCallError: the call raised, or took longer than the time limit.
        """
        start = self._clock()
        try:
            result = call()
        except passthrough:
            raise
        except Exception as exc:  # noqa: BLE001 — any error in user code is a failure
            message = str(exc) or type(exc).__name__
            self._fail(name, symbol, candle, message)
            raise PluginCallError(name, message) from exc
        took = self._clock() - start
        if took > self._limit_s:
            message = f"took {took:.1f} s (limit {self._limit_s:g} s)"
            self._fail(name, symbol, candle, message)
            raise PluginCallError(name, message)
        with self._lock:
            self._counts[name] = 0
        return result

    def failures(self, name: str) -> int:
        with self._lock:
            return self._counts.get(name, 0)

    def add_limit_listener(self, listener: Callable[[str], None]) -> None:
        with self._lock:
            self._listeners.append(listener)

    def remove_limit_listener(self, listener: Callable[[str], None]) -> None:
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def _fail(self, name: str, symbol: str, candle: str, message: str) -> None:
        with self._lock:
            count = self._counts.get(name, 0) + 1
            reached = count >= self._failures_to_stop
            self._counts[name] = 0 if reached else count
            first_on_candle = self._last_warned.get(name) != candle or not candle
            self._last_warned[name] = candle
            listeners = list(self._listeners) if reached else []
        if first_on_candle:
            _log.warning("[Indicators] %s failed on %s: %s", name, symbol or "a stock", message)
        for listener in listeners:
            listener(name)


GUARD = PluginGuard()
