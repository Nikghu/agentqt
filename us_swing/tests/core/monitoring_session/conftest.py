"""Shared fixtures for the monitoring-session test suite (FO-EXE-009 / FO-EXE-010).

Provides:
- ``engine`` — fresh in-memory SQLite engine with the full schema applied
  (migration is auto-run via ``create_schema``).
- ``seed_user`` — single ``users(user_id=1)`` row that satisfies the FK on
  ``trades`` and ``positions``.
- ``seed_price`` — factory that inserts N rows per timeframe for a symbol.
- ``make_screener_result`` — builds a duck-typed adapter exposing the
  ``preset_id``/``run_timestamp``/``results`` fields ``on_screener_results``
  reads off a ``ScreenerRunResult``.
- ``build_service`` — factory wrapper around ``build_default_service`` with
  injectable ``today``/``filtered_provider`` overrides.
- ``event_collector`` — subscribes every ``MonitoringEvent`` subtype to a
  list so tests can assert publication order and content.
"""
from __future__ import annotations

# Break circular import in us_swing.db package on test bootstrap.
import us_swing.data  # noqa: F401

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Iterator

import pytest
from sqlalchemy import Engine, create_engine, text

from us_swing.core.monitoring_session import (
    MonitoringCommand,
    MonitoringEventBus,
    MonitoringQuery,
    ReconcileCompleted,
    SymbolEnteredPosition,
    SymbolEvicted,
    SymbolExitedPosition,
    SymbolPositionScaled,
    SymbolSkipped,
    SymbolStartedMonitoring,
    build_default_service,
)
from us_swing.db.schema import create_schema


@pytest.fixture
def engine() -> Iterator[Engine]:
    """Fresh in-memory SQLite engine with full schema + lifecycle migration."""
    eng = create_engine("sqlite:///:memory:", future=True)
    create_schema(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def seed_user(engine: Engine) -> int:
    """Insert one user row so trades/positions FK constraints are satisfied."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (user_id, username, display_name, ibkr_client_id) "
                "VALUES (1, 'sys', 'System', 11)"
            )
        )
    return 1


@pytest.fixture
def seed_price(engine: Engine) -> Callable[[str, int], None]:
    """Returns a callable ``seed_price(symbol, n=3)`` that inserts N rows per
    intraday timeframe so eviction has something to delete."""
    def _seed(symbol: str, n: int = 3) -> None:
        with engine.begin() as conn:
            for tf in ("price_1m", "price_3m", "price_15m"):
                for i in range(n):
                    conn.execute(
                        text(
                            f"INSERT OR IGNORE INTO {tf} "
                            f"(symbol, datetime, open, high, low, close, volume) "
                            f"VALUES (:s, :dt, 1, 1, 1, 1, 1)"
                        ),
                        {"s": symbol, "dt": f"2026-05-14T09:3{i}:00"},
                    )
    return _seed


@pytest.fixture
def open_cycle(engine: Engine) -> Callable[..., None]:
    """Insert a ``trade_cycles`` row for *symbol* — the live position surface
    that replaced the retired ``positions`` table (FO-EXE-016)."""
    def _open(symbol: str, order_id: str | None = None, state: str = "OPEN") -> None:
        oid = order_id or f"oc-{symbol}"
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO trade_cycles (strategy_id, symbol, user_id, "
                    "monitoring_session_date, entry_time, entry_price, entry_qty, "
                    "entry_order_id, hard_stop_loss, target_type, stoploss_type, "
                    "state, opened_at) VALUES "
                    "('s', :sym, 1, '2026-05-14', '2026-05-14T14:00:00Z', 50.0, 100, "
                    ":oid, 48.0, 'fixed', 'fixed', :st, '2026-05-14T14:00:00Z')"
                ),
                {"sym": symbol, "oid": oid, "st": state},
            )
    return _open


@dataclass(frozen=True)
class _ScreenerResultAdapter:
    """Duck-typed stand-in for ``screener.storage.ScreenerRunResult`` —
    exposes the three fields ``MonitoringSessionService.on_screener_results``
    consumes (``preset_id``, ``run_timestamp``, ``results``).
    """
    preset_id:     str
    run_timestamp: str
    results:       dict[str, dict[str, Any]]


@pytest.fixture
def make_screener_result() -> Callable[..., _ScreenerResultAdapter]:
    """Returns a factory: ``make(passed=[...], failed=[...], preset_id=..., ts=...)``."""
    def _build(
        passed:        list[str]      = (),
        failed:        list[str]      = (),
        preset_id:     str            = "preset-test",
        run_timestamp: str            = "2026-05-14T13:30:00Z",
    ) -> _ScreenerResultAdapter:
        results: dict[str, dict[str, Any]] = {}
        for s in passed:
            results[s] = {"passed": True}
        for s in failed:
            results[s] = {"passed": False}
        return _ScreenerResultAdapter(preset_id, run_timestamp, results)
    return _build


@pytest.fixture
def build_service(engine: Engine) -> Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]]:
    """Returns a factory wrapping ``build_default_service`` with optional overrides.

    Usage::

        query, cmd, bus = build_service(
            today=date(2026, 5, 15),
            filtered={"A", "D"},
        )
    """
    def _build(
        today:    date | None              = None,
        filtered: frozenset[str] | set[str] | None = None,
    ) -> tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]:
        today_provider = (lambda d=today: d) if today is not None else None
        filtered_set   = frozenset(filtered) if filtered is not None else frozenset()
        filtered_provider = (lambda _d, f=filtered_set: f) if filtered is not None else None
        return build_default_service(
            engine,
            today_provider    = today_provider,
            filtered_provider = filtered_provider,
        )
    return _build


_ALL_EVENT_TYPES = (
    SymbolStartedMonitoring,
    SymbolEnteredPosition,
    SymbolPositionScaled,
    SymbolExitedPosition,
    SymbolSkipped,
    SymbolEvicted,
    ReconcileCompleted,
)


@pytest.fixture
def event_collector() -> Callable[[MonitoringEventBus], list]:
    """Subscribes a single appender to every MonitoringEvent subtype.

    Returns the collector list — tests can index by ``type(evt).__name__`` or
    by position to assert publication order and payload content.
    """
    def _attach(bus: MonitoringEventBus) -> list:
        collected: list = []
        for et in _ALL_EVENT_TYPES:
            bus.subscribe(et, collected.append)
        return collected
    return _attach
