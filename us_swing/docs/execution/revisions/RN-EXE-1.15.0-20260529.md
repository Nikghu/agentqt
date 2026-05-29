# Revision Note — RN-EXE-1.15.0-20260529

**Tool:** EXE
**Version:** 1.15.0
**Date:** 2026-05-29
**Author:** Claude Opus 4.8 under user direction
**Phase:** Final_Execution.md Phase 4 — LifecycleState internalisation

---

## Summary

Phase 4 (final phase) of the state-enum consolidation makes
`ExecutionEnums.LifecycleState` (added in Phase 0) the single source of truth
for the monitoring-session lifecycle enum and retires the duplicate
`LifecycleState(str, Enum)` that lived in `core/monitoring_session/_enums.py`.
Internal importers reference `ExecutionEnums.LifecycleState` directly; the
package keeps exporting `LifecycleState` from its public `__init__.py` (now
sourced from `ExecutionEnums`) so the `MonitoringSessionRow` DTO contract and
all existing call sites — production and test — are unchanged.

A conflict the plan did not anticipate was resolved: SRD-EXE-009.012 requires
`core/monitoring_session/` to stay Qt-free (so the core layer runs headless),
but `execution/__init__.py` eagerly imported two PyQt6-based QThread workers.
Importing `ExecutionEnums` from core would therefore have dragged PyQt6 into the
headless core layer at runtime — passing the static CI guard but defeating its
intent. The two workers are now lazily loaded via a PEP 562 `__getattr__`,
keeping `import us_swing.execution` Qt-free while preserving the package's
public API.

## Artefacts Touched

| Artefact | Change |
|---|---|
| `docs/execution/SRD.md` | SRD-EXE-009.012 cycled Reopen → Implemented (LifecycleState relocated; requirement text unchanged) |
| `docs/execution/UTCD.md` | Added UT-EXE-009.002.M02.T22 — ENTERED-ledger set equals open system position set across a fill sequence |
| `docs/execution/TRACE.md` v1.10.0 | FO-EXE-009 UTCD range extended to T22; Phase 4 RN linked |

## Code Changes

| File | Change |
|---|---|
| `execution/__init__.py` | `IntradayCandleLoader`, `LiveBarWorker`, `CandleLoadResult`, `SymbolReadiness` moved behind a PEP 562 `__getattr__` (lazy import); `ExecutionEnums` stays eager. `import us_swing.execution` is now Qt-free; package-level access to the workers is unchanged, and a `TYPE_CHECKING` block preserves their static types. |
| `core/monitoring_session/_enums.py` | Deleted the duplicate `LifecycleState(str, Enum)`; `TradeOrigin` and `Side` retained. |
| `core/monitoring_session/_repository.py` | Imports `ExecutionEnums`; module-local alias `_LifecycleState = ExecutionEnums.LifecycleState` keeps the 15 ledger call sites readable and ≤ 99 cols. |
| `core/monitoring_session/_dto.py` | `MonitoringSessionRow.lifecycle_state` typed `ExecutionEnums.LifecycleState`. |
| `core/monitoring_session/__init__.py` | `LifecycleState` re-exported from `ExecutionEnums` (kept in `__all__`); old import path `from us_swing.core.monitoring_session import LifecycleState` still works. |
| `core/monitoring_session/_service.py` | Audited — no change. ENTERED/EXITED transitions are already invoked only through `on_fill()`; SKIPPED/EVICTED are reconciler-driven (Final_Execution.md §2.5). |

## GUI Audit (§5.4.4)

Grep confirms **zero** `gui/` modules import `LifecycleState` — the enum stays
internal and is surfaced in no user-facing panel (Decision Log #4). No GUI change.

## Acceptance Criteria — Status (§5.4.5)

| AC | Status | Evidence |
|---|---|---|
| `LifecycleState.ENTERED` co-occurs with a system BUY fill | ✅ (behavioural) | ENTERED is driven by the first system BUY through `on_fill()`; asserted by `UT-EXE-009.002.M02.T22` (ENTERED set == open-position set). See Deferred for the typed `order_state` parameter. |
| Greps confirm no GUI module imports `LifecycleState` | ✅ | GUI audit above |
| Old import path works (re-export) or is fully removed | ✅ | Re-exported from `ExecutionEnums` via `__init__.py`; old path preserved |

## Tests

| Check | Result |
|---|---|
| `UT-EXE-009.002.M02.T22` (NEW) | Pass — `check_invariant().ok` holds across enter A, enter B, exit A; open positions {A,B} → {B}; A finalised EXITED |
| `tests/core/monitoring_session/` (full) | Pass incl. Qt-free guard T01/T02, except 1 pre-existing date-decay failure |
| `tests/execution/test_enums.py` | Pass |
| Qt-free runtime proof | `import us_swing.core.monitoring_session` leaves PyQt6 out of `sys.modules` |
| `ruff` / `mypy --strict` | Clean on all 5 changed files |

Pre-existing failures unrelated to Phase 4 (also recorded in RN-EXE-1.14.0;
each verified still failing on clean `HEAD`):
- `test_repository.py::test_fetch_history_includes_evicted`,
  `test_lifecycle_e2e.py::test_it_010_002_history_survives_eviction` — the
  `days=7` history cutoff (`now − 7d = 2026-05-22`) excludes the `2026-05-14`
  fixture date; date-relative decay, not a logic regression.
- `test_intraday_candle_loader.py`, `test_live_tick_worker.py` — pre-existing
  mock/environment issues in the IBKR/candle workers.
- 9 `tests/execution/*` collection errors — `talib` native library not
  installed in this environment.

## Deferred (still open after Phase 4)

- **SRD-EXE-014.008** — `on_fill` consuming `(side, order_state)` as a typed
  parameter rather than inferring the transition from `(has_open, side)`.
  `FillEvent` carries no `order_state` field today; adding it is coupled with
  the deferred broker reject/cancel paths (SRD-EXE-014.005/.006) under
  FO-EXE-001 / CircuitBreaker. The lifecycle transition is already fill-driven,
  so the behavioural §5.4.5 acceptance holds; only the explicit typed parameter
  is outstanding.

## Migration Notes

No schema or data migration. Every `LifecycleState` member keeps its exact wire
value, and `StrEnum` is byte-compatible with the former `(str, Enum)`, so
persisted `monitoring_session.lifecycle_state` values are unaffected.

---

**Commits:** managed by the user per project convention (feature branch
`feat/exe-phase4-lifecycle-internalisation`).
