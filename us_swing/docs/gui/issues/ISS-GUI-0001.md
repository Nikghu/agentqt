# Issue Report — ISS-GUI-0001

**Tool:** GUI (Settings → Database tab)
**Severity:** High (the app dies on an uncaught exception; the same code path would have destroyed the trade history had it succeeded)
**Status:** Resolved
**Date Opened:** 2026-09-04
**Date Resolved:** 2026-09-04
**Reporter:** User (crash log from `run_gui.py`, `PermissionError: [WinError 32]` on Reset Database)
**Resolution:** RN-GUI-1.4.1-20260904
**Related:** ISS-EXE-0012 (fixed in the same session, unrelated cause)

---

## Symptom

Pressing **Reset Database** in Settings → Database killed the application:

```
2026-09-03T09:28:27-0400  CRITICAL  root — Uncaught exception:
Traceback (most recent call last):
  File "us_swing/gui/settings_panel.py", line 1376, in _on_reset_db
    self._svc.reset_candle_db()
  File "us_swing/gui/app_service.py", line 3700, in reset_candle_db
    _CANDLE_DB_PATH.unlink(missing_ok=True)
PermissionError: [WinError 32] The process cannot access the file because it is
being used by another process: 'C:\Users\Niket32\.usswing\candles.db'
QThread: Destroyed while thread '' is still running
```

The trailing `QThread` message is a consequence, not a second defect: the crash tore the
process down while a worker thread was still alive.

## Evidence

`reset_candle_db()` deleted the database **file**. Windows refuses to unlink a file that any
process still holds open, and the app holds it open for its whole lifetime:

| Holder | Location |
|---|---|
| SQLAlchemy engine (`self._db`) | `gui/app_service.py:1690` — created at lifecycle boot, never disposed |
| Strategy store | `gui/strategy_store.py:28` |
| Rex counter repository | `execution/strategy_engine/_rex_counter.py` |
| Live bar worker | `execution/live_bar_worker.py` |
| Execution panel | `gui/execution_panel.py:102` |

Confirmed on the reporter's machine: opening a `sqlite3` connection and then calling
`Path.unlink()` reproduces `WinError 32` exactly.

A second, larger problem surfaced while reading the live database. `candles.db` is not only
candles — deleting the file would have taken the user's trading data with it:

| Table | Rows at time of report |
|---|---|
| `price_1d` / `price_1w` / `price_1m` / `price_3m` / `price_15m` | ~653,000 |
| `monitoring_session` | 992 |
| `trades` | 268 |
| `trade_cycles` | 133 |
| `strategy_rex_counters` | 88 |
| `strategies` | 2 |

The confirmation dialog promised only to "permanently delete ALL candle data". The Windows
lock is the sole reason this data loss never actually happened.

## Root Cause

Two defects on the same path:

1. **Wrong unit of deletion.** The reset removed the whole database file when it needed to
   clear only the candle rows. The file is shared with unrelated, non-reproducible trading
   state, and it is held open by design so the delete could never succeed on Windows.
2. **Unguarded Qt slot.** `_on_reset_db` called into the service with no `try`, so any
   exception escaped into the Qt event loop and terminated the app instead of surfacing to
   the user. The button was also left stuck on "Resetting…".

## Fix

| File | Change |
|---|---|
| `gui/app_service.py` | `reset_candle_db()` now issues `DELETE FROM` against `_RESETTABLE_CANDLE_TABLES` in place and never unlinks the file |
| `gui/app_service.py` | New `_RESETTABLE_CANDLE_TABLES = ("price_1d", "price_1w")` and `_reclaim_sqlite_space()`, which downgrades a `VACUUM` lock failure to a warning |
| `gui/settings_panel.py` | `_on_reset_db` wraps the call in `try/except/finally` — errors log and show a `QMessageBox.critical`, and the button is always restored |
| `gui/settings_panel.py` | Confirmation dialog reworded to match the new scope: daily and weekly candles only, trades and strategies kept |

Reset scope was confirmed with the user: **daily and weekly only**. Intraday tables
(`price_1m`, `price_3m`, `price_15m`) are now left in place, as are all trading tables.

`VACUUM` is best-effort. Reclaiming disk space is not part of the reset contract, so another
connection holding a read lock logs `[CandleDB] Could not compact the database file` rather
than failing the reset.

## Verification

`tests/gui/test_app_service_reset_candle_db.py` — 6 cases (UT-GUI-006.001.M01.T05–T06):
reset succeeds while a second connection is open (the original crash); trading tables
survive; intraday candles survive; the file is never unlinked; checkpoint and failed-symbols
files are removed and the status refresh fires; a missing table is recreated empty.

`tests/gui/` + `tests/execution/test_intraday_candle_loader.py`: 141 passed.
`ruff` on the touched files: 21 findings, identical to the HEAD baseline.
`mypy --strict` on `app_service.py` + `settings_panel.py`: 313 errors, identical to baseline.

## Affected Artifacts

| Artifact | Change | Status |
|---|---|---|
| `gui/app_service.py` | In-place row deletion replaces file unlink | Done |
| `gui/settings_panel.py` | Slot exception guard + reworded dialog | Done |
| `tests/gui/test_app_service_reset_candle_db.py` | New regression suite | Done |
| SRD-GUI-006.018 | New row covering crash-safe reset semantics and the preserved tables | Approved by user 2026-09-04 → Implemented |
| UTCD (GUI) | UT-GUI-006.001.M01.T05–T06 rows | Updated |
| TRACE (GUI) | SRD-GUI-006.018 row → test + RN references | Updated |

## Notes

- No SRD governed the Reset Database button before this issue. SRD-GUI-006.011 covers only
  the status card and its refresh, not the destructive path. SRD-GUI-006.018 was written to
  close that gap, approved by the user on 2026-09-04, and is now Implemented.
- `DatabaseManager` still exposes no `dispose()` / `close()`. Nothing in this fix needs one,
  since the reset no longer requires releasing the file handle, but any future feature that
  truly must replace the file will need it (INF, `MD-INF-004.001.M01`).
- The intraday tables are populated by `LiveBarWorker` and the candle loader and are not
  shown on the Database tab. If the user later wants them cleared too, adding them to
  `_RESETTABLE_CANDLE_TABLES` is the whole change.
