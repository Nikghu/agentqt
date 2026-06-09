# Revision Note — RN-EXE-1.19.0-20260608

**Version:** 1.19.0
**Date:** 2026-06-08
**Tool:** EXE
**Artifact:** FO-EXE-009, FO-EXE-010 / SRD-EXE-009.*, SRD-EXE-010.*
**Type:** Bugfix

---

## Summary

Fixed orphaned ENTERED lifecycle-ledger rows caused when a trade cycle closes via a non-FILLED exit fill (partial close, abort, or manual close). A new terminal-event projection now fires on every trade-cycle end (CycleClosed or CycleAborted) and flips the ledger to EXITED. Pre-open reconciliation now self-heals any already-stranded ENTERED row (logged as a heal warning) instead of reporting it as a fatal invariant violation, so reconciliation can proceed even after a dirty shutdown.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-EXE-009.002.M03 | `core/monitoring_session/__init__.py` | Added `wire_cycle_ledger_projection(bus, command, terminal_event_types, *, clock=None)` factory; injects it into `__all__` for wiring at composition root. |
| MD-EXE-009.002.M02 | `core/monitoring_session/_service.py` | Modified `reconcile_preopen()`: a symbol with ENTERED ledger row but no open cycle (entered − carryover) is now healed to EXITED via `mark_exited()` and logged as a heal warning instead of reported as invariant violation. Added heal count to INFO log. Changed SRD-EXE-010.003 from report-only to heal-stranded + report-unhealable. |
| (GUI) | `gui/app_service.py` | Wired `wire_cycle_ledger_projection(bus, command, (CycleClosed, CycleAborted))` after lifecycle service construction to subscribe to terminal trade-cycle events and flip ledger on close/abort. |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-EXE-009.010 | Expose `MonitoringCommand` (mutating methods) with lifecycle state-transition capabilities. | Implemented |
| SRD-EXE-010.003 | A symbol is retained if in filtered set, in carryover positions, or has any ENTERED ledger row. Invariant violations are reported. | Implemented |

---

## Design Decisions

- **Terminal-event projection pattern:** Elected to wire a stateless event handler at the composition root (`app_service`) rather than embed the ledger flip inside `TradeCycleService` or `OrderIngestion`. This keeps the monitoring lifecycle decoupled from trade-cycle details and allows the event handler to be injected/tested independently.
- **Self-healing reconciliation:** Pre-open reconcile now heals a symbol with ENTERED ledger but no open position (edge case after dirty shutdown) to prevent reconciliation from failing completely. The heal is logged at WARNING so the user can investigate if unexpected.

---

## Issues Resolved

- **Orphaned ENTERED rows (observed live 2026-06-08 for symbol SATS):** Trade cycle closed via a non-FILLED exit (abort, manual close) without flipping the ledger, leaving the symbol stranded in ENTERED state. Next pre-open reconcile flagged an invariant violation and stopped. Now: every cycle close/abort path triggers a ledger flip via the terminal-event handler.

---

## Test Coverage

- UT-EXE-009.002.M02.T17 — Rewritten: stranded ENTERED row is healed to EXITED (was: reported as invariant_violation).
- UT-EXE-009.002.M02.T17b — NEW: open cycle with no ENTERED ledger row stays a reported invariant_violation.
- UT-EXE-009.002.M02.T17c — NEW: terminal cycle-event projection flips ENTERED → EXITED.
- UT-EXE-009.002.M02.T17d — NEW: projection is a safe no-op for an unknown symbol.

Results: `tests/core/monitoring_session/test_service.py` + `tests/execution/test_trade_cycle_service.py` = 79 passed. ruff + mypy --strict clean on changed core files.
