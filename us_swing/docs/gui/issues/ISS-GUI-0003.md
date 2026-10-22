# Issue Report — ISS-GUI-0003

**Tool:** GUI (Settings → Database candle download; read by the Screener and the chart)
**Severity:** High (wrong weekly candles for every stock since late May 2026 — weekly screener runs and weekly charts used bad data)
**Status:** Resolved
**Date Opened:** 2026-10-22
**Date Resolved:** 2026-10-22
**Reporter:** User (EVRG 1W chart compared with the IBKR TWS weekly chart — time axis stretched after June 2026)
**Resolution:** RN-GUI-1.7.1-20261022
**Related:** SRD-GUI-006.011 (Database tab download), SRD-GUI-006.015 (per-symbol failures)

---

## Symptom

The EVRG weekly chart had too many candles after mid-2026: Jun→Aug took more width than
Jan→Jun. The database showed it for all 518 stocks: ~26,600 extra `price_1w` rows from ISO
week 2026-22 onward. EVRG had 231 weekly rows for 178 real weeks; the week of 2026-08-03 had
four rows (08-04, 08-05, 08-06, 08-07).

## Root Cause

`_CandleDownloadWorker` asked IBKR for `1 week` bars and wrote them with
`INSERT OR REPLACE` keyed on `(symbol, datetime)`. Two IBKR behaviours broke this once
delta downloads started:

| Fault | Effect |
|---|---|
| The in-progress week is stamped with the request day, not the week's end | Each daily delta run added a new row for the same week; old partial rows were never removed |
| A short delta window (min 4 weeks) is not Monday-aligned, so its first weekly bar covers only part of a week | That cut-short bar overwrote the good full-week row — e.g. EVRG 2026-08-14 volume 437,039 = Friday alone |

The benchmark (SPY) download had the same cut-short first-week fault on its `2 Y` window.

**SRD root cause: scope gap** — SRD-GUI-006.011 says the download fills `price_1w` but not
how a weekly candle is formed. New **SRD-GUI-006.019** covers it.

## Fix

| File | Change |
|---|---|
| `gui/app_service.py` | New `_rebuild_weekly_from_daily(conn, symbol)` — replaces the symbol's `price_1w` rows with Mon–Fri aggregates of `price_1d` (open first, high max, low min, close last, volume sum), dated on the week's last trading day |
| `gui/app_service.py` | `_download_all` and `_download_benchmark` no longer request IBKR `1 week` bars; they rebuild weekly per symbol after saving daily. NO_DATA now means no daily bars |

Proof the method is right: weekly bars built from the stored daily bars matched IBKR's good
(pre-week-22) weekly rows exactly — 153 of 155 weeks for both EVRG and AAPL; the two misses
were cut-short rows.

## Data Repair

`~/.usswing/candles.db` backed up to `candles_backup_20261022_before_weekly_rebuild.db`, then
`price_1w` rebuilt for all 518 symbols: 115,739 → 89,113 rows, 0 weeks with more than one row.

## Verification

See RN-GUI-1.7.1-20261022.

## Affected Artifacts

| Artifact | Change | Status |
|---|---|---|
| SRD (GUI) | SRD-GUI-006.019 added | Implemented |
| MD (GUI) | MD-GUI-006.001.M01 change row for `app_service.py` | Added |
| UTCD (GUI) | UT-GUI-006.001.M01.T11–T16 | Pass |
| `gui/app_service.py` | Weekly built from daily | Done |
| `tests/gui/test_app_service_weekly_candles.py` | 6 cases | Done |

## Notes

- Weekly depth now follows daily depth, so TODO T38 only needs a backward fill of daily history.
- `data/engine.py` `HistoricalDataEngine.bootstrap_symbol` also requests IBKR weekly bars but has
  no caller in the app; left unchanged.
