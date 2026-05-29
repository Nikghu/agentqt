# ISS-SCR-0002 — AI Transcript Panel Renders Blank After Stage 3 Fallback

**Date:** 2026-05-27
**Reported by:** User
**Severity:** Medium
**Status:** Resolved

## Summary

Running a screener preset that has LLM ranking enabled produces a visible but completely empty AI Transcript panel below the results table — no turns, no error indication. Reported as a regression ("it was working fine before").

## Reproduction Steps

1. Select a preset with `enable_llm_ranking=True`
2. Click ▶ Run Now
3. Wait for the run to complete
4. Observe the panel below the results table: the panel is shown but contains no transcript turns

## Root Cause

`_refresh_transcript_visibility()` in `screener_panel.py` checked only one of the two conditions required by SRD-SCR-014.006:

| Condition required by SRD | Checked? |
|---|---|
| (a) preset has `enable_llm_ranking=True` | Yes |
| (b) loaded result's `ai_transcript` is non-empty | **No** |

When Stage 3 LLM took any fallback path — API error, agentic-loop max-turns exceeded, client init failure — `_run_stage3` returned `ai_transcript=[]`. The panel was therefore shown empty instead of being hidden. Additionally, `CloudAIScreener._apply_with_tools` / `_apply_legacy` discarded the in-progress transcript on every premature error return, so even when the LLM had built up a partial conversation (system + user + tool rounds), nothing was preserved for the panel to display.

**SRD root cause:** code diverged from SRD-SCR-014.006 — SRD status unchanged (stays Approved).

## Fix

Three changes, all behaviour preserving on the happy path:

1. **`screener_panel.py::_refresh_transcript_visibility`** — show the panel only when both conditions in SRD-SCR-014.006 hold: preset has `enable_llm_ranking=True` AND the transcript is non-empty.
2. **`ai_transcript_panel.py::AITranscriptPanel.has_turns`** — new public predicate so the visibility check can ask the panel for its turn state without poking private state.
3. **`cloud_ai.py::_apply_legacy` / `_apply_with_tools`** — assign the in-progress transcript to `self.last_transcript` early, and on every premature fallback append a `system` turn that names the failure mode (client init, API error, agentic max-turns, JSON parse failure, empty content). This gives the user a diagnostic transcript instead of silence.
4. **`executor.py::_run_stage3`** — when `llm.apply()` raises, still read `llm.last_transcript` so any partial-turn content built before the exception is preserved in `ScreenerRunResult.ai_transcript`.

**Files:**
- `us_swing/src/us_swing/gui/screener_panel.py` (`_refresh_transcript_visibility`)
- `us_swing/src/us_swing/gui/ai_transcript_panel.py` (`has_turns`)
- `us_swing/src/us_swing/screener/screeners/cloud_ai.py` (`_apply_legacy`, `_apply_with_tools`)
- `us_swing/src/us_swing/screener/executor.py` (`_run_stage3`)
- `us_swing/tests/screener/test_executor.py` (added T23)

## Related

- SRD-SCR-014.003 (`last_transcript` population)
- SRD-SCR-014.006 (panel visibility — both conditions)
- RN-SCR-2.1.1-20260527
