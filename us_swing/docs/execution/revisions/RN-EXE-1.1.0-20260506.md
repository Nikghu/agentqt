# Revision Note — EXE v1.1.0

**Document ID:** RN-EXE-1.1.0-20260506
**Version:** 1.1.0
**Date:** 2026-05-06
**Author:** USSwing
**Status:** Final

---

## Summary

Introduces intraday candle data loading for the Execution tool (Phase 1). Adds `IntradayCandleLoader` — a `QThread` subclass that delta-fetches 1-minute OHLCV bars from IBKR for a screened stock list, validates ≥ 390 candles per derived timeframe (3 m, 5 m, 1 h), and persists all bars via `DatabaseManager`. Idempotent: re-running on an already up-to-date symbol inserts 0 rows.

---

## Functional Objectives Covered

| FO ID | Description |
|---|---|
| FO-EXE-006 | Download and validate intraday OHLCV candles for every screened symbol; delta-aware fetch; ≥ 390 candles per timeframe guaranteed before trading hours. |

---

## SRD IDs Covered

| SRD ID | Priority | Description |
|---|---|---|
| SRD-EXE-006.001 | Must | IntradayCandleLoader QThread entry point + load_progress / load_complete signals |
| SRD-EXE-006.002 | Must | Delta fetch via get_last_timestamp; only bars newer than last stored timestamp fetched |
| SRD-EXE-006.003 | Must | 91-calendar-day / 4-page IBKR paging strategy for first-time and large-gap fetches |
| SRD-EXE-006.004 | Must | Post-fetch validation via HistoricalDataEngine.aggregate_timeframe; ≥ 390 bars per tf |
| SRD-EXE-006.005 | Must | Per-symbol error isolation; WARNING logged; other symbols continue |
| SRD-EXE-006.006 | Should | get_readiness_report — sync DB-only readiness check returning dict[str, SymbolReadiness] |

---

## Modules Created / Modified

| Action | File | MD ID |
|---|---|---|
| Created | `us_swing/src/us_swing/execution/intraday_candle_loader.py` | MD-EXE-006.001.M01 |
| Created | `us_swing/src/us_swing/execution/__init__.py` | — (package marker + public re-exports) |
| Created | `us_swing/tests/execution/test_intraday_candle_loader.py` | — |
| Created | `us_swing/tests/execution/__init__.py` | — |

---

## Test Coverage

- 14 test functions covering all 13 UTCD cases (T01–T13) + ValueError guard for oversized symbol lists
- All tests pass on in-memory SQLite (no DB mocking per project rules)
- `ib_insync.IB` mocked at import boundary for isolation

---

## Design Decisions

- **Fresh `IB()` per QThread run** — avoids ib_insync event-loop conflicts with main Qt loop; `asyncio.run()` owns a clean loop for each run
- **Paging strategy** — 65 trading days ≈ 91 calendar days; IBKR 1 m limit = 30 cal days/request; `ceil(91/30) = 4` pages, newest-first
- **Idempotency** — `DatabaseManager.insert_bars()` uses `INSERT OR IGNORE` / `ON CONFLICT DO NOTHING`; re-fetching an existing window inserts 0 rows
- **load_complete emitted before disconnect** — guarantees signal fires exactly once even if `ib.disconnect()` raises

---

## Known Limitations

- `get_readiness_report` is capped at 500 symbols; callers with larger lists must chunk
- No retry logic for transient IBKR errors; failed symbols are surfaced via `CandleLoadResult.reason` and the caller must re-run
- LTP-based live 3 m candle formation during trading hours is out of scope for Phase 1 (deferred to Phase 2 / FO-EXE-007)
