# US Swing Trading System — Current Context

**Document:** CONTEXT.md
**Project:** us_swing
**Last Updated:** 2026-06-04 (Session 59)
**Updated By:** Claude Opus 4.8

---

**Current (Session 60, 2026-06-08):** **Fixed orphaned ENTERED ledger rows in monitoring-session lifecycle (hotfix for FO-EXE-009/010).** Root cause: trade-cycle closes via non-FILLED exit (abort, manual close) did not flip the ledger state, leaving symbols stranded in ENTERED. Observed live for symbol SATS on 2026-06-08. Solution: (1) New `wire_cycle_ledger_projection(bus, command, terminal_event_types, *, clock=None)` factory in `core/monitoring_session/__init__.py` — wires a stateless handler that subscribes to injected terminal trade-cycle events (CycleClosed, CycleAborted) and calls `mark_exited(symbol, now)` on each. (2) `reconcile_preopen()` in `_service.py` now self-heals orphaned ENTERED rows (entered but no open cycle) by calling `mark_exited()` instead of reporting invariant violation — logged as heal warning so user can investigate if unexpected. (3) Wired in `gui/app_service.py` after lifecycle service construction. Tests: UT-EXE-009.002.M02.T17 rewritten (heal instead of report) + 3 new cases T17b–T17d; suite 79 pass. ruff + mypy --strict clean. RN-EXE-1.19.0-20260608 written; TRACE-EXE FO-EXE-009/010 RN + UT columns updated (status kept Implemented — Verified is user-set). **Next:** UTCD backfill for FO-EXE-016 (Session 59 DoD debt); FO-EXE-003 (CircuitBreaker + EmergencyShutdown).

**Previous (Session 58, 2026-06-02):** **Active Trades end-to-end lifecycle + UI polish (paper mode).** Fixed the full pending→OPEN→live-PnL→auto-close→CLOSED flow and reworked the Active Trades / Strategy Builder GUI. Code touched: `gui/{active_cycles_panel,active_cycles_model,execution_panel,settings_panel,app_service}.py`, `execution/paper_broker.py`, `execution/trade_cycle/{_service,_repository,_protocols}.py`, `tests/execution/test_trade_cycle_service.py`. (1) **Entry** — panel routes Execute through a single injected `execute_executor` (=`AppService.execute_signal`) instead of popping the store itself; removed the fabricated optimistic OPENING flip; wired `pending_signal_executed → on_pending_removed`. (2) **Startup load** — model now seeds from `open_cycles()` (the `set_scope(None)` no-op had skipped `refresh()`); added missing `AppService.viewing_uid` property; USER column always shown. (3) **Live PnL + auto-subscribe** — live tick feed wired into `TradeCycleService.on_tick` + `set_active_symbols` callback so open-cycle symbols are force-subscribed (ungated/untrimmable); PnL=(LTP−entry)×qty. (4) **Auto-close** — subscribed `ExitTrigger` → marshaled SELL submit on the GUI thread via a queued signal → `force_exit_position(reason)`; real exit reason threaded through `_record_paper_exit`. (5) **PaperBroker order IDs** seeded from epoch-ms (fixes cross-restart `10001` reuse that made `find_by_exit_order` match a stale cycle and strand CLOSING). (6) **Manual close** — dropped the no-rollback optimistic CLOSING flip (now event-driven). (7) **Trade History** — SELL rows recorded at runtime and on boot rehydration. (8) **SellOrderState gate** — `on_exit_fill`/`close_cycle_by_id` gained `order_state`; PARTIAL holds CLOSING, FILLED finalizes CLOSED (symmetric with the BuyOrderState entry gate); +3 tests `UT-EXE-014.007.M02.T01–T03` (21 pass). (9) **CLOSED-today** rows persist in Active Trades via repo `closed_between` + ET-day bounds + terminal-aware realized PnL. (10) **UI** — state pill + action buttons relocated into the STATE cell (fixed pill width, ACTIONS column hidden); removed duplicate "ACTIVE TRADES" label; bottom tabs restyled with icons (selected uses palette TEXT so VS-dark shows white not blue); TIME column rendered in the Settings→System Market Timezone; Play/Stop icon synced to effective `StrategyRunState` (`status_for`). (11) **Circuit breaker** promoted to `AppService` (`circuit_breaker_active` property + `circuit_breaker_changed` signal + `set_circuit_breaker`); its toggle + Candle DB moved to Settings→System — also activates the previously-dead Active Trades execute-button CB gating. (12) **Strategy Builder** — removed "STRATEGY EXECUTOR" label, Add Strategy moved to bottom, "#" row-number header. TODO **T8** logged (partial-quantity accounting deferred). Patched venv `ib_insync._onSocketDisconnected(msg='')` for local API/lib skew. ruff clean on all edited modules; `app_service.py` retains 16 unrelated pre-existing warnings. **No RN/SRD/TRACE written this session** (rapid iterative GUI/bugfix work) — Revision Note + TRACE sync deferred. **Next:** write RN-EXE/RN-GUI + TRACE sync for this batch; FO-EXE-003 (CircuitBreaker + EmergencyShutdown), now partially seeded by the AppService CB state.

**Prior (Session 57, 2026-05-30):** **Two fixes completed:** (1) **ISS-EXE-0001 — strategy executor candle read-path.** Added SRD-EXE-006.010 + DD-EXE-006.010.D01; implemented aggregate-on-read in `intraday_candle_loader.py` (new `assemble_execution_bars` / `load_execution_frames` / `load_latest_execution_bar`) deriving 3m/15m from `price_1m` via `HistoricalDataEngine.aggregate_timeframe`, merged with live bars. Modified `app_service.py` providers to use cached DB + aggregation engine. UT-EXE-006.001.M01.T14–T16 pass; ruff + mypy clean. RN-EXE-1.5.1-20260530 written; TRACE-EXE updated. (2) **GUI SQUARING_OFF stuck state.** Fixed `_StrategyTablePane._on_run()` in `execution_panel.py` — replaced early return for SQUARING_OFF with a guard forcing state to STOPPED if no open cycles remain. Added UT-GUI-004.001.M01.T06–T07; ruff clean. RN-GUI-1.2.3-20260529 already written; TRACE-GUI updated. **Next:** FO-EXE-003 (CircuitBreaker + EmergencyShutdown) or continue GUI test coverage for active panels.

**Earlier (Session 56, 2026-05-29):** **FO-EXE-014 completion — broker reject/cancel + OPENING-hold + order-state-gated lifecycle.** Implemented the four remaining FO-EXE-014 SRDs (`.005`–`.008`, all set Approved by the user this session) at the **component level**. `.005`/`.006`: `ExecutionEngine.handle_order_reject` (stamps `trades` REJECTED + zero fill + signals cycle abort via a new injected `on_order_failed` callback) and `handle_order_cancel` (CANCELLED + preserves the partial `filled_quantity`); new `IBKRReject`/`IBKRCancel` DTOs in `data/models.py`. `.007`: `TradeCycleService.on_entry_fill` gained an `order_state` arg — `PARTIAL_FILLED` holds the cycle in `OPENING`, `FILLED` opens it (`OPENING→OPEN` publishes `CycleUpdated`); protocol updated to match. `.008`: monitoring `FillEvent` gained optional `order_state`; `on_fill` only flips `MONITORING→ENTERED` / `ENTERED→EXITED` on a fully FILLED order (`None` preserves prior behaviour → all existing callers/tests unaffected; a FILLED BUY completing an earlier partial flips a still-MONITORING row). 10 new UTCD cases; SRD-EXE-014.005–.008 Approved→Implemented; TRACE-EXE 1.10→1.11; RN-EXE-1.16.0-20260529. Also landed the **date-decay test fix** (made the two `history(days=7)` fixtures relative to `date.today()`). Installed `TA-Lib 0.6.8` (prebuilt wheel) to run the EXE suite — this resolves the prior "talib-missing collection errors" but unmasked **12 pre-existing failures** in candle-loader / tick-worker / strategy-evaluator tests (verified failing identically on a stashed clean HEAD — unrelated). ruff + mypy --strict clean on the 6 changed source modules. **FO-EXE-014 is now fully Implemented.** **Deferred → FO-EXE-003:** engine `handle_order_fill` PARTIAL-vs-FILLED computation (feeds `.004`'s trades-row, not `on_entry_fill`) + `app_service` production wiring (routing live reject/cancel into the handlers, feeding `on_fill` a real `order_state`, and the `on_order_failed → on_entry_failed(cycle_id)` map). **Next:** FO-EXE-003 (CircuitBreaker + EmergencyShutdown), which carries that wiring.

**Earlier (Phase 4):** Final_Execution.md **Phase 4 — LifecycleState internalisation** (Session 55, 2026-05-29) — final phase of the state-enum consolidation. Retired the duplicate `LifecycleState(str, Enum)` in `core/monitoring_session/_enums.py`; `ExecutionEnums.LifecycleState` is now the single source of truth. `_repository.py` (via module-local `_LifecycleState` alias) and `_dto.py` reference it directly; `__init__.py` re-exports it (kept in `__all__`), so the public import path and the `MonitoringSessionRow` DTO are unchanged. Resolved an unforeseen Qt-free conflict (SRD-EXE-009.012 mandates `core/monitoring_session/` stay Qt-free): `execution/__init__.py` now lazily loads its two PyQt6 QThread workers via PEP 562 `__getattr__`, so `import us_swing.execution` stays Qt-free and core can import `ExecutionEnums` without dragging PyQt6 into the headless layer — near-zero blast radius (`app_service.py` already imports the workers from their submodules). SRD-EXE-009.012 cycled Reopen→Implemented (text unchanged). New test UT-EXE-009.002.M02.T22 (ENTERED ledger set == open system position set across an enter/enter/exit fill sequence); Qt-free runtime proof added; ruff + mypy --strict clean on changed files. RN-EXE-1.15.0-20260529 written; TRACE-EXE 1.9→1.10. **State-enum consolidation plan (Phases 0–4) COMPLETE.** Pre-existing date-decay test failures (`fetch_history days=7` vs 2026-05-14 fixtures) + `talib`-missing collection errors persist, unrelated to Phase 4 (verified failing on clean HEAD; also recorded in RN-EXE-1.14.0). **Deferred:** SRD-EXE-014.008 (`on_fill` consuming a typed `order_state` parameter) — coupled with the deferred broker reject/cancel paths (SRD-EXE-014.005/.006) under FO-EXE-001. **Next:** FO-EXE-003 (CircuitBreaker + EmergencyShutdown), which also carries the deferred SRD-EXE-014 wiring.

**Earlier:** Active Trades panel Phase-2 fixes (Session 54, 2026-05-27) — Five user-reported defects from screenshot review. Added `TradeSignal.user_id` (SRD-EXE-011.020, schema_version 1→2) wired through `_router._build_entry_signal` + every EXIT site via `user_id_provider` injected by `AppService` (= `lambda: self._active_uid`). Active Cycles model gained a `#` row-number column (Col index 0; all subsequent indices shifted by +1) and a `DISMISSED` state colour. `_row_from_pending` now propagates `signal.user_id` and defaults qty to 1; USER cell resolves to logged-in display name via `_lookup_user_name`. `_build_entry_signal` now sets `qty_recommended=1` for non-zero testing minimum. `PendingSignalStore.dismiss()` / `execute()` emit new dedicated `pending_signal_dismissed` / `pending_signal_executed` Qt signals instead of `pending_signal_removed`, so the row stays visible with state transitioned in-place (DISMISSED / OPENING) rather than disappearing. `_RowActionsDelegate` redrawn with 26×22 icon-glyph buttons (▶ ✕ ✎ ■) matching the strategy table's Delete/Play/Reset style; Actions column fixed to 88 px and NUM column to 32 px via `setSectionResizeMode(Fixed)`. RN-EXE-1.10.0-20260527 written; SRD-EXE bumped 1.8→1.10; TRACE-EXE 1.7→1.8; TRACE-GUI 1.5→1.6. 3 new router tests appended (UT-EXE-011.001.M04.T18–T20). **Next:** continue FO-EXE-003 (CircuitBreaker + EmergencyShutdown) — risk controls layer.

**Earlier (Session 53):** ISS-SCR-0002 AI Transcript blank-panel fix (Session 53, 2026-05-27) — Fixed regression where the AI Transcript panel rendered visible-but-empty after Stage 3 LLM fallback. `_refresh_transcript_visibility` now honours both clauses of SRD-SCR-014.006 (LLM enabled AND transcript non-empty) via a new `AITranscriptPanel.has_turns()` predicate. `CloudAIScreener._apply_legacy` / `_apply_with_tools` now assign `self.last_transcript` early and append a `system` turn naming the failure cause on every fallback branch (client init, API error, agentic max-turns, JSON parse, empty content). `PresetExecutor._run_stage3` captures `llm.last_transcript` even when `llm.apply()` raises. Added `UT-SCR-003.001.M10.T23` regression test (23/23 executor tests pass). SRD-014.003 + SRD-014.006 marked Implemented in TRACE. ISS-SCR-0002 + RN-SCR-2.1.1-20260527 written.

**Earlier (Session 52):** FO-EXE-011 Rex Count Enforcement (Session 52, 2026-05-27) — Completed per-symbol re-execution counter (`rex_count` enforcement). New `RexCounterRepository` manages sibling SQLite table in `candles.db`; counters track remaining entries per (strategy_id, symbol) across engine restarts. Entry signals gated in `_router.evaluate()` after entry condition fires (drop with `reason='rex_limit'` when counter < 0); decrement in `on_order_fill()` after `StrategyEntered` event. Semantic: `rex_count = N` → N+1 total entries allowed (default N=0 → exactly 1 entry). GUI: Reset Strategy icon per row in strategy table with confirmation dialog; new Rex column on Active Cycles panel showing live counter (refreshed via `StrategyEntered` event). All 25 rex tests pass (8 repository unit + 7 router integration). RN-EXE-1.9.0-20260527 written. Two memory files updated: `feature_rex_count_enforcement.md` → Implemented, and `feature_active_trades_panel_rollout.md` (NEW) with 5-step rollout plan + pre-rollout gaps documented. **Next:** FO-EXE-003 (CircuitBreaker + EmergencyShutdown) — risk controls layer, or GUI test coverage for FO-GUI-004/014; Active Cycles panel rollout deferred pending gap resolution.

**FO-EXE-009 + FO-EXE-010 — COMPLETE (Session 44, 2026-05-18):**
- 65 pass / 2 skip; skips are `UT-EXE-001.001.M02.T08/T09`, blocked on FO-EXE-001/002.
- Source fix during test phase: reconciler now adds per-symbol `ReconcileError(...,"invariant_violation",...)` per SRD-EXE-010.003 (was log-only).
- Branch `feature/fo-exe-009-monitoring-session` pushed; 3 commits (`ca1d0db0` foundation, `69dd20c7` tests+fix, `add16c21` doc-flip+RN); PR #9 open.
- Deferred: on-fill seam (blocked), `09:15 ET` cron, `gui/lifecycle_bridge.py`.

**FO-EXE-009 + FO-EXE-010 — Intraday Monitoring Session Lifecycle — IN PROGRESS (Session 43, 2026-05-17):**
- New package `src/us_swing/core/monitoring_session/` (8 files): `_enums.py`, `_dto.py`, `_protocols.py`, `_events.py`, `_repository.py`, `_service.py`, `_scheduler.py`, `__init__.py`
- New schema: `monitoring_session` ledger table keyed `(session_date, symbol)`; new columns `trade_origin` + `monitoring_session_date` on `trades`; `origin` + `anchor_session_date` on `positions`; idempotent `migrate_lifecycle_columns(engine)` wired into `create_schema()` in `db/schema.py`
- Cross-tool service: CQRS-lite Protocols (`MonitoringQuery` / `MonitoringCommand` / `MonitoringEventBus`), 7-event sealed union, versioned frozen DTOs (`KeepSet`, `ReconcileReport`, `FillEvent`, `MonitoringSessionRow`, `InvariantReport`, `PositionSnapshot`, `ReconcileError`), `build_default_service` factory; public surface enforced via `__init__.py` only
- Lifecycle state machine handles first-BUY → ENTERED, scale-in/scale-out invariance, full-close → EXITED, manual-fill bypass, and duplicate-filter case; `check_invariant()` reports `{ENTERED ledger} vs {open system positions}` mismatch
- Reconciler: single-flight pre-open job — EOD finalize → keep_set computation → per-symbol atomic eviction across `price_1m/3m/15m` + ledger UPDATE → retry-once on `OperationalError`; idempotent; per-symbol failure isolated
- `gui/app_service.py` patched: lazy-init lifecycle service on first screener-results signal, route through `command.on_screener_results`, feed `keep_set.filtered ∪ carryover` into `_filtered_symbols` / `IntradayCandleLoader` / `LiveBarWorker.set_symbols`; subscribe to `ReconcileCompleted` to push refreshed keep set into running live worker; startup catch-up via `_lifecycle_reconcile_if_due()`
- Code-style passes: ruff clean on new files; mypy --strict clean for `core/monitoring_session/` (only pre-existing errors in other modules); smoke script `scripts/_smoke_lifecycle.py` validates the full Day-T-1 entry → Day-T reconcile → exit flow against in-memory SQLite (B/C evicted, A/D retained, history survives, invariant holds)
- **Deferred to next session:**
  - On-fill seam (`MonitoringCommand.on_fill` call from `ExecutionEngine.handle_order_fill`) — blocked on FO-EXE-001 / FO-EXE-002 implementation
  - Cron registration for `09:15 ET` reconcile trigger — current implementation uses startup-catch-up only; `build_scheduler` accepts a no-op `cron_register` placeholder
  - Pytest translation of UTCD entries (66 cases across 7 unit modules + integration); `tests/exe/test_monitoring_session_*.py` not yet written
  - RN-EXE-1.3.0-20260517 to mark SRD-EXE-009.*/.010.* Implemented and update TRACE Status column

**FO-EXE-008 + FO-GUI-012 — Live Tick Streaming — REFACTORED (Session 46, 2026-05-19):**
- Market Watch refactored to use 4 ETF proxies (SPY/QQQ/DIA/IWM) instead of ^GSPC/^IXIC/^DJI; WatchlistItem model used consistently across all three tick data sources
- New _MarketWatchTab added to dashboard_panel (MD-GUI-012.001.M02) with _MarketWatchModel + table showing symbol, last price, change $, change %
- _MWCell rich-text hover labels added to main_window.py displaying dynamic tooltip on chart hover with ticker + description
- LiveTickWorker.set_contracts() thread-safety fixed: updates now routed through `asyncio.run_coroutine_threadsafe()` to avoid event loop race conditions (FO-EXE-008 refactor)
- Candle DB diagnostics dialog added to execution_panel (query last candle per symbol, highlight stale/missing data)
- Files: 5 modified (`gui/app_service.py`, `gui/dashboard_panel.py`, `gui/main_window.py`, `gui/execution_panel.py`, `execution/live_tick_worker.py`), staged but uncommitted
- Artifacts: TRACE-EXE v1.4.1, TRACE-GUI v1.2.1 updated; RN-EXE-1.2.1-20260519, RN-GUI-1.2.0-20260519 (pending write); tests not yet verified
- Status: Code Refactored — awaiting test verification before commit

**FO-GUI-011 — Candle Chart Viewer — COMPLETE (Session 41, 2026-05-13):**
- "📈 Chart" navigation tab (index 3, before Settings) with symbol/timeframe/bars toolbar
- TradingView Lightweight Charts v5 candlestick + volume histogram (80px) via QWebEngineView
- Symbol dropdown auto-populated from candles.db; auto-refreshes on tab show
- Supports 1d and 1w timeframes; bar-count limit 20–2000 (default 500)
- Auto-reload on timeframe/bars parameter change when chart loaded
- OHLCV crosshair tooltip in header on hover; placeholder state when no data
- Offline JS bundle from `gui/resources/lightweight-charts.standalone.production.js` with CDN fallback
- Files: 1 new source (`gui/chart_panel.py` MD-GUI-011.001.M01), 1 RN (RN-GUI-1.0.0-20260513)
- Status: Implementation complete, RN-GUI-1.0.0-20260513 written; all SRD-GUI-011 requirements Implemented

**FO-EXE-006 — Intraday Candle Loader Phase 1 — COMPLETE (Session 40, 2026-05-06):**
- `IntradayCandleLoader(QThread)` delta-fetches 1 m IBKR bars for screened stock list, validates ≥ 390 candles per timeframe (3 m, 5 m, 1 h), persists via `DatabaseManager`
- Idempotent: re-running on up-to-date symbol inserts 0 rows; failed symbols isolated per-symbol with reason codes
- `CandleLoadResult` and `SymbolReadiness` dataclasses for progress/completion signals and readiness reporting
- Files: 1 new source (`execution/intraday_candle_loader.py` MD-EXE-006.001.M01), 1 new `execution/__init__.py`, 1 test file (`test_intraday_candle_loader.py` 14 tests), 1 RN
- All artifacts updated: FO v1.2.0, SRD v1.2.0 (all SRD-EXE-006 marked Implemented), DD v1.2.0, MD v1.2.0, UTCD v1.2.0 (all tests Pass), TRACE v1.2.0 (FO-EXE-006 Implemented, RN filled)
- Status: RN-EXE-1.1.0-20260506 written; all phases complete

**ISS-SCR-0001 — Edit Preset Dialog Assign Users Persistence — FIXED (Session 39, 2026-05-05):**
- Root cause: `_PresetBuilderDialog._on_save()` called `_build_preset_from_ui()` which reconstructed the entire preset, overwriting `assigned_to` with empty list from `AssignUsersWidget`
- Fix: Added `updates.pop("assigned_to", None)` when `_assign_widget` is not None, preserving the assigned users from the UI widget instead of overwriting
- Files: 1 modified (`screener_panel.py` — 3-line fix in `_on_save`), 1 new issue doc, 1 new RN
- FOs touched: FO-SCR-005 (Preset Management), FO-SCR-007 (GUI Preset Builder)
- Status: All tests pass; issue resolved; ready for next feature

**FO-SCR-011 Phase 1 — AI-Assisted Stock Ranking — COMPLETE (Session 38, 2026-04-25):**
- Single-provider AI ranking (Claude Haiku 4.5) integrated with tool-augmented reasoning
- User-authored natural-language query input in preset builder
- `get_candle_data` tool exposes daily/weekly OHLCV to Claude for on-demand analysis
- Per-symbol reasoning (~50 words) displayed in results table with tooltip
- Full backward compatibility: empty `ai_query` routes to legacy ranking path
- Files: 1 new (`_tool_executor.py`), 5 modified (preset.py, llm_claude.py, executor.py, screener_panel.py), 6 doc files updated
- Tests: 173/173 pass (24 new); all artifact docs updated; RN-SCR-2.1.0-20260425.md written
- SRD-SCR-013.001–008 now Approved; FO-SCR-011 now Approved; ready for Phase 2 multi-provider work
- **Blocked by:** None. Next: Phase 2 provider abstraction + OpenAI integration

**PriceActionScreener (M08) — COMPLETE (Session 37, 2026-04-22):**
- `screener/screeners/price_action.py` — 5 patterns implemented: proximity_52w_high (George & Hwang 2004), volume_breakout (Bulkowski), nr7_compression (Crabel), ema_pullback (AQR momentum), engulfing (Tharavanij 2017)
- Score = matched/enabled patterns; default threshold 0.2; symbols with <2 bars excluded
- Default config: proximity_52w_high + volume_breakout enabled; 3 others opt-in
- Tests: 19 tests in `tests/screener/test_price_action_screener.py`, all pass
- SRD-SCR-002.007, MD M08, UTCD updated; total SCR tests now 129

**Settings Screeners Tab — Removed (Session 36, 2026-04-22):**
- `_ScreenersTab` class deleted from `gui/settings_panel.py`; tab removed from `SettingsPanel.__init__`
- `ScreenerFilter` dataclass deleted from `data/models.py`
- `_DEFAULT_FILTERS` list and `get_screener_filters()` deleted from `gui/app_service.py`
- `_SCREENER_FILTERS` list and `get_screener_filters()` deleted from `gui/_demo.py`
- `ScreenerFilter` removed from `gui/_types.py` re-exports
- SRD-GUI-006.001 updated (tab list now: Users, Strategies, System, Universe, Database)
- SRD-GUI-006.004 marked Verified/Removed with rationale

**Watchlist Tab — Implemented (Session 35, 2026-04-22):**
- `data/models.py` → `WatchlistItem` dataclass (12 fields)
- `gui/app_service.py` → `_WatchlistQuoteWorker`, `watchlist_updated` signal, `add/remove/get_watchlist_items()`, `_refresh_watchlist()`, 30s refresh timer; wired into connect/disconnect
- `gui/dashboard_panel.py` → `_WatchlistModel` (11 cols, color-coded change), `_WatchlistTab` (toolbar + empty state + live refresh), tab "👁 Watchlist" after Trade History; `on_watchlist_add()` now persists to watchlist
- Real-time: 30s yfinance polling when feed is connected; manual ⟳ Refresh button always works; data shows LTP / Chg$ / Chg% / Open / High / Low / Volume / 52W H/L / Mkt Cap

**RS Index Filter — Implemented (Session 34, 2026-04-22):**
- `screener/screeners/indicator.py` → added `BenchmarkDataUnavailableError`, `InsufficientUniverseDataError`; added `_rs_slope()` and `_compute_rs_ranks()` helpers; `apply()` now pre-computes RS ranks once (vectorised via pandas) and applies `rs_index` filter per-symbol; `screen_detailed()` emits `rs_rank` and `rs_slope_up` keys when filter enabled
- `gui/screener_panel.py` → `_INDICATOR_DEFAULTS` gains `rs_index` key (default `enabled=False`, percentile 70, slope_days 63); `_format_indicator_config()` appends `RS≥N% slN` token; `_IndicatorConfigDialog` adds RS Index section (enabled checkbox, min-percentile spinbox, slope-days spinbox); `get_config()` serialises rs_index; both `_SCREENER_DISPLAY` dicts updated to include "RS Index"
- Fully backward-compatible: `enabled=False` by default, existing saved presets unaffected

**RS Index Bug Fix — `BenchmarkDataUnavailableError` (Session 34 addendum):**
- Root cause: `_PresetRunWorker.run()` only fetched bars for universe symbols; SPY was never in the `bars` dict. Additionally, `get_candles_bulk` defaulted to `limit=200` which is below the 252-bar lookback needed for RS rank — all symbols would silently receive rank 50.0.
- Fix in `gui/screener_panel.py` (`_PresetRunWorker.run()`): read `benchmark_symbol` from `get_system_config()`; append it to the fetch list if not already present; raise limit to 300 bars. Benchmark is present in `bars` but excluded from the screened `symbols` list.

**Blocked by:** Nothing

**Benchmark Data (SPY) — Implemented (Session 33, 2026-04-22):**
- `system_store.py` → `SystemConfig.benchmark_symbol: str = "SPY"` added; `load_system_config()` reads it
- `app_service.py` → `_CandleDownloadWorker`: new `_download_benchmark()` method fetches 2Y of 1d + 1w SPY bars via IBKR, stores in existing `price_1d`/`price_1w` tables; called automatically at start of every "full" or "delta" candle download
- SPY now appears in Chart Panel symbol dropdown after first candle download (no other UI changes needed)
- Benchmark download is non-fatal: `symbol_failed` signal emitted on error, main universe loop continues

**RS vs S&P 500 — Requirements Added (Session 33, 2026-04-22):**
- INF SRD: Added SRD-INF-002.006 (`SystemConfig.benchmark_symbol`), SRD-INF-003.008 (`bootstrap_benchmark()`), SRD-INF-003.009 (`update_benchmark()`)
- SCR FO: Added FO-SCR-010 (Relative Strength vs Benchmark Screening)
- SCR SRD: Added Section 12 — 5 new requirements (SRD-SCR-012.001–012.005); total now 78 SRDs, 10 FOs
- SCR MD: Updated M04 (indicator.py) — added RS line, RS rank, `BenchmarkDataUnavailableError`, `InsufficientUniverseDataError`, benchmark deps
- SCR UTCD: Added 8 new test cases (T09–T16) to `test_indicator_screener.py`; total now 121 tests
- **No schema migration required** — SPY can be stored in existing symbol-agnostic `price_1d`/`price_1w` tables
- TRACE.md **not yet updated** — needs updating after implementation

**GUI Screener Details Column — Indicator Config (Session 32, 2026-04-22):**
- `_format_indicator_config()` helper added to `screener_panel.py`; `_build_rows()` prepends `[<config summary>]` to Details when indicator_composite ref has a non-default config stored in the preset

**ANA Implementation — COMPLETE (Session 31, 2026-04-17):**
- 10 source files: `indicators.py`, `candle_builder.py`, `db_persister.py`, `strategies/breakout.py`, `strategies/pullback.py`, `exit_manager.py`, `strategy_engine.py` (+ `StrategyConfig`), `live_engine.py`, `__init__.py`
- 40/40 tests pass across 4 test files (test_indicators, test_candle_builder, test_db_persister, test_strategy_engine)
- 1 UTCD arithmetic error found and corrected: EMA(3) on [10,11,12,13] = 12.125 not 12.375
- Full suite: 203/203 pass — no regressions

**GUI Screener Panel Polish — COMPLETE (Session 30, 2026-04-17):**
- `gui/screener_panel.py` — WYSIWYG preset builder per SRD-SCR-007.002
- New classes: `_GroupWidget` (drag-reorderable composite group card + AND/OR toggle), `_WeightedRow` (per-screener weight spinbox), `_PresetBuilderDialog` (full WYSIWYG builder with live preview pane, composite + weighted stacks, Save / Save As)
- `ScreenerPanel` wired: `_on_new_preset()` → `_PresetBuilderDialog`; right-click context menu (Edit / Duplicate / Delete) on preset list
- `_NewPresetDialog` preserved as legacy fallback (unused)
- Full suite: 163/163 pass — no regressions

**INF Test Suite — COMPLETE (Session 29, 2026-04-17):**
- `tests/infrastructure/` — 42/42 tests pass across 8 modules
- Modules covered: PacingQueue (4), IBKRClient (5), UniverseManager (4), HistoricalDataEngine (5), DatabaseManager (6), Monitoring/Logging/Alerts/Health (5), UserManager (9), DummyProvider (4)
- 2 production bugs found and fixed: `_str_to_dt` stripped timezone (added `.replace(tzinfo=timezone.utc)`); `upsert_universe` used `sa.bindparam` incorrectly (fixed to use `ins.excluded`)
- Full suite: 163/163 pass — no regressions

**SCR Integration Tests — COMPLETE (Session 28, 2026-04-17):**
- `tests/screener/test_integration.py` — 15/15 pass
- Covered: end-to-end execution, composite AND/OR, weighted scoring, v1 migration, same-day overwrite, scheduled mode, LLM ranking (enabled/disabled/timeout), permissions, new user, deletion, concurrent runs, persistence across restart
- Bug fixed: `manager.py` `migrate_v1_presets()` — added `weight=1.0` to ScreenerRef (was silently excluded by weighted executor)
- Full suite: 121/121 pass — no regressions

**GUI Phase 5 — COMPLETE (Session 27, 2026-04-17):**
- `gui/screener_panel.py` rewritten v1 → v2 (preset-based)
- New classes: `_Row` dataclass, `_ResultsModel` (4-col v2), `_PresetRunWorker(QThread)`, `_NewPresetDialog(QDialog)`
- Left pane: preset list (admin + user sections, section headers, type badges [C]/[W])
- Toolbar: Run Now · progress · ← date nav → · mode badge · status · CSV export · Watchlist
- Right pane: sortable results table (Symbol · Score · Matched/Groups · Details)
- Empty state, error state, graceful backend degradation
- `watchlist_add_requested` signal preserved — main_window wiring unaffected
- Full suite: 106/106 pass — no regressions

**SCR Phase 5 — COMPLETE (Session 26, 2026-04-17):**
- `screener/__init__.py` (M15) — registers 6 built-in screeners at import time, exposes `migrate_v1_presets()` convenience function, exports all orchestration + storage + utility classes
- Full suite: 106/106 pass — no regressions

**SCR Phase 4 — COMPLETE (Session 25, 2026-04-17):**
- `screener/manager.py` (M12), `screener/scheduler.py` (M11)
- Tests: 21/21 pass (15 manager + 6 scheduler)
- Full suite: 106/106 pass — no regressions
- Added `apscheduler>=3.10` to `pyproject.toml`; installed apscheduler 3.11.2

**SCR Phase 3 — COMPLETE (Session 24, 2026-04-17):**
- `screener/utils.py` (M14), `screener/storage.py` (M13), `screener/executor.py` (M10)
- Tests: 40/40 pass (8 utils + 12 storage + 20 executor)
- Full suite: 85/85 pass — no regressions

**SCR Phase 2 — COMPLETE (Session 23, 2026-04-17):**
- `screener/screeners/indicator.py` (M04), `ml.py` (M05), `llm_claude.py` (M06), `llm_local.py` (M07), `price_action.py` (M08), `mcp.py` (M09)
- Tests: 27/27 pass (8 indicator + 5 ml + 10 llm_claude + 4 stubs-implicit)
- Also added `tests/__init__.py` + `tests/screener/__init__.py` (required for relative imports)

**SCR Phase 1 — COMPLETE (Session 22, 2026-04-16):**
- `screener/base.py` (M02), `screener/preset.py` (M01), `screener/registry.py` (M03)
- Tests: 18/18 pass (`test_preset.py` 12 + `test_registry.py` 6)
- Test infra created: `tests/conftest.py`, `tests/screener/conftest.py`

**INF unit tests:** COMPLETE — see §0 above.

> **Note (Session 22):** SCR Phase 1 Foundation implemented. 3 modules + 18 tests. All pass.

> **Note (Session 21):** All 6 Screener v2 documentation artifacts updated to v2.0.0 this session.
> FO (9 FOs), SRD (73 requirements, 11 sections), DD (15 designs + pseudocode), MD (15 modules),
> UTCD (113 unit + 15 integration = 128 tests), TRACE (full forward/reverse matrix, all readiness ✅).
> Architecture: 8 planning Q&A decisions locked (preset types, GUI = drag-and-drop WYSIWYG, etc).
> Implementation phase plan saved to memory: screener_v2_decision.md.

> **Note (Session 15):** Candle data sync requirements added this session. Before SCR implementation can begin, SRD-INF-003.001/006/007 and SRD-INF-002.005 need approval. These are new Draft items that extend the INF layer — they must be approved and INF DD/MD/UTCD updated before implementing `sync_candle_data()`.
> **Note (Session 16):** Database Management tab added to SettingsPanel (SRD-GUI-006.011). Implemented: `CandleDbStatus` enum, `CandleDbInfo` dataclass, `_CandleDbStatusWorker`, `_CandleDownloadWorker`, AppService signals/methods, `_DatabaseTab` widget. DB path: `~/.usswing/candles.db`. Download source: yfinance (initial). SRD-GUI-006.011 status: Draft.
> **Note (Session 17):** Candle download source switched yfinance → IBKR. Added: SRD-GUI-006.012 (IBKR connection gate), SRD-GUI-006.013 (checkpoint/resume), SRD-GUI-006.014 (mid-download disconnect handling). `_CandleDownloadWorker` rewritten to use `ib_insync` via `asyncio.run()`, per-symbol checkpoint writes, resume verification of last 5 symbols. New signal `candle_download_paused`. `_DatabaseTab` updated: IBKR gate dialog, `_apply_checkpoint_state()` for "▶ Resume" button, `_on_paused()` slot. All files pass py_compile.
> **Note (Session 18):** Three runtime bugs fixed: (1) `SystemConfig` missing `ibkr_system_client_id` field — added with default 10; (2) IBKR duration-string rules — durations >365d or >52w must use `Y` unit; (3) dot-in-symbol IBKR quirk — `BRK.B`→`BRK B`, `BF.B`→`BF B`. Per-symbol failure tracking added: FO-GUI-010 + SRD-GUI-006.015/016 written; `_CandleDownloadWorker` emits `symbol_failed(symbol, reason)`; `AppService` accumulates failures, persists to `~/.usswing/candle_failed_symbols.json`, exposes `get/has/clear_failed_symbols()`; `_DatabaseTab` shows live fail counter + "⚠ Download Discrepancies" panel + "🔧 Fix Discrepancies" button for targeted retry.
> **Note (Session 19):** Universe tab candle coverage columns added. `AppService.get_candle_symbol_coverage()` (sync GROUP BY query on `price_1d`) and `get_last_trading_day()` added. `_build_universe_html()` extended with `coverage` + `last_trading_day` params; two new JS columns — "DB" (✔/⚠/✘ icon) and "Last Updated" (YYYY-MM-DD date) — colour-coded green/amber/red. Rows with stale or missing data highlighted with amber/red background tint. `_UniverseTab._load_from_cache()` calls new methods; also connected to `candle_db_status_changed` so table auto-refreshes after any DB activity. `requirements.md` §5 updated with spec.
> **Note (Session 20):** Candle Chart Viewer implemented. New "📈 Chart" tab added as the 4th main nav tab. `CandleChartPanel` in `chart_panel.py` uses TradingView Lightweight Charts v5 (Apache 2.0, bundled at `gui/resources/lightweight-charts.standalone.production.js`). `AppService.get_candle_symbols()` and `get_candles_for_symbol(symbol, timeframe, limit)` added. Chart renders candlestick + synced volume histogram. Crosshair tooltip shows OHLCV. Symbol list auto-refreshes on tab show. `requirements.md` §32 added. Main nav expanded from 4 to 5 tabs.

---

## 1. Project Phase

**Phase:** GUI — AppService Migration Complete; Feed Connection Management Added
**Active Tools:** INF / SCR / ANA / EXE / GUI / MCP — all documentation complete and aligned
**GUI Status:** Full PyQt6 prototype running in paper mode (no demo data); Connect/Disconnect feed toggle in title bar; ALL GUI imports clean
**Next Step:** Write INF test suite (38 tests per UTCD); then begin SCR module implementation

---

## 2. Artifact Status

### Infrastructure (INF)

| Artifact | File | Status | Notes |
|---|---|---|---|
| FO | `docs/infrastructure/FO.md` | Draft v1.3.0 | Added: FO-INF-002 candle metadata; FO-INF-003 2-year history + candle sync |
| SRD | `docs/infrastructure/SRD.md` | Draft v1.4.0 | Added: SRD-INF-002.005 (UniverseRecord candle fields); SRD-INF-003.001 updated (2Y); SRD-INF-003.006/007 (candle metadata update, AppService.sync_candle_data); SRD-INF-004.001 updated (universe schema) |
| DD | `docs/infrastructure/DD.md` | Approved v1.1.0 | |
| MD | `docs/infrastructure/MD.md` | Approved v1.1.0 | |
| UTCD | `docs/infrastructure/UTCD.md` | Approved v1.1.0 | 38 tests specified; not yet written |
| TRACE | `docs/infrastructure/TRACE.md` | Draft — needs Implemented status update | |

### INF Implementation (src/us_swing/)

| Module | File | Status |
|---|---|---|
| Exceptions | `exceptions.py` | ✅ Implemented |
| Config | `config/settings.py` + `config/__init__.py` | ✅ Implemented |
| Domain models | `data/models.py` | ✅ Implemented — single source of truth |
| DB schema | `db/schema.py` | ✅ Implemented |
| DB manager | `db/manager.py` + `db/__init__.py` | ✅ Implemented |
| Pacing | `broker/pacing.py` | ✅ Implemented |
| IBKR client | `broker/client.py` + `broker/__init__.py` | ✅ Implemented |
| User manager | `user/manager.py` + `user/__init__.py` | ✅ Implemented |
| Universe manager | `universe/manager.py` + `universe/__init__.py` | ✅ Implemented |
| Data providers | `data/providers/*.py` | ✅ Implemented (protocol, ibkr, dummy) |
| Data engine | `data/engine.py` + `data/__init__.py` | ✅ Implemented |
| Monitoring | `monitoring/logging_setup.py` + `alerts.py` + `health.py` | ✅ Implemented |
| CLI | `__main__.py` (health subcommand added) | ✅ Updated |

### GUI Duplicate Removal

| File | Change | Status |
|---|---|---|
| `gui/_types.py` | Rewritten as re-export shim from `data/models.py` | ✅ Done |
| `gui/_demo.py` | Updated UserProfile/OpenPosition/TradeRecord/TradeSignal to canonical models | ✅ Done |
| `gui/settings_panel.py` | Updated to `user.risk_config.*` nested access; new UserProfile construction | ✅ Done |
| `gui/user_store.py` | Updated serialization for nested RiskConfig + display_name | ✅ Done |
| `gui/position_table_model.py` | `avg_price` → `average_price` | ✅ Done |

### INF Tests

| Directory | Status |
|---|---|
| `us_swing/tests/infrastructure/` | ✅ COMPLETE — 42 tests written and passing (Session 29) |

### Screener (SCR)

| Artifact | File | Status | Notes |
|---|---|---|---|
| FO | `docs/screener/FO.md` | **Draft v2.0.0** | Complete rewrite — 9 FOs (preset framework, plugins, execution, scheduling, permissions, LLM ranking, GUI, persistence, migration) |
| SRD | `docs/screener/SRD.md` | **Draft v2.0.0** | Complete rewrite — 73 requirements across 11 sections |
| DD | `docs/screener/DD.md` | **Draft v2.0.0** | Complete rewrite — 15 design descriptions with pseudocode |
| MD | `docs/screener/MD.md` | **Draft v2.0.0** | Complete rewrite — 15 modules (M01–M15) |
| UTCD | `docs/screener/UTCD.md` | **Draft v2.0.0** | Complete rewrite — 113 unit + 15 integration = 128 tests |
| TRACE | `docs/screener/TRACE.md` | **Draft v2.0.0** | Complete rewrite — full forward/reverse, all readiness ✅ |

### Analysis / Live Engine (ANA)

| Artifact | File | Status | Notes |
|---|---|---|---|
| FO | `docs/analysis/FO.md` | Draft v1.1.0 | 2 FOs |
| SRD | `docs/analysis/SRD.md` | Draft v1.1.0 | 19 requirements across 3 sections |
| DD | `docs/analysis/DD.md` | Draft v1.1.0 | — |
| MD | `docs/analysis/MD.md` | Draft v1.1.0 | 8 modules |
| UTCD | `docs/analysis/UTCD.md` | Draft v1.1.0 | 28 tests (+ 12 extras added in impl) |
| TRACE | `docs/analysis/TRACE.md` | Draft v1.1.0 | Needs Implemented update |

### ANA Implementation (src/us_swing/analysis/)

| Module | File | Status |
|---|---|---|
| Indicators | `analysis/indicators.py` | ✅ Implemented |
| CandleBuilder | `analysis/candle_builder.py` | ✅ Implemented |
| DatabasePersister | `analysis/db_persister.py` | ✅ Implemented |
| BreakoutStrategy | `analysis/strategies/breakout.py` | ✅ Implemented |
| PullbackStrategy | `analysis/strategies/pullback.py` | ✅ Implemented |
| ExitManager | `analysis/exit_manager.py` | ✅ Implemented |
| StrategyEngine + StrategyConfig | `analysis/strategy_engine.py` | ✅ Implemented |
| LiveEngine | `analysis/live_engine.py` | ✅ Implemented |
| Package init | `analysis/__init__.py` | ✅ Implemented |

### ANA Tests

| Directory | Status |
|---|---|
| `us_swing/tests/analysis/` | ✅ COMPLETE — 40 tests written and passing (Session 31) |

### Execution & Risk (EXE)

| Artifact | File | Status | Notes |
|---|---|---|---|
| FO | `docs/execution/FO.md` | Draft v1.7.0 | FO-EXE-011 (Strategy Engine) and FO-EXE-012 (Trade Cycle Ledger) both Approved; FO-EXE-011 now Verified with refactored lifecycle model |
| SRD | `docs/execution/SRD.md` | Draft v1.7.0 | Sections 11–12: 30 SRDs (15 per FO), all Approved for FO-EXE-011/012; 25 Implemented across other FOs, 60 Draft/Approved |
| DD | `docs/execution/DD.md` | Draft v1.7.0 | DD-EXE-011.* (4 designs) and DD-EXE-012.* (2 designs); 21 items total; FO-EXE-011/012 designs Approved |
| MD | `docs/execution/MD.md` | Draft v1.6.0 | MD-EXE-011.* (7 modules) and MD-EXE-012.* (6 modules) implemented; 26 modules total |
| UTCD | `docs/execution/UTCD.md` | Draft v1.2.0 | Tests for FO-EXE-011/012: 67 cases (38+29) all Pass; 142 total cases specified |
| TRACE | `docs/execution/TRACE.md` | Draft v1.6.0 — **updated** | FO-EXE-011 and FO-EXE-012 rows updated with RN-EXE-1.8.0-20260527; both Verified |

### GUI (NEW — created)

| Artifact | File | Status | Notes |
|---|---|---|---|
| FO | `docs/gui/FO.md` | Draft v2.1.0 | 10 FOs (FO-GUI-001 through FO-GUI-014); FO-GUI-011/012 Implemented; FO-GUI-014 Approved (Active Cycles Panel) |
| SRD | `docs/gui/SRD.md` | Draft v2.3.0 | 53 SRDs: 34 Draft, 12 Approved, 7 Implemented |
| DD | `docs/gui/DD.md` | Draft v1.2.0 | 9 DDs across FO-GUI-001, 002, 004, 007, 011, 012, 014; FO-GUI-011/012 DD Approved |
| MD | `docs/gui/MD.md` | Draft v1.0.0 | 15 modules; FO-GUI-004 now includes pending_signals_table_model.py (new); MD-GUI-014 (3 modules) for Active Cycles |
| UTCD | `docs/gui/UTCD.md` | Draft v1.1.0 | 81 test cases; FO-GUI-004/012/014 test specs updated |
| TRACE | `docs/gui/TRACE.md` | Draft v1.4.0 — **updated** | FO-GUI-004 updated with pending_signals_table_model.py and RN-EXE-1.8.0-20260527; FO-GUI-012/014 rows remain; 2 files Implemented, 13 Draft, 1 Approved |

### MCP Server (NEW — created)

| Artifact | File | Status | Notes |
|---|---|---|---|
| FO | `docs/mcp/FO.md` | Draft v1.0.0 | 6 FOs: Server Interface, Data/Universe, Screener/Watchlist, Signals, Execution/Positions, Health |
| SRD | `docs/mcp/SRD.md` | Draft v1.0.0 | 14 SRDs for 9 MCP tools |
| DD | `docs/mcp/DD.md` | Draft v1.0.0 | 2 designs: MCPServer core, submit_order flow |
| MD | `docs/mcp/MD.md` | Draft v1.0.0 | 6 modules: server, data_tools, screener_tools, analysis_tools, execution_tools, health_tools |
| UTCD | `docs/mcp/UTCD.md` | Draft v1.0.0 | 20 tests across all tool modules |
| TRACE | `docs/mcp/TRACE.md` | Draft v1.0.0 | Full forward/reverse trace |

---

## 3. Open Decisions

| # | Topic | Decision | Status |
|---|---|---|---|
| 1 | SQLAlchemy ORM vs Core | Use Core (raw-SQL style) for performance | Decided |
| 2 | Async strategy evaluation | Sync — evaluation < 50 ms, asyncio overhead not justified | Decided |
| 3 | Short selling | Long-only for v1 | Decided |
| 4 | GUI | **PyQt6 GUI is core component** — full operator control, not just monitoring | Decided (2026-03-06) |
| 5 | Start order of implementation | INF → SCR → ANA → EXE; GUI & MCP parallel | Decided (de facto — followed for 13 sessions) |
| 6 | Multi-user support | Per-user profiles, settings, IBKR client IDs, isolated positions | Decided (2026-03-06) |
| 7 | Paper trading mode | Simulated execution with identical logic to live; toggle per user | Decided (2026-03-06) |
| 8 | Auto-launch | Windows Task Scheduler, T-60 before market open | Decided (2026-03-06) |
| 9 | MCP server | One MCP tool per major operation | Decided (2026-03-06) |
| 10 | S&P 500 OHLCV dev source | Dummy provider for development; IBKR for production; source TBD for free alternative | Decided (2026-03-06) |
| 11 | User-defined quantity | Users can override auto-calculated position size via GUI | Decided (2026-03-06) |
| 12 | Position states | Track: NEW → PARTIAL_ENTRY → OPEN → PARTIAL_EXIT → CLOSED | Decided (2026-03-06) |

---

## 4. Known Issues / Risks

| # | Risk | Mitigation |
|---|---|---|
| 1 | IBKR Gateway pacing limits during bootstrap (500 symbols × 3 TFs = 1,500 requests) | PacingQueue limits to 50/10min; bootstrap_all uses max_concurrent=5; estimated ~5 hours for full bootstrap |
| 2 | Historical/live candle consistency is critical and hard to debug | `CandleConsistencyError` in test mode; same aggregation function used for both paths |
| 3 | Thread-safety of PositionTracker accessed by both StrategyEngine and ExecutionEngine | RLock on all mutations; documented in DD-EXE |
| 4 | IBKR real-time bar subscriptions limited to 100 concurrent | Max 20 in our design; well within limit |
| 5 | Multi-user complexity: concurrent IBKR sessions, isolated positions | Each user gets own IBKRClient with unique clientId; PositionTracker keyed by user_id |
| 6 | Paper/live mode switch mid-session risk | Require confirmation dialog; clear in-flight paper orders before switch; no automatic switch |
| 7 | GUI responsiveness during heavy data operations | All DB/network operations on background threads; GUI thread never blocked |
| 8 | S&P 500 data source for development (no IBKR available during coding) | Dummy provider with synthetic data; same interface as real provider |
| 9 | INF TRACE.md is stale — all Status columns show "Draft" despite INF being fully implemented | After writing the 38 tests, update TRACE-INF Status → "Implemented" for all implemented module rows |

---

## 5. Implementation Sequence (Proposed — Revised)

```
Phase 1 (INF):
  → config/settings.py
  → data/models.py
  → db/schema.py + db/manager.py (incl. users table, position states)
  → broker/pacing.py + broker/client.py
  → universe/manager.py
  → data_engine/engine.py  (with pluggable provider: ibkr / dummy)
  → user/manager.py  (multi-user CRUD)
  → monitoring/

Phase 2 (SCR):
  → analysis/indicators.py  [shared utility, needed by SCR]
  → screener/config.py  (per-user configurable)
  → screener/filters.py
  → screener/engine.py
  → screener/watchlist.py

Phase 3 (ANA):
  → analysis/candle_builder.py
  → analysis/db_persister.py
  → analysis/strategies/breakout.py + pullback.py  (user-pluggable)
  → analysis/exit_manager.py
  → analysis/strategy_engine.py
  → analysis/live_engine.py

Phase 4 (EXE):
  → execution/risk_manager.py  (capital availability check)
  → execution/position_tracker.py  (position state machine, partial fills)
  → execution/circuit_breaker.py
  → execution/execution_engine.py  (paper/live toggle)
  → execution/paper_engine.py  (simulated fills)
  → execution/emergency.py
  → __main__.py  [CLI entry point]

Phase 5 (GUI — parallel with Phases 1–4):
  → gui/main_window.py
  → gui/dashboard_panel.py
  → gui/screener_panel.py
  → gui/execution_panel.py
  → gui/position_panel.py
  → gui/settings_panel.py  (user mgmt, strategy config, scheduler)
  → gui/log_viewer.py
  → gui/theme.py

Phase 6 (MCP — parallel with Phases 1–4):
  → mcp/server.py
  → mcp/tools/fetch_ohlcv.py
  → mcp/tools/run_screener.py
  → mcp/tools/get_positions.py
  → mcp/tools/submit_order.py
  → mcp/tools/system_health.py
```

---

## 6. Documentation Revision Summary

All 36 documentation files (6 modules × 6 artifact types) are now aligned with requirements.md v2:

| Module | Version | Files | Total SRDs | Total Tests |
|---|---|---|---|---|
| INF | v1.1.0 | 6 revised | 35 | 38 |
| SCR | v1.1.0 | 6 revised | 17 | 27 |
| ANA | v1.1.0 | 6 revised | 19 | 28 |
| EXE | v1.1.0 | 6 revised | 28 | 54 |
| GUI | v2.1.0 | 4 revised (SRD/DD/UTCD + .md improvements) | 35 | 36 |
| MCP | v1.0.0 | 6 created | 14 | 20 |
| **Total** | — | **36 files** | **148** | **203** |
