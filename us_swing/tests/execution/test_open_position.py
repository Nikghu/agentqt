"""
Module: MD-EXE-018.013.M09 — data/models.py OpenPosition direction tests
Parent SRD: SRD-EXE-018.013
"""
from __future__ import annotations

import pytest

from us_swing.data.models import OpenPosition


def _position(**overrides: object) -> OpenPosition:
    values: dict[str, object] = {
        "symbol": "AAPL",
        "user_id": 1,
        "quantity": 10,
        "average_price": 100.0,
        "stop_loss": 0.0,
        "target_price": 0.0,
        "mode": "paper",
    }
    values.update(overrides)
    return OpenPosition(**values)  # type: ignore[arg-type]


def test_short_position_profit() -> None:
    """UT-EXE-018.013.M09.T01: a SHORT position shows a profit when the price falls."""
    pos = _position(direction="SHORT", current_price=97.0)
    assert pos.unrealised_pnl == pytest.approx(30.0)
    assert pos.pnl_pct == pytest.approx(3.0)


def test_short_position_loss() -> None:
    """UT-EXE-018.013.M09.T02: a SHORT position shows a loss when the price rises."""
    assert _position(direction="SHORT", current_price=103.0).unrealised_pnl == pytest.approx(-30.0)


def test_position_defaults_to_long() -> None:
    """UT-EXE-018.013.M09.T03: a position without a direction is LONG and keeps the long sign."""
    pos = _position(current_price=103.0)
    assert pos.direction == "LONG"
    assert pos.unrealised_pnl == pytest.approx(30.0)
