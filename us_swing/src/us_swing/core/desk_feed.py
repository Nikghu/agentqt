"""
Module: MD-GUI-034.054.M32 — core/desk_feed.py
Parent SRD: SRD-GUI-034.054
Also: SRD-GUI-034.056 — shared approve and reject of a trade pick
Also: MD-GUI-034.062.M36 — ask cards for Command (SRD-GUI-034.062)
Also: MD-GUI-034.043.M38 — asked panel cards and failed requests (SRD-GUI-034.043, .044)
Also: SRD-GUI-034.069 — the morning brief card is titled "Morning plan"

AI feed cards for Market Floor, read from ``desk.db`` read-only: briefs, waiting trade picks,
ready hires, lead chat replies and failed runs. Never imports ``desk``, ``market`` or ``gui``.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from us_swing.core.desk_alerts import open_alerts
from us_swing.core.desk_ai_settings import load_settings
from us_swing.core.desk_contract import DB_NAME
from us_swing.core.desk_data_asks import AskedProduct, failed_products, waiting_products
from us_swing.core.desk_hiring import list_hires
from us_swing.core.desk_recipes import recipe_words, run_recipe
from us_swing.core.desk_trades import (
    DeskTradeSink,
    TradePick,
    pick_state,
    record_trade_decision,
    trade_picks,
)

CardKind = Literal["result", "ask", "answer", "desk"]
BRIEF_LIMIT = 20
ANSWER_LIMIT = 5
_SUBJECTS = {"morning": "Morning plan", "evening": "Evening result"}
RUN_LIMIT = 5
PREVIEW_ROWS = 5
NO_ROWS = "No rows on the latest day"


@dataclass(frozen=True)
class FeedCard:
    """One AI feed card; ``pick`` is set on a trade pick Ask, ``ref`` names the Ask kind and
    ``item`` is the asked product id of a ``data`` Ask."""

    kind: CardKind
    sender: str
    subject: str
    when: datetime | None
    text: str
    symbol: str = ""
    ref: str = ""
    pick: TradePick | None = None
    item: int = 0


def _when(text: object) -> datetime | None:
    try:
        stamp = datetime.fromisoformat(str(text))
    except ValueError:
        return None
    return stamp if stamp.tzinfo is not None else None


def _rows(home: Path, sql: str, params: tuple[Any, ...]) -> list[tuple[Any, ...]]:
    path = home / DB_NAME
    if not path.exists():
        return []
    try:
        con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=2)
        try:
            return [tuple(r) for r in con.execute(sql, params).fetchall()]
        finally:
            con.close()
    except sqlite3.Error:
        return []


def ask_cards(home: Path, now: datetime) -> list[FeedCard]:
    """Waiting trade picks and ready hires as Ask cards, timed ``now``."""
    r = load_settings(home).trade_target_r
    cards = [
        FeedCard("ask", "Lead", f"Trade pick · {p.side.upper()} {p.symbol}", now,
                 f"Entry {p.entry:.2f}, stop {p.stop:.2f}, target {p.target:.2f}. {p.reason}".strip(),
                 p.symbol, "pick", p)
        for p in trade_picks(home, now, r) if p.state == "waiting"
    ]
    cards += [
        FeedCard("ask", "Hiring", f"Hire · {h.employee.name}", now,
                 f"{h.employee.name} finished the shadow days and waits for your decision.",
                 ref="hire")
        for h in list_hires(home) if h.ready
    ]
    cards += [FeedCard("ask", "Data", f"New panel · {p.title}", _when(p.created),
                       _product_text(home, p), ref="data", item=p.id)
              for p in waiting_products(home)]
    return cards


def _product_text(home: Path, product: AskedProduct) -> str:
    if product.recipe is None:
        return ""
    rows = run_recipe(home, product.recipe)[:PREVIEW_ROWS]
    preview = [" · ".join("-" if v is None else str(v) for v in r.values()) for r in rows]
    return "\n".join([recipe_words(product.recipe), *(preview or [NO_ROWS])])


def failed_cards(home: Path, now: datetime) -> list[FeedCard]:
    """Data requests the desk could not build in the last day, as Desk cards without buttons."""
    return [FeedCard("desk", "Data", "Request not built", _when(p.created),
                     f"{p.request} — {p.reason}") for p in failed_products(home, now)]


def feed_cards(home: Path, now: datetime) -> list[FeedCard]:
    """Return every feed card, newest first; Asks (timed ``now``) come first."""
    cards = ask_cards(home, now)
    for created, author, kind, text in _rows(
            home, "SELECT created, author, kind, text FROM briefs ORDER BY id DESC LIMIT ?",
            (BRIEF_LIMIT,)):
        subject = _SUBJECTS.get(str(kind), "Desk note")
        cards.append(FeedCard("result", str(author), subject, _when(created), str(text)))
    for created, text in _rows(
            home, "SELECT created, text FROM chat WHERE role = 'lead' ORDER BY id DESC LIMIT ?",
            (ANSWER_LIMIT,)):
        cards.append(FeedCard("answer", "Lead", "Answer", _when(created), str(text), ref="chat"))
    for started, kind, result, note in _rows(
            home, "SELECT started_at, kind, result, note FROM runs "
            "WHERE result NOT IN ('ok', 'running') ORDER BY id DESC LIMIT ?", (RUN_LIMIT,)):
        cards.append(FeedCard("desk", "Desk", f"Run {kind} {result}", _when(started),
                              str(note or "The run did not finish.")))
    for alert in open_alerts(home, now):
        cards.append(FeedCard("desk", "Desk", alert.title, alert.created,
                              f"{alert.text}\nWhat to do: {alert.fix}"))
    oldest = datetime.min.replace(tzinfo=now.tzinfo)
    return sorted(cards, key=lambda c: c.when or oldest, reverse=True)


def _closed_note(home: Path, pick: TradePick, now: datetime) -> str:
    state = pick_state(home, pick, now)
    if state == "waiting":
        return ""
    return "expired at the market open" if state == "expired" else "already decided"


def approve_pick(home: Path, pick: TradePick, sink: DeskTradeSink,
                 now: datetime) -> tuple[str, bool]:
    """Send ``pick`` to Execution and record the approval.

    Returns:
        ``(note, closed)``: ``("", True)`` when done; a note with ``closed`` True when the pick
        can no longer be decided, or with ``closed`` False when Execution refused it.
    """
    if note := _closed_note(home, pick, now):
        return note, True
    qty, why = sink.send_desk_pick(pick)
    if why:
        return why, False
    err = record_trade_decision(home, pick, "approve", qty, now)
    if err:
        sink.dismiss_desk_pick(pick)
        return err, True
    return "", True


def reject_pick(home: Path, pick: TradePick, now: datetime) -> tuple[str, bool]:
    """Record the rejection of ``pick``; returns ``(note, closed)`` like ``approve_pick``."""
    if note := _closed_note(home, pick, now):
        return note, True
    return record_trade_decision(home, pick, "reject", 0, now), True
