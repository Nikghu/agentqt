"""Tests for MD-MKT-020.002.M01 — core/desk_day.py (company day rows, AI Desk v3 M5)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from us_swing.core.desk_day import (
    NO_HANDOVER,
    STANDUP_CHARS,
    clash,
    connect,
    day_call_line,
    day_view,
    due_calls,
    has_handover,
    huddle_block,
    huddle_open,
    mark_huddle,
    save_call,
    save_day_end,
    save_results,
    save_standup,
    standup_text,
    votes_of,
)
from us_swing.market.store import MarketStore, RegimeViewRow, SectorViewRow

NY = ZoneInfo("America/New_York")
NOW = datetime(2026, 11, 13, 8, 0, tzinfo=NY)
DAY = "2026-11-12"


def _run(home: Path, sql: str, params: tuple[Any, ...] = ()) -> None:
    con = sqlite3.connect(home / "desk.db")
    try:
        with con:
            con.execute(sql, params)
    finally:
        con.close()


def _views(home: Path, regime: str | None = "Choppy",
           favour: list[str] | None = None) -> None:
    store = MarketStore(home)
    try:
        if regime:
            store.write_regime_view(RegimeViewRow(DAY, regime, 0.7, json.dumps(
                ["Breadth is mixed today"]), "brief", regime, True))
        if favour is not None:
            store.replace_day("sector_view", DAY, [SectorViewRow(
                DAY, json.dumps(favour), json.dumps(["Energy"]), "rotation", "brief")])
    finally:
        store.close()


def _all_views(home: Path) -> None:
    _views(home, "Uptrend", ["Information Technology"])
    for symbol, grade in (("AAA", "A"), ("BBB", "B"), ("CCC", "B")):
        _run(home, "INSERT INTO setup_review VALUES (?, 'long', ?, ?, 'note')",
             (DAY, symbol, grade))
    _run(home, "INSERT INTO news_tags VALUES (?, 'long', 'AAA', 'negative', 'r', 0, 0)", (DAY,))
    _run(home, "INSERT INTO risk_check VALUES (?, 'long', 'AAA', 'veto', 'code', 'r')", (DAY,))
    _run(home, "INSERT INTO risk_check VALUES (?, 'long', 'BBB', 'pass', 'code', '')", (DAY,))


def test_tables_on_first_use(tmp_path: Path) -> None:
    """UT-MKT-020.002.M01.T01: The day tables are made on first write."""
    save_standup(tmp_path, DAY, "Stand-up", NOW)
    con = sqlite3.connect(tmp_path / "desk.db")
    names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    con.close()
    assert {"day_brief", "decisions", "decision_votes"} <= names


def test_reads_with_no_file(tmp_path: Path) -> None:
    """UT-MKT-020.002.M01.T02: Reads with no desk.db give empty values and make no file."""
    assert "Regime view: no view today." in standup_text(tmp_path, DAY)
    view = day_view(tmp_path)
    assert view.call is None and view.handover == ()
    assert not has_handover(tmp_path, DAY)
    assert not (tmp_path / "desk.db").exists()


def test_standup_lines(tmp_path: Path) -> None:
    """UT-MKT-020.003.M01.T01: The stand-up has the handover and one line per view."""
    _all_views(tmp_path)
    save_day_end(tmp_path, "2026-11-11", ["NVDA in trade, stop 136"], [], "s", NOW)
    text = standup_text(tmp_path, DAY)
    assert text.startswith(f"Stand-up for {DAY}")
    assert "Handover from 2026-11-11: NVDA in trade, stop 136" in text
    assert "Regime view: Uptrend, confidence 70%. Breadth is mixed today" in text
    assert "Sector/flow: favour Information Technology; avoid Energy." in text
    assert "Setup review: 3 ideas graded: 1 A, 2 B, 0 C." in text
    assert "News review: 1 ideas tagged; 1 with bad news." in text
    assert "Risk check: 1 passed, 1 vetoed (1 by code)." in text


def test_standup_with_nothing(tmp_path: Path) -> None:
    """UT-MKT-020.003.M01.T02: Missing views and note each say so."""
    MarketStore(tmp_path).close()
    text = standup_text(tmp_path, DAY)
    assert NO_HANDOVER in text
    assert text.count("no view today") == 5


def test_standup_cut(tmp_path: Path) -> None:
    """UT-MKT-020.004.M01.T01: A long stand-up is cut to 1,200 characters."""
    _all_views(tmp_path)
    save_day_end(tmp_path, "2026-11-11", ["x" * 120] * 5, [], "s", NOW)
    _run(tmp_path, "UPDATE day_brief SET handover = ?", (json.dumps(["y" * 400] * 4),))
    assert len(standup_text(tmp_path, DAY)) <= STANDUP_CHARS


def test_downtrend_clash() -> None:
    """UT-MKT-020.005.M01.T01: Downtrend with no defensive sector is a clash."""
    why = clash("Downtrend", ["Information Technology", "Energy"])
    assert why and "Downtrend" in why and "Information Technology, Energy" in why


def test_uptrend_clash() -> None:
    """UT-MKT-020.005.M01.T02: Uptrend with only defensive sectors is a clash."""
    why = clash("Uptrend", ["Utilities", "Health Care"])
    assert why and "only defensive" in why


def test_no_clash() -> None:
    """UT-MKT-020.005.M01.T03: Choppy, mixed or empty views never clash."""
    assert clash("Choppy", ["Energy"]) is None
    assert clash("Downtrend", ["Utilities", "Energy"]) is None
    assert clash("Uptrend", ["Energy"]) is None
    assert clash("Downtrend", []) is None
    assert clash(None, ["Energy"]) is None


def test_no_huddle_block(tmp_path: Path) -> None:
    """UT-MKT-020.010.M01.T01: No huddle gives an empty block and nothing open."""
    _views(tmp_path)
    assert huddle_block(tmp_path, DAY) == ""
    assert not huddle_open(tmp_path, DAY)
    mark_huddle(tmp_path, DAY, "clash", NOW)
    assert huddle_block(tmp_path, DAY) == ""  # called but no meeting rows


def test_day_call_saved(tmp_path: Path) -> None:
    """UT-MKT-020.012.M01.T01: The call is kept open with its check day and huddle flag."""
    _views(tmp_path)
    mark_huddle(tmp_path, DAY, "clash", NOW)
    save_call(tmp_path, DAY, "Uptrend", ["Information Technology"], "note", "2026-11-19", NOW)
    view = day_view(tmp_path)
    assert view.call is not None
    assert (view.call.market, view.call.favour, view.call.due, view.call.status,
            view.call.huddle) == ("Uptrend", ("Information Technology",), "2026-11-19", "open",
                                  True)


def test_same_day_replaces(tmp_path: Path) -> None:
    """UT-MKT-020.012.M01.T02: A second call on one day replaces the first and its votes."""
    _views(tmp_path, "Choppy", ["Energy"])
    save_call(tmp_path, DAY, "Uptrend", ["Energy"], "", "2026-11-19", NOW)
    save_call(tmp_path, DAY, "Choppy", ["Utilities"], "", "2026-11-19", NOW)
    view = day_view(tmp_path)
    assert view.call is not None and view.call.market == "Choppy"
    assert {(v.skill, v.stance) for v in votes_of(tmp_path, DAY)} == {
        ("regime_view", "agreed"), ("sector_flow_view", "disagreed")}


def test_not_due_yet(tmp_path: Path) -> None:
    """UT-MKT-020.012.M01.T03: Calls not due or already checked are not listed."""
    _views(tmp_path)
    save_call(tmp_path, DAY, "Uptrend", ["Energy"], "", "2026-11-20", NOW)
    save_call(tmp_path, "2026-11-05", "Uptrend", ["Energy"], "", "2026-11-12", NOW)
    save_results(tmp_path, "2026-11-05", "right", "neutral", 1.2, None, {}, "2026-11-12")
    assert due_calls(tmp_path, "2026-11-19") == []
    assert [c.day for c in due_calls(tmp_path, "2026-11-20")] == [DAY]


def test_votes(tmp_path: Path) -> None:
    """UT-MKT-020.013.M01.T01: Each view's stance is kept by skill."""
    _views(tmp_path, "Choppy", ["Information Technology", "Energy"])
    votes = save_call(tmp_path, DAY, "Uptrend", ["Information Technology"], "", "2026-11-19",
                      NOW)
    assert {(v.skill, v.part, v.stance) for v in votes} == {
        ("regime_view", "market", "disagreed"), ("sector_flow_view", "sector", "agreed")}


def test_missing_view_no_vote(tmp_path: Path) -> None:
    """UT-MKT-020.013.M01.T02: A missing view gives no vote."""
    _views(tmp_path, "Uptrend", None)
    votes = save_call(tmp_path, DAY, "Uptrend", ["Energy"], "", "2026-11-19", NOW)
    assert [v.skill for v in votes] == ["regime_view"]


def test_day_call_line(tmp_path: Path) -> None:
    """UT-MKT-020.018.M01.T01: The line counts checked votes of a skill."""
    _views(tmp_path)
    connect(tmp_path).close()
    for day, result in (("2026-11-02", "right"), ("2026-11-03", "right"),
                        ("2026-11-04", "wrong"), ("2026-11-05", "neutral"), ("2026-11-06", "")):
        _run(tmp_path, "INSERT INTO decision_votes VALUES (?, 'regime_view', 'market', "
             "'agreed', ?)", (day, result))
    assert day_call_line(tmp_path, "regime_view") == (
        "Day calls you voted on: 4 checked, 2 right, 1 wrong.")


def test_no_line_without_checks(tmp_path: Path) -> None:
    """UT-MKT-020.018.M01.T02: Only open votes give no line."""
    _views(tmp_path)
    save_call(tmp_path, DAY, "Choppy", ["Energy"], "", "2026-11-19", NOW)
    assert day_call_line(tmp_path, "regime_view") == ""
    assert day_call_line(tmp_path, "setup_review") == ""


def test_day_end_rows(tmp_path: Path) -> None:
    """UT-MKT-020.022.M01.T01: Day-end rows are kept and the latest handover is shown."""
    save_day_end(tmp_path, DAY, ["NVDA in trade", "AMD did not trigger"],
                 [("setup_review", "AMD grade B was right")], "2 picks", NOW)
    assert has_handover(tmp_path, DAY)
    view = day_view(tmp_path)
    assert view.handover_day == DAY
    assert view.handover == ("NVDA in trade", "AMD did not trigger")


def test_checked_call_kept(tmp_path: Path) -> None:
    """UT-MKT-020.012.M01.T04: A rerun on a checked day keeps the call and its results."""
    _views(tmp_path, "Uptrend", ["Energy"])
    save_call(tmp_path, DAY, "Uptrend", ["Energy"], "", "2026-11-19", NOW)
    save_results(tmp_path, DAY, "right", "right", 1.5, 2.0,
                 {"regime_view": "right", "sector_flow_view": "right"}, "2026-11-19")
    save_call(tmp_path, DAY, "Downtrend", ["Utilities"], "", "2026-11-19", NOW)
    view = day_view(tmp_path)
    assert view.call is not None and (view.call.market, view.call.status) == ("Uptrend",
                                                                             "checked")
    assert {v.result for v in votes_of(tmp_path, DAY)} == {"right"}
