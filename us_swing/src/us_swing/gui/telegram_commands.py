"""
Module: MD-INF-010.001.M11 — gui/telegram_commands.py
Parent SRD: SRD-INF-010.015

``TelegramCommandBridge`` is the :class:`CommandPort` implementation for inbound
bot commands. The poller runs on the notification thread, but app state lives on
the GUI thread, so every query is marshalled onto the GUI thread with a blocking
queued signal and a ``Future`` before it touches ``AppService``.
"""
from __future__ import annotations

from concurrent.futures import Future
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

if TYPE_CHECKING:
    from us_swing.gui.app_service import AppService

_TIMEOUT_S = 10.0


class TelegramCommandBridge(QObject):
    """Answers inbound commands from live ``AppService`` state, thread-safely."""

    _request = pyqtSignal(str, object)

    def __init__(self, app: "AppService") -> None:
        super().__init__()
        self._app = app
        self._request.connect(self._on_request)

    # ── CommandPort surface — called from the notification thread ──────────────

    def status(self) -> str:
        return self._call("status")

    def pnl(self) -> str:
        return self._call("pnl")

    def positions(self) -> str:
        return self._call("positions")

    def signals(self) -> str:
        return self._call("signals")

    def screener(self) -> str:
        return self._call("screener")

    def cycles(self) -> str:
        return self._call("cycles")

    # ── Marshalling ────────────────────────────────────────────────────────────

    def _call(self, slot: str) -> str:
        """Run ``_<slot>`` on the GUI thread and block for its reply."""
        if QThread.currentThread() is self.thread():
            return self._compute(slot)
        future: Future[str] = Future()
        self._request.emit(slot, future)
        return future.result(timeout=_TIMEOUT_S)

    @pyqtSlot(str, object)
    def _on_request(self, slot: str, future: "Future[str]") -> None:
        try:
            future.set_result(self._compute(slot))
        except Exception as exc:  # surface on the caller thread, never here
            future.set_exception(exc)

    def _compute(self, slot: str) -> str:
        method = getattr(self, f"_{slot}")
        result: str = method()
        return result

    # ── Formatters (GUI thread) ────────────────────────────────────────────────

    def _status(self) -> str:
        feed = self._app.get_feed_status().replace("_", " ").title()
        market = self._app.get_market_status()
        nyse = market.get("nyse", "unknown").replace("_", " ").title()
        return f"[Status] Feed: {feed}\nMarket (NYSE): {nyse}"

    def _pnl(self) -> str:
        acct = self._app.get_account_state()
        positions = self._app.get_positions()
        unrealized = sum(p.unrealised_pnl for p in positions)
        return (
            f"[P&L] Realized ${acct.daily_pnl:,.2f}\n"
            f"Unrealized ${unrealized:,.2f} across {len(positions)} open position(s)"
        )

    def _positions(self) -> str:
        positions = self._app.get_positions()
        if not positions:
            return "[Positions] No open positions"
        lines = [
            f"{p.symbol}: {p.quantity} @ ${p.average_price:,.2f} (${p.unrealised_pnl:,.2f})"
            for p in positions
        ]
        return f"[Positions] {len(positions)} open\n" + "\n".join(lines)

    def _signals(self) -> str:
        signals = self._app.get_pending_signals()
        if not signals:
            return "[Signals] No pending signals"
        lines = [f"{s.side} {s.symbol} ({s.strategy_id})" for s in signals]
        return f"[Signals] {len(signals)} pending\n" + "\n".join(lines)

    def _screener(self) -> str:
        rows = self._app.get_latest_screener_results()
        if not rows:
            return "[Screener] No recent results"
        names = ", ".join(r.symbol for r in rows)
        return f"[Screener] {len(rows)} stock(s): {names}"

    def _cycles(self) -> str:
        open_strats = self._app.get_strategies_with_open_cycles()
        closed = self._app.get_recent_closed_cycles()
        open_part = ", ".join(sorted(open_strats)) if open_strats else "none"
        return (
            f"[Cycles] Strategies with open trades: {open_part}\n"
            f"Closed today: {len(closed)}"
        )
