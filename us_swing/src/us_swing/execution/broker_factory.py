"""Module: MD-EXE-015.003.M01 — execution/broker_factory.py
Parent SRD: SRD-EXE-015.004

Broker selection (Broker_fix.md Phase 6 — connection only).

Maps a user's ``(mode, broker_name)`` onto a concrete :class:`Broker`:

* ``mode == 'paper'`` always yields the ``SimBroker`` mock exchange;
* ``mode == 'live'`` yields the named live broker (currently only ``IBKR``).

The live brokers are held in a name-keyed registry, so adding a future broker is
a one-line entry here — no caller changes.  Selection is wired in the GUI's
``app_service``; the mode/broker values are hard-coded (``paper`` / ``IBKR``)
until the Settings UI is added.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from us_swing.broker.broker import Broker
from us_swing.broker.ibkr import IBKRBroker, IBKRClientGateway
from us_swing.broker.sim import PriceProvider, Scheduler, SimBroker

# Live broker name → builder.  The builder receives a connected order client
# (e.g. an ``IBKRClient``) and returns a :class:`Broker`.
LIVE_BROKERS: dict[str, Callable[[Any], Broker]] = {
    "IBKR": lambda client: IBKRBroker(IBKRClientGateway(client)),
}


def build_broker(
    *,
    mode: str,
    broker_name: str,
    scheduler: Scheduler,
    live_client_provider: Callable[[], Any] | None = None,
    price_provider: PriceProvider | None = None,
) -> Broker:
    """Return the broker for ``mode``/``broker_name``.

    Args:
        mode: ``'paper'`` or ``'live'``.
        broker_name: Live broker key (e.g. ``'IBKR'``); ignored in paper mode.
        scheduler: Async scheduler for the simulated broker's deferred fills.
        live_client_provider: Returns the connected order client; required and
            called only for live mode.
        price_provider: Resolves a symbol's current live market price for the
            simulated broker's fills (SRD-INF-009.007); paper mode only.

    Raises:
        ValueError: If a live ``broker_name`` is not registered.
        RuntimeError: If live mode is requested without a connection.
    """
    if mode == "paper":
        return SimBroker(scheduler=scheduler, price_provider=price_provider)
    builder = LIVE_BROKERS.get(broker_name)
    if builder is None:
        raise ValueError(
            f"Unknown broker '{broker_name}'. Available: {sorted(LIVE_BROKERS)}"
        )
    if live_client_provider is None:
        raise RuntimeError(
            f"Live mode selected ({broker_name}) but no broker connection is available"
        )
    return builder(live_client_provider())


__all__ = ["LIVE_BROKERS", "build_broker"]
