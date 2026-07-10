"""Tests for the inbound command bridge (MD-INF-010.001.M11)."""
from __future__ import annotations

from us_swing.core.notifications import CommandPort
from us_swing.data.models import AccountState, FilteredStockEntry, OpenPosition
from us_swing.gui.telegram_commands import TelegramCommandBridge


class _FakeApp:
    """Minimal AppService double exposing only what the bridge reads."""

    def __init__(
        self,
        positions: list[OpenPosition],
        account: AccountState,
        screener: list[FilteredStockEntry] | None = None,
        candles: dict[str, list[dict]] | None = None,
    ) -> None:
        self._positions = positions
        self._account = account
        self._screener = screener or []
        self._candles = candles or {}

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

    def get_latest_screener_results(self) -> list[FilteredStockEntry]:
        return self._screener

    def get_candles_bulk(
        self, symbols: list[str], timeframe: str = "1d", limit: int = 200
    ) -> dict[str, list[dict]]:
        return {s: self._candles[s] for s in symbols if s in self._candles}

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
    assert "Open Positions · 2" in reply


def _screen(symbol: str, score: float, name: str) -> FilteredStockEntry:
    return FilteredStockEntry(
        symbol=symbol, score=score, trading_styles=[], assigned_users=[],
        screener_name=name, run_type="scheduled", date="2026-07-10", time="09:32",
    )


def test_screener_shows_score_price_change_and_preset(qapp):
    """UT-INF-010.001.M11.T04: screener lists stocks by score with price, %chg, preset."""
    rows = [_screen("AAPL", 0.85, "Momentum Pullback"), _screen("NVDA", 0.92, "52W High Breakout")]
    candles = {
        "NVDA": [{"close": 120.0}, {"close": 124.2}],
        "AAPL": [{"close": 200.0}, {"close": 197.0}],
    }
    bridge = TelegramCommandBridge(  # type: ignore[arg-type]
        _FakeApp([], _account(), screener=rows, candles=candles)
    )
    reply = bridge.screener()
    assert "0.92" in reply and "52W High Breakout" in reply
    assert "124.20" in reply and "+3.5%" in reply   # (124.2-120)/120
    assert "-1.5%" in reply                          # AAPL (197-200)/200
    assert reply.index("NVDA") < reply.index("AAPL")  # ranked by score


def test_pnl_handles_flat_account(qapp):
    """UT-INF-010.001.M11.T03: pnl() reports zero cleanly with no positions."""
    bridge = TelegramCommandBridge(_FakeApp([], _account(pnl=0.0)))  # type: ignore[arg-type]
    reply = bridge.pnl()
    assert "Realized — <b>$0.00</b>" in reply
    assert "Open positions — <b>0</b>" in reply
