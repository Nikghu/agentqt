# Revision Note — RN-EXE-1.18.0-20260604

**Tool:** EXE
**Version:** 1.18.0
**Date:** 2026-06-04
**Author:** Claude Opus 4.8 under user direction
**Phase:** FO-EXE-016 — Retire `positions` table; OrderIngestion-driven monitoring lifecycle

---

## Summary

Retires the legacy `positions` table and makes `trade_cycles` the single open-position
surface, while preserving the `monitoring_session` lifecycle (`MONITORING → ENTERED →
EXITED`) by driving its transitions from the live `OrderIngestion` fill path instead of
the dead, unwired `MonitoringCommand.on_fill` hook.

This supersedes `cleanup.md` Steps 7B–8. Investigation during that cleanup showed `on_fill`
is the **designed** Lifecycle hook in `Final_Execution.md` §2.5–2.6 — not dead legacy — so
the work was re-scoped from a deletion into this feature (FO-EXE-016, all SRDs Approved by
the user before implementation).

## Design

- `MONITORING` is still created by the screener (`on_screener_results`) — unchanged.
- `ENTERED` / `EXITED` now flip from `OrderIngestion`: a completed entry fill calls
  `mark_entered`, a closing exit fill calls `mark_exited`. Both are idempotent and
  optional (no-op when the lifecycle service is unavailable).
- Open-position reads (`open_system_position_symbols`, used by screener carryover /
  invariant) now query non-terminal `trade_cycles` by table name — no `positions` read,
  no execution-schema import inside `core/`.
- The `positions` table, its `DatabaseManager` methods, and its migration entries are
  dropped (last, in an isolated commit).

## Code Changes

| File | Change | MD |
|---|---|---|
| `core/monitoring_session/_service.py` | Replace the dead `on_fill` with thin idempotent `mark_entered` / `mark_exited` ledger flips; drop the orphaned `has_open_system_position` query + `_is_complete_fill` helper. | MD-EXE-016.001.M01 |
| `execution/order_ingestion.py` | Optional `LifecycleSink`; on a `FILLED` event, entry → `mark_entered`, closing exit → `mark_exited`. | MD-EXE-016.001.M02 |
| `gui/app_service.py` | Construct `OrderIngestion(..., lifecycle=self._lifecycle_command)`. | MD-EXE-016.001.M03 |
| `core/monitoring_session/_repository.py` | `open_system_position_symbols` reads non-terminal `trade_cycles`; add `fetch_entered_row`; remove `upsert_position_with_anchor` / `has_open_system_position` / `position_anchor` / `insert_trade_with_anchor` and the `positions` import. | MD-EXE-016.003.M04 |
| `core/monitoring_session/_protocols.py` | `MonitoringCommand` gains `mark_entered` / `mark_exited`, drops `on_fill`; `MonitoringQuery` drops `has_open_system_position`. | — |
| `db/schema.py` | Remove the `positions` `sa.Table`; drop its `_LIFECYCLE_COLUMN_*` entries; add a one-time idempotent `DROP TABLE IF EXISTS positions` to `migrate_lifecycle_columns`. | MD-EXE-016.006.M05 |
| `db/manager.py` | Delete `upsert_position` / `delete_position` / `fetch_open_positions` and the `positions` + `PositionRecord` imports. | MD-EXE-016.006.M06 |

`PositionRecord` / `OpenPosition` (data models) are **kept** — the GUI still uses them
for the live IBKR portfolio view; only the DB table is retired.

## Acceptance — Status

| Behaviour (FO-EXE-016 AC) | Status | Evidence |
|---|---|---|
| Entry fill via ingestion → ledger `ENTERED` | ✅ | `test_mark_entered_flips_monitoring_to_entered`; integration `_enter` helper |
| Exit fill → ledger `EXITED` | ✅ | `test_mark_exited_flips_entered_to_exited` |
| Carryover reads `trade_cycles`, never `positions` | ✅ | `test_open_system_position_symbols_returns_open_cycle_symbols` |
| Zero `positions`-table references outside migration | ✅ | grep-verified |
| Dropping the table keeps app importable; suite at baseline | ✅ | full suite 32 pre-existing failures, unchanged |
| Lifecycle methods (`transition_to_entered/exited`) retained | ✅ | exercised by the seam |

## Tests

| Check | Result |
|---|---|
| `tests/core/monitoring_session` | Pass (53) |
| `tests/integration` (lifecycle e2e) | Pass / 2 skipped |
| Full suite | 480 passed, 32 failed (pre-existing baseline), 1 collection error (pre-existing) |
| `ruff` | Clean on all changed files |
| `mypy --strict` | No new errors in changed files (project-wide run surfaces only pre-existing errors) |

Obsolete `on_fill`-driven tests were removed; carryover / invariant / reconcile tests now
set up state via `mark_entered` + an open `trade_cycle`. New seam tests added.

## Deferred (DoD debt)

- **UTCD** for FO-EXE-016 was skipped at user direction (same pattern as FO-EXE-015).
  The implemented behaviour is covered by the migrated/added pytest cases above, but the
  formal `UTCD.md` rows are owed.
- **Order-state-gated lifecycle** (partial-vs-filled) now lives in `OrderIngestion`; its
  dedicated ingestion-layer tests are part of the UTCD backfill.

## Migration Notes

`migrate_lifecycle_columns` issues `DROP TABLE IF EXISTS positions` once on app start —
idempotent and safe on existing databases. `trades` / `trade_cycles` audit rows are
retained. No data is migrated out of `positions` (it was already inert — nothing wrote
system positions to it).

---

**Commits:** branch `feature/exe-016-retire-positions` — `8e84a094` (seam + repoint),
`430d3e41` (drop table); docs `51f626e2`, `ea4af628`.
