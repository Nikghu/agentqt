"""
Module: MD-EXE-011.001.M01 — StrategyEngine (Qt + asyncio bridge)
Parent SRD: SRD-EXE-011.001 — .003, .013, .014

This is the only file under `strategy_engine/` permitted to import PyQt6
— it is the explicit boundary between the Qt-driven AppService world and
the asyncio-driven business logic in `_router.py` + friends.
"""
from __future__ import annotations

import asyncio
import logging
import time as _time
from collections.abc import Callable
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from us_swing.execution.strategy_engine._context import _CycleState, _StrategyContext
from us_swing.execution.strategy_engine._evaluator import ConditionEvaluator
from us_swing.execution.strategy_engine._events import (
    StrategyEntered,
    StrategyExited,
    StrategySquaredOff,
)
from us_swing.execution.strategy_engine._protocols import (
    EventBus,
    ExecutionSubmitter,
    FillEvent,
    RejectEvent,
    RiskValidator,
)
from us_swing.execution.strategy_engine._router import _Router
from us_swing.execution.strategy_engine._signals import PendingSignalSink, TradeSignal

if TYPE_CHECKING:
    import pandas as pd

    from us_swing.data.models import OHLCVBar
    from us_swing.gui.strategy_builder_dialog import StrategyConfig

log = logging.getLogger(__name__)

_WRITEBACK_DEBOUNCE_S = 0.25


class StrategyEngine(QThread):
    """QThread-hosted asyncio engine that drives strategy evaluation.

    Owns the per-thread asyncio event loop, the `_Router`, and the
    `_StrategyContext` registry. AppService connects its `candle_closed`,
    `order_fill`, `order_reject`, `circuit_breaker_changed`, and
    `pending_signal_dismissed` signals to the corresponding `on_*` slots.
    """

    started_ok = pyqtSignal()
    stopped = pyqtSignal()

    def __init__(
        self,
        *,
        registry_loader: Callable[[], list[StrategyConfig]],
        registry_saver: Callable[[list[StrategyConfig]], None],
        candles_provider: Callable[[str], dict[str, pd.DataFrame]],
        bar_provider: Callable[[str, str], OHLCVBar | None],
        risk: RiskValidator,
        submitter: ExecutionSubmitter,
        pending: PendingSignalSink,
        bus: EventBus,
        primary_timeframe: str = "3m",
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._registry_loader = registry_loader
        self._registry_saver = registry_saver
        self._candles_provider = candles_provider
        self._bar_provider = bar_provider
        self._risk = risk
        self._submitter = submitter
        self._pending = pending
        self._bus = bus
        self._primary_tf = primary_timeframe

        self._loop: asyncio.AbstractEventLoop | None = None
        self._registry: dict[str, _StrategyContext] = {}
        self._router: _Router | None = None
        self._evaluator = ConditionEvaluator()
        self._cb_active = False
        self._last_persist_at: dict[str, float] = {}
        self._pending_persist = False

    # ── QThread entry point ──────────────────────────────────────────────────

    def run(self) -> None:  # noqa: D401 — Qt override
        try:
            asyncio.run(self._async_run())
        except Exception:
            log.exception("[Strategy] engine loop crashed")
        finally:
            self._loop = None
            self.stopped.emit()

    async def _async_run(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._registry = self._load_registry()

        queue: asyncio.Queue[TradeSignal] = asyncio.Queue(maxsize=512)
        self._router = _Router(
            queue=queue,
            registry=self._registry,
            evaluator=self._evaluator,
            risk=self._risk,
            submitter=self._submitter,
            pending=self._pending,
            bus=self._bus,
        )
        self.started_ok.emit()
        log.info("[Strategy] engine ready — %d active strateg(ies)", len(self._registry))

        await asyncio.gather(
            self._router.run_router_loop(),
            self._router.run_end_time_watcher(),
        )

    # ── Registry load ────────────────────────────────────────────────────────

    def _load_registry(self) -> dict[str, _StrategyContext]:
        out: dict[str, _StrategyContext] = {}
        for cfg in self._registry_loader():
            if cfg.mode == "disabled":
                continue
            cfg.strategy_signal["Status"] = "Active"
            out[cfg.name] = _StrategyContext(cfg=cfg)
        return out

    # ── Qt slots (called from AppService thread) ─────────────────────────────

    @pyqtSlot(str)
    def on_candle_closed(self, symbol: str) -> None:
        if self._loop is None or self._router is None or self._cb_active:
            return
        asyncio.run_coroutine_threadsafe(self._fanout(symbol), self._loop)

    @pyqtSlot(object)
    def on_order_fill(self, fill: FillEvent) -> None:
        if self._router is None:
            return
        self._router.on_order_fill(fill)
        self._schedule_persist(fill.strategy_id)

    @pyqtSlot(object)
    def on_order_reject(self, reject: RejectEvent) -> None:
        if self._router is None:
            return
        self._router.on_order_reject(reject)
        self._schedule_persist(reject.strategy_id)

    @pyqtSlot(bool)
    def on_circuit_breaker(self, active: bool) -> None:
        self._cb_active = active

    @pyqtSlot(str, str)
    def on_pending_dismissed(self, strategy_id: str, symbol: str) -> None:
        """User dismissed a pending signal — roll back UnderEntry/UnderExit."""
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self._rollback_dismissed, strategy_id, symbol)

    def _rollback_dismissed(self, strategy_id: str, symbol: str) -> None:
        ctx = self._registry.get(strategy_id)
        if ctx is None:
            return
        state = ctx.state(symbol)
        if state == _CycleState.UNDER_ENTRY:
            ctx.cycles[symbol] = _CycleState.ACTIVE
        elif state == _CycleState.UNDER_EXIT:
            ctx.cycles[symbol] = _CycleState.RUNNING
        self._schedule_persist(strategy_id)

    # ── Fan-out ──────────────────────────────────────────────────────────────

    async def _fanout(self, symbol: str) -> None:
        if self._router is None or self._cb_active:
            return
        bar = self._bar_provider(symbol, self._primary_tf)
        if bar is None:
            log.debug("[Strategy] fan-out: no bar available for %s/%s",
                      symbol, self._primary_tf)
            return
        candles = self._candles_provider(symbol)
        if not candles:
            return
        accepting = [
            ctx for ctx in self._registry.values() if ctx.accepts(symbol)
        ]
        if not accepting:
            return
        await asyncio.gather(
            *(
                self._router.evaluate(ctx, symbol, candles, bar)
                for ctx in accepting
            )
        )

    # ── Status writeback ─────────────────────────────────────────────────────

    def _schedule_persist(self, strategy_id: str) -> None:
        now = _time.monotonic()
        last = self._last_persist_at.get(strategy_id, 0.0)
        if now - last < _WRITEBACK_DEBOUNCE_S:
            if self._pending_persist:
                return
            self._pending_persist = True
            if self._loop is not None:
                self._loop.call_later(
                    _WRITEBACK_DEBOUNCE_S - (now - last),
                    self._flush_persist,
                )
            return
        self._flush_persist()

    def _flush_persist(self) -> None:
        try:
            cfgs = [ctx.cfg for ctx in self._registry.values()]
            for ctx in self._registry.values():
                primary_state = next(
                    iter(ctx.cycles.values()), _CycleState.ACTIVE
                )
                ctx.cfg.strategy_signal["Status"] = primary_state.value
            self._registry_saver(cfgs)
            now = _time.monotonic()
            for sid in self._registry:
                self._last_persist_at[sid] = now
        except Exception:
            log.exception("[Strategy] registry writeback failed")
        finally:
            self._pending_persist = False

    # ── Sync lifecycle wrappers (called from AppService thread) ──────────────

    def request_stop(self) -> None:
        """Signal both router loops to exit; quits the QThread after they unwind."""
        if self._loop is None or self._router is None:
            return
        self._loop.call_soon_threadsafe(self._router.request_stop)

    def emergency_stop(self, timeout: float = 120.0) -> None:
        """Block until every Running symbol reaches SquareOff."""
        if self._loop is None or self._router is None:
            return
        fut = asyncio.run_coroutine_threadsafe(self._router.emergency_stop(), self._loop)
        try:
            fut.result(timeout=timeout)
        except asyncio.TimeoutError:
            log.error("[Strategy] emergency_stop timed out after %.0fs", timeout)

    def reload_registry(self) -> None:
        """Re-load configurations from disk; diff and patch contexts in-place."""
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self._reload_registry_locked)

    def _reload_registry_locked(self) -> None:
        new_cfgs = {c.name: c for c in self._registry_loader() if c.mode != "disabled"}

        # Remove contexts whose strategy was deleted or disabled.
        for name in list(self._registry.keys()):
            if name not in new_cfgs:
                del self._registry[name]

        # Add new contexts; refresh cfg pointer on existing ones.
        for name, cfg in new_cfgs.items():
            if name in self._registry:
                self._registry[name].cfg = cfg
            else:
                cfg.strategy_signal["Status"] = "Active"
                self._registry[name] = _StrategyContext(cfg=cfg)

        # Publish a synthetic event so listeners can refresh.
        for name in new_cfgs:
            self._bus.publish(
                StrategySquaredOff(strategy_id=name, symbol="*", reason="reload")
            )
        log.info("[Strategy] registry reloaded — %d active strateg(ies)",
                 len(self._registry))

    # ── Test helpers ─────────────────────────────────────────────────────────

    @property
    def registry(self) -> dict[str, _StrategyContext]:
        return self._registry

    @property
    def router(self) -> _Router | None:
        return self._router


# Re-export the entry/exit/squared-off events at the engine level so callers
# don't have to reach into the private `_events` module to subscribe.
__all__ = [
    "StrategyEngine",
    "StrategyEntered",
    "StrategyExited",
    "StrategySquaredOff",
]
