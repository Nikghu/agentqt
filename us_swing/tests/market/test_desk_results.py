"""Tests for MD-MKT-009.005.M03 (core/desk_results.py), MD-MKT-009.005.M04 (app hook) and
MD-MKT-009.007.M05 (weekly report section). Employee names here are made up."""
from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.desk.test_hiring import _emp
from tests.market.test_desk_trades import _seed
from us_swing.core import desk_contract
from us_swing.core.desk_contract import DB_NAME
from us_swing.core.desk_results import record_pick_trade, results_lines, results_view
from us_swing.core.desk_trades import pick_expiry, record_trade_decision, record_trade_outcome
from us_swing.core.desk_trades import TradePick
from us_swing.data.market_calendar import ET
from us_swing.desk.weekly_report import build_report
from us_swing.gui.app_service import AppService
from us_swing.market.store import MarketStore, PickResultRow, SetupReviewRow, NewsTagRow

FRI = "2026-11-06"
SAT = datetime(2026, 11, 7, 12, 0, tzinfo=ET)


def _snap(symbol: str = "AAA", strategy: str = "AI Desk", exit_: float = 110.0) -> Any:
    return SimpleNamespace(strategy_id=strategy, symbol=symbol, direction="LONG",
                           entry_time="2026-11-09T14:40:00", entry_price=100.0,
                           exit_time="2026-11-10T15:00:00", exit_price=exit_, entry_qty=10,
                           realized_pnl_usd=(exit_ - 100.0) * 10, hard_stop_loss=95.0,
                           exit_reason="target")


def _trades(home: Path) -> list[tuple[Any, ...]]:
    con = sqlite3.connect(home / DB_NAME)
    try:
        return con.execute("SELECT subject, pnl, r FROM pick_trades").fetchall()
    finally:
        con.close()


def _results(home: Path, day: str, rows: list[tuple[str, str, str | None, float | None]]) -> None:
    """Paper rows: (symbol, status, entry_day, r) for long picks of ``day``."""
    store = MarketStore(home)
    try:
        old = store.read_frame("SELECT * FROM pick_results")
        keep = [PickResultRow(*r) for r in old.itertuples(index=False)]
        store.replace_pick_results(keep + [PickResultRow(day, "long", s, st, e, 100.0 if e else None,
                                                         None, None, r) for s, st, e, r in rows])
    finally:
        store.close()


def _four(home: Path) -> None:
    _seed(home, FRI, [("long", s, 100.0, 95.0, "pass") for s in ("TGT", "STP", "NOF", "OPN")])
    _results(home, FRI, [("TGT", "target", "2026-11-09", 2.0), ("STP", "stop", "2026-11-09", -1.0),
                         ("NOF", "no_fill", None, None), ("OPN", "open", "2026-11-10", 0.2)])


def test_real_trade_matched(tmp_path: Path) -> None:
    """UT-MKT-009.005.M03.T01: a closed AI Desk trade is saved against its executed pick."""
    pick = TradePick(FRI, "long", "AAA", 1, "", 100.0, 95.0, 110.0, pick_expiry(FRI))
    record_trade_decision(tmp_path, pick, "approve", 10, SAT)
    record_trade_outcome(tmp_path, pick.subject, "executed", SAT)
    record_pick_trade(tmp_path, _snap(), SAT)
    assert _trades(tmp_path) == [(f"{FRI}:long:AAA", 100.0, 2.0)]


def test_no_pick_and_append_only(tmp_path: Path) -> None:
    """UT-MKT-009.005.M03.T02: an unmatched trade keeps an empty subject; rows never change."""
    record_pick_trade(tmp_path, _snap(), SAT)
    assert _trades(tmp_path) == [("", 100.0, 2.0)]
    con = sqlite3.connect(tmp_path / DB_NAME)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("UPDATE pick_trades SET pnl = 0")
    finally:
        con.close()


def test_app_hook(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-MKT-009.005.M04.T01: only AI Desk cycles are saved."""
    monkeypatch.setattr(desk_contract, "desk_home", lambda: tmp_path)
    AppService._record_desk_trade(_snap())
    AppService._record_desk_trade(_snap("BBB", strategy="Other"))
    assert len(_trades(tmp_path)) == 1


def test_totals(tmp_path: Path) -> None:
    """UT-MKT-009.006.M03.T01: totals count picks, fills, finished, hit rate and average R."""
    _four(tmp_path)
    t = results_view(tmp_path, SAT).total
    assert (t.picks, t.fills, t.finished, t.targets, t.hit_rate, t.avg_r) == (4, 3, 2, 1, 0.5, 0.5)


def test_breakdowns(tmp_path: Path) -> None:
    """UT-MKT-009.006.M03.T02: groups per decision, setup grade and news tone."""
    _four(tmp_path)
    store = MarketStore(tmp_path)
    try:
        store.replace_day("setup_review", FRI, [SetupReviewRow(FRI, "long", "TGT", "A", ""),
                                                SetupReviewRow(FRI, "long", "STP", "B", "")])
        store.replace_day("news_tags", FRI, [NewsTagRow(FRI, "long", "TGT", "positive", "", 1.0, 80.0)])
    finally:
        store.close()
    pick = TradePick(FRI, "long", "TGT", 1, "", 100.0, 95.0, 110.0, pick_expiry(FRI))
    record_trade_decision(tmp_path, pick, "approve", 1, SAT)
    record_trade_decision(tmp_path, TradePick(FRI, "long", "STP", 1, "", 100.0, 95.0, 110.0,
                                              pick_expiry(FRI)), "reject", 0, SAT)
    b = results_view(tmp_path, SAT).breakdowns
    assert {g.label: g.picks for g in b["Decision"]} == {"approved": 1, "rejected": 1, "waiting": 2}
    assert {g.label: (g.picks, g.targets) for g in b["Setup grade"]} == {
        "A": (1, 1), "B": (1, 0), "none": (2, 0)}
    assert {g.label: g.picks for g in b["News tone"]} == {"positive": 1, "none": 3}


def test_empty_desk(tmp_path: Path) -> None:
    """UT-MKT-009.006.M03.T03: no desk file or no tables give zero totals."""
    assert results_view(tmp_path / "none", SAT).total.picks == 0
    sqlite3.connect(tmp_path / DB_NAME).close()
    view = results_view(tmp_path, SAT)
    assert (view.total.picks, view.real.trades) == (0, 0)
    assert results_lines(view) == ["No lead picks this week"]


def test_no_employee_names(tmp_path: Path) -> None:
    """UT-MKT-009.006.M03.T04: no employee name appears in any group label or line."""
    _emp(tmp_path, "emp-005", "Made Up Lead")
    _four(tmp_path)
    view = results_view(tmp_path, SAT)
    labels = [g.label for gs in view.breakdowns.values() for g in gs]
    assert not any("Made Up" in x for x in [*labels, *results_lines(view)])


def test_weekly_section(tmp_path: Path) -> None:
    """UT-MKT-009.007.M05.T01: the weekly report counts only the week's picks."""
    _four(tmp_path)
    _seed(tmp_path, "2026-10-29", [("long", "OLD", 100.0, 95.0, "pass")])
    text, _count, _cost = build_report(tmp_path, date(2026, 11, 6))
    section = text.split("Pick results:")[1]
    assert "Paper: 4 pick(s), 3 filled, 2 finished, hit rate 50%, average R 0.50" in section


def test_weekly_no_picks(tmp_path: Path) -> None:
    """UT-MKT-009.007.M05.T02: a week without lead picks says so."""
    text, _count, _cost = build_report(tmp_path, date(2026, 11, 6))
    assert text.endswith("Pick results:\nNo lead picks this week")
