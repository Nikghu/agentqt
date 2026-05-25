# Module Decomposition — Screener (SCR)

**Document ID:** MD-SCR
**Version:** 2.2.0
**Traces To:** DD-SCR v2.1.0
**Status:** Draft
**Last Updated:** 2026-05-06
**Project:** US Swing Trading System

---

## SCR Modules v2.0

| ID | Parent SRD | File | Responsibility | Public API | Deps | Status |
|---|---|---|---|---|---|---|
| MD-SCR-001.001.M01 | SRD-SCR-001.001–009 | `src/us_swing/screener/preset.py` | Preset dataclass + data model; serialization (to_dict / from_dict); validation (validate). ScreenerRef, ScreenerGroup helpers. Includes `trading_styles` field (SRD-001.009). | `Preset`, `ScreenerRef`, `ScreenerGroup`, `PresetType`, `_VALID_STYLES`, errors | `dataclasses`, `datetime`, `enum` | Approved |
| MD-SCR-001.002.M02 | SRD-SCR-002.001 | `src/us_swing/screener/base.py` | Screener protocol (abstract interface). Defines apply(), batch_features() signatures. Error classes: ScreenerError, ScreenerNotFoundError. | `Screener` (Protocol), `ScreenerError` | `typing.Protocol` | Approved |
| MD-SCR-001.003.M03 | SRD-SCR-002.001–002 | `src/us_swing/screener/registry.py` | ScreenerRegistry singleton — register(), get(), list_available() methods. Instantiates screeners on demand. | `ScreenerRegistry`, registration decorators | `base.py` | Approved |
| MD-SCR-002.001.M04 | SRD-SCR-002.003, SRD-SCR-012.001–012.005 | `src/us_swing/screener/screeners/indicator.py` | IndicatorScreener plugin: wraps v1 filter logic (RSI, ATR, Range, Breakout, Volume). Computes RS line and RS percentile rank vs benchmark (SPY). Implements Screener protocol. apply() returns identical results to v1 when RS params are at defaults. Raises `BenchmarkDataUnavailableError` if SPY bars absent. | `IndicatorScreener`, `BenchmarkDataUnavailableError`, `InsufficientUniverseDataError`, `compute_rs_line(symbol_bars, spy_bars, slope_days) -> list[float]`, `compute_rs_rank(symbol_252d_return, universe_returns) -> float` | `base.py`, `analysis/indicators.py`, `data/models.py`, `filters` (legacy), `db/manager.py` (SPY bar fetch), `SystemConfig.benchmark_symbol` | Approved |
| MD-SCR-002.002.M05 | SRD-SCR-002.004 | `src/us_swing/screener/screeners/ml.py` | MLScreener plugin: loads trained model, extracts features, runs inference. Stub for v2.0 (model_path required). | `MLScreener` | `base.py`, model loading library (sklearn/joblib) | Approved |
| MD-SCR-002.003.M06 | SRD-SCR-002.005, SRD-SCR-013.005 | `src/us_swing/screener/screeners/cloud_ai.py` | CloudAIScreener plugin: OpenRouter-backed ranking screener (Stage 3 only). batch_features() extracts indicators; apply() runs legacy single-shot or tool-augmented agentic loop via get_candle_data. Handles retries, rate limits, cost tracking. | `CloudAIScreener` | `base.py`, `openai` SDK (OpenRouter-compat), `storage.py`, `_tool_executor.py` | Approved |
| MD-SCR-013.001.M19 | SRD-SCR-013.001 | `src/us_swing/screener/screeners/_cloud_ai_models.py` | Cloud AI model registry: DEFAULT_MODEL, OPENROUTER_BASE, MODEL_PRESETS, FREE_MODEL_PRESETS, ALL_MODEL_PRESETS, LEGACY_MODEL_MIGRATION. supports_tool_use() helper. | `DEFAULT_MODEL`, `OPENROUTER_BASE`, `MODEL_PRESETS`, `FREE_MODEL_PRESETS`, `ALL_MODEL_PRESETS`, `LEGACY_MODEL_MIGRATION`, `supports_tool_use()` | `typing.Final` | Draft |
| MD-SCR-002.004.M07 | SRD-SCR-002.006 | `src/us_swing/screener/screeners/llm_local.py` | LLMLocalScreener plugin: local LLM via ollama/similar. Stub for v2.0; MVP may skip. | `LLMLocalScreener` | `base.py`, ollama API client | Approved |
| MD-SCR-002.005.M08 | SRD-SCR-002.007 | `src/us_swing/screener/screeners/price_action.py` | PriceActionScreener plugin: detects 5 OHLCV-based price action patterns (proximity_52w_high, volume_breakout, nr7_compression, ema_pullback, engulfing). Each independently configurable. Score = matched/enabled; passed if score ≥ threshold (default 0.2). | `PriceActionScreener`, `screener_id="price_action"`, `apply(symbols, bars, config) -> dict[str, tuple[bool, float]]`, `batch_features(symbols, bars) -> {}` | `base.py`, `analysis/indicators.py` (`ema()`) | Approved |
| MD-SCR-002.006.M09 | SRD-SCR-002.008 | `src/us_swing/screener/screeners/mcp.py` | MCPScreener plugin: external MCP tool integration. Stub for v2.0. | `MCPScreener` | `base.py`, MCP client | Approved |
| MD-SCR-003.001.M10 | SRD-SCR-003.001–008 | `src/us_swing/screener/executor.py` | PresetExecutor — orchestrates 3-stage pipeline. run_preset() main entry point. Handles pre-filter, parallel execution, LLM ranking, result serialization. | `PresetExecutor` | `preset.py`, `registry.py`, `base.py`, `db/manager.py`, `storage.py`, `utils.py`, `app_service` | Draft |
| MD-SCR-004.001.M11 | SRD-SCR-004.001–006 | `src/us_swing/screener/scheduler.py` | ScreenerScheduler — cron job scheduling. schedule(), unschedule(), get_schedule(). Persistence to JSON. Uses APScheduler. | `ScreenerScheduler` | `executor.py`, `apscheduler` | Draft |
| MD-SCR-005.001.M12 | SRD-SCR-005.001–008 | `src/us_swing/screener/manager.py` | PresetManager — CRUD + permissions. create(), load(), list_admin(style_filter), list_user(style_filter), update(), delete(), grant_access(), revoke_access(). Private _apply_style_filter() helper (SRD-005.004). Handles v1 migration. | `PresetManager`, `_apply_style_filter()`, permission errors | `preset.py`, `storage.py` | Draft |
| MD-SCR-006.001.M13 | SRD-SCR-008.001–005 | `src/us_swing/screener/storage.py` | ScreenerResultsStorage: save/load results. FeatureCache: per-symbol-per-day caching (24h TTL). APIUsageTracker: logs Claude API usage + costs. All atomic file I/O. | `ScreenerResultsStorage`, `FeatureCache`, `APIUsageTracker` | `pathlib`, `json`, `datetime` | Draft |
| MD-SCR-003.001.M14 | SRD-SCR-003.001, SRD-SCR-010.001–004 | `src/us_swing/screener/utils.py` | Shared utilities: PreFilter class (price, volume, halted checks). Error classes. Parallelization helpers. | `PreFilter`, error classes, `parallel_execute()` | `data/models.py` | Approved |
| MD-SCR-008.001.M15 | SRD-SCR-009.001–004 | `src/us_swing/screener/__init__.py` | Package init. Imports + exports. Register built-in screeners at module load. v1 migration trigger. | package exports, `migrate_v1_presets()` | all modules above | Draft |
| MD-SCR-007.010.M16 | SRD-SCR-007.001–010 | `src/us_swing/screener/gui/screener_panel.py` | ScreenerPanel tab widget. Preset selector dropdown, style filter `QComboBox`, "Run Now" button, results table, status bar, historical date picker, Export CSV. On style filter change: calls `PresetManager.list_admin_presets(style_filter)` and `list_user_presets(user_id, style_filter)` and rebuilds preset dropdown. | `ScreenerPanel` | `manager.py`, `executor.py`, `storage.py`, PyQt6 | Draft |
| MD-SCR-007.011.M17 | SRD-SCR-007.002–005, 007.011–012 | `src/us_swing/screener/gui/preset_builder.py` | PresetBuilderPanel modal + helpers. Drag-and-drop screener builder, AND/OR group toggling, collapsible config panels, trading style `QGroupBox` (3 checkboxes, editable vs. read-only badge mode), `AssignUsersWidget` (tokenised input; immediate grant/revoke on token add/remove; error badge for invalid IDs), Save / Save As / preview. | `PresetBuilderPanel`, `AssignUsersWidget`, `_UserTag` | `manager.py`, `preset.py`, `registry.py`, PyQt6 | Draft |
| MD-SCR-011.001.M18 | SRD-SCR-013.003–004 | `src/us_swing/screener/screeners/_tool_executor.py` | `CandleToolExecutor` — bridges AI provider `get_candle_data` tool calls to `DatabaseManager.fetch_bars()`. Enforces Stage-2 symbol allowlist, per-symbol call cap (default 3), validates `lookback_bars ≤ 300` and `timeframe ∈ {1d, 1w}`. Returns errors as JSON to the model (never raised) so the agentic loop can continue. Single-use per provider run. | `CandleToolExecutor`, `TOOL_NAME = "get_candle_data"` | `db/manager.py`, `data/models.py` | Draft |
| MD-SCR-014.008.M20 | SRD-SCR-014.008 | `src/us_swing/gui/ai_model_store.py` | Persistent JSON store for user-defined custom AI models. Merges built-in model presets with custom entries for the Cloud AI config dialog. Provides OpenRouter probe-based model validation. | `CustomAIModel`, `load_custom_models()`, `save_custom_models()`, `all_model_rows()`, `validate_model(model_id, api_key) -> tuple[bool, str]` | `screener/screeners/_cloud_ai_models.py`, `screener/screeners/_api_key_store.py`, `openai` (lazy) | Implemented |

---

## Dependency Graph (Detailed)

```
screener/
├─ __init__.py
│  ├─ imports all modules
│  ├─ calls ScreenerRegistry.register() for built-in screeners
│  └─ calls migrate_v1_presets() on first run
│
├─ preset.py
│  ├─ Preset, ScreenerRef, ScreenerGroup dataclasses
│  └─ no deps on other screener modules
│
├─ base.py
│  ├─ Screener protocol
│  └─ error classes
│
├─ registry.py
│  ├─ ScreenerRegistry
│  └─ ← base.py
│
├─ screeners/
│  ├─ __init__.py
│  ├─ indicator.py
│  │  ├─ IndicatorScreener
│  │  ├─ ← base.py
│  │  ├─ ← analysis/indicators.py (shared)
│  │  └─ ← filters.py (v1, for refactoring)
│  ├─ ml.py
│  │  ├─ MLScreener
│  │  └─ ← base.py
│  ├─ llm_claude.py
│  │  ├─ LLMClaudeScreener
│  │  ├─ ← base.py
│  │  └─ ← anthropic SDK
│  ├─ llm_local.py
│  │  ├─ LLMLocalScreener (stub)
│  │  └─ ← base.py
│  ├─ price_action.py (optional)
│  │  ├─ PriceActionScreener
│  │  └─ ← base.py
│  └─ mcp.py (optional)
│     ├─ MCPScreener (stub)
│     └─ ← base.py
│
├─ executor.py
│  ├─ PresetExecutor
│  ├─ ← preset.py
│  ├─ ← registry.py
│  ├─ ← base.py
│  ├─ ← db/manager.py (fetch bars)
│  ├─ ← storage.py (persist results)
│  ├─ ← utils.py (pre-filter, errors)
│  └─ ← app_service (universe, events)
│
├─ scheduler.py
│  ├─ ScreenerScheduler
│  ├─ ← executor.py
│  └─ ← apscheduler
│
├─ manager.py
│  ├─ PresetManager
│  ├─ ← preset.py
│  └─ ← storage.py
│
├─ storage.py
│  ├─ ScreenerResultsStorage
│  ├─ FeatureCache
│  ├─ APIUsageTracker
│  └─ (no internal screener deps; pure file I/O)
│
├─ utils.py
│  ├─ PreFilter, error classes, parallel helpers
│  ├─ ← data/models.py
│  └─ ← multiprocessing, asyncio
│
└─ gui/
   ├─ screener_panel.py
   │  ├─ ScreenerPanel
   │  ├─ ← manager.py (list_admin_presets, list_user_presets with style_filter)
   │  ├─ ← executor.py (run_preset)
   │  └─ ← storage.py (load_result)
   └─ preset_builder.py
      ├─ PresetBuilderPanel, AssignUsersWidget, _UserTag
      ├─ ← manager.py (grant_access, revoke_access)
      ├─ ← preset.py (Preset dataclass)
      └─ ← registry.py (list_available screeners)
```

---

## Cross-Module Integration Points

### 1. **Screener Discovery & Registration**

```python
# In screener/__init__.py:
from screener.registry import ScreenerRegistry
from screener.screeners.indicator import IndicatorScreener
from screener.screeners.ml import MLScreener
from screener.screeners.llm_claude import LLMClaudeScreener

# Register built-ins
ScreenerRegistry.register("indicator_composite", IndicatorScreener)
ScreenerRegistry.register("ml_ensemble_v3", MLScreener)
ScreenerRegistry.register("llm_claude_ranking", LLMClaudeScreener)
```

### 2. **Preset Execution Flow**

```python
# In app_service or GUI handler:
executor = PresetExecutor(db=DatabaseManager(), app_service=self)
result = executor.run_preset(preset_id="daily_rsi", user_id="user1", manual=True)
# Internally:
#  1. PresetManager.load_preset() → Preset instance
#  2. PreFilter.apply() → filtered symbols
#  3. ScreenerRegistry.get() for each screener → Screener instances
#  4. Screener.apply() in parallel → results
#  5. Composite/Weighted logic → combined results
#  6. (Optional) Screener.batch_features() + LLMClaudeScreener.apply() → ranked results
#  7. ScreenerResultsStorage.save_result() → file
#  8. emit_event("screener_run_completed")
```

### 3. **GUI Integration**

```python
# In gui/screener_panel.py:
from screener.manager import PresetManager
from screener.executor import PresetExecutor
from screener.storage import ScreenerResultsStorage

pm = PresetManager()
executor = PresetExecutor(...)
storage = ScreenerResultsStorage()

# Load presets for dropdown (style_filter=None = "All Styles")
admin_presets = pm.list_admin_presets(style_filter=style_filter)
user_presets = pm.list_user_presets(active_user_id, style_filter=style_filter)

# On "Run Now" click
result = executor.run_preset(selected_preset_id, active_user_id, manual=True)
# → display results in table

# On date picker
result = storage.load_result(preset_id, selected_date)
# → display historical results
```

### 4. **Scheduler Integration**

```python
# In main app startup:
from screener.scheduler import ScreenerScheduler

scheduler = ScreenerScheduler(executor=executor)
scheduler.start()  # Loads persisted schedules and begins listening
# → On cron trigger: executor.run_preset(preset_id, user_id, manual=False)
```

### 5. **Cost Tracking Integration (LLM)**

```python
# In screener/screeners/llm_claude.py:
from screener.storage import APIUsageTracker

tracker = APIUsageTracker()
# After Claude API call:
tracker.log_usage(preset_id=preset.id, tokens_in=..., tokens_out=...)
# Checks threshold and emits warning if exceeded
```

---

## Shared Dependency: analysis/indicators.py

The `analysis/indicators.py` module (owned by ANA tool) is a **shared utility** imported by:
- `screener/screeners/indicator.py` — for ATR, RSI, EMA calculations
- Any other screener that needs technical indicators

This avoids code duplication and ensures consistency between indicator-based screeners and analysis strategies.

---

## Error Hierarchy

```
ScreenerError (base)
├─ ScreenerNotFoundError
├─ ScreenerValidationError
├─ PresetError (base)
│  ├─ PresetValidationError
│  ├─ PresetAccessDenied
│  └─ PresetNotFoundError
└─ ScreenerExecutionError
   └─ PreFilterError
```

---

## Configuration & Settings

### System Settings (`config/settings.py`)

```python
# Screener / LLM settings
llm_cost_threshold_monthly_usd: float = 50.0
llm_cost_input_per_1k_tokens: float = 0.003
llm_cost_output_per_1k_tokens: float = 0.009
screener_pre_filter_min_price: float = 5.0
screener_pre_filter_min_volume: int = 1_000_000
screener_parallelization_max_workers: int = 4
screener_lm_timeout_seconds: int = 30
```

---

## File Naming Conventions

| Pattern | Purpose | Example |
|---------|---------|---------|
| `src/us_swing/screener/*.py` | Core screener modules | `executor.py`, `manager.py` |
| `src/us_swing/screener/screeners/*.py` | Screener plugins (implementations) | `indicator.py`, `llm_claude.py` |
| `~/.usswing/screener_results/presets_admin/*.json` | Admin preset definitions | `daily_rsi.json` |
| `~/.usswing/screener_results/presets_user/{user_id}/*.json` | User preset definitions | `user1/custom_screener.json` |
| `~/.usswing/screener_results/preset_{id}/{date}.json` | Execution results (dated) | `preset_daily_rsi/2026-04-16.json` |
| `~/.usswing/screener_cache/features_{date}.json` | Feature cache | `features_2026-04-16.json` |
| `~/.usswing/screener_api_usage.json` | LLM API usage log | (single file, appended) |
| `~/.usswing/screener_schedules.json` | Cron schedules | `{"daily_rsi": "0 8 * * 1-5"}` |

---

## Testing Module Locations

| Module | Tests | Location |
|---|---|---|
| `preset.py` | Serialization, validation | `tests/screener/test_preset.py` |
| `registry.py` | Registration, lookup, instantiation | `tests/screener/test_registry.py` |
| `indicator.py` | Filter equivalence to v1 | `tests/screener/test_indicator_screener.py` |
| `ml.py` | Mock model inference | `tests/screener/test_ml_screener.py` |
| `llm_claude.py` | Mocked Claude API, feature extraction | `tests/screener/test_llm_claude_screener.py` |
| `executor.py` | 3-stage pipeline, composite/weighted logic | `tests/screener/test_executor.py` |
| `scheduler.py` | Cron scheduling, persistence | `tests/screener/test_scheduler.py` |
| `manager.py` | CRUD, permissions, migration | `tests/screener/test_manager.py` |
| `storage.py` | Result I/O, feature cache, cost tracking | `tests/screener/test_storage.py` |
| `utils.py` | Pre-filter, error handling | `tests/screener/test_utils.py` |
| `gui/screener_panel.py` | Style filter dropdown, preset dropdown rebuild | `tests/screener/test_screener_panel.py` (Phase 5) |
| `gui/preset_builder.py` | Style checkboxes, AssignUsersWidget grant/revoke | `tests/screener/test_preset_builder.py` (Phase 5) |

---

## Implementation Priority (Recommended Order)

1. **Foundation (non-blocking):**
   - `preset.py` (data model + serialization)
   - `base.py` (protocol)
   - `registry.py` (screener discovery)

2. **Core plugins:**
   - `screeners/indicator.py` (v1 refactor; most critical)
   - `screeners/ml.py` (stub with mock)
   - `screeners/llm_claude.py` (LLM integration)

3. **Orchestration:**
   - `utils.py` (pre-filter, errors)
   - `executor.py` (3-stage pipeline)
   - `storage.py` (result persistence, caching)

4. **Management:**
   - `manager.py` (preset CRUD, permissions)
   - `scheduler.py` (cron scheduling)

5. **Integration:**
   - `__init__.py` (package setup, registration, migration)
   - `gui/screener_panel.py` (style filter dropdown + preset dropdown rebuild)
   - `gui/preset_builder.py` (trading style checkboxes + AssignUsersWidget)

---

**Status:** v2.1.0 Draft — FO-SCR-011 (Phase 1 AI Stock Ranking) module M18 (`_tool_executor.py`) added. Existing modules M01 (`preset.py`), M06 (`llm_claude.py`), M10 (`executor.py`), M16 (`gui/screener_panel.py`) extended with AI-ranking responsibilities — see `RN-SCR-2.1.0-20260425.md`.
