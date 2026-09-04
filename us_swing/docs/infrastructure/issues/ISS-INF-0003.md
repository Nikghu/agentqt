# Issue Report — ISS-INF-0003

**Tool:** INF (Data Provider Abstraction) — affects GUI, EXE and universe call sites
**Severity:** Medium (two S&P 500 members silently return no data from every Yahoo Finance call — quotes, market caps and live bars)
**Status:** Resolved
**Date Opened:** 2026-09-04
**Date Resolved:** 2026-09-04
**Reporter:** Follow-up from ISS-EXE-0012 (TODO T27) — user asked for the remaining call sites to be fixed
**Resolution:** RN-INF-1.7.0-20260904
**Related:** ISS-EXE-0012 (same defect, candle-loader call site only)

---

## Symptom

ISS-EXE-0012 fixed the dotted-symbol lookup in the candle loader's Yahoo fallback, but noted
that three other call sites carried the identical defect and were left out of scope. Each
would silently return nothing for `BRK.B` and `BF.B`:

| Location | Call | Effect |
|---|---|---|
| `gui/app_service.py:372` | `yf.Ticker(sym).fast_info` | Market-watch row shows zeroes |
| `execution/live_bar_worker.py:392` | `yf.download(symbols, ...)` | No live 3m/15m bars |
| `universe/store.py:221` | `yf.Ticker(sym).fast_info.market_cap` | Market cap `None` |

None of them raises. Every one is wrapped in a `try/except` that maps failure to a zero, a
`None` or a `continue`, so the whole class of failure was invisible.

## Root Cause

The project's canonical symbol uses a dot for class shares (`BRK.B`). Yahoo Finance keys them
with a hyphen (`BRK-B`); the dotted form resolves to nothing and comes back as an empty frame
rather than an error.

The conversion existed only as a private helper inside `intraday_candle_loader.py` after
ISS-EXE-0012, so nothing else could reach it. The IBKR equivalent (`.` → ` `) was likewise
copy-pasted at three separate sites. With no shared home, each new vendor call site had to
rediscover the rule — and all three missed it.

`live_bar_worker.py` carries an extra trap. `yf.download(..., group_by="ticker")` keys the
returned frame's column level 0 by the symbols **as passed**, so converting the request
without converting the lookup would swap a silent miss for a different silent miss.

## Fix

A single shared helper, placed in `core/` so no tool reaches into another:

| File | Change |
|---|---|
| `core/symbols.py` | **New** — `yahoo_symbol()`, the one definition of Yahoo class-share notation |
| `execution/intraday_candle_loader.py` | Private `_yahoo_symbol()` removed; imports the shared helper |
| `gui/app_service.py` | `_WatchlistQuoteWorker.run()` converts the lookup; emitted rows stay dotted |
| `universe/store.py` | `_fetch_market_caps()` converts the lookup; the returned mapping stays dotted |
| `execution/live_bar_worker.py` | `_poll_yfinance_once()` converts both the download list **and** the per-symbol frame lookup; DB writes and `candle_closed` stay dotted |

The invariant throughout: conversion happens per call, at the boundary. Nothing dotted is
ever persisted in vendor form.

## Verification

`tests/core/test_symbols.py` — 5 cases (UT-INF-007.001.M03.T01–T05): the conversion itself
and its idempotence, plus one per call site asserting the vendor symbol goes out and the
canonical symbol comes back. The three call-site tests were confirmed failing against the
pre-fix code.

- Full suite: **748 passed**, 2 skipped
- `ruff` on the four touched source files: 19 findings — identical to the HEAD baseline
- `mypy --strict`: 147 errors — identical to baseline; `core/symbols.py` itself is clean

## Affected Artifacts

| Artifact | Change | Status |
|---|---|---|
| SRD-INF-007.006 | New row — outbound calls use vendor notation, stored rows stay canonical | Approved by user 2026-09-04 → Implemented |
| MD-INF-007.001.M03 | New module row for `core/symbols.py` | Implemented |
| UTCD (INF) | UT-INF-007.001.M03.T01–T05 | Updated |
| TRACE (INF) | FO-INF-007 forward + reverse rows | Updated |
| `core/symbols.py` | New shared helper | Done |
| 4 call sites | Conversion applied | Done |

## Notes

- `swing_trader_data.py` also calls `yf.Ticker` in eight places. It was left alone: it takes
  an arbitrary user-supplied ticker rather than a universe symbol, so it has no canonical
  dotted form to convert from. Worth a look if it is ever pointed at the S&P 500 universe.
- The IBKR conversion (`.` → ` `) is still duplicated at `intraday_candle_loader.py:470`,
  `live_bar_worker.py:242` and `universe/store.py:193`. Folding it into `core/symbols.py`
  alongside `yahoo_symbol()` is the obvious next step, but no bug depends on it today, so it
  was not bundled into this fix.
