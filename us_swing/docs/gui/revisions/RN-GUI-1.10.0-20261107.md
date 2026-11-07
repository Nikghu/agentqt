# Revision Note — RN-GUI-1.10.0-20261107

**Version:** 1.10.0
**Date:** 2026-11-07
**Tool:** GUI
**Artifact:** FO-GUI-034 / SRD-GUI-034.045–.052
**Type:** Feature

---

## Summary

Market Floor now looks like the approved design (Option 1, screen 1A). The header shows market chips and a tidy toolbar; edit tools show only in edit mode. New painted panel views: market tiles, sector heat map, breadth line and sector rotation. Idea tables show a score bar and a coloured Long or Short label. The default Overview follows the design, and the saved Default layout gets it once.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-034.047.M27 | `gui/floor_charts.py` (new) | Tiles, heat map, line and rotation views; score and side cell delegates |
| MD-GUI-034.047.M27 | `gui/floor_panel.py` | Painted views in the panel body; a gone view opens in the product's first view |
| MD-GUI-034.045.M28 | `gui/market_floor.py` | Header chips, edit-only buttons, Fold feed, Reset tab; desk bar removed from the Floor |
| MD-GUI-034.047.M29 | `core/desk_floor.py`, `gui/floor_sample.py` | `market.tiles`, `breadth.history` products and `chips()` from desk.db |
| MD-GUI-034.052.M30 | `gui/floor_layouts.py` | New default Overview, Sectors and Regime & Breadth panels; file version 2 |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-034.045 | Header chips: regime, fear, VIX, above 50-day, next event | Implemented |
| SRD-GUI-034.046 | Tidy toolbar; edit tools only in edit mode; no desk bar on the Floor | Implemented |
| SRD-GUI-034.047 | Market tiles view | Implemented |
| SRD-GUI-034.048 | Sector heat map view | Implemented |
| SRD-GUI-034.049 | Breadth line view (60 days) | Implemented |
| SRD-GUI-034.050 | Sector rotation view | Implemented |
| SRD-GUI-034.051 | Score bar and side label in idea tables | Implemented |
| SRD-GUI-034.052 | Design default Overview; Default layout refreshed once | Implemented |

---

## Design Decisions

- Charts are painted with `QPainter` (user choice), not a web view.
- Bias chip, idea state (Triggered / Waiting), Ideas to Watchlist and rotation tails are left for later phases: the desk has no bias value and idea state needs live prices.
- The rotation chart shows sector ETF tickers (XLK, XLE...) so labels do not overlap.

---

## Tests

12 new UTCD tests Pass (`tests/gui/test_floor_design.py`); 5 older floor tests updated for the new default. Full suite: 2475 passed, 12 old failures (T112 and the sidebar list test, same on main), 2 skipped.
