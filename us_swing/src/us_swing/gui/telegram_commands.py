"""
Module: MD-INF-010.001.M11 — gui/telegram_commands.py
Parent SRD: SRD-INF-010.015

``TelegramCommandBridge`` is the :class:`CommandPort` implementation for inbound
bot commands. The poller runs on the notification thread, but app state lives on
the GUI thread, so every query is marshalled onto the GUI thread with a blocking
queued signal and a ``Future`` before it touches ``AppService``.
"""
from __future__ import annotations

import html
from concurrent.futures import Future
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

if TYPE_CHECKING:
    from us_swing.gui.app_service import AppService

_TIMEOUT_S = 10.0


def _esc(value: object) -> str:
    """HTML-escape a value for Telegram's HTML parse mode."""
    return html.escape(str(value), quote=False)


def _dot(value: float) -> str:
    """Green when non-negative, red when negative."""
    return "🟢" if value >= 0 else "🔴"


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
        feed_raw = self._app.get_feed_status()
        feed = feed_raw.replace("_", " ").title()
        nyse_raw = self._app.get_market_status().get("nyse", "unknown")
        nyse = nyse_raw.replace("_", " ").title()
        feed_dot = "🟢" if feed_raw.lower() == "connected" else "🔴"
        mkt_dot = (
            "🟢" if nyse_raw == "open"
            else "🟡" if nyse_raw in ("pre_market", "after_hours")
            else "🔴"
        )
        return (
            "📊 <b>System Status</b>\n\n"
            f"{feed_dot}  Feed — <b>{_esc(feed)}</b>\n"
            f"{mkt_dot}  Market · NYSE — <b>{_esc(nyse)}</b>"
        )

    def _pnl(self) -> str:
        acct = self._app.get_account_state()
        positions = self._app.get_positions()
        unrealized = sum(p.unrealised_pnl for p in positions)
        return (
            "💰 <b>Profit &amp; Loss</b>\n\n"
            f"{_dot(acct.daily_pnl)}  Realized — <b>${acct.daily_pnl:,.2f}</b>\n"
            f"{_dot(unrealized)}  Unrealized — <b>${unrealized:,.2f}</b>\n"
            f"📌  Open positions — <b>{len(positions)}</b>"
        )

    def _positions(self) -> str:
        positions = self._app.get_positions()
        if not positions:
            return "📈 <b>Open Positions</b>\n\nNothing open right now"
        table = [f"{'Symbol':<7}{'Qty':>5}{'Avg':>11}{'P&L':>12}"]
        for p in positions:
            table.append(
                f"{p.symbol:<7}{p.quantity:>5}"
                f"{p.average_price:>11,.2f}{p.unrealised_pnl:>+12,.2f}"
            )
        return (
            f"📈 <b>Open Positions · {len(positions)}</b>\n\n"
            f"<pre>{_esc(chr(10).join(table))}</pre>"
        )

    def _signals(self) -> str:
        signals = self._app.get_pending_signals()
        if not signals:
            return "🔔 <b>Pending Signals</b>\n\nNo pending signals"
        lines = [
            f"• <b>{_esc(s.side)} {_esc(s.symbol)}</b>  <i>{_esc(s.strategy_id)}</i>"
            for s in signals
        ]
        return f"🔔 <b>Pending Signals · {len(signals)}</b>\n\n" + "\n".join(lines)

    def _screener(self) -> str:
        rows = self._app.get_latest_screener_results()
        if not rows:
            return "🔎 <b>Screener</b>\n\nNo recent results"
        rows = sorted(rows, key=lambda r: r.score, reverse=True)
        top = rows[:10]
        prices = self._app.get_candles_bulk([r.symbol for r in top], "1d", limit=2)
        latest = max(rows, key=lambda r: (r.date, r.time))
        when = latest.date + (f" · {latest.time}" if latest.time else "")

        table = [f"{'Sym':<6}{'Score':>6}{'Last':>10}{'Chg':>8}  Screen"]
        for r in top:
            bars = prices.get(r.symbol) or []
            last_s, chg_s = "—", "—"
            if bars:
                last = float(bars[-1]["close"])
                last_s = f"{last:,.2f}"
                prev = float(bars[-2]["close"]) if len(bars) >= 2 else 0.0
                if prev:
                    chg_s = f"{(last - prev) / prev * 100:+.1f}%"
            screen = r.screener_name if len(r.screener_name) <= 22 else r.screener_name[:21] + "…"
            table.append(f"{r.symbol:<6}{r.score:>6.2f}{last_s:>10}{chg_s:>8}  {screen}")

        out = (
            f"🔎 <b>Screener · {len(rows)} stock(s)</b>\n"
            f"As of {_esc(when)}\n\n"
            f"<pre>{_esc(chr(10).join(table))}</pre>"
        )
        if len(rows) > len(top):
            out += f"\n… +{len(rows) - len(top)} more"
        return out

    def _cycles(self) -> str:
        open_strats = self._app.get_strategies_with_open_cycles()
        closed = self._app.get_recent_closed_cycles()
        open_part = ", ".join(_esc(s) for s in sorted(open_strats)) if open_strats else "none"
        return (
            "🔄 <b>Trade Cycles</b>\n\n"
            f"🟢  Open — {open_part}\n"
            f"✅  Closed today — <b>{len(closed)}</b>"
        )
