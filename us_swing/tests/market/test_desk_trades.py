"""Tests for MD-MKT-008.001.M01 (core/desk_trades.py) and MD-MKT-008.002.M02 (R setting)."""
from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path

import pytest

from us_swing.core import desk_trades as dt
from us_swing.core.desk_ai_settings import DeskAiSettings, load_settings
from us_swing.core.desk_contract import DB_NAME
from us_swing.data.market_calendar import ET
from us_swing.market.store import IdeaRow, LeadPickRow, MarketStore, RiskCheckRow

SRC = Path(dt.__file__).resolve().parents[1]
FRI = "2026-11-06"
SAT_NOON = datetime(2026, 11, 7, 12, 0, tzinfo=ET)


def _seed(home: Path, day: str, picks: list[tuple[str, str, float | None, float | None, str]]
          ) -> None:
    """Write ideas, risk checks and lead picks; each pick is (side, symbol, trigger, stop, verdict)."""
    store = MarketStore(home)
    try:
        ideas = [IdeaRow(day, side, sym, "list", i + 1, 80.0, "Tech", "breakout", trig, stop)
                 for i, (side, sym, trig, stop, _v) in enumerate(picks)]
        store.write_idea_days([day], [], ideas, [])
        store.replace_day("risk_check", day, [RiskCheckRow(day, side, sym, v, "code", "")
                                              for side, sym, _t, _s, v in picks if v])
        store.replace_day("lead_picks", day, [LeadPickRow(day, side, sym, i + 1, "strong")
                                              for i, (side, sym, _t, _s, _v) in
                                              enumerate(picks)])
    finally:
        store.close()


def _pick(day: str = FRI, side: str = "long", symbol: str = "AAA") -> dt.TradePick:
    return dt.TradePick(day, side, symbol, 1, "strong", 100.0, 95.0, 110.0, dt.pick_expiry(day))


def _rows(home: Path) -> list[tuple[str, str, str, str]]:
    con = sqlite3.connect(home / DB_NAME)
    try:
        return con.execute("SELECT kind, subject, decision, detail FROM approvals").fetchall()
    finally:
        con.close()


def test_trade_picks_listed(tmp_path: Path) -> None:
    """UT-MKT-008.001.M01.T01: risk-passed long and short picks are listed with their levels."""
    _seed(tmp_path, FRI, [("short", "BBB", 50.0, 52.0, "pass"), ("long", "AAA", 100.0, 95.0, "pass")])
    picks = dt.trade_picks(tmp_path, SAT_NOON, 2.0)
    assert [(p.side, p.symbol, p.entry, p.stop, p.target) for p in picks] == [
        ("long", "AAA", 100.0, 95.0, 110.0), ("short", "BBB", 50.0, 52.0, 46.0)]
    assert all(p.state == "waiting" for p in picks)


def test_trade_picks_not_listed(tmp_path: Path) -> None:
    """UT-MKT-008.001.M01.T02: vetoed, unchecked and trigger-less picks are not listed."""
    _seed(tmp_path, FRI, [("long", "VET", 100.0, 95.0, "veto"), ("long", "NOR", 100.0, 95.0, ""),
                          ("long", "NOT", None, 95.0, "pass")])
    assert dt.trade_picks(tmp_path, SAT_NOON, 2.0) == []


def test_trade_picks_latest_day_only(tmp_path: Path) -> None:
    """UT-MKT-008.001.M01.T03: only the newest lead pick day; no table gives an empty list."""
    assert dt.trade_picks(tmp_path, SAT_NOON, 2.0) == []
    sqlite3.connect(tmp_path / DB_NAME).close()
    assert dt.trade_picks(tmp_path, SAT_NOON, 2.0) == []
    _seed(tmp_path, "2026-11-05", [("long", "OLD", 10.0, 9.0, "pass")])
    _seed(tmp_path, FRI, [("long", "NEW", 10.0, 9.0, "pass")])
    assert [p.symbol for p in dt.trade_picks(tmp_path, SAT_NOON, 2.0)] == ["NEW"]


def test_target_two_r() -> None:
    """UT-MKT-008.002.M01.T01: the target is 2R from the entry."""
    assert dt.pick_target("long", 100.0, 95.0, 2.0) == 110.0
    assert dt.pick_target("short", 50.0, 52.0, 2.0) == 46.0


def test_target_bad_stop(tmp_path: Path) -> None:
    """UT-MKT-008.002.M01.T02: a stop at or on the wrong side of the entry gives no target."""
    assert dt.pick_target("long", 100.0, 100.0, 2.0) is None
    assert dt.pick_target("long", 100.0, 101.0, 2.0) is None
    assert dt.pick_target("short", 50.0, 49.0, 2.0) is None
    _seed(tmp_path, FRI, [("long", "BAD", 100.0, 101.0, "pass")])
    assert dt.trade_picks(tmp_path, SAT_NOON, 2.0) == []


def test_r_setting(tmp_path: Path) -> None:
    """UT-MKT-008.002.M02.T01: the R multiple defaults to 2.0 and loads from the file."""
    assert load_settings(tmp_path).trade_target_r == 2.0
    (tmp_path / "desk_ai.json").write_text(json.dumps({"trade_target_r": 1.5}), encoding="utf-8")
    assert load_settings(tmp_path).trade_target_r == 1.5


def test_r_setting_not_above_zero(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-008.002.M02.T02: an R multiple not above 0 is refused."""
    with pytest.raises(ValueError):
        DeskAiSettings(trade_target_r=0)
    (tmp_path / "desk_ai.json").write_text(json.dumps({"trade_target_r": -1}), encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        assert load_settings(tmp_path) == DeskAiSettings()
    assert "not valid" in caplog.text


def test_waiting_until_next_open(tmp_path: Path) -> None:
    """UT-MKT-008.003.M01.T01: a Friday pick waits until Monday's open."""
    pick = _pick()
    assert pick.expires == datetime(2026, 11, 9, 9, 30, tzinfo=ET)
    assert dt.pick_state(tmp_path, pick, SAT_NOON) == "waiting"


def test_expiry_edge_and_holiday(tmp_path: Path) -> None:
    """UT-MKT-008.003.M01.T02: expired exactly at the open; Thanksgiving is skipped."""
    assert dt.pick_state(tmp_path, _pick(), datetime(2026, 11, 9, 9, 30, tzinfo=ET)) == "expired"
    assert dt.pick_expiry("2026-11-25") == datetime(2026, 11, 27, 9, 30, tzinfo=ET)


def test_decided_state(tmp_path: Path) -> None:
    """UT-MKT-008.003.M01.T03: approve and reject rows give approved and rejected."""
    a, b = _pick(symbol="AAA"), _pick(symbol="BBB")
    assert dt.record_trade_decision(tmp_path, a, "approve", 5, SAT_NOON) == ""
    assert dt.record_trade_decision(tmp_path, b, "reject", 0, SAT_NOON) == ""
    assert dt.pick_state(tmp_path, a, SAT_NOON) == "approved"
    assert dt.pick_state(tmp_path, b, SAT_NOON) == "rejected"


def test_other_rows_ignored(tmp_path: Path) -> None:
    """UT-MKT-008.003.M01.T04: rows of other picks or other kinds do not decide a pick."""
    pick = _pick()
    assert dt.pick_state(tmp_path, pick, SAT_NOON) == "waiting"
    dt.record_trade_decision(tmp_path, _pick(symbol="ZZZ"), "reject", 0, SAT_NOON)
    con = sqlite3.connect(tmp_path / DB_NAME)
    with con:
        con.execute("INSERT INTO approvals (created, kind, subject, decision, detail) "
                    "VALUES ('x', 'hire', ?, 'reject', '')", (pick.subject,))
    con.close()
    assert dt.pick_state(tmp_path, pick, SAT_NOON) == "waiting"


def test_approve_row(tmp_path: Path) -> None:
    """UT-MKT-008.004.M01.T01: one trade row with the subject and the levels in detail."""
    assert dt.record_trade_decision(tmp_path, _pick(), "approve", 45, SAT_NOON) == ""
    [(kind, subject, decision, detail)] = _rows(tmp_path)
    assert (kind, subject, decision) == ("trade", f"{FRI}:long:AAA", "approve")
    d = json.loads(detail)
    assert (d["entry"], d["stop"], d["target"], d["qty"]) == (100.0, 95.0, 110.0, 45)


def test_second_or_late_decision(tmp_path: Path) -> None:
    """UT-MKT-008.004.M01.T02: second, late and unknown decisions are refused."""
    assert dt.record_trade_decision(tmp_path, _pick(), "approve", 1, SAT_NOON) == ""
    assert dt.record_trade_decision(tmp_path, _pick(), "reject", 0, SAT_NOON) != ""
    late = datetime(2026, 11, 9, 10, 0, tzinfo=ET)
    assert dt.record_trade_decision(tmp_path, _pick(symbol="LATE"), "approve", 1, late) != ""
    assert dt.record_trade_decision(tmp_path, _pick(symbol="M"), "maybe", 1, SAT_NOON) != ""
    assert len(_rows(tmp_path)) == 1


def test_table_made_and_append_only(tmp_path: Path) -> None:
    """UT-MKT-008.004.M01.T03: the approvals table is made when missing and stays append-only."""
    sqlite3.connect(tmp_path / DB_NAME).close()
    assert dt.record_trade_decision(tmp_path, _pick(), "approve", 1, SAT_NOON) == ""
    con = sqlite3.connect(tmp_path / DB_NAME)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("UPDATE approvals SET decision = 'reject'")
    finally:
        con.close()


def test_approved_picks_for_day(tmp_path: Path) -> None:
    """UT-MKT-008.004.M01.T04: only approved picks of the trading day come back."""
    dt.record_trade_decision(tmp_path, _pick(symbol="YES"), "approve", 3, SAT_NOON)
    dt.record_trade_decision(tmp_path, _pick(symbol="NO"), "reject", 0, SAT_NOON)
    picks = dt.approved_picks(tmp_path, date(2026, 11, 9))
    assert [(p.symbol, p.entry, p.target, p.state) for p in picks] == [
        ("YES", 100.0, 110.0, "approved")]
    assert dt.approved_picks(tmp_path, date(2026, 11, 10)) == []


def test_done_picks_left_out(tmp_path: Path) -> None:
    """UT-MKT-008.004.M01.T05: a pick whose signal was executed or dismissed is not approved-open."""
    dt.record_trade_decision(tmp_path, _pick(symbol="EXE"), "approve", 3, SAT_NOON)
    dt.record_trade_decision(tmp_path, _pick(symbol="OPEN"), "approve", 3, SAT_NOON)
    dt.record_trade_outcome(tmp_path, _pick(symbol="EXE").subject, "executed", SAT_NOON)
    assert [p.symbol for p in dt.approved_picks(tmp_path, date(2026, 11, 9))] == ["OPEN"]


def test_no_desk_or_gui_import() -> None:
    """UT-MKT-008.005.M01.T01: core/desk_trades.py imports neither desk, market nor gui."""
    text = (SRC / "core" / "desk_trades.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*(from|import) us_swing\.(desk|market|gui)\b", text, re.M)


def test_desk_process_never_writes() -> None:
    """UT-MKT-008.005.M01.T02: no desk or market code writes trade approvals."""
    for pkg in ("desk", "market"):
        for path in (SRC / pkg).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert "record_trade_decision" not in text, path
            assert "'trade'" not in text or "approvals" not in text, path


def test_logs(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-008.006.M01.T01: decision and expired-count log lines carry the [AI Desk] prefix."""
    _seed(tmp_path, FRI, [("long", "AAA", 100.0, 95.0, "pass"), ("long", "BBB", 10.0, 9.0, "pass")])
    with caplog.at_level(logging.INFO, logger="us_swing.core.desk_trades"):
        dt.record_trade_decision(tmp_path, _pick(), "approve", 1, SAT_NOON)
        dt.trade_picks(tmp_path, datetime(2026, 11, 9, 10, 0, tzinfo=ET), 2.0)
    msgs = [r.getMessage() for r in caplog.records]
    assert "[AI Desk] Trade pick long AAA approved" in msgs
    assert "[AI Desk] 1 trade pick(s) expired without a decision" in msgs
