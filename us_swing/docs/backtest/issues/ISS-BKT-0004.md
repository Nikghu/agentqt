# ISS-BKT-0004 — App freezes during a full S&P 500 backtest (Step 3 memory)

**Date:** 2026-11-27
**Tool:** BKT (seen in the GUI as a frozen app)
**Status:** Fixed (code), app check pending (TODO T272)

## Symptom

A 2021–2026 S&P 500 backtest with Leading sectors on ran for 13 minutes in Step 3 with no progress line. USSwing.exe used 6.9 GB and the PC was at 97% memory, so Windows paged to disk and the app and the PC hung.

## Root cause

Step 3 keeps every picked stock's 3m bars in memory. Each `_Bars` also held `index`, a Python dict from bar close time to row number for the whole period: about 16 MB of a 25 MB total per stock for 2021–2026. With about 450 stocks that is about 11 GB on a 16 GB PC. Runs got twice as long on 2026-11-27 when the start-date fix (SRD-BKT-002.091) let 2021 plans really start in 2021. Leading sectors and the Added-date filter were not the cause.

## Fix (no SRD change, behaviour unchanged)

- `_Bars.index` is removed. `_Sim.run_day` builds a time → row map only for the day's bars of the stocks it looks at, from the day ranges it already computes.
- Real data (IT sector 2021–2026, Leading sectors on): Step 3 memory 2,459 MB → 857 MB, time 182 s → 139 s; same 34 trades and net P&L $1,649.61. Two trades closing at the same moment can be listed in a different order; this already varied between runs before (set order).

## Advice

Do not run a big backtest while the Backtest Data download is running.
