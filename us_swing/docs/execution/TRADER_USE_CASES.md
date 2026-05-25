# Trader Use Cases — Execution & Risk Management (EXE)

**Document ID:** EXE-UC  
**Version:** 1.0.0  
**Last Updated:** 2026-05-19  
**Source Reference:** `swing_trading_use_cases.pdf` (May 2026) — 13 canonical trader use cases  
**Purpose:** Living gap-analysis document. Maps every PDF use case to the current plan, records what is fully covered, what is partially covered, and what is missing. Drives future FO additions.

---

## How to Read This Document

| Status | Meaning |
|---|---|
| **Covered** | Requirement is fully addressed by an existing FO + SRD |
| **Partial** | Core idea is in the plan but a specific sub-behaviour is not designed |
| **Gap** | No FO or SRD exists for this behaviour — needs a new or amended FO |

Plan references: `FO.md`, `SRD.md`, `STRATEGY_DESIGN.md` in this directory.

---

## Section 1 — Auto Mode (Fully Automatic Execution Engine)

The system parses strategy conditions, calculates position sizes from available capital, and executes without human confirmation.

---

### UC-01: Standard Ideal Win (Baseline Strategy Cycle)

**Flow:** Provision capital + stock → Auto mode → entry signal fires → position in profit → target exit reached → 100% liquidation → Order Book updated.

| Aspect | Plan Coverage | Evidence |
|---|---|---|
| Capital provisioning + position sizing | **Covered** | FO-EXE-001, SRD-EXE-001.002: `position_size = floor((equity × risk_pct) / (entry − stop))` |
| Auto entry without confirmation | **Covered** | STRATEGY_DESIGN §4 Mode table: Auto → direct to `ExecutionRouter`, no dialog |
| Target exit execution | **Covered** | FO-EXE-002, SRD-EXE-002.003: exit signal → market SELL of full quantity within 1 s |
| Order Book / trade record updated | **Covered** | SRD-EXE-001.004: `TradeRecord` written on submission; SRD-EXE-002.002: exit fills update `trades` with exit price + PnL |

**Verdict: Covered.**

---

### UC-02: Manual Scale-In Modification (Mid-Flight Pyramiding)

**Flow:** Auto entry → position in profit → **user manually adds more shares to the live position** → strategy target exit → system liquidates combined size.

| Aspect | Plan Coverage | Evidence |
|---|---|---|
| Initial auto entry | Covered | See UC-01 |
| User manually adding to an open position | **Gap** | No "Add to Position" action in GUI Execution Panel. `quantity_override` (SRD-EXE-005.005) applies only at initial entry, not to open positions. Monitoring ledger records `SymbolPositionScaled` for system fills (SRD-EXE-009.006) but no user-initiated mid-flight BUY flow exists. |
| Exit liquidates combined (original + added) quantity | Partial | FO-EXE-002 exits by full open quantity, so exit would cover it once scale-in is tracked — but depends on gap above being resolved. |

**Verdict: Gap — Scale-In entry path (manual trigger on live position) is not designed.**

---

### UC-03: System-Driven Scale-In (Automated Layering)

**Flow:** Auto entry → position in profit → **system detects momentum and auto-executes a pre-defined secondary BUY** → strategy target exit → full combined size liquidated → Order Book logs each entry block separately.

| Aspect | Plan Coverage | Evidence |
|---|---|---|
| Initial auto entry | Covered | See UC-01 |
| System detecting scaling criteria | **Gap** | `StrategySignal.action` is `Literal["entry", "exit", "hold"]` (STRATEGY_DESIGN §2). No `"scale_in"` action exists. Strategy `compute()` has no mechanism to signal "add to existing position." |
| Auto-executing secondary BUY at pre-defined size | **Gap** | No scale-in quantity parameter in `StrategyProtocol.Params`. `ExecutionRouter` has no scale-in routing branch. |
| Order Book logs individual entry blocks | Partial | `trades` table can hold multiple rows per symbol. But without scale-in signal routing, the second entry never gets created. |

**Verdict: Gap — `StrategySignal`, `StrategyProtocol.Params`, and `ExecutionRouter` all need scale-in support.**

---

### UC-04: Automated Partial Profit Scaling (Scale-Out Engine)

**Flow:** Auto entry → position in profit → **system hits TP1 → sells 50% automatically → shifts remaining stop to break-even** → remaining shares hit TP2 or trailing stop → final liquidation → Order Book shows layered exit entries.

| Aspect | Plan Coverage | Evidence |
|---|---|---|
| Single target exit | Covered | `StrategySignal.target: float | None` (STRATEGY_DESIGN §2) |
| Multi-target exits (TP1, TP2) | **Gap** | `StrategySignal` has one `target` field only. No `target1`, `target2`, or `targets: list[float]` structure. |
| Partial sell at TP1 (e.g., 50% of position) | **Gap** | No partial exit percentage concept in FO or SRD. `PARTIAL_EXIT` state (SRD-EXE-005.003) handles broker-side partial fills, not strategy-driven partial exits. |
| Shift stop to break-even after TP1 | **Gap** | No stop-update mechanism after a partial exit. Position's `stop_loss` field is set at entry and never modified. |
| Trailing stop on remainder after TP1 | **Gap** | Trailing stop field exists in FO-EXE-005 position data but no update-stop mechanism is designed (see UC-06). |
| Order Book layered exit records | Partial | `trades` table supports multiple rows per position. But without the above, only one exit row is ever created. |

**Verdict: Gap — Requires multi-target exit structure, strategy-driven partial exit action, and stop mutation after TP1.**

---

### UC-05: Absolute Capital Safeguard (Hard Stop-Loss Execution)

**Flow:** Auto entry → market reverses → unrealized loss accumulates → price hits hard stop → **system bypasses trend tracking and market-sells immediately** → scanner resets.

| Aspect | Plan Coverage | Evidence |
|---|---|---|
| Hard stop calculated at entry | Covered | `StrategySignal.stop_loss` set by strategy `compute()` (STRATEGY_DESIGN §2, BOSS EMA example: `stop = swing_low × 0.998`) |
| Immediate market sell when stop breached | Covered | FO-EXE-002: exit signals executed as market orders within 1 s. Strategy fires `action="exit"` when price crosses stop level. |
| Bypasses trend logic | Covered | Strategy `compute()` returns `action="exit"` unconditionally when stop is hit; no other conditions required. Auto mode routes directly to `ExecutionRouter` without any further checks beyond risk validation. |
| Scanner resets for next setup | Covered | `PositionTracker` clears closed position; `MonitoringSession` marks symbol EXITED; next screener run includes fresh candidates. |

**Verdict: Covered.**

---

### UC-06: Trailing Stop Profit Safeguard (Dynamic Lock-In)

**Flow:** Auto entry → position moves significantly into profit → **system dynamically shifts stop-loss boundary upward on each bar** → price peaks and breaks trailing stop → system sells to lock in gains.

| Aspect | Plan Coverage | Evidence |
|---|---|---|
| Trailing stop field on position | Partial | FO-EXE-005 lists `trailing-stop level` as a position field. SRD-EXE-002.002 mentions `trailing-stop triggered` as an exit cause. |
| Dynamic stop update on each bar close | **Gap** | No mechanism to update `trailing_stop_level` on the position after entry. Strategy `compute()` returns a `StrategySignal` but the signal has no `update_stop: float` field. `ExecutionEngine` has no `update_position_stop()` method. |
| Trailing stop as exit trigger | **Gap** | The strategy's `compute()` would need to read the current trailing stop from the position, compare to price, and emit exit — but strategies are position-unaware by design (they only see candle data). The trailing stop update path between the `PositionTracker` and the strategy engine is not designed. |

**Verdict: Gap — Trailing stop data field exists in FO-EXE-005 but the update-on-bar and exit-trigger mechanism is fully absent. Needs a `StrategySignal.update_trailing_stop: float | None` field and a `PositionManager.update_stop()` pathway.**

---

### UC-07: Manual Terminal Override (Emergency Kill Switch)

**Flow:** Position running (any P&L) → **user triggers Panic Close / Kill Switch on main console** → system revokes strategy logic blocks → immediate market exit → Order Book updated with manual override timestamp.

| Aspect | Plan Coverage | Evidence |
|---|---|---|
| GUI emergency button | Covered | SRD-EXE-003.005: GUI emergency button calls `EmergencyShutdown.run('manual')` |
| Immediate market exit of all positions | Covered | SRD-EXE-003.003: `EmergencyShutdown.run()` cancels pending orders, submits market close for all open positions, completes within 60 s |
| Strategy logic suspended | Covered | SRD-EXE-003.004: `circuit_breaker_active = True` blocks all further signal processing |
| Order Book updated with timestamp | Covered | SRD-EXE-001.004: `TradeRecord` includes `entry_time`; exit fills update `trades` row. Shutdown summary written to `logs/shutdown_YYYYMMDD_HHMMSS.log` (SRD-EXE-003.006) |
| Additional: CLI + SIGTERM routes | Covered | SRD-EXE-003.005: all three routes call the same `EmergencyShutdown.run()` |

**Verdict: Covered. Note — the PDF kill switch targets the single active position; our plan closes ALL positions, which is more comprehensive and safer.**

---

## Section 2 — Confirmation Mode (Human-in-the-Loop Gateway)

The system acts as an automated quant analyst, locating setups and structuring risk parameters, but holds order routing until manual approval.

---

### UC-08: Standard Approved Execution Cycle

**Flow:** Manual mode → strategy fires → **Buy Proposal Card rendered** → user approves → position in profit → strategy exit fires → **Exit Proposal Card rendered** → user approves → liquidated → Order Book updated.

| Aspect | Plan Coverage | Evidence |
|---|---|---|
| Buy Proposal Card | Covered | STRATEGY_DESIGN §5: `_SignalRow` with READY badge, entry/stop/target/R:R, Execute BUY button |
| User approval (Approve button) | Covered | STRATEGY_DESIGN §4/§5: Execute BUY → confirmation dialog → Confirm → order routed |
| Exit Proposal Card | Covered | STRATEGY_DESIGN §5: EXIT badge state, button reads "Execute SELL" |
| User approval of exit | Covered | STRATEGY_DESIGN §5: stale confirmation dialog pattern is defined; same pattern applies to EXIT |
| Order Book updated | Covered | SRD-EXE-001.004 (entry), SRD-EXE-002.002 (exit) |

**Verdict: Covered.**

---

### UC-09: Quantitative Setup Rejection

**Flow:** Manual mode → Buy Proposal Card → **user clicks Reject/Dismiss** → proposal purged → capital pool protected → user dismissal logged.

| Aspect | Plan Coverage | Evidence |
|---|---|---|
| Buy Proposal Card rendered | Covered | See UC-08 |
| Reject / Dismiss button on signal card | **Gap** | STRATEGY_DESIGN §5 shows only an Execute BUY button on `_SignalRow`. No explicit Dismiss/Reject button is designed. Signals currently go stale passively when the next bar does not re-confirm; there is no user-initiated dismissal action. |
| Capital pool protected (signal purged) | Partial | Capital was never reserved before the order was submitted, so there is no capital to "free." However, the signal should be removed from the Pending list and the pending count updated. |
| User dismissal logged | **Gap** | No requirement to log a `"User dismissed signal for {symbol}"` audit entry exists in FO or SRD. |

**Verdict: Gap — `_SignalRow` needs a Dismiss button; dismissal should remove the row and log at INFO.**

---

### UC-10: Confirmed Entry with Micro-Adjustments

**Flow:** Manual mode → Buy Proposal Card → **user edits qty or capital allocation inside the card** → user approves → order submitted with modified parameters.

| Aspect | Plan Coverage | Evidence |
|---|---|---|
| Qty spinbox on signal card | Covered | STRATEGY_DESIGN §5: `[25 ↑↓]` qty spinbox shown on `_SignalRow` with "(overridden)" label |
| Modified qty respected on Execute | Covered | SRD-EXE-005.005: `quantity_override` parameter passed to `ExecutionEngine.submit_signal()` |
| Override still passes capital check | Covered | SRD-EXE-005.005: "Override does not bypass risk validation, only position sizing" |
| Order Book records actual submitted qty | Covered | SRD-EXE-001.004: `TradeRecord.quantity` is the submitted quantity |

**Verdict: Covered.**

---

### UC-11: Confirmed Mid-Flight Scale-In Proposal

**Flow:** Manual mode → position live and in profit → **system identifies scaling criteria → renders Scale-In Optimization Proposal Card** → user approves → secondary capital layer added to position → Order Book appends secondary execution.

| Aspect | Plan Coverage | Evidence |
|---|---|---|
| System identifying scale-in criteria | **Gap** | Same gap as UC-03. No `"scale_in"` action in `StrategySignal`. Strategy `compute()` cannot distinguish "first entry" from "add to existing position." |
| Scale-In Proposal Card in Manual mode | **Gap** | No "Scale-In Proposal Card" widget is designed. Current `_SignalRow` is entry-only. |
| Capital for secondary layer validated | **Gap** | `RiskManager.can_enter_new()` (SRD-EXE-005.004) checks capital for new positions; no `can_scale_in()` variant for adding to an existing position. |
| Order Book shows secondary entry as separate row | Partial | `trades` table supports multiple rows per symbol; `SRD-EXE-009.006` (`SymbolPositionScaled`) already models this. Once the routing exists, the data layer is ready. |

**Verdict: Gap — Same root cause as UC-03. Requires scale-in signal action, new proposal card widget, and a `can_scale_in()` capital check.**

---

### UC-12: Confirmed Partial Profit Scaling

**Flow:** Manual mode → position live and in profit → strategy hits TP1 → **system renders Partial Liquidation Proposal Card (e.g., Sell 50%)** → user approves → 50% sold → system updates stop and continues monitoring remainder.

| Aspect | Plan Coverage | Evidence |
|---|---|---|
| TP1 milestone detection | **Gap** | Same gap as UC-04. `StrategySignal.target` is a single float; no TP1 milestone concept. |
| Partial Liquidation Proposal Card | **Gap** | No partial-exit proposal card widget exists. Current EXIT badge + "Execute SELL" always liquidates the full position. |
| User approves partial sell (e.g., 50%) | **Gap** | No `partial_exit_pct` or `partial_exit_qty` field in the execution flow. |
| System updates stop / keeps remainder active | **Gap** | Same stop-mutation gap as UC-04 and UC-06. Position's stop field has no update pathway after a partial exit. |

**Verdict: Gap — Same root cause as UC-04. Needs TP1/TP2 structure, partial exit proposal widget, and stop mutation path.**

---

### UC-13: Strategic Exit Proposal Rejection (Keep Holding)

**Flow:** Manual mode → position live → exit signal fires → **Exit Proposal Card shown** → user clicks "Reject / Keep Holding" → exit order suppressed → **system auto-attaches a trailing stop as safety net**.

| Aspect | Plan Coverage | Evidence |
|---|---|---|
| Exit Proposal Card in Manual mode | Covered | STRATEGY_DESIGN §5: EXIT badge state, "Execute SELL" button |
| Reject / Keep Holding option on exit card | **Gap** | No "Reject" or "Keep Holding" button on the EXIT badge row. Only "Execute SELL" is shown. A dismissed exit currently has no defined behaviour. |
| Exit order suppressed when rejected | **Gap** | No requirement or flow for suppressing a strategy exit in Manual mode while keeping the position open. |
| Auto-attach trailing stop after rejection | **Gap** | No trailing stop attachment logic at all (see UC-06 gap). After rejection, no safety mechanism is defined — position becomes unmanaged. |

**Verdict: Gap — EXIT badge row needs "Keep Holding" button; rejection must auto-attach a trailing stop (which is itself a gap from UC-06).**

---

## Section 3 — Additional User-Action Use Cases

These use cases are not in the PDF but represent normal trader expectations from any professional terminal. They were derived by reasoning through the full position lifecycle — before, during, and after a trade — from the trader's perspective only.

---

### UC-A: Manual Single-Position Close

**Flow:** Position is open (from any strategy or manual entry) → trader clicks **Close** on that specific position row in the Position Monitor → confirmation dialog → system submits market SELL for the exact open quantity → position marked CLOSED → trade recorded.

*This is distinct from UC-07 (kill switch), which closes every open position simultaneously.*

| Aspect | Plan Coverage | Evidence |
|---|---|---|
| Kill-switch closes all positions | Covered | FO-EXE-003, SRD-EXE-003.003 |
| Close button on a single position row | **Gap** | No Position Monitor panel is designed in `STRATEGY_DESIGN.md`. The Execution Panel shows "Auto Executed Today" (read-only) and Pending Signals — neither has a close button tied to an individual open position. |
| Confirmation dialog before single-position close | **Gap** | No such dialog exists; the kill-switch has no confirmation by design (emergency action). A single-close needs one. |
| Trade record updated with manual-close flag | Partial | `trades` table has `trade_origin` column but the routing for a user-initiated single-position close through `ExecutionEngine` is not specified. |

**Verdict: Gap — Requires a Position Monitor panel with per-row Close button and its own confirmation + execution path. New SRD rows needed.**

---

### UC-B: Manual Stop-Loss and Target Adjustment

**Flow:** Trader has an open position → in the Position Monitor, trader edits the stop or target price directly in an inline spinbox → system updates `PositionTracker` with the new values → the new stop/target is used for all future exit decisions on that position.

| Aspect | Plan Coverage | Evidence |
|---|---|---|
| Stop/target stored on position record | Partial | FO-EXE-005 lists `stop-loss level` and `target price` as position fields. SRD-EXE-002.001 mirrors state to `positions` table. |
| UI mechanism to edit stop/target inline | **Gap** | No editable stop/target fields anywhere in `STRATEGY_DESIGN.md`. Values are set at entry from `StrategySignal` and never modified. |
| Updated stop used for exit trigger | **Gap** | No `PositionManager.update_stop(symbol, new_stop)` method exists. Strategy `compute()` returns its own stop on each bar and would overwrite a manual adjustment unless the engine distinguishes user-overridden from strategy-generated stops. |
| Manual stop tighter than strategy stop should take precedence | **Gap** | No priority rule defined between user-set stop and strategy-generated stop on each bar. |

**Verdict: Gap — Requires editable stop/target fields in Position Monitor, a `PositionManager.update_stop()` method, and a priority rule: user-set stop always takes precedence over strategy-returned stop on the same bar.**

---

### UC-C: Trader-Initiated Manual Entry (No Strategy Signal)

**Flow:** Trader identifies a setup the strategy did not flag → opens a Manual Entry form in the Execution Panel → enters ticker, quantity, stop price, and target price → system validates capital → submits BUY → position created with `trade_origin = 'manual'` → position monitored going forward with manual stop/target.

| Aspect | Plan Coverage | Evidence |
|---|---|---|
| Manual fills recorded in `trades` | Covered | SRD-EXE-009.008: manual-origin fills recorded in `trades` only, no ledger change |
| Capital check before manual entry | Partial | `RiskManager.can_enter_new()` (SRD-EXE-005.004) checks capital but is triggered by strategy signals, not by a manual entry form. The validation logic is reusable. |
| Manual Trade Entry form / UI | **Gap** | No manual entry form exists in `STRATEGY_DESIGN.md` or anywhere in the GUI plan. All entries flow through the `StrategyEngine → Pending Signals` path. |
| Position monitored for manual stop/target | **Gap** | Manual positions would need to be monitored against their user-defined stop/target without a strategy compute() call driving the exit. A separate stop-watch path is needed. |

**Verdict: Gap — Requires a Manual Entry form widget, a stop-watch execution path for positions without a strategy, and `RiskManager` reuse for capital validation.**

---

### UC-D: Strategy Mode Switch Mid-Session With Open Positions

**Flow (Auto → Manual):** Strategy is set to Auto; it has opened two positions. Trader switches the strategy to Manual in Settings and saves. From this point: future exit signals for those positions go to Pending Signals instead of auto-executing.

**Flow (Manual → Auto):** Strategy is Manual; two signals are sitting in Pending Signals awaiting user action. Trader switches to Auto. The pending signals execute immediately without confirmation; subsequent signals auto-execute.

**Flow (Any → Disabled):** Strategy disabled mid-session; positions entered under that strategy receive no further exit signals from the strategy engine.

| Aspect | Plan Coverage | Evidence |
|---|---|---|
| Mode stored in DB per strategy | Covered | STRATEGY_DESIGN §4: "Configs written to DB" on Save Changes |
| Mode check per-signal at submission time | Covered | SRD-EXE-004.005: "Mode check must be per-signal, not cached at startup" |
| Behaviour for positions entered under previous mode | **Gap** | STRATEGY_DESIGN §4 says "strategy removed from next evaluation cycle" on Disabled, but does not define what happens to open positions managed by that strategy. A disabled strategy generating no more exit signals would leave open positions unmanaged. |
| Auto → Manual: exit signals now need approval | **Gap** | Undefined. The current mode reference table only defines signal destination at the moment a signal is generated — it does not say whether positions opened in Auto mode inherit manual exit behaviour after a switch. |
| Manual → Auto: pending signals auto-executed | **Gap** | Undefined. Should queued pending signals auto-fire or be purged when switching to Auto? |

**Verdict: Gap — Three mode-switch edge cases need explicit rules. Most critical: Disabled-with-open-positions must either auto-close those positions or attach a trailing stop as safety net.**

---

### UC-E: Pre-Market Session Readiness Check

**Flow:** Before 09:30 ET, trader opens the terminal and wants a single view confirming: which stocks passed screening, whether candles are loaded, which strategies are active and in what mode, how much capital is available today, and whether the circuit breaker is reset.

| Aspect | Plan Coverage | Evidence |
|---|---|---|
| Screened stocks visible | Covered | `_FilteredStocksPane` shows today's screener results |
| Candle readiness per stock | Covered | SRD-EXE-006.009: Candles column (`✓ / ⟳ / —`) in `_FilteredStocksPane` |
| Capital available display | Covered | FO-EXE-005: "GUI shall display: total equity, capital in use, capital available, max allocation limit" |
| Strategy mode per strategy | Covered | STRATEGY_DESIGN §4: Settings → Strategies tab shows current mode per card |
| Circuit breaker status | **Gap** | FO-EXE-003 triggers a CRITICAL log but there is no GUI indicator showing whether the circuit breaker fired today or whether trading is available. Trader cannot see this without reading the logs. |
| Consolidated pre-market readiness indicator | **Gap** | No single "Ready to Trade / Not Ready" summary widget that combines candle status, circuit breaker status, and capital availability into one actionable indicator. |

**Verdict: Partial — Individual pieces exist but circuit breaker status display and a consolidated readiness indicator are missing.**

---

### UC-G: Per-Position Exit Configuration After Entry

**Flow:** Trader enters a position → in the Position Monitor, clicks [▼] to expand the exit configuration row for that position → configures Fixed SL, enables/adjusts Trailing Stop, and optionally overrides the strategy exit mode for this specific position → all three exit paths are now live and independent.

*This use case is the entry point for the price-level exit paths. It is the action that separates "I have a position" from "my position is fully managed."*

| Aspect | Plan Coverage | Evidence |
|---|---|---|
| Fixed SL stored on position at entry | Covered | `StrategySignal.stop_loss` passed through to `PositionTracker` on fill |
| Fixed SL editable after entry | Covered | UC-B / GAP-09 — editable stop spinbox in Position Monitor |
| Trailing stop enable/configure per position | **Gap** | `PositionExitMonitor` not yet in plan; no `trailing_enabled`, `trail_mode`, `trail_offset` fields on `OpenPosition` |
| Trailing stop updates on each tick (not bar) | **Gap** | Current system has no tick-level stop monitor. `StrategyEngine` fires on 3m bar closes only. A gap-down between bars would not be caught until the next bar. |
| PositionExitMonitor bypasses strategy mode | **Gap** | No component exists that watches `tick_price` per open position and fires direct to `ExecutionRouter`. |
| Strategy exit override per position | **Gap** | Strategy mode is global per strategy card. No per-position override to force "send strategy exit to Pending" for an individual trade while the strategy itself is in Auto. |
| Effective stop display (fixed vs. trailing indicator) | **Gap** | Position Monitor column currently shows raw stop value. No 🔒/📍 indicator to distinguish fixed from trailing. |

**Verdict: Gap — The tick-level price monitor is the most critical missing component. Without `PositionExitMonitor`, Fixed SL protection only fires when the strategy's next `compute()` evaluates — up to 3 minutes late. This is unsafe.**

---

### UC-F: Max Concurrent Positions Count Limit

**Flow:** Trader configures a hard cap of N concurrent open positions (e.g. 3). Even if sufficient capital is available, a 4th entry signal is rejected. This is a count-based guard distinct from the capital-percentage guard.

| Aspect | Plan Coverage | Evidence |
|---|---|---|
| Capital allocation cap (%) | Covered | SRD-EXE-005.004: `can_enter_new()` rejects if `sum(open_position_values) > max_allocation_pct × equity` |
| Count-based position cap | **Gap** | `RiskManager` has no `max_concurrent_positions: int` parameter. No count check exists anywhere in FO or SRD. A trader with a large account could have 50 open positions at 1% risk each and the system would allow all 50 — correct by capital rules but impractical for manual oversight. |
| GUI display of position count vs. cap | **Gap** | No "X of N positions open" indicator in the Execution Panel or Position Monitor. |

**Verdict: Gap — `RiskManager` needs a `max_concurrent_positions` config field and a count check in `can_enter_new()`. A counter indicator needed in the GUI.**

---

## Gap Summary

| Gap ID | Description | Affects UCs | Priority | Required New FO? |
|---|---|---|---|---|
| **GAP-01** | Scale-In signal action — `StrategySignal.action = "scale_in"` + `ExecutionRouter` routing | UC-02, UC-03, UC-11 | High | Yes — new FO-EXE-012 |
| **GAP-02** | Multi-target exits — `TargetLevel` list in `StrategySignal` + partial exit routing + stop-after-TP mutation | UC-04, UC-12 | High | Yes — amend FO-EXE-001/002 |
| **GAP-03** | `PositionExitMonitor` — tick-level price watch for Fixed SL and Trailing SL; bypasses strategy mode; fires direct to `ExecutionRouter`. `OpenPosition` needs `trailing_enabled`, `trail_mode`, `trail_offset`, `trailing_stop_level`, `highest_price_since_entry` fields. | UC-06, UC-13, UC-G | **Critical** | Yes — new FO-EXE-011 |
| **GAP-04** | Dismiss/Reject button on Pending Signal card + INFO log for user dismissal | UC-09 | Medium | No — new SRD-EXE row + STRATEGY_DESIGN §5 |
| **GAP-05** | Exit rejection ("Keep Holding") on EXIT badge row + auto-attach trailing stop after rejection | UC-13 | Medium | No — new SRD-EXE row + STRATEGY_DESIGN §5; depends on GAP-03 |
| **GAP-06** | Scale-In Proposal Card widget for Manual mode | UC-11 | High | No — STRATEGY_DESIGN §5 + new SRD-EXE row; depends on GAP-01 |
| **GAP-07** | Partial Liquidation Proposal Card widget for Manual mode | UC-12 | High | No — STRATEGY_DESIGN §5 + new SRD-EXE row; depends on GAP-02 |
| **GAP-08** | Position Monitor panel — per-row manual Close button + single-position execution path | UC-A | High | Yes — new FO or amend FO-EXE-002 |
| **GAP-09** | Inline editable stop/target on open positions + `update_stop()` method + user-override priority rule | UC-B | High | Yes — amend FO-EXE-002/005 |
| **GAP-10** | Manual Trade Entry form (no strategy signal) + stop-watch handled by `PositionExitMonitor` (GAP-03) | UC-C | Medium | Yes — new FO-EXE-013 |
| **GAP-11** | Mode-switch behaviour with open positions: Auto→Manual, Manual→Auto, any→Disabled edge cases | UC-D | High | No — STRATEGY_DESIGN §4 + new SRD-EXE rows |
| **GAP-12** | Max concurrent positions count cap in `RiskManager` + GUI counter indicator | UC-F | Medium | No — amend SRD-EXE-001/005 |
| **GAP-13** | Circuit breaker status display in GUI + consolidated pre-market readiness indicator | UC-E | Low | No — new SRD-EXE row + GUI SRD row |

---

## What the Current Plan Fully Supports

| Capability | PDF UCs | Key FO/SRD |
|---|---|---|
| Auto entry with risk-based position sizing | UC-01 | FO-EXE-001, SRD-EXE-001.002 |
| Hard stop-loss immediate market exit | UC-05 | FO-EXE-002, SRD-EXE-002.003 |
| Emergency kill switch — all positions (GUI + CLI + SIGTERM) | UC-07 | FO-EXE-003, SRD-EXE-003.005 |
| Manual mode Buy Proposal Card + Approve | UC-08 | STRATEGY_DESIGN §5, SRD-EXE-005.005 |
| Manual mode qty micro-adjustment before execution | UC-10 | SRD-EXE-005.005 |
| Manual mode Exit Proposal Card + Approve | UC-08 | STRATEGY_DESIGN §5 EXIT badge |
| Signal staleness (STALE badge + Force Execute with warning) | — | STRATEGY_DESIGN §5 Step 5 |
| Daily loss circuit breaker (auto close all + halt) | — | FO-EXE-003, SRD-EXE-003.001–003 |
| Capital availability check before each entry | UC-E (partial) | FO-EXE-005, SRD-EXE-005.004 |
| Paper trading mode (identical logic, no real orders) | — | FO-EXE-004, SRD-EXE-004.001–004 |
| Position state machine (NEW → OPEN → CLOSED) | — | FO-EXE-005, SRD-EXE-005.001–003 |
| Candle readiness display per stock (pre-market) | UC-E (partial) | SRD-EXE-006.009 |
| Multi-user capital isolation | — | SRD-EXE-005.004 |

---

## Recommended Next Steps

Listed in dependency order — resolve blocking gaps before their dependents.

**Tier 1 — Foundational (everything else builds on these):**

1. **GAP-03 — CRITICAL FIRST** — `PositionExitMonitor`: tick-level price watcher for Fixed SL and Trailing SL. New FO-EXE-011. New file `execution/position_exit_monitor.py`. Adds `trailing_enabled`, `trail_mode`, `trail_offset`, `trailing_stop_level`, `highest_price_since_entry` to `OpenPosition`. Subscribes to `LiveTickWorker.tick_price`. Fires `ExecutionEngine.exit_position()` directly — no mode check, no dialog. This is the most critical safety component: without it, stop-losses only protect at bar close (up to 3 minutes late). Unblocks GAP-05, GAP-09, UC-C (manual positions), and UC-G.

2. **GAP-09** — Inline stop/target editing in Position Monitor. Amend FO-EXE-002/005. User-set stop fed into `PositionExitMonitor`'s effective stop calculation. Priority rule: user-edited stop always overrides strategy-returned stop on the same bar.

3. **GAP-11** — Mode-switch edge case rules (Auto→Manual, Manual→Auto, Disabled with open positions). Already added to STRATEGY_DESIGN §4. New SRD-EXE rows needed. Low implementation cost, high safety value.

**Tier 2 — New Signal Actions (strategy protocol changes):**

4. **GAP-01** — Scale-in signal action. New FO-EXE-011. Add `"scale_in"` to `StrategySignal.action` and `scale_in_qty_pct`. Add `can_scale_in()` to `RiskManager`. Add scale-in routing branch to `ExecutionRouter`.

5. **GAP-02** — Multi-target exits. Add `TargetLevel` dataclass and `targets: list[TargetLevel]` to `StrategySignal`. Amend `ExecutionEngine` to track which targets have been hit and apply `stop_after` after each TP.

**Tier 3 — GUI Cards (depend on Tier 2):**

6. **GAP-04** — Dismiss button on `_SignalRow`. Small change; one new SRD-EXE row.

7. **GAP-05** — "Keep Holding" button on EXIT badge row + auto-attach trailing stop. Depends on GAP-03.

8. **GAP-06** — Scale-In Proposal Card widget. Depends on GAP-01.

9. **GAP-07** — Partial Liquidation Proposal Card widget. Depends on GAP-02.

**Tier 4 — New Panels and Controls:**

10. **GAP-08** — Position Monitor panel with per-row Close button. New FO or amend FO-EXE-002. New `ExecutionEngine.close_position(symbol)` method.

11. **GAP-10** — Manual Trade Entry form. New FO-EXE-012. Capital validation reuses `RiskManager`. Stop-watch path for positions without a driving strategy.

12. **GAP-12** — Max concurrent positions count cap. Amend `RiskManager` + add `max_concurrent_positions` to `SystemConfig`. Low complexity.

13. **GAP-13** — Circuit breaker status + pre-market readiness indicator. GUI-only change; low risk.
