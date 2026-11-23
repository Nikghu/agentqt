"""Tests for MD-EXE-022.010.M04 (runner, live, replay) and MD-EXE-022.012.M05 (guard, engine)."""
from __future__ import annotations

import logging
import shutil
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest
from pytestqt.qtbot import QtBot

from tests.execution.plugin_helpers import SWING_PLUS, frames, swing_plus_source, write_plugin
from us_swing.core.expr.series import evaluate as replay
from us_swing.core.indicator_plugins import (
    REGISTRY,
    PluginArgError,
    PluginCallError,
    PluginGuard,
    plugin_dir,
    values_from_args,
)
from us_swing.execution import ExecutionEnums
from us_swing.execution.strategy_engine import _evaluator
from us_swing.execution.strategy_engine._context import _StrategyContext
from us_swing.execution.strategy_engine._engine import StrategyEngine
from us_swing.execution.strategy_engine._evaluator import (
    ConditionEvaluator,
    EvaluatorError,
    PluginFailure,
)

RUNNING = ExecutionEnums.StrategyRunState.RUNNING
STOPPED = ExecutionEnums.StrategyRunState.STOPPED
SWING_ARGS = "'Spot', 20, 'High', 'Previous', '3m'"


def _install(text: str | None = None, name: str = "swing_plus.py") -> None:
    folder = plugin_dir(1, REGISTRY.root)
    folder.mkdir(parents=True, exist_ok=True)
    if text is None:
        shutil.copy(SWING_PLUS, folder / name)
    else:
        write_plugin(folder, name, text)
    REGISTRY.load_for_user(1)


@pytest.fixture()
def guard(monkeypatch: pytest.MonkeyPatch) -> PluginGuard:
    fresh = PluginGuard()
    monkeypatch.setattr(_evaluator, "PLUGIN_GUARD", fresh)
    return fresh


def _live(expr_value: str, candles: dict[str, pd.DataFrame]) -> float:
    fn = _evaluator._plugin_fn("SWING_PLUS")
    assert fn is not None
    args = [a.strip().strip("'") for a in expr_value.split(",")]
    return fn([args[0], float(args[1]), *args[2:]], candles, "AAA")


# ── Runner and live / replay (M04) ────────────────────────────────────────────

def test_arguments_map_in_order() -> None:
    """UT-EXE-022.010.M04.T01: Arguments map to labels in parameters order, with checks."""
    _install()
    spec = REGISTRY.get("SWING_PLUS")
    assert spec is not None

    values = values_from_args(spec, ["Spot", 20.0, "High", "Previous", "3m"])

    assert values == {"Symbol Type": "Spot", "Candles": 20, "Price Swing": "High",
                      "Window": "Previous", "Timeframe": "3m"}
    assert isinstance(values["Candles"], int)


def test_wrong_count_or_value() -> None:
    """UT-EXE-022.010.M04.T02: A wrong count or value fails like a built-in indicator."""
    _install()
    spec = REGISTRY.get("SWING_PLUS")
    assert spec is not None

    with pytest.raises(PluginArgError, match="SWING_PLUS expects 5 arg"):
        values_from_args(spec, ["Spot", 20, "High", "Previous"])
    with pytest.raises(PluginArgError, match="SWING_PLUS: Candles must be 1 to 500, got 0"):
        values_from_args(spec, ["Spot", 0, "High", "Previous", "3m"])
    with pytest.raises(EvaluatorError, match="expects 5 arg"):
        ConditionEvaluator().evaluate("SWING_PLUS('Spot', 20) > 0", frames(60), "AAA")


def test_live_equals_replay(guard: PluginGuard) -> None:
    """UT-EXE-022.011.M04.T01: Live value equals the replay value at the same candle."""
    _install()
    data = frames(120)
    expr = f"Price('Spot', 'current', 'close', '3m') > SWING_PLUS({SWING_ARGS})"

    values = replay(expr, data).values
    label = next(k for k in values if k.startswith("SWING_PLUS(Spot, 20"))
    series = values[label]

    for candle in (40, 80, 119):
        upto = {tf: f.iloc[:candle + 1] if tf == "3m" else f for tf, f in data.items()}
        assert _live(SWING_ARGS, upto) == pytest.approx(series[candle])
    assert np.isnan(series[:20]).all()


def test_builtin_names_win(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-EXE-022.011.M04.T02: A built-in name never reaches the plugin registry."""
    asked: list[str] = []
    monkeypatch.setattr(_evaluator.INDICATOR_REGISTRY, "get", lambda name: asked.append(name))

    assert ConditionEvaluator().evaluate("EMA('Spot', 3, '3m') > 0", frames(60), "AAA")
    assert asked == []


def test_not_enough_candles_live(guard: PluginGuard) -> None:
    """UT-EXE-022.011.M04.T03: An empty newest value gives "insufficient bars" (no signal)."""
    _install()

    with pytest.raises(EvaluatorError, match="insufficient bars"):
        ConditionEvaluator().evaluate(
            "SWING_PLUS('Spot', 500, 'High', 'Previous', '3m') > 0", frames(120), "AAA")
    assert guard.failures("SWING_PLUS") == 0


# ── Guard (M05) ───────────────────────────────────────────────────────────────

def test_error_gives_no_signal_and_one_warning(
        guard: PluginGuard, caplog: pytest.LogCaptureFixture) -> None:
    """UT-EXE-022.012.M05.T01: An error raises PluginFailure; one warning per candle."""
    _install(swing_plus_source(("count = self.parameter(\"Candles\")",
                                "count = self.parameter(\"Candles\") / 0")))
    REGISTRY.load_for_user(1)  # dry run skipped: no probe, so the broken file loads
    data = frames(60)
    expr = f"SWING_PLUS({SWING_ARGS}) > 0"

    with caplog.at_level(logging.WARNING):
        for _ in range(2):
            with pytest.raises(PluginFailure) as info:
                ConditionEvaluator().evaluate(expr, data, "AAA")

    assert info.value.plugin_name == "SWING_PLUS"
    warnings = [r.getMessage() for r in caplog.records if r.name.endswith("_guard")]
    assert warnings == ["[Indicators] SWING_PLUS failed on AAA: division by zero"]
    assert guard.failures("SWING_PLUS", "AAA") == 2


def test_live_frames_one_warning_per_candle(
        guard: PluginGuard, caplog: pytest.LogCaptureFixture) -> None:
    """UT-EXE-022.012.M05.T04: Live frames (``datetime`` column) also warn once per candle."""
    _install(swing_plus_source(("count = self.parameter(\"Candles\")",
                                "count = self.parameter(\"Candles\") / 0")))
    data = {tf: f.rename(columns={"ts": "datetime"}) for tf, f in frames(60).items()}
    expr = f"SWING_PLUS({SWING_ARGS}) > 0"

    with caplog.at_level(logging.WARNING):
        for _ in range(2):
            with pytest.raises(PluginFailure):
                ConditionEvaluator().evaluate(expr, data, "AAA")

    warnings = [r.getMessage() for r in caplog.records if r.name.endswith("_guard")]
    assert warnings == ["[Indicators] SWING_PLUS failed on AAA: division by zero"]


def test_slow_call_is_a_failure() -> None:
    """UT-EXE-022.012.M05.T02: A call slower than 2 s is a failure; its result is dropped."""
    times: Iterator[float] = iter([0.0, 2.5])
    guard = PluginGuard(clock=lambda: next(times))

    with pytest.raises(PluginCallError, match=r"took 2\.5 s \(limit 2 s\)"):
        guard.run("SLOW", lambda: 1.0)
    assert guard.failures("SLOW") == 1


def test_normal_call_passes(caplog: pytest.LogCaptureFixture) -> None:
    """UT-EXE-022.012.M05.T03: A normal call returns its value with no warning."""
    guard = PluginGuard()

    with caplog.at_level(logging.WARNING):
        assert guard.run("FINE", lambda: 4.2) == 4.2

    assert guard.failures("FINE") == 0 and not caplog.records


def _fail(guard: PluginGuard, name: str, candle: str) -> None:
    with pytest.raises(PluginCallError):
        guard.run(name, lambda: 1 / 0, candle=candle)


def test_three_failures_call_listener() -> None:
    """UT-EXE-022.013.M05.T01 (guard part): The third failure in a row calls the listener."""
    guard = PluginGuard()
    hits: list[str] = []
    guard.add_limit_listener(hits.append)

    for candle in ("a", "b", "c"):
        _fail(guard, "BAD", candle)

    assert hits == ["BAD"] and guard.failures("BAD") == 0


def test_success_resets_count() -> None:
    """UT-EXE-022.013.M05.T02: A success between failures resets the count."""
    guard = PluginGuard()
    hits: list[str] = []
    guard.add_limit_listener(hits.append)

    _fail(guard, "BAD", "a")
    _fail(guard, "BAD", "b")
    guard.run("BAD", lambda: 1.0)
    _fail(guard, "BAD", "c")
    _fail(guard, "BAD", "d")

    assert hits == []


def test_two_failures_do_not_stop() -> None:
    """UT-EXE-022.013.M05.T03: Two failures in a row do not reach the listener."""
    guard = PluginGuard()
    hits: list[str] = []
    guard.add_limit_listener(hits.append)

    _fail(guard, "BAD", "a")
    _fail(guard, "BAD", "b")

    assert hits == [] and guard.failures("BAD") == 2


def test_hung_plugin_is_stopped_and_never_called_again() -> None:
    """UT-EXE-022.012.M05.T02 (review fix): A call that never returns is cut off and marked hung."""
    guard = PluginGuard(limit_s=0.2)
    hits: list[str] = []
    guard.add_limit_listener(hits.append)
    calls: list[int] = []

    def hang() -> float:
        calls.append(1)
        time.sleep(1.5)
        return 1.0

    with pytest.raises(PluginCallError, match=r"did not finish in 0\.2 s"):
        guard.run("HANG", hang, symbol="AAA")
    with pytest.raises(PluginCallError, match="stopped earlier"):
        guard.run("HANG", hang, symbol="AAA")

    assert guard.is_hung("HANG") and hits == ["HANG"] and calls == [1]


def test_sys_exit_in_plugin_is_a_failure() -> None:
    """UT-EXE-022.012.M05.T01 (review fix): sys.exit() in user code is a failure, not an exit."""
    guard = PluginGuard()

    with pytest.raises(PluginCallError, match=r"called sys\.exit\(\)"):
        guard.run("EXIT", lambda: sys.exit(1), symbol="AAA")
    assert guard.failures("EXIT", "AAA") == 1


def test_failures_counted_per_stock() -> None:
    """UT-EXE-022.013.M05.T01 (review fix): Successes on other stocks do not hide one stock's failures."""
    guard = PluginGuard()
    hits: list[str] = []
    guard.add_limit_listener(hits.append)

    for candle in ("a", "b", "c"):
        with pytest.raises(PluginCallError):
            guard.run("BAD", lambda: 1 / 0, symbol="AAA", candle=candle)
        guard.run("BAD", lambda: 1.0, symbol="BBB")

    assert hits == ["BAD"]


# ── Engine (M05) ──────────────────────────────────────────────────────────────

@dataclass
class _Cfg:
    name: str
    entry_condition: str = ""
    exit_condition: str = ""
    run_state: str = "RUNNING"
    mode: str = "auto"


def _engine(cfgs: list[_Cfg], saved: list[tuple[str, str]]) -> StrategyEngine:
    engine = StrategyEngine(
        registry_loader=lambda: cfgs,  # type: ignore[arg-type, return-value]
        registry_saver=lambda name, state: saved.append((name, state)),
        candles_provider=lambda _s: {}, bar_provider=lambda _s, _t: None,
        risk=MagicMock(), submitter=MagicMock(), pending=MagicMock(), bus=MagicMock())
    engine._registry = {c.name: _StrategyContext(cfg=c, run_state=RUNNING if c.run_state ==
                                                 "RUNNING" else STOPPED)  # type: ignore[arg-type]
                        for c in cfgs}
    engine._router = MagicMock()
    return engine


def test_failing_plugin_stops_its_strategies(qtbot: QtBot) -> None:
    """UT-EXE-022.013.M05.T01: Three failures stop its strategies, alert once, others run."""
    uses = f"SWING_PLUS({SWING_ARGS}) > 0"
    cfgs = [_Cfg("A", entry_condition=uses), _Cfg("B", exit_condition=uses),
            _Cfg("C", entry_condition="RSI('Spot', 14, '3m') > 50")]
    engine = _engine(cfgs, [])

    with qtbot.waitSignal(engine.plugin_stopped) as signal:
        stopped = engine.stop_plugin_users("SWING_PLUS")

    assert stopped == ["A", "B"] and signal.args == ["SWING_PLUS", ["A", "B"]]
    states = {name: ctx.run_state for name, ctx in engine.registry.items()}
    assert states == {"A": STOPPED, "B": STOPPED, "C": RUNNING}


def test_missing_plugin_blocks_start(qtbot: QtBot) -> None:
    """UT-EXE-022.014.M05.T01: A strategy needing a missing plugin stays stopped, with a reason."""
    saved: list[tuple[str, str]] = []
    engine = _engine([_Cfg("X", entry_condition="MY_ST('Spot', 3) > 0", run_state="STOPPED")],
                     saved)

    with qtbot.waitSignal(engine.start_refused) as signal:
        engine._apply_run_state("X", RUNNING)

    assert engine.registry["X"].run_state is STOPPED
    assert saved == [("X", "STOPPED")]
    assert signal.args == ["X", "X cannot start: indicator MY_ST is not installed"]


def test_plugin_present_lets_it_start() -> None:
    """UT-EXE-022.014.M05.T02: With the plugin loaded the strategy starts."""
    _install()
    engine = _engine([_Cfg("X", entry_condition=f"SWING_PLUS({SWING_ARGS}) > 0",
                           run_state="STOPPED")], [])

    engine._apply_run_state("X", RUNNING)

    assert engine.registry["X"].run_state is RUNNING


def test_alert_text() -> None:
    """UT-EXE-022.013.M05.T01 (alert part): The alert names the indicator and the strategies."""
    from us_swing.core.notifications import IndicatorStoppedEvent
    from us_swing.core.notifications._formatters import default_registry

    text = default_registry().render(
        IndicatorStoppedEvent(indicator="SWING_PLUS", strategies=("A", "B"))).text

    assert text == ("Indicator SWING_PLUS failed 3 times in a row. Stopped: A, B. "
                    "Open trades keep their stop and target.")
