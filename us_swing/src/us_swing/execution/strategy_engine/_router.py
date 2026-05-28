"""
Module: MD-EXE-011.001.M04 — Signal queue consumer + dispatch + watchdog
Parent SRD: SRD-EXE-011.008 — SRD-EXE-011.013, SRD-EXE-011.017, SRD-EXE-011.018,
           SRD-EXE-013.001 — .008
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, time
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import pandas as pd

from us_swing.execution import ExecutionEnums

from ._context import _StrategyContext
from ._evaluator import ConditionEvaluator, EvaluatorError
from ._events import (
    StrategyEntered,
    StrategyErrored,
    StrategyExited,
    StrategySignalDropped,
    StrategySignalPending,
    StrategySquaredOff,
)
from ._rex_counter import RexCounterRepository
from ._signals import Action, PendingSignalSink, TradeSignal

if TYPE_CHECKING:
    from us_swing.data.models import OHLCVBar
    from us_swing.execution.trade_cycle._protocols import TradeCycleQuery

    from ._protocols import (
        EventBus,
        ExecutionSubmitter,
        FillEvent,
        RejectEvent,
        RiskValidator,
    )

log = logging.getLogger(__name__)

_ET = ZoneInfo("America/New_York")
_END_TIME_TICK_S = 30.0


def _parse_hhmm(text: str) -> time:
    hh, mm = text.split(":")
    return time(int(hh), int(mm))


class _Router:
    """Signal-queue consumer + per-bar evaluation + watchdog loops.

    All business logic for state transitions and dispatch lives here so the
    engine layer (`_engine.py`) can stay a thin Qt / asyncio adapter.
    """

    def __init__(
        self,
        *,
        queue: asyncio.Queue[TradeSignal],
        registry: dict[str, _StrategyContext],
        evaluator: ConditionEvaluator,
        risk: RiskValidator,
        submitter: ExecutionSubmitter,
        pending: PendingSignalSink,
        bus: EventBus,
        rex_counters: RexCounterRepository | None = None,
        clock: Callable[[], datetime] | None = None,
        user_id_provider: Callable[[], int] | None = None,
        cycle_query: TradeCycleQuery | None = None,
    ) -> None:
        self._queue = queue
        self._registry = registry
        self._evaluator = evaluator
        self._risk = risk
        self._submitter = submitter
        self._pending = pending
        self._bus = bus
        self._rex_counters = rex_counters
        self._clock = clock or (lambda: datetime.now(_ET))
        self._user_id_provider = user_id_provider or (lambda: 0)
        self._cycle_query = cycle_query
        self._stop_event = asyncio.Event()
        self._emergency_active = False
        self._quiesced_event = asyncio.Event()
        self._quiesced_event.set()

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def request_stop(self) -> None:
        self._stop_event.set()

    def stop_requested(self) -> bool:
        return self._stop_event.is_set()

    # ── Derivation helpers ───────────────────────────────────────────────────

    def _has_open_cycle(self, strategy_id: str, symbol: str) -> bool:
        if self._cycle_query is None:
            return False
        return self._cycle_query.has_open_cycle(strategy_id, symbol)

    def _open_cycle_symbols(self, strategy_id: str) -> list[str]:
        if self._cycle_query is None:
            return []
        return [s.symbol for s in self._cycle_query.open_cycles_for_strategy(strategy_id)]

    # ── Per-bar evaluation (called from engine fan-out) ──────────────────────

    async def evaluate(
        self,
        ctx: _StrategyContext,
        symbol: str,
        candles: dict[str, pd.DataFrame],
        bar: OHLCVBar,
    ) -> None:
        """Evaluate a single context's entry/exit conditions on a bar close.

        Holds the per-(strategy, symbol) lock only across read-state →
        mutate-state. Order placement (`queue.put`) happens outside the lock.
        """
        if self._emergency_active:
            return
        if ctx.run_state is ExecutionEnums.StrategyRunState.STOPPED:
            return
        if ctx.run_state is ExecutionEnums.StrategyRunState.SQUARING_OFF:
            return
        if not ctx.within_schedule(self._clock()):
            return
        if not ctx.accepts(symbol):
            return

        action: Action | None = None
        signal: TradeSignal | None = None

        async with ctx.lock_for(symbol):
            if symbol in ctx.in_flight:
                log.debug("[Strategy] %s %s duplicate signal suppressed (in flight)",
                          ctx.name, symbol)
                return

            has_open = self._has_open_cycle(ctx.name, symbol)

            if has_open:
                if not ctx.cfg.exit_condition:
                    return
                try:
                    fired = self._evaluator.evaluate(ctx.cfg.exit_condition, candles, symbol)
                except EvaluatorError as exc:
                    log.warning("[Strategy] %s exit-expr failed for %s: %s",
                                ctx.name, symbol, exc)
                    self._bus.publish(
                        StrategyErrored(strategy_id=ctx.name, symbol=symbol, message=str(exc))
                    )
                    return
                if not fired:
                    return

                signal = TradeSignal(
                    action=Action.EXIT,
                    symbol=symbol,
                    strategy_id=ctx.name,
                    entry_price=float(bar.close),
                    reason="strategy",
                    user_id=self._user_id_provider(),
                )
                ctx.in_flight.add(symbol)
                action = Action.EXIT

            else:
                if not ctx.cfg.entry_condition:
                    return
                try:
                    fired = self._evaluator.evaluate(ctx.cfg.entry_condition, candles, symbol)
                except EvaluatorError as exc:
                    log.warning("[Strategy] %s entry-expr failed for %s: %s",
                                ctx.name, symbol, exc)
                    self._bus.publish(
                        StrategyErrored(strategy_id=ctx.name, symbol=symbol, message=str(exc))
                    )
                    return
                if not fired:
                    return

                if self._rex_counters is not None:
                    remaining = self._rex_counters.get(ctx.name, symbol)
                    if remaining is not None and remaining < 0:
                        signal_pre = self._build_entry_signal(ctx, symbol, bar)
                        self._bus.publish(
                            StrategySignalDropped(signal=signal_pre, reason="rex_limit")
                        )
                        log.info("[Strategy] %s ENTRY blocked for %s — rex limit reached",
                                 ctx.name, symbol)
                        return

                cap = self._risk.can_allocate(ctx.name, ctx.cfg.capital_max)
                if not cap.ok:
                    signal_pre = self._build_entry_signal(ctx, symbol, bar)
                    self._bus.publish(
                        StrategySignalDropped(signal=signal_pre, reason=cap.reason or "capital_cap")
                    )
                    log.warning("[Strategy] %s ENTRY dropped for %s — %s",
                                ctx.name, symbol, cap.reason or "capital_cap")
                    return

                signal = self._build_entry_signal(ctx, symbol, bar)
                ctx.in_flight.add(symbol)
                action = Action.ENTRY

        if signal is not None and action is not None:
            self._quiesced_event.clear()
            await self._queue.put(signal)

    # ── Router consumer loop ─────────────────────────────────────────────────

    async def run_router_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                signal = await asyncio.wait_for(self._queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            try:
                await self._dispatch(signal)
            except Exception as exc:  # defensive — never let one bad signal kill the loop
                log.exception("[Strategy] router dispatch crashed for %s/%s: %s",
                              signal.strategy_id, signal.symbol, exc)
                self._bus.publish(
                    StrategyErrored(
                        strategy_id=signal.strategy_id,
                        symbol=signal.symbol,
                        message=str(exc),
                    )
                )
            finally:
                self._queue.task_done()

    async def _dispatch(self, signal: TradeSignal) -> None:
        ctx = self._registry.get(signal.strategy_id)
        if ctx is None:
            log.warning("[Strategy] dispatch saw signal for unknown strategy %s",
                        signal.strategy_id)
            return

        # Manual mode OR auto-with-auto_trade-off → Pending queue
        if ctx.cfg.mode == "manual" or not ctx.cfg.auto_trade:
            self._pending.add(signal)
            self._bus.publish(StrategySignalPending(signal=signal))
            return

        # Auto + auto_trade=True → validate then submit
        result = self._risk.validate(signal)
        if not result.ok:
            self._bus.publish(
                StrategySignalDropped(signal=signal, reason=result.reason or "risk_reject")
            )
            await self._rollback(ctx, signal.symbol)
            return

        order_id = self._submitter.submit(signal, result.qty)
        if order_id is None:
            self._bus.publish(
                StrategySignalDropped(signal=signal, reason="submitter_returned_none")
            )
            await self._rollback(ctx, signal.symbol)

    async def _rollback(self, ctx: _StrategyContext, symbol: str) -> None:
        """Clear the in-flight flag when a dispatch is rejected."""
        async with ctx.lock_for(symbol):
            ctx.in_flight.discard(symbol)
        self._maybe_signal_quiesced()

    # ── Fill / reject hooks (called from engine Qt slots) ────────────────────

    def on_order_fill(self, fill: FillEvent) -> None:
        ctx = self._registry.get(fill.strategy_id)
        if ctx is None:
            return
        ctx.in_flight.discard(fill.symbol)
        if fill.is_entry:
            self._bus.publish(
                StrategyEntered(
                    strategy_id=fill.strategy_id,
                    symbol=fill.symbol,
                    entry_price=fill.fill_price,
                    qty=fill.fill_qty,
                )
            )
            if self._rex_counters is not None:
                self._rex_counters.decrement(
                    fill.strategy_id,
                    fill.symbol,
                    init_value=ctx.cfg.rex_count,
                )
        else:
            self._bus.publish(
                StrategyExited(
                    strategy_id=fill.strategy_id,
                    symbol=fill.symbol,
                    exit_price=fill.fill_price,
                    qty=fill.fill_qty,
                    reason="fill",
                )
            )
        self._maybe_signal_quiesced()

    def on_order_reject(self, reject: RejectEvent) -> None:
        ctx = self._registry.get(reject.strategy_id)
        if ctx is None:
            return
        ctx.in_flight.discard(reject.symbol)
        self._bus.publish(
            StrategyErrored(
                strategy_id=reject.strategy_id,
                symbol=reject.symbol,
                message=f"order_reject: {reject.reason}",
            )
        )
        log.debug("[Strategy] %s %s order rejected — %s",
                  reject.strategy_id, reject.symbol, reject.reason)
        self._maybe_signal_quiesced()

    # ── End-time watcher ─────────────────────────────────────────────────────

    async def run_end_time_watcher(self) -> None:
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=_END_TIME_TICK_S)
            except asyncio.TimeoutError:
                pass
            else:
                return
            await self._sweep_end_times()

    async def _sweep_end_times(self) -> None:
        now_et = self._clock()
        for ctx in list(self._registry.values()):
            if ctx.cfg.trade_type != "Intraday":
                continue
            end_t = _parse_hhmm(ctx.cfg.end_time)
            if now_et.time() < end_t:
                continue
            for symbol in self._open_cycle_symbols(ctx.name):
                await self._force_exit(ctx, symbol, reason="end_time")

    async def _force_exit(
        self,
        ctx: _StrategyContext,
        symbol: str,
        *,
        reason: str,
    ) -> None:
        async with ctx.lock_for(symbol):
            if symbol in ctx.in_flight:
                return
            if not self._has_open_cycle(ctx.name, symbol):
                return
            signal = TradeSignal(
                action=Action.EXIT,
                symbol=symbol,
                strategy_id=ctx.name,
                reason=reason,
                user_id=self._user_id_provider(),
            )
            ctx.in_flight.add(symbol)
        self._quiesced_event.clear()
        await self._queue.put(signal)
        self._bus.publish(
            StrategySquaredOff(strategy_id=ctx.name, symbol=symbol, reason=reason)
        )

    # ── Emergency stop ───────────────────────────────────────────────────────

    async def emergency_stop(self) -> None:
        """Force exit every open cycle across every strategy, then block until quiesced."""
        self._emergency_active = True
        try:
            for ctx in list(self._registry.values()):
                for symbol in self._open_cycle_symbols(ctx.name):
                    await self._force_exit(ctx, symbol, reason="emergency")
            await self._quiesced_event.wait()
        finally:
            self._emergency_active = False

    async def squaring_off_exit(self, ctx: _StrategyContext) -> int:
        """Enqueue forced EXIT signals for every open cycle of *ctx*.

        Returns the number of exits enqueued.  Called when the user
        transitions a strategy from RUNNING → SQUARING_OFF.
        """
        count = 0
        for symbol in self._open_cycle_symbols(ctx.name):
            await self._force_exit(ctx, symbol, reason="squaring_off")
            count += 1
        return count

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _build_entry_signal(
        self,
        ctx: _StrategyContext,
        symbol: str,
        bar: OHLCVBar,
    ) -> TradeSignal:
        entry_price = float(bar.close)
        stop_loss: float | None = None
        target: float | None = None
        if ctx.cfg.stoploss_enabled:
            stop_loss = entry_price * (1.0 - ctx.cfg.stoploss_value / 100.0)
        if ctx.cfg.target_enabled:
            target = entry_price * (1.0 + ctx.cfg.target_value / 100.0)
        return TradeSignal(
            action=Action.ENTRY,
            symbol=symbol,
            strategy_id=ctx.name,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target=target,
            qty_recommended=1,
            user_id=self._user_id_provider(),
        )

    def _maybe_signal_quiesced(self) -> None:
        """Mark the quiesced event when no strategy has any signal in flight."""
        for ctx in self._registry.values():
            if ctx.in_flight:
                return
        self._quiesced_event.set()
