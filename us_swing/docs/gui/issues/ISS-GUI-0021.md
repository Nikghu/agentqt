# Issue Report — ISS-GUI-0021

**Tool:** GUI
**Severity:** Low (extra Telegram message)
**Status:** Resolved (user check pending)
**Date Opened:** 2026-11-17
**Date Resolved:** 2026-11-17
**Resolution:** SRD-GUI-004.014 (approved by user 2026-11-17, Implemented)
**Reporter:** User — "whenever I ran the screener I am receiving messages with approved stock. it should not happen for manual run"

---

## Symptom

Clicking Run now on a screener preset sends the Telegram "screener approved" message, the same as the daily scheduled run.

## Root Cause

| Point | Detail |
|---|---|
| One path for both runs | `screener_panel.py::_on_run_finished()` called `notify_screener_results_updated()` the same way for manual and scheduled runs. |
| Message always on | `app_service.py::_on_screener_results_updated()` sends `ScreenerApprovedEvent` whenever `_notify_screener_approved` is True, which it was for every run. |

## Fix

| File | Change |
|---|---|
| `gui/app_service.py` | `notify_screener_results_updated(send_message=True)` sets the message flag for one refresh; the pick-change refresh uses it too |
| `gui/screener_panel.py` | `_on_run_finished()` sends the message only when the result's run type is `scheduled` |
| `tests/gui/test_manual_picks.py` | UT-GUI-004.001.M01.T26–T27 added; T17 now checks the real method |

The Execution list still refreshes after a manual run; only the message is skipped.

## Also checked — Acc / Dist "Distribution" preset shows 0 matches

Not a bug. On candles up to 2026-11-16, with the user's settings, only PGR passes the Acc / Dist checks, and the screener's first stage (price above $5 and last-day volume of at least 1 million) removes PGR (699K that day). Of the 531 stocks, 522 fail Minimum score 0.60 and 387 fail "Near range high". STT, FANG, T, APA, JPM and PLTR fail only "Near range high". No code change.

## User step

Run a preset with Run now: no Telegram message. The daily auto-run still sends one (T201).
