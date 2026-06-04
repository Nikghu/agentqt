"""Module: tests/execution/test_broker_factory.py
Parent SRD: SRD-EXE-015.004

Broker selection by (mode, broker_name).
"""
from __future__ import annotations

import pytest

from us_swing.broker.ibkr import IBKRBroker
from us_swing.broker.sim import SimBroker
from us_swing.execution.broker_factory import build_broker


def _noop_scheduler(_cb: object) -> None:
    pass


def test_paper_mode_yields_sim_broker() -> None:
    broker = build_broker(mode="paper", broker_name="IBKR", scheduler=_noop_scheduler)
    assert isinstance(broker, SimBroker)


def test_live_ibkr_yields_ibkr_broker() -> None:
    broker = build_broker(
        mode="live",
        broker_name="IBKR",
        scheduler=_noop_scheduler,
        live_client_provider=lambda: object(),  # gateway stores it; no ib_insync at build
    )
    assert isinstance(broker, IBKRBroker)


def test_live_unknown_broker_raises() -> None:
    with pytest.raises(ValueError, match="Unknown broker"):
        build_broker(
            mode="live",
            broker_name="ZERODHA",
            scheduler=_noop_scheduler,
            live_client_provider=lambda: object(),
        )


def test_live_without_connection_raises() -> None:
    with pytest.raises(RuntimeError, match="no broker connection"):
        build_broker(mode="live", broker_name="IBKR", scheduler=_noop_scheduler)
