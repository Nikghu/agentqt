# Revision Note — RN-EXE-1.38.0-20261029

**Version:** 1.38.0
**Date:** 2026-10-29
**Tool:** EXE
**Artifact:** FO-EXE-006 / SRD-EXE-006.014
**Type:** Bugfix

---

## Summary

Live strategy frames included the 3m and 15m bar that was still forming, so a strategy could act on a price that had not closed. The loader now drops the unfinished last 3m/15m bar in `load_execution_frames`. Live ST_AUTO entries and exits now fire only after a 15m bar closes. This matches the backtest (SRD-BKT-002.050).

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-EXE-006.001.M01 | `execution/intraday_candle_loader.py` | New `_closed_bars()` drops the unfinished last 3m/15m bar in `load_execution_frames` |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-EXE-006.014 | Live strategy frames drop the unfinished last intraday bar, so every function reads closed bars only | Implemented |

---

## Design Decisions

- User accepted (2026-10-29): live ST_AUTO entries/exits fire only after a 15m bar closes.
- Open: ST_AUTO `Price(... 'Last' ...)` now reads one 15m bar older than before; user to decide on `current` (TODO T63).
- SRD number: SRD-EXE-006.013 was already taken, so .014 is used.

---

## Issues Resolved

None

---

## Test Coverage

- New: UT-EXE-006.001.M01.T22–T23 — both Pass.
- `tests/execution`: 329 passed (one timing-flaky test, `test_request_stop_stops_engine_within_3s`, passes alone).
- `ruff` clean; `mypy` no errors in changed files.
