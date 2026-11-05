# ISS-BKT-0002 — 3m candles start months after the start date and Download missing never fills the gap

**Tool:** BKT · **Severity:** High · **Status:** Fixed · **Date:** 2026-11-04
**Affected:** MD-BKT-001.004.M02, MD-BKT-001.006.M04, MD-GUI-030.008.M06

## Expected
With start date 01-01-2024, every stock has 3m candles from the first trading day, and Download missing asks for any gap.

## Actual
Daily starts 2024-01-02, but 3m starts 2024-04-04/05 (286 stocks) or 2024-07-05 (199 stocks). The Universe BT From shows these dates with a green tick, and Download missing plans no 3m request for the gap.

## Root cause
When a 3m request came back empty, the downloader saved the request end as the stock's floor (503 stocks). The planner starts at the floor, so the older range was never asked again, and the Universe status did not compare the 3m first date with the start date.

## Fix
- A floor is saved only from daily data, for a stock listed after the start date. An empty 3m answer saves nothing, so the next Download missing asks again (SRD-BKT-001.017).
- `state.json` stores floors under a new key `listed`; the old `floors` key is not read, so the old 3m floors are dropped.
- Universe status `late` with an amber BT From when 3m starts more than 7 days after the start date (SRD-GUI-030.011).
- Tests UT-BKT-001.006.M04.T03 (changed), UT-BKT-001.017.M02.T01, UT-BKT-001.017.M04.T01, UT-GUI-030.011.M02.T01.

Real store dry run: the plan has 1,277 3m requests for 503 stocks (before: 0 for the gap).
