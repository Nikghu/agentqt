# Revision Note — RN-GUI-1.7.1-20261022

**Tool:** GUI
**Version:** 1.7.1
**Date:** 2026-10-22
**Type:** bugfix
**Author:** Claude Opus 5.5 under user direction
**Phase:** Weekly candles built from daily candles (ISS-GUI-0003)

---

## Summary

The user saw that the EVRG weekly chart did not match IBKR TWS: after mid-2026 it had too many
candles. Every stock was affected — about 26,600 extra or cut-short rows in `price_1w` since
ISO week 2026-22. Weekly candles are now built from the stored daily candles, and the existing
weekly table was rebuilt.

## The fault

The candle download asked IBKR for `1 week` bars. IBKR stamps the unfinished week with the
request day, so each daily delta run added another row for the same week. A short delta window
also starts mid-week, so its first weekly bar is cut short, and `INSERT OR REPLACE` let it
overwrite the good full-week row.

SRD root cause: **scope gap** — SRD-GUI-006.011 did not say how a weekly candle is formed. New
**SRD-GUI-006.019** (approved by the user in chat on 2026-10-22).

## The fix

| File | Change |
|---|---|
| `gui/app_service.py` | New `_rebuild_weekly_from_daily(conn, symbol)`: Mon–Fri aggregate of `price_1d` (open first, high max, low min, close last, volume sum), dated on the week's last trading day; replaces the symbol's `price_1w` rows in the same transaction as the daily write |
| `gui/app_service.py` | `_download_all` and `_download_benchmark` no longer request IBKR weekly bars. NO_DATA now means no daily bars |

Built-from-daily weeks matched IBKR's good weekly rows exactly (153 of 155 weeks for EVRG and
AAPL; the two misses were cut-short rows).

## Data repair

`~/.usswing/candles.db` backed up to `candles_backup_20261022_before_weekly_rebuild.db`, then
`price_1w` rebuilt for all 518 symbols: 115,739 → 89,113 rows, no week with more than one row.

## Also in this session

`gui/screener_panel.py` loads the last 600 daily/weekly bars per stock (was 300), so price
patterns with a lookback above 299 bars (52-week High / Breakout, up to 504) can match. No
artifact named the old limit.

## Verification

`tests/gui/test_app_service_weekly_candles.py` — 6 new cases (UT-GUI-006.001.M01.T11–T16), all pass.

- `tests/gui/`: **232 passed**
- `ruff` and `mypy --strict` on `app_service.py`: no new errors; all reported errors are on
  unchanged lines
- pyqt-code-reviewer: no BLOCK. WARN on an existing pattern — the per-symbol `sqlite3`
  connection is not closed if a write raises; left as is

## Follow-ups

- TODO T38: backward fill of older **daily** history; weekly depth now follows daily depth.
- `data/engine.py` `bootstrap_symbol` still requests IBKR weekly bars but has no caller.
