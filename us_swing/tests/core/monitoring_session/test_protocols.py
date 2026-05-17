"""Tests for MD-EXE-009.001.M02 — core/monitoring_session/_protocols.py."""
from __future__ import annotations


import pytest
from sqlalchemy import Engine

from us_swing.core.monitoring_session import (
    MonitoringCommand,
    MonitoringEventBus,
    MonitoringQuery,
    build_default_service,
)


# ── UT-EXE-009.001.M02.T02 ──────────────────────────────────────────────────


def test_protocols_are_runtime_checkable() -> None:
    """UT-EXE-009.001.M02.T02: All three Protocols are @runtime_checkable."""
    for proto in (MonitoringQuery, MonitoringCommand, MonitoringEventBus):
        # runtime_checkable protocols expose RUNTIME_CHECKABLE flag and support
        # isinstance() calls without raising TypeError.
        class _Dummy:
            pass

        # Should not raise TypeError (which non-runtime_checkable would).
        try:
            isinstance(_Dummy(), proto)  # type: ignore[arg-type]
        except TypeError as exc:
            pytest.fail(
                f"{proto.__name__} is not @runtime_checkable: {exc}"
            )

        # Verify the protocol carries the runtime_checkable marker.
        # Python 3.12+ uses _is_runtime_protocol; 3.11 uses _is_protocol.
        is_rt = getattr(proto, "_is_runtime_protocol", False) or getattr(
            proto, "_is_protocol", False
        )
        assert is_rt, f"{proto.__name__} is not marked as runtime_checkable"

        # Verify there are declared methods — inspect annotations + callable attrs.
        import inspect
        members = [
            name
            for name, val in inspect.getmembers(proto)
            if not name.startswith("_") and (callable(val) or isinstance(val, property))
        ]
        assert len(members) > 0, f"{proto.__name__} has no declared members"


# ── UT-EXE-009.001.M02.T03 ──────────────────────────────────────────────────


def test_concrete_service_isinstance_both_protocols(engine: Engine) -> None:
    """UT-EXE-009.001.M02.T03: Concrete service passes isinstance checks against both Protocols."""
    query, cmd, bus = build_default_service(engine)

    assert isinstance(query, MonitoringQuery)
    assert isinstance(cmd, MonitoringCommand)
    assert isinstance(bus, MonitoringEventBus)
    # The query and command views are the same concrete object.
    assert query is cmd
