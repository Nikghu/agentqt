# Revision Note — RN-GUI-1.18.0-20261023

**Version:** 1.18.0
**Date:** 2026-10-23
**Tool:** GUI
**Artifact:** FO-GUI-022 / SRD-GUI-022.008–.012
**Type:** Feature

---

## Summary

The screener results get the "Option A · Clean list + detail" polish, chosen by the user from the design canvas. A page header now sits over the results with the preset name, run tags and a run line. The run date moves into a stepper, the AI transcript opens in a drawer from a header pill, and the list and detail get company names, a plan box with a risk / reward bar and ✓ / ✕ rule icons. The look is calmer: accent colour only on Run now and the selection, pill rule chips and a segmented style control.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-022.001.M01 | `us_swing/src/us_swing/gui/screener_views.py` | New `RunStepper`, `SideDrawer`, `_RiskRewardBar`, header text helpers (`run_date_text`, `run_meta_text`, `transcript_pill_text`); `ResultRow.name` for the company line |
| MD-GUI-003.001.M01 | `us_swing/src/us_swing/gui/screener_panel.py` | Page header, Run now as the only accent button, Watchlist toolbar button removed, transcript pill opens the drawer, `+ New preset` in the rail header, segmented style chips, type tag dropped |
| MD-GUI-017.001.M02 | `us_swing/src/us_swing/gui/theme.py` | `_sidebar_qss` rules for the pill chips, segmented control and + button |
| MD-GUI-011.001.M01 | `us_swing/src/us_swing/gui/chart_panel.py` | `hide_toolbar()` so the detail chart shows without its input bar |
| — (no MD row) | `us_swing/src/us_swing/gui/ai_transcript_panel.py` | `hide_title` option so the transcript shows in the drawer without its own title |
| MD-GUI-022.001.M01 | `us_swing/assets/icons/` | New icons: chevron-left, chevron-right, message-square (Lucide 0.460.0, ISC licence) |
| MD-GUI-022.001.M01 | `us_swing/tests/gui/test_screener_views.py` | 6 new tests (UT-GUI-022.008–.011) |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-022.008 | Page header over the results: preset name, Weighted / Composite tag, Auto / Manual run tag and run line; Run now is the only filled accent button; toolbar Watchlist button removed | Implemented |
| SRD-GUI-022.009 | Run stepper: older / newer arrows and run date ("Oct 22, 2026", Latest tag); clicking the date lists saved runs | Implemented |
| SRD-GUI-022.010 | "AI transcript · N steps · $cost" header pill opens the transcript in a drawer over the right of the results; bottom transcript panel removed | Implemented |
| SRD-GUI-022.011 | List rows show rank, symbol, company name, score bar and "2/4" rules; detail shows company line, Open in Charts, Add to watchlist, chart without input bar, one plan box with risk / reward bar and ✓ / ✕ rule list | Implemented |
| SRD-GUI-022.012 | Look: UI font for numbers, accent kept for Run now and selection, pill rule chips, segmented style chips, + New preset in rail header, type tag dropped | Implemented |

---

## Design Decisions

- The transcript moved from the bottom splitter into a SideDrawer over the right of the results; Esc or ✕ closes it.
- Design option A was chosen by the user from the design canvas.

---

## Issues Resolved

None

---

## Test Coverage

6 new UTCD cases (UT-GUI-022.008.M01.T01, .009.M01.T01–T02, .010.M01.T01–T02, .011.M01.T01), all Pass. GUI suite: 333 passed. ruff clean on changed files except 4 pre-existing unused imports in `screener_panel.py`. mypy --strict clean on `screener_views.py`.

pyqt-code-reviewer: 0 critical / 0 high. 4 medium fixed: drawer focus for Esc, resize during slide, menu rebuilt inside its own action slot, one reused animation. Low findings fixed: zero-width parent, explicit lambda argument. Left as is: the "closed" signal fires at slide start.

Left out of the mock: 1D / 1W chart tabs (the chart uses the preset timeframe).

Visual check: not yet checked by the user in the running app.

- Follow-up: removed the floating busy bar from the header; a running scan shows "Running…" on Run now and "Scanning symbols…" in the run line (SRD-GUI-022.008).
