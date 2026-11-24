# Revision Note — RN-EXE-1.43.0-20261124

**Version:** 1.43.0
**Date:** 2026-11-24
**Tool:** EXE
**Artifact:** FO-EXE-015 / SRD-EXE-015.010, SRD-EXE-015.011
**Type:** Bugfix (ISS-EXE-0018)

---

## Summary

The "Chart plan - HRL" trade stayed in CLOSING. TWS gave its sell order number 95, which an older PRU sell already used, so the sell was never saved. The app also restarted before the sell filled at the open, so the fill never reached the trade. Each IBKR order now gets an app order number that never repeats, sent as the order reference. Fills of app orders from an earlier session are caught up at connect and while connected.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-EXE-015.010.M01 | `us_swing/src/us_swing/broker/ibkr.py` | Gateway makes a rising millisecond key per order, sets it as `orderRef`, maps TWS order id → key for status, errors and cancel |
| MD-EXE-015.011.M01 | `us_swing/src/us_swing/broker/ibkr.py` | `start_catch_up` hooks `execDetailsEvent` and `connectedEvent`, scans `ib.fills()`; `IBKRBroker.on_event` starts it |
| MD-EXE-015.011.M02 | `us_swing/src/us_swing/execution/order_ingestion.py` | `_recover` applies a fill with no live context to its saved row and closes the open cycle |
| MD-EXE-015.011.M02 | `us_swing/src/us_swing/db/manager.py` | `trade_by_id` added; shared `_trade_record` row reader |
| MD-EXE-015.011.M02 | `us_swing/src/us_swing/gui/app_service.py` | Passes the cycle query to `OrderIngestion` |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-EXE-015.010 | IBKR order numbers never repeat across sessions | Implemented |
| SRD-EXE-015.011 | Fills from an earlier session update the order row and close the trade | Implemented |

---

## Design Decisions

- An app-made key sent as `orderRef` instead of permId: TWS assigns permId only after the order is sent, so it is not known when the `trades` row is written.
- A caught-up fill does not go to the strategy engine; its in-flight state from the earlier session is gone, and closing the cycle frees the stock.
- A caught-up exit is saved with reason "manual" and the catch-up time, since the original signal is gone.

---

## Data Repair

Cycle 46 (Chart plan - HRL) closed by hand from the TWS fill: 5 @ $23.10 at 09:30:17 New York, exit reason hard_sl; the missing sell row was added under TWS permId 2097494704. Backup: `~/.usswing/candles_backup_20261124_before_hrl_repair.db`.

---

## Issues Resolved

| Issue | Summary |
|---|---|
| ISS-EXE-0018 | Trade stuck in CLOSING after TWS reused an order number |

---

## Tests

UT-EXE-015.010.M01.T01–T02, UT-EXE-015.011.M01.T01–T02 (`tests/broker/test_ibkr_order_key.py`); UT-EXE-015.011.M02.T01–T04 (`tests/execution/test_order_ingestion.py`). Execution, broker, infrastructure and integration suites: 535 passed; app-service GUI suite: 129 passed.
