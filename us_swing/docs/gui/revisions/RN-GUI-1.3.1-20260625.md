# Revision Note — RN-GUI-1.3.1-20260625

**Tool:** GUI
**Version:** 1.3.1
**Date:** 2026-06-25
**Type:** enhancement
**Author:** Claude Opus 4.8 under user direction
**Phase:** Active Trades inline risk editor

---

## Summary

Added an **"Off"** option to the trailing-mode dropdown in the Active Trades inline
risk editor (`_RiskEditorWidget`). A user can now disable trailing on an open cycle —
previously the dropdown only offered `$` / `%`, so once trailing was set there was no
way to turn it off from the GUI. Backend `validate_trailing_mode` now accepts an empty
string as "no trailing" so the choice flows through `update_risk` to the live stop
calculation. All changes are against already-Approved FO-GUI-014 / FO-EXE-012 — **no
new SRDs introduced**.

## Changes

| Area | Change |
|---|---|
| Trail mode dropdown | `_RiskEditorWidget` dropdown items are now `["Off", "$", "%"]`. A cycle with no trailing mode shows "Off" selected (first item) instead of defaulting to "$". |
| Save payload | `_collect_changed_fields()` maps the "Off" selection to an empty string `""` before diffing, so picking "Off" on a trailing cycle saves `trailing_mode=""`. |
| Backend validation | `validate_trailing_mode` treats `""` (like `None`) as "no trailing" instead of raising `ValueError`. The live calc already drops the trailing stop when the mode is neither `$` nor `%`, so an empty mode disables trailing end-to-end. |

## Files Changed

| File | Change |
|---|---|
| `gui/risk_editor_widget.py` | Added "Off" dropdown item; map "Off" → `""` in `_collect_changed_fields` |
| `execution/trade_cycle/_dto.py` | `validate_trailing_mode` accepts `""` as off |
| `tests/gui/test_risk_editor_widget.py` | New — UT-GUI-014.001.M03.T09, T10 |
| `tests/execution/test_trade_cycle_service.py` | New — UT-EXE-012.002.M02.T20 |

## Traceability

| Artifact | ID |
|---|---|
| FO | FO-GUI-014, FO-EXE-012 |
| SRD | SRD-GUI-014.007 (no text change), SRD-EXE-012.002 (no text change) |
| MD | MD-GUI-014.001.M03, MD-EXE-012.002.M02 |
| Tests | UT-GUI-014.001.M03.T09, T10; UT-EXE-012.002.M02.T20 |

## Tests / Checks

| Check | Result |
|---|---|
| `tests/gui/test_risk_editor_widget.py` | Pass (2) |
| `tests/execution/test_trade_cycle_service.py` | Pass (35) |
| `tests/execution/test_trade_cycle_schema_dto.py` | Pass |
| `ruff` | Clean on both edited modules |
| `mypy --strict` | No new errors on the two edited files (pre-existing errors elsewhere unchanged) |

## Deferred / Notes

- The Hard Stop / Target / Trail Offset spinbox minimums are unchanged — the original
  "allow 0" request is satisfied by the "Off" option, so no spinbox can take 0.
