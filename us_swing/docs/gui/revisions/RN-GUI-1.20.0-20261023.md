# Revision Note — RN-GUI-1.20.0-20261023

**Version:** 1.20.0
**Date:** 2026-10-23
**Tool:** GUI
**Artifact:** FO-GUI-024 / SRD-GUI-024.001
**Type:** Feature

---

## Summary

Phase 2 of the Execution screen redesign (canvas Option F2). The old "Trade Execution" title row is replaced by a page header in the same style as the Screener header: "Execution", ADMIN tag, the last screener run line, chips for unrealised P&L, strategies running X of Y and broker state, and the Execute-for combo (moved, same behaviour).

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-024.001.M01 | `us_swing/src/us_swing/gui/execution_header.py` | New: `ExecutionHeader`, `last_run_text()`; unrealised = sum of open-cycle P&L in the viewing scope (3 s refresh); running = RUNNING / SQUARING_OFF or holding an open cycle |
| MD-GUI-004.001.M01 | `us_swing/src/us_swing/gui/execution_panel.py` | Header row and `_on_scope_changed` replaced by `ExecutionHeader` |
| MD-GUI-017.001.M02 | `us_swing/src/us_swing/gui/theme.py` | `exec_chip` QSS (all themes) |
| MD-GUI-024.001.M01 | `us_swing/tests/gui/test_execution_header.py` | 3 tests (UT-GUI-024.001.M01.T01–T02) |

---

## Verification

3 new tests pass; execution panel and manual-pick tests (19) pass. `ruff` and `mypy --strict` clean on `execution_header.py`.
