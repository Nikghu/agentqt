# Revision Note — RN-INF-1.1.0-20260612

**Tool:** INF (+ EXE, GUI wiring)
**Version:** 1.1.0
**Date:** 2026-06-12
**Author:** Claude Opus 4.8 under user direction
**Phase:** Bugfix — ISS-INF-0002 (paper fills used a caller-supplied price, not the live market)

---

## Summary

The paper `SimBroker` filled MARKET orders at the `reference_price` the app
handed it (the latest 3-minute candle close), so a stale/bad candle booked a
wrong paper fill and wrong P&L. The live IBKR broker, by contrast, fills at the
real `avg_fill_price` and ignores the reference. This change makes the simulator
behave like a real broker: it resolves the fill price from an injected live-price
provider, so both paper and live get the fill price *from the broker layer*.

## Behaviour Changes

- `SimBroker(price_provider=...)`: a MARKET order now fills at the provider's
  current live price, overriding the advisory `reference_price`. LIMIT orders
  still fill at `limit_price`.
- Falls back to `reference_price` (then $0) only when no provider is wired or it
  returns a non-positive price — so an offline paper test is unchanged.
- `build_broker(..., price_provider=...)` forwards the provider for paper mode.
- `app_service` feeds the provider from a lock-guarded `_last_tick_price` map
  updated by the live tick stream — the same fresh source the cycle triggers use.

## Code Changes

| File | Change | SRD |
|---|---|---|
| `broker/sim.py` | `PriceProvider` alias; `price_provider` ctor arg; `_with_market_price` overrides reference for MARKET orders | SRD-INF-009.007 |
| `execution/broker_factory.py` | `build_broker` forwards `price_provider` to `SimBroker` | SRD-EXE-015.004 |
| `gui/app_service.py` | `_last_tick_price` (lock-guarded) + `_record_market_price` / `_market_price_for`; injects provider into `build_broker` | SRD-INF-009.007 |

## Acceptance — Status

| Check | Status | Evidence |
|---|---|---|
| MARKET order fills at the provider's live price | ✅ | UT-INF-009.004.M01.T01 |
| Falls back to reference when no live price | ✅ | T02 |
| Non-positive (0.0) provider price falls back | ✅ | T03 |
| LIMIT order ignores provider, uses limit_price | ✅ | T04 |
| No regression to the broker contract suite | ✅ | 20 broker tests pass |

## Tests

| Check | Result |
|---|---|
| `tests/broker/test_broker_contract.py` | 20 passed (4 new) |
| broker + router + cycle + adapter suites | 78 passed, no regressions |
| `ruff` | Clean on `sim.py`, `broker_factory.py`, test file (app_service has pre-existing unrelated debt only) |
| `mypy` | No errors in `sim.py` / `broker_factory.py` |

## Notes / Deviations

- Code review (code-reviewer): `sim.py` PASS; two WARNs fixed — `broker_factory`
  now imports the `PriceProvider` alias instead of re-declaring it, and
  `_last_tick_price` is guarded by a `threading.Lock` (written on the GUI thread,
  read on the engine thread).
- Reusing `reference_price` rather than adding a DTO field keeps every `FillModel`
  unchanged; the field is already documented as advisory.
- INF MD/UTCD never carried explicit rows for the FO-INF-009 broker modules; this
  adds a focused UTCD section for the new behaviour, leaving the broader MD
  backfill as a known separate gap.
- This supersedes the smaller `force_exit_position` reorder considered for
  Finding 2 — the broker-side fix is the correct symmetric design.

---

**Commit:** pending — Refs: SRD-INF-009.007
