# RN-SCR-2.1.1-20260527 — Fix Blank AI Transcript Panel on Stage 3 Fallback

**Date:** 2026-05-27
**Type:** Bug Fix
**Issue:** ISS-SCR-0002
**Affected Modules:**
- `gui/screener_panel.py` → `_refresh_transcript_visibility`
- `gui/ai_transcript_panel.py` → `AITranscriptPanel`
- `screener/screeners/cloud_ai.py` → `CloudAIScreener._apply_legacy`, `_apply_with_tools`
- `screener/executor.py` → `PresetExecutor._run_stage3`

## Change Summary

The AI Transcript panel rendered visible-but-empty whenever Stage 3 LLM ranking
took a fallback path. SRD-SCR-014.006 requires the panel to be hidden when the
transcript is empty, and SRD-SCR-014.003 implies a transcript should be
populated whenever an LLM round trip is attempted. Both requirements were
silently violated. Fix is two-pronged: the panel now hides itself when there
are no turns to show, and `CloudAIScreener` now preserves whatever turns it
had built before falling back, appending a final `system` turn naming the
failure cause.

## Problem

Two cooperating gaps produced the empty-panel state:

1. `_refresh_transcript_visibility()` only checked `preset.enable_llm_ranking`,
   ignoring SRD-SCR-014.006's "AND transcript non-empty" clause. With LLM
   ranking enabled, the panel was unconditionally shown after every run.
2. `CloudAIScreener._apply_with_tools` only assigned `self.last_transcript`
   on the success path. Every premature `return fallback` (client init
   failure, API error, agentic max-turns exceeded) discarded the locally-built
   transcript. `_apply_legacy` had a partial form of this bug for client init
   and API errors before the user turn was constructed. `PresetExecutor._run_stage3`
   compounded the issue by returning `[]` whenever `llm.apply()` raised,
   ignoring any partial state on the screener instance.

When the user's runs hit any fallback (e.g. transient OpenRouter 5xx, rate
limit, or a model that takes longer than `_AGENTIC_MAX_TURNS` to settle), the
result file contained `ai_transcript=[]`, the panel was shown, and nothing
appeared in it.

## Fix

- `AITranscriptPanel.has_turns()` — new public predicate over `_last_turns`,
  consumed by the visibility check.
- `ScreenerPanel._refresh_transcript_visibility` — now hides the panel
  whenever (a) the preset disables LLM ranking, or (b) the transcript is
  empty (both branches of SRD-SCR-014.006).
- `CloudAIScreener._apply_legacy` — builds the user turn upfront and assigns
  it to `self.last_transcript` before the API call; on every fallback path,
  appends a `system` turn describing the failure cause.
- `CloudAIScreener._apply_with_tools` — assigns the system+user turn pair to
  `self.last_transcript` before the agentic loop, then appends a final
  `system` turn on each fallback branch.
- `PresetExecutor._run_stage3` — when `llm.apply()` raises, reads
  `llm.last_transcript` and returns whatever partial transcript was built.

## Test Results

`pytest us_swing/tests/screener/test_executor.py -q` → **23 passed**
(new T23 verifies partial-transcript capture on Stage 3 exception).

Unrelated pre-existing failures remain in `test_preset.py`, `test_lifecycle_e2e.py`,
`test_live_tick_worker.py`, `test_app_service_tick.py`, and
`test_strategy_evaluator.py` — none touched by this fix.

`ruff check` on the four edited source files: 12 errors, all pre-existing in
unrelated regions of `screener_panel.py` (ambiguous `l` names) and an
unrelated unused-import in `executor.py`. Zero errors introduced.

## SRD Impact

None. SRD-SCR-014.003 and SRD-SCR-014.006 correctly described the intended
behaviour. Code was diverged from spec; no SRD changes needed.

## UTCD Update

- `UT-SCR-003.001.M10.T23` added — Stage 3 exception path now captures the
  screener's partial transcript into `ScreenerRunResult.ai_transcript`.
