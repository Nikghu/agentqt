# Revision Note — RN-EXE-1.32.3-20260904

**Tool:** EXE
**Version:** 1.32.3
**Date:** 2026-09-04
**Type:** bugfix
**Author:** Claude Opus 5 under user direction
**Phase:** Yahoo Finance candle fallback (ISS-EXE-0012)

---

## Summary

From the same startup log as ISS-GUI-0001: with TWS closed, the candle loader fell back to
Yahoo Finance and reported `$BRK.B: possibly delisted; no price data found`. The stock is not
delisted — Yahoo simply does not know it by that name.

## The fault

Yahoo Finance keys class shares with a hyphen (`BRK-B`); the project's canonical symbol uses
a dot (`BRK.B`). `_fetch_symbol_yfinance()` passed the dotted symbol straight into
`yf.Ticker(symbol)`, so `ticker.history()` returned an empty frame and the loader logged the
symbol as missing.

The separator is already normalised for IBKR, which wants a space — at
`intraday_candle_loader.py:470`, `live_bar_worker.py:242` and `universe/store.py:193`. Yahoo
never got the same treatment.

Two S&P 500 members are affected, `BRK.B` and `BF.B`, on every Yahoo fallback run. The
per-symbol error isolation required by SRD-EXE-006.005 worked exactly as specified and, in
doing so, kept a systematic failure looking like two isolated misses.

## The fix

| File | Change |
|---|---|
| `execution/intraday_candle_loader.py` | New module-level `_yahoo_symbol()` — `symbol.replace(".", "-")` |
| `execution/intraday_candle_loader.py` | `_fetch_symbol_yfinance()` now calls `yf.Ticker(_yahoo_symbol(symbol))` |

Only the lookup key changes. Stored rows, log lines and the `get_last_timestamp()` delta
check keep using the dotted symbol, so the database stays keyed on the canonical form and no
migration is needed.

## Verification

Two new cases in `tests/execution/test_intraday_candle_loader.py`:

- **UT-EXE-006.001.M01.T15** — `BRK.B` reaches Yahoo as `BRK-B`. Confirmed failing against
  the pre-fix code, then passing after.
- **UT-EXE-006.001.M01.T16** — `AAPL` passes through unchanged.

- `tests/execution/test_intraday_candle_loader.py` + `tests/gui/`: **141 passed**
- `ruff` on the touched file: 21 findings — identical to the HEAD baseline
- `mypy --strict`: 18 errors — identical to baseline

## Follow-ups

Three further Yahoo call sites carry the same defect and were deliberately left alone to keep
this fix to the reported bug:

| Location | Call |
|---|---|
| `gui/app_service.py:372` | `yf.Ticker(sym).fast_info` — market-watch quotes |
| `execution/live_bar_worker.py:392` | `yf.download(symbols, ...)` — live 3m/15m batch |
| `universe/store.py:221` | `yf.Ticker(sym).fast_info.market_cap` — universe market caps |

The clean follow-up is to move `_yahoo_symbol()` into `core/` and apply it at all four sites,
alongside the existing IBKR normalisation.
