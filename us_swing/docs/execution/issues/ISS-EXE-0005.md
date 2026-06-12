# Issue Report — ISS-EXE-0005

**Tool:** EXE (Execution)
**Severity:** High (wrong realized P&L value persisted on closed cycles)
**Status:** Resolved
**Date Opened:** 2026-06-12
**Date Resolved:** 2026-06-12
**Reporter:** User (USSwing)
**Resolution:** RN-EXE-1.23.0-20260612

---

## Symptom

In the Active Trades panel, the dollar P&L on closed cycles was wrong for
multi-share positions while the P&L **percentage** stayed correct.

Evidence (paper trading screenshot):

| Symbol | QTY | Entry | Exit | Shown PNL$ | Correct PNL$ |
|---|---|---|---|---|---|
| BDX | 3 | 150.60 | 147.83 | −8.31 | −8.31 ✓ |
| CL | 5 | 89.35 | 322.98 | +233.63 | +1168.15 ✗ |
| MNST | 5 | 91.12 | 403.69 | +312.57 | +1562.85 ✗ |

CL/MNST showed only the **per-share** difference — the dollar figure was
multiplied by 1, not the held quantity of 5. PNL% was correct in every row.

## Root Cause

`TradeCycleService._close_cycle` (`trade_cycle/_service.py`) froze
`realized_pnl_usd = (exit_price − entry_price) × exit_qty`, where `exit_qty`
is the quantity reported by the **sell fill event** (`event.filled_quantity`,
plumbed through `order_ingestion.on_exit_fill`). The formula matched
SRD-EXE-012.007 as written, so the code did **not** diverge — the SRD formula
itself was fragile.

A trade cycle is a one-shot full position: it only reaches `CLOSED` on a
`FILLED` full-position sell. At that point the realized quantity is invariantly
the held `entry_qty`. Trusting `exit_qty` breaks whenever the sell fill's
reported quantity diverges from the held position — e.g. a broker reporting the
final fill incrementally (1 share) rather than cumulatively — under-counting the
realized P&L. PNL% was unaffected because it does not use quantity.

## Fix

- **EXE (SRD-EXE-012.007, corrected):** realized P&L now multiplies by the held
  `snap.entry_qty` instead of the sell fill's reported `exit_qty`. `exit_qty` is
  still persisted to the exit fields for audit. One-line change plus an
  explanatory comment naming the FILLED-gate invariant.
- The live (unrealized) P&L path already used `entry_qty`, so this makes the
  closed value consistent with what was displayed while the trade was open.

## Affected Artifacts

| Artifact | Change |
|---|---|
| SRD-EXE-012.007 | Formula corrected `× exit_qty` → `× entry_qty`; Approved → Implemented |
| UT-EXE-012.002.M02.T18 | New — realized P&L uses held qty when exit_qty diverges (Pass) |
| UT-EXE-012.002.M02.T16, T17 | Documented in UTCD — pre-existing abort tests were missing from the doc (reconciled) |
| `execution/trade_cycle/_service.py` | `_close_cycle` realized P&L multiplier → `snap.entry_qty` |

## Notes / Deviations

- Complements ISS-EXE-0004, which fixed the **pending/display** exit quantity
  (`qty_recommended`). This issue fixes the **persisted realized P&L** value on
  the closed cycle row.
- DD has no explicit realized-P&L formula row (only a state-transition table),
  so no DD cascade was required.
- The absurd exit prices in the screenshot (CL $322.98, MNST $403.69 — far from
  those stocks' real prices) point to a separate live price-feed problem, not
  addressed here.
- Existing closed rows in the database keep their wrong P&L — acceptable as the
  project is in the testing phase (per user); no data backfill performed.
