# ISS-BKT-0001 — Net P&L counts trades still open at test end before their exit costs

**Tool:** BKT · **Severity:** Low · **Status:** Fixed · **Date:** 2026-11-02
**Affected:** MD-BKT-002.030.M12

## Expected
Net P&L (last day's equity minus capital) equals the sum of all trades' net P&L.

## Actual
Run "Backtest_4trade": 37 trades sum to $128.60, Net P&L shows $142.58 ($13.99 too high).

## Root cause
`_Sim.finish()` closes the positions still open with reason `end_of_test` after the last daily money row was saved. That row marks them at the close but without the exit slippage and the two $1 commissions (6 trades × $2 + about $2 slippage).

## Fix
`finish()` rewrites the last money row after the test-end closes: equity = capital + realized, nothing deployed or open (SRD-BKT-002.037). Old saved runs keep the old value; a re-run is correct. Test UT-BKT-002.037.M12.T02.
