# Revision Note — RN-INF-1.7.0-20260904

**Tool:** INF
**Version:** 1.7.0
**Date:** 2026-09-04
**Type:** bugfix
**Author:** Claude Opus 5 under user direction
**Phase:** Vendor symbol notation shared into `core/` (ISS-INF-0003)

---

## Summary

ISS-EXE-0012 fixed the dotted-symbol Yahoo lookup in the candle loader and flagged three more
call sites with the same defect (TODO T27). The user asked for those to be fixed. Rather than
copy the one-liner a third and fourth time, the conversion moves into `core/` and every Yahoo
call site now goes through it.

## The fault

The canonical symbol uses a dot for class shares (`BRK.B`); Yahoo keys them with a hyphen
(`BRK-B`). Three call sites passed the dotted form straight through:

| Location | Call | Effect for BRK.B / BF.B |
|---|---|---|
| `gui/app_service.py:372` | `yf.Ticker(sym).fast_info` | Market-watch row shows zeroes |
| `execution/live_bar_worker.py:392` | `yf.download(symbols, ...)` | No live 3m/15m bars |
| `universe/store.py:221` | `yf.Ticker(sym).fast_info.market_cap` | Market cap `None` |

Every one is wrapped in a `try/except` that maps failure to a zero, a `None` or a `continue`,
so none of them ever raised and the whole class of failure stayed invisible.

The deeper cause is that the conversion had no home. After ISS-EXE-0012 it was a private
helper inside `intraday_candle_loader.py`, unreachable from anywhere else, so each new vendor
call site had to rediscover the rule — and all three missed it.

`live_bar_worker` carries an extra trap: `yf.download(..., group_by="ticker")` keys the
returned frame by the symbols **as passed**, so converting the request without converting the
lookup just swaps one silent miss for another.

## The fix

| File | Change |
|---|---|
| `core/symbols.py` | **New** — `yahoo_symbol()`, the single definition of Yahoo class-share notation |
| `execution/intraday_candle_loader.py` | Private `_yahoo_symbol()` removed; imports the shared helper |
| `gui/app_service.py` | `_WatchlistQuoteWorker.run()` converts the lookup; emitted rows stay dotted |
| `universe/store.py` | `_fetch_market_caps()` converts the lookup; returned mapping stays dotted |
| `execution/live_bar_worker.py` | `_poll_yfinance_once()` converts the download list **and** the per-symbol frame lookup; DB writes and `candle_closed` stay dotted |

The invariant: conversion happens per call, at the boundary. Nothing is ever persisted in
vendor form. New `SRD-INF-007.006` states this under FO-INF-007 (Data Provider Abstraction),
so the next vendor call site has a requirement to follow rather than a convention to guess.

The import in `app_service.py` sits above the module's mid-file `_log` assignment on purpose —
everything below that line already trips `E402`, and placing it there keeps the ruff count at
the baseline.

## Verification

`tests/core/test_symbols.py` — 5 cases (UT-INF-007.001.M03.T01–T05): the conversion and its
idempotence, plus one per call site asserting the vendor symbol goes out and the canonical
symbol comes back. All three call-site tests were confirmed failing against the pre-fix code.

- Full suite: **748 passed**, 2 skipped (up from 740 — 8 new tests across this and ISS-GUI-0001)
- `ruff` on the four touched source files: 19 findings — identical to the HEAD baseline
- `mypy --strict`: 147 errors — identical to baseline; `core/symbols.py` itself is clean

The 11 pre-existing failures in `tests/analysis/test_candle_builder.py` and
`tests/screener/test_preset.py`, plus the collection error in
`tests/screener/test_llm_claude_screener.py`, were verified present at HEAD and left alone.

## Follow-ups

- **SRD-INF-007.006 is Draft and needs user approval.** `MD-INF-007.001.M03` and the TRACE row
  follow its status.
- The IBKR conversion (`.` → ` `) is still duplicated at `intraday_candle_loader.py:470`,
  `live_bar_worker.py:242` and `universe/store.py:193`. Folding it in next to `yahoo_symbol()`
  is the obvious next step; no bug depends on it today, so it was not bundled in here.
- `swing_trader_data.py` calls `yf.Ticker` in eight places and was left alone — it takes an
  arbitrary user-supplied ticker, not a universe symbol, so there is no canonical dotted form
  to convert from.
