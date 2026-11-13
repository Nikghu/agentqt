"""
Module: MD-MKT-013.008.M02 — market/watch_flag.py
Parent SRD: SRD-MKT-013.008
Also: SRD-MKT-005.023 (fixed levels in the plan text) — AI Desk v3 M1
Also: SRD-MKT-013.009 (verdict form, feed item, broken alert), SRD-MKT-013.012 (log line)
Also: SRD-MKT-013.013 (broken plan, stop or target touch go to the boss) — AI Desk v3 M2

The flag skill: for the oldest flag of the day that has no answer yet, shows the model the
flag, the plan for that stock (an idea or an open trade) and the last bars, and asks whether
the plan still holds. The answer is advice only; nothing here places or changes a trade.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from us_swing.core.desk_agents import AgentContext, Facts, FeedItem, Talker
from us_swing.core.desk_alerts import raise_alert
from us_swing.core.desk_msg import Draft
from us_swing.core.desk_watch import (
    NY,
    Flag,
    answer_flag,
    connect,
    label,
    next_flag,
    open_trades,
)
from us_swing.core.desk_watch import plan_day as _plan_day
from us_swing.market.candles import CANDLE_DB
from us_swing.market.watch import levels, today_bars

log = logging.getLogger(__name__)

KEY = "watch_flag"
BARS_SHOWN = 12
FLAG_LIFE = timedelta(minutes=30)  # same as the watch_flag event expiry
_RULES = (
    "Rules: say holds when the plan still makes sense, watch when it needs care, broken when "
    "the reason for the idea or trade is gone. Keep the note to two short sentences. You "
    "never place, change or close a trade; the owner decides."
)


class WatchVerdict(BaseModel):
    """The model's answer for one flag, checked by the gateway."""

    model_config = ConfigDict(extra="forbid")

    verdict: Literal["holds", "watch", "broken"]
    note: str = Field(min_length=3, max_length=300)


def _now() -> datetime:
    return datetime.now(NY)


def _plan_text(home: Path, symbol: str, day: str) -> str:
    lines: list[str] = []
    con = connect(home)
    try:
        plan = _plan_day(con, day)
        if plan is not None:
            join, trig_col, stop_col = levels(con)
            for side, trig, stop, setup in con.execute(
                    f"SELECT i.side, {trig_col}, {stop_col}, i.setup FROM ideas i {join} "  # noqa: S608
                    "WHERE i.date = ? AND i.symbol = ?", (plan, symbol)):
                lines.append(f"Idea: {side}, trigger {trig}, stop {stop}, setup {setup}")
    finally:
        con.close()
    for t in open_trades(home):
        if t.symbol == symbol:
            target = "none" if t.target is None else f"{t.target:.2f}"
            lines.append(f"Open trade: {t.side}, entry {t.entry:.2f}, stop {t.stop:.2f}, "
                         f"target {target}, strategy {t.strategy or 'unknown'}")
    return "\n".join(lines) or "No idea or open trade for this stock today."


class WatchFlagSkill:
    """Answers one watcher flag each time the watcher employee is woken."""

    key = KEY
    needs: tuple[str, ...] = ()
    answer = WatchVerdict

    def __init__(self, candles: Path = CANDLE_DB,
                 clock: Callable[[], datetime] = _now) -> None:
        """Set the candles file and the clock; injectable for tests."""
        self._candles = candles
        self._clock = clock
        self._shown: int | None = None

    def facts(self, home: Path) -> Facts:
        """The oldest unanswered flag, its plan and the last bars; stale when none is open."""
        now = self._clock()
        day = now.astimezone(NY).date().isoformat()
        flag = next_flag(home, day, now - FLAG_LIFE)
        self._shown = None if flag is None else flag.id
        if flag is None:
            return Facts("", day, False, "no open flag")
        bars = today_bars(self._candles, [flag.symbol], now).get(flag.symbol, [])
        shown = [f"{b.at:%H:%M} o {b.open:.2f} h {b.high:.2f} l {b.low:.2f} c {b.close:.2f} "
                 f"v {b.volume:.0f}" for b in bars[-BARS_SHOWN:]]
        text = "\n".join([
            f"Flag #{flag.id}: {flag.symbol} {label(flag.kind)} at {flag.price:.2f} "
            f"({flag.detail})", "",
            _plan_text(home, flag.symbol, day), "",
            "Last 3-minute bars (New York time):", *(shown or ["(no bars yet)"]), "",
            _RULES,
        ])
        return Facts(text, day, True)

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        """Ask for the verdict, keep it on the flag and alert when the plan is broken."""
        flag = next_flag(ctx.home, facts.data_day, self._clock() - FLAG_LIFE)
        if flag is None or flag.id != self._shown:
            return []  # the flag shown in the facts is gone or already answered
        reply = ctx.ask(facts.text, WatchVerdict)
        now = self._clock()
        if reply is None:
            answer_flag(ctx.home, flag.id, "none", "No valid answer", now)  # never block newer
            _escalate(ctx, flag, None)
            return []
        answer_flag(ctx.home, flag.id, reply.verdict, reply.note, now)
        log.info("[Watch] %s %s: %s", flag.symbol, label(flag.kind), reply.verdict)
        if reply.verdict == "broken":
            raise_alert(ctx.home, "plan_broken", flag.symbol, 0,
                        f"{flag.symbol}: {reply.note}", now)
        _escalate(ctx, flag, reply)
        return [FeedItem("info", f"{flag.symbol} {label(flag.kind)}: {reply.verdict} — "
                                 f"{reply.note}", facts.data_day)]


_TOUCH = ("stop_touch", "target_touch")


def _escalate(ctx: AgentContext, flag: Flag, reply: WatchVerdict | None) -> None:
    """Send a broken plan or a stop or target touch to the boss (SRD-MKT-013.013).

    Only the real gateway is a ``Talker``; the employees step drops the draft while
    escalation is off, so test fakes and replays send nothing.
    """
    broken = reply is not None and reply.verdict == "broken"
    if not isinstance(ctx, Talker) or not (broken or flag.kind in _TOUCH):
        return
    what = f"{flag.symbol} {label(flag.kind)}"
    note = reply.note if reply is not None else "no verdict from the flag check"
    ctx.send(Draft(type="escalate", to="boss", subject=what[:80],
                   text=f"{what} at {flag.price:.2f}: {note}"[:600], about=[flag.symbol]))
