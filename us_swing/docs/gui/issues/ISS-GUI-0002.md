# Issue Report — ISS-GUI-0002

**Tool:** GUI (Dashboard → Trade History; GUI log panel)
**Severity:** Medium (display only — orders, cycles and P&L are correct, but every short trade is shown and logged with the opposite side)
**Status:** Resolved
**Date Opened:** 2026-10-16
**Date Resolved:** 2026-10-16
**Reporter:** User (screenshot of Trade History, plus log line `[INFO ] [Orders] KVUE Buy fill confirmed: 105 share(s) at 18.87`)
**Resolution:** RN-GUI-1.5.1-20261016
**Related:** FO-EXE-018 (Short Trade Direction, RN-EXE-1.33.0-20260917)

---

## Symptom

The first short taken by the tool — `ST_AUTO` sold 105 KVUE at $18.87 on 2026-10-16 (paper) —
appeared in Trade History as **BUY**, and the log panel said `KVUE Buy fill confirmed`.

The database was right: `trades.side = SELL`, `trade_cycles.direction = SHORT`.

## Root Cause

`AppService._rehydrate_positions_from_cycles()` rebuilds the Trade History list from
`trade_cycles` after every order event and on boot. It wrote the sides as literals:

| Line (before fix) | Row | Hardcoded |
|---|---|---|
| `gui/app_service.py:2331` | entry | `side = "BUY"` |
| `gui/app_service.py:2349` | exit | `side = "SELL"` |

Correct while every trade was long. FO-EXE-018 moved the order path onto
`execution/direction.py::order_side()` but missed this display path. `_on_order_event_gui`
then reads `trade.side` from the same list to build the fill message, so the log inherited the
wrong side.

**SRD root cause: code diverged — SRD-EXE-018.003** ("one shared helper maps direction and
entry/exit to the order side … no other module derives it"). No SRD change needed.

## Fix

| File | Change |
|---|---|
| `gui/app_service.py` | Entry and exit rows take their side from `order_side(snap.direction, is_entry)` |

Rows from before FO-EXE-018 carry `direction = "LONG"` (column default), so they still show
BUY / SELL.

## Verification

`tests/gui/test_app_service_mode_threading.py` — 3 new cases (UT-GUI-002.005.M01.T01–T03):
closed short shows SELL entry + BUY cover; closed long unchanged; short entry fill log reads
`KVUE Sell fill confirmed`. T01 and T03 failed before the fix — T03 reproduced the user's exact
log line.

- `tests/gui/` + `tests/execution/` + `tests/broker/`: **485 passed**
- `ruff` (19) and `mypy --strict` (37) on the touched files: identical to the HEAD baseline
- A `cannot schedule new futures after interpreter shutdown` trace at test-process exit was
  confirmed present at HEAD and is unrelated

## Affected Artifacts

| Artifact | Change | Status |
|---|---|---|
| `gui/app_service.py` | Side derived from direction | Done |
| `tests/gui/test_app_service_mode_threading.py` | 3 regression cases | Done |
| UTCD (GUI) | UT-GUI-002.005.M01.T01–T03 | Added |
| TRACE (GUI) | Reverse-trace row for the fix | Updated |

## Notes

- SRD-GUI-002.005 (Trade History table) is in `Reopen`, set by the user before this issue. It
  was not edited; the test IDs reference it because it defines the Side column.
- The open KVUE short carries no stop loss (`ST_AUTO` has stop loss off). Unrelated to this
  display fault, but flagged to the user.
