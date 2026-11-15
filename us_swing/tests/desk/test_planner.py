"""Tests for MD-DSK-012.018.M34 (desk/planner.py): the task planner skill.

Employee names here are made up: code must never depend on them.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from tests.desk import task_support as ts
from us_swing.core import desk_steps
from us_swing.core.desk_alerts import open_alerts
from us_swing.core.desk_memory import failure_rows
from us_swing.core.desk_messages import accept
from us_swing.core.desk_msg import Draft
from us_swing.core.desk_registry import fill_registry
from us_swing.core.desk_tasks import card_rows, fill_plans, get_plan
from us_swing.desk import planner

ALL = ["symbol", "close", "rs_rank", "atr_pct", "side", "setup", "trigger", "stop", "earn_days"]


@pytest.fixture
def desk(home: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ts.prepare(home, monkeypatch)
    return home


def _rows(draft: Draft) -> list[list[Any]]:
    assert draft.data is not None and draft.data.rows is not None
    return draft.data.rows


def _nulls(draft: Draft) -> dict[str, str]:
    assert draft.data is not None
    return draft.data.nulls or {}


def _column(draft: Draft, name: str) -> list[Any]:
    assert draft.data is not None
    cols = draft.data.cols or ALL
    return [row[cols.index(name)] for row in _rows(draft)]


def _refusal(draft: Draft) -> str:
    assert draft.type == "reply" and draft.verdict is not None
    assert draft.verdict.result == "refused" and draft.data is None
    return draft.verdict.reason or ""


# ── one reply per ask (SRD-DSK-012.018) ──────────────────────────────────────


def test_one_reply_per_ask(desk: Path) -> None:
    """UT-DSK-012.018.M34.T01: One reply per ask."""
    mid = ts.ask(desk)
    ctx = ts.act(desk, mid)
    assert [(d.type, d.parent) for d in ctx.drafts] == [("reply", mid)]
    assert ctx.asked == 0
    assert len(_rows(ctx.drafts[0])) == 6


def test_not_an_ask(desk: Path) -> None:
    """UT-DSK-012.018.M34.T02: Not an ask."""
    first = ts.act(desk, ts.ask(desk))
    stored = accept(desk, first.drafts, ts.PLANNER, ts.ROSTER, ts.NOW, ts.DAY)
    reply_id = int(stored[0].split("#")[1])
    assert ts.act(desk, reply_id).drafts == []
    assert ts.act(desk, 999).drafts == []


def test_two_asks(desk: Path) -> None:
    """UT-DSK-012.018.M34.T03: Two asks."""
    one, two = ts.ask(desk, ["AVGO"]), ts.ask(desk, ["MU", "NVDA"])
    ctx = ts.act(desk, one, two)
    assert [d.parent for d in ctx.drafts] == [one, two]
    assert [len(_rows(d)) for d in ctx.drafts] == [1, 2]


def test_work_error(desk: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-DSK-012.018.M34.T05: Work error."""
    real, seen = planner._merge, []

    def broken(*args: Any) -> Any:
        seen.append(1)
        if len(seen) == 1:
            raise RuntimeError("bad merge")
        return real(*args)

    monkeypatch.setattr(planner, "_merge", broken)
    one, two = ts.ask(desk, ["AVGO"]), ts.ask(desk, ["MU"])
    ctx = ts.act(desk, one, two)
    first, second = ctx.drafts
    assert first.parent == one and first.verdict is not None
    assert (first.verdict.result, first.text) == ("failed", planner.ERROR)
    assert second.parent == two and second.verdict is not None
    assert second.verdict.result == "done"
    cards = {c.message: c for c in card_rows(desk)}
    assert (cards[one].status, cards[one].reason) == ("failed", planner.ERROR)
    assert cards[two].status == "done"
    stored = accept(desk, ctx.drafts, ts.PLANNER, ts.ROSTER, ts.NOW, ts.DAY)
    assert [s.split(" ")[0] for s in stored] == ["stored", "stored"]


# ── refusals (SRD-DSK-012.019) ───────────────────────────────────────────────


def test_no_format_named(desk: Path) -> None:
    """UT-DSK-012.019.M34.T01: No format named."""
    for draft in (ts.answer(desk, want=False), ts.answer(desk, schema=None)):
        why = _refusal(draft)
        assert "no table format named" in why and "setup_table.v1" in why


def test_no_plan(desk: Path) -> None:
    """UT-DSK-012.019.M34.T02: No plan."""
    assert _refusal(ts.answer(desk, schema="scores.v1")) == "no ready plan for scores.v1"
    assert _refusal(ts.answer(desk, schema="nothing.v9")) == "no ready plan for nothing.v9"


def test_unknown_column(desk: Path) -> None:
    """UT-DSK-012.019.M34.T03: Unknown column."""
    why = _refusal(ts.answer(desk, cols=["rs_rank", "volume"]))
    assert why == "unknown column volume in setup_table.v1"


def test_bad_symbols(desk: Path) -> None:
    """UT-DSK-012.019.M34.T04: Bad symbols."""
    many = [f"S{n}" for n in range(31)]
    for symbols in ([], "AVGO", [1, 2], many):
        assert _refusal(ts.answer(desk, symbols=symbols)) == "give 1 to 30 symbols in inputs.symbols"


def test_symbols_cleaned(desk: Path) -> None:
    """UT-DSK-012.019.M34.T05: Symbols cleaned."""
    draft = ts.answer(desk, symbols=["mu", "MU", " avgo ", ""])
    assert _column(draft, "symbol") == ["MU", "AVGO"]
    assert card_rows(desk)[0].keys == ("MU", "AVGO")


def test_refusal_makes_no_card(desk: Path) -> None:
    """UT-DSK-012.019.M34.T06: Refusal makes no card."""
    _refusal(ts.answer(desk, schema="scores.v1"))
    assert card_rows(desk) == []


# ── unmade columns (SRD-DSK-012.020) ─────────────────────────────────────────


def test_unmade_column_in_reply(desk: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-DSK-012.020.M34.T01: Unmade column in the reply."""
    left = {name: path for name, path in ts.PATHS.items() if name != "calendar.earnings"}
    monkeypatch.setattr(desk_steps, "TOOL_PATHS", left)
    fill_registry(desk, ts.NOW)
    fill_plans(desk, ts.NOW)
    draft = ts.answer(desk, symbols=["AVGO", "MU"])
    assert _column(draft, "earn_days") == [None, None]
    assert _nulls(draft)["earn_days"] == "not available"
    assert _column(draft, "rs_rank") == [80, 81]
    assert ts.W.called("calendar.earnings") == []


# ── waves (SRD-DSK-012.022) ──────────────────────────────────────────────────


def test_wave_two_gets_wave_one_keys(desk: Path) -> None:
    """UT-DSK-012.022.M34.T01: Wave 2 gets wave 1 keys."""
    ts.answer(desk, symbols=["AVGO", "ZZZZ", "MU"])
    assert ts.W.called("data.daily_close") == [("AVGO", "ZZZZ", "MU")]
    for tool in ("technical.rs_rank", "technical.atr_pct", "technical.setup",
                 "calendar.earnings"):
        assert ts.W.called(tool) == [("AVGO", "MU")]


def test_no_key_no_wave_two(desk: Path) -> None:
    """UT-DSK-012.022.M34.T02: No key, no wave 2."""
    draft = ts.answer(desk, symbols=["ZZZZ", "YYYY"])
    assert draft.verdict is not None and draft.verdict.result == "failed"
    assert draft.verdict.reason == draft.text == "no asked symbol has data: no daily bars"
    assert [name for name, _ in ts.W.calls] == ["data.daily_close"]
    parts = card_rows(desk)[0].parts
    assert [(p.id, p.status) for p in parts] == [("A", "ok"), ("B", "skipped"),
                                                 ("C", "skipped")]


# ── merge and check (SRD-DSK-012.024) ────────────────────────────────────────


def test_merge_in_asked_order(desk: Path) -> None:
    """UT-DSK-012.024.M34.T01: Merge in asked order."""
    draft = ts.answer(desk, symbols=["NVDA", "AVGO", "MU"])
    assert draft.data is not None and draft.data.cols is None
    assert _rows(draft) == [
        ["NVDA", 100.0, 80, 2.5, "long", "flag", 10.0, 9.0, 12],
        ["AVGO", 101.0, 81, 2.5, "long", "flag", 10.0, 9.0, 12],
        ["MU", 102.0, 82, 2.5, "long", "flag", 10.0, 9.0, 12]]


def test_wrong_value(desk: Path) -> None:
    """UT-DSK-012.024.M34.T02: Wrong value."""
    ts.W.wrong.add("technical.rs_rank")
    draft = ts.answer(desk, symbols=["AVGO"])
    assert _column(draft, "rs_rank") == [None]
    assert _nulls(draft)["AVGO.rs_rank"] == "wrong value from technical.rs_rank"
    assert draft.verdict is not None and draft.verdict.result == "partial"
    assert "1 wrong value left empty" in (draft.verdict.reason or "")


def test_missing_key(desk: Path) -> None:
    """UT-DSK-012.024.M34.T03: Missing key."""
    draft = ts.answer(desk, symbols=["AVGO", "ZZZZ", "MU"])
    assert _column(draft, "symbol") == ["AVGO", "MU"]
    assert _nulls(draft)["ZZZZ"] == "no daily bars"
    assert draft.verdict is not None and draft.verdict.result == "partial"
    assert draft.verdict.reason == "1 of 3 symbols not found"


def test_some_columns_only(desk: Path) -> None:
    """UT-DSK-012.024.M34.T04: Some columns only."""
    draft = ts.answer(desk, symbols=["AVGO"], cols=["earn_days", "rs_rank"])
    assert draft.data is not None and draft.data.cols == ["symbol", "rs_rank", "earn_days"]
    assert _rows(draft) == [["AVGO", 80, 12]]
    assert ts.W.called("technical.setup") == [] and ts.W.called("technical.atr_pct") == []


# ── reply (SRD-DSK-012.025) ──────────────────────────────────────────────────


def test_done_reply(desk: Path) -> None:
    """UT-DSK-012.025.M34.T01: Done reply."""
    ts.W.near.update(dict.fromkeys(ts.SIX, 2))
    ctx = ts.act(desk, ts.ask(desk))
    draft = ctx.drafts[0]
    assert draft.verdict is not None and draft.verdict.result == "done"
    assert draft.verdict.reason is None and draft.data is not None and not draft.data.nulls
    assert draft.flags is not None and len(draft.flags) == 5
    assert draft.flags[0].about == "AVGO" and "earnings in 2" in draft.flags[0].note
    stored = accept(desk, ctx.drafts, ts.PLANNER, ts.ROSTER, ts.NOW, ts.DAY)
    assert stored[0].startswith("stored")


def test_partial_reply(desk: Path) -> None:
    """UT-DSK-012.025.M34.T02: Partial reply."""
    ts.W.raises["calendar.earnings"] = 2
    ctx = ts.act(desk, ts.ask(desk, ["AVGO", "MU"]))
    draft = ctx.drafts[0]
    assert draft.verdict is not None and draft.verdict.result == "partial"
    assert draft.verdict.reason == f"Calendar tools failed: {ts.TIMED_OUT}"
    assert _column(draft, "earn_days") == [None, None]
    assert _nulls(draft) == {"earn_days": ts.TIMED_OUT}
    assert _column(draft, "rs_rank") == [80, 81] and _column(draft, "close") == [100.0, 101.0]
    assert accept(desk, ctx.drafts, ts.PLANNER, ts.ROSTER, ts.NOW, ts.DAY)[0].startswith("stored")


def test_failed_reply(desk: Path) -> None:
    """UT-DSK-012.025.M34.T03: Failed reply."""
    ts.W.raises["data.daily_close"] = 2
    ctx = ts.act(desk, ts.ask(desk, ["AVGO", "MU"]))
    draft = ctx.drafts[0]
    assert draft.verdict is not None and draft.verdict.result == "failed"
    assert draft.data is None and draft.text == f"Data tools failed: {ts.TIMED_OUT}"
    assert card_rows(desk)[0].status == "failed"
    assert accept(desk, ctx.drafts, ts.PLANNER, ts.ROSTER, ts.NOW, ts.DAY)[0].startswith("stored")


def test_explained_empty_value(desk: Path) -> None:
    """UT-DSK-012.025.M34.T04: Explained empty value."""
    ts.W.no_earnings.add("MU")
    draft = ts.answer(desk, symbols=["AVGO", "MU"])
    assert draft.verdict is not None and draft.verdict.result == "done"
    assert _column(draft, "earn_days") == [12, None]
    assert _nulls(draft) == {"MU.earn_days": "no earnings date found"}


# ── failure log (SRD-DSK-012.026) ────────────────────────────────────────────


def test_refusal_and_failed_part_logged(desk: Path) -> None:
    """UT-DSK-012.026.M34.T01: Refusal and failed part logged."""
    ts.answer(desk, schema="scores.v1")
    ts.W.raises["calendar.earnings"] = 2
    ts.answer(desk, symbols=["AVGO"])
    rows = failure_rows(desk)
    assert [(m.owner, m.kind, m.made) for m in rows] == [(ts.PLANNER, "failure", ts.DAY)] * 2
    assert [m.text for m in rows] == [
        f"setup_table.v1: Calendar tools failed: {ts.TIMED_OUT}",
        "Ask refused: no ready plan for scores.v1"]


def test_off_logs_nothing(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-DSK-012.026.M34.T02: Off logs nothing."""
    ts.prepare(home, monkeypatch, on=False)
    ts.answer(home)
    assert failure_rows(home) == []


# ── retire (SRD-DSK-012.027) ─────────────────────────────────────────────────


def _alert_kinds(home: Path) -> list[tuple[str, str]]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute("SELECT kind, source FROM alerts").fetchall()
    finally:
        con.close()


def test_alert_and_refusal_after_retire(desk: Path) -> None:
    """UT-DSK-012.027.M34.T01: Alert and refusal after retire."""
    sent: list[str] = []
    for _ in range(3):
        ts.W.raises["calendar.earnings"] = 2
        draft = ts.answer(desk, sent=sent, symbols=["AVGO"])
        assert draft.verdict is not None and draft.verdict.result == "partial"
    plan = get_plan(desk, ts.FORMAT)
    assert plan is not None and plan.status == "retired" and plan.why == ts.TIMED_OUT
    assert _alert_kinds(desk) == [("plan_retired", ts.FORMAT)]
    assert len(sent) == 1 and "Table plan retired" in sent[0]
    calls = len(ts.W.calls)
    why = _refusal(ts.answer(desk, sent=sent, symbols=["AVGO"]))
    assert why == f"the plan for setup_table.v1 is retired: {ts.TIMED_OUT}"
    assert len(ts.W.calls) == calls and len(sent) == 1
    assert [a.kind for a in open_alerts(desk, ts.NOW)] == ["plan_retired"]
    fill_plans(desk, ts.NOW)
    assert open_alerts(desk, ts.NOW) == []


def test_missing_key_is_no_failure(desk: Path) -> None:
    """UT-DSK-012.027.M34.T02: Missing key is no failure."""
    for _ in range(3):
        ts.answer(desk, symbols=["AVGO", "ZZZZ"])
    plan = get_plan(desk, ts.FORMAT)
    assert plan is not None and plan.status == "active" and plan.fails == 0
    assert open_alerts(desk, ts.NOW) == []


# ── switch (SRD-DSK-012.028) ─────────────────────────────────────────────────


def test_off_refuses(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-DSK-012.028.M34.T01: Off refuses."""
    ts.prepare(home, monkeypatch, on=False)
    assert _refusal(ts.answer(home)) == "task cards are off"
    assert card_rows(home) == [] and ts.W.calls == []


# ── logs (SRD-DSK-012.031) ───────────────────────────────────────────────────


def test_log_lines(desk: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-DSK-012.031.M34.T01: Log lines."""
    caplog.set_level(logging.INFO, logger="us_swing.desk.planner")
    ts.answer(desk, symbols=["AVGO", "MU"])
    ts.answer(desk, schema="scores.v1")
    for _ in range(3):
        ts.W.raises["calendar.earnings"] = 2
        ts.answer(desk, symbols=["AVGO"])
    text = caplog.text
    assert "[Task cards] Card 1 for Quill: setup_table.v1, 2 stock(s), done in" in text
    assert "[Task cards] Ask from Quill refused: no ready plan for scores.v1" in text
    assert f"[Task cards] Card 2 for Quill is partial: Calendar tools failed: {ts.TIMED_OUT}" \
        in text
    assert "[Task cards] Plan for setup_table.v1 retired after 3 failed cards" in text
    assert "emp-a" not in text
