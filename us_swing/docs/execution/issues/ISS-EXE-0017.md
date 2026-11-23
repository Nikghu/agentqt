# ISS-EXE-0017 — Strategy rule exits saved with reason "manual"

**Date:** 2026-11-23
**Tool:** EXE
**Status:** Fixed (code), app check pending (TODO T238)

## Symptom

On 2026-11-23 the WTrend_DTrigger exit rule sold PRU and APP (see ISS-EXE-0016). Both closed trades were saved with exit reason "manual", so they looked like hand-made exits.

## Root cause

The app kept one shared "reason for the next exit" value, starting as "manual". Only exits sent from the app (Dashboard Exit, stop loss, target) wrote to it, and it was never reset. Strategy rule exits did carry their own reason ("strategy"), but the broker adapter read only the shared value. A rule exit after a stop-loss exit could also be saved as "hard_sl".

## Fix

The broker adapter saves the reason from each exit signal itself (SRD-EXE-015.009). The app's own exits put their real reason on the signal. The shared value is removed. An unknown reason is saved as "manual".

Old trades are not changed: PRU (order 95) and APP (order 96) still show "manual".

## Tests

UT-EXE-015.002.M01.T25, UT-EXE-015.002.M01.T26; UT-EXE-014.007.M01.T05 updated.