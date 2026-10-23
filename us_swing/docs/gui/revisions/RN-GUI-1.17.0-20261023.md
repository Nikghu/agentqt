# Revision Note — RN-GUI-1.17.0-20261023

**Version:** 1.17.0
**Date:** 2026-10-23
**Tool:** GUI
**Artifact:** FO-GUI-022 / SRD-GUI-022.001–.007
**Type:** Feature

---

## Summary

The screener results replace the old table with two switchable views. List (the default) shows a ranked list and a detail panel with a real compact chart, Entry / Stop / Target / R:R tiles, the rule checklist and the AI reasoning. Cards shows one card per stock. A Sort box orders both views, and the rule summary shows as chips above the results. The preset rail is restyled with a search box, All / Swing / Day / Position chips, a Weighted / Composite tag and a last-run line. The CSV export adds the plan columns.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-022.001.M01 | `us_swing/src/us_swing/gui/screener_views.py` | New: result rows, sort, CSV rows, preset filter, last-run text, ViewSwitch, ListDetailView, CardsView, ChipGroup, PresetItem |
| MD-GUI-003.001.M01 | `us_swing/src/us_swing/gui/screener_panel.py` | Table, results model and chart delegate removed; views, chip strip, Sort, rail search and chips, cached last-run line; CSV adds Entry / Stop / Target / R:R |
| MD-GUI-017.001.M02 | `us_swing/src/us_swing/gui/theme.py` | New QSS rules for the views, chips and rail |
| MD-GUI-022.001.M01 | `us_swing/assets/icons/` | New icons: list, layout-grid, search (Lucide 0.460.0, ISC licence) |
| MD-GUI-022.001.M01 | `us_swing/tests/gui/test_screener_views.py` | New: 14 tests (UT-GUI-022.*) |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-022.001 | List / Cards switch in the screener toolbar, saved in QSettings; List is the default | Implemented |
| SRD-GUI-022.002 | List view: ranked list and detail panel with tier, score, Open chart, Watchlist, compact chart, plan tiles, rules and reasoning | Implemented |
| SRD-GUI-022.003 | Cards view: one card per stock with rank, tier, score bar, rule chips, reasoning, plan row and buttons | Implemented |
| SRD-GUI-022.004 | Preset rule summary shows once as chips; tiers Strong ≥ 0.70, Watch ≥ 0.40, else Weak | Implemented |
| SRD-GUI-022.005 | Sort box by AI score, R:R or rules passed; rows without R:R sort last | Implemented |
| SRD-GUI-022.006 | Chart, Watchlist, CSV, date navigation and AI transcript keep working; CSV adds plan columns; old table removed | Implemented |
| SRD-GUI-022.007 | Preset rail: search box, All / Swing / Day / Position chips, type tag and last-run line | Implemented |

---

## Design Decisions

- The Watchlist button shows only in the List view, where the detail panel has room for it.
- The detail chart is created once, on the first selection, and is not reloaded on a theme change.
- The last-run line uses a cache, refreshed after each run, so the rail does not read results on every paint.
- Options 2 and 3 from the design review were chosen by the user: switchable views, and the rail restyle.

---

## Issues Resolved

None

---

## Test Coverage

14 new UTCD cases (UT-GUI-022.001–.007), all Pass. GUI suite: 327 passed. ruff and mypy --strict clean on `screener_views.py`. `screener_panel.py` mypy errors fell from 93 to 74; all remaining are pre-existing.

pyqt-code-reviewer: WARNING; 1 HIGH, 3 MEDIUM and 1 LOW, all fixed (no chart reload on theme change, cards keep scroll and detach on reload, last-run cache, debug log, hide before deleteLater).

Visual check: both views and the rail were rendered offscreen. The real WebEngine chart crashes in that offscreen render, so it was stubbed there. **Not yet checked in the running app; the user must check the chart in the detail view.**

Commits: d15dbff6 (Phase A, SCR), a7148033 (Phase B), Phase C (commit pending).
