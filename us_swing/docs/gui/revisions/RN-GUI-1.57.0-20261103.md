# Revision Note — RN-GUI-1.57.0-20261103

**Tool:** GUI
**Version:** 1.57.0
**Date:** 2026-11-03
**Type:** enhancement
**Author:** Claude Opus 5.5 under user direction
**Phase:** Screener chart draws the AI plan from the next candle after the run, with a hit tag

---

## Summary

The Screener detail chart now draws the AI Entry, Stop and Target lines and zones. The zone starts at
the first candle after the run's last completed session (16:00 New York), so on an older run the later
candles show whether the plan was entered and hit its Target or Stop. The plan box shows a tag:
Not entered, Open, Target hit <date> or Stop hit <date>.

## Changes

| File | Change |
|---|---|
| `gui/screener_views.py` | New `plan_start_index()`, `plan_outcome()`, `outcome_text()`; `ListDetailView.load()` takes the run time; `_show_plan()` draws the plan and the tag |
| `gui/chart_panel.py` | `CandleChartPanel.set_plan()` takes an optional start candle time; Charts page unchanged (starts at the last candle) |
| `gui/screener_panel.py` | Keeps the shown run's time and passes it to the List view |
| `tests/gui/test_screener_views.py` | UT-GUI-022.011.M01.T02–T07 |

## Requirements

FO-GUI-022 requirement 8 and acceptance 5 added. SRD-GUI-022.011 reopened by user 2026-11-03, extended, Implemented.

## Rules

- Start: last completed session = run date in New York if run at or after 16:00, else the day before; the zone starts at the first candle after it (Sunday run → Monday; pre-market Monday → same Monday; Tuesday after close → Wednesday). No such candle yet → zone starts at the last candle and no tag.
- Entered: a candle reaches Entry from the side of the last close before the start (gap past Entry counts).
- After entry the first candle reaching Stop or Target decides; both in one candle → Stop.
- Only daily charts and long-shaped AI plans (stop < entry < target); no plan → no lines, no tag.

## Verification

- `pytest tests/gui/test_screener_views.py`: 26 passed
- `pytest tests/gui -k "chart or screener"`: 92 passed; 22 `test_chart_workspace.py` errors pre-existing (same on main, pass alone — TODO T92)
- `ruff` and `mypy --strict` clean on `screener_views.py`
- Rendered with the real chart and saved runs: BBY 26 Oct → Not entered (highest high 100.49 < entry 100.75); ISRG 23 Oct → Open
- Real-app check pending (TODO T91)
