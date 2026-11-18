# Revision Note — RN-SCR-2.9.0-20261118

**Version:** 2.9.0
**Date:** 2026-11-18
**Tool:** SCR
**Artifact:** FO-SCR-015 / SRD-SCR-017.017–.018
**Type:** Feature

---

## Summary

The Accumulation / Distribution settings dialog is rebuilt as four tabs (Basics, Volume & Pattern, Range Zone & Close Zone, Result) with two settings per row. A side panel explains the clicked setting in plain words for the chosen mode, with an example worked from the current values. The Result tab sums up all settings in one paragraph. The title bar shows the mode and a rules level (Wide, Balanced, Strict, Very strict); its tooltip names the two strictest settings. Settings not in use are greyed out. Saved configs and their results do not change.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-SCR-017.001.M32 | `src/us_swing/screener/screeners/acc_dist.py` | Added: `strictness()` and `Strictness` |
| MD-SCR-017.017.M34 | `src/us_swing/gui/acc_dist_tips.py` | Added: tab layout, labels, tips, tab intros, summary |
| MD-SCR-017.013.M33 | `src/us_swing/gui/acc_dist_settings_dialog.py` | Changed: tabbed layout, tip panel, title chips, greyed unused inputs |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-SCR-017.017 | Tabs, two-field rows, tip panel, summary | Implemented (approved by user 2026-11-18) |
| SRD-SCR-017.018 | Rules level in the title bar | Implemented (approved by user 2026-11-18) |

---

## Tests

7 new UT cases Pass (UT-SCR-017.017.M34.T01–T03, .017.M33.T01, .018.M32.T01–T02, .018.M33.T01); all 33 Acc / Dist tests pass. Ruff and mypy --strict clean. The dialog was drawn with the app theme and checked by screenshot on 3 tabs.

## Known

- On the user's current Distribution preset the rules level reads Wide (0.23); default settings read Balanced (0.46).
- The rules level describes the settings only; how many stocks match also depends on the market.
