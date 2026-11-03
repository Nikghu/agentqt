# Issue Report — ISS-GUI-0014

**Tool:** GUI (Settings → Candle data; daily candle download)
**Severity:** High (daily candles stop updating; screener and charts use old data)
**Status:** Resolved
**Date Opened:** 2026-11-03
**Date Resolved:** 2026-11-03
**Reporter:** User (screenshots: Candle data "Up to date", Update now off, 1 failed KVUE; Universe shows most stocks at 2026-10-30)
**Resolution:** RN-GUI-1.56.2-20261103
**Related:** SRD-GUI-006.011, SRD-GUI-006.013, SRD-GUI-006.016

---

## Symptom

Candle data said "Up to date · 503 stocks" with Data to 2026-11-02, and Update now was
disabled. The real database had only 30 of 503 stocks at 2026-11-02; 473 stopped at
2026-10-30. Retry Failed only retried KVUE, which failed again.

## Root Cause

1. The status check and the Update now start date both used the newest candle in the whole
   `price_1d` table. One update had stopped after about 30 stocks (name order), so one
   current stock was enough to mark the database CURRENT. Update now was off, and a delta run
   would also say "already up to date".
2. Retry Failed runs the same download worker in fix mode. It overwrote the unfinished
   update's resume checkpoint and then deleted it, so the update could not resume.
3. KVUE: IBKR returns Error 200 "No security definition"; last candle 2026-10-29. It is most
   likely no longer listed, so it fails on every run.

**SRD root cause: scope gap** — no SRD said which stock's date decides "up to date"
(SRD-GUI-006.011) or that Retry Failed must keep the checkpoint (SRD-GUI-006.013/.016).
New SRD-GUI-006.020 and .021, approved by user 2026-11-03.

## Fix

- `_oldest_last_candle_date()` returns the oldest last daily candle among the index stocks.
  The status worker and `_last_known_candle_date()` use it. Stocks that left the index and
  stocks in the failed list are left out, so KVUE cannot hold the date back.
- The fix-mode download no longer saves or deletes the checkpoint.
- One-off data repair (before the code fix): the 30 rows dated 2026-11-02 were deleted so the
  app shows "1 day behind"; backup `~/.usswing/candles_backup_20261103_before_stuck_update_fix.db`.

## Verification

UT-GUI-006.001.M01.T20–T23 Pass; candle and settings GUI tests 38 passed.
