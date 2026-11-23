# ISS-EXE-0016 — Strategy sold stocks on old prices right after startup

**Date:** 2026-11-23
**Tool:** EXE
**Status:** Fixed (code), app check pending

## Symptom

On 2026-11-23 the app was restarted at 09:37 ET after an IBKR disconnect. Within 25 seconds it sold PRU 7 shares (order 95, 09:37:51) and APP 2 shares (order 96, 09:38:07), both from strategy WTrend_DTrigger. Both cycles were saved with exit reason "manual".

## Root cause

The strategy engine checks rules every second from the moment it starts. Today's bars were not loaded yet (live bars started at 09:38:19), so the latest bars in the database were Friday 2026-11-20. On Friday's numbers the exit rule was true for both stocks: PRU weekly close 117.73 < 10-week EMA 118.05, and APP daily close 348.29 < 10-day swing low 348.69. At today's prices (PRU about 118.8, APP about 375) the rule was most likely false. The order prices (117.73, 348.46) are Friday's last prices.

## Fix

The engine checks entry and exit rules for a stock only when its latest 3m bar is from today's New York date (SRD-EXE-011.028). This applies to the per-second check and to the new-bar check. Rule checks start again once today's first bar is saved, so at the open rules (exits too) wait about 3 minutes until the 09:33 bar. The app logs [Strategy] Waiting for today's prices for <stock> before checking rules once per stock per day.

Not changed: the exit reason still shows "manual" for rule exits (separate fix, not requested).

## Tests

UT-EXE-011.001.M01.T09.