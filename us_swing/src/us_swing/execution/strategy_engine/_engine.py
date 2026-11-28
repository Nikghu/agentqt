"""
Module: MD-EXE-011.001.M01 — StrategyEngine (Qt + asyncio bridge)
Parent SRD: SRD-EXE-011.001 — .003, .013, .014, SRD-EXE-013.001 — .008

This is the only file under `strategy_engine/` permitted to import PyQt6
— it is the explicit boundary between the Qt-driven AppService world and
the asyncio-driven business logic in `_router.py` + friends.
"""
from __future__ import annotations

import asyncio
import logging
import time as _time
from collections.abc import Callable
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from us_swing.core.indicator_plugins import GUARD as PLUGIN_GUARD
from us_swing.core.indicator_plugins import REGISTRY as INDICATOR_REGISTRY
from us_swing.core.indicator_plugins import builtin_names
from us_swing.core.indicator_plugins._guard import FAILURES_TO_STOP
from us_swing.execution import ExecutionEnums
from us_swing.execution.strategy_engine._context import _StrategyContext
from us_swing.execution.strategy_engine._evaluator import ConditionEvaluator, function_names
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
from us_swing.execution.strategy_engine._rex_counter import RexCounterRepository
from us_swing.execution.strategy_engine._router import _Router
from us_swing.execution.strategy_engine._signals import PendingSignalSink, TradeSignal

if TYPE_CHECKING:
    import pandas as pd

    from us_swing.data.models import OHLCVBar
    from us_swing.execution.trade_cycle._protocols import TradeCycleQuery
    from us_swing.gui.strategy_builder_dialog import StrategyConfig

log = logging.getLogger(__name__)

_WRITEBACK_DEBOUNCE_S = 0.25
_TICK_INTERVAL_S = 1.0
_SQUARING_OFF_POLL_S = 2.0
_ET = ZoneInfo("America/New_York")

_StrategyRunState = ExecutionEnums.StrategyRunState


def _parse_run_state(raw: str) -> _StrategyRunState:
    """Convert a persisted ``run_state`` string into the enum.

    ``run_state`` is now a first-class field on ``StrategyConfig`` (DB-backed),
    trusted verbatim per SRD-EXE-013.008. An unrecognised value falls back to
    STOPPED.
    """
    try:
        return _StrategyRunState(raw)
    except ValueError:
        return _StrategyRunState.STOPPED


def bar_is_from_today(bar: OHLCVBar, now: datetime) -> bool:
    """True when *bar* is from today's New York date (ISS-EXE-0016).

    Rules must not run on an older day's bar, e.g. right after startup before
    today's prices are loaded. A naive bar time is read as UTC.
    """
    stamp = bar.datetime
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(_ET).date() == now.astimezone(_ET).date()


def plugins_used(cfg: StrategyConfig) -> set[str]:
    """Names in the strategy's conditions that are not built-in indicators."""
    names = function_names(cfg.entry_condition or "") | function_names(cfg.exit_condition or "")
    return names - builtin_names()


def missing_plugins(cfg: StrategyConfig) -> list[str]:
    """Custom indicators the strategy needs that are not loaded (SRD-EXE-022.014)."""
    return sorted(plugins_used(cfg) - INDICATOR_REGISTRY.names())


class StrategyEngine(QThread):
    """QThread-hosted asyncio engine that drives strategy evaluation.

    Owns the per-thread asyncio event loop, the `_Router`, and the
    `_StrategyContext` registry. AppService connects its `candle_closed`,
    `order_fill`, `order_reject`, `circuit_breaker_changed`, and
    `pending_signal_dismissed` signals to the corresponding `on_*` slots.
    """

    started_ok = pyqtSignal()
    stopped = pyqtSignal()
    run_state_changed = pyqtSignal(str, str)  # strategy_id, new_state
    start_refused = pyqtSignal(str, str)      # strategy_id, message (SRD-EXE-022.014)
    plugin_stopped = pyqtSignal(str, list)    # indicator name, stopped strategies (.013)

    def __init__(
        self,
        *,
        registry_loader: Callable[[], list[StrategyConfig]],
        registry_saver: Callable[[str, str], None],
        candles_provider: Callable[[str], dict[str, pd.DataFrame]],
        bar_provider: Callable[[str, str], OHLCVBar | None],
        risk: RiskValidator,
        submitter: ExecutionSubmitter,
        pending: PendingSignalSink,
        bus: EventBus,
        rex_counters: RexCounterRepository | None = None,
        symbols_provider: Callable[[], list[str]] | None = None,
        cycle_query: TradeCycleQuery | None = None,
        user_id_provider: Callable[[], int] | None = None,
        effective_capital_provider: Callable[[], float] | None = None,
        allocation_provider: Callable[[str, int], float] | None = None,
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
        self._rex_counters = rex_counters
        self._symbols_provider = symbols_provider or (lambda: [])
        self._cycle_query = cycle_query
        self._user_id_provider = user_id_provider or (lambda: 0)
        self._effective_capital_provider = effective_capital_provider
        self._allocation_provider = allocation_provider
        self._primary_tf = primary_timeframe

        self._loop: asyncio.AbstractEventLoop | None = None
        self._registry: dict[str, _StrategyContext] = {}
        self._router: _Router | None = None
        self._evaluator = ConditionEvaluator()
        self._cb_active = False
        self._last_persist_at: dict[str, float] = {}
        self._pending_persist = False
        self._stale_logged: set[tuple[str, date]] = set()

    # ── QThread entry point ──────────────────────────────────────────────────

    def run(self) -> None:  # noqa: D401 — Qt override
        PLUGIN_GUARD.add_limit_listener(self._on_plugin_limit)
        try:
            asyncio.run(self._async_run())
        except Exception:
            log.exception("[Strategy] engine loop crashed")
        finally:
            PLUGIN_GUARD.remove_limit_listener(self._on_plugin_limit)
            self._loop = None
            self.stopped.emit()

    async def _async_run(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._registry = self._load_registry()
        for ctx in self._registry.values():
            self._refuse_if_missing(ctx)

        queue: asyncio.Queue[TradeSignal] = asyncio.Queue(maxsize=512)
        self._router = _Router(
            queue=queue,
            registry=self._registry,
            evaluator=self._evaluator,
            risk=self._risk,
            submitter=self._submitter,
            pending=self._pending,
            bus=self._bus,
            rex_counters=self._rex_counters,
            user_id_provider=self._user_id_provider,
            cycle_query=self._cycle_query,
            effective_capital_provider=self._effective_capital_provider,
            allocation_provider=self._allocation_provider,
        )
        self.started_ok.emit()
        log.info("[Strategy] engine ready — %d active strateg(ies)", len(self._registry))

        await asyncio.gather(
            self._router.run_router_loop(),
            self._router.run_end_time_watcher(),
            self._strategy_tick_loop(),
            self._squaring_off_loop(),
        )

    # ── Periodic evaluation tick (cadence-driven, not bar-driven) ────────────

    async def _strategy_tick_loop(self) -> None:
        """Wake every second and evaluate any strategy whose cadence is due.

        Independent of the candle-close fan-out so exit conditions still fire
        when no new bars are arriving (e.g. IBKR disconnected, market closed,
        or user changed the exit expression mid-run).
        """
        assert self._router is not None
        router = self._router
        while not router.stop_requested():
            try:
                await asyncio.sleep(_TICK_INTERVAL_S)
            except asyncio.CancelledError:
                return
            if self._cb_active:
                continue
            now = datetime.now(_ET)
            for ctx in list(self._registry.values()):
                if ctx.run_state is not _StrategyRunState.RUNNING:
                    continue
                if not ctx.within_schedule(now):
                    continue
                if not self._is_time_to_evaluate(ctx, now):
                    continue
                ctx.last_eval_at = now
                try:
                    await self._evaluate_ctx(ctx, now)
                except Exception:
                    log.exception("[Strategy] tick eval crashed for %s", ctx.name)

    def _bar_ready(self, symbol: str, bar: OHLCVBar, now: datetime) -> bool:
        """True when *bar* is from today; log the wait once per stock per day."""
        if bar_is_from_today(bar, now):
            return True
        key = (symbol, now.date())
        if key not in self._stale_logged:
            self._stale_logged.add(key)
            log.info("[Strategy] Waiting for today's prices for %s before checking rules", symbol)
        return False

    async def _evaluate_ctx(self, ctx: _StrategyContext, now: datetime) -> None:
        """Fan out one evaluation pass for *ctx* across the candidate universe.

        Candidates are the union of the screened universe and the symbols that
        currently have an open cycle for this strategy — the latter ensures
        exit evaluation continues even when the symbol has dropped out of the
        screener.
        """
        assert self._router is not None
        try:
            universe = list(self._symbols_provider())
        except Exception:
            log.exception("[Strategy] symbols_provider failed")
            universe = []
        open_syms: list[str] = []
        if self._cycle_query is not None:
            try:
                open_syms = [
                    s.symbol for s in self._cycle_query.open_cycles_for_strategy(ctx.name)
                ]
            except Exception:
                log.exception("[Strategy] cycle_query.open_cycles_for_strategy failed")
        candidates = set(universe) | set(open_syms)
        in_scope = [s for s in candidates if ctx.accepts(s)]
        if not in_scope:
            return
        loop = asyncio.get_running_loop()
        for symbol in in_scope:
            bar = await loop.run_in_executor(None, self._bar_provider, symbol, self._primary_tf)
            if bar is None or not self._bar_ready(symbol, bar, now):
                continue
            candles = await loop.run_in_executor(None, self._candles_provider, symbol)
            if not candles:
                continue
            await self._router.evaluate(ctx, symbol, candles, bar)

    @staticmethod
    def _is_time_to_evaluate(ctx: _StrategyContext, now: datetime) -> bool:
        """Port of legacy is_time_to_evaluate logic (minute_close + execution_rate_sec).

        - First call (last_eval_at None) always fires.
        - minute_close > 0: only fires on minute-boundary cycles, after the
          delay-from-boundary, once per cycle.
        - minute_close == 0: pure rate-based — fires when execution_rate_sec
          have elapsed since the last fire.
        """
        minute_close = max(0, int(getattr(ctx.cfg, "minute_close", 1)))
        rate_sec = max(0, int(getattr(ctx.cfg, "execution_rate_sec", 1)))
        last = ctx.last_eval_at
        if last is None:
            return True
        if last.tzinfo is None:
            last = last.replace(tzinfo=_ET)

        if minute_close > 0:
            total_min = now.hour * 60 + now.minute
            if total_min % minute_close != 0:
                return False
            window_s = minute_close * 60
            delay = rate_sec if rate_sec < window_s else 0
            if now.second < delay:
                return False
            cur_cycle = total_min // minute_close
            last_total_min = last.hour * 60 + last.minute
            last_cycle = last_total_min // minute_close
            if cur_cycle == last_cycle and now.date() == last.date():
                return False
            return True

        if rate_sec <= 0:
            return True
        return (now - last).total_seconds() >= rate_sec

    # ── SQUARING_OFF auto-transition loop ────────────────────────────────────

    async def _squaring_off_loop(self) -> None:
        """Poll for strategies in SQUARING_OFF whose last cycle has closed.

        When a SQUARING_OFF strategy has no remaining open cycles in the
        ledger, transition it to STOPPED and persist.  Per SRD-EXE-013.003.
        """
        assert self._router is not None
        router = self._router
        while not router.stop_requested():
            try:
                await asyncio.sleep(_SQUARING_OFF_POLL_S)
            except asyncio.CancelledError:
                return
            for ctx in list(self._registry.values()):
                if ctx.run_state is not _StrategyRunState.SQUARING_OFF:
                    continue
                if self._cycle_query is None:
                    continue
                try:
                    open_cycles = self._cycle_query.open_cycles_for_strategy(ctx.name)
                except Exception:
                    log.exception(
                        "[Strategy] open_cycles_for_strategy failed for %s", ctx.name
                    )
                    continue
                if open_cycles:
                    continue
                ctx.run_state = _StrategyRunState.STOPPED
                self._schedule_persist(ctx.name)
                self.run_state_changed.emit(ctx.name, ctx.run_state.value)
                log.info("[Strategy] %s auto-stopped — all cycles closed", ctx.name)

    # ── Registry load ────────────────────────────────────────────────────────

    def _load_registry(self) -> dict[str, _StrategyContext]:
        """Build the in-memory registry from disk, reading ``run_state``.

        Per SRD-EXE-013.008 the persisted ``run_state`` is trusted verbatim,
        resolving the prior FO-EXE-011 §1 contradiction — a strategy that was
        RUNNING at the previous shutdown comes back up RUNNING.
        """
        out: dict[str, _StrategyContext] = {}
        for cfg in self._registry_loader():
            if cfg.mode == "disabled":
                continue
            run_state = _parse_run_state(cfg.run_state)
            out[cfg.name] = _StrategyContext(cfg=cfg, run_state=run_state)
        return out

    # ── Qt slots (called from AppService thread) ─────────────────────────────

    @pyqtSlot(str)
    def on_candle_closed(self, symbol: str) -> None:
        if self._loop is None or self._router is None or self._cb_active:
            return
        asyncio.run_coroutine_threadsafe(self._fanout(symbol), self._loop)

    @property
    def loop(self) -> asyncio.AbstractEventLoop | None:
        """The engine's running asyncio loop, or None before ``start()``.

        Exposed so the broker layer can schedule simulated fills onto the
        engine loop via ``call_soon_threadsafe`` from any thread, preserving
        the accept-then-fill ordering.
        """
        return self._loop

    @pyqtSlot(object)
    def on_order_fill(self, fill: FillEvent) -> None:
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self._apply_fill, fill)

    def _apply_fill(self, fill: FillEvent) -> None:
        if self._router is None:
            return
        self._router.on_order_fill(fill)
        self._schedule_persist(fill.strategy_id)

    @pyqtSlot(object)
    def on_order_reject(self, reject: RejectEvent) -> None:
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self._apply_reject, reject)

    def _apply_reject(self, reject: RejectEvent) -> None:
        if self._router is None:
            return
        self._router.on_order_reject(reject)
        self._schedule_persist(reject.strategy_id)

    @pyqtSlot(bool)
    def on_circuit_breaker(self, active: bool) -> None:
        self._cb_active = active

    @pyqtSlot(str, str)
    def on_pending_dismissed(self, strategy_id: str, symbol: str) -> None:
        """User dismissed a pending signal — clear the in-flight flag."""
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self._rollback_dismissed, strategy_id, symbol)

    def _rollback_dismissed(self, strategy_id: str, symbol: str) -> None:
        ctx = self._registry.get(strategy_id)
        if ctx is None:
            return
        ctx.in_flight.discard(symbol)
        self._schedule_persist(strategy_id)

    # ── Strategy lifecycle (called from GUI Play/Stop) ───────────────────────

    def set_run_state(self, strategy_id: str, new_state: _StrategyRunState) -> None:
        """Transition a strategy's ``run_state``.

        Per FO-EXE-013:
        - RUNNING → STOPPED: immediate, allowed only when no open cycles.
        - RUNNING → SQUARING_OFF: enqueues forced EXIT per open cycle; the
          background loop auto-transitions to STOPPED once cycles drain.
        - STOPPED → RUNNING: arms evaluation.
        """
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self._apply_run_state, strategy_id, new_state)

    def _apply_run_state(self, strategy_id: str, new_state: _StrategyRunState) -> None:
        ctx = self._registry.get(strategy_id)
        if ctx is None or self._router is None:
            return
        previous = ctx.run_state
        ctx.run_state = new_state
        if self._refuse_if_missing(ctx):
            return
        self._schedule_persist(strategy_id)
        self.run_state_changed.emit(strategy_id, new_state.value)
        log.info("[Strategy] %s run_state %s → %s", ctx.name, previous.value, new_state.value)
        if (previous is _StrategyRunState.STOPPED
                and new_state is _StrategyRunState.RUNNING
                and self._rex_counters is not None):
            deleted = self._rex_counters.reset(strategy_id)
            log.info("[Strategy] %s started — reset %d rex counter(s)", ctx.name, deleted)
        if new_state is _StrategyRunState.SQUARING_OFF:
            asyncio.create_task(self._router.squaring_off_exit(ctx))

    # ── Custom indicators (SRD-EXE-022.013–.014) ─────────────────────────────

    def _refuse_if_missing(self, ctx: _StrategyContext) -> bool:
        """Keep a strategy STOPPED when it needs a custom indicator that is not loaded."""
        if ctx.run_state is not _StrategyRunState.RUNNING:
            return False
        missing = missing_plugins(ctx.cfg)
        if not missing:
            return False
        ctx.run_state = _StrategyRunState.STOPPED
        ctx.cfg.run_state = _StrategyRunState.STOPPED.value
        try:
            self._registry_saver(ctx.name, _StrategyRunState.STOPPED.value)
        except Exception:
            log.exception("[Strategy] could not save %s as stopped", ctx.name)
        noun = "indicator" if len(missing) == 1 else "indicators"
        verb = "is" if len(missing) == 1 else "are"
        message = f"{ctx.name} cannot start: {noun} {', '.join(missing)} {verb} not installed"
        log.warning("[Strategy] %s", message)
        self.run_state_changed.emit(ctx.name, _StrategyRunState.STOPPED.value)
        self.start_refused.emit(ctx.name, message)
        return True

    def _on_plugin_limit(self, plugin_name: str) -> None:
        """Guard callback, from any thread: stop the strategies that use the indicator."""
        loop = self._loop
        if loop is not None:
            loop.call_soon_threadsafe(self.stop_plugin_users, plugin_name)

    def stop_plugin_users(self, plugin_name: str) -> list[str]:
        """Stop every running strategy that uses ``plugin_name``; open trades stay managed."""
        stopped: list[str] = []
        for ctx in self._registry.values():
            if (ctx.run_state is _StrategyRunState.RUNNING
                    and plugin_name in plugins_used(ctx.cfg)):
                ctx.run_state = _StrategyRunState.STOPPED
                self._schedule_persist(ctx.name)
                self.run_state_changed.emit(ctx.name, _StrategyRunState.STOPPED.value)
                log.error("[Strategy] %s stopped: indicator %s failed %d times in a row",
                          ctx.name, plugin_name, FAILURES_TO_STOP)
                stopped.append(ctx.name)
        if stopped:
            self.plugin_stopped.emit(plugin_name, stopped)
        return stopped

    # ── Fan-out ──────────────────────────────────────────────────────────────

    async def _fanout(self, symbol: str) -> None:
        if self._router is None or self._cb_active:
            return
        loop = asyncio.get_running_loop()
        bar = await loop.run_in_executor(None, self._bar_provider, symbol, self._primary_tf)
        if bar is None:
            log.debug("[Strategy] fan-out: no bar available for %s/%s",
                      symbol, self._primary_tf)
            return
        if not self._bar_ready(symbol, bar, datetime.now(_ET)):
            return
        candles = await loop.run_in_executor(None, self._candles_provider, symbol)
        if not candles:
            return
        accepting = [ctx for ctx in self._registry.values() if ctx.accepts(symbol)]
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
            for sid, ctx in self._registry.items():
                ctx.cfg.run_state = ctx.run_state.value
                self._registry_saver(sid, ctx.run_state.value)
            now = _time.monotonic()
            for sid in self._registry:
                self._last_persist_at[sid] = now
        except Exception:
            log.exception("[Strategy] registry writeback failed")
        finally:
            self._pending_persist = False

    # ── Sync lifecycle wrappers (called from AppService thread) ──────────────

    def has_direction_conflict(
        self, symbol: str, direction: str, timeout: float = 2.0
    ) -> bool:
        """True when an entry in *direction* on *symbol* would net against an
        opposite trade already held or in flight (SRD-EXE-018.012).

        The check reads ``in_flight`` sets owned by the engine loop, so it runs
        on that loop.  If the loop does not answer in time the entry is treated
        as conflicting — not sending an order is the safe outcome.
        """
        router = self._router
        if router is None:
            return False
        if self._loop is None:
            return router.has_direction_conflict(symbol, direction)

        async def _check() -> bool:
            return router.has_direction_conflict(symbol, direction)

        fut = asyncio.run_coroutine_threadsafe(_check(), self._loop)
        try:
            return fut.result(timeout=timeout)
        except TimeoutError:
            fut.cancel()
            log.warning("[Strategy] Could not check open trades for %s in time — entry not sent",
                        symbol)
            return True

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

        # Add new contexts; refresh cfg pointer on existing ones.  Run-state
        # is preserved from disk (load_strategies / user toggle) — never
        # forced here.
        for name, cfg in new_cfgs.items():
            if name in self._registry:
                self._registry[name].cfg = cfg
                self._registry[name].run_state = _parse_run_state(cfg.run_state)
            else:
                run_state = _parse_run_state(cfg.run_state)
                self._registry[name] = _StrategyContext(cfg=cfg, run_state=run_state)
        for ctx in self._registry.values():
            self._refuse_if_missing(ctx)

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
