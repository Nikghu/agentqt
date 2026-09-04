# Issue Report — ISS-EXE-0012

**Tool:** EXE (Execution)
**Severity:** Medium (class-share stocks never get intraday history from the Yahoo fallback, so their candle-based entries and exits are un-evaluable whenever IBKR is down)
**Status:** Resolved
**Date Opened:** 2026-09-04
**Date Resolved:** 2026-09-04
**Reporter:** User (`$BRK.B: possibly delisted; no price data found` in the startup log)
**Resolution:** RN-EXE-1.32.3-20260904
**Related:** ISS-GUI-0001 (fixed in the same session, unrelated cause)

---

## Symptom

With TWS closed, the candle loader fell back to Yahoo Finance and failed for `BRK.B`:

```
03:07:08 WARNING [Candles] IBKR connection failed ([WinError 1225] ...) — switching to Yahoo Finance
03:07:13 ERROR   yfinance — $BRK.B: possibly delisted; no price data found (period=2d)
03:07:13 WARNING [Candles] BRK.B — no data returned by Yahoo Finance
```

The IBKR connection refusal in the first line is expected — TWS was not running — and the
fallback itself worked. Only the dotted symbol failed.

## Evidence

Yahoo Finance keys class shares with a hyphen (`BRK-B`), not a dot. `BRK.B` resolves to
nothing there, so `ticker.history()` returns an empty frame and the loader logs it as a
missing symbol.

The codebase already normalises this separator for IBKR, which uses a space:

| Location | Conversion |
|---|---|
| `execution/intraday_candle_loader.py:470` | `symbol.replace(".", " ")` — BRK.B → BRK B |
| `execution/live_bar_worker.py:242` | `symbol.replace(".", " ")` |
| `universe/store.py:193` | `symbol.replace(".", " ")` |

No equivalent existed for Yahoo. `_fetch_symbol_yfinance()` passed the raw dotted symbol
straight to `yf.Ticker(symbol)`.

The S&P 500 universe carries two such symbols, `BRK.B` and `BF.B`, so both are affected on
every Yahoo fallback run.

## Root Cause

`_fetch_symbol_yfinance()` used the canonical dotted symbol as the Yahoo lookup key. The
per-symbol error isolation required by SRD-EXE-006.005 then swallowed the empty result as an
ordinary single-symbol miss, so the systematic failure never escalated.

## Fix

| File | Change |
|---|---|
| `execution/intraday_candle_loader.py` | New module-level `_yahoo_symbol()` — returns `symbol.replace(".", "-")` |
| `execution/intraday_candle_loader.py` | `_fetch_symbol_yfinance()` calls `yf.Ticker(_yahoo_symbol(symbol))` |

Only the lookup key changes. Stored rows, logs and the `get_last_timestamp()` delta check all
continue to use the dotted symbol, so the database stays keyed on the canonical form.

## Verification

`tests/execution/test_intraday_candle_loader.py` — 2 cases:

- UT-EXE-006.001.M01.T15 — `BRK.B` reaches Yahoo as `BRK-B`. Fails against the pre-fix code.
- UT-EXE-006.001.M01.T16 — `AAPL` is passed through unchanged.

`tests/execution/test_intraday_candle_loader.py` + `tests/gui/`: 141 passed.
`ruff` and `mypy --strict` counts on the touched file unchanged from baseline (21 / 18).

## Affected Artifacts

| Artifact | Change | Status |
|---|---|---|
| `execution/intraday_candle_loader.py` | `_yahoo_symbol()` added and applied | Done |
| `tests/execution/test_intraday_candle_loader.py` | T15 + T16 added | Done |
| UTCD (EXE) | UT-EXE-006.001.M01.T15–T16 rows | Updated |
| TRACE (EXE) | SRD-EXE-006.001 row → test + RN references | Updated |
| SRD-EXE-006.001 | No change — symbol normalisation is implementation detail, not a requirement | Unchanged |

## Notes

- Three other Yahoo call sites pass raw symbols and carry the identical defect. They are out
  of scope for this issue and are **not** fixed here:

  | Location | Call |
  |---|---|
  | `gui/app_service.py:372` | `yf.Ticker(sym).fast_info` — market-watch quotes |
  | `execution/live_bar_worker.py:392` | `yf.download(symbols, ...)` — live 3m/15m batch |
  | `universe/store.py:221` | `yf.Ticker(sym).fast_info.market_cap` — universe market caps |

  Each would silently return nothing for `BRK.B` and `BF.B`. Worth a follow-up issue that
  moves `_yahoo_symbol()` into `core/` and applies it at all four sites.
- SRD-EXE-006.005 (per-symbol error isolation) behaved correctly throughout — it is the
  reason the failure was a warning rather than an abort. It also masked how systematic the
  problem was.
