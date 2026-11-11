"""
Module: MD-MKT-013.010.M03 — market/checkin_note.py
Parent SRD: SRD-MKT-013.010

The check-in skill: at 10:00, 12:30 and 15:30 New York time it shows the model the plan
stocks against their triggers, the open trades against stop and target, the SPY move and
the flags since the last check-in, and asks for a short note for the owner.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time, timedelta
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from us_swing.core.desk_agents import AgentContext, Facts, FeedItem
from us_swing.core.desk_watch import BENCHMARK, NY, flags_since, label, open_trades
from us_swing.data.market_calendar import get_exchange_status
from us_swing.market.candles import CANDLE_DB
from us_swing.market.watch import plan_ideas, prev_closes, today_bars

KEY = "checkin_note"
MARKS = (time(9, 30), time(10, 0), time(12, 30), time(15, 30))
GAP = timedelta(minutes=15)
_RULES = ("Rules: write at most 4 short sentences for the owner: what changed, what needs "
          "care and what to watch next. You never place, change or close a trade.")


class CheckinNote(BaseModel):
    """The model's check-in note, checked by the gateway."""

    model_config = ConfigDict(extra="forbid")

    note: str = Field(min_length=10, max_length=600)


def _now() -> datetime:
    return datetime.now(NY)


def _since(now: datetime) -> datetime:
    """The last check-in mark at least 15 minutes before ``now`` (09:30 at the earliest)."""
    ny = now.astimezone(NY)
    marks = [datetime.combine(ny.date(), m, NY) for m in MARKS]
    earlier = [m for m in marks if m <= ny - GAP]
    return earlier[-1] if earlier else marks[0]


def _slot(now: datetime) -> str:
    ny = now.astimezone(NY)
    done = [m for m in MARKS[1:] if datetime.combine(ny.date(), m, NY) <= ny]
    return (done[-1] if done else MARKS[1]).strftime("%H:%M")


class CheckinNoteSkill:
    """Writes one short market note at each check-in."""

    key = KEY
    needs: tuple[str, ...] = ()
    answer = CheckinNote

    def __init__(self, candles: Path = CANDLE_DB,
                 clock: Callable[[], datetime] = _now) -> None:
        """Set the candles file and the clock; injectable for tests."""
        self._candles = candles
        self._clock = clock

    def facts(self, home: Path) -> Facts:
        """Plan, trades, SPY and flags since the last check-in; stale off trading days."""
        now = self._clock()
        ny = now.astimezone(NY)
        day = ny.date().isoformat()
        if get_exchange_status(datetime.combine(ny.date(), time(12, 0), NY)) != "open":
            return Facts("", day, False, "not a trading day")
        ideas, picks = plan_ideas(home, day)
        trades = open_trades(home)
        symbols = list(dict.fromkeys([i.symbol for i in ideas] + picks
                                     + [t.symbol for t in trades] + [BENCHMARK]))
        bars = today_bars(self._candles, symbols, now)
        last = {s: b[-1].close for s, b in bars.items() if b}
        prev = prev_closes(self._candles, home, [BENCHMARK], day)
        plan_lines = [f"{i.symbol} {i.side}: last {last[i.symbol]:.2f}, trigger {i.trigger:.2f} "
                      f"({(last[i.symbol] / i.trigger - 1) * 100:+.1f}%)"
                      for i in ideas if i.symbol in last]
        trade_lines = [f"{t.symbol} {t.side}: last {last[t.symbol]:.2f}, stop {t.stop:.2f}, "
                       f"target {'none' if t.target is None else f'{t.target:.2f}'}"
                       for t in trades if t.symbol in last]
        spy = (f"SPY {(last[BENCHMARK] / prev[BENCHMARK] - 1) * 100:+.1f}% from the last close"
               if BENCHMARK in last and BENCHMARK in prev else "SPY: no bars yet")
        flags = [f"{f.created[11:16]} {f.symbol} {label(f.kind)}: {f.detail}"
                 + (f" (verdict {f.verdict})" if f.verdict else "")
                 for f in flags_since(home, _since(now)) if f.day == day]
        text = "\n".join([
            f"Check-in {_slot(now)} New York time, {day}", "",
            "Plan stocks against their triggers:", *(plan_lines or ["(none with bars)"]), "",
            "Open trades:", *(trade_lines or ["(none with bars)"]), "",
            spy, "", "Flags since the last check-in:", *(flags or ["(none)"]), "",
            _RULES,
        ])
        return Facts(text, day, True)

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        """Ask for the note and post it to the feed."""
        reply = ctx.ask(facts.text, CheckinNote)
        if reply is None:
            return []
        return [FeedItem("info", f"Check-in {_slot(self._clock())}: {reply.note}",
                         facts.data_day)]
