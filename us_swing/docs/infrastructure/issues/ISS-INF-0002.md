# Issue Report — ISS-INF-0002

**Tool:** INF (Infrastructure) — broker layer; cross-tool EXE + GUI wiring
**Severity:** High (paper fills booked at a caller-supplied price, not the live market)
**Status:** Resolved
**Date Opened:** 2026-06-12
**Date Resolved:** 2026-06-12
**Reporter:** User (USSwing) — raised during the Finding 2 price investigation
**Resolution:** RN-INF-1.1.0-20260612

---

## Symptom

Paper trades closed at clearly wrong prices (e.g. CL $322.98, MNST $403.69 — far
from those stocks' real prices), producing wrong realized P&L. The live IBKR path
would never book such a value because the broker fills at the real market price.

## Root Cause

In paper mode the `SimBroker` did **not** source the fill price itself. Its
`ImmediateFillModel` filled a MARKET order at `OrderRequest.reference_price` — a
value computed *upstream* by the app (`force_exit_position → get_latest_close`,
the latest 3-minute candle close) and merely echoed back by the simulator.

This is the asymmetry with a real broker:

| | Who sets the fill price? | Uses `reference_price`? |
|---|---|---|
| Live (IBKR) | the broker (`avg_fill_price`) | No — ignored |
| Paper (SimBroker, before) | the app (`get_latest_close`) | Yes — echoed as the fill |

So any stale/bad candle close the app computed went straight into the paper fill
with no independent market check. A real broker would have filled at the live
market price regardless.

## Fix

The simulator now acts like a real broker — it resolves the fill price from a
live market source instead of trusting the caller:

- **INF (SRD-INF-009.007):** `SimBroker` accepts an injectable
  `price_provider(symbol) -> float | None`. For a MARKET order it fills at the
  provider's current live price (overriding the advisory `reference_price` via
  `dataclasses.replace`). LIMIT orders still fill at `limit_price`. Falls back to
  `reference_price` only when the provider is absent or returns a non-positive
  price.
- **EXE (SRD-EXE-015.004):** `build_broker` forwards an optional `price_provider`
  to `SimBroker` (paper only).
- **GUI (`app_service`):** keeps a lock-guarded `_last_tick_price` map fed by the
  live tick stream and injects `_market_price_for` as the provider, so paper
  fills use the freshest live price — the same source the cycle's triggers use.

## Affected Artifacts

| Artifact | Change |
|---|---|
| SRD-INF-009.007 | New (Approved → Implemented) — SimBroker fills at injected live price |
| SRD-EXE-015.004 | Cross-tool note — `build_broker` forwards `price_provider` |
| UT-INF-009.004.M01.T01–T04 | New — provider price used; fall back on None / 0.0; limit ignores provider (all Pass) |
| `broker/sim.py` | `PriceProvider` alias; `price_provider` ctor arg; `_with_market_price` |
| `execution/broker_factory.py` | `price_provider` param forwarded to `SimBroker` |
| `gui/app_service.py` | `_last_tick_price` (lock-guarded) + `_record_market_price` / `_market_price_for`; injects provider |

## Notes / Deviations

- INF MD/UTCD never carried explicit rows for the FO-INF-009 broker modules
  (`sim`/`ibkr`/`broker`) — they were shipped with the contract suite only. This
  fix adds a focused UTCD section for the new behaviour; the broader MD backfill
  remains a known, separate gap.
- Reusing `reference_price` (rather than adding a new DTO field) is deliberate:
  the field is already documented as "advisory… simulated brokers fill at this
  price", and every `FillModel` keeps working unchanged.
- When no live tick feed is running (pure offline paper test), the provider
  returns None and the simulator falls back to the old reference-price behaviour
  — no regression.
- Supersedes the smaller `force_exit_position` reorder that was considered for
  Finding 2; this broker-side fix is the correct, symmetric design.
