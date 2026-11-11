"""Tests for follow-up tickets from research skills (SRD-DSK-010.015, step F)."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from tests.desk.research_support import NOW, employee
from us_swing.core.desk_research import TicketAsk, connect, raise_follow_ups


def _ask(n: int = 0) -> TicketAsk:
    return TicketAsk(kind="setup_tuning", topic=f"Pullback {n}", goal=f"Try Pullback limit {n}",
                     done_test="A variant beats baseline", token_cap=8_000)


def _rows(home: Path) -> list[Any]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute("SELECT raised_by, raised_by_name, status, approved_by "
                           "FROM tickets").fetchall()
    finally:
        con.close()


def test_follow_up_in_lead_name(tmp_path: Path) -> None:
    """UT-DSK-010.015.M25.T01: The row is raised by the given lead and approved by auto."""
    employee(tmp_path, "l-1", "Lead A", "lead", "fake_lead")
    notes = raise_follow_ups(tmp_path, "l-1", [_ask()], NOW)
    assert notes[0].startswith("ticket ") and notes[0].endswith("approved")
    assert _rows(tmp_path) == [("l-1", "Lead A", "approved", "auto")]


def test_lead_gone(tmp_path: Path) -> None:
    """UT-DSK-010.015.M25.T02: A retired lead or an expert id refuses every ask."""
    employee(tmp_path, "l-1", "Lead A", "lead", "fake_lead", extra="status: retired\n")
    employee(tmp_path, "r-1", "Expert R", "expert", "fake_research")
    for emp_id in ("l-1", "r-1", "nobody"):
        notes = raise_follow_ups(tmp_path, emp_id, [_ask(), _ask(1)], NOW)
        assert notes == ["refused: the raising lead is no longer an active lead"] * 2
    assert not (tmp_path / "desk.db").exists() or _rows(tmp_path) == []


def test_lead_limits(tmp_path: Path) -> None:
    """UT-DSK-010.015.M25.T03: The lead's 3-a-day limit applies to follow-ups."""
    employee(tmp_path, "l-1", "Lead A", "lead", "fake_lead")
    con = connect(tmp_path)
    with con:
        for i in range(3):
            con.execute("INSERT INTO tickets (kind, topic, goal, raised_by, status, made) "
                        "VALUES ('sentiment', ?, ?, 'l-1', 'done', ?)",
                        (f"t{i}", f"goal {i}", NOW.isoformat()))
    con.close()
    assert raise_follow_ups(tmp_path, "l-1", [_ask()], NOW) == ["refused: 3 tickets a day"]
