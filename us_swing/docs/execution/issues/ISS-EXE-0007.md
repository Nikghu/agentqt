# Issue Report — ISS-EXE-0007

**Tool:** EXE (Execution)
**Severity:** Critical (an exit closes the wrong open position and records a corrupted realized P&L)
**Status:** Resolved
**Date Opened:** 2026-06-12
**Date Resolved:** 2026-06-12
**Reporter:** User (closing PCG instead exited QCOM at the wrong price)
**Resolution:** RN-EXE-1.26.0-20260612

---

## Symptom

With two positions open at once (QCOM and PCG, both strategy SUPERTREND), the
user clicked **Close** on the **PCG** row. The system instead closed **QCOM** at
PCG's price. A second Close on PCG then closed PCG correctly.

Database evidence (`trade_cycles`):

| cycle | symbol | entry | exit_price | exit_order_id | exit_time | realized_pnl |
|---|---|---|---|---|---|---|
| 25 | QCOM | 202.95 | **16.965** | …503 | 19:43:13 | **−371.97** |
| 26 | PCG  | 16.96  | 16.9627    | …504 | 19:44:16 | +0.04 |

QCOM opened 19:07 (older), PCG opened 19:19. The first PCG-close raised order
`…503`, which closed the **oldest** open cycle (QCOM) at PCG's price.

## Root Cause

`TradeCycleService.on_exit_fill` (`execution/trade_cycle/_service.py`) resolved
the cycle for an incoming exit fill as **"the first open cycle whose
`exit_order_id` is None"** — ignoring symbol and strategy entirely:

```python
target = next(
    (c for c in self._repo.open_cycles() if c.exit_order_id is None),
    None,
)
```

Every exit (manual *and* automatic target/SL/trailing) reaches this method via
`OrderIngestion._close_cycle` keyed only by `exit_order_id`, and the cycle is
never pre-stamped with that id. So with more than one open cycle, an exit always
closed the oldest un-stamped position rather than the one it was raised for. The
exit *price* came from the clicked symbol (PCG) but was applied to the wrong
cycle (QCOM). With a single open position the bug is invisible — which is why it
surfaced only now.

The `close_cycle_by_id(cycle_id, …)` path is correct but is not used by the
broker-fill flow; the `OrderContext` carries `symbol` and `strategy_id` but no
`cycle_id`.

## Fix

- **EXE:** `on_exit_fill` now takes `symbol` and `strategy_id` and resolves the
  target cycle by that pair, which is unique among open cycles (enforced by
  `DuplicateOpenCycleError`). The `exit_order_id is None` guard is retained.
- `OrderIngestion._close_cycle` passes `ctx.symbol` / `ctx.strategy_id` (both
  already on `OrderContext`).
- `TradeCycleCommand` protocol signature updated to match.

## Affected Artifacts

| Artifact | Change |
|---|---|
| SRD-EXE-014.007 | Clarified — exit fill resolves its cycle by (strategy_id, symbol), not the oldest open cycle |
| `execution/trade_cycle/_service.py` | `on_exit_fill` matches by (strategy_id, symbol) |
| `execution/trade_cycle/_protocols.py` | `on_exit_fill` signature += symbol, strategy_id |
| `execution/order_ingestion.py` | `_close_cycle` passes symbol + strategy_id |
| UT-EXE-014.007.M02.T19 | New regression — two open cycles; exit closes the matching symbol, leaves the older one OPEN (Pass) |

## Notes / Deviations

- Data left in place: cycle 25 (QCOM) carries a wrong exit. Reopening it is not
  safe (the paper position is gone and the market has moved), so the historical
  row is left as-is pending the user's decision.
- Same class of defect as the auto-exit path: a target/SL/trailing trigger on one
  of several open cycles could also have hit the wrong position before this fix.
