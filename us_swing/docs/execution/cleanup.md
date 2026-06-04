# cleanup — Broker Legacy Removal (Broker_fix.md Phase 6)

**Status:** Planned (not started)
**Tool:** EXE (+ INF db/schema, GUI app_service)
**Tracks:** SRD-EXE-015.006
**Created:** 2026-06-04

---

## 0. Goal

Remove the dead legacy execution path left behind after the broker abstraction
(FO-INF-009 + FO-EXE-015) went live, so future readers aren't confused by two
parallel order/position systems.  The new path — `BrokerAdapter` → `SimBroker`/
`IBKRBroker` → `OrderIngestion` → `trades` + `trade_cycles` — is the only one
that should remain.

**Nothing in this document changes behaviour.** It only deletes code that is
already unwired or made dead by the new pipeline.

---

## 1. Principle — bottom-up, leaf-first

Remove **leaf nodes first** (things nothing still depends on), then move up
toward the **root** (the shared `positions` table that many legacy modules
depend on).  A node becomes a "leaf" — safe to delete — only once everything
that referenced it is already gone.

```
ROOT  ── positions table ───────────────────────────────────────────┐
            ▲ depended on by                                         │ remove
            ├── DatabaseManager.upsert/delete/fetch_open_positions   │  LAST
            ├── health.py (open-position count)                      │
            ├── MonitoringSessionService position writers [unwired]  │
            └── PositionTracker                                      │
                   ▲ used by                                         │
                   └── ExecutionEngine                               │
                                                                     │
   ExecutionRouter [unwired] ── imports ──┬─► ExecutionEngine        │
     (top leaf — nothing imports it)      └─► PaperEngine [unwired]  │
                                                                     │
LEAVES (separate sub-tree) ──────────────────────────────────────── │ remove
   app_service fallback ──► PaperBroker          [Steps 1–3 DONE]    │  FIRST
                        └─► _on_paper_fill ─► _record_paper_entry/_exit
```

**Correction (2026-06-04):** `ExecutionRouter` imports *both* `ExecutionEngine`
and `PaperEngine`, and nothing imports `ExecutionRouter` — so it is the real top
leaf of this sub-tree. It must be deleted **before** `PaperEngine`; the original
diagram showed `PaperEngine` as a standalone leaf and missed that edge.

Read it top-down to understand dependencies; **delete it bottom-up** (leaves →
root).

---

## 2. Per-step recipe (apply to every step)

1. `ruff check` + `mypy --strict` on changed files — clean.
2. `pytest` the affected dirs — failure count must stay at the **baseline (21
   pre-existing failures as of 2026-06-04)**, never increase.
3. If unsure whether a failure is new, stash the step's edits and re-run to
   compare (the technique used in Phase 5).
4. **One commit per step** on branch `refactor/broker-legacy-removal`:
   `refactor(exe): remove <thing>` — small and revertible.
5. A *new* failure means something still references the target — stop and
   re-check the dependency graph before continuing.

---

## 3. Steps (leaf → root)

### Step 1 — Sever app_service from the legacy paper path
- **Change:** drop the `PaperBroker` fallback branch in `app_service` order-submitter
  wiring; require the broker pipeline (log clearly if DB/trade-cycle service is
  unavailable instead of falling back).
- **Effect:** orphans `_on_paper_fill`, `_record_paper_entry`, `_record_paper_exit`
  and the `PaperBroker` import — nothing is deleted yet.
- **Verify:** app_service imports; **GUI paper trade still works (manual check)**.
- **Files:** `gui/app_service.py`.

### Step 2 — Delete the dead app_service paper methods
- **Remove:** `_on_paper_fill`, `_record_paper_entry`, `_record_paper_exit`.
- **Pre-check:** grep confirms zero references after Step 1.
- **Files:** `gui/app_service.py`.

### Step 3 — Delete `PaperBroker` (now a leaf)
- **Remove:** `execution/paper_broker.py` + the app_service import.
- **Pre-check:** grep `PaperBroker` returns only docs/MODULE_MAP.
- **Files:** `execution/paper_broker.py`.

### Step 4 — Delete `ExecutionRouter`, then `PaperEngine`
- **Order matters:** `execution/execution_router.py` imports `PaperEngine`, so the
  router must go first or `paper_engine.py`'s deletion breaks its import.
- **Remove (4a):** `execution/execution_router.py` + `tests/execution/test_execution_router.py`
  — the top leaf; nothing imports the router.
- **Remove (4b):** `execution/paper_engine.py` + `tests/execution/test_paper_engine.py`
  — a leaf once the router is gone.
- **Pre-check:** after 4a, grep confirms `PaperEngine` has no live import.

### Step 5 — Delete `ExecutionEngine` (now a leaf)
- **Remove:** `execution/execution_engine.py` + `tests/execution/test_execution_engine.py`.
- **Pre-check:** with the router gone (Step 4a), only its own test imports it.
- **Effect:** frees `PositionTracker` to become a leaf.

### Step 6 — Delete `PositionTracker` (now a leaf)
- **Remove:** `execution/position_tracker.py` + `tests/execution/test_position_tracker.py`.
- **Fix:** the TYPE_CHECKING reference in `execution/risk_manager.py` and any
  reference in `tests/execution/test_risk_manager.py`.
- **Keep:** `PositionTrackerProtocol` in `analysis/strategy_engine.py` if still
  used there — that is a separate structural type, not the concrete class.

### Step 7 — Repoint the `positions` readers (pre-root)
- **`health.py`:** change the open-position count from
  `fetch_open_positions(...)` to a `trade_cycles` count.
- **`MonitoringSessionService`:** remove the position writers
  (`upsert_position_with_anchor`, and `insert_trade_with_anchor` if unwired) —
  **only after confirming the service is not wired into app_service.**

### Step 8 — Drop the `positions` table (ROOT — last, isolated)
- **Remove:** `DatabaseManager.upsert_position` / `delete_position` /
  `fetch_open_positions`; the `positions` `sa.Table` in `db/schema.py`; its index;
  and the `positions` entries in `_LIFECYCLE_COLUMN_ADDITIONS` /
  `_LIFECYCLE_COLUMN_REMOVALS`.
- **Update:** affected tests (`tests/integration/test_lifecycle_e2e.py`, monitoring
  tests).  Do this **alone in its own commit** — schema/migration is the only
  truly risky change, so isolating it makes any regression obvious.

### Step 9 — Docs, traceability, Revision Note
- Update `TRACE.md`, `MD.md`, `DD.md`; remove the legacy `_demo.py` log strings.
- Write the Revision Note; flip **SRD-EXE-015.006 → Implemented**.

---

## 4. Status checklist

| Step | Target | Done | Commit |
|---|---|---|---|
| 1 | app_service: drop PaperBroker fallback | ☑ | d2b0f1b9 |
| 2 | app_service: delete `_on_paper_fill`/`_record_paper_*` | ☑ | 15f42847 |
| 3 | delete `paper_broker.py` | ☑ | 50797512 |
| 4a | delete `execution_router.py` (+ test) | ☑ | 3eb5b8a9 |
| 4b | delete `paper_engine.py` (+ test) | ☑ | b83638d5 |
| 5 | delete `execution_engine.py` (+ test) | ☐ | |
| 6 | delete `position_tracker.py` (+ test); fix `risk_manager` | ☐ | |
| 7 | repoint `health.py` + remove MonitoringSession position writers | ☐ | |
| 8 | drop `positions` table + DatabaseManager methods + migration | ☐ | |
| 9 | docs / TRACE / RN; SRD-EXE-015.006 → Implemented | ☐ | |

---

## 5. Notes & guards

- **Baseline:** 21 pre-existing test failures (evaluator key-count, GSPC tick
  translation, tick-worker mocks) — unrelated to this work. The bar for every
  step is "no *new* failures."
- **`PaperBroker` is still imported** in `app_service` as the no-DB fallback —
  Step 1 must remove that before Step 3 can delete the module.
- **`positions` table is the root** because legacy writers *and* `health.py` read
  it. It must go last, alone, after every dependent is removed or repointed.
- The **new** position surface is `trade_cycles` (Active Trades) — the only one
  that should remain after cleanup.
