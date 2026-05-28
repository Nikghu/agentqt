"""
Module: MD-EXE-012.002.M02 — execution/trade_cycle/_service.py
Parent SRD: SRD-EXE-012.002, .003, .004, .005, .006, .007, .008,
            .009, .011, .013

``TradeCycleService`` owns the live per-cycle state machine.  It is
GUI-free (no PyQt6 import) and exposes both ``TradeCycleQuery`` and
``TradeCycleCommand``.  Ticks are bridged into a dedicated asyncio loop
running on a background thread; CRUD methods execute on the calling
thread under a re-entrant lock that guards the accumulator dict.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

from us_swing.core.monitoring_session import MonitoringEventBus
from us_swing.execution.trade_cycle._dto import (
    CycleSnapshot,
    DuplicateOpenCycleError,
    InvalidStateTransitionError,
    InvariantViolation,
    TradeCycleState,
    coerce_state,
    validate_stoploss_type,
    validate_target_type,
    validate_trailing_mode,
)
from us_swing.execution.trade_cycle._events import (
    CycleAborted,
    CycleClosed,
    CycleClosing,
    CycleOpened,
    CycleUpdated,
    ExitTrigger,
    RiskUpdated,
)
from us_swing.execution.trade_cycle._repository import TradeCycleRepository

log = logging.getLogger(__name__)

_THROTTLE_MS = 500


@dataclass
class _TickAccumulator:
    cycle_id:        int
    symbol:          str
    latest_price:    float = 0.0
    highest_seen:    float = 0.0
    last_persist_at: float = 0.0
    dirty:           bool  = False
    flush_handle:    asyncio.TimerHandle | None = None
    closing:         bool  = field(default=False)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


class TradeCycleService:
    """Live trade-cycle ledger service.

    Construct via :func:`build_default_service` from the package
    ``__init__``.  The public surface is the ``TradeCycleQuery`` and
    ``TradeCycleCommand`` Protocols — one concrete instance fulfils both.
    """

    def __init__(
        self,
        *,
        repo: TradeCycleRepository,
        bus: MonitoringEventBus,
        set_active_symbols: Callable[[frozenset[str]], None] | None = None,
        clock: Callable[[], datetime] | None                        = None,
    ) -> None:
        self._repo                = repo
        self._bus                 = bus
        self._set_active_symbols  = set_active_symbols or (lambda _s: None)
        self._clock               = clock or (lambda: datetime.now(timezone.utc))

        self._accs:        dict[int, _TickAccumulator] = {}   # cycle_id -> acc
        self._accs_by_sym: dict[str, set[int]]         = {}   # symbol -> {cycle_id}
        self._accs_lock                                = threading.RLock()

        self._loop:    asyncio.AbstractEventLoop | None = None
        self._thread:  threading.Thread | None          = None
        self._started                                   = False
        self._reload_done                               = False

    # ── Service lifecycle ────────────────────────────────────────────────────

    def start(self) -> None:
        """Spin up the background asyncio loop.  Idempotent."""
        if self._started:
            return
        ready = threading.Event()

        def _run() -> None:
            loop = asyncio.new_event_loop()
            self._loop = loop
            asyncio.set_event_loop(loop)
            ready.set()
            try:
                loop.run_forever()
            finally:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.close()
                self._loop = None

        self._thread = threading.Thread(
            target=_run, name="trade-cycle-loop", daemon=True
        )
        self._thread.start()
        ready.wait(timeout=2.0)
        self._started = True

    def stop(self) -> None:
        """Flush dirty accumulators and tear down the background loop."""
        if not self._started:
            return
        loop = self._loop
        if loop is not None and loop.is_running():
            fut = asyncio.run_coroutine_threadsafe(self._drain_all(), loop)
            try:
                fut.result(timeout=2.0)
            except Exception:
                log.exception("[Cycle] drain on stop failed")
            loop.call_soon_threadsafe(loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._thread  = None
        self._started = False

    # ── Query surface (TradeCycleQuery) ──────────────────────────────────────

    def open_cycles(self) -> tuple[CycleSnapshot, ...]:
        return self._repo.open_cycles()

    def cycle(self, cycle_id: int) -> CycleSnapshot | None:
        return self._repo.cycle(cycle_id)

    def history(
        self,
        *,
        symbol: str | None      = None,
        strategy_id: str | None = None,
        days: int               = 30,
    ) -> tuple[CycleSnapshot, ...]:
        return self._repo.history(symbol=symbol, strategy_id=strategy_id, days=days)

    def has_open_cycle(self, strategy_id: str, symbol: str) -> bool:
        return self._repo.has_open_cycle(strategy_id, symbol)

    def open_cycles_for_strategy(self, strategy_id: str) -> tuple[CycleSnapshot, ...]:
        return self._repo.open_cycles_for_strategy(strategy_id)

    # ── Command surface (TradeCycleCommand) ──────────────────────────────────

    def on_entry_fill(
        self,
        *,
        strategy_id:     str,
        symbol:          str,
        user_id:         int,
        entry_order_id:  str,
        entry_price:     float,
        entry_qty:       int,
        fill_time:       str,
        hard_stop_loss:  float,
        target_price:    float | None,
        target_type:     str,
        stoploss_type:   str,
        trailing_mode:   str | None,
        trailing_offset: float | None,
        monitoring_session_date: str,
    ) -> CycleSnapshot:
        """Open a new cycle on the broker fill of an entry order.

        Idempotent on ``entry_order_id`` — a duplicate call returns the
        existing snapshot.
        """
        existing = self._repo.find_by_entry_order(entry_order_id)
        if existing is not None:
            return existing

        validate_target_type(target_type)
        validate_stoploss_type(stoploss_type)
        validate_trailing_mode(trailing_mode)

        row = {
            "strategy_id":             strategy_id,
            "symbol":                  symbol,
            "user_id":                 user_id,
            "monitoring_session_date": monitoring_session_date,
            "entry_time":              fill_time,
            "entry_price":             entry_price,
            "entry_qty":               entry_qty,
            "entry_order_id":          entry_order_id,
            "hard_stop_loss":          hard_stop_loss,
            "target_price":            target_price,
            "target_type":             target_type,
            "stoploss_type":           stoploss_type,
            "trailing_mode":           trailing_mode,
            "trailing_offset":         trailing_offset,
            "current_price":           entry_price,
            "highest_price_seen":      entry_price,
            "effective_stop":          hard_stop_loss,
            "state":                   TradeCycleState.OPEN.value,
        }
        try:
            snap = self._repo.insert_open(row=row)
        except DuplicateOpenCycleError:
            log.warning(
                "[Cycle] Duplicate open cycle for %s %s rejected at repository",
                strategy_id, symbol,
            )
            raise

        with self._accs_lock:
            self._attach_accumulator(snap)
            self._refresh_active_symbols_locked()

        self._bus.publish(CycleOpened(
            cycle_id    = snap.cycle_id,
            symbol      = snap.symbol,
            strategy_id = snap.strategy_id,
            snapshot    = snap,
        ))
        return snap

    def on_exit_fill(
        self,
        *,
        exit_order_id: str,
        exit_price:    float,
        exit_qty:      int,
        exit_time:     str,
        exit_reason:   str,
    ) -> CycleSnapshot:
        """Close a cycle on the broker fill of an exit order.

        Idempotent on ``exit_order_id`` — a duplicate call returns the
        existing snapshot.  The cycle must currently be in OPEN or
        CLOSING (CLOSING is the normal path; OPEN supports a manual /
        emergency exit that bypassed the trigger).
        """
        existing = self._repo.find_by_exit_order(exit_order_id)
        if existing is not None:
            return existing

        target = next(
            (c for c in self._repo.open_cycles() if c.exit_order_id is None),
            None,
        )
        # The router/ExecutionEngine knows which cycle the SELL belongs to and
        # is expected to call on_exit_fill via cycle_id; we keep this lookup
        # as a guard for tests that do not pre-stamp the order id.
        if target is None:
            raise InvalidStateTransitionError(
                f"no open cycle accepts exit_order_id={exit_order_id!r}"
            )
        return self._close_cycle(
            cycle_id      = target.cycle_id,
            exit_order_id = exit_order_id,
            exit_price    = exit_price,
            exit_qty      = exit_qty,
            exit_time     = exit_time,
            exit_reason   = exit_reason,
        )

    def close_cycle_by_id(
        self,
        cycle_id: int,
        *,
        exit_order_id: str,
        exit_price:    float,
        exit_qty:      int,
        exit_time:     str,
        exit_reason:   str,
    ) -> CycleSnapshot:
        """Close a specific cycle by id (preferred path for ExecutionEngine)."""
        existing = self._repo.find_by_exit_order(exit_order_id)
        if existing is not None:
            return existing
        return self._close_cycle(
            cycle_id      = cycle_id,
            exit_order_id = exit_order_id,
            exit_price    = exit_price,
            exit_qty      = exit_qty,
            exit_time     = exit_time,
            exit_reason   = exit_reason,
        )

    def _close_cycle(
        self,
        *,
        cycle_id:      int,
        exit_order_id: str,
        exit_price:    float,
        exit_qty:      int,
        exit_time:     str,
        exit_reason:   str,
    ) -> CycleSnapshot:
        snap = self._repo.cycle(cycle_id)
        if snap is None:
            raise InvalidStateTransitionError(f"cycle {cycle_id} not found")
        if snap.state not in (TradeCycleState.OPEN, TradeCycleState.CLOSING):
            raise InvalidStateTransitionError(
                f"cannot close cycle {cycle_id} from state {snap.state.value!r}"
            )

        if snap.state is TradeCycleState.OPEN:
            self._repo.update_state(cycle_id, TradeCycleState.CLOSING)
            self._bus.publish(CycleClosing(
                cycle_id = cycle_id,
                symbol   = snap.symbol,
                reason   = exit_reason,
            ))

        realized_pnl_usd = (exit_price - snap.entry_price) * exit_qty
        realized_pnl_pct = (
            (exit_price - snap.entry_price) / snap.entry_price * 100.0
            if snap.entry_price else 0.0
        )

        closed = self._repo.close(
            cycle_id,
            exit_fields={
                "exit_order_id":    exit_order_id,
                "exit_price":       exit_price,
                "exit_qty":         exit_qty,
                "exit_time":        exit_time,
                "exit_reason":      exit_reason,
                "realized_pnl_usd": realized_pnl_usd,
                "realized_pnl_pct": realized_pnl_pct,
            },
        )

        with self._accs_lock:
            self._detach_accumulator(cycle_id)
            self._refresh_active_symbols_locked()

        self._bus.publish(CycleClosed(
            cycle_id         = closed.cycle_id,
            symbol           = closed.symbol,
            exit_reason      = exit_reason,
            realized_pnl_usd = realized_pnl_usd,
            realized_pnl_pct = realized_pnl_pct,
            snapshot         = closed,
        ))
        return closed

    def on_entry_failed(self, cycle_id: int, reason: str) -> CycleSnapshot:
        """Abort an OPENING cycle when the entry order is rejected."""
        snap = self._repo.abort(cycle_id, reason)
        with self._accs_lock:
            self._detach_accumulator(cycle_id)
            self._refresh_active_symbols_locked()
        self._bus.publish(CycleAborted(
            cycle_id = snap.cycle_id,
            symbol   = snap.symbol,
            reason   = reason,
        ))
        return snap

    def update_risk(
        self,
        cycle_id: int,
        *,
        hard_sl:         float | None = None,
        target:          float | None = None,
        trailing_offset: float | None = None,
        trailing_mode:   str | None   = None,
    ) -> CycleSnapshot:
        """Per-cycle risk-snapshot mutation.

        Raises :class:`InvariantViolation` on any failed validation; no
        partial mutation is committed.
        """
        snap = self._repo.cycle(cycle_id)
        if snap is None:
            raise InvalidStateTransitionError(f"cycle {cycle_id} not found")
        if not snap.state.is_non_terminal():
            raise InvariantViolation(
                f"cannot edit risk on cycle {cycle_id} in state {snap.state.value!r}"
            )

        current_price = snap.current_price if snap.current_price is not None else snap.entry_price

        if hard_sl is not None and hard_sl > current_price:
            raise InvariantViolation(
                f"hard_sl ({hard_sl}) must be ≤ current_price ({current_price})"
            )
        if target is not None and target < current_price:
            raise InvariantViolation(
                f"target ({target}) must be ≥ current_price ({current_price})"
            )
        if trailing_offset is not None and trailing_offset <= 0:
            raise InvariantViolation(
                f"trailing_offset ({trailing_offset}) must be > 0"
            )
        validate_trailing_mode(trailing_mode)

        fields: dict[str, Any] = {}
        if hard_sl is not None:
            fields["hard_stop_loss"] = hard_sl
        if target is not None:
            fields["target_price"] = target
        if trailing_offset is not None:
            fields["trailing_offset"] = trailing_offset
        if trailing_mode is not None:
            fields["trailing_mode"] = trailing_mode

        updated = self._repo.update_risk(cycle_id, fields=fields)
        self._bus.publish(RiskUpdated(
            cycle_id = updated.cycle_id,
            symbol   = updated.symbol,
            snapshot = updated,
        ))
        return updated

    # ── Startup hook ─────────────────────────────────────────────────────────

    def reload(self) -> None:
        """Re-attach tick accumulators for every non-terminal row on startup.

        Idempotent — subsequent calls are no-ops once the initial pass has
        completed.  Must be invoked before ``LiveBarWorker.start()``.
        """
        if self._reload_done:
            return
        with self._accs_lock:
            for snap in self._repo.open_cycles():
                if snap.cycle_id in self._accs:
                    continue
                self._attach_accumulator(snap)
            self._refresh_active_symbols_locked()
        self._reload_done = True

    # ── Tick path (bridge entry) ─────────────────────────────────────────────

    def on_tick(self, symbol: str, price: float) -> None:
        """Thread-safe entry point — called from the LiveTickWorker thread.

        Bounces into the background loop; if the loop is not running, the
        tick is dropped silently (the service is either still initialising
        or has shut down).
        """
        loop = self._loop
        if loop is None or not loop.is_running():
            return
        asyncio.run_coroutine_threadsafe(self._handle_tick(symbol, price), loop)

    async def _handle_tick(self, symbol: str, price: float) -> None:
        with self._accs_lock:
            cycle_ids = tuple(self._accs_by_sym.get(symbol, ()))
        for cycle_id in cycle_ids:
            with self._accs_lock:
                acc = self._accs.get(cycle_id)
                if acc is None or acc.closing:
                    continue
                if price > acc.highest_seen:
                    acc.highest_seen = price
                acc.latest_price = price
                acc.dirty        = True
            loop    = asyncio.get_running_loop()
            now     = loop.time()
            elapsed = (now - acc.last_persist_at) * 1000.0
            if elapsed >= _THROTTLE_MS:
                await self._flush(acc)
            elif acc.flush_handle is None:
                delay = max(0.0, (_THROTTLE_MS - elapsed) / 1000.0)
                acc.flush_handle = loop.call_later(delay, self._schedule_flush, acc)

    def _schedule_flush(self, acc: _TickAccumulator) -> None:
        asyncio.ensure_future(self._flush(acc))

    async def _flush(self, acc: _TickAccumulator) -> None:
        if not acc.dirty:
            return
        snap = self._repo.cycle(acc.cycle_id)
        if snap is None or snap.state not in (TradeCycleState.OPEN, TradeCycleState.CLOSING):
            with self._accs_lock:
                self._detach_accumulator(acc.cycle_id)
            return

        price   = acc.latest_price
        highest = acc.highest_seen
        live    = self._compute_live(snap, price, highest)

        self._repo.update_live(acc.cycle_id, fields=live)
        loop                = asyncio.get_running_loop()
        acc.last_persist_at = loop.time()
        acc.dirty           = False
        acc.flush_handle    = None

        fresh = self._repo.cycle(acc.cycle_id)
        if fresh is None:
            return
        self._bus.publish(CycleUpdated(
            cycle_id = fresh.cycle_id,
            symbol   = fresh.symbol,
            snapshot = fresh,
        ))
        self._check_exit_triggers(fresh, price)

    async def _drain_all(self) -> None:
        with self._accs_lock:
            accs = list(self._accs.values())
        for acc in accs:
            try:
                await self._flush(acc)
            except Exception:
                log.exception("[Cycle] drain flush failed for cycle_id=%s", acc.cycle_id)

    # ── Live-field computation ───────────────────────────────────────────────

    def _compute_live(
        self,
        snap: CycleSnapshot,
        price: float,
        highest: float,
    ) -> dict[str, Any]:
        pnl_usd = (price - snap.entry_price) * snap.entry_qty
        pnl_pct = (
            (price - snap.entry_price) / snap.entry_price * 100.0
            if snap.entry_price else 0.0
        )

        if snap.trailing_mode == "$":
            trail: float | None = highest - (snap.trailing_offset or 0.0)
        elif snap.trailing_mode == "%":
            trail = highest * (1.0 - (snap.trailing_offset or 0.0) / 100.0)
        else:
            trail = None

        if trail is not None and snap.trailing_stop_level is not None:
            trail = max(trail, snap.trailing_stop_level)

        if trail is not None:
            effective = max(snap.hard_stop_loss, trail)
        else:
            effective = snap.hard_stop_loss

        return {
            "current_price":       price,
            "current_pnl_usd":     pnl_usd,
            "current_pnl_pct":     pnl_pct,
            "highest_price_seen":  highest,
            "trailing_stop_level": trail,
            "effective_stop":      effective,
            "last_updated_at":     _utcnow_iso(),
        }

    # ── Exit-trigger evaluation ──────────────────────────────────────────────

    def _check_exit_triggers(self, snap: CycleSnapshot, price: float) -> None:
        if snap.state is not TradeCycleState.OPEN:
            return
        reason: str | None = None

        if snap.target_price is not None and price >= snap.target_price:
            reason = "target"
        elif snap.effective_stop is not None and price <= snap.effective_stop:
            if (snap.trailing_stop_level is not None
                    and snap.trailing_stop_level >= snap.hard_stop_loss
                    and price <= snap.trailing_stop_level):
                reason = "trailing_sl"
            else:
                reason = "hard_sl"

        if reason is None:
            return

        try:
            self._repo.update_state(snap.cycle_id, TradeCycleState.CLOSING)
        except InvalidStateTransitionError:
            return

        with self._accs_lock:
            acc = self._accs.get(snap.cycle_id)
            if acc is not None:
                acc.closing = True

        self._bus.publish(ExitTrigger(
            cycle_id      = snap.cycle_id,
            symbol        = snap.symbol,
            reason        = reason,
            trigger_price = price,
        ))

    # ── Accumulator bookkeeping ──────────────────────────────────────────────

    def _attach_accumulator(self, snap: CycleSnapshot) -> None:
        acc = _TickAccumulator(
            cycle_id        = snap.cycle_id,
            symbol          = snap.symbol,
            latest_price    = snap.current_price or snap.entry_price,
            highest_seen    = snap.highest_price_seen or snap.entry_price,
            last_persist_at = 0.0,
            dirty           = False,
            closing         = (snap.state is TradeCycleState.CLOSING),
        )
        self._accs[snap.cycle_id] = acc
        self._accs_by_sym.setdefault(snap.symbol, set()).add(snap.cycle_id)

    def _detach_accumulator(self, cycle_id: int) -> None:
        acc = self._accs.pop(cycle_id, None)
        if acc is None:
            return
        if acc.flush_handle is not None:
            try:
                acc.flush_handle.cancel()
            except Exception:
                pass
        peers = self._accs_by_sym.get(acc.symbol)
        if peers is not None:
            peers.discard(cycle_id)
            if not peers:
                self._accs_by_sym.pop(acc.symbol, None)

    def _refresh_active_symbols_locked(self) -> None:
        symbols = frozenset(self._accs_by_sym.keys())
        try:
            self._set_active_symbols(symbols)
        except Exception:
            log.exception("[Cycle] set_active_symbols callback raised")


def _validate_state_set(states: Iterable[str]) -> None:
    for s in states:
        coerce_state(s)


__all__ = [
    "TradeCycleService",
]
