"""
Module: MD-EXE-022.012.M05 — custom indicator failure guard
Parent SRD: SRD-EXE-022.012

Each live call of a custom indicator goes through the guard: an error, bad output
or a slow run counts as a failure and gives no signal (SRD-EXE-022.012); three
failures in a row on one stock tell the listeners to stop the strategies using it
(.013). User code runs in a worker thread with a hard wait, so a plugin that never
returns cannot freeze the engine; such a plugin is marked hung and never called again.
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any, TypeVar

_log = logging.getLogger(__name__)

TIME_LIMIT_S = 2.0
FAILURES_TO_STOP = 3

T = TypeVar("T")


class PluginCallError(Exception):
    """One custom indicator call failed (error, bad output or too slow)."""

    def __init__(self, plugin_name: str, message: str) -> None:
        super().__init__(message)
        self.plugin_name = plugin_name


class DeadlineExceeded(TimeoutError):
    """User code did not finish in time; its thread is left running in the background."""


class PluginExit(RuntimeError):
    """User code called ``sys.exit()``; turned into a normal error so the app keeps running."""


def call_with_deadline(call: Callable[[], T], seconds: float) -> T:
    """Run ``call`` in a daemon thread and wait at most ``seconds``.

    Raises:
        DeadlineExceeded: still running after ``seconds``.
        PluginExit: it called ``sys.exit()``.
        Exception: whatever ``call`` raised.
    """
    box: dict[str, Any] = {}

    def target() -> None:
        try:
            box["value"] = call()
        except BaseException as exc:  # noqa: BLE001 — hand every outcome back to the caller
            box["error"] = exc

    worker = threading.Thread(target=target, name="usswing-plugin", daemon=True)
    worker.start()
    worker.join(seconds)
    if worker.is_alive():
        raise DeadlineExceeded(f"did not finish in {seconds:g} s")
    error = box.get("error")
    if isinstance(error, SystemExit):
        raise PluginExit("called sys.exit()")
    if isinstance(error, Exception):
        raise error
    if error is not None:
        raise RuntimeError(f"stopped with {type(error).__name__}")
    return box["value"]  # type: ignore[no-any-return]


class PluginGuard:
    """Times each call, counts failures in a row per indicator and stock, calls back at the limit."""

    def __init__(self, clock: Callable[[], float] = time.perf_counter,
                 limit_s: float = TIME_LIMIT_S, failures_to_stop: int = FAILURES_TO_STOP) -> None:
        self._clock = clock
        self._limit_s = limit_s
        self._failures_to_stop = failures_to_stop
        self._lock = threading.Lock()
        self._counts: dict[tuple[str, str], int] = {}
        self._last_warned: dict[tuple[str, str], str] = {}
        self._hung: set[str] = set()
        self._listeners: list[Callable[[str], None]] = []

    def run(self, name: str, call: Callable[[], T], *, symbol: str = "", candle: str = "",
            passthrough: tuple[type[Exception], ...] = ()) -> T:
        """Run ``call`` for indicator ``name`` on ``symbol``.

        Raises:
            PluginCallError: the call raised, took too long, or the indicator is hung.
        """
        with self._lock:
            hung = name in self._hung
        if hung:
            raise PluginCallError(name, "stopped earlier because it did not finish")
        start = self._clock()
        try:
            result = call_with_deadline(call, self._limit_s)
        except passthrough:
            raise
        except DeadlineExceeded as exc:
            self._hang(name, symbol, str(exc))
            raise PluginCallError(name, str(exc)) from exc
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
            self._counts[(name, symbol)] = 0
        return result

    def failures(self, name: str, symbol: str = "") -> int:
        with self._lock:
            return self._counts.get((name, symbol), 0)

    def is_hung(self, name: str) -> bool:
        with self._lock:
            return name in self._hung

    def add_limit_listener(self, listener: Callable[[str], None]) -> None:
        with self._lock:
            self._listeners.append(listener)

    def remove_limit_listener(self, listener: Callable[[str], None]) -> None:
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def forget(self, name: str) -> None:
        """Clear counts and the hung mark, e.g. after the user reloads the indicator."""
        with self._lock:
            self._hung.discard(name)
            for key in [k for k in self._counts if k[0] == name]:
                del self._counts[key]

    def _hang(self, name: str, symbol: str, message: str) -> None:
        with self._lock:
            self._hung.add(name)
            listeners = list(self._listeners)
        _log.error("[Indicators] %s %s on %s and was stopped; restart the app to free it",
                   name, message, symbol or "a stock")
        for listener in listeners:
            listener(name)

    def _fail(self, name: str, symbol: str, candle: str, message: str) -> None:
        key = (name, symbol)
        with self._lock:
            count = self._counts.get(key, 0) + 1
            reached = count >= self._failures_to_stop
            self._counts[key] = 0 if reached else count
            first_on_candle = self._last_warned.get(key) != candle or not candle
            self._last_warned[key] = candle
            listeners = list(self._listeners) if reached else []
        if first_on_candle:
            _log.warning("[Indicators] %s failed on %s: %s", name, symbol or "a stock", message)
        for listener in listeners:
            listener(name)


GUARD = PluginGuard()
