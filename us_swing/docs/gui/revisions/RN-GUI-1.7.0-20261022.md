# Revision Note — RN-GUI-1.7.0-20261022

**Version:** 1.7.0
**Date:** 2026-10-22
**Tool:** GUI
**Artifact:** FO-GUI-016 / SRD-GUI-016.001–016.011
**Type:** Feature

---

## Summary

The screener "Price Action" config dialog is replaced by a new `PriceActionRulesDialog`. It has a pattern library on the left, a slim rule table on the right and a threshold header. The dialog reuses the indicator library tree, the toggle, settings and remove delegates, and the params popup, through small Protocol and argument changes. Both Screener Builder call sites and the Details column now use the new dialog and `pattern_config_summary()`. The old price action dialog, its labels and its defaults are removed.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-016.004.M07 | `src/us_swing/gui/pattern_rule_model.py` | New: table model for the dialog's `PatternRule` list; no screening logic |
| MD-GUI-016.001.M08 | `src/us_swing/gui/price_action_rules_dialog.py` | New: assembles pattern library, threshold header, rule table and footer |
| MD-GUI-015.003.M04 | `src/us_swing/gui/indicator_library_model.py` | `LibraryEntry` Protocol; `LibraryTreeModel` takes `entries` and `categories` (defaults: indicator catalogue) |
| MD-GUI-015.009.M03 | `src/us_swing/gui/indicator_rule_delegates.py` | `RuleRowsModel` Protocol for toggle and remove; Settings paints the model's display text |
| MD-GUI-015.008.M02 | `src/us_swing/gui/indicator_rule_model.py` | Settings column returns `settings_summary()` as display text |
| MD-GUI-015.011.M05 | `src/us_swing/gui/indicator_params_dialog.py` | `spec` typed as a `ParamsOwner` Protocol so pattern specs work |
| MD-GUI-003.001.M01 | `src/us_swing/gui/screener_panel.py` | Both price action call sites open `PriceActionRulesDialog`; Details adds `pattern_config_summary()`; deleted `_PriceActionConfigDialog`, `_PA_PATTERN_LABELS`, `_PA_DEFAULTS`, `_format_price_action_config`, and the now-unused `_CHECKBOX_QSS` and `_hdivider` |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-016.001 | `PriceActionRulesDialog` shows a pattern library left and a rule table right, titled "Price Action Patterns" | Implemented |
| SRD-GUI-016.002 | Library tree model takes any catalogue and category enum, so it reuses search, "in use" tags and counts | Implemented |
| SRD-GUI-016.003 | Double-click or drag of a pattern appends a rule with catalogue defaults | Implemented |
| SRD-GUI-016.004 | Rule table has columns On, Pattern, Settings and remove | Implemented |
| SRD-GUI-016.005 | Toggle, settings and remove delegates work with both the indicator and the pattern table models | Implemented |
| SRD-GUI-016.006 | Settings cell opens the shared params popup; patterns with no params show "—" and open nothing | Implemented |
| SRD-GUI-016.007 | Header shows rule count, enabled count and "Pass when ≥ [N] % of patterns match" (0–100 %, steps of 5) | Implemented |
| SRD-GUI-016.008 | On toggle disables and dims a rule; remove deletes it; tree counts and tags refresh | Implemented |
| SRD-GUI-016.009 | Dialog loads legacy and rule-list configs; returns `pattern_rules_to_config()` output on OK; Cancel changes nothing | Implemented |
| SRD-GUI-016.010 | Both call sites open the new dialog; Details shows `pattern_config_summary()`; old dialog deleted | Implemented |
| SRD-GUI-016.011 | Controls use `C.BTN_H` / `C.INPUT_H`; inline styles include `outline: none`; logs use the `[Screener]` prefix | Implemented |

---

## Design Decisions

- Layout "Library + slim table" was chosen by the user on 2026-10-22. It is the same library tree as the indicator dialog, so the two dialogs look and behave alike.
- The table model holds no screening logic. All rule logic lives in `core/price_patterns`.
- Review (pyqt-code-reviewer): APPROVE. Fixed: Details summary keeps the first-reference-per-screener behaviour; singular "1 pattern" text; warning text is one sentence.
- Not fixed (same as the indicator dialog): a 0 ms `QTimer.singleShot` without a receiver.

---

## Issues Resolved

None

---

## Test Coverage

25 unit test rows (UT-GUI-016.*) Pass. FO-GUI-015 tests still pass. Cross-module tests cover MD-GUI-003.001.M01. ruff and mypy --strict: 0 errors in new and changed modules. Manual GUI check in the running app is still pending (TODO T33, T37).
