# Revision Note — RN-GUI-2.4.0-20261119

**Version:** 2.4.0
**Date:** 2026-11-19
**Tool:** GUI
**Artifact:** FO-GUI-043 / SRD-GUI-043.001–.010
**Type:** Feature

---

## Summary

The screener now has a focus layout. The left pane (300 px) shows the open preset as a card with its ranked stocks, and the other presets as folded rows. The right side shows one stock at a time: a header with previous and next, a plan strip, a chart that takes the free height, and detail tabs. The top toolbar and the List / Cards view were removed to give the stock detail more room. This replaces SRD-GUI-022.001, .003 and .008, as the user agreed on 2026-11-19.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-043.001.M01 | `src/us_swing/gui/screener_panel.py` | Open-preset card, ⋯ menu, folded presets with search and filter chips, hide strip, right-click menu, saved last preset and pane state; toolbar and Cards view removed |
| MD-GUI-043.001.M01 | `assets/icons/ellipsis.svg` | New ⋯ menu icon |
| MD-GUI-043.003.M02 | `src/us_swing/gui/screener_views.py` | Two-line stock rows with tier bar; stock list can be detached from the detail view; CardsView, _Card, ViewSwitch, _ScoreBar and _rule_chip deleted |
| MD-GUI-043.007.M03 | `src/us_swing/gui/screener_views.py` | Stock header with sector and previous / next; plan strip over a chart that stretches; QTabBar detail tabs; `ResultRow.sector` and `rows_from_result` sectors argument |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-043.001 | Open preset as a card with its ranked stocks; other presets as folded rows | Implemented |
| SRD-GUI-043.002 | Card header with name, type and run-mode pills, Run now, ⋯ menu, run stepper and Sort | Implemented |
| SRD-GUI-043.003 | Two-line stock row with tier bar, symbol, score, company, rules and red flags | Implemented |
| SRD-GUI-043.004 | Search and All / Swing / Day / Position filter above the folded rows | Implemented |
| SRD-GUI-043.005 | Hide button folds the left pane to a strip; show button brings it back | Implemented |
| SRD-GUI-043.006 | Top toolbar and List / Cards switch removed; right side shows only the selected stock | Implemented |
| SRD-GUI-043.007 | Stock header with symbol, tier, chips, company, sector, score, previous / next, Open in Charts, Add to watchlist | Implemented |
| SRD-GUI-043.008 | Plan strip under the header: Stop, Entry, Target, Reward : risk | Implemented |
| SRD-GUI-043.009 | Chart fills the height between the plan strip and the tabs | Implemented |
| SRD-GUI-043.010 | Tabs AI reasoning, Rules, News, Fundamentals, Bull vs bear; one section at a time; empty tabs greyed | Implemented |

---

## Design Decisions

- Cards view and the top toolbar removed; SRD-GUI-022.001, .003 and .008 replaced by SRD-GUI-043.006 (user agreed 2026-11-19).
- Open preset and pane hidden state saved in `QSettings`; the last open preset reopens on start.
- Startup restore does not trigger an auto-run.
- Right-click Edit, Duplicate and Delete kept on the card and folded rows.
- Previous / next follow the left list order and stop at the ends.
- Empty sections in the left list are hidden; empty detail tabs are greyed, not hidden.

---

## Issues Resolved

None

---

## Test Coverage

16 new UT-GUI-043 cases in `tests/gui/test_screener_focus.py`, all Pass. UT-GUI-022.001.M01.T01–T02 and .003.M01.T01–T02 marked Removed (user, 2026-11-19, SRD-GUI-043.006). Full GUI suite: 777 tests pass. mypy shows no new errors. ruff shows only 3 pre-existing unused imports in `screener_panel.py`. pyqt-code-reviewer approved both phases; fixes made: delete of the open preset clears the card and stepper; preset name map cleared on repopulate; Run now stays off during a run; empty section headers hidden; startup restore does not trigger auto-run; disabled tab colour and no bold on the selected tab.

Layout was checked on an offscreen render with fake data only, not in the live app. User app check: T212 (open).
