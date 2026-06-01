# Revision Note — RN-GUI-1.3.0-20260602

**Tool:** GUI
**Version:** 1.3.0
**Date:** 2026-06-02
**Type:** fix + enhancement
**Author:** Claude Opus 4.8 under user direction
**Phase:** Active Trades lifecycle end-to-end (paper mode) + Active Trades / Strategy Builder UI

---

## Summary

Screenshot-driven session that fixed the full paper-mode Active Trades workflow
(pending → OPEN → live PnL → auto-close → CLOSED) and polished the Active Trades and
Strategy Builder panes. Service-layer support is in RN-EXE-1.17.0-20260602. All
changes are against already-Approved FO-GUI-014 / FO-GUI-004 requirements — **no new
SRDs introduced**.

## Lifecycle Fixes (FO-GUI-014, FO-EXE-011/012/013/014)

| Area | Change |
|---|---|
| Entry | `ActiveCyclesPanel` routes Execute through one injected `execute_executor` (=`AppService.execute_signal`) instead of popping the pending store itself; removed the fabricated optimistic `OPENING` flip; wired `pending_signal_executed → on_pending_removed`. Fixes pending rows stranded in OPENING with no DB cycle. |
| Startup load | `_ActiveCyclesModel.refresh()` now seeds from `open_cycles()` (a `set_scope(None)` no-op previously skipped the initial refresh); added the missing `AppService.viewing_uid` property; USER column always shown. Open trades now persist across restarts. |
| Live PnL + auto-subscribe | `AppService` wires the live tick feed into `TradeCycleService.on_tick` and passes `set_active_symbols` so open-cycle symbols are force-subscribed (ungated by S&P 500, untrimmable). PnL = (LTP − entry) × qty. |
| Auto-close | `AppService` subscribes `ExitTrigger` on the bus and marshals the SELL submit onto the GUI thread via a queued signal (`_auto_exit_requested`) → `force_exit_position(reason)`; the real exit reason (target / hard_sl / trailing_sl) is threaded into `_record_paper_exit`. |
| Manual close | Removed the no-rollback optimistic `CLOSING` flip in `_on_close_clicked`; row state is now driven solely by `CycleClosing` / `CycleClosed`. |
| Trade History | `_record_paper_exit` and `_rehydrate_positions_from_cycles` now emit a `side="SELL"` `TradeRecord` (exit fill → `entry_price`/`entry_time` so the per-order model renders Avg Price / Date & Time). Previously BUY-only. |
| CLOSED-today | `refresh()` merges `closed_between(today-ET-window)`; `on_cycle_closed` flips the row to a muted CLOSED instead of removing; terminal rows show realized PnL / exit price. Dropped on the next ET day. |

## UI / UX

| Area | Change |
|---|---|
| State cell | State pill + per-row action buttons (▶ ✕ / ✎ ■) moved into the STATE column (`_RowActionsDelegate` repurposed onto `Col.STATE`, fixed-width pill, ACTIONS column hidden). |
| Labels / tabs | Removed the duplicate "ACTIVE TRADES" header; bottom tabs restyled to match the Dashboard with icons (`📈 Active Trades`, `🛠 Strategy Builder`); selected tab uses palette `TEXT` (white in VS-dark) instead of `BLUE`. |
| TIME column | Rendered in the Settings → System **Market Timezone** (naive machine-local timestamps converted via `astimezone`); unified cycle (entry) and pending (signal) sources. |
| Play/Stop | Strategy table RUN icon and click-action both derive from the effective `StrategyRunState` (`model.status_for`), so the icon never disagrees with the STATUS badge. |
| Circuit breaker | Promoted to `AppService` (`circuit_breaker_active` property, `circuit_breaker_changed` signal, `set_circuit_breaker`). The toggle + Candle DB diagnostics moved to Settings → System; the ExecutionPanel banner now reacts to the signal. This also activates the previously-dead Active Trades execute-button CB gating. |
| Strategy Builder | Removed "STRATEGY EXECUTOR" label; "+ Add Strategy" moved to the bottom; "#" row-number header on the corner cell. |

## Files Changed

| File | Change |
|---|---|
| `gui/active_cycles_panel.py` | execute_executor wiring, executed→removed signal, STATE-cell delegate (pill + buttons), market-tz provider, always-show USER, startup refresh, fixed pill width |
| `gui/active_cycles_model.py` | startup seed + CLOSED-today merge, terminal-aware realized PnL, market-tz time formatter, STATE no longer full-cell painted |
| `gui/app_service.py` | `viewing_uid` property; tick→`on_tick` + `set_active_symbols`; `ExitTrigger`→queued SELL submit; SELL trade-history rows (runtime + rehydrate); circuit-breaker state/signal/setter; exit-reason passthrough |
| `gui/execution_panel.py` | tab icons + style, removed duplicate label, Play/Stop sync, CB banner via signal, Candle DB/CB moved out, Strategy Builder layout (Add at bottom, "#" header) |
| `gui/settings_panel.py` | Settings → System "Diagnostics" group (Candle DB + Trip/Reset Circuit Breaker); fixed pre-existing ruff nits |

## Traceability

| Artifact | ID |
|---|---|
| FO | FO-GUI-014, FO-GUI-004 |
| SRD | SRD-GUI-014.001–.013, SRD-GUI-004.001 (no text change) |
| MD | MD-GUI-014.001.M01/M02, MD-GUI-004.001.M01 |
| Tests | service-side `UT-EXE-014.007.M02.T01–T03` (RN-EXE-1.17.0); no new GUI UTCD this batch |

## Tests / Checks

| Check | Result |
|---|---|
| `tests/execution/test_trade_cycle_service.py` | Pass (21) |
| Offscreen render smoke (STATE delegate, corner "#") | Pass |
| `ruff` | Clean on all five edited GUI modules (`app_service.py` retains 16 unrelated pre-existing warnings) |

## Deferred / Notes

- GUI UTCD for the new Active Trades behaviours (no `pytest-qt` coverage for
  `ActiveCyclesPanel` exists yet — TODO T4).
- TIME / CLOSED-today are computed at row-build; a Market-Timezone change repaints on
  next refresh, not live.
- A local venv patch to `ib_insync._onSocketDisconnected(msg='')` (ibapi/ib_insync
  version skew) is **not** in the repo.

---

**Commits:** branch `feat/active-trades-lifecycle-2026-06-02`, commit `eb462d95`, PR #28.
