# Revision Note — RN-GUI-1.8.0-20261022

**Tool:** GUI
**Version:** 1.8.0
**Date:** 2026-10-22
**Type:** feature
**Author:** Claude Opus 5.5 under user direction
**Phase:** Manual picks in Trade Execution (FO-GUI-004, SRD-GUI-004.010–.012)

---

## Summary

The user can now trade stocks the screener did not pick. A `[Add symbol…] [+ Add]` box sits in
the Filtered Stocks header. A pick shows at the top as **★ SYMBOL** with RUN "Manual pick" and a
**✕ Remove** cell, stays until removed (per user), and the strategy engine, candle fetch and live
prices treat it like a screened stock.

User decisions (2026-10-22): layout 1 (add box in the header, picks pinned in the same table);
picks stay until removed.

## Behaviour

| Case | Result |
|---|---|
| Typing in the box | Suggestions match symbol or company name ("dell" → "DELL — Dell Technologies"); list refreshes when the universe loads |
| Unknown / duplicate / empty symbol | Refused with a tooltip message |
| Add before the stock list has loaded | Refused: "The stock list is still loading" |
| `BRK B` typed | Stored as `BRK.B` |
| Screener also finds a picked stock | Shown once, as the pick |
| Pick added or removed | List refreshes; no Telegram "screener approved" message |
| Pick removed | Engine stops trading it at once — unless it has an open trade or a screener still lists it |
| Picks only, no screener results | Table shows the picks |

Picks need no assigned users (SRD-GUI-004.009 applies to presets only). The monitoring ledger
records picks under "Manual pick", apart from screener rows.

## Automatic cleanup of old intraday candles (SRD-GUI-004.013)

At app start, before the candle fetch, all 1m/3m/15m candles of a stock are deleted when it is
not in Filtered Stocks, has no open trade or position, and its newest bar is more than 5 days
(`intraday_retention_days`, previously unused) older than the newest bar in the database. Idle
is measured against the database, so a long break from the app deletes nothing. It is skipped
if open trades cannot be read. Daily/weekly candles are not touched. A `[Candles]` log line
lists the removed stocks. The scan takes about 0.3 s on the current DB (924k 1m rows); today it
would remove one stock (VST). User decisions (2026-10-22): stale stocks only; run at app start.

## Files

| File | Change |
|---|---|
| `gui/manual_picks_store.py` (new) | Per-user JSON at `~/.usswing/manual_picks.json`, atomic write, bad file read as empty |
| `gui/app_service.py` | `add_manual_pick()`, `remove_manual_pick()`, `_manual_pick_entries()`, `_refresh_after_pick_change()`; picks lead `get_latest_screener_results()`; ledger split; empty list now updates the engine list; notification gate |
| `gui/execution_panel.py` | Pick input row, `_PinnedPicksProxy`, pick rows in the model, ✕ click removes |
| `data/models.py` | `run_type` comment adds `"pick"` |
| `tests/gui/test_manual_picks.py` (new) | UT-GUI-004.001.M01.T11–T20 |
| `tests/gui/test_app_service_screener_feed.py` | Fake service gains `_manual_pick_entries` |
| `gui/intraday_cleanup.py` (new) | `remove_stale_intraday()` |
| `tests/gui/test_intraday_cleanup.py` (new) | UT-GUI-004.001.M01.T21–T25 |

## Verification

- `tests/gui/`: **254 passed**
- `ruff` clean on new files; `mypy --strict` no new errors (2 old ones remain in unchanged lines)
- pyqt-code-reviewer: no BLOCK. Both WARNs fixed: removed picks left on the engine list for the
  rest of the day; a failed save could raise inside a click handler.

## Not done

- Not checked in the running app yet.
- Clicking ✕ selects the row first, so the chart switches to that stock briefly before the list
  refreshes (reviewer NIT, left as is).
