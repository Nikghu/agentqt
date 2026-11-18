"""Unit tests: AI Ranking stock context in preset.py, cloud_ai.py and executor.py.
Refs: UT-SCR-018.001.M01.T01 – T02, UT-SCR-018.006.M06.T01 – T02, UT-SCR-018.007.M10.T01 – T02,
      UT-SCR-019.001.M01.T01 – T02, UT-SCR-019.003.M06.T01 – T02, UT-SCR-019.007.M10.T01 – T02,
      UT-SCR-020.001.M01.T01 – T02, UT-SCR-020.009.M10.T01 – T02
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from us_swing.core.notifications import AiAnswer
from us_swing.core.stock_context import CompanyFacts, Headline, Research, Review, ReviewRun
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


# ── Phase 2: news tone and web research (FO-SCR-017) ──────────────────────────


def test_news_and_research_round_trip() -> None:
    """UT-SCR-019.001.M01.T01: News and research choices round-trip."""
    preset = _preset(ai_provider="claude", ai_model="claude-sonnet-5-5",
                     ai_context=["news", "research"])
    preset.validate()
    assert Preset.from_dict(preset.to_dict()).ai_context == ["news", "research"]


def test_research_needs_claude() -> None:
    """UT-SCR-019.001.M01.T02: Research needs Claude Code CLI."""
    with pytest.raises(PresetValidationError):
        _preset(ai_provider="openrouter", ai_context=["research"]).validate()


def test_tone_read_from_ranking_answer() -> None:
    """UT-SCR-019.003.M06.T01: Tone read from the ranking answer."""
    screener = CloudAIScreener()
    answer = [{"symbol": "AAPL", "score": 0.8, "news_tone": 0.5},
              {"symbol": "MSFT", "score": 0.6, "news_tone": 2.0},
              {"symbol": "GOOGL", "score": 0.4, "news_tone": "x"}]
    screener._parse_ranking(json.dumps(answer), SYMBOLS, fallback={})
    assert screener.last_news_tone == {"AAPL": 0.5, "MSFT": 1.0}
    assert "news_tone" in cloud_ai._CONTEXT_RULE


def test_legacy_path_uses_array_with_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-SCR-019.003.M06.T02: Legacy path uses array format with context."""
    sent: list[str] = []
    reply = json.dumps([{"symbol": "AAPL", "score": 0.8, "reasoning": "ok", "news_tone": -0.4}])

    def fake_call(self: CloudAIScreener, client: Any, **kwargs: Any) -> Any:
        sent.append(kwargs["messages"][0]["content"])
        message = SimpleNamespace(content=reply)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)

    monkeypatch.setattr(CloudAIScreener, "_make_client", lambda self: object())
    monkeypatch.setattr(CloudAIScreener, "_call_with_retry", fake_call)
    screener = CloudAIScreener()
    result = screener.apply(SYMBOLS, BARS, {"ai_provider": "openrouter", "ai_query": "",
                                            "ai_context_text": "=== STOCK CONTEXT ==="})
    assert "JSON array" in sent[0] and "STOCK CONTEXT" in sent[0]
    assert result["AAPL"] == (True, 0.8)
    assert screener.last_reasoning["AAPL"] == "ok"
    assert screener.last_news_tone == {"AAPL": -0.4}


def _phase2_executor(
    tmp_path: Path, context: list[str], research: MagicMock,
) -> PresetExecutor:
    ind = MagicMock()
    ind.apply.side_effect = lambda syms, bars, cfg: {s: (True, 0.9) for s in syms}
    llm = MagicMock()
    llm.apply.side_effect = lambda syms, bars, cfg: {s: (True, 0.7) for s in syms}
    llm.last_reasoning = {}
    llm.last_news_tone = {"AAPL": -0.6}
    registry = ScreenerRegistry()
    registry.register("ind_a", lambda: ind)
    registry.register("llm_claude_ranking", lambda: llm)
    preset = Preset(
        id="ctx2", name="Ctx2", preset_type=PresetType.WEIGHTED,
        screeners=[ScreenerRef(screener_id="ind_a", enabled=True, weight=1.0)],
        threshold=0.5, enable_llm_ranking=True, top_n=3, ai_provider="claude",
        ai_model="claude-sonnet-5-5", ai_context=context,
    )
    manager = MagicMock()
    manager.load_preset.return_value = preset
    news = MagicMock(return_value={"AAPL": [Headline("Probe opened", "Reuters",
                                                     "2026-11-17T12:00:00Z", "https://r.test")]})
    return PresetExecutor(
        preset_manager=manager, storage=ScreenerResultsStorage(base_dir=tmp_path),
        registry=registry, news_lookup=news, research_runner=research,
    )


def test_executor_saves_tone_news_and_research(tmp_path: Path) -> None:
    """UT-SCR-019.007.M10.T01: Executor saves tone, news and research."""
    research = MagicMock(return_value={
        "AAPL": Research("Offering priced at a discount.", ("https://s.test/a",), "share offering"),
    })
    executor = _phase2_executor(tmp_path, ["news", "research"], research)
    result = executor.run_preset("ctx2", "u", symbols=SYMBOLS, bars=BARS)
    aapl = result.results["AAPL"]
    assert aapl["ai_context"]["news_tone"] == -0.6
    assert aapl["ai_context"]["news_level"] == "red"
    assert aapl["ai_context"]["news"][0]["title"] == "Probe opened"
    assert aapl["ai_research"] == {"summary": "Offering priced at a discount.",
                                   "sources": ["https://s.test/a"], "risk": "share offering"}
    assert aapl["ai_flags"] == ["Negative news", "Research: share offering"]
    assert sorted(research.call_args[0][0]) == sorted(SYMBOLS)
    assert research.call_args[0][1] == "claude-sonnet-5-5"


def test_research_not_run_unless_ticked(tmp_path: Path) -> None:
    """UT-SCR-019.007.M10.T02: Research not run unless ticked."""
    research = MagicMock()
    executor = _phase2_executor(tmp_path, ["news"], research)
    result = executor.run_preset("ctx2", "u", symbols=SYMBOLS, bars=BARS)
    research.assert_not_called()
    assert all("ai_research" not in row for row in result.results.values())


# ── Phase 3: company data and bull vs bear review (FO-SCR-018) ────────────────

_PHASE3 = ["surprise", "fundamentals", "short", "analysts", "review"]


def test_company_and_review_round_trip() -> None:
    """UT-SCR-020.001.M01.T01: New choices round-trip."""
    preset = _preset(ai_provider="claude", ai_model="claude-sonnet-5-5", ai_context=_PHASE3)
    preset.validate()
    assert Preset.from_dict(preset.to_dict()).ai_context == _PHASE3


def test_review_needs_claude() -> None:
    """UT-SCR-020.001.M01.T02: Review needs Claude Code CLI."""
    with pytest.raises(PresetValidationError):
        _preset(ai_context=["review"]).validate()


def _phase3_executor(
    tmp_path: Path, context: list[str], company: MagicMock, review: MagicMock,
) -> PresetExecutor:
    executor = _phase2_executor(tmp_path, context, MagicMock(return_value={}))
    executor._company_lookup = company
    executor._review_runner = review
    return executor


def _review_run(facts: Any, _model: str) -> dict[str, ReviewRun]:
    verdicts = {"AAPL": "Avoid", "MSFT": "Long"}
    return {
        sym: ReviewRun(text, "{...}", Review(("up",), ("down",), verdicts[sym], "medium"), 2.5)
        for sym, text in facts.items() if sym in verdicts
    }


def test_executor_saves_company_and_review(tmp_path: Path) -> None:
    """UT-SCR-020.009.M10.T01: Executor saves facts, review, flag and transcript."""
    company = MagicMock(return_value={
        "AAPL": CompanyFacts(eps_surprise_pct=-3.5, short_pct=24.0, pe=30.0),
    })
    review = MagicMock(side_effect=_review_run)
    executor = _phase3_executor(tmp_path, ["news", *_PHASE3], company, review)
    result = executor.run_preset("ctx2", "u", symbols=SYMBOLS, bars=BARS)
    assert sorted(company.call_args[0][1]) == ["analysts", "fundamentals", "short", "surprise"]
    aapl = result.results["AAPL"]
    assert aapl["ai_context"]["eps_surprise_pct"] == -3.5
    assert aapl["ai_context"]["pe"] == 30.0
    assert aapl["ai_review"]["verdict"] == "Avoid"
    assert aapl["ai_flags"] == ["EPS miss -3.5%", "High short interest (24% of float)",
                                "Negative news", "Review: avoid"]
    assert "Review: long" not in result.results["MSFT"].get("ai_flags", [])
    facts = review.call_args[0][0]["AAPL"]
    assert "Price: close" in facts and "Last EPS: miss -3.5%" in facts
    assert "Negative news" not in facts and "tone" not in facts and "score" not in facts.lower()
    turns = [t for t in result.ai_transcript if t.content.startswith("Bull vs bear · ")]
    assert len(turns) == 2
    assert any(t.role == "assistant" and t.response_time_ms == 2500
               for t in result.ai_transcript)


def test_company_and_review_not_run_unless_ticked(tmp_path: Path) -> None:
    """UT-SCR-020.009.M10.T02: Review and company lookup not run unless ticked."""
    company, review = MagicMock(), MagicMock()
    executor = _phase3_executor(tmp_path, ["news"], company, review)
    result = executor.run_preset("ctx2", "u", symbols=SYMBOLS, bars=BARS)
    company.assert_not_called()
    review.assert_not_called()
    assert all("ai_review" not in row for row in result.results.values())
