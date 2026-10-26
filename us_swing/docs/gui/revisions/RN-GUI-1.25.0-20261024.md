# Revision Note — RN-GUI-1.25.0-20261024

**Version:** 1.25.0
**Date:** 2026-10-24
**Tool:** GUI
**Artifact:** FO-GUI-025 / SRD-GUI-025.001–.007
**Type:** Feature

---

## Summary

The Dashboard now uses a tiled workspace (FO-GUI-025, Phase 1 of 5). A one-line KPI strip sits at the top with a user view switch and a Comfort / Compact density switch. Four tiles sit in a 2 × 2 grid (Open Positions, Market Watch, Trade History, P&L by Strategy), and each tile can be maximised. Layout settings are remembered across restarts.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-025.003.M01 | `us_swing/src/us_swing/gui/dashboard_tiles.py` | New: Tile, TileGrid (maximise), KpiStrip, StrategyPnlList, PnlBar |
| MD-GUI-025.001.M02 | `us_swing/src/us_swing/gui/dashboard_panel.py` | Tiled layout, KPI values, view and density switches, remembered settings, watchlist tile; removed stat cards and scope strip |
| MD-GUI-001.001.M01 | `us_swing/src/us_swing/gui/main_window.py` | Dashboard lays out its own cards; removed old dashboard wiring |
| — | `us_swing/assets/icons/maximize-2.svg`, `minimize-2.svg` | New Lucide icons for the tile maximise button |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-025.001 | A one-line KPI strip shows P&L today, unrealised P&L, equity, cash, capital used "of 95%" and open positions. | Implemented |
| SRD-GUI-025.002 | The strip ends with the user view switch and a Comfort / Compact density switch. | Implemented |
| SRD-GUI-025.003 | Four tiles sit in a 2 × 2 grid, each with its own header, count and buttons. | Implemented |
| SRD-GUI-025.004 | Each tile has a Maximise button; clicking again restores the grid. Only one tile maximised at a time. | Implemented |
| SRD-GUI-025.005 | The P&L by Strategy tile lists today's P&L as bars with a total row, or "No strategies". | Implemented |
| SRD-GUI-025.006 | Density, user view and the maximised tile are remembered across restarts. | Implemented |
| SRD-GUI-025.007 | The Market Watch tile shows the user's watchlist with add, remove and refresh controls. | Implemented |

---

## Design Decisions

- Market Watch tile shows the user's watchlist (not index ETFs); index ETFs stay in the title bar. User choice.
- Square Off All moved into the Open Positions tile header.
- Dashboard refresh of strategy P&L is debounced; the tile timers run only while the dashboard is visible.

---

## Issues Resolved

None

---

## Test Coverage

10 UT cases (UT-GUI-025.*) in `tests/gui/test_dashboard_tiles.py` — 10 Pass. GUI suite 355 passed. Note: `test_chart_workspace.py` cannot import on this machine (PyQt6-WebEngine / PyQt6 version mismatch, pre-existing environment issue).
