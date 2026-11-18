"""Unit tests: AI Ranking stock context in preset.py, cloud_ai.py and executor.py.
Refs: UT-SCR-018.001.M01.T01 – T02, UT-SCR-018.006.M06.T01 – T02, UT-SCR-018.007.M10.T01 – T02
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from us_swing.core.notifications import AiAnswer
from us_swing.screener.executor import PresetExecutor
from us_swing.screener.preset import (
    Preset,
    PresetType,
    PresetValidationError,
    ScreenerRef,
)
from us_swing.screener.registry import ScreenerRegistry
from us_swing.screener.screeners import cloud_ai
from us_swing.screener.screeners.cloud_ai import CloudAIScreener, _claude_instruction
from us_swing.screener.storage import ScreenerResultsStorage

from .conftest import make_bars

SYMBOLS = ["AAPL", "MSFT", "GOOGL"]
BARS = {s: make_bars(s, n=60, seed=i) for i, s in enumerate(SYMBOLS)}


def _preset(**kwargs: Any) -> Preset:
    return Preset(id="p1", name="P1", preset_type=PresetType.COMPOSITE, **kwargs)


def test_context_choice_round_trips() -> None:
    """UT-SCR-018.001.M01.T01: Context choice round-trips; old preset empty."""
    preset = _preset(ai_context=["earnings", "sector"])
    data = preset.to_dict()
    assert Preset.from_dict(data).ai_context == ["earnings", "sector"]
    del data["ai_context"]
    assert Preset.from_dict(data).ai_context == []


def test_unknown_context_rejected() -> None:
    """UT-SCR-018.001.M01.T02: Unknown context rejected."""
    with pytest.raises(PresetValidationError):
        _preset(ai_context=["weather"]).validate()


def _run_claude(monkeypatch: pytest.MonkeyPatch, config: dict[str, Any]) -> tuple[str, str]:
    seen: list[tuple[str, str]] = []

    def fake_ask(_config: Any, instruction: str, facts: str, timeout_s: float = 90.0) -> AiAnswer:
        seen.append((instruction, facts))
        return AiAnswer(text=json.dumps([{"symbol": "AAPL", "score": 0.8, "reasoning": "ok"}]))

    monkeypatch.setattr(cloud_ai, "ask_ai", fake_ask)
    CloudAIScreener().apply(SYMBOLS, BARS, {"ai_provider": "claude", "ai_query": "", **config})
    return seen[0]


def test_context_goes_into_ai_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-SCR-018.006.M06.T01: Context goes into the AI request."""
    block = "=== STOCK CONTEXT (market: risk-on) ===\nAAPL | earnings in 3 days (red)"
    instruction, facts = _run_claude(monkeypatch, {"ai_context_text": block})
    assert facts.endswith(block)
    assert "flag" in instruction.lower() and instruction != _claude_instruction("")


def test_no_context_prompt_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-SCR-018.006.M06.T02: No context, prompt unchanged."""
    instruction, facts = _run_claude(monkeypatch, {})
    assert instruction == _claude_instruction("")
    assert "STOCK CONTEXT" not in facts


def _executor(tmp_path: Path, preset: Preset, lookup: Any) -> tuple[PresetExecutor, MagicMock]:
    ind = MagicMock()
    ind.apply.side_effect = lambda syms, bars, cfg: {s: (True, 0.9) for s in syms}
    llm = MagicMock()
    llm.apply.side_effect = lambda syms, bars, cfg: {s: (True, 0.7) for s in syms}
    llm.last_reasoning = {}
    registry = ScreenerRegistry()
    registry.register("ind_a", lambda: ind)
    registry.register("llm_claude_ranking", lambda: llm)
    manager = MagicMock()
    manager.load_preset.return_value = preset
    executor = PresetExecutor(
        preset_manager=manager,
        storage=ScreenerResultsStorage(base_dir=tmp_path),
        registry=registry,
        earnings_lookup=lookup,
    )
    return executor, llm


def _ai_preset(context: list[str]) -> Preset:
    return Preset(
        id="ctx", name="Ctx", preset_type=PresetType.WEIGHTED,
        screeners=[ScreenerRef(screener_id="ind_a", enabled=True, weight=1.0)],
        threshold=0.5, enable_llm_ranking=True, top_n=3, ai_context=context,
    )


def test_executor_builds_sends_and_saves_context(tmp_path: Path) -> None:
    """UT-SCR-018.007.M10.T01: Executor builds, sends and saves context."""
    today = date.today()
    lookup = MagicMock(return_value={"AAPL": today + timedelta(days=2), "MSFT": None,
                                     "GOOGL": today + timedelta(days=30)})
    executor, llm = _executor(tmp_path, _ai_preset(["earnings", "sector"]), lookup)
    result = executor.run_preset(
        "ctx", "u", symbols=SYMBOLS, bars=BARS,
        sectors={"AAPL": "Information Technology"}, context_closes={},
    )
    assert "AAPL | earnings in 2 days (red)" in llm.apply.call_args[0][2]["ai_context_text"]
    aapl = result.results["AAPL"]
    assert aapl["ai_flags"] == ["Earnings in 2 days"]
    assert aapl["ai_context"]["earnings_level"] == "red"
    assert "market" in aapl["ai_context"]
    assert result.results["GOOGL"]["ai_flags"] == []


def test_no_context_ticked(tmp_path: Path) -> None:
    """UT-SCR-018.007.M10.T02: No context ticked."""
    lookup = MagicMock()
    executor, llm = _executor(tmp_path, _ai_preset([]), lookup)
    result = executor.run_preset("ctx", "u", symbols=SYMBOLS, bars=BARS)
    lookup.assert_not_called()
    assert "ai_context_text" not in llm.apply.call_args[0][2]
    assert all("ai_context" not in row and "ai_flags" not in row
               for row in result.results.values())
