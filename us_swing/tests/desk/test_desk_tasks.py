"""Tests for MD-DSK-012.016.M32 (core/desk_tasks.py): table plans, task cards and their reads."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from us_swing.core.desk_registry import (
    Column,
    TableFormat,
    fill_registry,
    seed_formats,
    seed_tools,
)
from us_swing.core.desk_tasks import (
    STOPPED,
    CardPart,
    card_rows,
    close_card,
    close_open_cards,
    fill_plans,
    get_plan,
    group_label,
    group_of,
    make_plan,
    note_result,
    open_card,
    plan_rows,
    ready_formats,
)

NOW = datetime(2026, 11, 13, 9, 0, tzinfo=ZoneInfo("America/New_York"))
FORMAT = "setup_table.v1"


def _format(format_id: str) -> TableFormat:
    return next(f for f in seed_formats() if f.id == format_id)


def _ready(home: Path) -> None:
    fill_registry(home, NOW)
    fill_plans(home, NOW)


def _retire(home: Path, why: str = "connection timed out") -> list[bool]:
    return [note_result(home, FORMAT, True, why, NOW) for _ in range(3)]


# ── plans (SRD-DSK-012.016, .020) ────────────────────────────────────────────


def test_plan_of_the_setup_table() -> None:
    """UT-DSK-012.016.M32.T01: Plan of the setup table."""
    plan = make_plan(_format(FORMAT), seed_tools())
    assert plan is not None and plan.format == FORMAT and plan.unmade == ()
    first, *rest = plan.parts
    assert (first.id, first.wave, first.group) == ("A", 1, "data")
    assert first.tools == {"data.daily_close": ["symbol", "close"]}
    assert [(p.id, p.wave, p.group) for p in rest] == [("B", 2, "calendar"),
                                                      ("C", 2, "technical")]
    assert rest[0].tools == {"calendar.earnings": ["earn_days"]}
    assert rest[1].tools == {"technical.atr_pct": ["atr_pct"], "technical.rs_rank": ["rs_rank"],
                             "technical.setup": ["side", "setup", "trigger", "stop"]}


def test_no_key_tool_no_plan() -> None:
    """UT-DSK-012.016.M32.T02: No key tool, no plan."""
    tools = seed_tools()
    assert make_plan(_format("scores.v1"), tools) is None
    off = [t.model_copy(update={"status": "off"}) if t.name == "data.daily_close" else t
           for t in tools]
    assert make_plan(_format(FORMAT), off) is None


def test_plans_filled(home: Path) -> None:
    """UT-DSK-012.016.M32.T03: Plans filled."""
    fill_registry(home, NOW)
    assert fill_plans(home, NOW) == 1
    assert fill_plans(home, NOW + timedelta(minutes=1)) == 1
    plans = plan_rows(home)
    assert [(p.format, p.status, p.fails) for p in plans] == [(FORMAT, "active", 0)]
    assert get_plan(home, "scores.v1") is None
    assert get_plan(home, FORMAT) == plans[0]


def test_fill_wakes_a_retired_plan(home: Path) -> None:
    """UT-DSK-012.016.M32.T04: Fill wakes a retired plan."""
    _ready(home)
    _retire(home)
    fill_plans(home, NOW)
    plan = get_plan(home, FORMAT)
    assert plan is not None and (plan.status, plan.fails, plan.why) == ("active", 0, "")


def test_unmade_column_in_the_plan() -> None:
    """UT-DSK-012.020.M32.T01: Unmade column in the plan."""
    fmt = TableFormat(id="mix.v1", title="Mix", columns=[
        Column(name="symbol", type="text", meaning="stock", by="data.daily_close"),
        Column(name="rs_rank", type="number", meaning="rank", by="technical.rs_rank"),
        Column(name="earn_days", type="number", meaning="days", by="calendar.earnings"),
        Column(name="note", type="text", meaning="free note")])
    tools = [t.model_copy(update={"status": "off"}) if t.name == "calendar.earnings" else t
             for t in seed_tools()]
    plan = make_plan(fmt, tools)
    assert plan is not None and plan.unmade == ("earn_days", "note")
    made = {col for part in plan.parts for cols in part.tools.values() for col in cols}
    assert made == {"symbol", "rs_rank"}


def test_group_of_a_tool() -> None:
    """UT-DSK-012.021.M32.T01: Group of a tool."""
    assert group_of("technical.rs_rank") == "technical"
    assert group_label("calendar") == "Calendar tools"


# ── cards (SRD-DSK-012.017) ──────────────────────────────────────────────────


def _parts() -> list[CardPart]:
    return [CardPart(id="A", wave=1, group="data", tools=["data.daily_close"],
                     cols=["symbol", "close"], rows=2, status="ok", secs=0.2),
            CardPart(id="B", wave=2, group="calendar", tools=["calendar.earnings"],
                     cols=["earn_days"], status="failed", secs=3.0, reason="connection timed out")]


def test_card_row(home: Path) -> None:
    """UT-DSK-012.017.M32.T01: Card row."""
    card_id = open_card(home, 7, "emp-a", "emp-p", FORMAT, ["symbol", "earn_days"],
                        ["AVGO", "MU"], NOW)
    assert close_card(home, card_id, "partial", _parts(), 2,
                      "Calendar tools failed: connection timed out",
                      NOW + timedelta(seconds=3), 3.214)
    card = card_rows(home)[0]
    assert (card.id, card.message, card.asker, card.planner, card.format) == (
        card_id, 7, "emp-a", "emp-p", FORMAT)
    assert card.cols == ("symbol", "earn_days") and card.keys == ("AVGO", "MU")
    assert (card.status, card.rows, card.secs) == ("partial", 2, 3.21)
    assert card.reason == "Calendar tools failed: connection timed out"
    assert card.made == "2026-11-13T09:00:00-05:00" and card.ended == "2026-11-13T09:00:03-05:00"
    assert list(card.parts) == _parts()


def test_card_left_open(home: Path) -> None:
    """UT-DSK-012.017.M32.T02: Card left open."""
    open_card(home, 7, "emp-a", "emp-p", FORMAT, ["symbol"], ["AVGO"], NOW)
    card = card_rows(home)[0]
    assert (card.status, card.ended, card.secs, card.parts) == ("working", None, None, ())


def test_cards_left_working(home: Path) -> None:
    """UT-DSK-012.017.M32.T04: Cards left working."""
    working = open_card(home, 7, "emp-a", "emp-p", FORMAT, ["symbol"], ["AVGO"], NOW)
    done = open_card(home, 8, "emp-a", "emp-p", FORMAT, ["symbol"], ["MU"], NOW)
    close_card(home, done, "done", [], 1, "", NOW, 0.5)
    assert close_open_cards(home, NOW + timedelta(minutes=5)) == 1
    cards = {c.id: c for c in card_rows(home)}
    assert (cards[working].status, cards[working].reason) == ("failed", STOPPED)
    assert cards[working].ended == "2026-11-13T09:05:00-05:00"
    assert cards[done].status == "done"
    assert close_open_cards(home, NOW) == 0


def test_unknown_card(home: Path) -> None:
    """UT-DSK-012.017.M32.T03: Unknown card."""
    assert close_card(home, 99, "done", [], 0, "", NOW, 0.1) is False
    assert card_rows(home) == []


# ── retire (SRD-DSK-012.027) ─────────────────────────────────────────────────


def test_retire_at_three(home: Path) -> None:
    """UT-DSK-012.027.M32.T01: Retire at 3."""
    _ready(home)
    assert _retire(home, "feed is down") == [False, False, True]
    plan = get_plan(home, FORMAT)
    assert plan is not None and (plan.status, plan.fails, plan.why) == ("retired", 3,
                                                                        "feed is down")
    assert note_result(home, FORMAT, True, "again", NOW) is False
    assert note_result(home, "scores.v1", True, "no plan", NOW) is False


def test_clean_card_resets(home: Path) -> None:
    """UT-DSK-012.027.M32.T02: Clean card resets."""
    _ready(home)
    for failed in (True, True, False, True):
        assert note_result(home, FORMAT, failed, "feed is down", NOW) is False
    plan = get_plan(home, FORMAT)
    assert plan is not None and (plan.status, plan.fails, plan.why) == ("active", 1, "")


# ── reads (SRD-DSK-012.030) ──────────────────────────────────────────────────


def test_reads(home: Path) -> None:
    """UT-DSK-012.030.M32.T01: Reads."""
    _ready(home)
    ids = [open_card(home, n, "emp-a", "emp-p", FORMAT, ["symbol"], ["AVGO"], NOW)
           for n in (1, 2, 3)]
    assert [p.format for p in plan_rows(home)] == [FORMAT]
    assert [c.id for c in card_rows(home)] == ids[::-1]
    assert [c.id for c in card_rows(home, limit=2)] == ids[:0:-1]


def test_retired_plan_is_not_ready(home: Path) -> None:
    """UT-DSK-012.030.M32.T02: Retired plan is not ready."""
    _ready(home)
    assert [f.id for f in ready_formats(home)] == [FORMAT]
    _retire(home)
    assert ready_formats(home) == []


def test_no_data(home: Path) -> None:
    """UT-DSK-012.030.M32.T03: No data."""
    assert plan_rows(home) == [] and card_rows(home) == [] and ready_formats(home) == []
    assert get_plan(home, FORMAT) is None
    assert not home.exists()
