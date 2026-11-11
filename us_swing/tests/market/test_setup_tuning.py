"""Tests for setup tuning research (FO-MKT-015, Autonomous desk step F skill 1)."""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from tests.market.p5b_support import FakeCtx
from us_swing.core.desk_research import KINDS, StepResult, Ticket
from us_swing.core.desk_steps import DEFAULT_EMPLOYEE_PACKAGES, SKILL_PATHS
from us_swing.desk.registry import default_folders, load_employee
from us_swing.market import tuning_replay
from us_swing.market.flow import roll
from us_swing.market.setup_knobs import KNOBS, check_changes, knob_value
from us_swing.market.setup_tuning import (
    Change,
    SetupTuningSkill,
    TuningPlan,
    TuningVerdict,
    VariantAsk,
)
from us_swing.market.setups import Bars, long_candidates, short_candidates, sma
from us_swing.market.tuning_replay import Row, gain, load_bars, row_from_r, table_text
from us_swing.market.tuning_strategy import (
    apply_changes,
    pick_stocks,
    run_strategy,
    stop_problem,
    strategy_knobs,
    trade_r,
)

NOW = datetime(2026, 11, 11, 11, 0)

STRATEGY: dict[str, Any] = {
    "name": "RSI Dip", "entry_condition": "RSI(14) < 30", "exit_condition": "RSI(14) > 70",
    "stoploss_enabled": True, "stoploss_type": "fixed", "stoploss_value": 2.0,
    "target_enabled": True, "target_value": 4.0, "symbol_mode": "all",
    "symbols_include": [], "direction": "LONG",
}


def _ticket(state: dict[str, Any] | None = None, tid: int = 7) -> Ticket:
    return Ticket(
        id=tid, kind="setup_tuning", topic="Pullback limits", goal="Try nearer SMA limits",
        done_test="Any variant beats baseline by 0.05R", token_cap=8_000, step_cap=8,
        time_cap_min=60, raised_by="emp-005", raised_by_name="Lead", status="running",
        made="2026-11-11T09:00:00-05:00", approved_by="auto", approved=None, started=None,
        ended=None, tokens=0, steps=0, biggest=0, quiet_steps=0, last_call="",
        state=json.dumps(state or {}), result="", end_reason="", gain=None, updated=None)


def _rows(base: float, best: float, trades: int = 120) -> list[dict[str, Any]]:
    return [Row("base", {}, 300, 0.5, base).to_dict(),
            Row("v1", {"near_sma": 1.01}, trades, 0.55, best).to_dict()]


def _skill(by_label: dict[str, float] | None = None, trades: int = 150,
           strategies: list[dict[str, Any]] | None = None,
           strategy_run: Any = None) -> SetupTuningSkill:
    fake = by_label or {"base": 0.10, "v1": 0.20, "v2": 0.05, "v3": 0.11}

    def bars() -> Any:
        return "bars"

    skill = SetupTuningSkill(lambda: NOW, bars, lambda: list(strategies or [dict(STRATEGY)]),
                             lambda: ["AAPL", "MSFT"],
                             strategy_run or (lambda cfg, ch, label, st: Row(
                                 label, dict(ch), trades, 0.5, fake[label])))
    return skill


@pytest.fixture
def fake_replay(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = {"base": 0.10, "v1": 0.20, "v2": 0.05, "v3": 0.11}

    def replay(setup: str, changes: dict[str, float], label: str, bars: Any) -> Row:
        return Row(label, dict(changes), 150, 0.5, fake[label])

    monkeypatch.setattr("us_swing.market.setup_tuning.replay_setup", replay)


def _plan(target: str = "Pullback", values: tuple[float, ...] = (1.01, 1.03, 1.0)
          ) -> TuningPlan:
    return TuningPlan(target=target, variants=[
        VariantAsk(changes=[Change(knob="near_sma", value=v)]) for v in values])


def _bars(days: int = 400, seed: int = 3) -> Bars:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-01", periods=days)
    cols = ["AAA", "BBB", "CCC"]
    close = pd.DataFrame(100 + rng.normal(0.05, 1, (days, 3)).cumsum(axis=0), idx, cols)
    high = close + rng.uniform(0.1, 1.5, (days, 3))
    low = close - rng.uniform(0.1, 1.5, (days, 3))
    vol = pd.DataFrame(rng.uniform(1e5, 5e5, (days, 3)), idx, cols)
    return Bars(close, high, low, vol)


def _run(skill: SetupTuningSkill, ctx: Any, ticket: Ticket) -> list[StepResult]:
    out: list[StepResult] = []
    state = json.loads(ticket.state)
    for _ in range(8):
        t = _ticket(state, ticket.id)
        res = skill.step(ctx, t)
        assert res is not None
        out.append(res)
        if res.outcome != "go":
            break
        state = res.state or state
        if state.get("phase") == "verdict":
            ctx.answer = TuningVerdict(verdict="Variant v1 did better than today's values.")
    return out


def _lessons(home: Path) -> list[Any]:
    path = home / "desk.db"
    if not path.exists():
        return []
    con = sqlite3.connect(path)
    try:
        if not con.execute("SELECT name FROM sqlite_master WHERE name='lessons'").fetchall():
            return []
        return con.execute("SELECT text, tags, claim, status FROM lessons").fetchall()
    finally:
        con.close()


# ---------------- skill basics ----------------

def test_skill_kinds() -> None:
    """UT-MKT-015.001.M01.T01: The skill works setup tuning tickets only."""
    assert SetupTuningSkill.kinds == ("setup_tuning",)
    assert "setup_tuning" in KINDS
    assert SetupTuningSkill.step_tokens > 0


def test_unknown_target(tmp_path: Path) -> None:
    """UT-MKT-015.001.M01.T02: A target that is neither a setup nor a strategy fails."""
    ctx = FakeCtx(tmp_path, _plan("Moonshot"))
    res = _skill().step(ctx, _ticket())
    assert res is not None and res.outcome == "failed" and "Moonshot" in res.note


# ---------------- knobs ----------------

def test_defaults_unchanged() -> None:
    """UT-MKT-015.002.M02.T01: With no values the rules match today's fixed numbers."""
    bars = _bars()
    defaults = {s: {k.name: k.default for k in ks} for s, ks in KNOBS.items()}
    for make in (long_candidates, short_candidates):
        for (n1, m1, t1, s1), (n2, m2, t2, s2) in zip(make(bars), make(bars, defaults),
                                                      strict=True):
            assert n1 == n2
            pd.testing.assert_frame_equal(m1, m2)
            pd.testing.assert_frame_equal(t1, t2)
            pd.testing.assert_frame_equal(s1, s2)
    c = bars.closes
    sma21, sma50 = sma(c, 21), sma(c, 50)
    old = ((c > sma50) & (sma50 > sma50.shift(10)) & (roll(bars.lows, 3, "min") <= sma21 * 1.02)
           & (c >= sma21))
    pd.testing.assert_frame_equal(long_candidates(bars)[2][1], old)


def test_range_check() -> None:
    """UT-MKT-015.002.M02.T02: Out-of-range and unknown knobs are dropped."""
    assert check_changes("Pullback", {"near_sma": 1.2, "foo": 3.0}) == {}
    assert check_changes("Pullback", {"near_sma": 1.01}) == {"near_sma": 1.01}


def test_whole_knob() -> None:
    """UT-MKT-015.002.M02.T03: Day-count knobs are rounded."""
    assert knob_value({"Pullback": {"sma_days": 20.6}}, "Pullback", "sma_days") == 21.0
    assert check_changes("Pullback", {"sma_days": 30.4}) == {"sma_days": 30.0}


# ---------------- pick step ----------------

def test_pick_step(tmp_path: Path) -> None:
    """UT-MKT-015.003.M01.T01: Three valid Pullback variants go into the state."""
    ctx = FakeCtx(tmp_path, _plan())
    res = _skill().step(ctx, _ticket())
    assert res is not None and res.outcome == "go"
    assert res.state["phase"] == "run" and res.state["side"] == "long"
    assert [v["label"] for v in res.state["variants"]] == ["v1", "v2", "v3"]
    assert "near_sma" in ctx.asked[0] and "RSI Dip" in ctx.asked[0]


def test_no_valid_variant(tmp_path: Path) -> None:
    """UT-MKT-015.003.M01.T02: All variants out of range ends the ticket failed."""
    ctx = FakeCtx(tmp_path, _plan(values=(1.5, 2.0)))
    res = _skill().step(ctx, _ticket())
    assert res is not None and res.outcome == "failed"


def test_too_many() -> None:
    """UT-MKT-015.003.M01.T03: Four variants or three changes are not a valid answer."""
    with pytest.raises(ValidationError):
        _plan(values=(1.01, 1.02, 1.03, 1.04))
    with pytest.raises(ValidationError):
        VariantAsk(changes=[Change(knob="a", value=1), Change(knob="b", value=1),
                            Change(knob="c", value=1)])


# ---------------- replay ----------------

def _one_stock(highs: list[float], lows: list[float], closes: list[float]
               ) -> tuple[list[str], Any, Any, Any]:
    days = [f"2026-01-{i + 1:02d}" for i in range(len(closes))]
    return days, np.array(highs, float), np.array(lows, float), np.array(closes, float)


def test_replay_trade() -> None:
    """UT-MKT-015.004.M03.T01: A fill that runs to 2R gives one trade of 2.0R."""
    days, h, lo, c = _one_stock([100, 102, 106] + [104] * 15, [98, 100, 103] + [102] * 15,
                                [99, 101, 105] + [103] * 15)
    trig = np.full(len(c), 101.0)
    stop = np.full(len(c), 99.0)
    rs = tuning_replay._stock_r("long", days, h, lo, c, np.array([0]), trig, stop)
    assert rs == [2.0]
    assert row_from_r("base", {}, rs) == Row("base", {}, 1, 1.0, 2.0)


def test_busy_stock() -> None:
    """UT-MKT-015.004.M03.T02: Matches on 3 days in a row give one trade."""
    days, h, lo, c = _one_stock([100, 100, 100, 106] + [104] * 15,
                                [98, 98, 98, 103] + [102] * 15,
                                [99, 99, 99, 105] + [103] * 15)
    trig = np.full(len(c), 101.0)
    stop = np.full(len(c), 99.0)
    rs = tuning_replay._stock_r("long", days, h, lo, c, np.array([0, 1, 2]), trig, stop)
    assert rs == [2.0]


def test_no_data(tmp_path: Path) -> None:
    """UT-MKT-015.004.M03.T03: An empty Backtest Data folder gives no bars and no row."""
    assert load_bars(tmp_path, lambda: [("AAA", "AAA", "Tech")]) is None
    assert tuning_replay.replay_setup("Pullback", {}, "base", None) is None


def test_five_year_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-MKT-015.004.M03.T04: A match older than 5 years is not traded."""
    idx = pd.bdate_range("2019-01-01", "2025-12-31")
    cols = ["AAA"]
    close = pd.DataFrame(99.0, idx, cols)
    bars = Bars(close, close + 1, close - 1, pd.DataFrame(1e5, idx, cols))
    match = pd.DataFrame(False, idx, cols)
    match.iloc[5] = True
    level = pd.DataFrame(99.5, idx, cols)
    monkeypatch.setattr(tuning_replay, "setup_frames",
                        lambda b, s, ch: (match, level, level - 2))
    assert tuning_replay.trade_rs(bars, "Pullback", {}) == []
    match.iloc[5] = False
    match.iloc[-40] = True
    assert tuning_replay.trade_rs(bars, "Pullback", {}) == [-0.25]


# ---------------- strategy ----------------

def test_strategy_copy() -> None:
    """UT-MKT-015.005.M04.T01: A change makes a renamed copy; the live dict is unchanged."""
    live = dict(STRATEGY)
    copy = apply_changes(live, {"entry#2": 35.0}, "v1")
    assert copy["entry_condition"] == "RSI(14) < 35"
    assert copy["name"] == "RSI Dip (tune v1)"
    assert live == STRATEGY
    timed = {**STRATEGY, "entry_condition": "close(15m) > 1.5 and time > 09:30"}
    assert [k.name for k in strategy_knobs(timed) if k.name.startswith("entry")] == ["entry#1"]
    small = apply_changes(timed, {"entry#1": 0.00001}, "v2")
    assert small["entry_condition"] == "close(15m) > 0.00001 and time > 09:30"


def test_no_fixed_stop() -> None:
    """UT-MKT-015.005.M04.T02: No stop or a trailing stop cannot be tested in R."""
    assert stop_problem({**STRATEGY, "stoploss_enabled": False})
    assert stop_problem({**STRATEGY, "stoploss_type": "trailing"})
    assert stop_problem(STRATEGY) == ""


def test_pick_stocks() -> None:
    """UT-MKT-015.005.M04.T03: Own include list first, else up to 30 known asked stocks."""
    own = {**STRATEGY, "symbol_mode": "include", "symbols_include": ["nvda", "AMD"]}
    assert pick_stocks(own, ["AAPL"], ["AAPL"]) == ["NVDA", "AMD"]
    known = [f"S{i}" for i in range(40)]
    asked = ["ZZZ", *known[:35]]
    assert pick_stocks(STRATEGY, asked, known) == known[:30]


def test_trade_r() -> None:
    """UT-MKT-015.005.M04.T04: R is net P&L over the money the stop risks."""
    trades = pd.DataFrame({"qty": [10], "entry_px": [100.0], "net_pnl": [40.0]})
    assert trade_r(trades, 2.0) == [2.0]
    assert trade_r(pd.DataFrame(), 2.0) == []


@dataclass
class _Est:
    errors: list[str]
    data_span: tuple[date, date] | None


@dataclass
class _Daily:
    frame: pd.DataFrame
    days: list[date]


class _FakeService:
    def __init__(self, loader: Any, seen: dict[str, Any]) -> None:
        seen["loaded"] = loader()
        self.seen = seen

    def estimate(self, plan: Any, user_id: str) -> _Est:
        return _Est([], (date(2023, 1, 3), date(2026, 11, 10)))

    def run_stocks(self, plan: Any, user_id: str, *, workers: int = 4,
                   record: bool = True) -> _Daily:
        self.seen["stocks_record"] = record
        self.seen["period"] = plan.period
        return _Daily(pd.DataFrame(), [])

    def run_signals(self, plan: Any, daily: Any, *, workers: int = 4,
                    record: bool = True) -> pd.DataFrame:
        self.seen["signals_record"] = record
        return pd.DataFrame()


def test_run_not_saved() -> None:
    """UT-MKT-015.005.M04.T05: Both steps run with record off and only the copy is loaded."""
    seen: dict[str, Any] = {}

    @dataclass
    class _Result:
        trades: pd.DataFrame

    def portfolio(*args: Any) -> list[_Result]:
        return [_Result(pd.DataFrame({"qty": [10], "entry_px": [100.0], "net_pnl": [20.0]}))]

    row = run_strategy(STRATEGY, {"entry#2": 35.0}, "v1", ["AAPL"], today=date(2026, 11, 11),
                       service=lambda loader: _FakeService(loader, seen),
                       portfolio=portfolio, user=lambda: "admin")
    assert seen["stocks_record"] is False and seen["signals_record"] is False
    assert [s["name"] for s in seen["loaded"]] == ["RSI Dip (tune v1)"]
    assert seen["period"].start == date(2023, 1, 3)
    assert row == Row("v1", {"entry#2": 35.0}, 1, 1.0, 1.0)


# ---------------- table and gain ----------------

def test_table() -> None:
    """UT-MKT-015.006.M03.T01: The table lists trades, win, R and change."""
    rows = [Row.from_dict(r) for r in _rows(0.10, 0.16)]
    text = table_text(rows)
    assert "base (today's values): 300 trades, win 50%, +0.10R" in text
    assert "v1 (near_sma 1.01): 120 trades, win 55%, +0.16R, change +0.06R" in text


def test_table_no_trades() -> None:
    """UT-MKT-015.006.M03.T02: A variant with no trades shows zeros."""
    row = row_from_r("v1", {"near_sma": 1.01}, [])
    assert row == Row("v1", {"near_sma": 1.01}, 0, 0.0, 0.0)
    assert "0 trades, win 0%, +0.00R" in table_text([row])


def test_gain() -> None:
    """UT-MKT-015.007.M03.T01: +0.06R on 120 trades is a gain."""
    best = gain([Row.from_dict(r) for r in _rows(0.10, 0.16)])
    assert best is not None and best.label == "v1"
    few = [Row("base", {}, 300, 0.5, 0.0), Row("v1", {}, 20, 0.9, 0.6),
           Row("v2", {}, 300, 0.6, 0.2)]
    picked = gain(few)
    assert picked is not None and picked.label == "v2"


def test_gain_limits() -> None:
    """UT-MKT-015.007.M03.T02: +0.04R, or a gain on 99 trades, is not a gain."""
    assert gain([Row.from_dict(r) for r in _rows(0.10, 0.14, 500)]) is None
    assert gain([Row.from_dict(r) for r in _rows(0.10, 0.30, 99)]) is None


def test_gain_no_variant() -> None:
    """UT-MKT-015.007.M03.T03: Baseline alone, or a worse variant, is not a gain."""
    assert gain([Row("base", {}, 300, 0.5, 0.1)]) is None
    assert gain([Row.from_dict(r) for r in _rows(0.10, -0.20)]) is None


# ---------------- whole ticket ----------------

def test_full_ticket(tmp_path: Path, fake_replay: None) -> None:
    """UT-MKT-015.008.M01.T01: Pick, baseline, 3 variants and verdict end done with a gain."""
    ctx = FakeCtx(tmp_path, _plan())
    steps = _run(_skill(), ctx, _ticket())
    assert [s.call for s in steps] == ["pick", "run base", "run v1", "run v2", "run v3",
                                       "verdict"]
    last = steps[-1]
    assert last.outcome == "done" and last.gain is True
    assert "Verdict:" in last.note and "Gain: yes, v1" in last.note
    assert "base (today's values)" in steps[1].note


def test_no_verdict_answer(tmp_path: Path) -> None:
    """UT-MKT-015.008.M01.T02: No verdict answer gives an empty note and outcome go."""
    state = {"phase": "verdict", "target": "Pullback", "kind": "setup", "side": "long",
             "variants": [], "stocks": [], "rows": _rows(0.1, 0.2)}
    res = _skill().step(FakeCtx(tmp_path, None), _ticket(state))
    assert res is not None and res.note == "" and res.outcome == "go"


def _verdict_state(kind: str = "setup", best: float = 0.2) -> dict[str, Any]:
    target = "Pullback" if kind == "setup" else "RSI Dip"
    return {"phase": "verdict", "target": target, "kind": kind, "side": "long",
            "variants": [], "stocks": ["AAPL"], "rows": _rows(0.1, best)}


def test_candidate_lesson(tmp_path: Path) -> None:
    """UT-MKT-015.009.M01.T01: A setup gain writes one candidate lesson, claim worse."""
    ctx = FakeCtx(tmp_path, TuningVerdict(verdict="Variant v1 did better than today."))
    res = _skill().step(ctx, _ticket(_verdict_state()))
    assert res is not None and res.gain is True
    lessons = _lessons(tmp_path)
    assert len(lessons) == 1
    text, tags, claim, status = lessons[0]
    assert json.loads(tags) == {"setup": "Pullback", "side": "long"}
    assert (claim, status) == ("worse", "candidate") and "Pullback" in text


def test_no_lesson(tmp_path: Path) -> None:
    """UT-MKT-015.009.M01.T02: No gain, or a strategy gain, writes no lesson."""
    ctx = FakeCtx(tmp_path, TuningVerdict(verdict="Nothing beat today's values here."))
    res = _skill().step(ctx, _ticket(_verdict_state(best=0.11)))
    assert res is not None and res.gain is False
    res = _skill().step(ctx, _ticket(_verdict_state("strategy")))
    assert res is not None and res.gain is True
    assert _lessons(tmp_path) == []


def test_report_only(tmp_path: Path) -> None:
    """UT-MKT-015.010.M01.T01: A strategy ticket with a gain leaves the live dict alone."""
    live = [dict(STRATEGY)]
    ctx = FakeCtx(tmp_path, TuningPlan(target="RSI Dip", variants=[
        VariantAsk(changes=[Change(knob="entry#2", value=35)])], stocks=["AAPL"]))
    steps = _run(_skill({"base": 0.1, "v1": 0.3}, strategies=live), ctx, _ticket())
    assert steps[-1].outcome == "done" and steps[-1].gain is True
    assert live == [STRATEGY]


def test_winning_values_named(tmp_path: Path, fake_replay: None) -> None:
    """UT-MKT-015.010.M01.T02: The verdict names the winning values; defaults unchanged."""
    before = {s: tuple(ks) for s, ks in KNOBS.items()}
    ctx = FakeCtx(tmp_path, _plan())
    last = _run(_skill(), ctx, _ticket())[-1]
    assert "v1 (near_sma 1.01)" in last.note
    assert {s: tuple(ks) for s, ks in KNOBS.items()} == before


# ---------------- employee and logs ----------------

def _folders() -> dict[str, Path]:
    return {f.name: f for f in default_folders(DEFAULT_EMPLOYEE_PACKAGES)}


def test_default_employee() -> None:
    """UT-MKT-015.011.M01.T01: emp-013 ships with skill setup_tuning and a loadable path."""
    hire = load_employee(_folders()["emp-013"], SKILL_PATHS)
    assert hire is not None
    assert (hire.spec.level, hire.spec.skill, hire.spec.trigger) == (
        "expert", "setup_tuning", ("research_done",))
    assert isinstance(hire.skill, SetupTuningSkill)


def test_never_wakes(tmp_path: Path) -> None:
    """UT-MKT-015.011.M01.T02: Events never wake the research employee."""
    skill = _skill()
    facts = skill.facts(tmp_path)
    assert not facts.fresh
    assert skill.act(FakeCtx(tmp_path, None), facts) == []


def test_logs(tmp_path: Path, fake_replay: None, caplog: pytest.LogCaptureFixture) -> None:
    """UT-MKT-015.012.M01.T01: Pick, run and verdict steps log with the research prefix."""
    caplog.set_level(logging.INFO, logger="us_swing.market.setup_tuning")
    _run(_skill(), FakeCtx(tmp_path, _plan()), _ticket())
    text = caplog.text
    assert "[Research] Ticket 7 will test 3 variant(s) of Pullback" in text
    assert "[Research] Ticket 7 Pullback v1: 150 trades, +0.20R" in text
    assert "[Research] Ticket 7 Pullback found a gain: v1 +0.10R" in text
