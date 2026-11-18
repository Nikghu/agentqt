# Revision Note — RN-SCR-2.11.0-20261118

**Version:** 2.11.0
**Date:** 2026-11-18
**Tool:** SCR (with GUI)
**Artifact:** FO-SCR-016 / SRD-SCR-018.001–.007, FO-GUI-022 / SRD-GUI-022.016–.017
**Type:** Feature

---

## Summary

AI Ranking can now see stock context beyond price (phase 1). Each preset ticks Earnings date and / or Sector strength. For the stocks reaching Stage 3 the app looks up the next earnings date (Yahoo Finance, cached once a day per stock), ranks each stock's sector against RSP over 1 month, and reads the market regime from SPY's 50- and 200-day averages. Fixed rules mark red flags: earnings within 5 days, or a sector in the bottom 3 of 11. A STOCK CONTEXT block goes into the same AI request (both providers) and the AI is told to weigh the flags and name them in its reasoning; code does not change the scores. Results save `ai_context` and `ai_flags`. The result list shows a ⚑ count, the detail shows green / yellow / red chips and a Red flags section, and cards show the chips and ⚑.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-SCR-018.004.M35 | `src/us_swing/core/stock_context/_sector.py` | New: sector list and moves (moved from `gui/sector_rotation.py`), GICS → ETF map |
| MD-SCR-018.002.M36 | `src/us_swing/core/stock_context/_earnings.py` | New: `EarningsLookup` with daily JSON cache |
| MD-SCR-018.003.M37 | `src/us_swing/core/stock_context/_context.py`, `__init__.py` | New: levels, flags, regime, prompt block |
| MD-SCR-001.001.M01 | `src/us_swing/screener/preset.py` | Added: `ai_context` |
| MD-SCR-002.003.M06 | `src/us_swing/screener/screeners/cloud_ai.py` | Added: context block + flag rule on all prompt paths |
| MD-SCR-003.001.M10 | `src/us_swing/screener/executor.py` | Added: build, send and save context; `earnings_lookup`, `sectors`, `context_closes` |
| MD-GUI-022.001.M01 | `src/us_swing/gui/screener_panel.py`, `gui/screener_views.py` | Added: context tick boxes; chips, Red flags, ⚑ count |
| MD-GUI-025.022.M06 | `src/us_swing/gui/sector_rotation.py` | Changed: imports the sector code from core |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-SCR-018.001 | Preset context choice | Implemented (approved by user 2026-11-18) |
| SRD-SCR-018.002 | Earnings date lookup, cached daily | Implemented (approved by user 2026-11-18) |
| SRD-SCR-018.003 | Earnings levels and flag | Implemented (approved by user 2026-11-18) |
| SRD-SCR-018.004 | Sector rank vs RSP and flag | Implemented (approved by user 2026-11-18) |
| SRD-SCR-018.005 | SPY market regime | Implemented (approved by user 2026-11-18) |
| SRD-SCR-018.006 | Context block in the AI prompt | Implemented (approved by user 2026-11-18) |
| SRD-SCR-018.007 | Context and flags saved in results | Implemented (approved by user 2026-11-18) |
| SRD-GUI-022.016 | Context tick boxes in Edit Preset | Implemented (approved by user 2026-11-18) |
| SRD-GUI-022.017 | Chips, Red flags, ⚑ count | Implemented (approved by user 2026-11-18) |

---

## Tests

17 new UT cases Pass (14 UT-SCR-018.*, 3 UT-GUI-022.016–.017). 540 screener, core and screener-GUI tests pass. Ruff clean and mypy --strict clean on the new package. Checked with real data: candles.db closes for 13 symbols and live Yahoo earnings dates gave the expected block (NVDA earnings today + weakest sector). Screenshots of the result view and the AI box taken in a real window.

## Known

- `test_preset.py` T17/T18 and `test_llm_claude_screener.py` were already failing before this change.
- Backtests stay price-only; the context is fetched only for live runs.
- Phase 2 (news tone, web research for top picks) is not started.
- A full screener run with AI ranking in the app is still to be checked by the user (TODO T206).
