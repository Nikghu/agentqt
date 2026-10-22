# Revision Note — RN-GUI-1.6.0-20261022

**Version:** 1.6.0
**Date:** 2026-10-22
**Tool:** GUI
**Artifact:** FO-GUI-015 / SRD-GUI-015.001–015.015
**Type:** Feature

---

## Summary

The screener "Indicator Filters" dialog is replaced by a new rule-builder dialog. It has a library tree on the left and a rule table on the right (mockup C4). The Screener Builder call sites and the Details column use the new dialog and the shared `config_summary()` helper. The old dialog and its defaults are removed. The dialog's frameless base class moves unchanged to a shared module.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-015.002.M01 | `src/us_swing/gui/frameless_dialog.py` | New: `FramelessDialog` moved unchanged from `screener_panel.py` |
| MD-GUI-015.008.M02 | `src/us_swing/gui/indicator_rule_model.py` | New: rule table model; no screening logic |
| MD-GUI-015.009.M03 | `src/us_swing/gui/indicator_rule_delegates.py` | New: toggle, condition, number, settings and remove delegates |
| MD-GUI-015.003.M04 | `src/us_swing/gui/indicator_library_model.py` | New: catalogue tree with usage counts, search proxy, drag source |
| MD-GUI-015.011.M05 | `src/us_swing/gui/indicator_params_dialog.py` | New: frameless editor for one indicator's parameters |
| MD-GUI-015.001.M06 | `src/us_swing/gui/indicator_rules_dialog.py` | New: assembles library pane, rule table, header and footer |
| MD-GUI-003.001.M01 | `src/us_swing/gui/screener_panel.py` | Imports `FramelessDialog` (keeps `_FramelessDialog` alias); both builder call sites open `IndicatorRulesDialog`; Details uses `config_summary()`; removed `_IndicatorConfigDialog`, `_INDICATOR_DEFAULTS`, `_format_indicator_config` |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-015.001 | `IndicatorRulesDialog` shows a library pane left and a rule table right, titled "Indicator Filters" | Implemented |
| SRD-GUI-015.002 | Frameless dialog base moved unchanged to `gui/frameless_dialog.py` as `FramelessDialog` | Implemented |
| SRD-GUI-015.003 | Library tree lists catalogue entries under category rows showing "used / total"; empty categories hidden | Implemented |
| SRD-GUI-015.004 | Case-insensitive search box filters the tree by indicator name | Implemented |
| SRD-GUI-015.005 | Indicators used by a rule show an "in use" tag that updates on add and remove | Implemented |
| SRD-GUI-015.006 | Unavailable indicators are greyed out, show a reason tooltip, and cannot be added | Implemented |
| SRD-GUI-015.007 | Double-click or drag of an available indicator appends a rule with catalogue defaults | Implemented |
| SRD-GUI-015.008 | Rule table has columns On, Indicator, Condition, Value, To, Settings and remove | Implemented |
| SRD-GUI-015.009 | Condition editor lists only allowed conditions; To is editable only for "between" | Implemented |
| SRD-GUI-015.010 | Value and To are numeric spinboxes limited to the indicator's range | Implemented |
| SRD-GUI-015.011 | Settings cell opens a params editor using `ParamSpec` ranges | Implemented |
| SRD-GUI-015.012 | On toggle disables and dims a rule; remove deletes it; tree counts and tags refresh | Implemented |
| SRD-GUI-015.013 | Dialog loads legacy and rule-list configs; returns `rules_to_config()` output on OK; Cancel changes nothing | Implemented |
| SRD-GUI-015.014 | Both Screener Builder call sites open the new dialog; Details uses `config_summary()`; old dialog deleted | Implemented |
| SRD-GUI-015.015 | Controls use `C.BTN_H` / `C.INPUT_H`; inline styles include `outline: none`; logs use the `[Screener]` prefix | Implemented |

---

## Design Decisions

- Layout follows mockup C4 (library tree left, rule table right), as chosen by the user.
- The table model holds no screening logic. All rule logic lives in `core/indicator_rules`.
- Review (pyqt-code-reviewer): APPROVE. Its two MEDIUM findings were fixed: the "To" value is kept on condition change, and an unreadable saved config is kept unless the user edits it.
- Saved rules with bad numbers now raise `IndicatorRuleError`.
- After the first manual look (2026-10-22), the user chose design S2 for editing settings: the parameter editor is now a popup panel under the Settings cell with no title bar or window buttons (Enter saves; Esc or a click outside discards). In the same pass:
  - The Settings column is right-aligned grey text with labels (`period 14`, `MA 10`, `10 bars`, `slope 63 d`, `12 · 26 · 9 ▾`), built by the new core `settings_summary()`.
  - Value/To show `$5`, `$5,000`, `1.0%` and `1.0×`.
  - The Indicator column shows full names.
  - OK is the green `✔ OK` button (`btn_green`).

---

## Issues Resolved

None

---

## Test Coverage

39 unit tests (UT-GUI-015.*) specified and all Pass. Cross-module tests cover MD-GUI-003.001.M01. The GUI test suite crashes at interpreter exit (0xC0000409) independent of this change, and the PyQt6 QtWebEngine DLL fails to load in this environment (tests stub it). ruff and mypy --strict: 0 errors in all new and changed modules. Manual GUI check in the running app is still pending (TODO T33).
