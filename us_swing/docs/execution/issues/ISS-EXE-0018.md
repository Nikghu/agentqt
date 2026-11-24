# ISS-EXE-0018 — Trade stuck in CLOSING after TWS reused an order number

**Date:** 2026-11-24
**Tool:** EXE
**Status:** Fixed (code + HRL data repair), app check pending (TODO T244)

## Symptom

The "Chart plan - HRL" trade (5 shares, opened 2026-11-20) stayed in CLOSING in Active Trades. TWS showed the 5 shares were sold.

## Root cause

At 03:20 New York time on 2026-11-24 the hard stop sent SELL 5 HRL. TWS gave it order number 95, but number 95 already belonged to the PRU sell of 2026-11-23. The `trades` row is keyed on that number and saved with "insert or ignore", so the HRL sell was never saved. The same clash overwrote the SW sell row on 2026-11-20 (TODO T221).

The app then restarted at 04:15. The sell filled at the open (5 @ $23.10, 09:30:17). The new session only listened to orders it had placed itself, so the fill never reached the trade.

## Fix

- Each IBKR order gets an app order number that never repeats, sent to TWS as the order reference (SRD-EXE-015.010). permId was not used because TWS gives it only after the order is sent.
- At connect and while connected, a fill with an app reference from an earlier session updates its saved order row and closes its open trade (SRD-EXE-015.011).
- HRL data repaired by hand from the TWS fill: trade CLOSED at $23.10, exit reason hard_sl, sell row added.

## Not covered

- Orders sent before this fix carry no reference, so they cannot be caught up.
- A caught-up exit is saved with reason "manual" (its signal is gone after a restart).
- The stop fired on a pre-market price ($21.41) far below the real price (TODO T245).

## Tests

UT-EXE-015.010.M01.T01–T02, UT-EXE-015.011.M01.T01–T02, UT-EXE-015.011.M02.T01–T04.
