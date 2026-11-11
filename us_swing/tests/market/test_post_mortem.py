"""Tests for pick post-mortem research (FO-MKT-016, Autonomous desk step F skill 2)."""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from pydantic import ValidationError

from tests.desk.research_support import employee
from tests.market.p5b_support import FakeCtx
from us_swing.core.desk_lessons import connect as lessons_connect
from us_swing.core.desk_research import StepResult, Ticket, TicketAsk
from us_swing.core.desk_research import connect as tickets_connect
from us_swing.core.desk_steps import DEFAULT_EMPLOYEE_PACKAGES, SKILL_PATHS
from us_swing.data.market_calendar import ET
from us_swing.desk.registry import default_folders, load_employee
from us_swing.market.lesson_reflect import Candidate
from us_swing.market.post_mortem import (
    PickChoice,
    PickNote,
    PostMortem,
    PostMortemSkill,
)
from us_swing.market.post_mortem_facts import PickBars, path_line, pick_bars, pick_records
from us_swing.market.store import MarketStore

NOW = datetime(2026, 11, 11, 12, 0, tzinfo=ET)
L1, L2, L3, W1 = ("2026-11-02|long|AAA", "2026-11-03|long|BBB", "2026-11-04|long|CCC",
                  "2026-11-05|long|DDD")


def _pick(home: Path, key: str, r: float, setup: str = "Pullback") -> None:
    day, side, sym = key.split("|")
    con = sqlite3.connect(home / "desk.db")
    try:
        with con:
            con.execute("INSERT INTO pick_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (day, side, sym, "stop" if r < 0 else "target", day, 100.0, day,
                         99.0, r))
            con.execute("INSERT INTO ideas VALUES (?, ?, ?, 'list', 1, 72, 'Tech', ?, 100, 98)",
                        (day, side, sym, setup))
    finally:
        con.close()


@pytest.fixture
def home(tmp_path: Path) -> Path:
    MarketStore(tmp_path).close()
    lessons_connect(tmp_path).close()
    tickets_connect(tmp_path).close()
    for key, r in ((L1, -1.0), (L2, -1.0), (L3, -0.5), (W1, 2.0)):
        _pick(tmp_path, key, r)
    employee(tmp_path, "l-1", "Lead A", "lead", "fake_lead")
    return tmp_path


def _ticket(state: dict[str, Any] | None = None, raised_by: str = "l-1") -> Ticket:
    return Ticket(
        id=9, kind="post_mortem", topic="Last week losers", goal="Why did the losers fail",
        done_test="A common cause is found or ruled out", token_cap=8_000, step_cap=8,
        time_cap_min=60, raised_by=raised_by, raised_by_name="Lead A", status="running",
        made="2026-11-11T09:00:00-05:00", approved_by="auto", approved=None, started=None,
        ended=None, tokens=0, steps=0, biggest=0, quiet_steps=0, last_call="",
        state=json.dumps(state or {}), result="", end_reason="", gain=None, updated=None)


def _records(home: Path, keys: Any) -> list[str]:
    return [f"{k}: fake facts; path best +0.2R, worst -1.0R" for k in keys]


def _skill() -> PostMortemSkill:
    return PostMortemSkill(lambda: NOW, _records)


def _study_state() -> dict[str, Any]:
    return {"phase": "study", "losers": [L1, L2], "winners": [W1],
            "records": _records(Path(), [L1, L2, W1])}


def _answer(lessons: list[Candidate] | None = None,
            follow_ups: list[TicketAsk] | None = None) -> PostMortem:
    return PostMortem(notes=[PickNote(pick=L1, note="Gapped down at the open"),
                             PickNote(pick="2026-01-01|long|ZZZ", note="unknown pick")],
                      lessons=lessons or [], follow_ups=follow_ups or [],
                      summary="Both losers gapped down after weak news.")


def _lesson(picks: list[str]) -> Candidate:
    return Candidate(text="Pullback longs after a gap down fail more", tags={"setup": "Pullback"},
                     claim="worse", picks=picks)


def _ask(cap: int = 8_000) -> TicketAsk:
    return TicketAsk(kind="setup_tuning", topic="Pullback gap", goal="Test a tighter Pullback "
                     "limit after gaps", done_test="A variant beats baseline", token_cap=cap)


def _rows(home: Path, sql: str) -> list[Any]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def _run(ctx: FakeCtx, skill: PostMortemSkill) -> list[StepResult]:
    out: list[StepResult] = []
    state: dict[str, Any] = {}
    answers = [PickChoice(losers=[L1, L2], winners=[W1]), None,
               _answer([_lesson([L1, L2])], [_ask()])]
    for answer in answers:
        ctx.answer = answer
        res = skill.step(ctx, _ticket(state))
        assert res is not None
        out.append(res)
        state = res.state or state
    return out


# ---------------- steps ----------------

def test_three_steps(home: Path) -> None:
    """UT-MKT-016.001.M01.T01: Pick, gather and study end the ticket done."""
    steps = _run(FakeCtx(home, None), _skill())
    assert [s.call for s in steps] == ["pick", "gather", "study"]
    assert [s.outcome for s in steps] == ["go", "go", "done"]


def test_no_answer(home: Path) -> None:
    """UT-MKT-016.001.M01.T02: No pick answer gives an empty note and outcome go."""
    res = _skill().step(FakeCtx(home, None), _ticket())
    assert res is not None and res.note == "" and res.outcome == "go"


def test_pick_list_30_days(home: Path) -> None:
    """UT-MKT-016.002.M01.T01: Only picks of the last 30 days are shown."""
    old = (NOW.date() - timedelta(days=40)).isoformat() + "|long|OLD"
    _pick(home, old, -1.0)
    ctx = FakeCtx(home, None)
    _skill().step(ctx, _ticket())
    assert L1 in ctx.asked[0] and "OLD" not in ctx.asked[0]


def test_pick_list_size(home: Path) -> None:
    """UT-MKT-016.002.M01.T02: At most 120 picks are shown, newest first."""
    for i in range(150):
        day = (NOW.date() - timedelta(days=i % 25)).isoformat()
        _pick(home, f"{day}|short|S{i:03d}", -0.5)
    ctx = FakeCtx(home, None)
    _skill().step(ctx, _ticket())
    lines = [x for x in ctx.asked[0].splitlines() if x[:1].isdigit()]
    assert len(lines) == 120
    assert lines[0].startswith(NOW.date().isoformat())


def test_bad_keys_dropped(home: Path) -> None:
    """UT-MKT-016.003.M01.T01: Unknown keys and a winner named as loser are dropped."""
    ctx = FakeCtx(home, PickChoice(losers=[L1, L2, W1, "2026-11-01|long|ZZZ"], winners=[L3]))
    res = _skill().step(ctx, _ticket())
    assert res is not None and res.state["losers"] == [L1, L2]
    assert res.state["winners"] == []


def test_too_few_losers(home: Path) -> None:
    """UT-MKT-016.003.M01.T02: One valid loser ends the ticket failed."""
    ctx = FakeCtx(home, PickChoice(losers=[L1, W1]))
    res = _skill().step(ctx, _ticket())
    assert res is not None and res.outcome == "failed"


# ---------------- records and path ----------------

def _no_bars(symbols: Any) -> PickBars:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]))
    return PickBars(empty, empty, empty, empty)


def test_record_facts(home: Path) -> None:
    """UT-MKT-016.004.M02.T01: A record holds every stored fact of the pick."""
    day, side, sym = L1.split("|")
    con = sqlite3.connect(home / "desk.db")
    with con:
        con.execute("INSERT INTO idea_reasons VALUES (?, ?, ?, 1, 'Near the 21-day average')",
                    (day, side, sym))
        con.execute("INSERT INTO setup_review VALUES (?, ?, ?, 'B', 'Clean base')",
                    (day, side, sym))
        con.execute("INSERT INTO risk_check (date, side, symbol, verdict, reason) "
                    "VALUES (?, ?, ?, 'ok', '')", (day, side, sym))
        con.execute("INSERT INTO lead_picks VALUES (?, ?, ?, 1, 'Strong sector')",
                    (day, side, sym))
        con.execute("INSERT INTO news_tags (date, side, symbol, tone) VALUES (?, ?, ?, "
                    "'negative')", (day, side, sym))
        con.execute("INSERT INTO regime_snapshot (date, regime) VALUES (?, 'bull')", (day,))
    con.close()
    line = pick_records(home, [L1], _no_bars)[0]
    for part in ("Pullback, score 72", "trigger 100.00", "idea: Near the 21-day average",
                 "grade B (Clean base)", "risk ok", "lead: Strong sector", "tone negative",
                 "regime bull", "result stop -1.00R", "path: no bars"):
        assert part in line, part


def test_missing_tables(tmp_path: Path) -> None:
    """UT-MKT-016.004.M02.T02: Only pick_results present still gives a record."""
    con = sqlite3.connect(tmp_path / "desk.db")
    with con:
        con.execute("CREATE TABLE pick_results (date TEXT, side TEXT, symbol TEXT, status TEXT, "
                    "entry_day TEXT, entry REAL, exit_day TEXT, exit REAL, r REAL)")
        con.execute("INSERT INTO pick_results VALUES ('2026-11-02', 'long', 'AAA', 'stop', "
                    "'2026-11-03', 100, '2026-11-04', 98, -1.0)")
    con.close()
    line = pick_records(tmp_path, [L1], _no_bars)[0]
    assert "result stop -1.00R" in line and "path: no levels" in line


def _bars() -> PickBars:
    idx = pd.to_datetime(["2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05"])
    opens = pd.DataFrame({"AAA": [99, 100.5, 101, 100], "SPY": [500] * 4}, index=idx)
    highs = pd.DataFrame({"AAA": [100, 103, 101, 100], "SPY": [501] * 4}, index=idx)
    lows = pd.DataFrame({"AAA": [98, 99, 97, 99], "SPY": [499] * 4}, index=idx)
    closes = pd.DataFrame({"AAA": [99, 102, 98, 99], "SPY": [500, 502, 505, 510]}, index=idx)
    return PickBars(opens.astype(float), highs.astype(float), lows.astype(float),
                    closes.astype(float))


def test_price_path() -> None:
    """UT-MKT-016.005.M02.T01: Gap, best and worst R and SPY % over the hold."""
    line = path_line(_bars(), "long", "AAA", "2026-11-02", 100.0, 98.0, "2026-11-04")
    assert line == "path gap +0.5%, best +1.5R, worst -1.5R, SPY +1.0%"


def _write_bt(root: Path, sym: str, days: list[str], close: float) -> None:
    folder = root / "1d"
    folder.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"ts": pd.to_datetime(days), "open": close, "high": close + 1,
                  "low": close - 1, "close": close, "volume": 1e5}).to_parquet(
        folder / f"{sym}.parquet")


def _write_candles(path: Path, sym: str, days: list[str], close: float) -> None:
    con = sqlite3.connect(path)
    with con:
        con.execute("CREATE TABLE IF NOT EXISTS price_1d (symbol TEXT, datetime TEXT, "
                    "open REAL, high REAL, low REAL, close REAL, volume INTEGER)")
        for d in days:
            con.execute("INSERT INTO price_1d VALUES (?, ?, ?, ?, ?, ?, 1)",
                        (sym, d, close, close + 1, close - 1, close))
    con.close()


def test_backtest_data_first(tmp_path: Path) -> None:
    """UT-MKT-016.005.M02.T02: Backtest Data wins; candles.db fills only missing days."""
    root, candles = tmp_path / "bt", tmp_path / "candles.db"
    _write_bt(root, "AAA", ["2026-11-02", "2026-11-03"], 100.0)
    _write_candles(candles, "AAA", ["2026-11-03", "2026-11-04"], 50.0)
    bars = pick_bars(["AAA"], root, candles)
    closes = bars.closes["AAA"]
    assert closes[pd.Timestamp("2026-11-03")] == 100.0
    assert closes[pd.Timestamp("2026-11-04")] == 50.0


def test_no_bars(tmp_path: Path) -> None:
    """UT-MKT-016.005.M02.T03: A stock in neither store has no path."""
    bars = pick_bars(["AAA"], tmp_path / "none", tmp_path / "missing.db")
    assert path_line(bars, "long", "AAA", "2026-11-02", 100.0, 98.0, None) == "path: no bars"


# ---------------- study ----------------

def test_study_answer(home: Path) -> None:
    """UT-MKT-016.006.M01.T01: The result holds the summary and the studied pick notes."""
    res = _skill().step(FakeCtx(home, _answer()), _ticket(_study_state()))
    assert res is not None and res.outcome == "done"
    assert "Summary: Both losers gapped down" in res.note
    assert f"{L1}: Gapped down at the open" in res.note and "ZZZ" not in res.note


def test_answer_limits() -> None:
    """UT-MKT-016.006.M01.T02: Too many lessons, follow-ups or a long note are not valid."""
    with pytest.raises(ValidationError):
        PostMortem(lessons=[_lesson([L1])] * 4, summary="x" * 20)
    with pytest.raises(ValidationError):
        PostMortem(follow_ups=[_ask()] * 3, summary="x" * 20)
    with pytest.raises(ValidationError):
        PickNote(pick=L1, note="x" * 151)


def test_lesson_kept(home: Path) -> None:
    """UT-MKT-016.007.M01.T01: A lesson whose picks are all studied is a candidate."""
    _skill().step(FakeCtx(home, _answer([_lesson([L1, L2])])), _ticket(_study_state()))
    rows = _rows(home, "SELECT claim, status FROM lessons")
    assert rows == [("worse", "candidate")]


def test_lesson_dropped(home: Path) -> None:
    """UT-MKT-016.007.M01.T02: A lesson naming an unstudied pick is dropped."""
    _skill().step(FakeCtx(home, _answer([_lesson([L1, L3])])), _ticket(_study_state()))
    assert _rows(home, "SELECT COUNT(*) FROM lessons") == [(0,)]


def test_follow_up(home: Path) -> None:
    """UT-MKT-016.008.M01.T01: A follow-up is raised by the ticket's lead and auto approved."""
    again = TicketAsk(kind="post_mortem", topic="More losers", goal="Study the other losers",
                      done_test="A cause is found", token_cap=5_000)
    res = _skill().step(FakeCtx(home, _answer(follow_ups=[_ask(), again])),
                        _ticket(_study_state()))
    assert res is not None and "Follow-up: ticket" in res.note
    assert _rows(home, "SELECT kind, raised_by, status FROM tickets") == [
        ("setup_tuning", "l-1", "approved")]


def test_follow_up_refused(home: Path) -> None:
    """UT-MKT-016.008.M01.T02: A lead over its daily limit gets a refusal; ticket still done."""
    con = sqlite3.connect(home / "desk.db")
    with con:
        for i in range(3):
            con.execute("INSERT INTO tickets (kind, topic, goal, raised_by, status, made) "
                        "VALUES ('sentiment', ?, ?, 'l-1', 'done', ?)",
                        (f"t{i}", f"goal {i}", NOW.isoformat()))
    con.close()
    res = _skill().step(FakeCtx(home, _answer(follow_ups=[_ask()])), _ticket(_study_state()))
    assert res is not None and res.outcome == "done"
    assert "Follow-up: refused: 3 tickets a day" in res.note


def test_gain_yes(home: Path) -> None:
    """UT-MKT-016.009.M01.T01: A kept lesson makes the gain yes."""
    res = _skill().step(FakeCtx(home, _answer([_lesson([L1, L2])])), _ticket(_study_state()))
    assert res is not None and res.gain is True and "Lessons kept: 1" in res.note


def test_gain_no(home: Path) -> None:
    """UT-MKT-016.009.M01.T02: No kept lesson makes the gain no; still done."""
    res = _skill().step(FakeCtx(home, _answer()), _ticket(_study_state()))
    assert res is not None and res.gain is False and res.outcome == "done"


# ---------------- employee and logs ----------------

def test_default_employee() -> None:
    """UT-MKT-016.010.M01.T01: emp-014 ships with skill post_mortem and a loadable path."""
    folders = {f.name: f for f in default_folders(DEFAULT_EMPLOYEE_PACKAGES)}
    hire = load_employee(folders["emp-014"], SKILL_PATHS)
    assert hire is not None
    assert (hire.spec.level, hire.spec.skill, hire.spec.trigger) == (
        "expert", "post_mortem", ("research_done",))
    assert isinstance(hire.skill, PostMortemSkill)


def test_never_wakes(tmp_path: Path) -> None:
    """UT-MKT-016.010.M01.T02: Events never wake the post-mortem employee."""
    skill = _skill()
    facts = skill.facts(tmp_path)
    assert not facts.fresh and skill.act(FakeCtx(tmp_path, None), facts) == []


def test_logs(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-016.011.M01.T01: Steps log pick count, lessons kept and follow-ups raised."""
    caplog.set_level(logging.INFO, logger="us_swing.market.post_mortem")
    _run(FakeCtx(home, None), _skill())
    assert "[Research] Ticket 9 will study 2 loser(s) and 1 winner(s)" in caplog.text
    assert "[Research] Ticket 9 gathered 3 pick(s)" in caplog.text
    assert "[Research] Ticket 9 kept 1 lesson(s), raised 1 follow-up ticket(s)" in caplog.text
