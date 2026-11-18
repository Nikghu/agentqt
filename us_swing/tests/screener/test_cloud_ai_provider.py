"""Unit tests: MD-SCR-001.001.M01 preset.py and MD-SCR-002.003.M06 cloud_ai.py — AI Provider.
Refs: UT-SCR-013.010.M01.T01 – T02, UT-SCR-013.011.M06.T01 – T02
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from us_swing.core.notifications import AiAnswer
from us_swing.data.models import OHLCVBar
from us_swing.screener.preset import Preset, PresetType, PresetValidationError
from us_swing.screener.screeners import cloud_ai
from us_swing.screener.screeners.cloud_ai import CloudAIScreener

SYMBOLS = ["NVDA", "JCI"]


def _bars(symbol: str) -> list[OHLCVBar]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        OHLCVBar(symbol=symbol, datetime=start + timedelta(days=i), open=100.0 + i,
                 high=101.0 + i, low=99.0 + i, close=100.5 + i, volume=1_000_000,
                 timeframe="1d")
        for i in range(60)
    ]


def _preset(**kwargs: Any) -> Preset:
    return Preset(id="p1", name="P1", preset_type=PresetType.COMPOSITE, **kwargs)


def test_provider_round_trips_and_old_preset_is_openrouter() -> None:
    """UT-SCR-013.010.M01.T01: Provider round-trips; old preset is OpenRouter."""
    preset = _preset(ai_provider="claude", ai_model="claude-sonnet-5-5")
    assert Preset.from_dict(preset.to_dict()).ai_provider == "claude"
    old = preset.to_dict()
    del old["ai_provider"]
    assert Preset.from_dict(old).ai_provider == "openrouter"


def test_model_format_checked_only_for_openrouter() -> None:
    """UT-SCR-013.010.M01.T02: Model format checked only for OpenRouter."""
    _preset(ai_provider="claude", ai_model="claude-sonnet-5-5").validate()
    with pytest.raises(PresetValidationError):
        _preset(ai_provider="openrouter", ai_model="claude-sonnet-5-5").validate()
    with pytest.raises(PresetValidationError):
        _preset(ai_provider="x", ai_model="claude-sonnet-5-5").validate()


def test_claude_path_ranks_in_one_cli_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-SCR-013.011.M06.T01: Claude path ranks in one CLI request."""
    calls: list[tuple[Any, str, str]] = []
    answer = json.dumps([
        {"symbol": "NVDA", "score": 0.9, "reasoning": "Strong trend",
         "entry": 222, "stop": 212, "target": 255},
        {"symbol": "JCI", "score": 0.4, "reasoning": "Weak volume"},
    ])

    def fake_ask(config: Any, instruction: str, facts: str, timeout_s: float = 90.0) -> AiAnswer:
        calls.append((config, instruction, facts))
        return AiAnswer(text=answer, provider="claude", seconds=1.0)

    def no_client(self: CloudAIScreener) -> Any:
        raise AssertionError("OpenRouter client must not be made")

    monkeypatch.setattr(cloud_ai, "ask_ai", fake_ask)
    monkeypatch.setattr(CloudAIScreener, "_make_client", no_client)
    screener = CloudAIScreener()
    result = screener.apply(SYMBOLS, {s: _bars(s) for s in SYMBOLS}, {
        "ai_provider": "claude", "ai_model": "claude-haiku-4-5",
        "ai_query": "strongest momentum", "db": object(),
    })

    assert len(calls) == 1
    config, instruction, facts = calls[0]
    assert config.claude_model == "claude-haiku-4-5" and config.default == "claude"
    assert "strongest momentum" in instruction and "get_candle_data" not in instruction
    assert "NVDA" in facts and "JCI" in facts
    assert result == {"NVDA": (True, 0.9), "JCI": (True, 0.4)}
    assert screener.last_reasoning["NVDA"] == "Strong trend"
    assert screener.last_plan["NVDA"] == {"entry": 222.0, "stop": 212.0, "target": 255.0}
    assert screener.last_transcript[-1].role == "assistant"


@pytest.mark.parametrize("answer", [
    AiAnswer(error="Claude Code CLI: not installed on this PC"),
    AiAnswer(text="Sorry, I cannot rank these.", provider="claude"),
])
def test_claude_failure_falls_back(monkeypatch: pytest.MonkeyPatch, answer: AiAnswer) -> None:
    """UT-SCR-013.011.M06.T02: CLI failure falls back."""
    monkeypatch.setattr(cloud_ai, "ask_ai", lambda *args, **kwargs: answer)
    screener = CloudAIScreener()
    result = screener.apply(SYMBOLS, {s: _bars(s) for s in SYMBOLS}, {
        "ai_provider": "claude", "ai_model": "claude-sonnet-5-5", "ai_query": "",
    })
    assert result == {"NVDA": (True, 0.0), "JCI": (True, 0.0)}
    assert screener.last_transcript[-1].role == "system"
    assert "Stage 2" in screener.last_transcript[-1].content
