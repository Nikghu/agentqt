# Revision Note — RN-GUI-1.5.1-20261016

**Tool:** GUI
**Version:** 1.5.1
**Date:** 2026-10-16
**Type:** bugfix
**Author:** Claude Opus 5.5 under user direction
**Phase:** Trade History side for short trades (ISS-GUI-0002)

---

## Summary

The first short the tool ever took — `ST_AUTO` sold 105 KVUE at $18.87 (paper) — showed as
**BUY** in Trade History, and the log said `[Orders] KVUE Buy fill confirmed`. The order, the
cycle and the database were all correct; only the display path was wrong.

## The fault

`AppService._rehydrate_positions_from_cycles()` rebuilds Trade History from `trade_cycles`
after every order event and on boot. It hardcoded `side = "BUY"` for the entry row and
`side = "SELL"` for the exit row. FO-EXE-018 moved the order path onto
`execution/direction.py::order_side()` but missed this function. The fill message in
`_on_order_event_gui` reads its side from the same list, so the log was wrong too.

SRD root cause: code diverged from **SRD-EXE-018.003** (one helper maps direction to order
side; no other module derives it). No SRD changed.

## The fix

| File | Change |
|---|---|
| `gui/app_service.py` | Entry and exit rows use `order_side(snap.direction, is_entry)` |

A short now shows **SELL** on entry and **BUY** on cover; longs are unchanged. Cycles from
before FO-EXE-018 carry `direction = "LONG"` by default and still show BUY / SELL.

## Verification

`tests/gui/test_app_service_mode_threading.py` — 3 new cases (UT-GUI-002.005.M01.T01–T03).
T01 and T03 failed before the fix; T03 reproduced the user's exact log line.

- `tests/gui/` + `tests/execution/` + `tests/broker/`: **485 passed**
- `ruff` 19 and `mypy --strict` 37 on the touched files — identical to the HEAD baseline
- A `cannot schedule new futures after interpreter shutdown` trace at test-process exit is
  present at HEAD and unrelated

## Follow-ups

- SRD-GUI-002.005 (Trade History table) remains in `Reopen`, as the user left it.
