"""Tests for step D on the desk side: MD-DSK-003.021.M24 (core/desk_watch.py), check-in and
watch rules in MD-DSK-001.015.M03 (clock), MD-DSK-001.010.M04 (loop), MD-DSK-001.021.M07
(watch path), MD-DSK-003.004.M15 (event kinds) and MD-DSK-007.001.M21 (alerts)."""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from tests.desk.conftest import FakeClock
from us_swing.core.desk_alerts import open_alerts, raise_alert
from us_swing.core.desk_contract import StepContext
from us_swing.core.desk_events import post_event
from us_swing.core.desk_steps import load_watch
from us_swing.core.desk_watch import (
    OpenTrade,
    add_flag,
    desk_live_symbols,
    open_trades,
    write_open_trades,
)
from us_swing.desk.clock import checkins_due
from us_swing.desk.process import DeskProcess
from us_swing.desk.recorder import NY
from us_swing.market.store import MarketStore

THU = datetime(2026, 11, 12, 10, 1, tzinfo=NY)


def _rows(home: Path, sql: str, params: tuple[Any, ...] = ()) -> list[Any]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


class _Events:
    """An event handler with no work, so only the clock and the watchers act."""

    def has_work(self, home: Path) -> bool:
        return False

    def handle_events(self, ctx: StepContext) -> None:
        return None


def _desk(home: Path, clock: FakeClock, watch: Any = None) -> DeskProcess:
    """A started desk whose first tick already ran the day's morning run."""
    desk = DeskProcess(home, clock=clock, sleep=lambda _s: None, events=_Events(), watch=watch)
    assert desk.start()
    desk.tick()
    return desk


# ---------------- clock ----------------

def test_checkins_due() -> None:
    """UT-DSK-003.020.M03.T01: 10:01, 12:31 and 15:31 on a trading day give the three slots."""
    assert checkins_due(THU) == [("2026-11-12", 1000)]
    assert checkins_due(THU.replace(hour=12, minute=31)) == [("2026-11-12", 1230)]
    assert checkins_due(THU.replace(hour=15, minute=31)) == [("2026-11-12", 1530)]


def test_no_checkin() -> None:
    """UT-DSK-003.020.M03.T02: Saturday, and 10:31 on a trading day, give nothing."""
    assert checkins_due(datetime(2026, 11, 14, 10, 1, tzinfo=NY)) == []
    assert checkins_due(THU.replace(minute=31)) == []


def test_loop_posts_checkin_once(home: Path) -> None:
    """UT-DSK-003.020.M04.T01: Ticks at 10:01 and 10:05 post one check-in for slot 1000."""
    clock = FakeClock(THU)
    desk = _desk(home, clock)
    desk.tick()
    clock.now = THU.replace(minute=5)
    desk.tick()
    desk.close()
    assert _rows(home, "SELECT key FROM events WHERE kind = 'market_checkin'") == [
        ("market_checkin|2026-11-12|1000",)]


# ---------------- events ----------------

def test_event_rules(home: Path) -> None:
    """UT-DSK-003.021.M15.T01: Check-ins are P2 with 30 minutes; flags P0, 5 and 30 minutes."""
    post_event(home, "market_checkin", "2026-11-12", THU, 1000)
    post_event(home, "market_checkin", "2026-11-12", THU, 1230)
    post_event(home, "watch_flag", "2026-11-12", THU, 7)
    rows = _rows(home, "SELECT kind, priority, deadline, expires FROM events ORDER BY id")
    assert rows[0] == ("market_checkin", 2, None, "2026-11-12T10:31:00-05:00")
    assert len(rows) == 3
    assert rows[2] == ("watch_flag", 0, "2026-11-12T10:06:00-05:00", "2026-11-12T10:31:00-05:00")


# ---------------- flags ----------------

def test_flag_stored_with_event(home: Path) -> None:
    """UT-DSK-003.021.M24.T01: A flag is a row and a waiting watch_flag event with its id."""
    fid = add_flag(home, "trigger_hit", "AAA", "long trigger 50.00", 50.2, THU)
    assert _rows(home, "SELECT kind, symbol, hour FROM watch_flags") == [("trigger_hit", "AAA", 10)]
    assert _rows(home, "SELECT key, state FROM events") == [
        (f"watch_flag|2026-11-12|{fid}", "waiting")]


def test_once_an_hour(home: Path) -> None:
    """UT-DSK-003.022.M24.T01: The same stock and kind twice in one hour is stored once."""
    assert add_flag(home, "gap", "AAA", "gap", 51.0, THU) is not None
    assert add_flag(home, "gap", "AAA", "gap", 51.5, THU + timedelta(minutes=20)) is None
    assert _rows(home, "SELECT COUNT(*) FROM events") == [(1,)]


def test_next_hour(home: Path) -> None:
    """UT-DSK-003.022.M24.T02: An hour later the same stock and kind make a new flag."""
    add_flag(home, "volume_spike", "AAA", "4.0 times", 51.0, THU)
    assert add_flag(home, "volume_spike", "AAA", "5.0 times", 52.0, THU + timedelta(hours=1))


def test_unknown_flag_kind(home: Path) -> None:
    """UT-DSK-003.021.M24.T03: An unknown kind is refused; no row and no event."""
    with pytest.raises(ValueError):
        add_flag(home, "lunch", "AAA", "", 1.0, THU)
    assert not (home / "desk.db").exists() or _rows(
        home, "SELECT COUNT(*) FROM events") == [(0,)]


def test_code_feed_note(home: Path) -> None:
    """UT-DSK-003.024.M24.T01: Each flag adds a brief by Watchers with stock, label and price."""
    add_flag(home, "stop_touch", "AAA", "long stop 47.20", 47.1, THU)
    assert _rows(home, "SELECT author, kind, text, employee_id FROM briefs") == [
        ("Watchers", "info", "AAA: touched its stop at 47.10 — long stop 47.20", "")]


def test_no_note_for_repeat(home: Path) -> None:
    """UT-DSK-003.024.M24.T02: A repeat flag in the same hour adds no second note."""
    add_flag(home, "gap", "AAA", "gap", 51.0, THU)
    add_flag(home, "gap", "AAA", "gap", 51.0, THU + timedelta(minutes=5))
    assert _rows(home, "SELECT COUNT(*) FROM briefs") == [(1,)]


def test_open_trades_and_live_symbols(home: Path) -> None:
    """UT-DSK-003.021.M24.T02: Trades read back; live symbols are listed ideas, picks, SPY."""
    write_open_trades(home, [OpenTrade("AAA", "long", 50, 47, 56, "s1"),
                             OpenTrade("BBB", "short", 30, 32, None, "")], THU)
    assert [t.symbol for t in open_trades(home)] == ["AAA", "BBB"]
    assert open_trades(home)[1].target is None
    MarketStore(home).close()
    con = sqlite3.connect(home / "desk.db")
    with con:
        for sym, status, rank in (("IDA", "list", 1), ("IDB", "watch", 2), ("IDC", "list", 3)):
            con.execute("INSERT INTO ideas (date, side, symbol, status, rank) VALUES "
                        "('2026-11-11', 'long', ?, ?, ?)", (sym, status, rank))
        con.execute("INSERT INTO lead_picks VALUES ('2026-11-11', 'long', 'IDA', 1, 'r')")
        con.execute("INSERT INTO lead_picks VALUES ('2026-11-11', 'long', 'PIK', 2, 'r')")
    con.close()
    assert desk_live_symbols(home, "2026-11-12") == ["IDA", "IDC", "PIK", "SPY"]
    assert desk_live_symbols(home / "none", "2026-11-12") == ["SPY"]


# ---------------- watch loop ----------------

def test_watch_every_five_minutes(home: Path) -> None:
    """UT-DSK-003.023.M04.T01: Ticks at 10:00, 10:02 and 10:05 run the watchers twice."""
    calls: list[datetime] = []
    clock = FakeClock(THU.replace(minute=0))
    desk = _desk(home, clock, lambda h, now: calls.append(now) or 0)
    for minute in (0, 2, 5):
        clock.now = THU.replace(minute=minute)
        desk.tick()
    desk.close()
    assert [c.minute for c in calls] == [0, 5]


def test_watch_not_out_of_hours_or_paused(home: Path) -> None:
    """UT-DSK-003.023.M04.T02: At 08:00, and while paused at 11:00, nothing is watched."""
    from us_swing.core.desk_contract import CommandKind, send_command

    calls: list[datetime] = []
    clock = FakeClock(THU.replace(hour=8, minute=0))
    desk = _desk(home, clock, lambda h, now: calls.append(now) or 0)
    desk.tick()
    send_command(CommandKind.PAUSE, home)
    clock.now = THU.replace(hour=11, minute=0)
    desk.tick()
    desk.tick()
    desk.close()
    assert calls == []


def test_watch_error(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-003.023.M04.T03: A failing watcher pass is logged and the desk keeps going."""
    def broken(h: Path, now: datetime) -> int:
        raise RuntimeError("bars broke")

    clock = FakeClock(THU)
    desk = _desk(home, clock, broken)
    with caplog.at_level(logging.ERROR):
        assert desk.tick()
    desk.close()
    assert "[Watch] The market watchers failed" in caplog.text


def test_watch_path_loads() -> None:
    """UT-DSK-003.023.M07.T01: load_watch gives the market run_watch function."""
    from us_swing.market.watch import run_watch

    assert load_watch() is run_watch


# ---------------- alerts ----------------

def test_trade_and_plan_alerts(tmp_path: Path) -> None:
    """UT-DSK-007.009.M21.T01: The three kinds have their titles and stay open for the day."""
    sent: list[str] = []
    for kind in ("trade_stop", "trade_target", "plan_broken"):
        raise_alert(tmp_path, kind, "AAA", 0, "detail", THU, lambda t: sent.append(t) or True)
    assert [a.title for a in open_alerts(tmp_path, THU + timedelta(hours=1))] == [
        "Plan broken", "Trade at target", "Trade at stop"]
    assert len(sent) == 3


def test_trade_alert_once_a_day(tmp_path: Path) -> None:
    """UT-DSK-007.009.M21.T02: Two stop touches of one stock on one day give one alert."""
    send = lambda t: True  # noqa: E731
    assert raise_alert(tmp_path, "trade_stop", "AAA", 0, "x", THU, send) is not None
    assert raise_alert(tmp_path, "trade_stop", "AAA", 0, "y", THU, send) is None
