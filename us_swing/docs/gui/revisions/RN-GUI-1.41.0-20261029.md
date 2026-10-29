# Revision Note — RN-GUI-1.41.0-20261029

**Version:** 1.41.0
**Date:** 2026-10-29
**Tool:** GUI
**Artifact:** FO-GUI-031 / SRD-GUI-031.030–.034
**Type:** Feature

---

## Summary

Backtest screen, Phase 3. The builder (now scrollable) has an ACCOUNT group: Capital $ and Daily loss stop % (from the active user's risk settings), When money short, Commission and Slippage. Run now also does Step 3, with progress on the Portfolio pill. New tabs: Trades (summary line with trades, net P&L and win rate), Day log (entered or why skipped) and Money (per day). Also headings on the Stocks and Signals tabs.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-031.002.M02 | `gui/backtest_builder.py` | ACCOUNT group, `set_account_defaults()`, plan account and costs |
| MD-GUI-031.003.M03 | `gui/backtest_workspace.py` | Step 3 in the run worker; Trades / Day log / Money tabs; scrollable builder; headings |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-031.030 | Account fields with user defaults | Implemented |
| SRD-GUI-031.031 | Run does Step 3 | Implemented |
| SRD-GUI-031.032–.034 | Trades, Day log, Money tabs | Implemented |

---

## Tests

- 4 new tests (UT-GUI-031.030–.033); Backtest GUI tests 16 passed. `ruff` and `mypy --strict` clean.
- Real window: 103 trades listed; after the first screenshot the columns were fitted, the builder made scrollable and negative money shown as -$.
