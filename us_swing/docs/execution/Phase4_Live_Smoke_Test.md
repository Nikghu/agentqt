# Phase 4 — Live TWS-Paper Smoke Test (runbook)

**Status:** NOT RUN — deferred by the user on 2026-08-27
**Account:** DU7078110 (IBKR paper) · `127.0.0.1:7497`
**Gate:** T15 audit is green (`T15_Record_Resolution_Audit.md`), so this is cleared to run
**Rules:** 1 share per order · manual execution only · auto-trade stays OFF

Phases 0–4 are all merged. Everything below is provable only against a real TWS —
mapping, reject feedback, rollback and the liveness gate already have unit coverage.

---

## Before you start

1. **TWS** — logged into the paper account, port 7497, API enabled, paper-trading
   disclaimer accepted.
2. **App** — Settings → Users → set the user's mode to **live**, accept the warning.
3. **Restart the app.** The broker is built once at startup; a mode change does
   nothing until you restart.
4. Launch from source: `python us_swing/run_gui.py`
5. Tail the log: `tail -f ~/.usswing/logs/us_swing_<today>.log`

> **Multi-user caveat:** `app_service.py:1307` builds the broker from
> `self._users[0].mode` — the **first** user, not the active one. With a single
> account they are the same. If more users are ever added, the live one must be
> first or the broker silently builds in paper mode.

---

## Step 1 — confirm live routing engaged

Look for, in the file log:

```
[Orders] Live order routing connected to IBKR at 127.0.0.1:7497
```

**Stop if the GUI log panel shows this instead:**

```
[Orders] Live order routing unavailable — orders are simulated, not sent to IBKR: ...
```

That is the SimBroker fallback; nothing after this point would be a real test.

In TWS, **Data → API → Settings** should show a client on **id 15** — distinct
from 14 (ticks), 13 (live), 12 (intraday), 10 (system).

## Step 2 — BUY 1 share

Liquid, cheap symbol. Let a manual strategy raise a pending entry, set quantity
to **1**, execute. Watch for acceptance → Active Trades OPEN row → fill → cycle
opens.

Verify the ledger tagging (this is what Phase 2 fixed):

```sql
select trade_id, symbol, side, mode, order_state, filled_quantity
from trades order by rowid desc limit 5;
```

against `~/.usswing/candles.db`. **`mode` must read `live`.** If it says `paper`,
live routing did not engage — go back to step 1.

Cross-check price and quantity against TWS's own Trades panel.

## Step 3 — SELL it back

Use the **stop button on the Active Trades tab**. That is the routed path.
Phase 0 disabled the Dashboard's Square Off All and Manage actions in live mode;
they now show an explanatory dialog instead of silently doing nothing.

Expect: cycle closes, SELL row written, position clears.

## Step 4 — force a rejection (validates Phases 1 + 3 together)

Place a deliberately oversized BUY, well beyond the paper account's buying power.

TWS rejects with **error 201**, which arrives only via `errorEvent`. Before
Phase 3 nothing listened, and the symbol stuck permanently.

Expect:

```
[Orders] Order rejected — Order rejected - insufficient margin ...
```

**The critical check:** that symbol must be tradeable again immediately. Raise a
fresh signal on it. If it is blocked, `in_flight` did not clear and Phase 1's
rollback failed.

## Step 5 — kill TWS mid-flight

With the app connected, close TWS completely, then try to execute a pending
signal.

Expect `BrokerConnectionError` — *"IBKR order connection is not live — the order
was not sent"* — and the symbol released, not stranded. This is the Phase 4 gate.

Restart TWS and confirm ticks recover on their own (the watchdog from
`RN-GUI-1.4.0-20260826`).

---

## If something goes wrong

Any order that reaches IBKR but does not show correctly in the app: **square it
off in TWS, not in the app.** The app's view is the thing under test — treat TWS
as the source of truth.

To abort: close the app, then flatten anything left open directly in TWS.

## Evidence to capture

```
grep -E "Orders\]|Strategy\]|error" ~/.usswing/logs/us_swing_<today>.log | tail -60
```

plus the `trades` query from step 2.

---

## Known risks

**F4 is closed** (2026-08-27). `execute_signal` now refuses a manual ENTRY on a
stock the strategy already holds, so the single-open-cycle invariant
`SRD-EXE-014.007` assumes is finally enforced on both paths.

Still open, both deferred by the plan itself: dashboard order routing (Phase 5),
reconnect-mid-order resync (Phase 6), startup reconciliation (Phase 8), and
FO-EXE-003 (circuit breaker + emergency shutdown).
