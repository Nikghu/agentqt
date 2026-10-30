# Revision Note — RN-GUI-1.42.1-20261029

**Version:** 1.42.1
**Date:** 2026-10-29
**Tool:** GUI
**Artifact:** ISS-GUI-0012
**Type:** Bugfix

---

## Summary

The app no longer freezes for 2–3 seconds when candles close and TWS is not connected. The last
price in the watchlist, Execution and Active Trades now reads one database row instead of
rebuilding 30 days of candles on the screen thread (287 ms → 1.7 ms per stock).

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-EXE-006.001.M01 | `execution/intraday_candle_loader.py` | New `load_latest_close()` |
| — | `gui/app_service.py` | `get_latest_close()` uses `load_latest_close()` |

---

## Tests

- UT-EXE-006.001.M01.T24–T25 added; candle read-path, force-exit and watchlist tests 24 passed. `ruff` clean on changed lines.
- Real database: same last prices for 10 stocks; old 287 ms vs new 1.7 ms per stock.
