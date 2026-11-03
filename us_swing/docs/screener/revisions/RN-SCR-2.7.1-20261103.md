# Revision Note — RN-SCR-2.7.1-20261103

**Tool:** SCR
**Version:** 2.7.1
**Date:** 2026-11-03
**Type:** bugfix
**Author:** Claude Opus 5.5 under user direction
**Phase:** Screener auto-run only on up-to-date candles (ISS-SCR-0003)

---

## Summary

The 09:00 ET auto-run trusted a candle status cached at start-up, so an app left open for days
could screen old candles. Now, in 09:00–09:30 ET, presets whose newest result (auto or manual)
used the last trading day's candles are left alone; the rest run only after a fresh candle check
says the candles are current. Candles behind means no run and one warning per trading day.

## Changes

| File | Change |
|---|---|
| `gui/screener_panel.py` | `_maybe_auto_run` rewritten; new `_presets_needing_run`, `_latest_candle_date`, `_request_db_check`, `_candles_current`, `_warn_candles_behind`, `_in_auto_run_window`; run worker passes `candle_date` |
| `gui/app_service.py` | Public `last_trading_day()` and `last_candle_date()` |
| `screener/storage.py` | `ScreenerRunResult.candle_date` (optional; old files load as `None`) |
| `screener/executor.py` | `run_preset(candle_date=...)` saved with the result |
| `tests/gui/test_screener_autorun.py` | **New** — UT-SCR-004.007.M16.T01–T06 |
| `tests/screener/test_storage.py`, `test_executor.py` | UT-SCR-004.009.M13.T01–T02, UT-SCR-004.009.M10.T01 |

## Requirements

SRD-SCR-004.007 (reworded), SRD-SCR-004.009 (new) — approved by user 2026-11-03, Implemented.

## Notes

- Check stays at 09:00 ET (user choice); retries every minute until 09:30, so a candle update at 09:10 still runs.
- Fresh candle check asked at most once per 50 s.

## Verification

- 10 new UT pass; `pytest tests/screener tests/gui`: 836 passed. Pre-existing on main: 2 `test_preset.py` fails, `test_llm_claude_screener.py` import error, 22 `test_chart_workspace.py` order errors
- `ruff` / `mypy`: same counts as main (31 / 43, pre-existing)
- Real-app check in 09:00–09:30 ET pending (TODO T88)
