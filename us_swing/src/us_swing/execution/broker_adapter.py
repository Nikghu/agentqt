"""Module: MD-EXE-015.002.M01 — execution/broker_adapter.py
Parent SRD: SRD-EXE-015.001, SRD-EXE-015.004

Broker adapter (Broker_fix.md Phase 5).

The single seam between the execution core and the pluggable broker layer.  It
satisfies the engine's existing ``ExecutionSubmitter.submit(signal, qty)``
surface — so the router is unchanged — while underneath it speaks the neutral
broker contract:

* translates a ``TradeSignal`` into a broker ``OrderRequest``;
* builds the ``OrderContext`` (risk snapshot from the strategy config) and hands
  it to :class:`OrderIngestion` at acceptance;
* subscribes to the broker's ``OrderEvent`` stream and forwards each event into
  ingestion — then notifies an optional listener so the GUI can refresh.

Broker selection (Sim vs a live broker) is decided by whoever constructs the
adapter; downstream code never sees which broker answered.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from us_swing.broker.broker import Broker, OrderEvent, OrderRequest, OrderSide, OrderType
from us_swing.execution.order_ingestion import OrderContext, OrderIngestion
from us_swing.execution.strategy_engine._signals import Action, TradeSignal

log = logging.getLogger(__name__)


class BrokerAdapter:
    """Adapts the engine's submitter surface onto the neutral broker contract."""

    def __init__(
        self,
        *,
        broker: Broker,
        ingestion: OrderIngestion,
        config_provider: Callable[[str], Any],
        user_id_provider: Callable[[], int],
        session_date_provider: Callable[[], str],
        mode_provider: Callable[[], str] | None = None,
        exit_reason_provider: Callable[[], str] | None = None,
        on_event: Callable[[OrderEvent], None] | None = None,
    ) -> None:
        self._broker = broker
        self._ingestion = ingestion
        self._config_provider = config_provider
        self._user_id_provider = user_id_provider
        self._session_date_provider = session_date_provider
        self._mode_provider = mode_provider or (lambda: "paper")
        self._exit_reason_provider = exit_reason_provider or (lambda: "manual")
        self._on_event = on_event
        broker.on_event(self._on_broker_event)

    # ── ExecutionSubmitter surface (called by the router) ────────────────────

    def submit(self, signal: TradeSignal, qty: int) -> int | None:
        is_entry = signal.action is Action.ENTRY
        side = OrderSide.BUY if is_entry else OrderSide.SELL
        request = OrderRequest(
            client_ref=signal.signal_id,
            symbol=signal.symbol,
            side=side,
            quantity=qty,
            order_type=OrderType.MARKET,
            reference_price=signal.entry_price,
        )
        broker_order_id = self._broker.place_order(request)
        self._ingestion.on_order_accepted(
            self._build_context(signal, qty, side, is_entry, broker_order_id)
        )
        return int(broker_order_id)

    # ── Broker → execution (asynchronous fills) ──────────────────────────────

    def _on_broker_event(self, event: OrderEvent) -> None:
        self._ingestion.on_order_event(event)
        if self._on_event is not None:
            self._on_event(event)

    # ── Context assembly ─────────────────────────────────────────────────────

    def _build_context(
        self,
        signal: TradeSignal,
        qty: int,
        side: OrderSide,
        is_entry: bool,
        broker_order_id: str,
    ) -> OrderContext:
        price = signal.entry_price or 0.0
        hard_sl, target_price, target_type, stoploss_type = self._entry_risk(
            self._config_provider(signal.strategy_id) if is_entry else None, price
        )
        return OrderContext(
            broker_order_id=broker_order_id,
            signal_id=signal.signal_id,
            strategy_id=signal.strategy_id,
            user_id=self._user_id_provider(),
            symbol=signal.symbol,
            side=side,
            is_entry=is_entry,
            quantity=qty,
            intended_price=price,
            mode=self._mode_provider(),
            hard_stop_loss=hard_sl,
            target_price=target_price,
            target_type=target_type,
            stoploss_type=stoploss_type,
            monitoring_session_date=self._session_date_provider(),
            exit_reason=self._exit_reason_provider() if not is_entry else "manual",
        )

    @staticmethod
    def _entry_risk(config: Any, price: float) -> tuple[float, float | None, str, str]:
        """Compute the absolute hard-stop and target from the strategy config,
        mirroring the legacy paper-fill snapshot."""
        if config is None:
            return 0.0, None, "fixed", "fixed"
        target_enabled = bool(getattr(config, "target_enabled", False))
        sl_enabled = bool(getattr(config, "stoploss_enabled", False))
        target_pct = float(getattr(config, "target_value", 0.0))
        sl_pct = float(getattr(config, "stoploss_value", 0.0))
        target_type = (getattr(config, "target_type", "fixed") or "fixed")
        stoploss_type = (getattr(config, "stoploss_type", "fixed") or "fixed")
        target_price = price * (1.0 + target_pct / 100.0) if target_enabled else None
        hard_sl = price * (1.0 - sl_pct / 100.0) if sl_enabled else 0.0
        return hard_sl, target_price, target_type, stoploss_type


__all__ = ["BrokerAdapter"]
