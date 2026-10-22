# Issue Report — ISS-GUI-0004

**Tool:** GUI (Trade Execution → Filtered Stocks; monitoring ledger; intraday candle fetch)
**Severity:** Medium (stocks from a preset meant for nobody reached the Execution section and the engine)
**Status:** Resolved
**Date Opened:** 2026-10-22
**Date Resolved:** 2026-10-22
**Reporter:** User (screenshots: preset "Test" with no assigned users; its 6 stocks listed in Filtered Stocks as RUN Manual)
**Resolution:** RN-GUI-1.7.2-20261022
**Related:** SRD-GUI-004.008 (screener → execution bridge), SRD-SCR-004.007 (scheduler skips unassigned presets)

---

## Symptom

Preset "Test" (Weekly) had no users assigned. After a manual run, MMM, CRL, EVRG, HAS, HLT and
TRV appeared in Trade Execution → Filtered Stocks with screener "Test".

## Root Cause

`AppService.get_latest_screener_results()` loaded the newest result of every
`preset_*` folder under `~/.usswing/screener_results/` and never checked the preset's
`assigned_to`. A result folder with no matching preset (deleted preset) was also included,
named by its raw id. The scheduler already skipped unassigned presets, so only manual runs
leaked through.

The same list feeds the Filtered Stocks pane, the monitoring ledger and the intraday candle
fetch, so the engine also processed these stocks.

**SRD root cause: scope gap** — SRD-GUI-004.008 defines the bridge but has no assignment
rule. New **SRD-GUI-004.009**.

## Fix

| File | Change |
|---|---|
| `gui/app_service.py` | `get_latest_screener_results()` skips a result folder when its preset is not found or has an empty `assigned_to` |

User choices (2026-10-22): exclude from both display and engine; also hide deleted presets.

## Verification

`tests/gui/test_app_service_screener_feed.py` — 3 cases (UT-GUI-004.001.M01.T08–T10), pass.
`tests/gui/`: 235 passed.

## Affected Artifacts

| Artifact | Change | Status |
|---|---|---|
| SRD (GUI) | SRD-GUI-004.009 added | Implemented |
| MD (GUI) | MD-GUI-004.001.M01 change row | Added |
| UTCD (GUI) | UT-GUI-004.001.M01.T08–T10 | Pass |
| TRACE (GUI) | Forward row for SRD-GUI-004.009 | Added |

## Notes

- Manual runs of an unassigned preset still show in the Screener tab — only Execution ignores them.
- `preset_meta` holds admin presets plus the active user's own presets, so another user's
  private preset is also skipped. Today there is one account.
