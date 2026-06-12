# Issue Report — ISS-EXE-0006

**Tool:** EXE (Execution)
**Severity:** High (paper mode records $0 exits and a fake ~−100% loss on auto square-off)
**Status:** Resolved
**Date Opened:** 2026-06-12
**Date Resolved:** 2026-06-12
**Reporter:** Claude (found while investigating ISS-EXE-0005 / price-feed concern)
**Resolution:** RN-EXE-1.24.0-20260612

---

## Symptom

In paper mode, a **forced exit** — end-of-day square-off, strategy-stop
square-off, or emergency shutdown — closed the cycle at an **exit price of $0**,
producing a frozen realized P&L of roughly `(0 − entry_price) × qty`, i.e. a fake
total loss of the position value. A normal strategy exit (driven by the exit
condition on a bar close) was unaffected.

## Root Cause

Exit `TradeSignal`s are built at two sites in
`execution/strategy_engine/_router.py`:

- The strategy-exit site (`evaluate`) sets `entry_price=float(bar.close)`.
- `_force_exit` (used by end-time sweep, square-off, and emergency) built the
  signal **without `entry_price`**.

`TradeSignal.entry_price` defaults to `None`. That flows to `BrokerAdapter` as
`OrderRequest.reference_price=None`, and `SimBroker._fill_price` turns a `None`
reference into `0.0` for a MARKET order. So the paper fill price was $0.

Live mode is unaffected: a real MARKET order ignores the reference price and
fills at the live market price.

No SRD covered the fill-reference price of a forced exit — a scope gap.

## Fix

- **EXE (new SRD-EXE-011.022):** `_force_exit` now sets
  `entry_price = _open_cycle_price(strategy_id, symbol)`, a new helper that
  mirrors `_open_cycle_qty` and reads the open cycle's `current_price` (last live
  tick) when it is a positive value, falling back to the always-positive
  `entry_price`. This gives the paper simulator a realistic reference; live
  MARKET orders still ignore it.
- A non-positive `current_price` (e.g. `0.0` from a halted symbol / missing tick)
  is treated as "no usable price" and falls back to `entry_price`, so the $0 fill
  can never recur.

## Affected Artifacts

| Artifact | Change |
|---|---|
| SRD-EXE-011.022 | New (Approved → Implemented) — forced exit carries open-cycle last price |
| MD-EXE-011.001.M04 | Parent SRD list += .021/.022; `_open_cycle_price` helper noted |
| UT-EXE-011.001.M04.T27/T28/T29 | New — carries current_price; falls back on None; falls back on 0.0 (all Pass) |
| `execution/strategy_engine/_router.py` | `_open_cycle_price` helper; `entry_price` set on the `_force_exit` signal; module header SRD list updated |

## Notes / Deviations

- Complements ISS-EXE-0005 (closed-cycle realized P&L quantity). This issue is
  about the closed-cycle exit **price** on forced exits.
- The screenshot that started this investigation showed **non-zero** inflated
  exit prices, so those rows were *not* this $0 path — that out-of-range pricing
  points to a separate live price-feed problem, deferred by the user.
- Found during the "option 4" price-feed investigation; raised as its own issue
  because it is a concrete, testable code defect independent of the feed.
