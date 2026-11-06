# Revision Note — RN-MKT-0.9.0-20261106

**Version:** 0.9.0
**Date:** 2026-11-06
**Tool:** MKT (with EXE and GUI)
**Artifact:** FO-MKT-008 (P7) / SRD-MKT-008.001–.006; FO-EXE-021 / SRD-EXE-021.001–.007; SRD-GUI-034.034–.036 (FO-GUI-034 still at Reopen)
**Type:** Feature

---

## Summary

P7 links AI Desk to Execution. Each risk-passed lead pick shows in AI Desk → Command → Approvals waiting with side, entry (idea trigger), stop (idea stop), a 2R target and a Capital Max quantity. Approve adds one pending entry signal under a fixed "AI Desk" strategy in Execution; the user still places the order with Execute. Reject only records the decision. Every decision is a new `trade` row in the append-only `approvals` table. An undecided pick expires at the next NYSE open; a desk signal not executed by that day's close is removed. No AI employee approves a pick or places a trade; only the app process writes trade approvals and signals.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-MKT-008.001.M01 | `us_swing/src/us_swing/core/desk_trades.py` | New: `TradePick`, `DeskTradeSink`, `pick_target()`, `pick_expiry()`, `pick_state()`, `trade_picks()`, `record_trade_decision()`, `approved_picks()`; plain SQL on `desk.db`; imports no `desk`, `market` or `gui` |
| MD-MKT-008.002.M02 | `us_swing/src/us_swing/core/desk_ai_settings.py` | Changed: `trade_target_r` (default 2.0, must be above 0) |
| MD-EXE-021.002.M01 | `us_swing/src/us_swing/execution/desk_signals.py` | New: `AI_DESK_STRATEGY`, `AI_DESK_TYPE`, `desk_signal_id()`, `build_desk_signal()`, `desk_signal_close()` |
| MD-EXE-021.001.M02 | `us_swing/src/us_swing/gui/app_service.py` | Changed: AI Desk strategy row added on start; `desk_pick_qty()`, `send_desk_pick()`, `dismiss_desk_pick()`; 60 s close sweep; re-send of today's approved picks once at start |
| MD-EXE-021.005.M03 | `us_swing/src/us_swing/execution/broker_adapter.py` | Changed: `ai_desk` entries keep the signal's absolute stop and target |
| MD-EXE-021.001.M04 | `us_swing/src/us_swing/execution/strategy_engine/_engine.py` | Changed: `_EXTERNAL_TYPES`; tick loop and candle fan-out skip `ai_desk` strategies |
| MD-GUI-034.034.M24 | `us_swing/src/us_swing/gui/ai_desk_hiring.py` | Changed: `TradePickRow` and pick rows in `approvals_box()` |
| MD-GUI-034.034.M24 | `us_swing/src/us_swing/gui/ai_desk.py`, `gui/main_window.py` | Changed: `AiDeskWorkspace(poller, sink)`; the main window passes the app service |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-MKT-008.001 | Trade picks: lead picks of the latest day with risk verdict pass, trigger and stop from `ideas`. | Implemented |
| SRD-MKT-008.002 | Target = trigger ± `trade_target_r` × R; a pick with a bad stop is not listed. | Implemented |
| SRD-MKT-008.003 | A pick waits until a trade row exists or the next NYSE open passes; state is worked out, never stored. | Implemented |
| SRD-MKT-008.004 | Each decision adds one `trade` approval row with the levels and quantity; a second or late decision is refused. | Implemented |
| SRD-MKT-008.005 | Logic in `core/`; only the app process writes trade approvals. | Implemented |
| SRD-MKT-008.006 | `[AI Desk]` log lines for decisions and expired picks. | Implemented |
| SRD-EXE-021.001 | "AI Desk" strategy row (type `ai_desk`, Positional, auto trade off) added when missing; never evaluated. | Implemented |
| SRD-EXE-021.002 | `send_desk_pick()` adds one ENTRY signal with the pick's direction and levels; id `desk:day:side:symbol`. | Implemented |
| SRD-EXE-021.003 | Quantity from the AI Desk Capital Max; 0 adds no signal and warns. | Implemented |
| SRD-EXE-021.004 | A desk signal not executed by its trading day's close is dismissed. | Implemented |
| SRD-EXE-021.005 | An AI Desk entry exits on the signal's stop and target. | Implemented |
| SRD-EXE-021.006 | Today's approved picks are sent again after a restart, unless pending or already traded. | Implemented |
| SRD-EXE-021.007 | `[AI Desk]` log lines for sent, refused and removed signals. | Implemented |
| SRD-GUI-034.034 | Approvals waiting lists each waiting pick with its levels, quantity, Approve and Reject. | Implemented |
| SRD-GUI-034.035 | Approve sends, then records; Reject only records; a refused send saves nothing. | Implemented |
| SRD-GUI-034.036 | Decided and expired picks drop off on the next show. | Implemented |

---

## Design Decisions

- User answers (2026-11-06): pending signal, Approvals waiting, expire at next open, shorts allowed, one "AI Desk" strategy, Capital Max quantity, 2R target.
- The pick expires at the open, but its signal lives until that day's close, so the user can execute it during the day.
- Pending signals live in memory, so today's approved picks are sent again on app start.
- Approve sends first and saves second; if saving fails the signal is dismissed again.
- Changed from the first DD: Start on AI Desk is not refused, because the Strategies pane saves `run_state` before the engine hears; instead the engine always skips `ai_desk` strategies. MD-EXE-021.001.M04 and UT-EXE-021.001.M04.T01 replace the Start refusal test.
- Quantity uses the router's formula (Capital Max × per-trade % of the effective capital), which equals `size_for_strategy` (SRD-EXE-021.003 wording) at the default per-trade 100%.
- Shorts are allowed, but today the risk check vetoes every short (T124), so none will show until T124 is fixed.

---

## Test Results

- New tests: 18 MKT (`tests/market/test_desk_trades.py`), 18 EXE (`tests/execution/test_desk_signals.py`), 8 GUI (`tests/gui/test_ai_desk_trades.py`); all Pass.
- Coverage: `core/desk_trades.py` 93%, `execution/desk_signals.py` 100%.
- Full suite: 2408 passed, 13 failed, 2 skipped. The 12 old failures (T112) plus `test_slow_empty_answer_is_timeout`, which passes alone (timing under load). No new failure from P7.

---

## Open

- T129: user check in the app after an evening run (Approvals waiting rows, Approve to Execution, Reject, expiry at open).
- SRD-EXE-021.003 says `size_for_strategy`; the user may reopen it to name the router formula.
