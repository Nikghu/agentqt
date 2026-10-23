# Revision Note — RN-GUI-1.19.0-20261023

**Version:** 1.19.0
**Date:** 2026-10-23
**Tool:** GUI
**Artifact:** FO-GUI-023 / SRD-GUI-023.001–.003
**Type:** Feature

---

## Summary

The window now shows its main sections as separate rounded cards with a small gap between them, like VS Code. The user chose "Whole app", a 4 px gap and 6 px corners. Sidebar, each screen, right panel, log panel and icon strip are cards; the Screener shows its preset list and results as two cards. Behaviour does not change.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-023.001.M01 | `us_swing/src/us_swing/gui/cards.py` | New: `card()` wraps a section in a rounded card (2 px padding keeps children inside the corners); `gutter()` marks gap widgets; `GAP` = 4 |
| MD-GUI-001.001.M01 | `us_swing/src/us_swing/gui/main_window.py` | Body row margins and spacing = GAP; screens wrapped in cards; right and log panels keep the gap inside so a closed panel leaves none; open sizes + GAP; sidebar follows its slot geometry |
| MD-GUI-003.001.M01 | `us_swing/src/us_swing/gui/screener_panel.py` | Rail and results become two cards; fixed-width splitter dropped |
| MD-GUI-017.001.M02 | `us_swing/src/us_swing/gui/theme.py` | `_sidebar_qss` (all themes): `shell_gutter`, `shell_card`, sidebar and icon strip full border + radius, `preset_pane` transparent |
| — | `us_swing/src/us_swing/gui/side_panels.py` | Icon strip 46 px wide so buttons stay centred with the new border |
| MD-GUI-023.001.M01 | `us_swing/tests/gui/test_cards.py` | 2 new tests (UT-GUI-023.001.M01.T01–T02) |

---

## Verification

- GUI suite: 335 passed. ruff clean on changed files (4 old unused imports in `screener_panel.py` remain); mypy --strict clean on `cards.py`.
- Screenshots of the real window (Dashboard, Screener, Screener with Watchlist and Live Log open) checked: gaps, corners and closed panels as expected.
- pyqt-code-reviewer: APPROVE, 0 critical / high. Fixed: docstring wording, open sizes + GAP, icon strip width. Left: possible double border inside the log card (looked fine in Carbon).

## Not done

- Inside of Dashboard, Execution, Charts and Settings is not split into smaller cards (possible later step).
- Mocha and VS Code themes not checked by eye.

- Follow-up (SRD-GUI-023.004, user request): the gap colour is now the theme's lighter hover grey instead of the dark title-bar colour, so sections stand out clearly.
