# Revision Note — RN-GUI-1.59.3-20261105

**Tool:** GUI
**Version:** 1.59.3
**Date:** 2026-11-05
**Type:** bugfix
**Author:** Claude Opus 5.5 under user direction
**Phase:** Update now downloads only stocks behind (ISS-GUI-0018)

---

## Summary

Update now (delta mode) sent all index stocks to the download, starting from the oldest last candle. One stock behind (HLT) made all 503 stocks re-download. It now picks only index stocks whose last daily candle is before the last trading day (failed stocks included, so IBKR is asked again) and starts from the day after the oldest of them. None behind → "All stocks are already up to date", no download.

## Changes

| File | Change |
|---|---|
| `gui/app_service.py` | `_stocks_behind()`, `AppService._candle_stocks_behind()`; delta branch of `start_candle_download` |
| `tests/gui/test_app_service_candle_status.py` | UT-GUI-006.001.M01.T25–T27 |

## Requirements

SRD-GUI-006.023 added, asked by user 2026-11-05 in chat → Implemented.

## Verification

- `tests/gui -k candle`: 41 passed. ruff and mypy show no new errors in `app_service.py`.
- Real app run with TWS not done (user check, T106).
