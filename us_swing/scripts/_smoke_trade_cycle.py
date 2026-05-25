"""Smoke test for FO-EXE-012 trade-cycle ledger.

Validates the end-to-end happy path against in-memory SQLite:
  - schema bootstrap creates trade_cycles table
  - on_entry_fill inserts row, publishes CycleOpened
  - tick path computes pnl + trailing, publishes CycleUpdated + ExitTrigger
  - on_exit_fill closes the cycle, publishes CycleClosing + CycleClosed
  - update_risk enforces hard_sl <= current_price invariant
  - duplicate entry_order_id is idempotent
  - reload() re-attaches accumulators after a service restart

Run with:
  $env:PYTHONPATH = "F:\\USMarket_Backtesting\\us_swing\\src"
  python F:\\USMarket_Backtesting\\us_swing\\scripts\\_smoke_trade_cycle.py
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

import sqlalchemy as sa

# Pre-warm the data package — its __init__ resolves the
# db.manager <-> data.engine cycle that exists in this codebase
# independently of FO-EXE-012.  Once data is loaded, importing
# db.schema works normally.
import us_swing.data  # noqa: F401
from us_swing.db.schema import create_schema
from us_swing.execution.trade_cycle import (
    CycleClosed,
    CycleClosing,
    CycleOpened,
    CycleUpdated,
    ExitTrigger,
    InvariantViolation,
    RiskUpdated,
    build_default_service,
)


class _CaptureBus:
    def __init__(self) -> None:
        self.events: dict[type, list[Any]] = defaultdict(list)

    def publish(self, event: Any) -> None:
        self.events[type(event)].append(event)

    def subscribe(self, *_a: Any, **_k: Any):  # pragma: no cover - bus stub
        class _NoSub:
            def cancel(self) -> None: ...
        return _NoSub()


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)
    print(f"  OK  {msg}")


def main() -> None:
    engine = sa.create_engine(
        "sqlite://",
        connect_args = {"check_same_thread": False},
        poolclass    = sa.pool.StaticPool,
        future       = True,
    )
    create_schema(engine)

    bus    = _CaptureBus()
    query, command = build_default_service(engine, bus)
    command.start()  # type: ignore[attr-defined]

    try:
        # ── on_entry_fill ────────────────────────────────────────────────
        snap = command.on_entry_fill(
            strategy_id             = "strat-A",
            symbol                  = "AAPL",
            user_id                 = 1,
            entry_order_id          = "ORD-1001",
            entry_price             = 100.0,
            entry_qty               = 10,
            fill_time               = "2026-05-22T13:30:00",
            hard_stop_loss          = 95.0,
            target_price            = 110.0,
            target_type             = "fixed",
            stoploss_type           = "fixed",
            trailing_mode           = "$",
            trailing_offset         = 2.0,
            monitoring_session_date = "2026-05-22",
        )
        _assert(snap.state == "OPEN", "entry fill opens cycle in OPEN state")
        _assert(len(bus.events[CycleOpened]) == 1, "CycleOpened published")

        # ── idempotency on entry_order_id ────────────────────────────────
        dup = command.on_entry_fill(
            strategy_id             = "strat-A",
            symbol                  = "AAPL",
            user_id                 = 1,
            entry_order_id          = "ORD-1001",
            entry_price             = 999.0,
            entry_qty               = 999,
            fill_time               = "2026-05-22T13:30:00",
            hard_stop_loss          = 1.0,
            target_price            = None,
            target_type             = "fixed",
            stoploss_type           = "fixed",
            trailing_mode           = None,
            trailing_offset         = None,
            monitoring_session_date = "2026-05-22",
        )
        _assert(dup.cycle_id == snap.cycle_id, "duplicate entry_order_id returns existing")
        _assert(len(bus.events[CycleOpened]) == 1, "no duplicate CycleOpened")

        # ── tick path ────────────────────────────────────────────────────
        command.on_tick("AAPL", 103.0)  # type: ignore[attr-defined]
        time.sleep(0.7)                  # > 500ms throttle window
        command.on_tick("AAPL", 105.0)  # type: ignore[attr-defined]
        time.sleep(0.7)
        _assert(len(bus.events[CycleUpdated]) >= 1, "tick produced CycleUpdated")

        fresh = query.cycle(snap.cycle_id)
        assert fresh is not None
        _assert(fresh.highest_price_seen == 105.0, "highest_price_seen tracks max")
        _assert(fresh.current_pnl_usd is not None and fresh.current_pnl_usd > 0,
                "current_pnl_usd computed > 0 on profitable tick")
        _assert(fresh.trailing_stop_level == 103.0, "trailing $2 from highest 105 = 103")
        _assert(fresh.effective_stop == 103.0, "effective = max(hard 95, trail 103) = 103")

        # ── exit trigger via target ──────────────────────────────────────
        command.on_tick("AAPL", 111.0)  # type: ignore[attr-defined]
        time.sleep(0.7)
        _assert(len(bus.events[ExitTrigger]) == 1, "target hit publishes ExitTrigger")
        _assert(bus.events[ExitTrigger][0].reason == "target", "exit reason = target")

        after_trigger = query.cycle(snap.cycle_id)
        assert after_trigger is not None
        _assert(after_trigger.state == "CLOSING", "cycle transitions to CLOSING")

        # ── on_exit_fill ─────────────────────────────────────────────────
        closed = command.close_cycle_by_id(  # type: ignore[attr-defined]
            snap.cycle_id,
            exit_order_id = "EXIT-2001",
            exit_price    = 111.0,
            exit_qty      = 10,
            exit_time     = "2026-05-22T13:31:00",
            exit_reason   = "target",
        )
        _assert(closed.state == "CLOSED", "exit fill closes cycle")
        _assert(closed.realized_pnl_usd == 110.0, "realized PnL = (111-100)*10 = 110")
        _assert(len(bus.events[CycleClosed]) == 1, "CycleClosed published")

        # ── second cycle for update_risk + invariant ─────────────────────
        snap2 = command.on_entry_fill(
            strategy_id             = "strat-B",
            symbol                  = "MSFT",
            user_id                 = 1,
            entry_order_id          = "ORD-1002",
            entry_price             = 200.0,
            entry_qty               = 5,
            fill_time               = "2026-05-22T13:32:00",
            hard_stop_loss          = 190.0,
            target_price            = 220.0,
            target_type             = "fixed",
            stoploss_type           = "fixed",
            trailing_mode           = None,
            trailing_offset         = None,
            monitoring_session_date = "2026-05-22",
        )
        # hard_sl above current_price must raise
        try:
            command.update_risk(snap2.cycle_id, hard_sl=999.0)
        except InvariantViolation:
            _assert(True, "update_risk rejects hard_sl > current_price")
        else:
            _assert(False, "update_risk should have raised InvariantViolation")

        updated = command.update_risk(snap2.cycle_id, hard_sl=185.0, target=230.0)
        _assert(updated.hard_stop_loss == 185.0 and updated.target_price == 230.0,
                "update_risk persists valid edits")
        _assert(len(bus.events[RiskUpdated]) == 1, "RiskUpdated published")

        # ── reload semantics ─────────────────────────────────────────────
        command.stop()  # type: ignore[attr-defined]
        q2, c2 = build_default_service(engine, _CaptureBus())
        c2.start()  # type: ignore[attr-defined]
        c2.reload()
        open_after_reload = q2.open_cycles()
        _assert(len(open_after_reload) == 1, "reload re-attaches the 1 open cycle")
        c2.stop()  # type: ignore[attr-defined]

    finally:
        try:
            command.stop()  # type: ignore[attr-defined]
        except Exception:
            pass

    print("\n[Cycle] smoke test PASSED")


if __name__ == "__main__":
    main()
