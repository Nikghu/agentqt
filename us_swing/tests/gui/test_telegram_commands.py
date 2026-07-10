"""Tests for the inbound command bridge (MD-INF-010.001.M11)."""
from __future__ import annotations

from us_swing.core.notifications import CommandPort
from us_swing.data.models import AccountState, OpenPosition
from us_swing.gui.telegram_commands import TelegramCommandBridge


class _FakeApp:
    """Minimal AppService double exposing only what the bridge reads."""

    def __init__(self, positions: list[OpenPosition], account: AccountState) -> None:
        self._positions = positions
        self._account = account

    def get_feed_status(self) -> str:
        return "connected"

    def get_market_status(self) -> dict[str, str]:
        return {"nyse": "open", "nasdaq": "open"}

    def get_account_state(self, user_id: int | None = None) -> AccountState:
        return self._account

    def get_positions(self, user_id: int | None = None) -> list[OpenPosition]:
        return self._positions

    def get_pending_signals(self, user_id: int | None = None) -> list:
        return []

    def get_latest_screener_results(self) -> list:
        return []

    def get_strategies_with_open_cycles(self) -> set[str]:
        return set()

    def get_recent_closed_cycles(self) -> list:
        return []


def _position(symbol: str, price: float, current: float) -> OpenPosition:
    return OpenPosition(
        symbol=symbol,
        user_id=1,
        quantity=10,
        average_price=price,
        stop_loss=0.0,
        target_price=0.0,
        mode="paper",
        current_price=current,
    )


def _account(pnl: float = 0.0) -> AccountState:
    return AccountState(
        user_id=1,
        equity=100_000.0,
        start_of_day_equity=100_000.0,
        open_position_value=0.0,
        daily_pnl=pnl,
    )


def test_bridge_satisfies_command_port(qapp):
    """UT-INF-010.001.M11.T01: the bridge is a CommandPort."""
    bridge = TelegramCommandBridge(_FakeApp([], _account()))  # type: ignore[arg-type]
    assert isinstance(bridge, CommandPort)


def test_positions_lists_symbols(qapp):
    """UT-INF-010.001.M11.T02: positions() names each open symbol and the count."""
    positions = [_position("AAPL", 100.0, 110.0), _position("MSFT", 200.0, 190.0)]
    bridge = TelegramCommandBridge(_FakeApp(positions, _account()))  # type: ignore[arg-type]
    reply = bridge.positions()
    assert "AAPL" in reply
    assert "MSFT" in reply
    assert "2 open" in reply


def test_pnl_handles_flat_account(qapp):
    """UT-INF-010.001.M11.T03: pnl() reports zero cleanly with no positions."""
    bridge = TelegramCommandBridge(_FakeApp([], _account(pnl=0.0)))  # type: ignore[arg-type]
    reply = bridge.pnl()
    assert "Realized $0.00" in reply
    assert "0 open position(s)" in reply
