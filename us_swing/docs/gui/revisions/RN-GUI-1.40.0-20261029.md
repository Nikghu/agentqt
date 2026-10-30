# Revision Note — RN-GUI-1.40.0-20261029

**Version:** 1.40.0
**Date:** 2026-10-29
**Tool:** GUI
**Artifact:** FO-GUI-031 / SRD-GUI-031.020–.023
**Type:** Feature

---

## Summary

Backtest screen, Phase 2. The builder lists the live strategies with tick boxes (allocation % and per-trade %). Run now does Step 1 and then Step 2, with progress on both step pills. A Signals tab lists the periods (strategy, stock, kind, start, end, close) newest first with a strategy filter; double-click opens Charts on that stock. Engine work is in RN-BKT-1.3.0.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-031.002.M02 | `gui/backtest_builder.py` | STRATEGIES list, `set_strategies()`, plan strategies |
| MD-GUI-031.003.M03 | `gui/backtest_workspace.py` | Run does both steps; Stocks / Signals tabs; filter; double-click to Charts |
| MD-GUI-031.001.M01 | `gui/main_window.py` | Backtest `chart_requested` routed to Charts |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-031.020 | Strategies list | Implemented |
| SRD-GUI-031.021 | Run does Step 1 and Step 2 | Implemented |
| SRD-GUI-031.022 | Signals tab with filter | Implemented |
| SRD-GUI-031.023 | Double-click opens Charts | Implemented |

---

## Tests

- 4 new tests (UT-GUI-031.020–.023); Backtest GUI tests 12 passed. `ruff` and `mypy --strict` clean.
- Real window with the user's data: IT sector, preset Test, top 5, ST_AUTO → 15,059 periods listed; time columns widened after the screenshot showed them cut.

---

## Notes

- Period shading on the chart comes later.
