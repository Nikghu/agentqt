"""
Module: MD-EXE-009.002.M02 — core/monitoring_session/_service.py
Parent SRD: SRD-EXE-009.004 — SRD-EXE-009.010, SRD-EXE-010.001 — SRD-EXE-010.006

Lifecycle state machine + reconciler.  Implements both ``MonitoringQuery``
(read-only) and ``MonitoringCommand`` (mutating) — consumers type-annotate
against the protocol they need.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import date, datetime, timezone
from typing import Any, Callable
from uuid import uuid4
from zoneinfo import ZoneInfo

import sqlalchemy as sa

from us_swing.core.monitoring_session._dto import (
    FillEvent,
    InvariantReport,
    KeepSet,
    MonitoringSessionRow,
    ReconcileError,
    ReconcileReport,
)
from us_swing.core.monitoring_session._enums import Side, TradeOrigin
from us_swing.core.monitoring_session._events import (
    ReconcileCompleted,
    SymbolEnteredPosition,
    SymbolEvicted,
    SymbolExitedPosition,
    SymbolPositionScaled,
    SymbolStartedMonitoring,
)
from us_swing.core.monitoring_session._protocols import MonitoringEventBus
from us_swing.core.monitoring_session._repository import MonitoringRepository
from us_swing.execution import ExecutionEnums

log = logging.getLogger(__name__)

_NY = ZoneInfo("America/New_York")
_RETRY_BACKOFF_S = 0.20


def _is_complete_fill(
    order_state: ExecutionEnums.BuyOrderState | ExecutionEnums.SellOrderState | None,
) -> bool:
    """Whether a fill fully completes its order, advancing lifecycle state.

    ``None`` (legacy callers without an order-state) counts as complete, so
    existing system and manual fills keep their pre-SRD-EXE-014.008 behaviour.
    """
    return order_state is None or order_state in (
        ExecutionEnums.BuyOrderState.FILLED,
        ExecutionEnums.SellOrderState.FILLED,
    )


def _today_et() -> date:
    return datetime.now(_NY).date()


# Sentinel returned when single-flight rejects a concurrent call.
_SKIPPED_REPORT = ReconcileReport(
    filtered_n      = 0,
    carryover_n     = 0,
    skipped_n       = 0,
    evicted_n       = 0,
    evicted_symbols = (),
    duration_ms     = 0,
    errors          = (ReconcileError("__skipped__", "already_running", 1),),
    schema_version  = 1,
)


class MonitoringSessionService:
    """Concrete implementer of both ``MonitoringQuery`` and ``MonitoringCommand``.

    Designed so consumers can hold a narrow Protocol reference and have it
    swapped for a test double or BKT replay implementation without
    consumer-side changes.
    """

    def __init__(
        self,
        repo: MonitoringRepository,
        bus: MonitoringEventBus,
        *,
        clock: Callable[[], datetime] | None             = None,
        today_provider: Callable[[], date] | None        = None,
        filtered_provider: Callable[[date], frozenset[str]] | None = None,
    ) -> None:
        self._repo  = repo
        self._bus   = bus
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._today = today_provider or _today_et
        # Caller supplies how to resolve today's filtered set; injected to keep
        # this module ignorant of `SystemConfig.active_screener_preset_id`.
        self._filtered_provider = filtered_provider or (lambda _d: frozenset())

        self._fill_lock      = threading.RLock()
        self._reconcile_lock = threading.Lock()
        self._reconcile_running_for: date | None = None

    # ── MonitoringQuery surface ──────────────────────────────────────────────

    def keep_set(self, today: date) -> KeepSet:
        return KeepSet(
            filtered       = self._filtered_provider(today),
            carryover      = self._repo.open_system_position_symbols(),
            as_of          = today,
            schema_version = 1,
        )

    def open_system_positions(self) -> frozenset[str]:
        return self._repo.open_system_position_symbols()

    def has_open_system_position(self, symbol: str) -> bool:
        return self._repo.has_open_system_position(symbol)

    def session_for(
        self,
        session_date: date,
        symbol: str,
    ) -> MonitoringSessionRow | None:
        return self._repo.fetch_session(session_date, symbol)

    def history(
        self,
        symbol: str,
        days: int = 30,
    ) -> tuple[MonitoringSessionRow, ...]:
        return self._repo.fetch_history(symbol, days)

    def check_invariant(self) -> InvariantReport:
        a = self._repo.entered_symbols()
        b = self._repo.open_system_position_symbols()
        ok = a == b
        report = InvariantReport(
            ok             = ok,
            only_in_a      = tuple(sorted(a - b)),
            only_in_b      = tuple(sorted(b - a)),
            schema_version = 1,
        )
        if not ok:
            log.error(
                "[Lifecycle] Invariant violation — ledger ENTERED %s open positions %s",
                sorted(a), sorted(b),
            )
        return report

    # ── MonitoringCommand surface ────────────────────────────────────────────

    def on_screener_results(self, result: Any) -> KeepSet:
        """Insert MONITORING rows for today's passing screener symbols.

        ``result`` is duck-typed against ``screener.storage.ScreenerRunResult``
        — accessed via ``preset_id``, ``run_timestamp``, ``results``.
        """
        today = self._today()
        symbols = sorted(
            s for s, meta in result.results.items()
            if isinstance(meta, dict) and meta.get("passed")
        )

        inserted = self._repo.insert_monitoring_rows(
            session_date  = today,
            preset_id     = result.preset_id,
            run_timestamp = result.run_timestamp,
            symbols       = symbols,
        )
        session_date_s = today.isoformat()
        for symbol in inserted:
            self._bus.publish(SymbolStartedMonitoring(
                event_id       = uuid4().hex,
                occurred_at    = self._clock().isoformat(),
                symbol         = symbol,
                session_date   = session_date_s,
                preset_id      = result.preset_id,
                run_timestamp  = result.run_timestamp,
                schema_version = 1,
            ))

        return KeepSet(
            filtered       = frozenset(symbols),
            carryover      = self._repo.open_system_position_symbols(),
            as_of          = today,
            schema_version = 1,
        )

    def on_fill(self, fill: FillEvent) -> None:
        """Route a fill through the lifecycle state machine."""
        # SRD-EXE-009.008 (a) — manual fills bypass the ledger entirely.
        if fill.origin is TradeOrigin.MANUAL:
            self._repo.insert_trade_with_anchor(
                trade_id            = fill.trade_id,
                user_id             = fill.user_id,
                symbol              = fill.symbol,
                side                = fill.side,
                qty                 = fill.qty,
                price               = fill.price,
                fill_time           = fill.fill_time,
                origin              = TradeOrigin.MANUAL,
                anchor_session_date = None,
            )
            self._repo.upsert_position_with_anchor(
                user_id             = fill.user_id,
                symbol              = fill.symbol,
                side                = fill.side,
                fill_qty            = fill.qty,
                fill_price          = fill.price,
                origin              = TradeOrigin.MANUAL,
                anchor_session_date = None,
            )
            return

        with self._fill_lock:
            has_open = self._repo.has_open_system_position(fill.symbol)

            if not has_open and fill.side is Side.BUY:
                # SRD-EXE-009.005 — first system BUY transition.
                anchor = self._repo.fetch_earliest_open_monitoring_row(fill.symbol)
                if anchor is None:
                    # SRD-EXE-009.007 edge — defensive record without raising.
                    log.error(
                        "[Lifecycle] System BUY for %s has no MONITORING row",
                        fill.symbol,
                    )
                    self._repo.insert_trade_with_anchor(
                        trade_id            = fill.trade_id,
                        user_id             = fill.user_id,
                        symbol              = fill.symbol,
                        side                = fill.side,
                        qty                 = fill.qty,
                        price               = fill.price,
                        fill_time           = fill.fill_time,
                        origin              = TradeOrigin.SYSTEM,
                        anchor_session_date = None,
                    )
                    self._repo.upsert_position_with_anchor(
                        user_id             = fill.user_id,
                        symbol              = fill.symbol,
                        side                = fill.side,
                        fill_qty            = fill.qty,
                        fill_price          = fill.price,
                        origin              = TradeOrigin.SYSTEM,
                        anchor_session_date = None,
                    )
                    return

                anchor_date = anchor.session_date
                # SRD-EXE-014.008 — only a fully FILLED entry order flips the
                # ledger MONITORING -> ENTERED; a partial fill records the
                # position but the symbol stays MONITORING until it completes.
                entry_complete = _is_complete_fill(fill.order_state)
                if entry_complete:
                    self._repo.transition_to_entered(
                        session_date = anchor_date,
                        symbol       = fill.symbol,
                        entered_at   = fill.fill_time,
                        trade_id     = fill.trade_id,
                    )
                self._repo.insert_trade_with_anchor(
                    trade_id            = fill.trade_id,
                    user_id             = fill.user_id,
                    symbol              = fill.symbol,
                    side                = fill.side,
                    qty                 = fill.qty,
                    price               = fill.price,
                    fill_time           = fill.fill_time,
                    origin              = TradeOrigin.SYSTEM,
                    anchor_session_date = anchor_date,
                )
                snap = self._repo.upsert_position_with_anchor(
                    user_id             = fill.user_id,
                    symbol              = fill.symbol,
                    side                = fill.side,
                    fill_qty            = fill.qty,
                    fill_price          = fill.price,
                    origin              = TradeOrigin.SYSTEM,
                    anchor_session_date = anchor_date,
                )
                if entry_complete:
                    self._bus.publish(SymbolEnteredPosition(
                        event_id            = uuid4().hex,
                        occurred_at         = self._clock().isoformat(),
                        symbol              = fill.symbol,
                        anchor_session_date = anchor_date,
                        trade_id            = fill.trade_id,
                        fill_qty            = fill.qty,
                        fill_time           = fill.fill_time,
                        schema_version      = 1,
                    ))
                else:
                    self._bus.publish(SymbolPositionScaled(
                        event_id            = uuid4().hex,
                        occurred_at         = self._clock().isoformat(),
                        symbol              = fill.symbol,
                        anchor_session_date = anchor_date,
                        trade_id            = fill.trade_id,
                        side                = fill.side,
                        fill_qty            = fill.qty,
                        new_position_state  = snap.state,
                        fill_time           = fill.fill_time,
                        schema_version      = 1,
                    ))
                return

            # has_open == True — scale-in, scale-out, or closing fill.
            open_anchor: str | None = self._repo.position_anchor(fill.symbol)
            self._repo.insert_trade_with_anchor(
                trade_id            = fill.trade_id,
                user_id             = fill.user_id,
                symbol              = fill.symbol,
                side                = fill.side,
                qty                 = fill.qty,
                price               = fill.price,
                fill_time           = fill.fill_time,
                origin              = TradeOrigin.SYSTEM,
                anchor_session_date = open_anchor,
            )
            snap = self._repo.upsert_position_with_anchor(
                user_id             = fill.user_id,
                symbol              = fill.symbol,
                side                = fill.side,
                fill_qty            = fill.qty,
                fill_price          = fill.price,
                origin              = TradeOrigin.SYSTEM,
                anchor_session_date = open_anchor,
            )

            # SRD-EXE-014.008 — a BUY that completes a previously partial entry
            # flips the still-MONITORING ledger row to ENTERED.
            if fill.side is Side.BUY and _is_complete_fill(fill.order_state):
                pending = self._repo.fetch_earliest_open_monitoring_row(fill.symbol)
                if pending is not None:
                    self._repo.transition_to_entered(
                        session_date = pending.session_date,
                        symbol       = fill.symbol,
                        entered_at   = fill.fill_time,
                        trade_id     = fill.trade_id,
                    )
                    self._bus.publish(SymbolEnteredPosition(
                        event_id            = uuid4().hex,
                        occurred_at         = self._clock().isoformat(),
                        symbol              = fill.symbol,
                        anchor_session_date = pending.session_date,
                        trade_id            = fill.trade_id,
                        fill_qty            = fill.qty,
                        fill_time           = fill.fill_time,
                        schema_version      = 1,
                    ))
                    return

            if snap.state == "CLOSED" and _is_complete_fill(fill.order_state):
                # SRD-EXE-009.007 — exit transition.
                if open_anchor is not None:
                    self._repo.transition_to_exited(
                        session_date = open_anchor,
                        symbol       = fill.symbol,
                        exited_at    = fill.fill_time,
                    )
                self._bus.publish(SymbolExitedPosition(
                    event_id            = uuid4().hex,
                    occurred_at         = self._clock().isoformat(),
                    symbol              = fill.symbol,
                    anchor_session_date = open_anchor or "",
                    exit_trade_id       = fill.trade_id,
                    exit_time           = fill.fill_time,
                    realised_pnl        = snap.realised_pnl,
                    schema_version      = 1,
                ))
            else:
                # SRD-EXE-009.006 — scale-in or scale-out.
                self._bus.publish(SymbolPositionScaled(
                    event_id            = uuid4().hex,
                    occurred_at         = self._clock().isoformat(),
                    symbol              = fill.symbol,
                    anchor_session_date = open_anchor or "",
                    trade_id            = fill.trade_id,
                    side                = fill.side,
                    fill_qty            = fill.qty,
                    new_position_state  = snap.state,
                    fill_time           = fill.fill_time,
                    schema_version      = 1,
                ))

    def reconcile_preopen(self, today: date) -> ReconcileReport:
        """Pre-open candle DB reconciliation.  Single-flight, idempotent."""
        if not self._reconcile_lock.acquire(blocking=False):
            log.warning(
                "[Lifecycle] Reconcile already running for %s — skipping duplicate call",
                self._reconcile_running_for,
            )
            return _SKIPPED_REPORT
        started_at = time.perf_counter()
        try:
            self._reconcile_running_for = today

            # Step 1 — EOD finalize.
            skipped_n = self._repo.bulk_skip_stale_monitoring(today)

            # Step 2 — compute eviction set.
            keep    = self.keep_set(today)
            entered = self._repo.entered_symbols()
            stale   = self._repo.stale_lifecycle_symbols(today)
            evict   = stale - keep.filtered - keep.carryover - entered

            # Defensive invariant check — flag mismatches but still evict the
            # symbols that ARE safe to evict.
            if entered != keep.carryover:
                inv = self.check_invariant()
                log.error(
                    "[Lifecycle] Invariant mismatch during reconcile: only_in_a=%s only_in_b=%s",
                    inv.only_in_a, inv.only_in_b,
                )

            evicted_ok: list[str] = []
            errors:     list[ReconcileError] = []
            now_iso = self._clock().isoformat()

            # SRD-EXE-010.003 — per-symbol invariant violation reporting.
            # Symbols where the ledger and positions views disagree get a
            # `ReconcileError("X","invariant_violation",1)` row in the report
            # (logging only is not sufficient — operators audit via the report).
            for symbol in sorted(entered ^ keep.carryover):
                errors.append(ReconcileError(symbol, "invariant_violation", 1))
                log.error(
                    "[Lifecycle] Invariant violation during reconcile: symbol=%s",
                    symbol,
                )

            for symbol in sorted(evict):
                # Per-symbol retry-once on transient OperationalError.
                last_exc: Exception | None = None
                for attempt in (1, 2):
                    try:
                        dates = self._repo.evict_symbol_atomic(
                            symbol     = symbol,
                            today      = today,
                            evicted_at = now_iso,
                        )
                        evicted_ok.append(symbol)
                        self._bus.publish(SymbolEvicted(
                            event_id              = uuid4().hex,
                            occurred_at           = now_iso,
                            symbol                = symbol,
                            evicted_session_dates = dates,
                            schema_version        = 1,
                        ))
                        last_exc = None
                        break
                    except sa.exc.OperationalError as exc:
                        last_exc = exc
                        if attempt == 1:
                            time.sleep(_RETRY_BACKOFF_S)
                            continue
                    except Exception as exc:
                        last_exc = exc
                        break
                if last_exc is not None:
                    errors.append(ReconcileError(symbol, repr(last_exc), 1))
                    log.warning(
                        "[Lifecycle] Eviction failed for %s: %r", symbol, last_exc,
                    )

            duration_ms = int((time.perf_counter() - started_at) * 1000)
            report = ReconcileReport(
                filtered_n      = len(keep.filtered),
                carryover_n     = len(keep.carryover),
                skipped_n       = skipped_n,
                evicted_n       = len(evicted_ok),
                evicted_symbols = tuple(sorted(evicted_ok)),
                duration_ms     = duration_ms,
                errors          = tuple(errors),
                schema_version  = 1,
            )
            log.info(
                "[Lifecycle] Reconcile complete — %d filtered, %d carryover, "
                "%d marked skipped, %d evicted in %d ms",
                report.filtered_n, report.carryover_n, report.skipped_n,
                report.evicted_n, report.duration_ms,
            )
            self._bus.publish(ReconcileCompleted(
                event_id       = uuid4().hex,
                occurred_at    = now_iso,
                report         = report,
                schema_version = 1,
            ))
            return report
        finally:
            self._reconcile_running_for = None
            self._reconcile_lock.release()
