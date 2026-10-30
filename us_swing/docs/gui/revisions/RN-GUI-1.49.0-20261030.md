# Revision Note — RN-GUI-1.49.0-20261030

**Version:** 1.49.0
**Date:** 2026-10-30
**Tool:** GUI
**Artifact:** FO-GUI-031 / SRD-GUI-031.070–.074
**Type:** Feature

---

## Summary

The Backtest setup moved out of the left builder into its own window (user picked option C1, https://claude.ai/artifact/974y5KaeuTj5YP4QYSezaB). The Backtest screen now shows a one-line plan summary under the step strip with Edit setup and Run, and the results use the full width. Edit setup opens a frameless modal window: a side menu (Run, Stocks, Screener, Strategies, Account) where each item shows its value and a ✓ or ! mark, titled cards with one help line and label-left / control-right rows, and a footer with the data check line, Cancel, Save and Run. Screener source is a Replay / Saved lists choice; Strategies is a table (Use, Strategy, Allocation %, Per trade %). Cancel, Esc and ✕ put the old plan back.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-031.071.M10 | `gui/backtest_setup.py` | New: `BacktestSetupDialog`, `section_marks()` |
| MD-GUI-031.002.M02 | `gui/backtest_builder.py` | Card pages, `card()`, strategy table, source choice, `summaries()`, `load_plan()` |
| MD-GUI-031.003.M03 | `gui/backtest_workspace.py` | Left builder removed; plan line, Edit setup, window wiring |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-031.070 | Plan line with Edit setup and Run; full-width results | Implemented |
| SRD-GUI-031.071 | Setup window with side menu values and ✓ / ! | Implemented |
| SRD-GUI-031.072 | Titled cards, label-left / control-right rows | Implemented |
| SRD-GUI-031.073 | Source choice; strategy table | Implemented |
| SRD-GUI-031.074 | Footer with data check, Cancel, Save, Run | Implemented |

---

## Tests

8 new tests; backtest GUI + engine 210 pass; Screener, main window and Settings tests 77 pass. Real-window check with real presets and strategies.
