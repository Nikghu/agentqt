# Issue Report — ISS-EXE-0013

**Tool:** EXE (Execution)
**Severity:** High (flat 15m candles were shown on the chart and fed to strategy 15m indicators for a whole trading day)
**Status:** Resolved
**Date Opened:** 2026-10-27
**Date Resolved:** 2026-10-27
**Reporter:** User (Execution workspace screenshot — DELL 15M chart shows only flat dashes for 26 Oct)
**Resolution:** RN-EXE-1.37.1-20261027

---

## Symptom

On 26 Oct every historical DELL 15m candle was a flat dash (open = high = low = close, volume 0). The 3m chart was fine. Up to 23 Oct the 15m chart was fine.

## Evidence

| Check | Result |
|---|---|
| `price_15m` rows on 26 Oct | 215 of 225 flat with volume 0, across all 9 stocks |
| `price_15m` rows on 23 Oct (IBKR feed) | 2 of 232 flat (same cause, short Yahoo spell) |
| DELL 19:30 UTC flat row | 471.38 = close of the 19:30 1m bar, so it was saved about 1 minute into the window |
| Log 26 Oct 09:30 / 09:54 ET | IBKR timed out, then "9 of 9 stocks lack market data permission — falling back to Yahoo Finance" |
| `live_bar_worker.py` history | Unchanged since 2026-09-04; first full trading day on the Yahoo live path |

## Root Cause

`LiveBarWorker._write_yfinance_direct()` polls Yahoo 15m bars every 60 s and saved every bar, including the one still forming. Just after a window opens, that bar has one price and volume 0. It was written with `INSERT OR IGNORE`, and later polls only write bars after the last saved time, so the flat bar was never corrected. The 3m path builds from 1m bars and already skips the last bucket, so it was not affected.

Both readers (`AppService.get_intraday_candles_for_symbol` for charts and `assemble_execution_bars` for strategies) let a saved `price_15m` row win over the 1m-built candle, so the flat rows hid the correct 1m data.

A second, smaller defect was found in the IBKR path: after the worker (re)starts mid-window, the first candle holds only part of that window and was saved the same way.

## Fix

| File | Change |
|---|---|
| `execution/live_bar_worker.py` | `_write_yfinance_direct()` skips a bar until its window has ended |
| `execution/live_bar_worker.py` | `_first_bar_dt` per symbol; `_on_candle_closed()` drops a window that began before the first 5-second bar; cleared on unsubscribe and session end |

Data cleanup (user approved): `~/.usswing/candles.db` backed up to `candles_backup_20261027_before_flat15m_cleanup.db`, then the 217 flat zero-volume `price_15m` rows were deleted. All 217 slots have 1m data, so charts and strategies now build them from `price_1m`. DELL 26 Oct: 26 candles, 0 flat.

## Verification

`tests/execution/test_live_bar_worker.py` — UT-EXE-007.001.M01.T27–T29, all fail against the pre-fix code and pass after. `tests/execution`: 327 passed; `tests/gui` + `tests/integration`: 510 passed, 2 skipped. `ruff` clean; `mypy --strict` count unchanged (18, all in other files).

## Affected Artifacts

| Artifact | Change | Status |
|---|---|---|
| SRD-EXE-007.010 | New — live tables hold only complete candles (user approved) | Implemented |
| MD-EXE-007.001.M01 | Covers SRD-EXE-007.010 | Updated |
| UTCD (EXE) | UT-EXE-007.001.M01.T27–T29 | Pass |
| TRACE (EXE) | SRD-EXE-007.010 row | Updated |

## Notes

- IBKR reported no market data permission for all 9 stocks on 26 Oct. The user should check the TWS market data subscription; until then the Yahoo path is used.
- Partial first IBKR candles saved before this fix (worker restarts on earlier days) cannot be told apart from full ones and were left in place.
