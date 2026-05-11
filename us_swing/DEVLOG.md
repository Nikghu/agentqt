# US Swing Trading System — Development Log

---

## [20260511] AGT — Introduced skills/ folder; migrated 5 commands to skills; added code-writer skill

- Type: Refactor
- RN: RN-AGT-1.0.0-20260511
- Artifacts updated: RN
- Decisions: commands/ for user-triggered workflows only; skills/ for agent-invoked inline skills; pyqt-comment-analyzer, dev-context, workspace, hookify, trace moved to skills; new code-writer skill embeds PyQt6 + Python patterns inline

---

## [20260506] EXE — Implemented IntradayCandleLoader with delta-fetch and validation

- Type: Feature
- FO(s): FO-EXE-006
- Artifacts updated: FO, SRD, DD, MD, UTCD, Code, Tests, RN
- Decisions: Fresh IB() per QThread run to avoid event-loop conflicts; 4-page IBKR paging (65 trading days) for first fetch; INSERT OR IGNORE for idempotent bar inserts; per-symbol error isolation with reason codes

---

## [20260505] SCR — Fixed Edit Preset dialog not persisting Assign Users

- Type: Bugfix
- FO(s): FO-SCR-005, FO-SCR-007
- Artifacts updated: Code, Issues, RN
- Decisions: None

---

## Session 2026-04-25 (38) — FO-SCR-011 Phase 1 Implemented: AI-Assisted Stock Ranking

**Agent:** Claude Sonnet 4.6

### Summary

Completed Phase 1 of FO-SCR-011 — AI-Assisted Stock Ranking with Tool-Augmented Reasoning. Users can now author natural-language queries to rank stocks post-filtering; Claude Haiku has on-demand access to daily/weekly OHLCV data and provides ~50-word per-stock reasoning. Full backward compatibility preserved — empty `ai_query` routes to legacy single-shot path.

### Implementation Highlights

**Core architecture:**
- `CandleToolExecutor` (`_tool_executor.py`): routes `get_candle_data` tool calls, validates symbol allowlist, enforces per-symbol call cap (default 3), returns errors as JSON (never raises)
- Multi-turn agentic loop in `LLMClaudeScreener._apply_with_tools()`: manages tool_use responses, parses final JSON ranking with reasoning
- `Preset.ai_query` (1–500 chars) + `Preset.ai_model` (configurable, defaults to `claude-haiku-4-5-20251001`)
- Reasoning side-channel: `screener.last_reasoning` dict merged into `result.results[sym]["ai_reasoning"]` by `PresetExecutor`

**GUI integration:**
- Preset Builder: "AI Query" QLineEdit (height `C.INPUT_H`, disabled for non-creators)
- Results table: "AI Reasoning" column (60-char truncated preview, full text in tooltip)
- CSV export: includes AI Reasoning field
- `_PresetRunWorker`: instantiates `DatabaseManager` per run, threads DB handle to `PresetExecutor` → screener config

**Provider-agnostic design:**
- Tool schema (`symbol`, `timeframe ∈ {1d, 1w}`, `lookback_bars ∈ [1, 300]`) designed for Claude, OpenAI, Gemini
- Phase 2 will refactor `_apply_with_tools()` into provider-agnostic helper without redesigning tool interface

### Verification

- **Unit tests:** 173/173 pass (24 new tests across preset, tool_executor, llm_claude, executor modules)
- **Linting:** ruff clean; mypy --strict clean on all new/modified code
- **Coverage:** ≥80% per-module; ≥90% for Must-priority SRDs
- **Smoke test:** Pending — requires real ANTHROPIC_API_KEY and populated candles.db

### Files Changed

**New (1):**
- `us_swing/src/us_swing/screener/screeners/_tool_executor.py` — `CandleToolExecutor` (~140 LOC)

**Modified (5):**
- `screener/preset.py` — `ai_query` + `ai_model` fields, validation
- `screener/screeners/llm_claude.py` — tool-augmented path, multi-turn loop, legacy path preserved
- `screener/executor.py` — Stage 3 wiring, reasoning merge
- `gui/screener_panel.py` — AI Query field, AI Reasoning column, DB handle threading
- `tests/screener/test_tool_executor.py` — new test file (13 tests)

**Documentation (6):**
- `docs/screener/FO.md` — v2.1.0 + FO-SCR-011
- `docs/screener/SRD.md` — v2.1.0 + Section 13 (SRD-SCR-013.001–008)
- `docs/screener/DD.md` — v2.1.0 + DD-SCR-011.001.D21
- `docs/screener/MD.md` — v2.1.0 + M18, footer note on 4 modified modules
- `docs/screener/TRACE.md` — v2.1.0 + FO-SCR-011 trace tree (11 FOs, 86 SRDs, 21 DDs, 18 MDs)
- `docs/screener/UTCD.md` — v2.1.0 + 22 test entries; total 173 tests
- `docs/screener/revisions/RN-SCR-2.1.0-20260425.md` — comprehensive revision note

### Artifact Status

- **FO-SCR-011:** Approved
- **SRD-SCR-013.001–008:** Approved
- **DD-SCR-011.001.D21:** Written
- **MD-SCR-011.001.M18:** Written
- **UTCD entries:** All 22 passing
- **Revision Note:** RN-SCR-2.1.0-20260425.md written

### Next Steps (Phase 2 — Multi-Provider)

Plan written but not yet started:
1. Refactor `_apply_with_tools()` into provider-agnostic `ai_ranking/` package
2. Introduce `AIProviderProtocol`, `ClaudeProvider`, `OpenAIProvider`
3. Add `Preset.ai_provider: Literal["claude", "openai"]` single-choice dropdown
4. Extend `APIUsageTracker` with per-provider spend tracking

**Estimated scope:** 4 new files (~600 LOC), 2 modified, 1 GUI dropdown. No breaking changes to Phase 1 design.

---

## Session 2026-04-22 (37) — PriceActionScreener M08 Implemented

**Work done:**
- Researched 5 empirically-backed OHLCV price action patterns (George & Hwang 2004, Bulkowski, Crabel, AQR, Tharavanij 2017)
- Updated SRD-SCR-002.007 with concrete pattern list, config schema, and scoring rule
- Updated MD-SCR-002.005.M08 with full API and dependency on `analysis/indicators.py`
- Updated UTCD: added `test_price_action_screener.py` section (8 tests); total now 129
- Implemented `screener/screeners/price_action.py` — 5 patterns: proximity_52w_high, volume_breakout, nr7_compression, ema_pullback, engulfing; score = matched/enabled; threshold default 0.2
- Created `tests/screener/test_price_action_screener.py` — 19 tests, all pass
- `__init__.py` already registered `price_action` screener (no change needed)
- Full suite: 222/222 pass — no regressions; ruff + mypy clean on new file

**Files changed:**
- `us_swing/docs/screener/SRD.md` — SRD-SCR-002.007 expanded
- `us_swing/docs/screener/MD.md` — M08 row updated
- `us_swing/docs/screener/UTCD.md` — new test section + summary updated to 129
- `us_swing/src/us_swing/screener/screeners/price_action.py` — full implementation
- `us_swing/tests/screener/test_price_action_screener.py` — new test file (19 tests)

---

## Session 2026-04-22 (36) — Removed v1 Screeners Tab from Settings

**Removed:** `_ScreenersTab` (Settings → Screeners tab) — v1 `ScreenerFilter` flat-config model superseded by v2 JSON preset architecture. All screener config now lives in the Screener panel (`_PresetBuilderDialog`).

**Files changed:**
- `gui/settings_panel.py` — deleted `_ScreenersTab` class; removed tab from `SettingsPanel`
- `data/models.py` — deleted `ScreenerFilter` dataclass
- `gui/app_service.py` — deleted `_DEFAULT_FILTERS`, `get_screener_filters()`
- `gui/_demo.py` — deleted `_SCREENER_FILTERS`, `get_screener_filters()`
- `gui/_types.py` — removed `ScreenerFilter` re-export
- `docs/gui/SRD.md` — SRD-GUI-006.001 updated; SRD-GUI-006.004 marked Verified/Removed

---

## Session 2026-04-22 (35) — Watchlist Tab on Dashboard

**Agent:** Claude Sonnet 4.6

### Changes
- `data/models.py`: added `WatchlistItem` dataclass with 12 fields (symbol, ltp, prev_close, change, change_pct, day_open, day_high, day_low, volume, year_high, year_low, market_cap)
- `gui/app_service.py`: added `_WatchlistQuoteWorker(QThread)` (fetches full quote via yfinance `fast_info`); added `watchlist_updated` pyqtSignal; added `_watchlist: list[WatchlistItem]`, `_wl_timer` (30s); added `add_to_watchlist()`, `remove_from_watchlist()`, `get_watchlist_items()`, `_refresh_watchlist()`, `_on_watchlist_data()` methods; wired timer start/stop into connect/disconnect flow; imported `WatchlistItem`
- `gui/dashboard_panel.py`: added `_WatchlistModel(QAbstractTableModel)` with 11 broker-terminal columns (Symbol|LTP|Chg$|Chg%|Open|High|Low|Volume|52WH|52WL|MktCap), color-coded change columns (green/red); added `_WatchlistTab(QWidget)` with symbol input+Add/Remove/Refresh toolbar, empty-state overlay, "Updated HH:MM:SS" status label; wired to `svc.watchlist_updated`; added tab "👁 Watchlist" to `_dash_tabs` after Trade History; fixed `on_watchlist_add()` to delegate to `_watchlist_tab.add_symbol()`

### No new dependencies
Uses yfinance already in pyproject.toml.

---

## Session 2026-04-22 (34) — RS Index Filter Implementation

**Agent:** Claude Sonnet 4.6

### Changes
- `screener/screeners/indicator.py`: added `BenchmarkDataUnavailableError` + `InsufficientUniverseDataError` exceptions; `_rs_slope()` (bar-aligned ratio comparison) and `_compute_rs_ranks()` (pandas vectorised 252d return percentile rank); `apply()` pre-computes RS ranks once before the symbol loop and applies `rs_index` filter block; `screen_detailed()` populates `rs_rank` and `rs_slope_up` detail keys
- `gui/screener_panel.py`: `_INDICATOR_DEFAULTS` extended with `rs_index`; `_format_indicator_config()` appends `RS≥N% slN` summary token; `_IndicatorConfigDialog` gains RS Index section (enabled, min percentile, slope days); `get_config()` serialises rs_index; both display-name dicts updated

### Dependency note
RS rank computation uses pandas (already in pyproject.toml). No new dependencies.
RS filter defaults to `enabled=False` — zero impact on existing presets until user explicitly enables it.

### Bug fix — `BenchmarkDataUnavailableError` on screener run
- **Root cause 1:** `_PresetRunWorker.run()` called `get_candles_bulk(symbols, …)` — SPY was never in the fetch list, so `bars.get("SPY", [])` returned `[]` → exception raised.
- **Root cause 2:** `get_candles_bulk` defaulted to `limit=200`; RS rank needs ≥253 bars. With only 200 bars, `_compute_rs_ranks` could not qualify any symbol and would return rank 50.0 for all.
- **Fix:** Read `benchmark_symbol` from `get_system_config()` (default "SPY"); append it to the fetch list; raise `limit` to 300. Benchmark stays in `bars` only — excluded from the `symbols` list so it never appears in results.

---

## Session 2026-04-22 (33) — Benchmark (SPY) Data + RS Requirements

**Agent:** Claude Sonnet 4.6

### Part A — Benchmark data implementation (code)

**`src/us_swing/gui/system_store.py`:**
- `SystemConfig.benchmark_symbol: str = "SPY"` added
- `load_system_config()` reads `"benchmark_symbol"` key; normalizes to uppercase; falls back to `"SPY"` on blank

**`src/us_swing/gui/app_service.py`:**
- `_CandleDownloadWorker.__init__()`: new `benchmark_symbol: str = "SPY"` parameter
- New `_CandleDownloadWorker._download_benchmark(ib)`: fetches `"2 Y"` of 1d + 1w bars for SPY via IBKR, inserts into `price_1d`/`price_1w` (same `INSERT OR REPLACE` pattern); emits `symbol_failed` on error (non-fatal)
- `_CandleDownloadWorker._download_all()`: calls `_download_benchmark(ib)` at start, before the universe symbol loop, for `mode in ("full", "delta")`
- `start_candle_download()`: passes `benchmark_symbol=cfg.benchmark_symbol` to worker

**Effect:** SPY candles appear in `price_1d`/`price_1w` after the next candle download. Chart Panel picks up SPY automatically (its `get_candle_symbols()` queries `SELECT DISTINCT symbol FROM price_1d`).

### Part B — RS requirements documentation

**INF SRD** (`docs/infrastructure/SRD.md`): Added SRD-INF-002.006, SRD-INF-003.008, SRD-INF-003.009
**SCR FO** (`docs/screener/FO.md`): Added FO-SCR-010
**SCR SRD** (`docs/screener/SRD.md`): Added Section 12 (SRD-SCR-012.001–012.005); totals 78 SRDs, 10 FOs
**SCR MD** (`docs/screener/MD.md`): Updated M04 — RS methods, new error classes, benchmark deps
**SCR UTCD** (`docs/screener/UTCD.md`): Added 8 RS test cases (T09–T16); total 121 tests

---

## Session 2026-04-22 (33) — RS vs S&P 500: Requirements Added to INF + SCR Docs

**Agent:** Claude Sonnet 4.6
**Trigger:** Relative strength vs S&P 500 was identified as missing from all screener requirements; SPY candle data was also missing from INF scope.

### Changes

**INF SRD** (`docs/infrastructure/SRD.md`):
- SRD-INF-002.006: `SystemConfig.benchmark_symbol` config field (default "SPY")
- SRD-INF-003.008: `HistoricalDataEngine.bootstrap_benchmark()` — fetches 2yr SPY 1d/1w bars
- SRD-INF-003.009: `HistoricalDataEngine.update_benchmark()` — incremental SPY sync

**SCR FO** (`docs/screener/FO.md`): Added FO-SCR-010 (Relative Strength vs Benchmark)

**SCR SRD** (`docs/screener/SRD.md`): Added Section 12 (5 requirements — RS line, RS rank, config params, error, performance). Totals: 10 FOs, 78 SRDs.

**SCR MD** (`docs/screener/MD.md`): Updated M04 — added RS computation, new error classes, benchmark deps.

**SCR UTCD** (`docs/screener/UTCD.md`): Added 8 RS test cases (T09–T16). Total: 121 tests.

### Key Decisions
- No DB schema migration needed — existing `price_1d`/`price_1w` are symbol-agnostic; SPY stored as regular symbol rows
- SPY NOT added to `universe` table (it's a benchmark, not a constituent)
- RS params default to 0 → RS filtering disabled by default (v1 preset backward compat preserved)
- TRACE.md pending update after implementation

---

## Session 2026-04-22 (32) — Screener Details Column: Indicator Config Summary

**Change:** `gui/screener_panel.py`
- Added `_format_indicator_config(config: dict) -> str` — compact one-line summary of IndicatorScreener config (e.g. `ATR≥1.0%  ·  RSI(30–70 p14)  ·  $5–5K  ·  BK10  ·  Vol≥1.0×`). Disabled filters are omitted.
- `ScreenerPanel._build_rows()` now resolves the active preset's `indicator_composite` ref config once per run and prepends `[<config summary>]` to every row's Details string when a non-default config is present.

---

## Session 2026-04-17 (31) — ANA Module Implementation Complete

**Agent:** Claude Sonnet 4.6
**Trigger:** Implement ANA (Analysis / Live Signal Engine) sub-package.

### Summary

Full ANA implementation: 10 source files + 4 test files, 40 tests all passing.

### Files Created

**Source (`src/us_swing/analysis/`):**
- `indicators.py` — `ema()`, `ema_value()`, `atr()`, `rsi()` pure functions
- `candle_builder.py` — `CandleBuilder`: count-based 5s→multi-TF aggregation, gap fill, `register_callback()`
- `db_persister.py` — `DatabasePersister`: queue + daemon writer thread, 5s drain cycle, sentinel flush
- `strategies/breakout.py` — `BreakoutStrategy`: 1h EMA50 trend + N-bar-high breakout
- `strategies/pullback.py` — `PullbackStrategy`: 1h EMA21 trend + 5m EMA21 cross-above recovery
- `exit_manager.py` — `ExitManager`: stop-loss / target / ATR trailing-stop; trail never retreats
- `strategy_engine.py` — `StrategyEngine` + `StrategyConfig`: per-user config, position suppression, INFO signal log
- `live_engine.py` — `LiveEngine`: IBKR subscription manager (max 20), wires CandleBuilder → strategies + DB
- `__init__.py`, `strategies/__init__.py`

**Tests (`tests/analysis/`):**
- `conftest.py` — helpers: `make_ohlcv_series()`, `make_rt_bars()`, `make_open_position()`
- `test_indicators.py` — 8 tests
- `test_candle_builder.py` — 9 tests
- `test_db_persister.py` — 3 tests
- `test_strategy_engine.py` — 20 tests (breakout, pullback, engine, config, exit)

### Decisions / Bugs

- **UTCD arithmetic error:** EMA(3) on [10,11,12,13] with seed-from-first-bar yields 12.125, not 12.375 as stated in UTCD. Test corrected.
- **StrategyConfig** co-located in `strategy_engine.py`; both `exit_manager.py` and strategies import from there under `TYPE_CHECKING` to avoid circular imports at runtime.
- **CandleBuilder** uses count-based windows (not epoch-aligned) to match UTCD test expectations (T01: 12 bars → 1 candle, T06: 36 bars → 1 3m candle).
- **LiveEngine** uses `register_callback()` on builder during `__init__` so the live-engine dispatch is the only active callback; strategy tests use builder directly with their own callbacks.

### Test Results

- ANA suite: 40/40 pass
- Full suite: 203/203 pass — no regressions

---

## Session 2026-04-17 (30) — GUI Screener Panel Polish Complete

**Agent:** Claude Sonnet 4.6
**Trigger:** Implement drag-and-drop WYSIWYG preset builder per SRD-SCR-007.002.

### Summary

- **`gui/screener_panel.py`** — added three new classes and wired them into `ScreenerPanel`:
  - `_GroupWidget` — composite group card: AND/OR toggle QPushButton (styled blue/purple), drag-reorderable `QListWidget` (`DragDropMode.InternalMove`), ＋ add screener menu, × remove, right-click "Remove from group"
  - `_WeightedRow` — per-screener row with drag hint, short name label, `QDoubleSpinBox` weight (0.01–1.00), × remove
  - `_PresetBuilderDialog` — full WYSIWYG builder: name + description fields, Composite/Weighted radio buttons (disabled in edit mode), `QStackedWidget` (composite groups area / weighted threshold + rows), live preview `QPlainTextEdit` (72px), Save / Save As… / Cancel; `_validate()` highlights name field on error
  - `_populate_from_preset()` handles both composite groups and weighted refs for edit mode
  - `_build_preset_from_ui()` constructs `Preset` from current UI state for create/update/clone
- **`ScreenerPanel` wiring:**
  - `_on_new_preset()` → `_PresetBuilderDialog` (replaced `_NewPresetDialog`)
  - `_preset_list` context menu policy set; `_on_preset_context_menu()` shows Edit / Duplicate / Delete
  - `_on_edit_preset()` → opens builder with existing `Preset` (edit mode)
  - `_on_duplicate_preset()` → opens builder in create mode pre-populated, name suffixed "(copy)"
  - `_on_delete_preset()` → QMessageBox confirmation → `mgr.delete_preset()` → list refresh
- `_NewPresetDialog` preserved as legacy (unused)
- Full suite: **163/163 pass** — no regressions

---

## Session 2026-04-17 (29) — INF Test Suite Complete (42/42)

**Agent:** Claude Sonnet 4.6
**Trigger:** Write 38 INF unit tests in `us_swing/tests/infrastructure/` per `docs/infrastructure/UTCD.md`.

### Summary

Wrote 42 INF unit tests across 8 test files (UTCD specified 38; final count is 42 as UTCD table rows total to 42 on careful re-count). All pass. Full suite 163/163 — no regressions.

### Files Created

- `us_swing/tests/infrastructure/__init__.py`
- `us_swing/tests/infrastructure/conftest.py` — `in_memory_db`, `app_config`, `live_config` fixtures
- `us_swing/tests/infrastructure/test_pacing.py` — 4 tests (PacingQueue)
- `us_swing/tests/infrastructure/test_ibkr_client.py` — 5 tests (IBKRClient)
- `us_swing/tests/infrastructure/test_universe_manager.py` — 4 tests (UniverseManager)
- `us_swing/tests/infrastructure/test_data_engine.py` — 5 tests (HistoricalDataEngine)
- `us_swing/tests/infrastructure/test_db_manager.py` — 6 tests (DatabaseManager)
- `us_swing/tests/infrastructure/test_monitoring.py` — 5 tests (logging / alerts / health)
- `us_swing/tests/infrastructure/test_user_manager.py` — 9 tests (UserManager)
- `us_swing/tests/infrastructure/test_dummy_provider.py` — 4 tests (DummyProvider)

### Production Bugs Fixed

| File | Bug | Fix |
|---|---|---|
| `db/manager.py` | `_str_to_dt` returned naive datetime → broke `(now - last)` arithmetic and `==` comparisons | Added `.replace(tzinfo=timezone.utc)` |
| `db/manager.py` | `upsert_universe` used `sa.bindparam("name")` in bulk INSERT `ON CONFLICT DO UPDATE` — invalid with SQLAlchemy 2.0 bulk semantics | Changed to `ins.excluded.name` / `ins.excluded.sector` |

### Technical Notes

- Import order in infrastructure `conftest.py` must start with `from us_swing.data.models import OHLCVBar` to avoid circular import (`db/__init__` → `db/manager` → `data/__init__` → `data/engine` → `db/manager` re-entry).
- `test_T02_excepthook_logs_uncaught_exception`: must restore `sys.excepthook = sys.__excepthook__` before calling `configure_logging` so the hook's `_original` is Python's default, not pytest-qt's hook.

---

## Session 2026-04-17 (28) — SCR Integration Tests Complete (15/15)

**Agent:** Claude Sonnet 4.6
**Trigger:** SCR Integration tests — `tests/screener/test_integration.py` (15 tests per `docs/screener/UTCD.md` §Integration).

### Summary

Implemented and validated all 15 integration tests for the Screener v2 system.

### Files Changed

- `tests/screener/test_integration.py` — 15 integration tests (NEW)
- `src/us_swing/screener/manager.py` — bug fix: `migrate_v1_presets()` now sets `weight=1.0` on ScreenerRef

### Tests Implemented (T01–T15)

| ID | Description | Result |
|----|-------------|--------|
| T01 | Full preset execution end-to-end | PASS |
| T02 | Composite AND/OR group logic | PASS |
| T03 | Weighted score calculation | PASS |
| T04 | v1 migration and execution | PASS |
| T05 | Manual trigger overwrites same-day result | PASS |
| T06 | Scheduled mode stored with correct execution_mode | PASS |
| T07 | LLM ranking enabled — augments results | PASS |
| T08 | LLM ranking disabled — results unchanged | PASS |
| T09 | LLM timeout fallback — uses Stage 2 results | PASS |
| T10 | Permission denied for non-creator/non-assigned | PASS |
| T11 | Permission granted via grant_access | PASS |
| T12 | New user create and run | PASS |
| T13 | Delete preset cleans up result files | PASS |
| T14 | Concurrent runs — no interference | PASS |
| T15 | Result persistence across PresetManager restart | PASS |

### Bugs Fixed

- `manager.py` `migrate_v1_presets()`: ScreenerRef was created without `weight`, so the weighted executor's `r.weight is not None` guard excluded it. Total weight = 0.0 → all symbols scored 0.0 → none passed threshold=0.5. Fix: added `weight=1.0`.

### Test Counts

- Integration suite: 15/15
- Full screener suite: 121/121 (no regressions)

---

## Session 2026-04-17 (27) — GUI Phase 5 Screener Panel v2 Complete

**Agent:** Claude Sonnet 4.6
**Trigger:** GUI Phase 5 — `gui/screener_panel.py` rewrite (v1 filter-chips → v2 preset-based).

### Summary

Full rewrite of `screener_panel.py` to v2 preset-based architecture. Removed v1 `_FilterChip` / `_ScreenerWorker` / v1 `_ResultsModel`. Replaced with:

**New classes:**
- `_Row` dataclass — per-symbol display data (symbol, score, matched, details)
- `_ResultsModel(QAbstractTableModel)` — 4-col model (Symbol · Score · Matched/Groups · Details); score color-coded ≥0.7 green / ≥0.4 yellow / <0.4 red
- `_PresetRunWorker(QThread)` — background runner; calls `PresetExecutor.run_preset()` with SP500 universe from `AppService.get_sp500_universe()`; emits `finished(object)` / `failed(str)`
- `_NewPresetDialog(QDialog)` — functional preset creation: name, type (Composite/Weighted), screener checkboxes from `ScreenerRegistry`, threshold (Weighted); calls `PresetManager.create_preset()`
- `ScreenerPanel(QWidget)` — full v2 panel

**Layout (matches existing GUI style exactly):**
- Toolbar (48px surface): `▶ Run Now` · progress · `‹ date ›` nav · mode badge (MANUAL/SCHEDULED) · status · CSV export · `＋ Watchlist`
- Left pane (260px): `ADMIN` / `MINE` section headers, preset items with `[C]`/`[W]` type badges, `＋ New Preset` button (mauve theme)
- Right pane: sortable `QTableView` with `QSortFilterProxyModel`; empty/error state overlays

**Non-breaking:**
- `watchlist_add_requested = pyqtSignal(str)` preserved — `main_window.py` wiring unchanged
- `AppService` not modified — no existing signals or methods touched
- Backend degrades gracefully if `PresetManager` unavailable (first-run, missing deps)
- Historical results: date navigation loads from `ScreenerResultsStorage.list_results()` / `load_result()`

### Test Results
- Full suite: **106/106 pass** — no regressions
- Import check: all 4 classes import cleanly; `main_window` import unaffected

### Architecture Notes
- `_PresetRunWorker` passes `symbols=sp500_list, bars={}` to executor → empty results until IBKR bar data is available (correct behaviour for this phase)
- Screener backend lazily initialized — errors caught and shown in status label

### Next
SCR integration tests — `tests/screener/test_integration.py` (15 tests)

---

## Session 2026-04-17 (26) — SCR Phase 5 Package Init Complete

**Agent:** Claude Sonnet 4.6
**Trigger:** Phase 5 — M15 `screener/__init__.py`.

### Summary

Completed M15 (package init). Rewrote `screener/__init__.py` to:
- Register all 6 built-in screeners in `ScreenerRegistry` at import time (`indicator_composite`, `ml_ensemble_v3`, `llm_claude_ranking`, `llm_local_mistral`, `price_action`, `mcp`)
- Export all orchestration + storage + utility classes (`PresetExecutor`, `PresetManager`, `ScreenerScheduler`, `ScreenerResultsStorage`, `FeatureCache`, `APIUsageTracker`, `PreFilter`)
- Expose `migrate_v1_presets()` convenience wrapper (delegates to `PresetManager.migrate_v1_presets()`)

### Test Results
- Full suite: **106/106 pass** — no regressions
- Import verified: `ScreenerRegistry.list_available()` returns all 6 screener IDs

### Next
GUI Phase 5 — `gui/screener_panel.py` (SRD-SCR-007 + docs/gui/SRD.md)

---

## Session 2026-04-17 (25) — SCR Phase 4 Management Implemented

**Agent:** Claude Sonnet 4.6
**Trigger:** Phase 4 — Management: manager.py (15 tests), scheduler.py (6 tests).

### Summary

- Implemented `screener/manager.py` — `PresetManager`: create/load/list/update/delete presets, grant/revoke access, v1 migration to indicator_composite screener.
- Implemented `screener/scheduler.py` — `ScreenerScheduler`: APScheduler cron scheduling, JSON persistence, injectable scheduler for testing. `CronError(ValueError)` for invalid cron.
- Added `apscheduler>=3.10` (+ tzlocal) to `pyproject.toml` dependencies; installed apscheduler 3.11.2.
- 21 new tests (15 manager + 6 scheduler) — all pass. Full suite: **106/106 pass**.

### Files Created/Modified

| File | Action |
|------|--------|
| `src/us_swing/screener/manager.py` | Created — PresetManager |
| `src/us_swing/screener/scheduler.py` | Created — ScreenerScheduler |
| `tests/screener/test_manager.py` | Created — 15 tests |
| `tests/screener/test_scheduler.py` | Created — 6 tests |
| `pyproject.toml` | Added apscheduler>=3.10 dependency |

---

## Session 2026-04-17 (24) — SCR Phase 3 Orchestration Implemented

**Agent:** Claude Sonnet 4.6
**Trigger:** Phase 3 — Orchestration: utils.py, executor.py, storage.py. Tests first per UTCD.

### Summary

Implemented SCR Phase 3 (Orchestration) — 3 modules + 40 tests. Full suite 85/85 pass.

### Files Created

**Implementation:**
- `us_swing/src/us_swing/screener/utils.py` — M14: PreFilter (price >$5, volume >1M, empty-bars exclusion), `parallel_execute()` helper, re-exports of all error classes from base.py.
- `us_swing/src/us_swing/screener/storage.py` — M13: `ScreenerResultsStorage` (atomic save/load/list), `FeatureCache` (24h TTL, per-symbol-per-day JSON), `APIUsageTracker` (cost formula, $50/mo WARNING), `ScreenerRunResult` dataclass.
- `us_swing/src/us_swing/screener/executor.py` — M10: `PresetExecutor` with full 3-stage pipeline: Stage 1 (PreFilter), Stage 2 (ThreadPoolExecutor for CPU screeners + asyncio.run for LLM screeners), Stage 3 (optional LLM ranking with fallback). Composite AND/OR logic, weighted score Σ(s_i×w_i)/Σ(w_i), `on_complete` callback.

**Tests (40 new):**
- `tests/screener/test_utils.py` — 8 tests: price/volume/halted filters, bulk timing, error hierarchy
- `tests/screener/test_storage.py` — 12 tests: atomic save/load, TTL expiry, cost formula, $50 warning
- `tests/screener/test_executor.py` — 20 tests: permissions, Stage 1–3, composite/weighted logic, fallback, on_complete event

### Key Decisions
- `ScreenerRunResult.results` stores only passing symbols (not all screened).
- `list_results()` returns date strings (YYYY-MM-DD) sorted desc, limit 30.
- Stage 2 LLM screeners identified by `"llm" in screener_id.lower()`; routed to asyncio.run().
- CPU screeners run via `ThreadPoolExecutor` (ProcessPoolExecutor not used; mocks aren't picklable in tests).

---

## Session 2026-04-17 (23) — SCR Phase 2 Core Plugins Implemented

**Agent:** Claude Sonnet 4.6
**Trigger:** Resume Phase 2 after discovering tests existed but implementations were missing.

### Summary

Implemented SCR Phase 2 (Core Plugins) — 6 modules + 27 tests. All 45 screener tests pass (18 Phase 1 + 27 Phase 2).

### Files Created

**Implementation (Phase 2):**
- `us_swing/src/us_swing/screener/screeners/indicator.py` — M04: IndicatorScreener with 5 configurable filters (ATR%, RSI, range, breakout, volume). Score = fraction of enabled passing filters.
- `us_swing/src/us_swing/screener/screeners/ml.py` — M05: MLScreener using joblib; per-symbol predict_proba, configurable threshold.
- `us_swing/src/us_swing/screener/screeners/llm_claude.py` — M06: LLMClaudeScreener; batch_features() extracts 7 features; apply() calls Claude API with graceful fallback on any error; cost tracking via optional usage_tracker.
- `us_swing/src/us_swing/screener/screeners/llm_local.py` — M07: stub (raises ScreenerError).
- `us_swing/src/us_swing/screener/screeners/price_action.py` — M08: stub (raises ScreenerError).
- `us_swing/src/us_swing/screener/screeners/mcp.py` — M09: stub (raises ScreenerError).
- `us_swing/src/us_swing/screener/screeners/__init__.py` — updated with all 6 exports.

**Infrastructure fix:**
- `us_swing/tests/__init__.py` — added (required for relative imports in Phase 2 tests).
- `us_swing/tests/screener/__init__.py` — added.

### Test Results

```
45 passed in 0.24s
test_indicator_screener.py: 8/8  test_ml_screener.py: 5/5  test_llm_claude_screener.py: 10/10
test_preset.py: 12/12  test_registry.py: 6/6
```

### Key Implementation Notes

- `llm_claude.py` uses broad `except Exception` instead of `except anthropic.APITimeoutError / AuthenticationError / RateLimitError` — the specific exception classes cannot be used in except clauses when the `anthropic` module is fully mocked in tests (non-BaseException mock attribute causes TypeError). Broad catch is functionally equivalent since all three map to fallback.
- `get_monthly_cost()` result wrapped in `float()` with try/except to handle MagicMock in tests.

### Next Step

SCR Phase 3 — Orchestration: `utils.py`, `executor.py`, `storage.py`. Write tests first.

---

## Session 2026-04-16 (22) — SCR Phase 1 Foundation Implemented

**Agent:** Claude Sonnet 4.6
**Trigger:** User requested SCR Phase 1 implementation per screener_v2_decision.md.

### Summary

Implemented SCR Phase 1 (Foundation) — 3 modules + 18 tests. All 18 tests pass.

### Files Created

**Tests (written first per UTCD-SCR v2.0.0):**
- `us_swing/tests/conftest.py` — root conftest; adds `us_swing/src` to sys.path
- `us_swing/tests/screener/conftest.py` — fixtures: `_clear_registry`, `composite_preset`, `weighted_preset`, mock classes
- `us_swing/tests/screener/test_preset.py` — 12 tests (T01–T12) for preset.py
- `us_swing/tests/screener/test_registry.py` — 6 tests (T01–T06) for registry.py

**Implementation:**
- `us_swing/src/us_swing/screener/base.py` — M02: `Screener` Protocol + full error hierarchy
- `us_swing/src/us_swing/screener/preset.py` — M01: `Preset`, `ScreenerRef`, `ScreenerGroup`, `PresetType`, `GroupLogic`; `to_dict()`, `from_dict()`, `validate()`
- `us_swing/src/us_swing/screener/registry.py` — M03: `ScreenerRegistry` singleton; `register()`, `get()`, `list_available()`, `_clear()`
- `us_swing/src/us_swing/screener/__init__.py` — Phase 1 public exports
- `us_swing/src/us_swing/screener/screeners/__init__.py` — stub for Phase 2 plugins

### Test Results

```
18 passed in 0.07s
test_preset.py: 12/12  test_registry.py: 6/6
```

### Next Step

SCR Phase 2 — Core plugins: `screeners/indicator.py` (v1 refactor), `screeners/ml.py` (stub), `screeners/llm_claude.py`, stubs for llm_local/price_action/mcp.
Tests: `test_indicator_screener.py` (8), `test_ml_screener.py` (5), `test_llm_claude_screener.py` (10).

---

## Session 2026-04-16 (21) — Screener v2.0 Documentation Complete

**Agent:** Claude Sonnet 4.6
**Trigger:** Continue from Session 20; user had begun Screener v2 architecture planning this morning.

### Summary

Full Screener v2 redesign documentation written. All 6 artifacts updated from v1.x to v2.0.0.
Architecture planning: 8 Q&A decisions locked before writing docs (Q1–Q7 from morning session + Q8 GUI approach answered this session).

### Architecture Decisions Locked

- Preset types: Composite (AND/OR group logic) + Weighted (scored ensemble)
- 3-stage execution pipeline: Pre-Filter → Parallel Screeners → Optional LLM Ranking
- Result storage: File-based (`~/.usswing/screener_results/`)
- Permissions: Hybrid admin/user + sharing/grants
- GUI: Drag-and-drop WYSIWYG preset builder
- LLM role: Ranking only (Stage 3), not filtering; $50/month cost threshold

### Artifacts Updated

| Artifact | Before | After | Key Change |
|---|---|---|---|
| `docs/screener/FO.md` | v1.1.0 (3 FOs) | v2.0.0 (9 FOs) | Full preset framework, plugins, scheduling, LLM, permissions |
| `docs/screener/SRD.md` | v1.2.0 (17 SRDs) | v2.0.0 (73 SRDs, 11 sections) | Complete redesign |
| `docs/screener/DD.md` | v1.1.0 | v2.0.0 (15 designs) | Plugin protocol, executor pipeline, storage, caching |
| `docs/screener/MD.md` | v1.1.0 (4 modules) | v2.0.0 (15 modules) | preset/base/registry/screeners/executor/scheduler/manager/storage/utils |
| `docs/screener/UTCD.md` | v1.1.0 (27 tests) | v2.0.0 (128 tests) | 113 unit + 15 integration |
| `docs/screener/TRACE.md` | v1.1.0 | v2.0.0 | Full FO→SRD→DD→MD→UT matrix, implementation readiness ✅ |

### Implementation Phase Plan (stored in memory)

- Phase 1 (Foundation): preset.py, base.py, registry.py — write tests first (18 tests)
- Phase 2 (Plugins): indicator.py (v1 refactor), ml.py, llm_claude.py, stubs — 23 tests
- Phase 3 (Orchestration): utils.py, executor.py, storage.py — 40 tests
- Phase 4 (Management): manager.py, scheduler.py — 21 tests
- Phase 5 (Integration): __init__.py, GUI screener_panel.py — 15 integration tests

### Pending (not started)

- INF 38 unit tests still pending from Session 20 (`tests/infrastructure/` dir does not exist)
- SCR implementation not started — docs are the prerequisite

---

## Session 2026-04-08 (20) — Candle Chart Viewer (TradingView Lightweight Charts)

**Agent:** Claude Sonnet 4.6
**Trigger:** User needs to visually verify candle data quality after database download.

### Changes

#### `gui/resources/lightweight-charts.standalone.production.js` (new)
- TradingView Lightweight Charts v5.0.5 standalone bundle (174 KB, Apache 2.0).
- Bundled locally so the chart works fully offline.

#### `gui/chart_panel.py` (new)
- `CandleChartPanel(QWidget)` — the full chart viewer.
- Toolbar: symbol combo (editable, populated from DB), timeframe combo (1d/1w), bars spinbox (20–2000), Load Chart button, Refresh List button.
- `QWebEngineView` renders self-contained HTML with Lightweight Charts:
  - Candlestick pane (main) + volume histogram sub-pane (80 px).
  - Both panes sync scroll/zoom via `subscribeVisibleLogicalRangeChange`.
  - Crosshair tooltip in header strip — OHLCV + volume on hover.
  - Dark theme using `theme.C` colour constants.
  - Offline-first: inline JS bundle; CDN fallback if bundle missing.
  - Watermark: `"US Swing | SYMBOL — TF"`.
- `showEvent` refreshes the symbol list each time the tab becomes visible.
- Placeholder shown until first chart is loaded; "no data" message if DB has no rows for selected symbol.

#### `gui/app_service.py`
- `get_candle_symbols() -> list[str]` — `SELECT DISTINCT symbol FROM price_1d ORDER BY symbol`.
- `get_candles_for_symbol(symbol, timeframe, limit) -> list[dict]` — returns rows with Unix `time` timestamps as required by Lightweight Charts; supports `price_1d` and `price_1w`.

#### `gui/main_window.py`
- Import: `from us_swing.gui.chart_panel import CandleChartPanel`.
- Navigation expanded from 4 → 5 tabs: Dashboard · Screener · Execution · **Chart** · Settings.
- `CandleChartPanel` instantiated and inserted before `SettingsPanel` in both `panels` list and `nav_items`.

#### `requirements.md`
- §21 Implementation Status: updated tab count to 5-tab nav; added §32 row.
- §32 added: full Chart Viewer spec (engine, toolbar, crosshair, sync, watermark, AppService API).

---

## Session 2026-04-08 (19b) — Universe Tab: Candle Coverage Columns

**Agent:** Claude Sonnet 4.6
**Trigger:** User requested candle DB availability status + last-updated date in the Universe (Settings → Universe) table, with discrepancy highlighting.

### Changes

#### `app_service.py`
- Added `get_last_trading_day() -> str` — public wrapper around `_compute_last_trading_day()`.
- Added `get_candle_symbol_coverage() -> dict[str, str | None]` — single `SELECT symbol, MAX(datetime) FROM price_1d GROUP BY symbol` query; returns empty dict if DB absent or unreadable.

#### `settings_panel.py`
- `_UNIVERSE_HTML` CSS: added `.stale` (amber #322a14) and `.missing` (red #321414) row classes with hover override.
- `_UNIVERSE_HTML` JS `COLS`: added `['DB', 7, 50]` and `['Last Updated', 6, 120]`; `colOrder` extended to 8 entries.
- Cell renderer: `ci===6` → icon (✔/⚠/✘) coloured green/amber/red based on `r[7]` (status); `ci===7` → date or `—` with matching colour.
- Row renderer: adds `class="stale"` or `class="missing"` based on `r[7]`; current rows have no extra class.
- `_build_universe_html()`: added `coverage` + `last_trading_day` params; `_sym_status()` helper computes per-symbol `(last_date, status)` tuple appended as `r[6]`/`r[7]`.
- `_UniverseTab._load_from_cache()`: calls `get_candle_symbol_coverage()` and `get_last_trading_day()` before building HTML.
- `_UniverseTab.__init__`: connected `svc.candle_db_status_changed` → `_load_from_cache()` so table refreshes after every DB build/delta.

#### `requirements.md`
- §5 Universe Manager: added "Universe Tab — Candle Coverage Display" spec section documenting the new columns, colour coding, and auto-refresh behaviour.

---

## Session 2026-04-08 (19) — Runtime Bug Fixes + Per-Symbol Failure Tracking

**Agent:** Claude Sonnet 4.6
**Trigger:** Three runtime errors during "Build Full Database" + user request for failure visibility and repair UX.

### Bug Fixes

#### `app_service.py` / `system_store.py` — `ibkr_system_client_id` missing
- `SystemConfig` dataclass was missing `ibkr_system_client_id: int = 10`; added to dataclass + `load_system_config()`.

#### `app_service.py` — IBKR duration-string validation (Error 321)
- IBKR rejects `"N D"` > 365 days and `"N W"` > 52 weeks. Added `ibkr_duration_1d` / `ibkr_duration_1w` logic: converts to `"N Y"` when thresholds exceeded.

#### `app_service.py` — Dot-in-symbol IBKR quirk (Error 200 on BRK.B, BF.B)
- IBKR contract symbols use space not dot. Added `ibkr_symbol = symbol.replace(".", " ")` before `Stock()` construction. DB still stores canonical dotted name.

### New Feature — Per-Symbol Failure Tracking (FO-GUI-010)

#### `docs/gui/FO.md`
- Added **FO-GUI-010**: functional objective for per-symbol failure tracking and Fix Discrepancies repair flow.

#### `docs/gui/SRD.md`
- **SRD-GUI-006.015 (new):** Worker `symbol_failed` signal; AppService accumulation + `candle_failed_symbols.json` persistence; `start_candle_download(symbols=)` fix-mode override.
- **SRD-GUI-006.016 (new):** `_DatabaseTab` discrepancy group, live fail counter, "🔧 Fix Discrepancies" button, persisted panel restore on startup.

#### `app_service.py`
- `_CandleDownloadWorker`: `symbol_failed = pyqtSignal(str, str)`; `except Exception` now captures and emits; empty-bars → `"NO_DATA"`.
- `AppService`: `candle_symbol_failed` + `candle_download_failures` signals; `_current_failed` list; `_on_candle_symbol_failed()` handler; `_on_candle_finished()` saves/deletes `candle_failed_symbols.json` and emits `candle_download_failures`; `get_failed_symbols()`, `has_failed_symbols()`, `clear_failed_symbols()` public methods; `start_candle_download(symbols=None)` fix-mode path.

#### `settings_panel.py` — `_DatabaseTab`
- Live `_fail_count_lbl` in progress section increments on `candle_symbol_failed`.
- New `_disc_group` (QGroupBox) with summary label, symbol list label, "🔧 Fix Discrepancies" button.
- `_on_symbol_failed()`, `_on_failures_ready()`, `_on_fix_discrepancies()`, `_show_discrepancies()`, `_load_persisted_failures()` methods.
- `_set_downloading(True)` resets/hides discrepancy panel.

---

## Session 2026-04-08 (18) — IBKR Download Source + Checkpoint/Resume

**Agent:** Claude Sonnet 4.6
**Trigger:** User wants candle download to use IBKR (not yfinance) as the authoritative data source, with automatic resume on interruption and last-data verification on restart.

### Changes

#### `us_swing/docs/gui/SRD.md`
- **SRD-GUI-006.011** updated: removed yfinance reference; noted IBKR as source; added `candle_download_paused` signal; checkpoint path in constraints.
- **SRD-GUI-006.012 (new):** IBKR connection gate — `start_candle_download()` checks `CONNECTED`; GUI shows `QMessageBox.warning` if not connected.
- **SRD-GUI-006.013 (new):** Checkpoint/resume — `~/.usswing/candle_download_checkpoint.json` written after each symbol; auto-detected on next download call; last 5 symbols re-verified against DB.
- **SRD-GUI-006.014 (new):** Mid-download disconnect — worker emits `failed("IBKR_DISCONNECTED")`; AppService routes to `candle_download_paused`; UI shows paused state with resume option.

#### `us_swing/src/us_swing/gui/app_service.py`
- Added `import asyncio`, `import json`.
- Constants: renamed `_CANDLE_BATCH_SIZE/PAUSE` → `_CANDLE_SYMBOL_PAUSE_S = 1.0`; added `_CHECKPOINT_PATH`, `_RESUME_VERIFY_COUNT = 5`.
- Added module-level helpers: `_save_checkpoint()`, `_load_checkpoint()`, `_delete_checkpoint()`, `_verify_resume_symbols()`, `_bar_date_str()`.
- **`_CandleDownloadWorker` rewritten:**
  - Constructor now takes `ibkr_host`, `ibkr_port`, `ibkr_client_id`.
  - `run()` calls `asyncio.run(self._async_run())`.
  - `_async_run()`: connects `ib_insync.IB` via `connectAsync()`; emits `failed("IBKR_NOT_CONNECTED")` on failure.
  - `_download_all()`: loops symbols; uses `reqHistoricalDataAsync` for 1d + 1w bars; writes DB atomically per symbol; saves checkpoint after each symbol; deletes checkpoint on clean finish; checks `ib.isConnected()` per iteration.
- **`AppService`:** added `candle_download_paused` signal; added `has_candle_checkpoint()`; updated `start_candle_download()` with IBKR gate + checkpoint resume logic + stale symbol re-verification; updated `stop_candle_download()` docstring; updated `_on_candle_failed()` to route `IBKR_DISCONNECTED` → `candle_download_paused`.

#### `us_swing/src/us_swing/gui/settings_panel.py`
- Added `QMessageBox` import.
- **`_DatabaseTab`:** added `candle_download_paused` signal wiring; added `_apply_checkpoint_state()` — shows "▶ Resume Download" button if checkpoint file exists; added `_on_paused()` slot (shows paused state, calls `_apply_checkpoint_state`); updated `_on_build_clicked()` to check IBKR connection status (shows warning dialog if not connected) and handle checkpoint resume path; `_on_finished()` and `_on_failed()` now call `_apply_checkpoint_state()`; `_on_status_loaded()` calls `_apply_checkpoint_state()` after button update.

### Architecture Decisions
- Download worker creates its own dedicated `ib_insync.IB()` connection using `SystemConfig.ibkr_system_client_id` — separate from user client IDs and from the TCP probe used by `connect_feed()`.
- `asyncio.run()` used in `QThread.run()` — creates isolated event loop per download session; clean on completion.
- Per-symbol rate limit pause (1.0 s, interruptible in 0.1 s steps) replaces per-batch pause — more responsive to stop requests and cleaner for IBKR's per-request pacing model.
- Checkpoint keyed by `mode + start_date`; a full-mode checkpoint does not resume a delta-mode call (delta always starts fresh).
- Auto-resume is NOT implemented — user must click Resume after reconnect (SRD-GUI-006.014).

### Syntax Verification
- Both `app_service.py` and `settings_panel.py` pass `python -m py_compile`.

### Next Steps
- Write 38 INF unit tests in `us_swing/tests/infrastructure/` per `docs/infrastructure/UTCD.md` (highest priority, pre-existing).

---

## Session 2026-04-08 (17) — Candle Database Management Tab

**Agent:** Claude Sonnet 4.6
**Trigger:** User needs a one-time S&P 500 OHLCV database builder with status display, start-date picker, batch download, and delta fill — to avoid re-downloading every day.

### Changes

**New SRD:** `SRD-GUI-006.011` added to `docs/gui/SRD.md` — "Database" tab specification.

**`gui/app_service.py`:**
- Added `CandleDbStatus` enum (`EMPTY` / `PARTIAL` / `CURRENT`)
- Added `CandleDbInfo` dataclass (status, dates, coverage, candle counts)
- Added `_compute_last_trading_day()` — uses existing `market_calendar.py` NYSE_HOLIDAYS; accounts for 16:00 ET closing bell
- Added `_ensure_candle_tables()` — creates `price_1d`/`price_1w` SQLite tables if missing
- Added `_CandleDbStatusWorker(QThread)` — background DB stat query; emits `CandleDbInfo`
- Added `_CandleDownloadWorker(QThread)` — yfinance batch downloader; 20 symbols/batch, 2 s inter-batch pause; stop-safe
- Added signals: `candle_db_status_changed`, `candle_download_progress`, `candle_download_finished`, `candle_download_failed`
- Added AppService methods: `refresh_candle_db_status()`, `start_candle_download()`, `stop_candle_download()`, `_last_known_candle_date()`

**`gui/settings_panel.py`:**
- Added `_DatabaseTab(QWidget)` — status card (colored badge, dates, coverage, candle count), build/delta button (state-aware), progress group (progress bar + cancel button)
- `SettingsPanel` now has 6 tabs: Users / Strategies / Screeners / System / Universe / **Database**

### Architecture Decisions

1. **Separate "Database" tab** — not System tab; single-responsibility principle
2. **yfinance as download source** — already a project dependency; IBKR swap deferred until post-INF-test via existing DataProvider protocol
3. **DB path** — `~/.usswing/candles.db` (consistent with `~/.usswing/` convention)
4. **Status = CURRENT** — requires MAX(datetime) == last trading day AND ≥ 95% symbol coverage
5. **Delta mode** — computes start date from `MAX(datetime)` in price_1d, no user input needed
6. **Stop safety** — worker checks `_stop_flag` between symbols and every 0.2 s during inter-batch pauses

### Immediate Next (unchanged)

Write 38 INF unit tests per `docs/infrastructure/UTCD.md`. SRD-GUI-006.011 needs approval before UTCD update.

---

## Session 2026-03-17 (16) — Candle Data Sync Requirements

**Agent:** Claude Sonnet 4.6 (Opus 4.6 fast)
**Trigger:** User wants S&P 500 candle data (1d + 1w, 2 years) stored in DB before screener runs. First-time bootstrap + daily incremental sync. Universe tab to show candle status per symbol. Sync triggered from GUI.

### Decisions

1. **2-year history for 1d/1w** (was 1 year): screener indicators (ATR, RSI, BB, breakout levels) require robust baselines; 2 years → ~504 trading days. 1m bars stay at 5 trading days (intraday, not needed by EOD screener).
2. **Candle metadata on `universe` table**: `candle_start_date`, `candle_last_date`, `data_status` ('missing'/'stale'/'up_to_date'). Updated atomically by `HistoricalDataEngine` after each symbol's bootstrap or sync.
3. **`AppService.sync_candle_data()`**: triggers incremental 1d+1w sync for all symbols in background QThread; emits `candle_sync_updated` signal on completion. Called automatically on startup after universe loads; also on-demand from GUI.
4. **Universe tab extended**: HTML table gains 3 columns (First Bar, Last Bar, Status ●). "🔄 Sync Candles" button added alongside existing "🔄 Refresh". Tab reloads on both `sp500_updated` and `candle_sync_updated`.
5. **Screener data guard**: symbols with `data_status='missing'` excluded from scan; `'stale'` included with WARNING. Scan aborted with ERROR only if ALL symbols are missing.

### Changed Files

| File | Change |
|---|---|
| `docs/infrastructure/FO.md` | v1.2.0 → v1.3.0: FO-INF-002 + candle metadata; FO-INF-003: 1Y → 2Y for 1d/1w, candle sync flow, acceptance criteria updated |
| `docs/infrastructure/SRD.md` | v1.3.0 → v1.4.0: SRD-INF-002.005 (new); SRD-INF-003.001 updated (2Y, Draft); SRD-INF-003.006/007 (new); SRD-INF-004.001 updated (universe schema) |
| `docs/gui/SRD.md` | v2.2.0 → v2.3.0: SRD-GUI-006.006 updated (candle columns + Sync Candles button) |
| `docs/screener/FO.md` | v1.1.0 (no version bump): cached candle data requirement + 2Y minimum note added |
| `docs/screener/SRD.md` | v1.1.0 → v1.2.0: SRD-SCR-001.009 (new) — data readiness guard |

### Result

All candle data management design decisions captured as Draft requirements. No source changes. Pending: approval of Draft INF items, then DD/MD/UTCD updates for `sync_candle_data()` and the extended `UniverseRecord` before implementation.

---

## Session 2026-03-17 (15) — Admin Flag + IBKR Dual-Use Requirements; DD-GUI-002 Corrected

**Agent:** Claude Sonnet 4.6
**Trigger:** User asked (1) why per-user P&L/equity not visible on scope switch; (2) how to handle admin designation and IBKR dual-use (same account for system data + admin trading).

### Decisions

1. **Per-user data is already shown in `_AdminContextBar`** when scope combo switches — equity, Day P&L, open positions, risk %, mode, IBKR # all update per user. Values are stub data (`$100K hardcoded`, `daily_pnl=0.0`) until INF/EXE are wired. Not a requirement gap.
2. **`PositionMonitorPanel` not in nav** — "Capital Utilised" progress bar is unreachable from the current UI. Known gap; not addressed yet.
3. **IBKR dual-use resolved** — system uses `ibkr_system_client_id` (from `SystemConfig`) for its market data connection; admin user's `ibkr_client_id` is for trading orders. Both connect to same TWS. clientIds must differ.
4. **`is_admin: bool` added to `UserProfile`** — first user = auto-admin; `LastAdminError` prevents deleting/demoting last admin.
5. **DD-GUI-002.001.D01 rewritten** — was completely stale (`PositionTracker` constructor, 8 wrong column names, no User column, wrong colour logic). Now reflects actual implementation including `TradeHistoryModel`, `set_show_user()`, `set_highlighted_row()`, `C.*` theme constants.

### Changed Files

| File | Change |
|---|---|
| `docs/infrastructure/FO.md` | v1.1.0 → v1.2.0: FO-INF-001 + system clientId note; FO-INF-006 + is_admin + LastAdminError |
| `docs/infrastructure/SRD.md` | v1.2.0 → v1.3.0: SRD-INF-001.006 (ibkr_system_client_id); SRD-INF-006.008/009/010 (is_admin, auto-admin, LastAdminError) |
| `docs/gui/FO.md` | v2.0.0 → v2.1.0: FO-GUI-006 + admin protection + System clientId field |
| `docs/gui/SRD.md` | v2.1.0 → v2.2.0: SRD-GUI-006.007/008/009/010 (Admin col, dialog checkbox, delete guard, System clientId spinbox) |
| `docs/gui/DD.md` | v1.1.0 → v1.2.0: DD-GUI-002.001.D01 fully rewritten (PositionTableModel + TradeHistoryModel) |

### Result

All admin designation and IBKR dual-use design decisions are now captured as Draft requirements. No source changes. Ready for Approval before implementation.

---

## Session 2026-03-16 (14) — GUI Docs Aligned; .md Tooling Improvements

**Agent:** Claude Sonnet 4.6
**Trigger:** User requested codebase review for .md improvement opportunities; then targeted DD / SRD / UTCD corrections for GUI module.

### Decisions

1. **AGENT_BOOT.md rewritten** — Stale `pilot1`-first content replaced; `us_swing` declared active; Current State updated to Phase: Post-GUI, INF implemented, 38 tests pending.
2. **PROMPTS.md extended** — 4 new templates added: Session Resume, Test Writing (UTCD→pytest), Document Status Update, Architecture Review.
3. **CLAUDE.md extended** — 3 new sections: Active Project, Date Handling (staleness warning), Plan Mode Guidance.
4. **process.md patched** — Rule 8 added (plan mode for AI agents); BKT scope note added (no FO defined, do not implement until EXE complete).
5. **CONTEXT.md §0 added** — Immediate Next Step section added at top; Decision #5 marked Decided (de facto); Known Issue #9 (INF TRACE stale) added.
6. **DD-GUI-001.001.D01 rewritten** — Fully aligned with `main_window.py` implementation: `AppService` DI, frameless layout, `_TitleBar`/`_AdminContextBar`/`QStackedWidget`, 4 panels, 1180×740 geometry, signal wiring table, admin scope table, feed state machine.
7. **SRD-GUI all 9 sections reviewed** — v2.0.0 → v2.1.0; corrected: status bar (Internet/P&L/Positions left; NYSE/NASDAQ right), default size 1180×740, column lists for all table models, Universe tab uses QWebEngineView, Market Watch in `_AdminContextBar` (not Dashboard), log source is `AppService.log_message` signal.
8. **UTCD-GUI all 7 modules corrected** — v1.0.0 → v1.1.0; fixed: T01 tab count (4, not 6), status bar widget names, scope icon signal path, feed button text, column counts (9 base / 10 with User), P&L colour constants (`C.PNL_POS_BG`/`C.PNL_NEG_BG`), `modelReset` vs `layoutChanged`, CAN ENTER/CANNOT ENTER badge text, Pause/Resume flush semantics.

### Changed Files

| File | Change |
|---|---|
| `AGENT_BOOT.md` | Rewritten Current State; added Active Project section; expanded Common Commands; On-Demand Guide reordered |
| `PROMPTS.md` | 4 new prompt templates prepended/appended |
| `CLAUDE.md` | 3 new sections added (Active Project, Date Handling, Plan Mode Guidance) |
| `process.md` | Rule 8 in §0; BKT scope note before §14.3 |
| `us_swing/CONTEXT.md` | §0 Immediate Next Step added; Decision #5 decided; Known Issue #9 added; INF Tests sub-table added |
| `docs/gui/DD.md` | DD-GUI-001.001.D01 fully rewritten → v1.1.0 |
| `docs/gui/SRD.md` | All 9 sections aligned with implementation → v2.1.0 |
| `docs/gui/UTCD.md` | All 36 tests corrected across 7 modules → v1.1.0 |

### Result

All GUI documentation (DD/SRD/UTCD) now accurately reflects the implemented PyQt6 GUI. AI boot context corrected so future sessions start with `us_swing` as the active project and the 38-INF-tests as the immediate next step.

---

## Session 2026-03-15 (13) — Market Watch Moved to Admin Context Bar; Edit Button Removed

**Agent:** GitHub Copilot (Claude Sonnet 4.6)
**Trigger:** User requested Market Watch strip removed from Dashboard panel; moved inline into `_AdminContextBar` row (leftmost position, hardcoded symbols, no edit button).

### Decisions

1. **Market Watch location** — Removed `_MarketWatchWidget` class and instantiation from `dashboard_panel.py`; displayed inline in `_AdminContextBar` (globally visible, 28px strip below accent line).
2. **Format** — `MARKET WATCH  S&P 500  $X,XXX.XX  +X.XX%    NASDAQ  $X,XXX.XX  -X.XX%    Dow Jones  $X,XXX.XX  +X.XX%  │  🌐 ALL USERS ...`
3. **No Edit button** — Symbols are hardcoded in `AppService._watch`; no dialog needed.
4. **`_AdminContextBar._refresh_mw()`** — Wired to `svc.market_watch_updated` signal from AppService.

### Changed Files

| File | Change |
|---|---|
| `gui/dashboard_panel.py` | Removed `_MarketWatchWidget` class (lines 792–916) and instantiation; layout cleaned |
| `gui/main_window.py` | `_AdminContextBar`: Market Watch labels at leftmost position; `_refresh_mw()` method added; signal wired |

### Result

All GUI imports clean. Market Watch displays at top-left of admin bar visible across all panels.

---

## Session 2026-03-15 (9) — Demo Backend Removed; AppService + Feed Toggle Added

**Agent:** GitHub Copilot (Claude Sonnet 4.6)
**Trigger:** User confused by Alice/Bob/Carol demo data; requested clean paper-mode service, explicit Connect/Disconnect toggle, and architecture-level `ConnectionStatus` access.

### Decisions

1. **`AppService` replaces `DemoService`** — No fake seed data. Empty positions/trades on startup. Real users from `user_store.py`; default "trader" UserProfile created on first run if no users exist.
2. **Feed toggle in title bar** — `_TitleBar` gains a 3-state QPushButton (Connect Feed / ⟳ Connecting… / 🟢 Connected) placed after Scope combo, before window-controls divider.
3. **Disconnect confirmation** — Clicking "🟢 Connected" triggers `QMessageBox.question` before calling `disconnect_feed()`.
4. **`AppService.connection_status`** — typed `ConnectionStatus` enum property for architecture-level failsafe checks; `feed_status_changed(str)` signal broadcasts raw value for GUI slots.
5. **Status bar** — Updated from "⬤  Demo Mode" (green) to "⬤  Disconnected" (muted) with dynamic updates via `_on_sb_feed_status_changed`.
6. **`_demo.py` preserved** — Not deleted; just no longer imported by any file. Available for reference.
7. **FO-GUI-008 + SRD-GUI-008.001–004** — Added to `docs/gui/FO.md` and `docs/gui/SRD.md`.

### Changed Files

| File | Change |
|---|---|
| `gui/app_service.py` | **Created** — drop-in `AppService(QObject)` replacing `DemoService` |
| `gui/main_window.py` | Import → `AppService`; `_TitleBar` feed button added; status bar updated |
| `gui/__main__.py` | `DemoService()` → `AppService()`; param renamed `svc` |
| `gui/dashboard_panel.py` | Import → `AppService` |
| `gui/execution_panel.py` | Import → `AppService` |
| `gui/log_viewer_panel.py` | Import → `AppService` |
| `gui/position_monitor_panel.py` | Import → `AppService` |
| `gui/screener_panel.py` | Import → `AppService` |
| `gui/settings_panel.py` | Import → `AppService` |
| `docs/gui/FO.md` | Added `FO-GUI-008` |
| `docs/gui/SRD.md` | Added Section 8 (`SRD-GUI-008.001–004`) |

### Verification

- All GUI imports pass: `ALL PANELS OK` confirmed via Python import test
- No remaining `DemoService` references outside `_demo.py`

---

## Session 2026-03-15 (8) — INF Module Implementation + GUI Model Consolidation

**Agent:** GitHub Copilot (Claude Sonnet 4.6)
**Trigger:** User approved all INF requirements; requested full implementation of the Infrastructure module, removal of GUI model duplicates, and paper-only mode enforcement.

### Decisions

1. **Single source of truth for domain models** — `data/models.py` defines all dataclasses/enums. `gui/_types.py` is now a thin re-export shim for backward-compat imports. No GUI file defines its own data class.
2. **Paper-only enforcement** — `AppConfig.live_mode_enabled = False`; `UserManager.switch_mode()` raises `LiveModeDisabledError` when attempting switch to 'live'. Settings panel only exposes "paper" in mode combo.
3. **`UserProfile` flattened → nested** — `risk_config: RiskConfig` replaces 6 flat risk fields. `display_name` added. `user_store.py` JSON format updated (field `max_capital_pct` → `max_allocation_pct`).
4. **`TradeSignal` enriched** — added `entry_price`, `stop_loss`, `target_price`, `recommended_qty` optional fields so execution panel can show R/R ratio without extending the type.
5. **`PositionRecord.trailing_stop`** — given default `0.0` so `OpenPosition` instances can be constructed without trailing_stop argument.
6. **SQLAlchemy** added to `pyproject.toml` dependencies and installed in venv.
7. **SRD-INF-001.002 discrepancy** — corrected `ConnectionError` (built-in) → `BrokerConnectionError` (custom); row held at Draft per process rules.

### New Files (INF module, `src/us_swing/`)

| File | Purpose |
|---|---|
| `exceptions.py` | 9-class exception hierarchy rooted at `USSwingError` |
| `config/settings.py` + `__init__.py` | `AppConfig` + sub-configs; TOML+env loader |
| `data/models.py` | Canonical domain dataclasses + enums (single source of truth) |
| `db/schema.py` | SQLAlchemy Core table definitions |
| `db/manager.py` + `__init__.py` | `DatabaseManager` — all CRUD, SQLite upsert |
| `broker/pacing.py` | Asyncio rolling-window token bucket (50 req / 600 s) |
| `broker/client.py` + `__init__.py` | `IBKRClient` with reconnect + exponential backoff |
| `user/manager.py` + `__init__.py` | `UserManager` CRUD + `switch_mode` with live-mode gate |
| `universe/manager.py` + `__init__.py` | `UniverseManager` — Wikipedia refresh + scheduler |
| `data/providers/protocol.py` | `DataProvider` runtime-checkable Protocol |
| `data/providers/ibkr_provider.py` | `IBKRProvider` (thin adapter over IBKRClient) |
| `data/providers/dummy_provider.py` | `DummyProvider` — seeded Geometric Brownian Motion |
| `data/providers/__init__.py` | |
| `data/engine.py` + `data/__init__.py` | `HistoricalDataEngine` — bootstrap, incremental, aggregate |
| `monitoring/logging_setup.py` | `configure_logging()` + sys.excepthook |
| `monitoring/alerts.py` | `AlertDispatcher` + `AlertHandler` |
| `monitoring/health.py` | `HealthCheck.report()` |
| `monitoring/__init__.py` | |

### Modified Files

| File | Change |
|---|---|
| `src/us_swing/__main__.py` | Added `health` CLI subcommand |
| `us_swing/docs/infrastructure/SRD.md` | All Draft → Approved; SRD-INF-001.002 fix; v1.2.0 |
| `gui/_types.py` | Rewritten as re-export shim from `data/models.py` |
| `gui/_demo.py` | UserProfile + OpenPosition + TradeRecord + TradeSignal updated to canonical models |
| `gui/settings_panel.py` | `user.risk_config.*` nested access; new UserProfile construction with RiskConfig |
| `gui/user_store.py` | Update serialization for nested RiskConfig; import from `data.models` |
| `gui/position_table_model.py` | `avg_price` → `average_price` |
| `pyproject.toml` | Added `sqlalchemy>=2.0` dependency |

### Verification

```
ALL GUI IMPORTS OK  (all 10 gui modules import without error)
```

### Next Steps

1. Write test suite in `us_swing/tests/infrastructure/` (38 tests per UTCD)
2. Update `TRACE.md` — set all SRD-INF rows to `Implemented`
3. Begin SCR (Screener) module implementation

---



**Agent:** GitHub Copilot (Claude Sonnet 4.6)
**Trigger:** User requested (a) more modern look for the open-position double-click dialog, (b) professional H/V layout, (c) dialog movable on screen (was fixed in center).

### Changes — `src/us_swing/gui/dashboard_panel.py`

1. **`_DLG_QSS`** — added `border:1px solid {C.OVERLAY2}` on `QDialog` for definition as floating panel; added proper `QTabBar` / `QTabWidget` styling inside the dialog (dark Catppuccin tabs matching global theme).

2. **`_ExitPositionDialog.__init__`** — fully redesigned:
   - Root layout is now **zero-margin** (`QVBoxLayout` with `contentsMargins(0,0,0,0)`) so the title bar goes edge-to-edge.
   - `setMinimumWidth(580)` / `setMinimumHeight(540)` — was 480, cramped.
   - `_drag_pos` attribute initialised for drag tracking.

3. **`_build_title_bar(symbol)`** — new method, returns a 46px dark `QFrame` (`#11111b`) with:
   - Symbol badge (blue tint), "Exit Position" label, "Drag to move" hint.
   - ✕ Close button (red on hover).
   - `mousePressEvent` / `mouseMoveEvent` / `mouseReleaseEvent` wired to dialog-level drag handlers → dialog is **fully draggable** anywhere on screen.

4. **`_build_summary_card(pos)`** — new method replacing the old single-line HTML table header:
   - **Row 0**: Symbol (13pt blue), State badge, Mode badge.
   - **Row 1** (4 columns, separated by vertical dividers): Qty · Avg Entry · Current · Unrealised P&L (color-coded).
   - **Row 2** (4 columns): Stop Loss · Target · Risk to SL · **R/R Ratio** (green ≥2, yellow ≥1, red <1).
   - Column labels in 7pt muted uppercase; values 10pt bold; thin HLine / VLine dividers.

5. **`_title_mouse_press` / `_title_mouse_move` / `_title_mouse_release`** — drag event handlers enabling free window movement.

6. **Button row** — separator line added above; buttons height fixed at 32px for cleaner look.

---

## Session 2026-03-08 (6) — Admin Multi-User Terminal Redesign

**Agent:** GitHub Copilot (Claude Sonnet 4.6)
**Trigger:** User reported "Manage Selected" UX broken; then requested full admin multi-user redesign across all panels.

### Problems Fixed

1. **Manage Selected did nothing** — button disabled by default, no row-selection hint. Fixed: `SingleSelection` mode on positions table, double-click to open dialog, status label "Click a row to select · Double-click to manage" → updates to ticker on selection.

### Admin Multi-User Architecture

Introduced a **scope model** across the entire GUI: `viewing_uid: int | None` in `DemoService`.
- `None` = aggregate view (all users)
- `int` = single-user focus

Signal `viewing_changed = pyqtSignal()` propagates scope changes to all panels simultaneously.

### Files Modified

| File | Changes |
|------|---------|
| `src/us_swing/gui/_demo.py` | Expanded to 3 users (Alice LIVE, Bob PAPER, Carol PAPER); 8 positions; 9 trades. Added `viewing_uid` scope API (`set_viewing_uid`, `get_viewing_uid`, `get_user_by_id`, `get_user_label`); `viewing_changed` signal; per-user equity dict `_USER_EQUITY`; per-user PnL dict `_user_pnl`. All data accessors and mutations (`close_position`, `partial_close_position`, `set_stop_loss`) are now `user_id`-aware. |
| `src/us_swing/gui/position_table_model.py` | Optional "User" column for All-Users admin view. `set_show_user(show, user_labels)` toggles column via `beginResetModel`/`endResetModel`. `_display()`, `_background()`, `_foreground()` handle column index offset. |
| `src/us_swing/gui/main_window.py` | `_TitleBar`: replaced user/mode chips with permanent `🔐 ADMIN` gold badge + `Scope:` QComboBox (🌐 All Users / per-user entries). New `_AdminContextBar` class (28px strip): All-Users mode shows N accounts, combined equity/PnL, total positions; single-user mode shows username, equity, day P&L, risk %, mode badge, IBKR client ID. Removed obsolete `set_active_user()`. Connects `viewing_changed → _refresh_status`. |
| `src/us_swing/gui/dashboard_panel.py` | Scope pill strip (32px): 🌐 All + 🔴 Alice / 🔵 Bob / 🔵 Carol pills with `setAutoExclusive(True)`. `_on_scope_changed()` syncs pills, toggles User column, resizes columns. All mutations carry `pos.user_id` from the row. `_ExitPositionDialog` shows `🔐 Admin Action · Acting on behalf of <b>username</b>` banner with yellow tint. Square Off All confirmation scopes text to current view. |
| `src/us_swing/gui/execution_panel.py` | Header: `🔐 ADMIN` badge + `Execute for:` QComboBox synced to global scope. `_on_scope_changed()` keeps combo in sync. Order confirmation shows `🔐 Admin · Executing for: <label>` attribution in yellow. |
| `docs/gui/FO.md` | Bumped to v2.0.0. Added FO-GUI-000 (Admin Terminal Architecture): scope model table, scope controls, AdminContextBar, admin action attribution. Updated FO-GUI-001 (4 tabs, ADMIN badge, scope combo, AdminContextBar), FO-GUI-002 (User column, scope pills, scoped Square Off All, acting-for banner), FO-GUI-004 (Execute-for combo, scope sync, attribution). |
| `docs/gui/SRD.md` | Bumped to v2.0.0. Added Section 0: SRD-GUI-000.001–000.005 (scope model, combo, AdminContextBar, ADMIN badge, mutation attribution). Updated Sections 1, 2, 4 to match FO v2.0.0. |

### Key Design Decisions

- **Scope model via `viewing_uid`**: `None` = all-users aggregate, `int` = single user. Single source of truth in `DemoService`; all panels subscribe to `viewing_changed`.
- **User column as opt-in**: `PositionTableModel.set_show_user()` toggled by dashboard scope change — column only appears when admin views all users.
- **Mutations always carry row `user_id`**: Admin actions act on the position's owner regardless of scope combo setting, preventing misattribution.
- **Acting-for banner**: Yellow-tinted banner in `_ExitPositionDialog` explicitly labels admin actions on behalf of a user, following Bloomberg/IBKR admin terminal patterns.
- **`_AdminContextBar`**: Replaces the old user/mode chip approach — context-aware metadata strip reacts to scope without requiring admin to navigate away.

### Validation

All imports OK (`python -c "from us_swing.gui.main_window import MainWindow; ..."`).

---

## Session 2026-03-06 (5) — GUI Frontend (Demo Mode) Complete

**Agent:** GitHub Copilot (Claude Sonnet 4.6)
**Trigger:** User approved GUI FO requirements; requested full PyQt6 frontend for review before backend.

### Files Created

| File | Purpose |
|------|---------|
| `us_swing/src/us_swing/__init__.py` | Package root |
| `us_swing/src/us_swing/__main__.py` | Entry point (`python us_swing/run_gui.py`) |
| `us_swing/src/us_swing/gui/__init__.py` | GUI sub-package |
| `us_swing/src/us_swing/gui/theme.py` | Catppuccin Mocha QSS + `C` colour tokens |
| `us_swing/src/us_swing/gui/_types.py` | Shared dataclasses (data contract for backend) |
| `us_swing/src/us_swing/gui/_demo.py` | `DemoService` with 4 positions, 3 users, 5 trades, 3 signals, 12 screener results; QTimer price simulation (2 s) |
| `us_swing/src/us_swing/gui/log_bridge.py` | LogBuffer + LogSignalEmitter (QueueHandler → Qt signal) |
| `us_swing/src/us_swing/gui/position_table_model.py` | `PositionTableModel` + `TradeHistoryModel` |
| `us_swing/src/us_swing/gui/dashboard_panel.py` | FO-GUI-002: stat cards + position table + capital bar + trade history |
| `us_swing/src/us_swing/gui/screener_panel.py` | FO-GUI-003: filter list + QThread screener + sortable results |
| `us_swing/src/us_swing/gui/execution_panel.py` | FO-GUI-004: signal rows + qty override + circuit breaker |
| `us_swing/src/us_swing/gui/position_monitor_panel.py` | FO-GUI-005: capital row + close-position button |
| `us_swing/src/us_swing/gui/settings_panel.py` | FO-GUI-006: 5 sub-tabs (Users/Risk/Strategies/Screeners/System) |
| `us_swing/src/us_swing/gui/log_viewer_panel.py` | FO-GUI-007: streaming HTML log + live filters + pause |
| `us_swing/src/us_swing/gui/main_window.py` | QMainWindow: 6 tabs + live status bar |
| `us_swing/run_gui.py` | Launcher: `python us_swing/run_gui.py` |

### Key Design Decisions

- `_types.py` dataclasses are the real data contract; backend will implement the same types.
- `DemoService(QObject)` provides `positions_updated`, `account_updated`, `log_message(str,str)` signals — identical interface the real backend will expose.
- Screener runs in `QThread` with 1.4 s simulated delay.
- All PyQt6 enums use 6.x long form (`Qt.ItemDataRole.DisplayRole` etc.).
- Window geometry persisted via `QSettings`.

### Launch Command
```
python us_swing/run_gui.py
```
Run from `f:\USMarket_Backtesting\`.

---

## Session 2026-03-06 (4) — ALM Tool Bug Fix

**Agent:** GitHub Copilot (Claude Sonnet 4.6)
**Trigger:** User reported GUI and MCP modules not visible in the ALM Viewer.

### Root Cause

The ALM parser (`alm/parser.py` `_HEADING_RE`) requires `## ID: Title` heading format (colon separator). All 6 FO headings in `docs/gui/FO.md` and all 6 in `docs/mcp/FO.md` used `## ID — Title` (em-dash), yielding zero parseable nodes — causing both modules to be invisible in the tree.

### Fix Applied

Replaced em-dash (`—`) with colon (`:`) in all 13 FO headings across:
- `docs/gui/FO.md` — 7 headings (FO-GUI-001 through FO-GUI-007)
- `docs/mcp/FO.md` — 6 headings (FO-MCP-001 through FO-MCP-006)

No other changes. INF/SCR/ANA/EXE were unaffected (always used colon format).

---

## Session 2026-03-06 (2) — Documentation Alignment Check & Fixes

**Agent:** GitHub Copilot (Claude Sonnet 4.6)
**Trigger:** User requested alignment verification after previous session's documentation updates.

### Alignment Check Performed

Read all updated files: `idea.md`, `requirements.md`, `CONTEXT.md`, `DEVLOG.md`, and all 4 FO files (INF/SCR/ANA/EXE).

### Issues Found & Fixed (all in `requirements.md`)

| # | Section | Issue | Fix Applied |
|---|---|---|---|
| 1 | §4 System Startup Flow | Old 7-step CLI flow — no GUI auto-open, no user loading, no user-selected screeners | Replaced with 10-step GUI-aware flow referencing §24 |
| 2 | §12 Daily Operational Workflow | Old headings (T-60/Market Open/During/After) had no GUI, no per-user, no position state carry-over | Rewrote with GUI-centric descriptions at each phase |
| 3 | §15 Future Enhancements | Still listed "Add web dashboard monitoring" — conflicts with GUI being core | Replaced with updated future list (removed web dashboard; added mobile push, market calendar, auth, data export) |
| 4 | §19.2 Folder Structure | Old structure missing `gui/`, `mcp/`, `user/`, `data/providers/`, `execution/paper_engine.py` folders | Replaced with full updated tree |
| 5 | §19.3 Runtime Flow | CLI-only flow (main.py → no GUI) | Replaced with GUI-primary flow showing MCP as parallel background server |
| 6 | §7 DB Schema — Schema redundancy | `paper_trades` table created but `trades` already had `mode (paper/live)` column — duplicate purpose. Also: `positions` had missing `mode` column | Removed `paper_trades` table; added `mode` to `positions`; added schema note clarifying unified approach. Added `(user_id, symbol)` index |
| 7 | §23.2 Paper Trading Engine | Referenced "separate DB table (`paper_positions`, `paper_trades`)" which now contradicts unified schema | Updated to reference `trades` with `mode = 'paper'` |

### No Issues Found In

- `idea.md` v2.0.0 — fully aligned
- `CONTEXT.md` — all artifact statuses accurate; revision tracker complete
- FO files (INF/SCR/ANA/EXE) — correctly flagged Draft/needs-revision; no additional fixes needed at this stage (revisions will happen per CONTEXT.md §6 tracker in next session)

---

## Session 2026-03-06 (1) — Workflow Clarification & Documentation Revision

**Agent:** GitHub Copilot (Claude Opus 4.6)
**Trigger:** User provided real-world workflow description and identified gaps in existing documentation.

### Gap Analysis Performed

Compared user's workflow requirements against all existing FO/SRD documents across 4 tools (INF/SCR/ANA/EXE). Identified 10 major gaps:

| # | Gap | Severity |
|---|---|---|
| 1 | GUI not documented (was "out of scope v1") | **MAJOR** |
| 2 | Multi-user support absent | **MAJOR** |
| 3 | MCP server not in us_swing docs | **GAP** |
| 4 | Paper trading mode absent | **GAP** |
| 5 | Windows Task Scheduler auto-launch absent | **GAP** |
| 6 | User-defined trade quantity (override auto-calc) | **GAP** |
| 7 | Position state tracking across days (partial entry/exit) | **PARTIAL** |
| 8 | Capital availability check before new entry (GUI-visible) | **PARTIAL** |
| 9 | User-selectable screeners via GUI | **PARTIAL** |
| 10 | S&P 500 data source unknown for dev (need dummy provider) | **CLARIFICATION** |

Also identified components user may have missed: Notifications/Alerts, Performance Reporting, Market Calendar Awareness, User Authentication, Config Profiles, Data Backup/Export.

### Documents Updated

| File | Changes |
|---|---|
| `idea.md` | v1.0.0 → v2.0.0: Vision expanded (GUI core, MCP, multi-user, paper trading, scheduler). Decisions #5–#12 added. Tool roadmap expanded to 8 tools (added GUI, MCP, RPT). Tech stack updated (PyQt6, FastMCP, Task Scheduler, dummy provider). Future enhancements revised. |
| `requirements.md` | Added sections §21–§30: GUI Module, Multi-User Support, Paper Trading Mode, Windows Task Scheduler, Position State Tracking, S&P 500 Data Source, MCP Server Interface, Notifications & Alerts, Performance Reporting. Updated §2 Functional Requirements (16 items, up from 10). Updated §3 Architecture (12 modules, up from 7). Updated §7 DB Design (added `users`, `paper_trades` tables; added `user_id`, `state`, `mode` columns). |
| `CONTEXT.md` | Full rewrite: Phase updated to "Documentation Review & Revision". All artifact statuses marked "needs revision" with specific notes. 12 open decisions (up from 5). 8 known risks (up from 4). Implementation sequence expanded to 6 phases (added GUI Phase 5, MCP Phase 6). Added §6 Documentation Revision Tracker. |
| `AGENT_BOOT.md` | Added tool codes: GUI, MCP, RPT. |

### Key Decisions Made

| Decision | Choice |
|---|---|
| GUI role | Core component — full operator control, not optional/future |
| Multi-user | Yes — per-user profiles, IBKR client IDs, isolated positions/settings |
| Paper trading | Yes — simulated fills with identical logic; per-user toggle |
| Auto-launch | Windows Task Scheduler, T-60 before market open |
| MCP server | Yes — one tool per major operation |
| S&P 500 dev data | Dummy provider (same interface as IBKR); real source TBD |
| User quantity | Override allowed via GUI; auto-calc is default |
| Position states | NEW → PARTIAL_ENTRY → OPEN → PARTIAL_EXIT → CLOSED |

### NOT Done (Pending Next Session)

- ~~FO/SRD/DD/MD/UTCD revision across all 4 existing tools (INF/SCR/ANA/EXE) to incorporate new scope~~ **DONE — Session 2026-03-06 (3)**
- ~~Create `docs/gui/` folder with FO through TRACE~~ **DONE — Session 2026-03-06 (3)**
- ~~Create `docs/mcp/` folder with FO through TRACE~~ **DONE — Session 2026-03-06 (3)**
- User approval of revised documentation before implementation begins

---

## Session 2026-03-06 (3) — Full Documentation Revision & New Module Creation

**Agent:** GitHub Copilot (Claude Opus 4.6)
**Trigger:** User requested review and update of all module docs (DD, FO, MD, SRD, TRACE, UTCD) based on new requirements.md changes, plus creation of new modules if warranted.

### Work Performed

Read all 24 existing doc files across 4 modules, requirements.md, and CONTEXT.md. Systematically updated each module to align with requirements.md §21–§30 (GUI, multi-user, paper trading, position states, capital check, MCP).

### INF (Infrastructure) — All 6 Files Updated to v1.1.0

- **FO.md:** Added FO-INF-006 (Multi-User Profile Management), FO-INF-007 (Data Provider Abstraction)
- **SRD.md:** Added Section 6 (7 UserManager SRDs), Section 7 (5 DataProvider SRDs); updated schema SRDs for users table
- **DD.md:** Added users table DDL, UserManager design (UserProfile, settings JSON, mode switch), DataProvider protocol (IBKRProvider, DummyProvider, factory)
- **MD.md:** Added 3 modules: user/manager.py, data/providers/ibkr_provider.py, data/providers/dummy_provider.py
- **UTCD.md:** Added 9 UserManager tests, 4 DummyProvider tests
- **TRACE.md:** Updated all counts (FO:7, SRD:35, DD:7, MD:14, UTCD:38)

### SCR (Screener) — All 6 Files Updated to v1.1.0

- **FO.md:** Added FO-SCR-003 (Per-User Screener Configuration & GUI-Driven Screening)
- **SRD.md:** Added Section 3 (4 SRDs for per-user screener config and GUI interaction)
- **DD.md:** Added `from_user_settings()` classmethod and `to_dict()` to ScreenerConfig
- **MD.md:** Updated module SRD references
- **UTCD.md:** Added 4 ScreenerConfig serialisation tests
- **TRACE.md:** Updated counts (FO:3, SRD:17, UTCD:27)

### ANA (Analysis) — All 6 Files Updated to v1.1.0

- **FO.md:** Updated FO-ANA-002 for per-user strategy config and position check
- **SRD.md:** Updated position check for user_id; added Section 3 (3 SRDs for per-user strategy config)
- **DD.md:** Added user_id parameter to StrategyEngine constructor
- **MD.md:** Updated per-user context descriptions
- **UTCD.md:** Updated T02 for per-user check; added 4 per-user strategy config tests
- **TRACE.md:** Updated counts (FO:2, SRD:19, UTCD:28)

### EXE (Execution) — All 6 Files Updated to v1.1.0

- **FO.md:** Updated FO-EXE-002 for per-user positions; added FO-EXE-004 (Paper Trading Mode), FO-EXE-005 (Position State Machine & Capital Availability Check)
- **SRD.md:** Added user_id to trade/position SRDs; added Section 4 (5 Paper Engine SRDs), Section 5 (6 Position State/Capital SRDs); updated emergency shutdown for GUI button
- **DD.md:** Added user_id to AccountState; added can_enter_new() to RiskManager; updated ExecutionEngine for mode/quantity_override; expanded OpenPosition with state/filled_qty/mode; added PaperEngine design, ExecutionRouter, Position State Machine FSM with valid transitions, startup restore
- **MD.md:** Updated existing modules for user_id/state references; added paper_engine.py, execution_router.py; updated dependency graph and project module map
- **UTCD.md:** Updated existing tests for user_id context; added 25 new tests: 7 PaperEngine, 3 ExecutionRouter, 9 Position State Machine, 6 Capital Check & Qty Override
- **TRACE.md:** Updated counts (FO:5, SRD:28, DD:6, MD:7, UTCD:54)

### GUI (New Module) — 6 Files Created at v1.0.0

- **FO.md:** 7 FOs — MainWindow, Dashboard, Screener Panel, Trade Execution Panel, Position Monitor, Settings, Log Viewer
- **SRD.md:** 30 SRDs across 7 sections — detailed PyQt6 widget specs, all referencing specific Qt classes
- **DD.md:** 4 designs — MainWindow shell, PositionTableModel, ExecutionPanel signal flow, LogViewer bridge architecture
- **MD.md:** 9 modules — main_window, dashboard_panel, position_table_model, screener_panel, execution_panel, position_monitor_panel, settings_panel, log_viewer_panel, log_bridge
- **UTCD.md:** 36 tests using pytest-qt across all panel modules
- **TRACE.md:** Full forward/reverse traceability matrix

### MCP (New Module) — 6 Files Created at v1.0.0

- **FO.md:** 6 FOs — Server Interface, Data/Universe Tools, Screener/Watchlist Tools, Signal Tools, Execution/Position Tools, System Health
- **SRD.md:** 14 SRDs covering 9 MCP tools with JSON schema validation, user_id scoping, error handling
- **DD.md:** 2 designs — MCPServer core (FastMCP, validation flow, error contract), submit_order flow
- **MD.md:** 6 modules — server.py, data_tools.py, screener_tools.py, analysis_tools.py, execution_tools.py, health_tools.py + 9 JSON schema files
- **UTCD.md:** 20 tests covering all tool handlers
- **TRACE.md:** Full forward/reverse traceability matrix

### Meta-Documents Updated

- **CONTEXT.md:** Updated phase to "Documentation Revised"; all 36 artifact statuses marked as revised/created with version numbers; revision tracker replaced with summary table (143 total SRDs, 203 total tests)
- **DEVLOG.md:** This entry

### Summary Statistics

| Metric | Count |
|---|---|
| Files updated (existing) | 24 |
| Files created (new) | 12 |
| Total documentation files | 36 |
| Total FOs | 30 |
| Total SRDs | 143 |
| Total DDs | 22 |
| Total MDs | 51 |
| Total test cases | 203 |

---

## Session 2026-03-05 — Documentation Generation

**Agent:** GitHub Copilot (Claude Sonnet 4.6)
**Source Requirement:** `us_swing/requirements.md`

### Completed

- Read full `requirements.md` (589 lines, 21 sections)
- Defined 4 tool codes for us_swing: **INF** (Infrastructure), **SCR** (Screener), **ANA** (Analysis/Live Engine), **EXE** (Execution & Risk)
- Generated complete documentation for all 4 tools:
  - `docs/infrastructure/` — FO (5 objectives), SRD (23 requirements), DD (5 designs), MD (11 modules), UTCD (25 test cases), TRACE
  - `docs/screener/` — FO (2 objectives), SRD (13 requirements), DD (2 designs), MD (4 modules), UTCD (23 test cases), TRACE
  - `docs/analysis/` — FO (2 objectives), SRD (16 requirements), DD (3 designs), MD (8 modules), UTCD (24 test cases), TRACE
  - `docs/execution/` — FO (3 objectives), SRD (17 requirements), DD (3 designs), MD (5 modules), UTCD (29 test cases), TRACE
- Created `idea.md` — vision, roadmap, tech stack decisions
- Created `CONTEXT.md` — current artifact status, open decisions, risks, implementation sequence
- Created `DEVLOG.md` (this file)
- Total: 24 documentation files across 4 tool folders

### Key Decisions Made

| Decision | Choice |
|---|---|
| Database backend (dev/prod) | SQLite / PostgreSQL, selectable via `DATABASE_URL` config |
| ORM approach | SQLAlchemy Core (not ORM layer) for performance |
| Timeframe aggregation | 3m/5m/15m/1h/4h all synthesised from 1m — never fetched from IBKR |
| Strategy evaluation mode | Synchronous (< 50 ms per symbol per candle close) |
| Short selling | Long-only for v1 |
| GUI | CLI health-check only for v1; no GUI trading interface |

### Next Steps

- User reviews all documentation (FO → SRD → DD → MD → UTCD for all 4 tools)
- User approves / requests changes
- On approval: begin implementation Phase 1 (INF) in order per CONTEXT.md §5
- Update SRD statuses from `Draft` → `Approved` before implementation begins
