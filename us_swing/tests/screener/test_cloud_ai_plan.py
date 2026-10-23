"""Unit tests: MD-SCR-002.003.M06 — screeners/cloud_ai.py trade plan fields.
Refs: UT-SCR-013.009.M06.T01 – UT-SCR-013.009.M06.T03
"""
from __future__ import annotations

import json

from us_swing.screener.screeners.cloud_ai import CloudAIScreener, _tool_system_prompt

SYMBOLS = ["NVDA", "JCI", "WAB", "COF"]


def _parse(records: list[dict[str, object]]) -> CloudAIScreener:
    screener = CloudAIScreener()
    screener._parse_ranking(json.dumps(records), SYMBOLS, fallback={})
    return screener


def test_valid_plan_kept():
    """UT-SCR-013.009.M06.T01: Valid plan kept."""
    screener = _parse([{"symbol": "NVDA", "score": 0.85, "reasoning": "Support held",
                        "entry": 222, "stop": 212, "target": 255}])
    assert screener.last_plan["NVDA"] == {"entry": 222.0, "stop": 212.0, "target": 255.0}


def test_missing_or_bad_value_drops_plan():
    """UT-SCR-013.009.M06.T02: Missing or bad value drops the plan."""
    screener = _parse([
        {"symbol": "JCI", "score": 0.75, "reasoning": "a", "entry": 151, "stop": 144},
        {"symbol": "WAB", "score": 0.65, "reasoning": "b",
         "entry": 289, "stop": "abc", "target": 335},
        {"symbol": "COF", "score": 0.55, "reasoning": "c",
         "entry": -5, "stop": 189, "target": 260},
    ])
    assert screener.last_plan == {}
    assert screener.last_reasoning == {"JCI": "a", "WAB": "b", "COF": "c"}


def test_prompt_asks_for_plan_fields():
    """UT-SCR-013.009.M06.T03: Prompt asks for plan fields."""
    prompt = _tool_system_prompt("find bullish breakouts")
    assert "find bullish breakouts" in prompt
    for key in ('"entry"', '"stop"', '"target"'):
        assert key in prompt
