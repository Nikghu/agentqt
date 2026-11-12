"""Tests for strategy test research (FO-MKT-019): recipe, replay, store, skill and employee."""
from __future__ import annotations

import inspect
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from pydantic import ValidationError

from tests.market.p5b_support import FakeCtx
from us_swing.core.desk_cards import (
    HEADER,
    CardTest,
    card,
    card_id_of,
    latest_tests,
    open_test_cards,
    save_test,
    untested_block,
)
from us_swing.core.desk_steps import DEFAULT_EMPLOYEE_PACKAGES, SKILL_PATHS
from us_swing.core.indicator_rules import BarArrays
from us_swing.core.desk_research import OWNER_TEST_CAP, StepResult, Ticket
from us_swing.data.market_calendar import ET
from us_swing.desk.registry import default_folders, load_employee
from us_swing.market import strategy_test as st_module
from us_swing.market.book_cards import CardText, save_card
from us_swing.market.card_recipe import (
    IndicatorBlock,
    PatternBlock,
    Recipe,
    StopBlock,
    block_menu,
    check_recipe,
)
from us_swing.market.card_replay import (
    WARMUP,
    Stock,
    TooSlow,
    Trade,
    baseline,
    levels,
    load_data,
    replay,
    score,
)
from us_swing.market.strategy_test import StrategyTestSkill, CardVerdict

NOW = datetime(2026, 11, 12, 12, 0, tzinfo=ET)
N = WARMUP + 60
SIGNAL = WARMUP + 10
SPEC = Path(__file__).resolve().parents[2] / "USSwing.spec"


def _recipe(**kw: Any) -> Recipe:
    base: dict[str, Any] = {
        "side": "long",
        "indicators": [IndicatorBlock(id="volume_ratio", condition="at_least", value=3.0)],
        "patterns": [], "entry": "next_open", "stop": StopBlock(kind="percent", n=5)}
    base.update(kw)
    return Recipe(**base)


def _stock(spikes: tuple[int, ...] = (SIGNAL,), rise_at: int | None = SIGNAL + 3,
           symbol: str = "AAA") -> Stock:
    close = np.full(N, 100.0)
    high, low, open_ = close + 0.5, close - 0.5, close.copy()
    volume = np.full(N, 1_000.0)
    for s in spikes:
        volume[s] = 10_000.0
    if rise_at is not None:
        high[rise_at] = 111.0
    days = tuple(f"2025-{1 + i // 28:02d}-{1 + i % 28:02d}" if i < 336 else f"x{i}"
                 for i in range(N))
    return Stock(symbol, days, BarArrays(open_, high, low, close, volume))


# ── recipe (M02) ──────────────────────────────────────────────────────────


def test_block_menu() -> None:
    """UT-MKT-019.003.M02.T01: The menu lists daily blocks only."""
    menu = block_menu()
    assert "- rsi:" in menu and "- bull_flag" in menu
    for gone in ("rvol_3m", "market_cap", "rs_index"):
        assert f"- {gone}" not in menu


def test_bad_recipe_answer() -> None:
    """UT-MKT-019.003.M02.T02: A bad answer is refused by the model check."""
    with pytest.raises(ValidationError):
        _recipe(side="both")
    with pytest.raises(ValidationError):
        Recipe.model_validate({**_recipe().model_dump(), "extra": 1})
    with pytest.raises(ValidationError):
        _recipe(indicators=[IndicatorBlock(id="rsi", condition="at_most", value=30)] * 5)


def test_good_recipe() -> None:
    """UT-MKT-019.004.M02.T01: A recipe of known blocks has no problems."""
    recipe = _recipe(indicators=[IndicatorBlock(id="rsi", condition="at_most", value=30)],
                     patterns=[PatternBlock(id="hammer")], stop=StopBlock(kind="atr", n=2))
    assert check_recipe(recipe) == []


def test_unmapped_part() -> None:
    """UT-MKT-019.004.M02.T02: An unmapped card part is named."""
    assert check_recipe(_recipe(unmapped=["earnings date"])) == ["earnings date has no block"]


def test_unknown_and_intraday_block() -> None:
    """UT-MKT-019.004.M02.T03: Unknown and intraday blocks are named."""
    problems = check_recipe(_recipe(indicators=[
        IndicatorBlock(id="moon_phase", condition="at_least", value=1),
        IndicatorBlock(id="rvol_3m", condition="at_least", value=2)]))
    assert problems == ["moon_phase has no block", "rvol_3m has no block"]


def test_out_of_range() -> None:
    """UT-MKT-019.004.M02.T04: Value, stop and empty entry problems are all named."""
    problems = check_recipe(_recipe(indicators=[], stop=StopBlock(kind="atr", n=9)))
    assert problems == ["the entry has no block", "the atr stop 9 is outside 0.5-5"]
    bad = check_recipe(_recipe(indicators=[IndicatorBlock(id="rsi", condition="at_least",
                                                          value=150)]))
    assert bad == ["rsi value is outside 0 to 100"]


# ── replay and score (M03) ────────────────────────────────────────────────


def test_replay_trade() -> None:
    """UT-MKT-019.005.M03.T01: One signal gives one +2R trade on the right day."""
    trades = replay(_recipe(), [_stock()])
    assert trades == [Trade("AAA", _stock().days[SIGNAL], 2.0)]


def test_one_trade_per_stock() -> None:
    """UT-MKT-019.005.M03.T02: Signals while a trade is open add no trade."""
    trades = replay(_recipe(), [_stock(spikes=(SIGNAL, SIGNAL + 1, SIGNAL + 2))])
    assert len(trades) == 1


def test_entry_and_stop_types() -> None:
    """UT-MKT-019.005.M03.T03: Triggers and stops follow the recipe."""
    a = _stock().arrays
    assert levels(_recipe(), a, SIGNAL) == (100.0, 95.0, 110.0)
    brk = levels(_recipe(entry="signal_break", stop=StopBlock(kind="signal_bar")), a, SIGNAL)
    assert brk == (100.5, 99.5, 102.5)
    nday = levels(_recipe(stop=StopBlock(kind="n_day", n=5)), a, SIGNAL)
    assert nday is not None and nday[1] == 99.5
    atr = levels(_recipe(stop=StopBlock(kind="atr", n=2)), a, SIGNAL)
    assert atr is not None and atr[1] == pytest.approx(98.0)
    short = levels(_recipe(side="short"), a, SIGNAL)
    assert short == (100.0, 105.0, 90.0)


def test_no_backtest_data(tmp_path: Path) -> None:
    """UT-MKT-019.005.M03.T04: No data gives an empty list and a failed ticket."""
    assert load_data(tmp_path) == []
    skill = StrategyTestSkill(lambda: NOW, lambda: [])
    state = {"phase": "replay", "card": 1, "recipe": _recipe().model_dump()}
    result = skill.step(FakeCtx(tmp_path, None), _ticket(state=state))
    assert result is not None and result.outcome == "failed"
    assert "Backtest Data" in result.note


def test_baseline_same_sample() -> None:
    """UT-MKT-019.006.M03.T01: The baseline is the same on every run."""
    data = [_stock(), _stock(symbol="BBB", rise_at=None)]
    assert baseline(_recipe(), data) == baseline(_recipe(), data)
    assert len(baseline(_recipe(), data)) > 0


def test_baseline_skips_bad_levels() -> None:
    """UT-MKT-019.006.M03.T02: A day whose stop is past the trigger gives no trade."""
    stock = _stock()
    stock.arrays.open[WARMUP + 1] = 90.0
    recipe = _recipe(stop=StopBlock(kind="signal_bar"))
    assert levels(recipe, stock.arrays, WARMUP) is None
    assert all(t.day != stock.days[WARMUP] for t in baseline(recipe, [stock]))


def _trades(rs: list[float]) -> list[Trade]:
    return [Trade("AAA", f"2025-01-{i + 1:02d}" if i < 28 else f"2025-02-{i - 27:02d}", r)
            for i, r in enumerate(rs)]


def test_pass_rule() -> None:
    """UT-MKT-019.007.M03.T01: 30 trades at +0.25R over a 0.0 baseline pass."""
    s = score(_trades([0.25] * 30), _trades([0.0] * 10))
    assert s.passed and s.trades == 30 and s.avg_r == 0.25


def test_fail_cases() -> None:
    """UT-MKT-019.007.M03.T02: Too few trades, 0.2R, or below baseline fail."""
    assert not score(_trades([0.5] * 29), []).passed
    assert not score(_trades([0.2] * 40), []).passed
    assert not score(_trades([0.3] * 40), _trades([0.35] * 5)).passed


def test_worst_run() -> None:
    """UT-MKT-019.007.M03.T03: Worst losing run and win rate."""
    s = score(_trades([-1, -1, 2, -1, -1, -1]), [])
    assert s.worst_run == 3 and s.win_rate == pytest.approx(1 / 6)


# ── store (M04) ───────────────────────────────────────────────────────────


def _card(home: Path, name: str = "Volume breakout", chapter: int = 2) -> int:
    return save_card(home, "upload:book.txt", chapter, 1,
                     CardText(name, "Buy strength", "Rising", "Break on volume", "2R",
                              "5% below", ("Buy when the price breaks",)), "2026-11-12T09:00")


def test_card_from_topic(tmp_path: Path) -> None:
    """UT-MKT-019.002.M04.T01: The card id comes from the topic and the card is found."""
    for i in range(12):
        _card(tmp_path, f"Card {i}", i + 1)
    assert card_id_of("sc-12") == 12 and card_id_of("hello") is None
    found = card(tmp_path, 12)
    assert found is not None and found.name == "Card 11"
    assert found.quotes == ("Buy when the price breaks",)


def test_save_and_latest(tmp_path: Path) -> None:
    """UT-MKT-019.009.M04.T01: The latest test of a card wins."""
    save_test(tmp_path, CardTest(1, 5, "a", "fail"))
    save_test(tmp_path, CardTest(1, 6, "b", "pass", trades=40))
    assert latest_tests(tmp_path)[1].ticket_id == 6


def test_untested_block(tmp_path: Path) -> None:
    """UT-MKT-019.011.M04.T01: At most 8 lines, topic form, tested card left out."""
    ids = [_card(tmp_path, f"Card {i}", i + 1) for i in range(12)]
    save_test(tmp_path, CardTest(ids[-1], 5, "a", "pass"))
    block = untested_block(tmp_path).splitlines()
    assert len(block) == 8 and "SC-<n>" in block[0]
    assert f"SC-{ids[-1]}:" not in "\n".join(block) and block[1].startswith(f"SC-{ids[-2]}:")


def _open_ticket(home: Path, topic: str, status: str) -> None:
    from us_swing.core.desk_research import connect  # noqa: PLC0415

    con = connect(home)
    with con:
        con.execute("INSERT INTO tickets (kind, topic, goal, done_test, token_cap, raised_by, "
                    "raised_by_name, status, made) VALUES ('strategy_test', ?, 'g', 'd', "
                    "5000, 'l-1', 'Lead', ?, '2026-11-12')", (topic, status))
    con.close()


def test_open_tests(tmp_path: Path) -> None:
    """UT-MKT-019.011.M04.T02: Only open tickets count as open tests."""
    _open_ticket(tmp_path, "SC-2", "approved")
    _open_ticket(tmp_path, "SC-3", "done")
    assert open_test_cards(tmp_path) == {2}


def test_no_cards_block(tmp_path: Path) -> None:
    """UT-MKT-019.011.M04.T03: No desk.db, or all cards tested, gives an empty block."""
    assert untested_block(tmp_path / "none") == ""
    cid = _card(tmp_path)
    save_test(tmp_path, CardTest(cid, 1, "a", "fail"))
    assert untested_block(tmp_path) == ""


# ── skill (M01) ───────────────────────────────────────────────────────────


def _ticket(topic: str = "SC-1", state: dict[str, Any] | None = None) -> Ticket:
    return Ticket(
        id=9, kind="strategy_test", topic=topic, goal="Test the card on all data",
        done_test="Pass or fail by code", token_cap=10_000, step_cap=8, time_cap_min=60,
        raised_by="l-1", raised_by_name="Lead A", status="running",
        made="2026-11-12T09:00:00-05:00", approved_by="master", approved=None, started=None,
        ended=None, tokens=0, steps=0, biggest=0, quiet_steps=0, last_call="",
        state=json.dumps(state or {}), result="", end_reason="", gain=None, updated=None)


def _data(passing: bool) -> list[Stock]:
    rise = SIGNAL + 3 if passing else None
    return [_stock(rise_at=rise, symbol=f"S{i:02d}") for i in range(35)]


def _run(home: Path, recipe: Recipe | None, verdict: CardVerdict | None,
         passing: bool = True) -> list[StepResult]:
    skill = StrategyTestSkill(lambda: NOW, lambda: _data(passing))
    ctx = FakeCtx(home, recipe)
    out: list[StepResult] = []
    state: dict[str, Any] = {}
    for _ in range(4):
        result = skill.step(ctx, _ticket(state=state))
        assert result is not None
        out.append(result)
        if result.outcome != "go" or not result.state:
            break
        state = result.state
        if state.get("phase") == "verdict":
            ctx.answer = verdict
    return out


VERDICT = CardVerdict(verdict="The card made money often.\nLosses were small.")


def _query(home: Path, sql: str) -> list[Any]:
    con = sqlite3.connect(home / "desk.db")
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def test_four_steps(tmp_path: Path) -> None:
    """UT-MKT-019.001.M01.T01: Recipe, check, replay and verdict end done."""
    _card(tmp_path)
    steps = _run(tmp_path, _recipe(), VERDICT)
    assert [s.call for s in steps] == ["recipe", "check", "replay", "verdict"]
    assert steps[-1].outcome == "done"


def test_no_recipe_answer(tmp_path: Path) -> None:
    """UT-MKT-019.001.M01.T02: No answer at recipe waits for the next tick."""
    _card(tmp_path)
    steps = _run(tmp_path, None, VERDICT)
    assert steps[0].note == "" and steps[0].outcome == "go" and not steps[0].state


def test_missing_card(tmp_path: Path) -> None:
    """UT-MKT-019.002.M01.T01: A missing card or bad topic fails before any AI call."""
    skill = StrategyTestSkill(lambda: NOW, lambda: [])
    for topic in ("SC-99", "hello"):
        ctx = FakeCtx(tmp_path, _recipe())
        result = skill.step(ctx, _ticket(topic))
        assert result is not None and result.outcome == "failed" and ctx.asked == []


def test_cant_test_ends(tmp_path: Path) -> None:
    """UT-MKT-019.004.M01.T01: An unmapped part ends the ticket with a can't test row."""
    _card(tmp_path)
    steps = _run(tmp_path, _recipe(unmapped=["earnings date"]), VERDICT)
    assert steps[-1].call == "check" and steps[-1].outcome == "failed"
    assert steps[-1].note.startswith("Can't test: earnings date has no block")
    assert latest_tests(tmp_path)[1].result == "cant_test"


def test_verdict_lines(tmp_path: Path) -> None:
    """UT-MKT-019.008.M01.T01: The result holds the table, pass line and verdict."""
    _card(tmp_path)
    note = _run(tmp_path, _recipe(), VERDICT)[-1].note
    assert "Average R: +2.00" in note and "Result: pass" in note
    assert "Verdict: The card made money often." in note


def test_no_verdict_answer(tmp_path: Path) -> None:
    """UT-MKT-019.008.M01.T02: No verdict answer waits and saves nothing yet."""
    _card(tmp_path)
    steps = _run(tmp_path, _recipe(), None)
    assert steps[-1].call == "verdict" and steps[-1].outcome == "go"
    assert latest_tests(tmp_path) == {}


def test_gain_on_pass(tmp_path: Path) -> None:
    """UT-MKT-019.009.M01.T01: A pass is a gain and saved as pass."""
    _card(tmp_path)
    assert _run(tmp_path, _recipe(), VERDICT)[-1].gain is True
    assert latest_tests(tmp_path)[1].result == "pass"


def test_no_gain_on_fail(tmp_path: Path) -> None:
    """UT-MKT-019.009.M01.T02: A fail is no gain, saved as fail, with no lesson."""
    _card(tmp_path)
    assert _run(tmp_path, _recipe(), VERDICT, passing=False)[-1].gain is False
    assert latest_tests(tmp_path)[1].result == "fail"
    assert _query(tmp_path, "SELECT name FROM sqlite_master WHERE name = 'lessons'") == [] or \
        _query(tmp_path, "SELECT COUNT(*) FROM lessons")[0][0] == 0


def test_lesson_on_pass(tmp_path: Path) -> None:
    """UT-MKT-019.010.M01.T01: A pass adds one candidate lesson naming the card."""
    _card(tmp_path)
    _run(tmp_path, _recipe(), VERDICT)
    texts = [t for (t,) in _query(tmp_path, "SELECT text FROM lessons")]
    assert len(texts) == 1 and "SC-1" in texts[0]


def test_default_employee() -> None:
    """UT-MKT-019.012.M05.T01: emp-017 ships with skill strategy_test, path and build entry."""
    folders = {f.name: f for f in default_folders(DEFAULT_EMPLOYEE_PACKAGES)}
    hire = load_employee(folders["emp-017"], SKILL_PATHS)
    assert hire is not None and hire.spec.skill == "strategy_test"
    assert isinstance(hire.skill, StrategyTestSkill)
    assert "us_swing.market.strategy_test" in SPEC.read_text(encoding="utf-8")


def test_no_hardcoded_name() -> None:
    """UT-MKT-019.012.M05.T02: No employee name or title in the skill code."""
    source = inspect.getsource(st_module)
    assert "Expert 14" not in source and "Strategy tester" not in source


def test_never_live(tmp_path: Path) -> None:
    """UT-MKT-019.013.M01.T01: A full run leaves the strategy and settings files alone."""
    watched = [tmp_path / "strategies.json", tmp_path / "settings.json"]
    for path in watched:
        path.write_text("{}", encoding="utf-8")
    before = [p.stat().st_mtime_ns for p in watched]
    _card(tmp_path)
    _run(tmp_path, _recipe(), VERDICT)
    assert [p.stat().st_mtime_ns for p in watched] == before


def test_report_only(tmp_path: Path) -> None:
    """UT-MKT-019.013.M01.T02: A run adds rows only to card_tests and lessons."""
    _card(tmp_path)
    tables_before = {n for (n,) in _query(tmp_path, "SELECT name FROM sqlite_master "
                                                    "WHERE type = 'table'")}
    counts = {t: _query(tmp_path, f"SELECT COUNT(*) FROM {t}")[0][0]
              for t in tables_before - {"sqlite_sequence"}}
    _run(tmp_path, _recipe(), VERDICT)
    for t, n in counts.items():
        assert _query(tmp_path, f"SELECT COUNT(*) FROM {t}")[0][0] == n, t
    new = {n for (n,) in _query(tmp_path, "SELECT name FROM sqlite_master WHERE type = "
                                          "'table'")} - tables_before
    assert new <= {"card_tests", "lessons", "lesson_uses", "lesson_edits", "memory_state",
                   "sqlite_sequence"}


def test_logs(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-019.014.M01.T01: Each step logs a [Research] line with ticket and card."""
    _card(tmp_path)
    with caplog.at_level(logging.INFO):
        _run(tmp_path, _recipe(), VERDICT)
    lines = [r.getMessage() for r in caplog.records if "Ticket 9 card SC-1" in r.getMessage()]
    assert len(lines) >= 3 and all(m.startswith("[Research]") for m in lines)



def test_time_limit(tmp_path: Path) -> None:
    """UT-MKT-019.005.M03.T05: A replay past its time limit stops and fails the ticket."""
    with pytest.raises(TooSlow):
        replay(_recipe(), [_stock(), _stock()], limit_s=-1)


def test_owner_cap() -> None:
    """UT-MKT-019.011.M04.T04: The lead is told to give strategy tests 20,000 tokens."""
    assert "token cap 20000" in HEADER and OWNER_TEST_CAP == 20_000
