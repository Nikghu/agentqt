"""Unit tests: MD-SCR-003.001.M10 — screener/executor.py
Refs: UT-SCR-003.001.M10.T01 – UT-SCR-003.001.M10.T22
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from us_swing.screener.base import PresetAccessDenied
from us_swing.screener.executor import PresetExecutor
from us_swing.screener.preset import (
    GroupLogic,
    Preset,
    PresetType,
    ScreenerGroup,
    ScreenerRef,
)
from us_swing.screener.registry import ScreenerRegistry
from us_swing.screener.storage import AITranscriptTurn, ScreenerResultsStorage, ScreenerRunResult

from .conftest import make_bars, make_composite_preset, make_weighted_preset


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_storage(tmp_path: Path) -> ScreenerResultsStorage:
    return ScreenerResultsStorage(base_dir=tmp_path / "results")


def _mock_preset_manager(preset: Preset) -> MagicMock:
    pm = MagicMock()
    pm.load_preset.return_value = preset
    return pm


def _make_screener(scores: dict[str, float] | None = None) -> MagicMock:
    """Mock Screener that passes every symbol with configurable scores."""
    screener = MagicMock()
    screener.apply.side_effect = lambda syms, bars, cfg: {
        s: (True, (scores or {}).get(s, 0.8)) for s in syms
    }
    screener.batch_features.return_value = {}
    return screener


SYMBOLS_3 = ["AAPL", "MSFT", "GOOGL"]
BARS_3 = {s: make_bars(s, n=50, seed=i) for i, s in enumerate(SYMBOLS_3)}


# ---------------------------------------------------------------------------
# T01 — run_preset loads preset and validates permissions
# ---------------------------------------------------------------------------

def test_run_preset_loads_preset(tmp_path: Path):
    """UT-SCR-003.001.M10.T01: run_preset calls preset_manager.load_preset."""
    preset = make_weighted_preset("p1")
    registry = ScreenerRegistry()
    registry.register("indicator_composite", lambda: _make_screener())
    registry.register("ml_ensemble", lambda: _make_screener())
    registry.register("llm_claude_ranking", lambda: _make_screener())

    executor = PresetExecutor(
        preset_manager=_mock_preset_manager(preset),
        storage=_mock_storage(tmp_path),
        registry=registry,
    )
    result = executor.run_preset("p1", "user1", symbols=SYMBOLS_3, bars=BARS_3)
    assert isinstance(result, ScreenerRunResult)
    assert result.preset_id == "p1"


# ---------------------------------------------------------------------------
# T02 — PresetAccessDenied propagated from preset_manager
# ---------------------------------------------------------------------------

def test_run_preset_access_denied(tmp_path: Path):
    """UT-SCR-003.001.M10.T02: PresetAccessDenied raised for unauthorized user."""
    pm = MagicMock()
    pm.load_preset.side_effect = PresetAccessDenied("No access")
    executor = PresetExecutor(preset_manager=pm, storage=_mock_storage(tmp_path))
    with pytest.raises(PresetAccessDenied):
        executor.run_preset("p1", "bad_user", symbols=[], bars={})


# ---------------------------------------------------------------------------
# T03 — Stage 1 excludes symbols with price ≤ $5
# ---------------------------------------------------------------------------

def test_stage1_excludes_low_price(tmp_path: Path):
    """UT-SCR-003.001.M10.T03: symbols with close ≤ $5 not in results."""
    cheap = "CHEAP"
    normal = "NORMAL"
    symbols = [cheap, normal]
    bars = {
        cheap: make_bars(cheap, n=10, base_price=3.0),
        normal: make_bars(normal, n=10, base_price=50.0),
    }
    preset = make_weighted_preset("p1")
    registry = ScreenerRegistry()
    registry.register("indicator_composite", lambda: _make_screener())
    registry.register("ml_ensemble", lambda: _make_screener())
    registry.register("llm_claude_ranking", lambda: _make_screener())

    executor = PresetExecutor(
        preset_manager=_mock_preset_manager(preset),
        storage=_mock_storage(tmp_path),
        registry=registry,
    )
    result = executor.run_preset("p1", "u", symbols=symbols, bars=bars)
    assert cheap not in result.results
    assert normal in result.results


# ---------------------------------------------------------------------------
# T04 — Stage 1 excludes symbols with volume < 1 M
# ---------------------------------------------------------------------------

def test_stage1_excludes_low_volume(tmp_path: Path):
    """UT-SCR-003.001.M10.T04: symbols with volume < 1 M not in results."""
    lowvol = "LOWVOL"
    normal = "NORMAL"
    symbols = [lowvol, normal]
    bars = {
        lowvol: make_bars(lowvol, n=10, base_price=50.0, volume=500_000),
        normal: make_bars(normal, n=10, base_price=50.0, volume=5_000_000),
    }
    preset = make_weighted_preset("p1")
    registry = ScreenerRegistry()
    registry.register("indicator_composite", lambda: _make_screener())
    registry.register("ml_ensemble", lambda: _make_screener())
    registry.register("llm_claude_ranking", lambda: _make_screener())

    executor = PresetExecutor(
        preset_manager=_mock_preset_manager(preset),
        storage=_mock_storage(tmp_path),
        registry=registry,
    )
    result = executor.run_preset("p1", "u", symbols=symbols, bars=bars)
    assert lowvol not in result.results
    assert normal in result.results


# ---------------------------------------------------------------------------
# T05 — Stage 1 excludes halted (bars missing / empty)
# ---------------------------------------------------------------------------

def test_stage1_excludes_halted(tmp_path: Path):
    """UT-SCR-003.001.M10.T05: symbol with no bars treated as halted/excluded."""
    halted = "HALTED"
    normal = "NORMAL"
    symbols = [halted, normal]
    bars = {
        halted: [],  # no data = halted
        normal: make_bars(normal, n=10, base_price=50.0),
    }
    preset = make_weighted_preset("p1")
    registry = ScreenerRegistry()
    registry.register("indicator_composite", lambda: _make_screener())
    registry.register("ml_ensemble", lambda: _make_screener())
    registry.register("llm_claude_ranking", lambda: _make_screener())

    executor = PresetExecutor(
        preset_manager=_mock_preset_manager(preset),
        storage=_mock_storage(tmp_path),
        registry=registry,
    )
    result = executor.run_preset("p1", "u", symbols=symbols, bars=bars)
    assert halted not in result.results


# ---------------------------------------------------------------------------
# T06 — Stage 1 completes in < 1 s for 500 symbols
# ---------------------------------------------------------------------------

def test_stage1_execution_time(tmp_path: Path):
    """UT-SCR-003.001.M10.T06: run_preset with 500 symbols completes in < 1 s."""
    symbols = [f"SYM{i:04d}" for i in range(500)]
    bars = {s: make_bars(s, n=10, base_price=50.0) for s in symbols}
    # Weighted preset with a single fast mock screener
    ref = ScreenerRef(screener_id="fast_screener", enabled=True, weight=1.0)
    preset = Preset(
        id="perf",
        name="Perf",
        preset_type=PresetType.WEIGHTED,
        screeners=[ref],
        threshold=0.5,
    )
    registry = ScreenerRegistry()
    registry.register("fast_screener", lambda: _make_screener())

    executor = PresetExecutor(
        preset_manager=_mock_preset_manager(preset),
        storage=_mock_storage(tmp_path),
        registry=registry,
    )
    start = time.perf_counter()
    executor.run_preset("perf", "u", symbols=symbols, bars=bars)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 1000, f"Took {elapsed_ms:.0f} ms"


# ---------------------------------------------------------------------------
# T07 — Stage 2 calls all 5 enabled screeners
# ---------------------------------------------------------------------------

def test_stage2_calls_all_enabled_screeners(tmp_path: Path):
    """UT-SCR-003.001.M10.T07: all 5 enabled screeners are called in Stage 2."""
    screeners: dict[str, MagicMock] = {}
    registry = ScreenerRegistry()
    for i in range(5):
        sid = f"screener_{i}"
        m = _make_screener()
        screeners[sid] = m
        registry.register(sid, lambda m=m: m)

    refs = [
        ScreenerRef(screener_id=f"screener_{i}", enabled=True, weight=0.2)
        for i in range(5)
    ]
    preset = Preset(
        id="p5",
        name="Five",
        preset_type=PresetType.WEIGHTED,
        screeners=refs,
        threshold=0.5,
    )
    executor = PresetExecutor(
        preset_manager=_mock_preset_manager(preset),
        storage=_mock_storage(tmp_path),
        registry=registry,
    )
    executor.run_preset("p5", "u", symbols=SYMBOLS_3, bars=BARS_3)
    for sid, mock in screeners.items():
        assert mock.apply.called, f"{sid}.apply() was not called"


# ---------------------------------------------------------------------------
# T08 — Stage 2 CPU-bound screeners: results collected from parallel execution
# ---------------------------------------------------------------------------

def test_stage2_cpu_screeners_results_collected(tmp_path: Path):
    """UT-SCR-003.001.M10.T08: indicator + ML screener results returned from parallel pool."""
    ind = _make_screener({"AAPL": 0.9, "MSFT": 0.7, "GOOGL": 0.5})
    ml = _make_screener({"AAPL": 0.8, "MSFT": 0.6, "GOOGL": 0.4})
    registry = ScreenerRegistry()
    registry.register("indicator_composite", lambda: ind)
    registry.register("ml_ensemble", lambda: ml)

    refs = [
        ScreenerRef(screener_id="indicator_composite", enabled=True, weight=0.6),
        ScreenerRef(screener_id="ml_ensemble", enabled=True, weight=0.4),
    ]
    preset = Preset(
        id="cpu_test",
        name="CPU",
        preset_type=PresetType.WEIGHTED,
        screeners=refs,
        threshold=0.5,
    )
    executor = PresetExecutor(
        preset_manager=_mock_preset_manager(preset),
        storage=_mock_storage(tmp_path),
        registry=registry,
    )
    result = executor.run_preset("cpu_test", "u", symbols=SYMBOLS_3, bars=BARS_3)
    assert ind.apply.called
    assert ml.apply.called
    # AAPL score: (0.9*0.6 + 0.8*0.4) / 1.0 = 0.86 → passes threshold 0.5
    assert "AAPL" in result.results


# ---------------------------------------------------------------------------
# T09 — Stage 2 LLM (I/O-bound) screener results collected via asyncio
# ---------------------------------------------------------------------------

def test_stage2_llm_screener_results_collected(tmp_path: Path):
    """UT-SCR-003.001.M10.T09: LLM screener apply() called; results collected."""
    llm = _make_screener({"AAPL": 0.9, "MSFT": 0.7, "GOOGL": 0.5})
    registry = ScreenerRegistry()
    registry.register("llm_ranker", lambda: llm)

    refs = [ScreenerRef(screener_id="llm_ranker", enabled=True, weight=1.0)]
    preset = Preset(
        id="llm_test",
        name="LLM",
        preset_type=PresetType.WEIGHTED,
        screeners=refs,
        threshold=0.5,
    )
    executor = PresetExecutor(
        preset_manager=_mock_preset_manager(preset),
        storage=_mock_storage(tmp_path),
        registry=registry,
    )
    result = executor.run_preset("llm_test", "u", symbols=SYMBOLS_3, bars=BARS_3)
    assert llm.apply.called
    assert "AAPL" in result.results


# ---------------------------------------------------------------------------
# T10 — Composite: symbol passes if ANY group passes (OR between groups)
# ---------------------------------------------------------------------------

def test_composite_or_logic_symbol_passes(tmp_path: Path):
    """UT-SCR-003.001.M10.T10: composite symbol included when it passes at least one group."""
    # G1 → sym passes; G2 → sym fails
    s1 = MagicMock()
    s1.apply.side_effect = lambda syms, bars, cfg: {s: (True, 0.8) for s in syms}
    s2 = MagicMock()
    s2.apply.side_effect = lambda syms, bars, cfg: {s: (False, 0.2) for s in syms}

    registry = ScreenerRegistry()
    registry.register("s1", lambda: s1)
    registry.register("s2", lambda: s2)

    group1 = ScreenerGroup(
        group_id="g1", logic=GroupLogic.AND,
        screeners=[ScreenerRef(screener_id="s1", enabled=True)]
    )
    group2 = ScreenerGroup(
        group_id="g2", logic=GroupLogic.AND,
        screeners=[ScreenerRef(screener_id="s2", enabled=True)]
    )
    preset = Preset(
        id="comp",
        name="Comp",
        preset_type=PresetType.COMPOSITE,
        groups=[group1, group2],
    )
    executor = PresetExecutor(
        preset_manager=_mock_preset_manager(preset),
        storage=_mock_storage(tmp_path),
        registry=registry,
    )
    result = executor.run_preset("comp", "u", symbols=["AAPL"], bars=BARS_3)
    assert "AAPL" in result.results  # passed g1 → included


# ---------------------------------------------------------------------------
# T11 — Composite: symbol excluded if ALL groups fail
# ---------------------------------------------------------------------------

def test_composite_all_groups_fail(tmp_path: Path):
    """UT-SCR-003.001.M10.T11: symbol excluded when it fails all groups."""
    fail = MagicMock()
    fail.apply.side_effect = lambda syms, bars, cfg: {s: (False, 0.1) for s in syms}
    registry = ScreenerRegistry()
    registry.register("fail_s", lambda: fail)

    group1 = ScreenerGroup(
        group_id="g1", logic=GroupLogic.AND,
        screeners=[ScreenerRef(screener_id="fail_s", enabled=True)]
    )
    group2 = ScreenerGroup(
        group_id="g2", logic=GroupLogic.AND,
        screeners=[ScreenerRef(screener_id="fail_s", enabled=True)]
    )
    preset = Preset(
        id="comp_fail",
        name="Fail",
        preset_type=PresetType.COMPOSITE,
        groups=[group1, group2],
    )
    executor = PresetExecutor(
        preset_manager=_mock_preset_manager(preset),
        storage=_mock_storage(tmp_path),
        registry=registry,
    )
    result = executor.run_preset("comp_fail", "u", symbols=["AAPL"], bars=BARS_3)
    assert "AAPL" not in result.results


# ---------------------------------------------------------------------------
# T12 — Composite result includes matching_groups
# ---------------------------------------------------------------------------

def test_composite_result_includes_matching_groups(tmp_path: Path):
    """UT-SCR-003.001.M10.T12: result[symbol]['matching_groups'] lists passed groups."""
    s1 = MagicMock()
    s1.apply.side_effect = lambda syms, bars, cfg: {s: (True, 0.9) for s in syms}
    s2 = MagicMock()
    s2.apply.side_effect = lambda syms, bars, cfg: {s: (True, 0.8) for s in syms}
    registry = ScreenerRegistry()
    registry.register("s1", lambda: s1)
    registry.register("s2", lambda: s2)

    group1 = ScreenerGroup(
        group_id="g1", logic=GroupLogic.AND,
        screeners=[ScreenerRef(screener_id="s1", enabled=True)]
    )
    group2 = ScreenerGroup(
        group_id="g2", logic=GroupLogic.AND,
        screeners=[ScreenerRef(screener_id="s2", enabled=True)]
    )
    preset = Preset(
        id="mg_test",
        name="MG",
        preset_type=PresetType.COMPOSITE,
        groups=[group1, group2],
    )
    executor = PresetExecutor(
        preset_manager=_mock_preset_manager(preset),
        storage=_mock_storage(tmp_path),
        registry=registry,
    )
    result = executor.run_preset("mg_test", "u", symbols=["AAPL"], bars=BARS_3)
    assert "AAPL" in result.results
    mg = result.results["AAPL"]["matching_groups"]
    assert "g1" in mg
    assert "g2" in mg


# ---------------------------------------------------------------------------
# T13 — Weighted score: Σ(score_i × weight_i) / Σ(weights)
# ---------------------------------------------------------------------------

def test_weighted_score_formula(tmp_path: Path):
    """UT-SCR-003.001.M10.T13: weighted score = (0.8×0.4 + 0.6×0.3 + 0.9×0.3) ≈ 0.77."""
    sym = "AAPL"
    scores_per_screener = {
        "ind": {sym: (True, 0.8)},
        "ml":  {sym: (True, 0.6)},
        "llm_ranker2": {sym: (True, 0.9)},
    }

    registry = ScreenerRegistry()
    for sid, sym_scores in scores_per_screener.items():
        mock = MagicMock()
        mock.apply.side_effect = lambda syms, bars, cfg, _s=sym_scores: {
            s: _s.get(s, (False, 0.0)) for s in syms
        }
        registry.register(sid, lambda m=mock: m)

    refs = [
        ScreenerRef(screener_id="ind", enabled=True, weight=0.4),
        ScreenerRef(screener_id="ml", enabled=True, weight=0.3),
        ScreenerRef(screener_id="llm_ranker2", enabled=True, weight=0.3),
    ]
    preset = Preset(
        id="w_test",
        name="W",
        preset_type=PresetType.WEIGHTED,
        screeners=refs,
        threshold=0.5,
    )
    executor = PresetExecutor(
        preset_manager=_mock_preset_manager(preset),
        storage=_mock_storage(tmp_path),
        registry=registry,
    )
    result = executor.run_preset("w_test", "u", symbols=[sym], bars=BARS_3)
    # score = (0.8*0.4 + 0.6*0.3 + 0.9*0.3) / 1.0 = 0.32 + 0.18 + 0.27 = 0.77
    assert sym in result.results
    assert abs(result.results[sym]["score"] - 0.77) < 0.01


# ---------------------------------------------------------------------------
# T14 — Weighted: symbol passes if score ≥ threshold
# ---------------------------------------------------------------------------

def test_weighted_passes_threshold(tmp_path: Path):
    """UT-SCR-003.001.M10.T14: symbol with score=0.77 passes threshold=0.7."""
    sym = "AAPL"
    mock = MagicMock()
    mock.apply.side_effect = lambda syms, bars, cfg: {s: (True, 0.8) for s in syms}
    registry = ScreenerRegistry()
    registry.register("ind", lambda: mock)

    refs = [ScreenerRef(screener_id="ind", enabled=True, weight=1.0)]
    preset = Preset(
        id="thresh",
        name="Thresh",
        preset_type=PresetType.WEIGHTED,
        screeners=refs,
        threshold=0.7,
    )
    executor = PresetExecutor(
        preset_manager=_mock_preset_manager(preset),
        storage=_mock_storage(tmp_path),
        registry=registry,
    )
    result = executor.run_preset("thresh", "u", symbols=[sym], bars=BARS_3)
    assert sym in result.results
    assert result.results[sym]["score"] >= 0.7


# ---------------------------------------------------------------------------
# T15 — Weighted: disabled screeners excluded from weighted sum
# ---------------------------------------------------------------------------

def test_weighted_disabled_screener_excluded(tmp_path: Path):
    """UT-SCR-003.001.M10.T15: disabled screener not counted in Σ(weights)."""
    active = MagicMock()
    active.apply.side_effect = lambda syms, bars, cfg: {s: (True, 0.9) for s in syms}
    disabled = MagicMock()
    disabled.apply.side_effect = lambda syms, bars, cfg: {s: (True, 0.1) for s in syms}

    registry = ScreenerRegistry()
    registry.register("active_s", lambda: active)
    registry.register("disabled_s", lambda: disabled)

    refs = [
        ScreenerRef(screener_id="active_s", enabled=True, weight=1.0),
        ScreenerRef(screener_id="disabled_s", enabled=False, weight=1.0),
    ]
    preset = Preset(
        id="dis_test",
        name="Dis",
        preset_type=PresetType.WEIGHTED,
        screeners=refs,
        threshold=0.5,
    )
    executor = PresetExecutor(
        preset_manager=_mock_preset_manager(preset),
        storage=_mock_storage(tmp_path),
        registry=registry,
    )
    result = executor.run_preset("dis_test", "u", symbols=["AAPL"], bars=BARS_3)
    assert not disabled.apply.called
    assert "AAPL" in result.results
    assert abs(result.results["AAPL"]["score"] - 0.9) < 0.01


# ---------------------------------------------------------------------------
# T16 — Stage 3 skipped if enable_llm_ranking=False
# ---------------------------------------------------------------------------

def test_stage3_skipped_when_disabled(tmp_path: Path):
    """UT-SCR-003.001.M10.T16: Stage-3 LLM ranker not called when enable_llm_ranking=False."""
    llm_stage3 = MagicMock()
    llm_stage3.apply.return_value = {}
    ind = _make_screener()
    registry = ScreenerRegistry()
    # Register indicator as Stage 2 screener; register Stage-3 ranker separately
    registry.register("ind_only", lambda: ind)
    registry.register("llm_claude_ranking", lambda: llm_stage3)

    # Preset uses only indicator in Stage 2; LLM ranking explicitly disabled
    refs = [ScreenerRef(screener_id="ind_only", enabled=True, weight=1.0)]
    preset = Preset(
        id="p_no_llm",
        name="NoLLM",
        preset_type=PresetType.WEIGHTED,
        screeners=refs,
        threshold=0.5,
        enable_llm_ranking=False,
    )

    executor = PresetExecutor(
        preset_manager=_mock_preset_manager(preset),
        storage=_mock_storage(tmp_path),
        registry=registry,
    )
    executor.run_preset("p_no_llm", "u", symbols=SYMBOLS_3, bars=BARS_3)
    assert not llm_stage3.apply.called


# ---------------------------------------------------------------------------
# T17 — Stage 3 LLM ranking returns top-N
# ---------------------------------------------------------------------------

def test_stage3_llm_ranking_top_n(tmp_path: Path):
    """UT-SCR-003.001.M10.T17: top_n=2 → only 2 symbols in result."""
    symbols = [f"SYM{i}" for i in range(10)]
    bars = {s: make_bars(s, n=10, base_price=50.0) for s in symbols}

    # All symbols pass Stage 2
    ind = MagicMock()
    ind.apply.side_effect = lambda syms, bars, cfg: {s: (True, 0.8) for s in syms}
    ind.batch_features.return_value = {}

    # LLM gives score only to 2 symbols
    llm = MagicMock()
    llm.apply.side_effect = lambda syms, bars, cfg: {
        s: (True, 0.9 if s in ["SYM0", "SYM1"] else 0.3) for s in syms
    }

    registry = ScreenerRegistry()
    registry.register("ind_s", lambda: ind)
    registry.register("llm_claude_ranking", lambda: llm)

    refs = [ScreenerRef(screener_id="ind_s", enabled=True, weight=1.0)]
    preset = Preset(
        id="top_n",
        name="TopN",
        preset_type=PresetType.WEIGHTED,
        screeners=refs,
        threshold=0.5,
        enable_llm_ranking=True,
        top_n=2,
    )
    executor = PresetExecutor(
        preset_manager=_mock_preset_manager(preset),
        storage=_mock_storage(tmp_path),
        registry=registry,
    )
    result = executor.run_preset("top_n", "u", symbols=symbols, bars=bars)
    assert len(result.results) <= 2


# ---------------------------------------------------------------------------
# T18 — Stage 3 LLM timeout → fallback to Stage 2 results
# ---------------------------------------------------------------------------

def test_stage3_llm_timeout_fallback(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """UT-SCR-003.001.M10.T18: Stage 3 error falls back to Stage 2; WARNING logged."""
    ind = _make_screener()
    llm = MagicMock()
    llm.apply.side_effect = TimeoutError("LLM timed out")
    registry = ScreenerRegistry()
    registry.register("ind_s2", lambda: ind)
    registry.register("llm_claude_ranking", lambda: llm)

    refs = [ScreenerRef(screener_id="ind_s2", enabled=True, weight=1.0)]
    preset = Preset(
        id="fallback",
        name="Fallback",
        preset_type=PresetType.WEIGHTED,
        screeners=refs,
        threshold=0.5,
        enable_llm_ranking=True,
        top_n=5,
    )
    executor = PresetExecutor(
        preset_manager=_mock_preset_manager(preset),
        storage=_mock_storage(tmp_path),
        registry=registry,
    )
    with caplog.at_level(logging.WARNING, logger="us_swing.screener.executor"):
        result = executor.run_preset("fallback", "u", symbols=SYMBOLS_3, bars=BARS_3)
    # Stage 2 results returned (not empty)
    assert len(result.results) > 0
    assert any("fallback" in rec.message.lower() or "stage 3" in rec.message.lower()
               for rec in caplog.records)


# ---------------------------------------------------------------------------
# T19 — on_complete callback fired on successful run
# ---------------------------------------------------------------------------

def test_on_complete_event_emitted(tmp_path: Path):
    """UT-SCR-003.001.M10.T19: on_complete callback invoked with ScreenerRunResult."""
    preset = make_weighted_preset("p_ev")
    registry = ScreenerRegistry()
    registry.register("indicator_composite", lambda: _make_screener())
    registry.register("ml_ensemble", lambda: _make_screener())
    registry.register("llm_claude_ranking", lambda: _make_screener())

    events: list[ScreenerRunResult] = []
    executor = PresetExecutor(
        preset_manager=_mock_preset_manager(preset),
        storage=_mock_storage(tmp_path),
        registry=registry,
    )
    executor.on_complete = events.append

    executor.run_preset("p_ev", "u", symbols=SYMBOLS_3, bars=BARS_3)
    assert len(events) == 1
    assert isinstance(events[0], ScreenerRunResult)
    assert events[0].preset_id == "p_ev"


# ---------------------------------------------------------------------------
# T20 — empty result set completes without error
# ---------------------------------------------------------------------------

def test_empty_result_no_exception(tmp_path: Path):
    """UT-SCR-003.001.M10.T20: all symbols fail → empty results, no exception."""
    fail = MagicMock()
    fail.apply.side_effect = lambda syms, bars, cfg: {s: (False, 0.1) for s in syms}
    registry = ScreenerRegistry()
    registry.register("fail_all", lambda: fail)

    refs = [ScreenerRef(screener_id="fail_all", enabled=True, weight=1.0)]
    preset = Preset(
        id="empty",
        name="Empty",
        preset_type=PresetType.WEIGHTED,
        screeners=refs,
        threshold=0.5,
    )
    executor = PresetExecutor(
        preset_manager=_mock_preset_manager(preset),
        storage=_mock_storage(tmp_path),
        registry=registry,
    )
    result = executor.run_preset("empty", "u", symbols=SYMBOLS_3, bars=BARS_3)
    assert isinstance(result, ScreenerRunResult)
    assert result.results == {}


# ---------------------------------------------------------------------------
# T21 — Stage 3 LLM config carries db, passing_symbols, ai_query, ai_model
#       (SRD-SCR-013.006)
# ---------------------------------------------------------------------------

def test_stage3_passes_db_and_ai_fields_to_llm(tmp_path: Path):
    """UT-SCR-003.001.M10.T21"""
    ind = _make_screener()
    llm = MagicMock()
    llm.apply.side_effect = lambda syms, bars, cfg: {s: (True, 0.7) for s in syms}
    llm.last_reasoning = {}

    registry = ScreenerRegistry()
    registry.register("ind_a", lambda: ind)
    registry.register("llm_claude_ranking", lambda: llm)

    refs = [ScreenerRef(screener_id="ind_a", enabled=True, weight=1.0)]
    preset = Preset(
        id="ai_cfg",
        name="AI Config",
        preset_type=PresetType.WEIGHTED,
        screeners=refs,
        threshold=0.5,
        enable_llm_ranking=True,
        top_n=3,
        ai_query="find bullish breakouts",
        ai_model="claude-sonnet-4-5-20250929",
    )
    fake_db = MagicMock(name="fake_db")
    executor = PresetExecutor(
        db=fake_db,
        preset_manager=_mock_preset_manager(preset),
        storage=_mock_storage(tmp_path),
        registry=registry,
    )
    executor.run_preset("ai_cfg", "u", symbols=SYMBOLS_3, bars=BARS_3)

    cfg = llm.apply.call_args[0][2]
    assert cfg["ai_query"] == "find bullish breakouts"
    assert cfg["ai_model"] == "claude-sonnet-4-5-20250929"
    assert cfg["db"] is fake_db
    assert isinstance(cfg["passing_symbols"], set)
    assert cfg["passing_symbols"].issubset(set(SYMBOLS_3))


# ---------------------------------------------------------------------------
# T22 — ai_reasoning side-channel merges into result[sym]["ai_reasoning"]
#       (SRD-SCR-013.007)
# ---------------------------------------------------------------------------

def test_ai_reasoning_merged_into_results(tmp_path: Path):
    """UT-SCR-003.001.M10.T22"""
    ind = _make_screener()
    llm = MagicMock()
    llm.apply.side_effect = lambda syms, bars, cfg: {s: (True, 0.8) for s in syms}
    llm.last_reasoning = {
        "AAPL":  "Strong breakout above 50d MA",
        "MSFT":  "Range-bound, low momentum",
        "GOOGL": "Weak relative strength",
    }
    registry = ScreenerRegistry()
    registry.register("ind_b", lambda: ind)
    registry.register("llm_claude_ranking", lambda: llm)

    refs = [ScreenerRef(screener_id="ind_b", enabled=True, weight=1.0)]
    preset = Preset(
        id="reasoning",
        name="Reasoning",
        preset_type=PresetType.WEIGHTED,
        screeners=refs,
        threshold=0.5,
        enable_llm_ranking=True,
        top_n=5,
        ai_query="rank these",
    )
    executor = PresetExecutor(
        db=MagicMock(),
        preset_manager=_mock_preset_manager(preset),
        storage=_mock_storage(tmp_path),
        registry=registry,
    )
    result = executor.run_preset("reasoning", "u", symbols=SYMBOLS_3, bars=BARS_3)

    for sym, data in result.results.items():
        assert data.get("ai_reasoning") == llm.last_reasoning[sym]


# ---------------------------------------------------------------------------
# T23 — Stage 3 LLM exception → partial transcript preserved from the screener
#       (ISS-SCR-0001 regression; SRD-SCR-014.003 / SRD-SCR-014.006)
# ---------------------------------------------------------------------------

def test_stage3_llm_exception_preserves_partial_transcript(tmp_path: Path):
    """UT-SCR-003.001.M10.T23"""
    partial = [
        AITranscriptTurn(role="system", content="prompt"),
        AITranscriptTurn(role="user", content="analysing AAPL"),
    ]
    ind = _make_screener()
    llm = MagicMock()

    def _apply(_syms: list[str], _bars: dict, _cfg: dict) -> dict:
        llm.last_transcript = list(partial)
        raise TimeoutError("LLM timed out")

    llm.apply.side_effect = _apply
    llm.last_reasoning = {}

    registry = ScreenerRegistry()
    registry.register("ind_p", lambda: ind)
    registry.register("llm_claude_ranking", lambda: llm)

    refs = [ScreenerRef(screener_id="ind_p", enabled=True, weight=1.0)]
    preset = Preset(
        id="partial",
        name="Partial",
        preset_type=PresetType.WEIGHTED,
        screeners=refs,
        threshold=0.5,
        enable_llm_ranking=True,
        top_n=5,
    )
    executor = PresetExecutor(
        preset_manager=_mock_preset_manager(preset),
        storage=_mock_storage(tmp_path),
        registry=registry,
    )
    result = executor.run_preset("partial", "u", symbols=SYMBOLS_3, bars=BARS_3)

    assert len(result.ai_transcript) == 2
    assert [t.role for t in result.ai_transcript] == ["system", "user"]


# ---------------------------------------------------------------------------
# T24 — Stage 3 input cap: >20 passing symbols trimmed to top 10 by market cap
# ---------------------------------------------------------------------------

def test_stage3_input_capped_to_top_by_market_cap(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
):
    """UT-SCR-003.001.M10.T24: Stage 3 sends at most the top 10 by market cap."""
    symbols = [f"SYM{i:02d}" for i in range(25)]
    bars = {s: make_bars(s, n=50, seed=i) for i, s in enumerate(symbols)}
    # Descending caps: SYM00 largest ... SYM24 smallest.
    market_caps = {s: float(len(symbols) - i) for i, s in enumerate(symbols)}
    top10 = {f"SYM{i:02d}" for i in range(10)}

    ind = _make_screener()
    llm = MagicMock()
    llm.apply.side_effect = lambda syms, b, cfg: {s: (True, 0.7) for s in syms}
    llm.last_reasoning = {}

    registry = ScreenerRegistry()
    registry.register("ind_cap", lambda: ind)
    registry.register("llm_claude_ranking", lambda: llm)

    preset = Preset(
        id="cap",
        name="Cap",
        preset_type=PresetType.WEIGHTED,
        screeners=[ScreenerRef(screener_id="ind_cap", enabled=True, weight=1.0)],
        threshold=0.5,
        enable_llm_ranking=True,
        top_n=10,
        ai_query="rank these",
    )
    notify = MagicMock()
    executor = PresetExecutor(
        db=MagicMock(),
        preset_manager=_mock_preset_manager(preset),
        storage=_mock_storage(tmp_path),
        registry=registry,
        notify=notify,
    )
    with caplog.at_level(logging.WARNING):
        result = executor.run_preset(
            "cap", "u", symbols=symbols, bars=bars, market_caps=market_caps,
        )

    sent = llm.apply.call_args[0][0]
    assert len(sent) == 10
    assert set(sent) == top10
    # Symbols outside the top 10 by market cap are dropped from the passing set.
    assert set(result.results) == top10
    assert "Stage 3 does not support more than 20" in caplog.text
    # The cap notice is surfaced to the user via the notify callback.
    notify.assert_called_once()
    level, msg = notify.call_args[0]
    assert level == "WARNING"
    assert "top 10 by market cap" in msg


# ---------------------------------------------------------------------------
# T25 — Stage 3 input cap not applied when 20 or fewer symbols pass
# ---------------------------------------------------------------------------

def test_stage3_no_cap_when_within_limit(tmp_path: Path):
    """UT-SCR-003.001.M10.T25: All passing symbols sent when count <= 20."""
    symbols = [f"SYM{i:02d}" for i in range(20)]
    bars = {s: make_bars(s, n=50, seed=i) for i, s in enumerate(symbols)}

    ind = _make_screener()
    llm = MagicMock()
    llm.apply.side_effect = lambda syms, b, cfg: {s: (True, 0.7) for s in syms}
    llm.last_reasoning = {}

    registry = ScreenerRegistry()
    registry.register("ind_nocap", lambda: ind)
    registry.register("llm_claude_ranking", lambda: llm)

    preset = Preset(
        id="nocap",
        name="NoCap",
        preset_type=PresetType.WEIGHTED,
        screeners=[ScreenerRef(screener_id="ind_nocap", enabled=True, weight=1.0)],
        threshold=0.5,
        enable_llm_ranking=True,
        top_n=20,
        ai_query="rank these",
    )
    executor = PresetExecutor(
        db=MagicMock(),
        preset_manager=_mock_preset_manager(preset),
        storage=_mock_storage(tmp_path),
        registry=registry,
    )
    executor.run_preset("nocap", "u", symbols=symbols, bars=bars)

    sent = llm.apply.call_args[0][0]
    assert len(sent) == 20
