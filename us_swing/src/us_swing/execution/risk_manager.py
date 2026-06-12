"""
Module: MD-EXE-001.001.M01 / MD-EXE-017.001.M01 / MD-EXE-017.012.M10 — RiskManager
Parent SRD: SRD-EXE-001.001, SRD-EXE-001.002, SRD-EXE-005.004,
            SRD-EXE-017.003, SRD-EXE-017.005, SRD-EXE-017.006,
            SRD-EXE-017.015, SRD-EXE-017.017
"""
from __future__ import annotations

import logging
import math
from collections.abc import Callable, Sequence
from typing import Protocol

from us_swing.data.models import AccountState, OpenPosition, RiskConfig
from us_swing.execution.strategy_engine._events import RiskWarning
from us_swing.execution.strategy_engine._protocols import (
    CanAllocateResult,
    ValidationResult,
)
from us_swing.execution.strategy_engine._signals import TradeSignal

log = logging.getLogger(__name__)


class _PositionSource(Protocol):
    """Minimal read interface RiskManager needs for capital checks."""

    def get_all(self, user_id: int) -> Sequence[OpenPosition]: ...


class RiskManager:
    """Synchronous risk gate: position sizing, capital checks, circuit-breaker guard."""

    def __init__(
        self,
        config: RiskConfig,
        account_provider: Callable[[], AccountState],
        cb_state_provider: Callable[[], bool],
        user_id: int,
        tracker: _PositionSource | None = None,
        effective_capital_provider: Callable[[], float] | None = None,
        warning_sink: Callable[[RiskWarning], None] | None = None,
    ) -> None:
        self._config = config
        self._account_provider = account_provider
        self._cb_state_provider = cb_state_provider
        self._user_id = user_id
        self._tracker = tracker
        self._effective_capital_provider = effective_capital_provider
        self._warning_sink = warning_sink
        self._reservations: dict[tuple[str, str], float] = {}

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _effective_capital(self) -> float:
        """Per-user dollar budget; falls back to account equity when unset."""
        if self._effective_capital_provider is not None:
            return self._effective_capital_provider()
        return self._account_provider().equity

    def _emit_warning(self, kind: str, symbol: str, message: str) -> None:
        if self._warning_sink is not None:
            self._warning_sink(RiskWarning(kind=kind, symbol=symbol, message=message))

    @staticmethod
    def size_for_strategy(
        entry_price: float,
        capital_max_pct: int,
        effective_capital: float,
    ) -> int:
        """Share count so that `entry_price × qty ≤ effective_capital × pct/100`."""
        if entry_price <= 0:
            return 0
        budget = effective_capital * capital_max_pct / 100.0
        return math.floor(budget / entry_price)

    # ── RiskValidator protocol ────────────────────────────────────────────────

    def validate(self, signal: TradeSignal) -> ValidationResult:
        """Final gate: only the circuit breaker blocks; other limits are advisory.

        The submission quantity is the capital-max-sized `qty_recommended` set by
        the router (FO-EXE-017), not the legacy risk-per-trade formula.
        """
        account = self._account_provider()
        cb_active = self._cb_state_provider()
        result = self.validate_signal(signal, account, cb_active)
        if not result.ok:
            return result
        return ValidationResult(ok=True, qty=signal.qty_recommended or 0)

    def margin_available(self) -> float:
        """Remaining budget across all strategies: capital − deployed − reservations.

        Deployed value is read live from the open-cycle tracker, so an EXIT fill
        frees margin on the next call without any event plumbing. Reservations
        cover the enqueue→fill window (SRD-EXE-017.017). Never negative.
        """
        deployed = 0.0
        if self._tracker is not None:
            deployed = sum(
                p.average_price * p.quantity
                for p in self._tracker.get_all(self._user_id)
            )
        reserved = sum(self._reservations.values())
        return max(0.0, self._effective_capital() - deployed - reserved)

    def reserve(self, strategy_id: str, symbol: str, value: float) -> None:
        """Hold projected entry value so same-bar entries cannot over-commit."""
        self._reservations[(strategy_id, symbol)] = value

    def release(self, strategy_id: str, symbol: str) -> None:
        """Drop a reservation on fill, reject, or rollback (idempotent)."""
        self._reservations.pop((strategy_id, symbol), None)

    def can_allocate(self, strategy_id: str, capital_max_pct: int) -> CanAllocateResult:
        """Blocking per-strategy cap measured against the absolute capital budget."""
        if self._tracker is None:
            return CanAllocateResult(ok=True)
        limit = self._effective_capital() * capital_max_pct / 100.0
        deployed = sum(
            p.average_price * p.quantity
            for p in self._tracker.get_all(self._user_id)
            if p.strategy_id == strategy_id
        )
        if deployed >= limit:
            return CanAllocateResult(
                ok=False,
                reason=f"strategy {strategy_id!r} at capital limit",
            )
        return CanAllocateResult(ok=True)

    # ── Public helpers ────────────────────────────────────────────────────────

    def validate_signal(
        self,
        signal: TradeSignal,
        account_state: AccountState,
        cb_active: bool,
    ) -> ValidationResult:
        """Only the circuit breaker blocks; max-position and risk-per-trade warn."""
        if cb_active:
            return ValidationResult(ok=False, reason="circuit breaker active")

        entry = signal.entry_price or 0.0
        qty = signal.qty_recommended or 0
        proposed = entry * qty

        if proposed > self._config.max_position_value:
            self._emit_warning(
                "max_position",
                signal.symbol,
                f"[Risk] {signal.symbol} position ${proposed:.0f} exceeds max position "
                f"${self._config.max_position_value:.0f}",
            )

        stop = signal.stop_loss or 0.0
        if entry > 0 and stop > 0 and account_state.equity > 0:
            risk_pct = abs(entry - stop) * qty / account_state.equity * 100.0
            if risk_pct > self._config.risk_per_trade_pct:
                self._emit_warning(
                    "risk_per_trade",
                    signal.symbol,
                    f"[Risk] {signal.symbol} trade risk {risk_pct:.1f}% exceeds limit "
                    f"{self._config.risk_per_trade_pct:.1f}%",
                )

        return ValidationResult(ok=True)

    def calculate_position_size(
        self,
        signal: TradeSignal,
        account_state: AccountState,
    ) -> int:
        """floor(equity*risk_pct / risk_per_share), capped at max_position_value/entry."""
        entry = signal.entry_price or 0.0
        stop = signal.stop_loss or 0.0
        if entry <= 0 or stop <= 0 or entry == stop:
            return 0
        risk_per_share = abs(entry - stop)
        risk_dollars = account_state.equity * self._config.risk_per_trade_pct / 100
        formula_qty = math.floor(risk_dollars / risk_per_share)
        cap = math.floor(self._config.max_position_value / entry)
        return min(formula_qty, cap)

