# Revision Note — RN-GUI-2.5.0-20261119

**Version:** 2.5.0
**Date:** 2026-11-19
**Tool:** GUI
**Artifact:** FO-GUI-044 / SRD-GUI-044.001–.007
**Type:** Feature

---

## Summary

The Screener left pane is now a tree. My presets sit in Swing, Day and Position folders, and ready-made presets sit in their own folder. The open preset opens in place inside its folder, with Run, the ⋯ menu, the run stepper, tags, Sort and its stocks under it. Stock rows are one line with a score bar. The header has Search (opens a box), New preset and Collapse all; the Hide panel button, style chips and the open-preset card are gone. A status line sits at the bottom. The user picked design option B on https://claude.ai/artifact/62FR3QeEZdYmjNN2tV956p. SRD-GUI-043.001–.005 are replaced by SRD-GUI-044.007 (user approved 2026-11-19).

The same session also added a drag bar above the chart's volume strip (SRD-GUI-043.011, commit 7be11f9b) and kept rule values next to their names in the detail tabs (commit 05f7d537).

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-044.001.M01 | `src/us_swing/gui/screener_tree.py` | New: folder row, preset row, branch frame, folder for a preset |
| MD-GUI-044.001.M02 | `src/us_swing/gui/screener_panel.py` | Left pane rebuilt as a 320 px tree; search box, collapse all, saved closed folders, status line; hide strip, chips, card and old preset list removed |
| MD-GUI-044.001.M02 | `assets/icons/folder.svg`, `assets/icons/chevrons-down-up.svg` | New icons |
| MD-GUI-044.004.M03 | `src/us_swing/gui/screener_views.py` | One-line stock row with `_ScoreBar`; `STOCK_ROW_H` |
| MD-GUI-044.001.M02 | `src/us_swing/gui/theme.py` | Tree row, branch guide line and footer rules; open card rules removed |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-044.001 | Swing, Day, Position and Ready-made folders with counts; closed folders saved | Implemented |
| SRD-GUI-044.002 | Preset opens in place; the one that was open closes; last open preset reopens | Implemented |
| SRD-GUI-044.003 | Open row with count, Run, ⋯ menu; run stepper, Sort and tags under it | Implemented |
| SRD-GUI-044.004 | One-line stock row with score bar and red flags | Implemented |
| SRD-GUI-044.005 | Search box, New preset and Collapse all in the header | Implemented |
| SRD-GUI-044.006 | Status line at the bottom | Implemented |
| SRD-GUI-044.007 | Hide panel, style chips and open card removed | Implemented |

---

## Design Decisions

- Only Hide panel was dropped from the header; Collapse all stays (user, 2026-11-19).
- Ready-made presets get their own folder; search box opens from 🔍; closed folders are remembered (user, 2026-11-19).
- A preset goes to the folder of its first ticked trading style (Swing, Day, Position order); none ticked → Swing. Fixed after the user saw a Day preset stay in Swing (the tree read a wrong field).
- Trading Style in Edit Preset allows one choice only (SRD-GUI-042.007, user request); this changes "check multiple" in SRD-SCR-007.011.
- Pane widened from 300 to 320 px so the tag line and Sort fit.
- Opening a preset opens its folder; folder clicks during a search are not saved; Collapse all closes the search first (review fixes).

---

## Issues Resolved

None

---

## Test Coverage

14 new UT-GUI-044 cases in `tests/gui/test_screener_focus.py`, all Pass; 8 UT-GUI-043 rows marked Removed. GUI tests: 784 pass, run in three parts because a known crash in the dashboard tile tests stops a full run (the last commit crashes the same way). mypy: no new errors. ruff: only 3 old unused imports in `screener_panel.py`. pyqt-code-reviewer: approve; its medium and low points fixed.

Layout checked on a hidden render with fake data only, not in the live app. User app check: T213 (open).
