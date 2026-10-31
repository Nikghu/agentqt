# Revision Note — RN-GUI-1.52.0-20261031

**Version:** 1.52.0
**Date:** 2026-10-31
**Tool:** GUI
**Artifact:** FO-GUI-031 / SRD-GUI-031.068
**Type:** Feature

---

## Summary

The Backtest view tabs (Trade Inspector, Detail Report, Reports) are replaced by one segmented pill bar: Inspector, Report and Saved runs, each with an icon (option B of https://claude.ai/artifact/DUW3e9Mv6kAzhi4zWTLDEG). Keys 1, 2 and 3 switch views; a text field keeps the key while you type. A short note beside the bar says what the view holds, and the Variant picker sits on the right with a label that shows only when the run has more than one variant.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-031.003.M03 | `gui/backtest_workspace.py` | `QTabWidget` replaced by `QStackedWidget` plus `view_switch` (`ChipGroup`), `view_note`, 1 / 2 / 3 `QShortcut`s, `variant_label` |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-031.068 | View pill bar with icons, keys, note and Variant picker | Implemented |

---

## Design Decisions

- `self.tabs` stays the name of the view stack, so existing `setCurrentWidget` calls and tests keep working.
- Shortcuts use the window context; Qt ignores them while the Backtest screen is hidden, and text fields accept the key first (ShortcutOverride).

---

## Issues Resolved

None

---

## Test Coverage

UT-GUI-031.068.M03.T01 added; UT-GUI-031.050.M03.T01 and the Report-tab check updated. Full GUI suite 592 passed, same 22 test-order errors as main. ruff clean, no mypy errors in changed lines. Real-app check by user pending.
