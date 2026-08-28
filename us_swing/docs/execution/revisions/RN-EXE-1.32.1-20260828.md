# Revision Note — RN-EXE-1.32.1-20260828

**Tool:** EXE
**Version:** 1.32.1
**Date:** 2026-08-28
**Type:** bugfix
**Author:** Claude Opus 5 under user direction
**Phase:** IBKR live-readiness review + GUI submit-failure guard

---

## Summary

The user asked whether the IBKR live implementation is ready for deep testing on a
paper account. Rather than trust `RN-EXE-1.32.0`, the whole live path was re-read
against `IBKR_Live_Execution_Plan.md`. Every Phase 0–4 change is genuinely present.
One gap survived all four phases, and this note records it and its fix.

The Phase 4 liveness gate raises `BrokerConnectionError` before touching a dead
socket, and `BrokerAdapter.submit` deliberately re-raises it (`broker_adapter.py:77-80`)
after discarding the registered context. The **router** catches that and rolls back.
The two **GUI** order paths did not — they called the submitter bare.

## The fault

| Path | Site | What happened |
|---|---|---|
| Manual pending-signal execute | `gui/app_service.py:2141` | Exception reached the Qt slot at `execution_panel.py:1488` |
| Active Trades force-exit | `gui/app_service.py:2488` | Same |

Compounding it on the entry path: `execute_signal` calls `_pending_store.execute()`
**before** submitting, and `PendingSignalStore` exposes only `add` / `dismiss` /
`execute` — there is no restore. So a failed submit popped the signal, showed the
user a traceback instead of a message, and left no row to retry from once TWS came
back.

This is exactly **step 5** of `docs/execution/Phase4_Live_Smoke_Test.md` — "kill TWS
mid-flight, then execute a pending signal" — which the runbook says should show a
clean `BrokerConnectionError` message with the symbol released. It would not have.

## The fix

Both paths now catch, `log.exception` for the file log, emit a user-facing
`[Orders]` message to the GUI log panel, and return `-1`. `execute_signal`
additionally re-adds the popped signal to the pending store, so the row reappears
and the user can retry.

`_submit_cycle_exit` does **not** re-add — a force-exit has no pending row to
restore.

## Deliberately not fixed

- **`_pending_exit_reason` stays stale.** `_submit_cycle_exit` sets it before
  submitting; on failure the value survives and a later unrelated exit fill could
  pick up the wrong reason. Real, but separate from this guard — recorded as TODO
  T20 rather than folded in silently.

## Also found while reviewing — recorded, not actioned

- **`cancel_order` has no production caller** anywhere in `src/`. The CANCELLED
  branch in `order_ingestion` can only fire from a manual cancel inside TWS, so the
  path carries no real exercise. TODO T21.
- **`IBKRClientGateway._order_ids` is never pruned.** A late `errorEvent` on a
  finished order re-enters `_on_error`, and since `_client_ref` was already popped
  on the terminal status, ingestion logs "unknown order — skipping". Noise, not
  harm. TODO T22.
- **Broker built from `_users[0].mode`** (`app_service.py:1307`), not the active
  user, and only once at startup. `settings_panel.py:254` already warns "Restart
  the tool for the new trading mode to take effect", so single-user is safe. Carried
  forward from RN-EXE-1.32.0.

## Files Changed

| File | Change |
|---|---|
| `src/us_swing/gui/app_service.py` | try/except around both submit calls; re-add on the entry path |
| `tests/gui/test_app_service_submit_guard.py` | New — 5 cases |
| `docs/execution/MD.md` | New `FO-EXE-015` section, `MD-EXE-015.004.M01` |
| `docs/execution/UTCD.md` | `UT-EXE-015.004.M01.T32–T36` |
| `docs/execution/TRACE.md` | Row extended to T20–T36, v1.20.1 |

## Verification

- `pytest us_swing/tests/gui us_swing/tests/execution us_swing/tests/broker` —
  **385 passed**
- Full suite: 717 passed, 11 failed — every failure in
  `analysis/test_candle_builder.py` or `screener/test_preset.py`, none on the
  execution path
- `ruff` — 19 findings on `app_service.py`, identical to the pre-existing baseline
  (E402 imports, unused `math`); `broker/` and `execution/` clean; new test file clean
- `mypy --strict` — no errors in the edited regions
- Merged as PR #68, branch deleted

## Outstanding

- **Phase 4 live smoke test — STILL NOT RUN.** This was the last code gap before it.
  Runbook at `docs/execution/Phase4_Live_Smoke_Test.md`; 5 steps, 1 share, manual
  only. TODO T19.
- TODO T20–T22 above.
- Unchanged from RN-EXE-1.32.0: F5 DB constraint, N1 silent cancel no-op, N2
  account-wide helpers, and the deferred Phases 5 / 6 / 8 plus FO-EXE-003.
