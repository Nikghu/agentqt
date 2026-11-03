# Revision Note — RN-GUI-1.56.6-20261103

**Tool:** GUI
**Version:** 1.56.6
**Date:** 2026-11-03
**Type:** bugfix
**Author:** Claude Opus 5.5 under user direction
**Phase:** Intraday chart axis in New York time; unused market hours fields removed

---

## Summary

After the US clock change (1 Nov) the intraday chart axis looked one hour off: the chart library labels
the axis in UTC, and only the hover label used New York time. The axis now uses New York time, so the
session always reads 09:30 … 16:00. Settings → Scheduler also showed "Market open time" / "Market close
time" (saved as 15:00 / 23:00 US/Eastern); no code reads them, so the fields are removed.

## Changes

| File | Change |
|---|---|
| `gui/chart_panel.py` | `_build_html` adds a New York `tickMarkFormatter` for intraday timeframes (Execution, Charts, Screener charts) |
| `gui/settings_panel.py` | Market open / close fields removed from the Scheduler section, its load and save |

## Requirements

FO-GUI-026 (chart) and FO-GUI-027 (Settings); no SRD text change. `SystemConfig.market_open/market_close`
and `is_market_open()` in `gui/system_store.py` are kept (old saved files still load); `is_market_open()` has no callers.

## Verification

- DELL 3m candles rendered: axis reads 11:00, 12:00, 13:00 New York (UTC would be 16:00, 17:00, 18:00)
- `pytest tests/gui -k "settings or scheduler or sidebar or chart_drawings"`: 91 passed
- `ruff` clean on both files
- Real-app check pending (TODO T94)
