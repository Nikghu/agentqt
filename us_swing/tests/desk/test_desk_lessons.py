"""Tests for MD-DSK-009.001.M23 — core/desk_lessons.py (and the desk tick, MD-DSK-001.010.M04)."""
from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from tests.desk.conftest import FakeClock
from us_swing.core import desk_lessons
from us_swing.core.desk_lessons import (
    add_candidate,
    add_edit,
    apply_edits,
    connect,
    lessons_block,
    review_lessons,
)
from us_swing.desk.process import DeskProcess
from us_swing.desk.recorder import NY
from us_swing.market.store import MarketStore

NOW = datetime(2026, 11, 11, 9, 0, tzinfo=NY)
DAY = "2026-11-11"
PULL = {"setup": "pullback"}


def _rows(home: Path, sql: str, params: tuple[Any, ...] = ()) -> list[Any]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def _pick(home: Path, day: str, symbol: str, r: float, setup: str = "pullback",
          side: str = "long", sector: str = "Tech", status: str = "stop") -> str:
    """Add one closed lead pick with its idea; return its key."""
    MarketStore(home).close()
    con = sqlite3.connect(home / "desk.db")
    try:
        with con:
            con.execute("INSERT INTO ideas (date, side, symbol, status, rank, score, sector, "
                        "setup, \"trigger\", stop) VALUES (?, ?, ?, 'list', 1, 50, ?, ?, 50, 47)",
                        (day, side, symbol, sector, setup))
            con.execute("INSERT INTO pick_results VALUES (?, ?, ?, ?, ?, 50, ?, 50, ?)",
                        (day, side, symbol, status, day, day, r))
    finally:
        con.close()
    return f"{day}|{side}|{symbol}"


def _base(home: Path, bad: int = 5, good: int = 5) -> list[str]:
    """``bad`` pullback picks at -1R and ``good`` breakout picks at +2R in early October."""
    keys = [_pick(home, f"2026-10-0{1 + i % 5}", f"P{i}", -1.0) for i in range(bad)]
    keys += [_pick(home, f"2026-10-0{1 + i % 5}", f"B{i}", 2.0, setup="breakout")
             for i in range(good)]
    return keys


def _status(home: Path, lid: int) -> str:
    return str(_rows(home, "SELECT status FROM lessons WHERE id = ?", (lid,))[0][0])


def _active(home: Path, text: str, tags: dict[str, str], confidence: float = 0.5,
            pinned: bool = False, on: str = "2026-10-06T09:00:00-04:00",
            confirmed: str | None = None) -> int:
    """Store one active lesson directly (test data factory)."""
    con = connect(home)
    try:
        with con:
            cur = con.execute(
                "INSERT INTO lessons (text, tags, claim, proof, cases, avg_r, confidence, status,"
                " made, active_on, last_confirmed, pinned, author, why) VALUES (?, ?, 'worse', "
                "'[]', 5, -1, ?, 'active', ?, ?, ?, ?, 'desk', '')",
                (text, json.dumps(tags, sort_keys=True), confidence, on, on, confirmed or on,
                 int(pinned)))
        return int(cur.lastrowid or 0)
    finally:
        con.close()


def _ideas(home: Path, day: str = DAY, side: str = "long", setup: str = "pullback") -> None:
    MarketStore(home).close()
    con = sqlite3.connect(home / "desk.db")
    try:
        with con:
            con.execute("INSERT INTO ideas (date, side, symbol, status, rank, score, sector, "
                        "setup, \"trigger\", stop) VALUES (?, ?, 'IDEA', 'list', 1, 50, 'Tech', "
                        "?, 50, 47)", (day, side, setup))
    finally:
        con.close()


# ---------------- store ----------------

def test_lesson_stored(home: Path) -> None:
    """UT-DSK-009.001.M23.T01: A candidate is stored with tags, claim, proof and author desk."""
    keys = _base(home, bad=2)
    lid = add_candidate(home, "Pullbacks fail", PULL, "worse", keys[:2], NOW)
    rows = _rows(home, "SELECT text, tags, claim, proof, cases, status, author FROM lessons")
    assert rows == [("Pullbacks fail", '{"setup": "pullback"}', "worse", json.dumps(keys[:2]),
                     2, "candidate", "desk")]
    assert lid == 1


@pytest.mark.parametrize("tags, claim", [
    (PULL, "maybe"),
    ({"side": "long", "setup": "a", "sector": "b", "tone": "c"}, "worse"),
    ({"mood": "x"}, "worse"),
])
def test_bad_lesson(home: Path, tags: dict[str, str], claim: str) -> None:
    """UT-DSK-009.001.M23.T02: A bad claim, 4 tags or an unknown tag key is refused."""
    connect(home).close()
    with pytest.raises(ValueError):
        add_candidate(home, "Some lesson", tags, claim, [], NOW)
    assert _rows(home, "SELECT COUNT(*) FROM lessons") == [(0,)]


# ---------------- active at 5 cases ----------------

def test_active_at_five_cases(home: Path) -> None:
    """UT-DSK-009.002.M23.T01: A worse claim backed by 5 picks below the average is active."""
    keys = _base(home)
    lid = add_candidate(home, "Pullbacks fail", PULL, "worse", keys[:5], NOW)
    assert _status(home, lid) == "active"
    assert _rows(home, "SELECT active_on FROM lessons") == [(NOW.isoformat(),)]


def test_too_few_cases(home: Path) -> None:
    """UT-DSK-009.002.M23.T02: With 3 matching picks the lesson stays a candidate."""
    keys = _base(home, bad=3)
    assert _status(home, add_candidate(home, "Pullbacks fail", PULL, "worse", keys, NOW)) == (
        "candidate")


def test_cases_do_not_back_it(home: Path) -> None:
    """UT-DSK-009.002.M23.T03: A worse claim whose picks are above the average stays candidate."""
    keys = _base(home)
    lid = add_candidate(home, "Breakouts fail", {"setup": "breakout"}, "worse", keys, NOW)
    assert _status(home, lid) == "candidate"


def test_unproved_for_30_days(home: Path) -> None:
    """UT-DSK-009.002.M23.T04: A candidate made 31 days ago is retired by the review."""
    lid = add_candidate(home, "Pullbacks fail", PULL, "worse", [], NOW - timedelta(days=31))
    review_lessons(home, NOW)
    assert _rows(home, "SELECT status, why FROM lessons WHERE id = ?", (lid,)) == [
        ("retired", "not proved in 30 days")]


# ---------------- same lesson ----------------

def test_same_lesson_updated(home: Path) -> None:
    """UT-DSK-009.003.M23.T01: The same tags and claim update one row with the newer text."""
    add_candidate(home, "Pullbacks fail", PULL, "worse", [], NOW)
    add_candidate(home, "Pullback longs lose", PULL, "worse", [], NOW)
    assert _rows(home, "SELECT text FROM lessons") == [("Pullback longs lose",)]


def test_other_claim_is_new(home: Path) -> None:
    """UT-DSK-009.003.M23.T02: The same tags with the other claim add a second row."""
    add_candidate(home, "Pullbacks fail", PULL, "worse", [], NOW)
    add_candidate(home, "Pullbacks win", PULL, "better", [], NOW)
    assert _rows(home, "SELECT COUNT(*) FROM lessons") == [(2,)]


def test_retired_not_revived(home: Path) -> None:
    """UT-DSK-009.003.M23.T03: A candidate like a retired lesson is a new row; old one stays."""
    old = add_candidate(home, "Pullbacks fail", PULL, "worse", [], NOW)
    add_edit(home, old, "retire", NOW)
    apply_edits(home, NOW)
    new = add_candidate(home, "Pullbacks fail again", PULL, "worse", [], NOW)
    assert new != old and _status(home, old) == "retired"


# ---------------- lessons block ----------------

def test_top_five_pinned_first(home: Path) -> None:
    """UT-DSK-009.004.M23.T01: 7 matching lessons give 5 lines, pinned first, then confidence."""
    _ideas(home)
    tag_sets = [{"side": "long"}, PULL, {"sector": "Tech"}, {"side": "long", "setup": "pullback"},
                {"side": "long", "sector": "Tech"}, {"setup": "pullback", "sector": "Tech"},
                {"side": "long", "grade": "A"}]
    ids = [_active(home, f"Lesson {i}", t, confidence=0.5 + i / 20)
           for i, t in enumerate(tag_sets)]
    pinned = _active(home, "Pinned one", {"regime": "Uptrend", "side": "long"}, 0.1, True)
    con = connect(home)
    with con:
        con.execute("INSERT INTO regime_snapshot (date, regime) VALUES (?, 'Uptrend')", (DAY,))
    con.close()
    lines = lessons_block(home, "setup_review", DAY).splitlines()
    assert lines[0] == desk_lessons.HEADER and len(lines) == 6
    shown = [int(re.match(r"- L-(\d+):", x).group(1)) for x in lines[1:]]  # type: ignore[union-attr]
    assert shown == [pinned, ids[6], ids[5], ids[4], ids[3]]


def test_nothing_to_show(home: Path) -> None:
    """UT-DSK-009.004.M23.T02: Only candidates, or no matching idea, give an empty block."""
    _ideas(home)
    add_candidate(home, "Pullbacks fail", PULL, "worse", [], NOW)
    assert lessons_block(home, "setup_review", DAY) == ""
    _active(home, "Shorts fail", {"side": "short"})
    assert lessons_block(home, "setup_review", DAY) == ""


def test_token_cap(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-DSK-009.004.M23.T03: The block never passes the character cap."""
    _ideas(home)
    for i, tags in enumerate(({"side": "long"}, PULL, {"sector": "Tech"})):
        _active(home, f"{i} " + "x" * 190, tags)
    assert len(lessons_block(home, "s", DAY)) <= desk_lessons.MAX_CHARS
    monkeypatch.setattr(desk_lessons, "MAX_CHARS", 450)
    block = lessons_block(home, "s2", DAY)
    assert len(block) <= 450 and len(block.splitlines()) == 2


# ---------------- prompt text only ----------------

def test_limits_never_read_lessons() -> None:
    """UT-DSK-009.005.M23.T01: Execution, broker, trade and limit code never import lessons."""
    src = Path(__file__).resolve().parents[2] / "src" / "us_swing"
    files = [*(src / "execution").rglob("*.py"), *(src / "broker").rglob("*.py"),
             src / "core" / "desk_trades.py", src / "market" / "idea_step.py",
             src / "market" / "risk_limits.py"]
    found = [str(p.relative_to(src)) for p in files
             if "desk_lessons" in p.read_text(encoding="utf-8")]
    assert files and found == []


# ---------------- uses ----------------

def test_uses_kept(home: Path) -> None:
    """UT-DSK-009.006.M23.T01: Two lessons shown to setup review give two uses for that day."""
    _ideas(home)
    a, b = _active(home, "One", {"side": "long"}), _active(home, "Two", PULL)
    lessons_block(home, "setup_review", DAY)
    assert sorted(_rows(home, "SELECT day, skill, lesson_id FROM lesson_uses")) == [
        (DAY, "setup_review", a), (DAY, "setup_review", b)]


def test_no_uses_when_nothing_shown(home: Path) -> None:
    """UT-DSK-009.006.M23.T02: A block with no matching lesson writes no uses."""
    _ideas(home)
    _active(home, "Shorts fail", {"side": "short"})
    lessons_block(home, "setup_review", DAY)
    assert _rows(home, "SELECT COUNT(*) FROM lesson_uses") == [(0,)]


# ---------------- retire ----------------

def _shown(home: Path, lid: int, days: list[str]) -> None:
    con = connect(home)
    with con:
        con.executemany("INSERT OR IGNORE INTO lesson_uses VALUES (?, 'setup_review', ?)",
                        [(d, lid) for d in days])
    con.close()


def test_later_picks_do_not_back_it(home: Path) -> None:
    """UT-DSK-009.007.M23.T01: 10 later shown picks above the average retire a worse lesson."""
    _base(home)
    lid = _active(home, "Pullbacks fail", PULL)
    days = [f"2026-10-{10 + i}" for i in range(10)]
    for i, d in enumerate(days):
        _pick(home, d, f"L{i}", 3.0)
    _shown(home, lid, days)
    review_lessons(home, NOW)
    assert _rows(home, "SELECT status, why FROM lessons") == [
        ("retired", "later picks do not back it")]


def test_confirmed(home: Path) -> None:
    """UT-DSK-009.007.M23.T02: A later shown pick on the claimed side moves last confirmed."""
    _base(home)
    lid = _active(home, "Pullbacks fail", PULL)
    _pick(home, "2026-10-10", "L1", -2.0)
    _shown(home, lid, ["2026-10-10"])
    review_lessons(home, NOW)
    assert _rows(home, "SELECT status, last_confirmed FROM lessons") == [
        ("active", NOW.isoformat())]


def test_ninety_days_and_pinned(home: Path) -> None:
    """UT-DSK-009.007.M23.T03: Not confirmed for 91 days: unpinned retires, pinned stays."""
    old = (NOW - timedelta(days=91)).isoformat()
    loose = _active(home, "Loose", PULL, on=old)
    kept = _active(home, "Kept", {"side": "long"}, pinned=True, on=old)
    review_lessons(home, NOW)
    assert _status(home, loose) == "retired" and _status(home, kept) == "active"


# ---------------- Master edits ----------------

def test_edits_applied(home: Path) -> None:
    """UT-DSK-009.008.M23.T01: Pin, edit, retire and delete are applied; edit keeps id."""
    a, b, c = (_active(home, n, {"side": s}) for n, s in (("A", "long"), ("B", "short"),
                                                           ("C", "long")))
    add_edit(home, a, "pin", NOW)
    add_edit(home, a, "edit", NOW, "Better words")
    add_edit(home, b, "retire", NOW)
    add_edit(home, c, "delete", NOW)
    assert apply_edits(home, NOW) == 4
    assert _rows(home, "SELECT id, text, pinned, author, cases FROM lessons WHERE id = ?",
                 (a,)) == [(a, "Better words", 1, "master", 5)]
    assert _status(home, b) == "retired"
    assert _rows(home, "SELECT COUNT(*) FROM lessons WHERE id = ?", (c,)) == [(0,)]
    assert _rows(home, "SELECT COUNT(*) FROM lesson_edits WHERE applied IS NULL") == [(0,)]


def test_unknown_lesson(home: Path) -> None:
    """UT-DSK-009.008.M23.T02: An edit for a missing lesson is closed with a note."""
    add_edit(home, 99, "pin", NOW)
    apply_edits(home, NOW)
    assert _rows(home, "SELECT note FROM lesson_edits") == [("lesson not found",)]


def test_tick_applies_edits(home: Path, clock: FakeClock) -> None:
    """UT-DSK-009.008.M04.T01: One desk tick applies a pending pin."""
    lid = _active(home, "Pullbacks fail", PULL)
    add_edit(home, lid, "pin", NOW)
    desk = DeskProcess(home, clock=clock, sleep=lambda _s: None, steps=[])
    assert desk.start()
    desk.tick()
    desk.close()
    assert _rows(home, "SELECT pinned FROM lessons") == [(1,)]


# ---------------- log lines ----------------

def test_log_lines(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-009.009.M23.T01: Adding, making active and retiring are logged under Memory."""
    keys = _base(home)
    with caplog.at_level(logging.INFO):
        lid = add_candidate(home, "Pullbacks fail", PULL, "worse", keys[:5], NOW)
        add_edit(home, lid, "retire", NOW)
        apply_edits(home, NOW)
    assert f"[Memory] New candidate lesson L-{lid}" in caplog.text
    assert f"[Memory] Lesson L-{lid} is active (5 cases)" in caplog.text
    assert f"[Memory] Lesson L-{lid} retired" in caplog.text


# ---------------- after code review ----------------

def test_master_text_kept(home: Path) -> None:
    """UT-DSK-009.003.M23.T04: A new candidate never replaces the Master's or a pinned text."""
    lid = add_candidate(home, "Pullbacks fail", PULL, "worse", [], NOW)
    add_edit(home, lid, "edit", NOW, "My own words")
    apply_edits(home, NOW)
    add_candidate(home, "Desk words", PULL, "worse", [], NOW)
    assert _rows(home, "SELECT text FROM lessons") == [("My own words",)]


def test_recently_retired_not_active(home: Path) -> None:
    """UT-DSK-009.003.M23.T05: Like a lesson retired in the last 90 days, it stays candidate."""
    keys = _base(home)
    old = add_candidate(home, "Pullbacks fail", PULL, "worse", keys[:5], NOW)
    add_edit(home, old, "retire", NOW)
    apply_edits(home, NOW)
    new = add_candidate(home, "Pullbacks fail again", PULL, "worse", keys[:5], NOW)
    assert _status(home, new) == "candidate"


def test_memory_error_plain_text(home: Path, monkeypatch: pytest.MonkeyPatch,
                                 caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-009.004.M23.T04: A memory error gives the plain facts and a warning."""
    def broken(*_a: object) -> str:
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(desk_lessons, "lessons_block", broken)
    with caplog.at_level(logging.WARNING):
        assert desk_lessons.with_lessons("facts", home, "setup_review", DAY) == "facts"
    assert "[Memory] Could not read the lessons" in caplog.text
