# Revision Note — RN-SCR-2.7.0-20261023

**Version:** 2.7.0
**Date:** 2026-10-23
**Tool:** SCR
**Artifact:** FO-SCR-015 / SRD-SCR-017.001–.013
**Type:** Feature

---

## Summary

New **Accumulation / Distribution** screener (`acc_dist`). Accumulation passes when rallies come on high volume and drops on low volume near the range low; Distribution is the reverse near the range high. Score = mean of rally match % and drop match %. Optional location and close-position filters; every threshold is a setting. Candle-size checks are out of scope.

---

## New Files

| MD ID | File | Purpose |
|---|---|---|
| MD-SCR-017.001.M32 | `us_swing/src/us_swing/screener/screeners/acc_dist.py` | Screener logic and settings |
| MD-SCR-017.013.M33 | `us_swing/src/us_swing/gui/acc_dist_settings_dialog.py` | Settings dialog |

## Modified Files

| File | Change |
|---|---|
| `us_swing/src/us_swing/screener/__init__.py` | Register `acc_dist` |
| `us_swing/src/us_swing/screener/screeners/__init__.py` | Export `AccDistScreener` |

---

## Builder wiring

- `gui/screener_panel.py`: "Acc / Dist" display name; configure button, context menu and weighted row open the settings dialog.

---

## Test Coverage

20 new tests (15 screener, 5 dialog and wiring), all pass. `ruff` and `mypy --strict` clean on the new files. Existing failures on `main`, not from this change: `test_preset.py` T17/T18 and the `test_llm_claude_screener.py` import error.
