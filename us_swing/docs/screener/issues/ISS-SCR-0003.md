# ISS-SCR-0003 — Daily Auto-Run Trusts an Old Candle Status

**Date:** 2026-11-03
**Reported by:** User
**Severity:** High
**Status:** Resolved

## Summary

When the app stays open for days, the 09:00 ET screener auto-run can start on candles that are one or more trading days old.

## Root Cause

| Point | Detail |
|---|---|
| Candle status is checked only at start-up, after a candle download, and after a candle reset | No later re-check, so the screener keeps an old "current" status in memory |
| `_maybe_auto_run` trusted that cached status | Days later it still read "current" and started the run |
| "Already ran" looked only for a scheduled result dated today | A manual run on the latest candles did not count; a result could not say which candles it used |

**SRD root cause:** SRD-SCR-004.007 did not require fresh candles. Reworded (Draft) and SRD-SCR-004.009 added.

## Fix

1. `screener_panel.py::_maybe_auto_run` — in 09:00–09:30 ET: skip presets whose newest result (auto or manual) used the last trading day's candles; for the rest, ask for a fresh candle check and run only when it says current. Candles behind → no run and one `[Screener]` warning per trading day.
2. `storage.py::ScreenerRunResult.candle_date` — new optional field; old files load as `None`.
3. `executor.py::run_preset(candle_date=...)` — saved with the result; the run worker passes the candle DB's last daily candle date.
4. `app_service.py` — public `last_trading_day()` and `last_candle_date()`.

**Files:**
- `us_swing/src/us_swing/gui/screener_panel.py`
- `us_swing/src/us_swing/gui/app_service.py`
- `us_swing/src/us_swing/screener/storage.py`
- `us_swing/src/us_swing/screener/executor.py`
- `us_swing/tests/gui/test_screener_autorun.py` (new, T01–T06)
- `us_swing/tests/screener/test_storage.py`, `us_swing/tests/screener/test_executor.py`

## Related

- SRD-SCR-004.007 (auto-run rule), SRD-SCR-004.009 (`candle_date`)
- SRD-GUI-006.020 (how "candles current" is measured)
