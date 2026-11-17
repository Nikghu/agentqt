# Revision Note — RN-GUI-2.1.0-20261117

**Version:** 2.1.0
**Date:** 2026-11-17
**Tool:** GUI
**Artifact:** FO-GUI-025 / SRD-GUI-025.021–.023
**Type:** Feature

---

## Summary

The Dashboard Market Watch tile now has a Sector Rotation tab. It ranks the 11 sector ETFs by their move minus the equal-weight S&P 500 (RSP) move over 1W, 1M or 3M, as green and red bars. The candle download now also fetches daily candles for RSP and the 11 sector ETFs, after SPY.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-025.022.M06 | `src/us_swing/gui/sector_rotation.py` | Added: sector moves against RSP and the ranked bar view |
| MD-GUI-025.023.M07 | `src/us_swing/gui/app_service.py` | Changed: `get_daily_closes()`; candle download fetches RSP and sector ETFs (stops on Stop) |
| MD-GUI-025.001.M02 | `src/us_swing/gui/dashboard_panel.py` | Changed: Market Watch / Sector Rotation tabs and range chips in the tile |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-025.021 | Market Watch and Sector Rotation tabs in the tile | Implemented |
| SRD-GUI-025.022 | Ranked sector bars against RSP over 1W / 1M / 3M | Implemented |
| SRD-GUI-025.023 | Candle download fetches RSP and the 11 sector ETFs | Implemented |

---

## Tests

8 new UT cases Pass (UT-GUI-025.021.M02.T01, .022.M06.T01–T05, .022.M07.T01, .023.M07.T01). GUI suite: 725 passed.

## Known

- The tab shows "No sector candles yet" until the next candle update with TWS.
- Each update asks IBKR for 2 years of daily bars for 12 more symbols (as for SPY).
