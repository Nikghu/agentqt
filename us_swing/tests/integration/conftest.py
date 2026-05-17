"""Integration-test fixtures — duplicates from core/monitoring_session/conftest.py.

These fixtures are inlined here to avoid cross-conftest pytest_plugins path
resolution issues between the core/ and integration/ subdirectories.
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
    """Returns a callable seed_price(symbol, n=3) that inserts N rows per intraday timeframe."""
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


@dataclass(frozen=True)
class _ScreenerResultAdapter:
    preset_id:     str
    run_timestamp: str
    results:       dict[str, dict[str, Any]]


@pytest.fixture
def make_screener_result() -> Callable[..., _ScreenerResultAdapter]:
    """Returns a factory: make(passed=[...], failed=[...], preset_id=..., ts=...)."""
    def _build(
        passed:        list[str] = (),
        failed:        list[str] = (),
        preset_id:     str = "preset-test",
        run_timestamp: str = "2026-05-14T13:30:00Z",
    ) -> _ScreenerResultAdapter:
        results: dict[str, dict[str, Any]] = {}
        for s in passed:
            results[s] = {"passed": True}
        for s in failed:
            results[s] = {"passed": False}
        return _ScreenerResultAdapter(preset_id, run_timestamp, results)
    return _build


@pytest.fixture
def build_service(
    engine: Engine,
) -> Callable[..., tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]]:
    """Factory wrapping build_default_service with optional overrides."""
    def _build(
        today:    date | None                              = None,
        filtered: frozenset[str] | set[str] | None = None,
    ) -> tuple[MonitoringQuery, MonitoringCommand, MonitoringEventBus]:
        today_provider    = (lambda d=today: d) if today is not None else None
        filtered_set      = frozenset(filtered) if filtered is not None else frozenset()
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
    """Subscribes a single appender to every MonitoringEvent subtype."""
    def _attach(bus: MonitoringEventBus) -> list:
        collected: list = []
        for et in _ALL_EVENT_TYPES:
            bus.subscribe(et, collected.append)
        return collected
    return _attach
