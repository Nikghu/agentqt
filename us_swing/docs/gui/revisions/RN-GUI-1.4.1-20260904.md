# Revision Note — RN-GUI-1.4.1-20260904

**Tool:** GUI
**Version:** 1.4.1
**Date:** 2026-09-04
**Type:** bugfix
**Author:** Claude Opus 5 under user direction
**Phase:** Settings → Database reset (ISS-GUI-0001)

---

## Summary

The user asked why **Reset Database** killed the app with
`PermissionError: [WinError 32] ... candles.db`. It crashed because the reset deleted the
database *file*, and the app holds that file open for its whole lifetime. Reading the live
database while diagnosing turned up the bigger half of the problem: `candles.db` also stores
the user's trades, cycles and strategies, so the delete was never safe to succeed either.

## The fault

Two defects on one path.

**1 — Wrong unit of deletion.** `reset_candle_db()` called
`_CANDLE_DB_PATH.unlink(missing_ok=True)`. Windows refuses to unlink an open file, and five
components hold `candles.db` open by design:

| Holder | Location |
|---|---|
| SQLAlchemy engine (`self._db`) | `gui/app_service.py:1690` — created at lifecycle boot, never disposed |
| Strategy store | `gui/strategy_store.py:28` |
| Rex counter repository | `execution/strategy_engine/_rex_counter.py` |
| Live bar worker | `execution/live_bar_worker.py` |
| Execution panel | `gui/execution_panel.py:102` |

Had the unlink ever succeeded, it would have destroyed far more than candles:

| Table | Rows on the reporter's machine |
|---|---|
| `price_1d` / `price_1w` / `price_1m` / `price_3m` / `price_15m` | ~653,000 |
| `monitoring_session` | 992 |
| `trades` | 268 |
| `trade_cycles` | 133 |
| `strategy_rex_counters` | 88 |
| `strategies` | 2 |

The confirmation dialog promised only to delete "ALL candle data". The Windows lock is the
one reason the trading data was never lost.

**2 — Unguarded Qt slot.** `_on_reset_db` called the service with no `try`, so the exception
escaped into the Qt event loop and terminated the process. The `QThread: Destroyed while
thread '' is still running` line in the log is that teardown, not a separate bug. The button
was also left stuck reading "Resetting…".

## The fix

Clear rows in place instead of removing the file — no handle release needed, and the trading
tables are untouched:

| File | Change |
|---|---|
| `gui/app_service.py` | `reset_candle_db()` runs `DELETE FROM` over `_RESETTABLE_CANDLE_TABLES`; the unlink is gone |
| `gui/app_service.py` | New `_RESETTABLE_CANDLE_TABLES = ("price_1d", "price_1w")` |
| `gui/app_service.py` | New `_reclaim_sqlite_space()` — `VACUUM` is best-effort, a lock held by another connection logs a warning instead of failing the reset |
| `gui/settings_panel.py` | `_on_reset_db` wrapped in `try/except/finally`: errors log and raise a `QMessageBox.critical`, the button is always restored |
| `gui/settings_panel.py` | Dialog reworded — daily and weekly candles only, trades and strategies kept |

Scope was the user's call, taken before implementing: **daily and weekly only**. The intraday
tables now survive a reset as well.

## Behaviour change

Reset used to promise, and attempt, a full wipe of `candles.db`. It now clears `price_1d` and
`price_1w` and nothing else. On Windows this is the first time the button does anything at
all. Anyone relying on it to clear intraday candles must add those tables to
`_RESETTABLE_CANDLE_TABLES`.

## Verification

`tests/gui/test_app_service_reset_candle_db.py` — 6 new cases
(UT-GUI-006.001.M01.T05–T06): reset succeeds while a second connection is open (the original
crash); trading tables survive; intraday candles survive; the file is never unlinked;
ancillary files are cleared and the status refresh fires; a missing table is recreated empty.

The `WinError 32` scenario was reproduced directly on the reporter's machine before the fix
was accepted, so T01 is a real regression guard rather than a synthetic one.

- `tests/gui/` + `tests/execution/test_intraday_candle_loader.py`: **141 passed**
- `ruff` on the touched files: 21 findings — identical to the HEAD baseline, all pre-existing
- `mypy --strict` on `app_service.py` + `settings_panel.py`: 313 errors — identical to baseline

11 failures elsewhere in the suite (`tests/analysis/test_candle_builder.py`,
`tests/screener/test_preset.py`) and one collection error
(`tests/screener/test_llm_claude_screener.py`) were verified present at HEAD and are
unrelated to this change.

## Follow-ups

- **SRD-GUI-006.018 approved by the user on 2026-09-04 and set to `Implemented`.** It is the
  new row covering crash-safe reset and the preserved tables; no SRD governed the Reset
  button before it.
- `DatabaseManager` exposes no `dispose()` / `close()`. Not needed by this fix, but any
  future feature that must genuinely replace the database file will need one
  (INF, `MD-INF-004.001.M01`).
