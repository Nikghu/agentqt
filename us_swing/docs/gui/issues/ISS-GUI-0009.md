# Issue Report — ISS-GUI-0009

**Tool:** GUI
**Severity:** High (app shows "Not responding" for seconds during market hours while trades stream)
**Status:** Resolved
**Date Opened:** 2026-10-27
**Date Resolved:** 2026-10-27
**Reporter:** User (screenshot — Dashboard, "USSwing.exe is not responding", v1.6.1)
**Resolution:** RN-GUI-1.37.2-20261027

---

## Symptom

During market hours, with the IBKR feed live and 9 paper positions streaming, the app froze for a few seconds at a time and Windows showed "USSwing.exe is not responding". It then recovered on its own.

## Evidence

`py-spy` attached to the running v1.6.1 app (read-only):

| Check | Result |
|---|---|
| CPU use | ~1000 s of CPU in 30 min since start |
| Main thread busy (30 s and 60 s profiles) | 58% and 54% of the time |
| Charts source list rebuild (`SourceList._fill`) | 27.9% of all time, while Charts was not open |
| Theme file read (`load_theme_id`) | 8.2% of all time |
| 5 dumps taken during a live "Not responding" | 4 of 5 in `_on_watchlist_tick` → `SourceList.refresh` → `_fill` |
| One `C.RED` lookup | 142 µs (disk read) vs 0.18 µs in memory |

## Root Cause

1. `SourceList` (Charts, PR #87) is connected to `watchlist_updated` / `positions_updated`, which fire on every tick. Each time it deleted and rebuilt all row widgets, with several `setStyleSheet` calls each, even while hidden.
2. `active_palette()` — behind every `C.<token>` lookup — read `~/.usswing/theme_id` from disk on each call (since the Carbon theme work, 23 Oct), so every paint did file I/O.
3. Tick slots emitted one view signal per tick, so every listening view refreshed many times a second.

In tick bursts the main thread reached 100% and could not answer Windows for 5 s.

## Fix

| File | Change |
|---|---|
| `gui/theme.py` | Theme id read once and kept in memory; `save_theme_id` updates it |
| `gui/chart_source_list.py` | Skips tick refreshes while hidden; refreshes in `showEvent` when stale |
| `gui/app_service.py` | `_queue_tick_refresh` / `_flush_tick_refresh`: tick view signals sent at most every 250 ms; cleared on disconnect |

## Verification

UT-GUI-000.008.M01.T01–T02, M02.T01, M03.T01–T02 — all fail or error on the pre-fix code and pass after. `tests/gui` + `tests/integration`: 515 passed, 2 skipped; `tests/execution`: 327 passed. `ruff` clean; `mypy --strict` count unchanged (141, all pre-existing). Live re-profile of the fixed build is pending during market hours.

## Affected Artifacts

| Artifact | Change | Status |
|---|---|---|
| SRD-GUI-000.008 | New — app stays responsive while ticks stream (user approved) | Implemented |
| MD-GUI-000.008.M01–M03 | New rows | Implemented |
| UTCD (GUI) | UT-GUI-000.008.* | Pass |
| TRACE (GUI) | SRD-GUI-000.008 row | Updated |

## Notes

- The user remembered a similar freeze being fixed before; no earlier freeze fix was found in git history or the issue files.
