# Revision Note — RN-GUI-1.55.0-20261103

**Version:** 1.55.0
**Date:** 2026-11-03
**Tool:** GUI
**Artifact:** FO-GUI-031 / SRD-GUI-031.086
**Type:** Enhancement

---

## Summary

A new backtest plan now starts with Daily loss stop 10 % and Commission $0 per order. Only Capital still comes from the active user's risk settings.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-031.002.M02 | `gui/backtest_builder.py` | Start values 10 % and $0; `set_account_defaults(capital)` no longer takes the loss stop |
| MD-GUI-031.003.M03 | `gui/backtest_workspace.py` | Passes only Max capital to the builder |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-031.086 | Backtest start values: loss stop 10 %, commission $0 | Implemented |

---

## Design Decisions

- User chose 2026-11-03: the backtest loss stop no longer copies the live Max daily loss.
- `backtest/spec.py` fallbacks are unchanged, so old plan files without a commission still read $1 and old results stay the same.

---

## Test Coverage

- New UT-GUI-031.086.M02.T01; UT-GUI-031.030.M02.T01 updated. Backtest GUI and `tests/backtest`: 218 passed.
- `ruff` clean; `mypy --strict` no new errors.
