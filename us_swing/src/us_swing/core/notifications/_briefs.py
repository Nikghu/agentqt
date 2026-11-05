"""
Module: MD-INF-012.002.M01 — Daily Brief Timing
Parent SRD: SRD-INF-012.002

When the Morning brief and the Day-end report are due, a per-user log of the day each
was last sent (so a restart never sends twice), and the AI facts text with its number
check (SRD-INF-012.004).
"""
from __future__ import annotations

import datetime
import json
import logging
import re
from pathlib import Path

from us_swing.core.notifications._events import MorningBriefEvent
from us_swing.data.market_calendar import ET, get_exchange_status

_log = logging.getLogger(__name__)

MORNING_BRIEF = "morning_brief"
DAY_END = "day_end"
DAY_END_FROM = datetime.time(16, 5)
SEND_LOG_PATH = Path.home() / ".usswing" / "notify_state.json"
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def brief_due(now_et: datetime.datetime, last_sent: datetime.date | None) -> bool:
    """True in pre-market on a trading day when today's brief is not sent yet."""
    return get_exchange_status(now_et) == "pre_market" and last_sent != now_et.date()


def day_end_due(now_et: datetime.datetime, last_sent: datetime.date | None) -> bool:
    """True from 16:05 ET until midnight ET on a trading day when not sent yet."""
    return (
        is_trading_day(now_et.date())
        and now_et.time() >= DAY_END_FROM
        and last_sent != now_et.date()
    )


def is_trading_day(day: datetime.date) -> bool:
    """True when the US market opens on ``day`` (not a weekend or NYSE holiday)."""
    noon = datetime.datetime.combine(day, datetime.time(12, 0), tzinfo=ET)
    return get_exchange_status(noon) == "open"


class SendLog:
    """The day each daily message was last sent, per user, kept in one JSON file."""

    def __init__(self, path: Path | None = None) -> None:
        self._given = path

    @property
    def _path(self) -> Path:
        return self._given or SEND_LOG_PATH

    def last_sent(self, user_id: int, kind: str) -> datetime.date | None:
        """The last sent day of ``kind`` for ``user_id``, or None."""
        value = self._read().get(str(user_id), {}).get(kind)
        try:
            return datetime.date.fromisoformat(value) if value else None
        except (TypeError, ValueError):
            return None

    def mark(self, user_id: int, kind: str, day: datetime.date) -> None:
        """Record that ``kind`` was sent to ``user_id`` on ``day``."""
        data = self._read()
        data.setdefault(str(user_id), {})[kind] = day.isoformat()
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError as exc:
            _log.warning("[Notify] Could not save the daily message log: %s", exc)

    def _read(self) -> dict[str, dict[str, str]]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}


def brief_facts(event: MorningBriefEvent) -> str:
    """Plain facts of the brief for the AI comment."""
    lines = [f"Date: {event.session_date}"]
    for quote in (*event.quotes, *([event.vix] if event.vix else [])):
        lines.append(f"{quote.symbol}: {quote.last:.2f}, {quote.change_pct:+.2f}% vs previous close")
    lines.append(f"Open trades: {event.open_count}, unrealized P&L {event.unrealized:+.0f} USD")
    lines += [f"Open trade {t.symbol}: {t.pnl:+.0f} USD" for t in event.open_trades]
    lines.append(f"Waiting signals: {', '.join(event.signals) or 'none'}")
    lines.append(f"Last screener stocks: {', '.join(event.screener_top) or 'none'}")
    return "\n".join(lines)


def numbers_ok(comment: str, facts: str) -> bool:
    """True when every number in ``comment`` also appears in ``facts``."""
    known = {_plain(n) for n in _NUMBER.findall(facts)}
    return all(_plain(n) in known for n in _NUMBER.findall(comment))


def _plain(number: str) -> str:
    return number.replace(",", "")
