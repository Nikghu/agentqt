# Revision Note — RN-EXE-1.42.2-20261123

**Version:** 1.42.2
**Date:** 2026-11-23
**Tool:** EXE
**Artifact:** FO-EXE-015 / SRD-EXE-015.009
**Type:** Bugfix (ISS-EXE-0017)

---

## Summary

Strategy rule exits were saved with exit reason "manual" because the broker adapter read one shared reason value. Each exit order now saves the reason carried by its own signal, so rule exits show "strategy" and app exits show their real reason.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-EXE-015.002.M01 | `src/us_swing/execution/broker_adapter.py` | Exit reason read from the signal (`_exit_reason()`); `exit_reason_provider` argument removed |
| MD-EXE-015.002.M01 | `src/us_swing/gui/app_service.py` | Forced exits put their reason on the signal; `_pending_exit_reason` removed |
| MD-EXE-015.002.M01 | `tests/execution/test_broker_adapter.py`, `tests/gui/test_app_service_force_exit_cycle.py`, `tests/integration/test_short_cycle_e2e.py` | New T25, T26; tests pass the reason on the signal |

## Docs

SRD-EXE v1.41.0 (SRD-EXE-015.009), UTCD-EXE v1.28.0, ISS-EXE-0017.

## Tests

`pytest tests/execution tests/gui/test_app_service_force_exit_cycle.py tests/gui/test_app_service_duplicate_exit.py tests/integration/test_short_cycle_e2e.py`: 451 pass. `ruff` and `mypy --strict` clean on `broker_adapter.py`.

## User check

The next strategy rule exit shows "strategy" in Trade History; a Dashboard Exit shows "manual".