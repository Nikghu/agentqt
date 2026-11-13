"""Tests for MD-DSK-009.010.M30 (core/desk_memory.py) and the M3 changes in M23
(core/desk_lessons.py), M27 (core/desk_msg.py), M13 (settings) and M04 (desk tick).

Employee ids here are made up: code must never depend on them.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from us_swing.core import desk_lessons, desk_memory
from us_swing.core.desk_ai_settings import DeskAiSettings
from us_swing.core.desk_memory import (
    CORE_CHARS,
    RECALL_CHARS,
    CleanupAction,
    add_edit,
    apply_cleanup,
    apply_edits,
    core_block,
    open_views_due,
    recall,
    review,
    score_view,
    write,
)
from us_swing.core.desk_msg import Remember, with_remember
from us_swing.desk.process import DeskProcess
from us_swing.desk.recorder import NY
from us_swing.market.store import MarketStore

NOW = datetime(2026, 11, 6, 9, 0, tzinfo=NY)
DAY = "2026-11-06"
OWNER = "emp-x"


def _note(text: str, symbol: str | None = None) -> Remember:
    return Remember(kind="note", text=text, symbol=symbol)


def _view(symbol: str, direction: str, text: str = "my call") -> Remember:
    return Remember(kind="view", text=text, symbol=symbol, direction=direction)  # type: ignore[arg-type]


def _rows(home: Path, sql: str, params: tuple[Any, ...] = ()) -> list[Any]:
    con = desk_memory.connect(home)
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def _set(home: Path, mid: int, **values: Any) -> None:
    con = desk_memory.connect(home)
    try:
        with con:
            for key, value in values.items():
                con.execute(f"UPDATE memories SET {key} = ? WHERE id = ?", (value, mid))
    finally:
        con.close()


def _ids(home: Path, kind: str = "note") -> list[int]:
    return [r[0] for r in _rows(home, "SELECT id FROM memories WHERE kind = ? ORDER BY id",
                                (kind,))]


# ---------------- file (SRD-DSK-009.010) ----------------

def test_file_made(home: Path) -> None:
    """UT-DSK-009.010.M30.T01: connect makes memory.db in WAL mode with desk.db attached."""
    con = desk_memory.connect(home)
    try:
        mode = con.execute("PRAGMA journal_mode").fetchone()[0]
        names = [r[1] for r in con.execute("PRAGMA database_list")]
    finally:
        con.close()
    assert (home / "memory.db").exists() and mode == "wal" and "desk" in names


def test_read_only_no_file(home: Path) -> None:
    """UT-DSK-009.010.M30.T02: read_only on an empty folder gives None and makes no file."""
    home.mkdir(parents=True)
    assert desk_memory.read_only(home) is None
    assert not (home / "memory.db").exists()


# ---------------- lesson move (SRD-DSK-009.011) ----------------

def _old_lessons(home: Path) -> None:
    """Lesson tables in desk.db as the M2 code left them."""
    home.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(home / "desk.db")
    try:
        con.executescript(desk_lessons.SCHEMA)
        with con:
            for lid, text in ((1, "Pullbacks fail"), (2, "Breakouts work")):
                con.execute("INSERT INTO lessons (id, text, tags, claim, proof, cases, avg_r, "
                            "confidence, status, made, active_on, pinned, author, why) VALUES "
                            "(?, ?, '{\"setup\": \"pullback\"}', 'worse', '[]', 5, -1.0, 0.8, "
                            "'active', '2026-10-01T09:00:00', '2026-10-02T09:00:00', 0, "
                            "'desk', '')", (lid, text))
            con.execute("INSERT INTO lesson_uses VALUES ('2026-10-03', 'setup_review', 1)")
            con.execute("INSERT INTO lesson_edits (lesson_id, action, text, created) "
                        "VALUES (2, 'pin', '', '2026-10-04T09:00:00')")
            con.execute("INSERT INTO memory_state VALUES ('reflected_keys', '[]')")
    finally:
        con.close()


def test_lessons_move(home: Path) -> None:
    """UT-DSK-009.011.M30.T01: The lesson rows move to memory.db with their ids."""
    _old_lessons(home)
    con = desk_lessons.connect(home)
    try:
        lessons = con.execute("SELECT id, text FROM main.lessons ORDER BY id").fetchall()
        uses = con.execute("SELECT * FROM main.lesson_uses").fetchall()
        edits = con.execute("SELECT lesson_id, action FROM main.lesson_edits").fetchall()
        moved = desk_lessons.get_state(con, "lessons_moved")
    finally:
        con.close()
    assert lessons == [(1, "Pullbacks fail"), (2, "Breakouts work")]
    assert uses == [("2026-10-03", "setup_review", 1)] and edits == [(2, "pin")]
    assert moved


def test_move_once(home: Path) -> None:
    """UT-DSK-009.011.M30.T02: A second connect copies nothing more."""
    _old_lessons(home)
    desk_lessons.connect(home).close()
    con = sqlite3.connect(home / "desk.db")
    with con:
        con.execute("INSERT INTO lessons (id, text, tags, claim, status, made, author) VALUES "
                    "(3, 'Late one', '{}', 'better', 'active', '2026-10-05', 'desk')")
    con.close()
    desk_lessons.connect(home).close()
    assert _rows(home, "SELECT COUNT(*) FROM main.lessons") == [(2,)]


def test_lessons_read_the_same(home: Path) -> None:
    """UT-DSK-009.011.M23.T01: After the move lesson rows, proof and block read as before."""
    _old_lessons(home)
    before = desk_lessons.lesson_rows(home, "active")  # read from desk.db, not moved yet
    pending_before = desk_lessons.pending_edits(home)
    assert not (home / "memory.db").exists()
    desk_lessons.connect(home).close()
    rows = desk_lessons.lesson_rows(home, "active")
    assert rows == before and desk_lessons.pending_edits(home) == pending_before
    assert [(x.id, x.text, x.tags, x.claim, x.cases) for x in rows] == [
        (1, "Pullbacks fail", {"setup": "pullback"}, "worse", 5),
        (2, "Breakouts work", {"setup": "pullback"}, "worse", 5)]
    assert desk_lessons.pending_edits(home) == {2}
    assert desk_lessons.proof_rows(home, 1) == []


def test_cases_from_desk_db(home: Path) -> None:
    """UT-DSK-009.011.M23.T02: After the move, picks in desk.db still prove a lesson."""
    desk_lessons.connect(home).close()
    MarketStore(home).close()
    con = sqlite3.connect(home / "desk.db")
    with con:
        for i in range(6):
            day = f"2026-10-0{1 + i}"
            con.execute("INSERT INTO ideas (date, side, symbol, status, rank, score, sector, "
                        "setup, \"trigger\", stop) VALUES (?, 'long', ?, 'list', 1, 50, 'Tech', "
                        "?, 50, 47)", (day, f"S{i}", "pullback" if i < 5 else "breakout"))
            con.execute("INSERT INTO pick_results VALUES (?, 'long', ?, 'stop', ?, 50, ?, 50, ?)",
                        (day, f"S{i}", day, day, -1.0 if i < 5 else 3.0))
    con.close()
    keys = [f"2026-10-0{1 + i}|long|S{i}" for i in range(5)]
    lid = desk_lessons.add_candidate(home, "Pullbacks fail", {"setup": "pullback"}, "worse",
                                     keys, NOW)
    assert [x.id for x in desk_lessons.lesson_rows(home, "active")] == [lid]


# ---------------- rows and remember field (SRD-DSK-009.012, .013) ----------------

def test_memory_rows(home: Path) -> None:
    """UT-DSK-009.012.M30.T01: A note and a view are stored; FTS finds the view by symbol."""
    write(home, OWNER, [_note("Gaps fade by noon"), _view("NVDA", "up")], DAY, NOW)
    rows = _rows(home, "SELECT kind, owner, text, symbol, direction, made, due, status "
                       "FROM memories ORDER BY id")
    assert rows[0] == ("note", OWNER, "Gaps fade by noon", "", "", DAY, "", "active")
    assert rows[1][:6] == ("view", OWNER, "my call", "NVDA", "up", DAY)
    assert rows[1][6] == "2026-11-20" and rows[1][7] == "open"
    found = _rows(home, "SELECT rowid FROM memories_fts WHERE memories_fts MATCH 'NVDA'")
    assert found == [(2,)]


def test_bad_kind(home: Path) -> None:
    """UT-DSK-009.012.M30.T02: A kind other than note or view is refused."""
    draft = Remember.model_construct(kind="lesson", text="x", symbol=None, direction=None)
    assert write(home, OWNER, [draft], DAY, NOW) == ["dropped: unknown kind"]
    assert _rows(home, "SELECT COUNT(*) FROM memories") == [(0,)]


class _Answer(BaseModel):
    word: str


def test_remember_field() -> None:
    """UT-DSK-009.013.M27.T01: with_remember parses a note and a view."""
    model = with_remember(_Answer)
    answer = model.model_validate({"word": "x", "remember": [
        {"kind": "note", "text": "A"}, {"kind": "view", "text": "B", "symbol": "AAPL",
                                        "direction": "down"}]})
    assert [r.kind for r in answer.remember] == ["note", "view"]  # type: ignore[attr-defined]


def test_remember_refused() -> None:
    """UT-DSK-009.013.M27.T02: A bad item is dropped, extras past 3 too; the answer stays."""
    model = with_remember(_Answer)
    answer = model.model_validate({"word": "x", "remember": [
        {"kind": "view", "text": "B", "symbol": "AAPL"}, {"kind": "note", "text": "y" * 300}]})
    kept = answer.remember  # type: ignore[attr-defined]
    assert answer.word == "x" and [(r.kind, len(r.text)) for r in kept] == [("note", 200)]
    many = model.model_validate({"word": "x", "remember": [{"kind": "note", "text": "A"}] * 4})
    assert len(many.remember) == 3  # type: ignore[attr-defined]
    with pytest.raises(ValidationError):
        Remember(kind="view", text="B", symbol="AAPL")


# ---------------- clean write (SRD-DSK-009.014, .015) ----------------

def test_three_a_day(home: Path) -> None:
    """UT-DSK-009.014.M30.T01: Of 5 drafts on one day 3 are kept."""
    out = write(home, OWNER, [_note(f"Lesson number {w}") for w in "abcde"], DAY, NOW)
    assert out == ["added"] * 3 + ["dropped: 3 a day"] * 2


def test_next_day_counts_again(home: Path) -> None:
    """UT-DSK-009.014.M30.T02: The cap starts again the next day."""
    write(home, OWNER, [_note(f"Lesson number {w}") for w in "abc"], DAY, NOW)
    assert write(home, OWNER, [_note("Another day another note")], "2026-11-09", NOW) == [
        "added"]


def test_same_view(home: Path) -> None:
    """UT-DSK-009.015.M30.T01: The same open view is no change."""
    write(home, OWNER, [_view("NVDA", "up")], DAY, NOW)
    assert write(home, OWNER, [_view("NVDA", "up")], "2026-11-09", NOW) == ["no change"]


def test_opposite_view(home: Path) -> None:
    """UT-DSK-009.015.M30.T02: An opposite view retires the old one."""
    write(home, OWNER, [_view("NVDA", "up")], DAY, NOW)
    write(home, OWNER, [_view("NVDA", "down")], "2026-11-09", NOW)
    assert _rows(home, "SELECT direction, status, why FROM memories ORDER BY id") == [
        ("up", "retired", "changed view"), ("down", "open", "")]


def test_near_note(home: Path) -> None:
    """UT-DSK-009.015.M30.T03: A note with nearly the same words updates the old one."""
    write(home, OWNER, [_note("gap ups on earnings fade by noon most days now")], DAY, NOW)
    out = write(home, OWNER, [_note("gap ups on earnings fade by noon most days now often")],
                DAY, NOW)
    assert out == ["updated"] and len(_ids(home)) == 1


def test_pinned_note_kept(home: Path) -> None:
    """UT-DSK-009.015.M30.T04: A pinned note is never changed by code."""
    text = "gap ups on earnings fade by noon most days now"
    write(home, OWNER, [_note(text)], DAY, NOW)
    _set(home, 1, pinned=1)
    assert write(home, OWNER, [_note(text + " often")], DAY, NOW) == ["no change"]
    assert _rows(home, "SELECT text FROM memories") == [(text,)]


# ---------------- core block (SRD-DSK-009.016) ----------------

def test_core_block(home: Path) -> None:
    """UT-DSK-009.016.M30.T01: Track record, pinned, open view and miss lines."""
    write(home, OWNER, [_view("AAA", "up"), _view("BBB", "up"), _view("CCC", "up")], DAY, NOW)
    for mid, move in ((1, 2.0), (2, 3.0), (3, -2.5)):
        score_view(home, mid, move, "2026-11-20")
    write(home, OWNER, [_note("Keep stops wide on Fridays"), _view("NVDA", "down")],
          "2026-11-20", NOW)
    note = _ids(home)[0]
    _set(home, note, pinned=1)
    text = core_block(home, OWNER, "2026-11-21")
    assert "Track record: 3 views checked, 2 right, 1 wrong, 0 neutral (66% right)." in text
    assert "- Keep stops wide on Fridays" in text
    assert "- NVDA down, check" in text
    assert "- CCC up on 2026-11-06: moved -2.5%" in text


def test_core_block_empty(home: Path) -> None:
    """UT-DSK-009.016.M30.T02: An owner with no memories gets no block."""
    write(home, "emp-other", [_note("Something")], DAY, NOW)
    assert core_block(home, OWNER, DAY) == ""


def test_core_block_cap(home: Path) -> None:
    """UT-DSK-009.016.M30.T03: The block is at most 1,200 characters, cut at a line end."""
    for i in range(40):
        write(home, OWNER, [_note(f"pinned note {i} " + "word " * 10)], f"2026-10-{i % 28 + 1:02d}",
              NOW)
    _set_all_pinned(home)
    text = core_block(home, OWNER, DAY)
    assert 0 < len(text) <= CORE_CHARS and text.endswith("word")


def _set_all_pinned(home: Path) -> None:
    con = desk_memory.connect(home)
    with con:
        con.execute("UPDATE memories SET pinned = 1")
    con.close()


# ---------------- recall (SRD-DSK-009.017) ----------------

def test_recall_by_symbol(home: Path) -> None:
    """UT-DSK-009.017.M30.T01: The note on a stock in the facts comes first; uses are kept."""
    write(home, OWNER, [_note("Apple holds the 50 day", "AAPL"),
                        _note("Microsoft lags its sector", "MSFT"),
                        _note("Tesla gaps fill fast", "TSLA")], DAY, NOW)
    text = recall(home, OWNER, "Ideas today: TSLA long at 250", DAY)
    lines = text.splitlines()
    assert "Tesla gaps fill fast" in lines[1] and len(lines) == 4
    assert _rows(home, "SELECT COUNT(*) FROM memory_uses WHERE day = ?", (DAY,)) == [(3,)]


def test_recall_only_known_symbols(home: Path) -> None:
    """Upper-case words that are not the owner's note symbols do not drive recall."""
    write(home, OWNER, [_note("A is for apple, US banks lag"), _note("Tesla gaps", "TSLA")],
          DAY, NOW)
    lines = recall(home, OWNER, "A US NOTE: TSLA long", DAY).splitlines()
    assert "Tesla gaps" in lines[1]


def test_recall_leaves_weak(home: Path) -> None:
    """UT-DSK-009.017.M30.T02: A weak note is not recalled."""
    write(home, OWNER, [_note("Tesla gaps fill fast", "TSLA")], DAY, NOW)
    _set(home, 1, status="weak")
    assert recall(home, OWNER, "TSLA long", DAY) == ""


def test_recall_cap(home: Path) -> None:
    """UT-DSK-009.017.M30.T03: At most 10 notes and 4,000 characters."""
    for i in range(15):
        write(home, OWNER, [_note(f"note {i} " + "x" * 150 + f" tag{i}")],
              f"2026-10-{i + 1:02d}", NOW)
    text = recall(home, OWNER, "nothing", DAY)
    assert len(text.splitlines()) == 11 and len(text) <= RECALL_CHARS


# ---------------- scores (SRD-DSK-009.018–.020) ----------------

def _shown_note(home: Path) -> int:
    write(home, OWNER, [_note("Semis lead the tape", "NVDA"), _view("NVDA", "up")], DAY, NOW)
    recall(home, OWNER, "NVDA", DAY)
    return _ids(home)[0]


def test_right_view_scores_notes(home: Path) -> None:
    """UT-DSK-009.018.M30.T01: A right view adds one right to the note shown that day."""
    note = _shown_note(home)
    assert score_view(home, _ids(home, "view")[0], 2.0, "2026-11-20") == "right"
    assert _rows(home, "SELECT right, wrong FROM memories WHERE id = ?", (note,)) == [(1, 0)]


def test_neutral_view(home: Path) -> None:
    """UT-DSK-009.018.M30.T02: A neutral view changes no count."""
    note = _shown_note(home)
    assert score_view(home, _ids(home, "view")[0], 0.5, "2026-11-20") == "neutral"
    assert _rows(home, "SELECT right, wrong FROM memories WHERE id = ?", (note,)) == [(0, 0)]


def test_other_day_not_scored(home: Path) -> None:
    """UT-DSK-009.018.M30.T03: A note shown on another day is not scored."""
    write(home, OWNER, [_note("Semis lead the tape", "NVDA"), _view("NVDA", "up")], DAY, NOW)
    recall(home, OWNER, "NVDA", "2026-11-09")
    score_view(home, _ids(home, "view")[0], 2.0, "2026-11-20")
    assert _rows(home, "SELECT right FROM memories WHERE kind = 'note'") == [(0,)]


@pytest.mark.parametrize(("right", "wrong", "status"), [
    (1, 4, "weak"),     # UT-DSK-009.019.M30.T01
    (0, 4, "active"),   # UT-DSK-009.019.M30.T02
])
def test_weak(home: Path, right: int, wrong: int, status: str) -> None:
    """UT-DSK-009.019.M30.T01/T02: Under 40% after 5 checks is weak; fewer checks stay."""
    write(home, OWNER, [_note("A note")], DAY, NOW)
    _set(home, 1, right=right, wrong=wrong)
    review(home, NOW)
    assert _rows(home, "SELECT status FROM memories") == [(status,)]


def test_back_to_active(home: Path) -> None:
    """UT-DSK-009.019.M30.T03: A weak note at 40% or more is active again."""
    write(home, OWNER, [_note("A note")], DAY, NOW)
    _set(home, 1, right=2, wrong=3, status="weak")
    review(home, NOW)
    assert _rows(home, "SELECT status FROM memories") == [("active",)]


def test_expiry(home: Path) -> None:
    """UT-DSK-009.020.M30.T01: An unproven note 31 days old retires."""
    write(home, OWNER, [_note("Old note")], "2026-10-05", NOW - timedelta(days=32))
    review(home, NOW)
    assert _rows(home, "SELECT status FROM memories") == [("retired",)]


def test_proven_or_pinned_stay(home: Path) -> None:
    """UT-DSK-009.020.M30.T02: Proven and pinned notes 40 days old stay."""
    old = NOW - timedelta(days=40)
    write(home, OWNER, [_note("Proven one"), _note("Pinned two words")], "2026-09-25", old)
    _set(home, 1, right=3)
    _set(home, 2, pinned=1)
    review(home, NOW)
    assert _rows(home, "SELECT status FROM memories ORDER BY id") == [("active",), ("active",)]


def test_view_without_prices_retires(home: Path) -> None:
    """A view still open 30 days after its check day retires."""
    write(home, OWNER, [_view("ZZZ", "up")], "2026-09-01", NOW)
    review(home, NOW)
    assert _rows(home, "SELECT status, why FROM memories") == [("retired", "no prices to check")]


def test_open_views_due(home: Path) -> None:
    """Only open views with a check day by the given day come back."""
    write(home, OWNER, [_view("NVDA", "up")], DAY, NOW)
    assert open_views_due(home, "2026-11-19") == []
    assert [v.symbol for v in open_views_due(home, "2026-11-20")] == ["NVDA"]


# ---------------- clean-up actions (SRD-DSK-009.021) ----------------

def test_apply_cleanup(home: Path) -> None:
    """Merge adds counts to the target; retire retires; other owners and pins are left."""
    write(home, OWNER, [_note("First words here"), _note("Second other text"),
                        _note("Third more stuff")], DAY, NOW)
    write(home, "emp-other", [_note("Not mine at all")], DAY, NOW)
    _set(home, 1, right=2)
    _set(home, 3, pinned=1)
    merged, retired = apply_cleanup(home, OWNER, [
        CleanupAction(1, "merge", 2, "Joined text"), CleanupAction(3, "retire"),
        CleanupAction(4, "retire")], NOW)
    assert (merged, retired) == (1, 0)
    assert _rows(home, "SELECT id, status, text, right FROM memories ORDER BY id") == [
        (1, "retired", "First words here", 2), (2, "active", "Joined text", 2),
        (3, "active", "Third more stuff", 0), (4, "active", "Not mine at all", 0)]


# ---------------- edits (SRD-DSK-009.022) ----------------

def test_pin_edit(home: Path) -> None:
    """UT-DSK-009.022.M30.T01: A pin edit pins the note when applied."""
    write(home, OWNER, [_note("A note")], DAY, NOW)
    add_edit(home, 1, "pin", NOW)
    assert apply_edits(home, NOW) == 1
    assert _rows(home, "SELECT pinned FROM memories") == [(1,)]
    assert _rows(home, "SELECT note FROM memory_edits") == [("done",)]


def test_retired_stays(home: Path) -> None:
    """UT-DSK-009.022.M30.T02: Pinning a retired note leaves it retired and says why."""
    write(home, OWNER, [_note("A note")], DAY, NOW)
    _set(home, 1, status="retired")
    add_edit(home, 1, "pin", NOW)
    apply_edits(home, NOW)
    assert _rows(home, "SELECT status, pinned FROM memories") == [("retired", 0)]
    assert _rows(home, "SELECT note FROM memory_edits") == [("note is retired",)]


def test_tick_applies_note_edits(home: Path, clock: Any) -> None:
    """UT-DSK-009.022.M04.T01: One desk tick applies a pending note edit."""
    write(home, OWNER, [_note("A note")], DAY, NOW)
    add_edit(home, 1, "retire", NOW)
    desk = DeskProcess(home, clock=clock, sleep=lambda _s: None, steps=[])
    assert desk.start()
    desk.tick()
    desk.close()
    assert _rows(home, "SELECT status FROM memories") == [("retired",)]


def test_bad_edit_action(home: Path) -> None:
    """An unknown edit action is refused."""
    with pytest.raises(ValueError, match="action"):
        add_edit(home, 1, "delete", NOW)


# ---------------- settings and logs (SRD-DSK-009.023, .024) ----------------

def test_off_by_default() -> None:
    """UT-DSK-009.023.M13.T01: Memory v2 is off by default."""
    assert DeskAiSettings().memory_v2_on is False


def test_log_lines(home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-009.024.M30.T01: Move, drop, weak and retire are logged under Memory."""
    _old_lessons(home)
    with caplog.at_level(logging.INFO):
        desk_lessons.connect(home).close()
        write(home, OWNER, [_note(f"Lesson number {w}") for w in "abcd"], DAY, NOW)
        _set(home, 1, right=1, wrong=4)
        _set(home, 2, made="2026-09-01", updated="2026-09-01")
        review(home, NOW)
    text = caplog.text
    assert "[Memory] Moved 2 lesson(s) to the memory file" in text
    assert "[Memory] 1 note(s) of emp-x not kept" in text
    assert "[Memory] Note N-1 left out of recall" in text
    assert "[Memory] Note N-2 retired" in text
