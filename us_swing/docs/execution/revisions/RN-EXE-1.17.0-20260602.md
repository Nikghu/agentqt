# Revision Note — RN-EXE-1.17.0-20260602

**Tool:** EXE
**Version:** 1.17.0
**Date:** 2026-06-02
**Author:** Claude Opus 4.8 under user direction
**Phase:** Trade-cycle service hardening — SELL-side order-state gate, CLOSED-today query, unique paper order ids

---

## Summary

Service-layer changes that back the Session 58 Active Trades lifecycle work (the GUI
wiring is in RN-GUI-1.3.0-20260602). All changes are enhancements/fixes against
already-Approved requirements — **no new SRDs were introduced**.

- **SellOrderState exit gate (FO-EXE-014).** `TradeCycleService.on_exit_fill` and
  `close_cycle_by_id` gained an `order_state: SellOrderState` argument (default
  `FILLED`), making the exit path symmetric with the `.007` BuyOrderState entry gate.
  A `PARTIAL_FILLED` sell holds the cycle in `CLOSING` (stamps `exit_order_id`, no
  finalize); a `FILLED` sell finalizes `CLOSING → CLOSED`. A later `FILLED` carrying
  the same `exit_order_id` is recognised (cycle already `CLOSING`) and completes it,
  mirroring how the entry gate completes `OPENING → OPEN`.
- **CLOSED-today query (FO-EXE-012).** New `TradeCycleRepository.closed_between(start,
  end)` / `TradeCycleService.closed_between` returning `CLOSED` cycles whose
  `closed_at` falls in a UTC `[start, end)` window. The caller passes a market-day
  window; this lets the Active Trades panel keep same-day closed trades visible.
- **Unique paper order ids (FO-EXE-011 / PaperBroker).** `PaperBroker._next_order_id`
  is now seeded from epoch-milliseconds instead of a fixed `10001`. The fixed base
  reset to the same value each app start, so order ids collided with prior sessions'
  rows and the unique `entry_order_id` / `exit_order_id` idempotency guard
  (`find_by_exit_order`) wrongly matched an **older** cycle — silently skipping a
  manual close and stranding the row in `CLOSING`.

## Root Cause (stranded CLOSING)

On restart the in-memory `PaperBroker` counter reset to `10001`. A manual close
produced a SELL with `order_id=10001`, which already existed as another (earlier)
cycle's `entry/exit_order_id`. `close_cycle_by_id`'s `find_by_exit_order("10001")`
returned that stale cycle and short-circuited (`return existing`), so the real cycle
never moved `OPEN → CLOSING → CLOSED`. Confirmed against the live DB (USB cycle 1 had
`entry_order_id == exit_order_id == 10001`).

## Code Changes

| File | Change |
|---|---|
| `execution/trade_cycle/_service.py` | `on_exit_fill` / `close_cycle_by_id` gain `order_state` (default `FILLED`); `_close_cycle` gates finalize on `FILLED`, holds `CLOSING` on `PARTIAL_FILLED` (stamps `exit_order_id` via `update_live`); same-`exit_order_id` FILLED after a partial completes the close. Added `closed_between`. |
| `execution/trade_cycle/_repository.py` | New `closed_between(start_iso, end_iso)` — `state == CLOSED AND closed_at ∈ [start, end)`, ordered by `cycle_id`. |
| `execution/trade_cycle/_protocols.py` | `TradeCycleQuery.closed_between` added; `TradeCycleCommand.on_exit_fill` gains `order_state` (default `FILLED`). |
| `execution/paper_broker.py` | Seed `_next_order_id = int(time.time() * 1000)` so ids stay unique across restarts. |

## Acceptance — Status

| Behaviour | Status | Evidence |
|---|---|---|
| FILLED sell finalizes CLOSED | ✅ | `UT-EXE-014.007.M02.T01` |
| PARTIAL sell holds CLOSING (no `CycleClosed`) | ✅ | `UT-EXE-014.007.M02.T02` |
| PARTIAL → FILLED advances CLOSING → CLOSED | ✅ | `UT-EXE-014.007.M02.T03` |
| `closed_between` returns only today's CLOSED | ✅ | exercised via GUI refresh path (RN-GUI-1.3.0) |
| paper order ids unique across restart | ✅ | seed = epoch-ms (verified `> 10001`) |

## Tests

| Check | Result |
|---|---|
| +3 UTCD `UT-EXE-014.007.M02.T01–T03` | Pass |
| `tests/execution/test_trade_cycle_service.py` (full) | Pass (21) |
| `ruff` | Clean on `_service.py`, `_repository.py`, `_protocols.py`, `paper_broker.py` |
| `mypy --strict` | Clean on the changed trade_cycle modules (project-wide run surfaces only pre-existing errors in untouched modules) |

## Deferred

- **Partial-quantity accounting (TODO T8).** The gate holds the intermediate state but
  does not split quantity (e.g. sell 40 of 100 → 60-share residual). Same limitation
  as the entry gate. Tracked as TODO T8 → FO-EXE-012 follow-up.
- **Revision-note coupling:** the live tick→`on_tick` feed and `ExitTrigger`→SELL
  submit wiring live in `app_service.py` and are documented in RN-GUI-1.3.0-20260602.

## Migration Notes

No schema or data migration. `order_state` arguments are additive with `FILLED`
defaults; `closed_between` is read-only. Existing paper rows with legacy `10001`-style
ids are untouched and remain consistent.

---

**Commits:** branch `feat/active-trades-lifecycle-2026-06-02`, commit `eb462d95`, PR #28.
