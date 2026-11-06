# Revision Note — RN-MKT-0.10.0-20261106

**Version:** 0.10.0
**Date:** 2026-11-06
**Tool:** MKT (with GUI)
**Artifact:** FO-MKT-009 (P8) / SRD-MKT-009.001–.008; SRD-GUI-034.037–.038 (FO-GUI-034 still at Reopen)
**Type:** Feature

---

## Summary

P8 measures how the desk's lead picks turn out. A new desk step, "Pick results", works out a paper result for every lead pick from daily candles, whether the Master approved, rejected or let it expire. A pick is entered when its trigger is touched within 5 trading days. It ends at its stop, its 2R target, or the close of its 10th day. When an AI Desk trade closes in the app, its real result is saved against the pick. A shared results view gives totals and breakdowns by Master decision, setup review grade and news tone. These show in a new live AI Desk → Results section and in the Friday weekly report. Results are grouped by skill input, never by employee name.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-MKT-009.001.M01 | `us_swing/src/us_swing/market/pick_results.py` | New: `paper_result()`, `PaperResult`, `Bar`, `PickResultsStep` ("Pick results") |
| MD-MKT-009.004.M02 | `us_swing/src/us_swing/market/store.py` | Changed: table `pick_results`, `PickResultRow`, `PICK_STATUSES`, `replace_pick_results()` |
| MD-MKT-009.005.M03 | `us_swing/src/us_swing/core/desk_results.py` | New: append-only `pick_trades`, `record_pick_trade()`, `results_view()`, `results_lines()`, `group_cells()` |
| MD-MKT-009.005.M04 | `us_swing/src/us_swing/gui/app_service.py` | Changed: `_record_desk_trade()` called on CycleClosed for the AI Desk strategy |
| MD-MKT-009.007.M05 | `us_swing/src/us_swing/desk/weekly_report.py` | Changed: Pick results section |
| MD-MKT-009.001.M06 | `us_swing/src/us_swing/core/desk_steps.py` | Changed: `PickResultsStep` after `NewsStep` |
| MD-GUI-034.037.M25 | `us_swing/src/us_swing/gui/ai_desk_results.py`, `gui/ai_desk.py` | New live section "Results" after "Reports" |
| — | `us_swing/tests/gui/test_ai_desk.py` | Changed: 12 sections; Results is real data with no sample tag (intended) |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-MKT-009.001 | "Pick results" desk step works out a paper result for every lead pick from daily candles. | Implemented |
| SRD-MKT-009.002 | Entered on the first day the trigger is reached within 5 trading days; else no fill. | Implemented |
| SRD-MKT-009.003 | Ends at stop, target or the 10th day's close; stop wins ties; open until then. | Implemented |
| SRD-MKT-009.004 | `pick_results` keeps one row per pick; replaced on each run. | Implemented |
| SRD-MKT-009.005 | A closed AI Desk trade adds one append-only `pick_trades` row against its pick. | Implemented |
| SRD-MKT-009.006 | A shared results view gives totals and breakdowns by decision, setup grade and news tone. | Implemented |
| SRD-MKT-009.007 | The weekly report has a pick results section for the week's picks. | Implemented |
| SRD-MKT-009.008 | `[Results]` log line with picks worked out and still open. | Implemented |
| SRD-GUI-034.037 | AI Desk live Results section with totals and breakdowns. | Implemented |
| SRD-GUI-034.038 | Pick table, newest first; real P&L blank when not traded. | Implemented |

---

## Design Decisions

- User answers (2026-11-06): real plus paper results; trigger within 5 days, then stop, 2R target or 10 days; credit to the lead and inputs (setup grade, news tone); show in AI Desk Results and the weekly report.
- Entry is the trigger and exits are the stop or target price. Daily bars have no open, so gaps are not modelled.
- When stop and target are both reached on one day, it counts as a stop (cautious).
- Hit rate is target exits ÷ finished picks. A pick counts as a fill only once it has an entry day.
- The step runs after News, not straight after Ideas: an existing test pins News right after Ideas.
- `results_view()` takes `now` so it can mark undecided picks as expired. The DD names it without `now`.
- Review: both reviewers approved. A trade with no exit price now saves an empty R. Points left as is: GUI-thread reads (same as the other live sections), narrow-window table width, and `LIKE` wildcards in tickers.

---

## Test Results

- New tests: 14 (`tests/market/test_pick_results.py`), 9 (`tests/market/test_desk_results.py`), 5 (`tests/gui/test_ai_desk_results.py`); all Pass. Coverage 96–100% on the three new modules.
- Real check on a copy of the desk: 2 lead picks (2026-11-04) are both entered on 2026-11-05 and still open.
- Full suite: 2439 passed, 12 old failures (T112), 2 skipped. No new failure.

---

## Open

- T130: user check after the next evening run. Restart the desk first so the new step runs.
