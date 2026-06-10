# Revision Note — RN-EXE-1.21.0-20260610

**Tool:** EXE
**Version:** 1.21.0
**Date:** 2026-06-10
**Author:** Claude Opus 4.8 under user direction
**Phase:** Enhancement — FO-EXE-006 (SRD-EXE-006.012: Daily/Weekly frames in execution provider)

---

## Summary

Surfaces the **daily (1d) and weekly (1w)** bars already downloaded pre-market for
the screener to the strategy engine, so **both entry and exit** conditions can
reference daily/weekly timeframes. Previously the execution provider returned only
the intraday frames (3m, 15m); exit — which has no screener — could never act on a
daily/weekly condition. The Strategy Builder Timeframe dropdowns now offer `1d` and
`1w` for every indicator.

## Behaviour Changes

- `load_execution_frames(...)` now adds `1d` / `1w` frames (alongside 3m/15m) to the
  candles dict passed to the evaluator. Both entry and exit share that dict, so daily
  /weekly conditions work on both paths with **no engine, router, or evaluator change**.
- **Closed bars only** — daily/weekly are read straight from `price_1d` / `price_1w`
  with no aggregation, no live merge, and no synthetic current-day bar. The pre-market
  download stops at the last closed session/week, so `Price('current', …, '1d')`
  resolves to the last completed daily candle (decision recorded for SRD-EXE-006.012).
- A timeframe is omitted when no stored bars exist for it (no error).
- Strategy Builder: every indicator's Timeframe dropdown extends
  `["3m","15m"]` → `["3m","15m","1d","1w"]`; the value flows verbatim into the
  generated expression (e.g. `RSI('Stock', 14, '1d')`).

## Code Changes

| File | Change | MD |
|---|---|---|
| `execution/intraday_candle_loader.py` | New `load_stored_frames()` reads stored 1d/1w via `db.fetch_bars` (400-day window); `load_execution_frames` merges it into the result | MD-EXE-006.001.M01 |
| `gui/strategy_builder_dialog.py` | Add `1d`, `1w` to every indicator Timeframe `Datatype` list | MD-EXE-006.001.M01 |

## Tests

| Check | Result |
|---|---|
| `tests/execution/test_execution_candle_readpath.py` (T17–T19 added) | 7 passed |
| Full execution + integration suites | 187 passed, 2 skipped; 12 failures all pre-existing (candle loader aggregation, live tick worker, evaluator 14-key — verified identical with changes stashed) |
| `ruff check` | Clean on changed files |
| `mypy` | No new errors in changed file (5 pre-existing errors unchanged) |

## Notes / Deviations

- Stored 1d/1w intentionally bypass `aggregate_timeframe` — those timeframes are
  stored directly by the screener download, not derived from 1m.
- `load_stored_frames` does not take `hist_engine` (no aggregation needed); it reads
  the DB only.

---

**Commit:** pending — Refs: MD-EXE-006.001.M01
