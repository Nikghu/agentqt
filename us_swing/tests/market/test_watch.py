"""Tests for MD-MKT-013.001.M01 (market/watch.py), MD-MKT-013.008.M02 (watch_flag skill),
MD-MKT-013.010.M03 (checkin_note skill) and MD-MKT-013.011.M04 (default employees)."""
from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from tests.market.p5b_support import FakeCtx
from us_swing.core.desk_steps import DEFAULT_EMPLOYEE_PACKAGES, SKILL_PATHS
from us_swing.core.desk_watch import NY, OpenTrade, add_flag, write_open_trades
from us_swing.desk.registry import default_folders, load_employee
from us_swing.market import watch
from us_swing.market.checkin_note import CheckinNote, CheckinNoteSkill
from us_swing.market.news import Headline
from us_swing.market.store import MarketStore
from us_swing.market.watch import run_watch, today_bars
from us_swing.market.watch_flag import WatchFlagSkill, WatchVerdict

NOW = datetime(2026, 11, 12, 11, 0, tzinfo=NY)
DAY = "2026-11-12"


@pytest.fixture(autouse=True)
def _fresh_news() -> Iterator[None]:
    watch._last_news.clear()
    yield
    watch._last_news.clear()


@pytest.fixture
def home(tmp_path: Path) -> Path:
    path = tmp_path / "desk"
    MarketStore(path).close()
    return path


@pytest.fixture
def candles(tmp_path: Path) -> Path:
    path = tmp_path / "candles.db"
    con = sqlite3.connect(path)
    con.executescript(
        "CREATE TABLE price_3m (symbol TEXT, datetime TEXT, open REAL, high REAL, low REAL, "
        "close REAL, volume INTEGER, PRIMARY KEY (symbol, datetime));"
        "CREATE TABLE price_1d (symbol TEXT, datetime TEXT, open REAL, high REAL, low REAL, "
        "close REAL, volume INTEGER);")
    con.close()
    return path


def _bars(candles: Path, symbol: str, rows: list[tuple[float, float, float, float, float]],
          end: datetime = NOW, step: int = 3) -> None:
    """Bars (open, high, low, close, volume), the last one ending 3 minutes before ``end``."""
    con = sqlite3.connect(candles)
    with con:
        for i, (o, h, lo, c, v) in enumerate(rows):
            at = end - timedelta(minutes=step * (len(rows) - i))
            con.execute("INSERT INTO price_3m VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (symbol, at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S"), o, h, lo, c,
                         v))
    con.close()


def _daily(candles: Path, symbol: str, close: float) -> None:
    con = sqlite3.connect(candles)
    with con:
        con.execute("INSERT INTO price_1d VALUES (?, '2026-11-11', ?, ?, ?, ?, 1000)",
                    (symbol, close, close, close, close))
    con.close()


def _idea(home: Path, side: str, symbol: str, trigger: float, stop: float,
          pick: bool = False) -> None:
    con = sqlite3.connect(home / "desk.db")
    with con:
        con.execute("INSERT INTO ideas (date, side, symbol, status, rank, score, sector, setup, "
                    '"trigger", stop) VALUES (?, ?, ?, \'list\', 1, 50, \'Tech\', \'Breakout\', '
                    "?, ?)", (DAY, side, symbol, trigger, stop))
        if pick:
            con.execute("INSERT INTO lead_picks VALUES (?, ?, ?, 1, 'r')", (DAY, side, symbol))
    con.close()


def _flags(home: Path) -> list[tuple[str, str]]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute("SELECT kind, symbol FROM watch_flags ORDER BY id").fetchall()
    finally:
        con.close()


def _alerts(home: Path) -> list[str]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return [r[0] for r in con.execute("SELECT kind FROM alerts ORDER BY id")]
    finally:
        con.close()


def _run(home: Path, candles: Path, now: datetime = NOW, news: Any = None) -> int:
    return run_watch(home, now, candles, news or (lambda _s: []))


def _flat(n: int, price: float = 50.0, vol: float = 100) -> list[tuple[float, ...]]:
    return [(price, price + 0.1, price - 0.1, price, vol)] * n


# ---------------- bars ----------------

def test_today_bars(candles: Path) -> None:
    """UT-MKT-013.001.M01.T01: Only today's New York bars, oldest first, in New York time."""
    _bars(candles, "AAA", [(1, 1, 1, 1, 1)], end=NOW - timedelta(days=1))
    _bars(candles, "AAA", [(2, 2, 2, 2, 2), (3, 3, 3, 3, 3)])
    got = today_bars(candles, ["AAA"], NOW)["AAA"]
    assert [b.close for b in got] == [2, 3]
    assert got[-1].at == NOW - timedelta(minutes=3)


def test_stale_feed(home: Path, candles: Path) -> None:
    """UT-MKT-013.001.M01.T02: A newest bar 20 minutes old gives no flag."""
    _idea(home, "long", "AAA", 50.0, 47.0)
    _bars(candles, "AAA", [(50, 52, 49, 51, 100)], end=NOW - timedelta(minutes=17))
    assert _run(home, candles) == 0 and _flags(home) == []


# ---------------- trigger ----------------

def test_trigger_hit_long(home: Path, candles: Path) -> None:
    """UT-MKT-013.002.M01.T01: A long idea whose high reaches its trigger is flagged."""
    _idea(home, "long", "AAA", 50.0, 47.0)
    _bars(candles, "AAA", [(49.5, 49.8, 49.4, 49.7, 100), (49.7, 50.2, 49.6, 50.1, 100)])
    _run(home, candles)
    assert _flags(home) == [("trigger_hit", "AAA")]


def test_below_trigger(home: Path, candles: Path) -> None:
    """UT-MKT-013.002.M01.T02: A long idea below its trigger is not flagged."""
    _idea(home, "long", "AAA", 50.0, 47.0)
    _bars(candles, "AAA", [(49.5, 49.8, 49.4, 49.7, 100)])
    assert _run(home, candles) == 0


def test_short_trigger_once_a_day(home: Path, candles: Path) -> None:
    """UT-MKT-013.002.M01.T03: A short idea below its trigger is flagged once a day."""
    _idea(home, "short", "BBB", 30.0, 32.0)
    _bars(candles, "BBB", [(30.2, 30.3, 29.9, 30.0, 100)])
    _run(home, candles)
    _bars(candles, "BBB", [(30.0, 30.1, 29.8, 29.9, 100)], end=NOW + timedelta(hours=1))
    _run(home, candles, NOW + timedelta(hours=1))
    assert _flags(home) == [("trigger_hit", "BBB")]


# ---------------- trades ----------------

def test_stop_touch(home: Path, candles: Path) -> None:
    """UT-MKT-013.003.M01.T01: A long trade whose low reaches the stop: flag and alert."""
    write_open_trades(home, [OpenTrade("AAA", "long", 50, 47, 56, "s1")], NOW)
    _bars(candles, "AAA", [(47.5, 47.6, 46.9, 47.1, 100)])
    _run(home, candles)
    assert _flags(home) == [("stop_touch", "AAA")] and _alerts(home) == ["trade_stop"]


def test_short_target_touch(home: Path, candles: Path) -> None:
    """UT-MKT-013.003.M01.T02: A short trade whose low reaches the target: flag and alert."""
    write_open_trades(home, [OpenTrade("BBB", "short", 30, 32, 26, "s2")], NOW)
    _bars(candles, "BBB", [(26.4, 26.5, 25.9, 26.1, 100), (26.3, 26.6, 26.2, 26.5, 100)])
    _run(home, candles)
    _bars(candles, "BBB", [(26.0, 26.2, 25.8, 26.0, 100)], end=NOW + timedelta(hours=1))
    _run(home, candles, NOW + timedelta(hours=1))
    assert _flags(home) == [("target_touch", "BBB")] and _alerts(home) == ["trade_target"]


def test_inside_range(home: Path, candles: Path) -> None:
    """UT-MKT-013.003.M01.T03: A price between stop and target gives no flag."""
    write_open_trades(home, [OpenTrade("AAA", "long", 50, 47, 56, "s1")], NOW)
    _bars(candles, "AAA", [(50, 51, 49, 50.5, 100)])
    assert _run(home, candles) == 0


def test_no_stop_set(home: Path, candles: Path) -> None:
    """UT-MKT-013.003.M01.T04: A trade with stop 0 (none set) never gives a stop flag."""
    write_open_trades(home, [OpenTrade("SHT", "short", 30, 0.0, None, "s3")], NOW)
    _bars(candles, "SHT", [(30, 31, 29, 30.5, 100)])
    assert _run(home, candles) == 0


# ---------------- volume and gap ----------------

def test_volume_spike(home: Path, candles: Path) -> None:
    """UT-MKT-013.004.M01.T01: Last volume 4 times the 20-bar mean is flagged."""
    _idea(home, "long", "AAA", 60.0, 47.0)
    _bars(candles, "AAA", _flat(20) + [(50, 50.1, 49.9, 50, 400)], step=1)
    _run(home, candles)
    assert ("volume_spike", "AAA") in _flags(home)


def test_too_few_bars(home: Path, candles: Path) -> None:
    """UT-MKT-013.004.M01.T02: With 10 bars no volume flag is made."""
    _idea(home, "long", "AAA", 60.0, 47.0)
    _bars(candles, "AAA", _flat(9) + [(50, 50.1, 49.9, 50, 900)], step=1)
    _run(home, candles)
    assert ("volume_spike", "AAA") not in _flags(home)


def test_gap(home: Path, candles: Path) -> None:
    """UT-MKT-013.005.M01.T01: A first open 4% above the last close is flagged once."""
    _idea(home, "long", "AAA", 60.0, 47.0)
    _daily(candles, "AAA", 50.0)
    _bars(candles, "AAA", [(52.0, 52.1, 51.9, 52.0, 100)] * 30)  # 09:30 to 10:57
    _run(home, candles)
    _bars(candles, "AAA", [(52.0, 52.1, 51.9, 52.0, 100)], end=NOW + timedelta(hours=1, minutes=1))
    _run(home, candles, NOW + timedelta(hours=1, minutes=1))
    assert _flags(home).count(("gap", "AAA")) == 1
    con = sqlite3.connect(home / "desk.db")
    assert con.execute("SELECT detail FROM watch_flags").fetchone() == (
        "opened +4.0% from the last close",)
    con.close()


def test_gap_needs_open_bar(home: Path, candles: Path) -> None:
    """UT-MKT-013.005.M01.T03: Without the 09:30 bar (app started late) no gap is judged."""
    _idea(home, "long", "AAA", 60.0, 47.0)
    _daily(candles, "AAA", 50.0)
    _bars(candles, "AAA", [(52.0, 52.1, 51.9, 52.0, 100)] * 5)
    _run(home, candles)
    assert ("gap", "AAA") not in _flags(home)


def test_small_gap(home: Path, candles: Path) -> None:
    """UT-MKT-013.005.M01.T02: A first open 2% above gives no gap flag."""
    _idea(home, "long", "AAA", 60.0, 47.0)
    _daily(candles, "AAA", 50.0)
    _bars(candles, "AAA", [(51.0, 51.1, 50.9, 51.0, 100)])
    _run(home, candles)
    assert ("gap", "AAA") not in _flags(home)


# ---------------- SPY ----------------

def test_spy_move(home: Path, candles: Path) -> None:
    """UT-MKT-013.006.M01.T01: SPY 2% down is a regime_move flag."""
    _daily(candles, "SPY", 600.0)
    _bars(candles, "SPY", [(590, 590, 587, 588, 100)])
    _run(home, candles)
    assert _flags(home) == [("regime_move", "SPY")]


def test_spy_once_per_direction(home: Path, candles: Path) -> None:
    """UT-MKT-013.006.M01.T02: Down twice gives one flag; a later up move gives another."""
    _daily(candles, "SPY", 600.0)
    _bars(candles, "SPY", [(590, 590, 587, 588, 100)])
    _run(home, candles)
    later = NOW + timedelta(hours=1)
    _bars(candles, "SPY", [(589, 589, 586, 587, 100)], end=later)
    _run(home, candles, later)
    up = NOW + timedelta(hours=2)
    _bars(candles, "SPY", [(611, 612, 610, 611, 100)], end=up)
    _run(home, candles, up)
    assert _flags(home) == [("regime_move", "SPY"), ("regime_move", "SPY")]


def test_small_spy_move(home: Path, candles: Path) -> None:
    """UT-MKT-013.006.M01.T03: SPY 1% down gives no flag."""
    _daily(candles, "SPY", 600.0)
    _bars(candles, "SPY", [(594, 595, 593, 594, 100)])
    assert _run(home, candles) == 0


# ---------------- headlines ----------------

def _news(title: str, at: datetime) -> Any:
    calls: list[str] = []

    def fetch(symbol: str) -> list[Headline]:
        calls.append(symbol)
        return [Headline(symbol, "Yahoo Finance", at, title, "http://x")]

    fetch.calls = calls  # type: ignore[attr-defined]
    return fetch


def test_new_headline(home: Path, candles: Path) -> None:
    """UT-MKT-013.007.M01.T01: An unseen headline for a lead pick is flagged."""
    _idea(home, "long", "AAA", 60.0, 47.0, pick=True)
    _run(home, candles, news=_news("Alpha wins a big order", NOW - timedelta(minutes=20)))
    assert _flags(home) == [("headline", "AAA")]


def test_seen_or_old_headline(home: Path, candles: Path) -> None:
    """UT-MKT-013.007.M01.T02: A title already in news_items, or from before the open, is left."""
    _idea(home, "long", "AAA", 60.0, 47.0, pick=True)
    con = sqlite3.connect(home / "desk.db")
    with con:
        con.execute("INSERT INTO news_items (date, symbol, title) VALUES (?, 'AAA', 'Old news')",
                    (DAY,))
    con.close()
    _run(home, candles, news=_news("Old news", NOW - timedelta(minutes=20)))
    watch._last_news.clear()
    _run(home, candles, news=_news("Night story", NOW.replace(hour=7)))
    assert _flags(home) == []


def test_news_every_15_minutes(home: Path, candles: Path) -> None:
    """UT-MKT-013.007.M01.T03: Two passes 5 minutes apart fetch the news once."""
    _idea(home, "long", "AAA", 60.0, 47.0, pick=True)
    fetch = _news("Story", NOW - timedelta(minutes=20))
    _run(home, candles, news=fetch)
    _run(home, candles, NOW + timedelta(minutes=5), news=fetch)
    assert fetch.calls == ["AAA"]


def test_pass_log(home: Path, candles: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-003.025.M01.T01: A pass with 2 flags logs the count and the kinds."""
    _idea(home, "long", "AAA", 50.0, 47.0)
    _bars(candles, "AAA", [(50, 50.5, 49.9, 50.2, 100)])
    _daily(candles, "SPY", 600.0)
    _bars(candles, "SPY", [(590, 590, 587, 588, 100)])
    with caplog.at_level(logging.INFO):
        assert _run(home, candles) == 2
    assert "[Watch] 2 new flag(s): regime_move, trigger_hit" in caplog.text


# ---------------- flag skill ----------------

def _skill(candles: Path) -> WatchFlagSkill:
    return WatchFlagSkill(candles, lambda: NOW)


def test_flag_facts(home: Path, candles: Path) -> None:
    """UT-MKT-013.008.M02.T01: The facts hold the open flag, the plan and the bars."""
    _idea(home, "long", "AAA", 50.0, 47.0)
    _bars(candles, "AAA", [(49.7, 50.2, 49.6, 50.1, 100)])
    add_flag(home, "trigger_hit", "AAA", "long trigger 50.00", 50.1, NOW)
    facts = _skill(candles).facts(home)
    assert facts.fresh
    for part in ("AAA reached its trigger at 50.10", "Idea: long, trigger 50.0", "c 50.10"):
        assert part in facts.text


def test_no_open_flag(home: Path, candles: Path) -> None:
    """UT-MKT-013.008.M02.T02: With every flag answered the skill stays asleep."""
    fid = add_flag(home, "gap", "AAA", "gap", 52.0, NOW)
    from us_swing.core.desk_watch import answer_flag

    answer_flag(home, fid or 0, "holds", "Fine", NOW)
    assert not _skill(candles).facts(home).fresh


def test_no_answer_frees_queue(home: Path, candles: Path) -> None:
    """UT-MKT-013.009.M02.T04: A flag with no valid answer is closed so newer flags go next."""
    add_flag(home, "gap", "AAA", "gap", 52.0, NOW)
    add_flag(home, "gap", "BBB", "gap", 30.0, NOW)
    skill = _skill(candles)
    assert skill.act(FakeCtx(home, None), skill.facts(home)) == []
    assert "BBB" in skill.facts(home).text


def test_verdict_kept(home: Path, candles: Path) -> None:
    """UT-MKT-013.009.M02.T01: A verdict is kept on the flag and gives one feed item."""
    add_flag(home, "gap", "AAA", "gap", 52.0, NOW)
    skill = _skill(candles)
    items = skill.act(FakeCtx(home, WatchVerdict(verdict="holds", note="Gap fits the plan")),
                      skill.facts(home))
    con = sqlite3.connect(home / "desk.db")
    assert con.execute("SELECT verdict FROM watch_flags").fetchone() == ("holds",)
    con.close()
    assert [i.text for i in items] == ["AAA gap: holds — Gap fits the plan"]


def test_broken_plan(home: Path, candles: Path) -> None:
    """UT-MKT-013.009.M02.T02: A broken verdict raises the Plan broken alert."""
    add_flag(home, "headline", "AAA", "Alpha cuts guidance", 48.0, NOW)
    skill = _skill(candles)
    skill.act(FakeCtx(home, WatchVerdict(verdict="broken", note="Guidance cut ends the idea")),
              skill.facts(home))
    assert _alerts(home) == ["plan_broken"]


@pytest.mark.parametrize("bad", [{"verdict": "maybe", "note": "Not sure here"},
                                 {"verdict": "holds", "note": "x" * 301}])
def test_bad_verdict(bad: dict[str, str]) -> None:
    """UT-MKT-013.009.M02.T03: An unknown verdict or a note over 300 is refused."""
    with pytest.raises(ValidationError):
        WatchVerdict.model_validate(bad)


def test_answer_log(home: Path, candles: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-013.012.M02.T01: Each answer logs the stock, kind and verdict."""
    add_flag(home, "gap", "AAA", "gap", 52.0, NOW)
    skill = _skill(candles)
    with caplog.at_level(logging.INFO):
        skill.act(FakeCtx(home, WatchVerdict(verdict="watch", note="Gap may fade")),
                  skill.facts(home))
    assert "[Watch] AAA gap: watch" in caplog.text


# ---------------- check-in skill ----------------

def test_checkin_note(home: Path, candles: Path) -> None:
    """UT-MKT-013.010.M03.T01: Facts hold plan, trades, SPY and flags; the brief says Check-in."""
    _idea(home, "long", "AAA", 50.0, 47.0)
    write_open_trades(home, [OpenTrade("BBB", "long", 30, 28, 34, "s1")], NOW)
    _bars(candles, "AAA", [(49.5, 49.8, 49.4, 49.7, 100)])
    _bars(candles, "BBB", [(30.5, 30.8, 30.4, 30.6, 100)])
    _daily(candles, "SPY", 600.0)
    _bars(candles, "SPY", [(603, 604, 602, 603, 100)])
    add_flag(home, "gap", "AAA", "opened +3.5% from the last close", 51.0,
             NOW - timedelta(minutes=30))
    skill = CheckinNoteSkill(candles, lambda: NOW)
    facts = skill.facts(home)
    for part in ("AAA long: last 49.70, trigger 50.00", "BBB long: last 30.60, stop 28.00",
                 "SPY +0.5% from the last close", "AAA gap: opened +3.5%"):
        assert part in facts.text, part
    items = skill.act(FakeCtx(home, CheckinNote(note="Quiet morning; AAA is near its trigger.")),
                      facts)
    assert items[0].text.startswith("Check-in 10:00: Quiet morning")


def test_checkin_not_trading_day(home: Path, candles: Path) -> None:
    """UT-MKT-013.010.M03.T02: On a Saturday the check-in skill stays asleep."""
    sat = datetime(2026, 11, 14, 10, 1, tzinfo=NY)
    assert not CheckinNoteSkill(candles, lambda: sat).facts(home).fresh


# ---------------- defaults ----------------

def _folders() -> dict[str, Path]:
    return {f.name: f for f in default_folders(DEFAULT_EMPLOYEE_PACKAGES)}


def test_default_employees() -> None:
    """UT-MKT-013.011.M04.T01: emp-011 is the watcher expert; emp-012 the market lead."""
    watcher = load_employee(_folders()["emp-011"], SKILL_PATHS)
    lead = load_employee(_folders()["emp-012"], SKILL_PATHS)
    assert watcher is not None and lead is not None
    assert (watcher.spec.level, watcher.spec.skill, watcher.spec.trigger) == (
        "expert", "watch_flag", ("watch_flag",))
    assert (lead.spec.level, lead.spec.skill, lead.spec.trigger) == (
        "lead", "checkin_note", ("market_checkin",))


def test_unknown_skill_guard() -> None:
    """UT-MKT-013.011.M04.T02: Without the two skill paths both employees sleep."""
    paths = {k: v for k, v in SKILL_PATHS.items() if k not in ("watch_flag", "checkin_note")}
    assert load_employee(_folders()["emp-011"], paths) is None
    assert load_employee(_folders()["emp-012"], paths) is None
