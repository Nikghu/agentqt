# Revision Note — RN-INF-1.8.0-20261103

**Tool:** INF
**Version:** 1.8.0
**Date:** 2026-11-03
**Type:** enhancement
**Author:** Claude Opus 5.5 under user direction
**Phase:** IBKR market orders sent as Adaptive algo (SRD-INF-009.008)

---

## Summary

IBKR sent the user a monthly FYI about market orders: a plain MKT order can fill at a poor
price. On the user's request, live IBKR market orders now go out as IBKR Adaptive algo orders
with priority Normal. They still fill promptly but work between the bid and ask, so the
risk of a bad fill is lower.

## The change

| File | Change |
|---|---|
| `broker/ibkr.py` | New `build_ib_order()` helper builds the ib_insync order; MARKET gets `algoStrategy="Adaptive"`, `adaptivePriority=Normal`; LIMIT unchanged; `tif=DAY` kept for both. `IBKRClientGateway._place()` calls it |
| `tests/broker/test_ibkr.py` | **New** — UT-INF-009.005.M01.T01–T02 |

Not changed: the paper broker (`broker/sim.py`), the emergency close-all in
`broker/client.py` (kept plain MKT so it fills fastest), and all GUI order-type settings.

Adaptive works only for SMART-routed US stocks in regular hours. The app sends no
`outsideRth` orders, so this holds today.

## Verification

- `pytest tests/broker tests/execution tests/infrastructure`: all pass (38 + 404)
- `ruff check`: clean on changed files
- `mypy --strict broker/ibkr.py`: no new errors (18 old errors in other files, same before and after)
- Live TWS check pending: place one small market order and confirm TWS shows it as an Adaptive algo order
