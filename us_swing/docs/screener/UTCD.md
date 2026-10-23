# Unit Test & Coverage Definition — Screener (SCR)

**Document ID:** UTCD-SCR
**Version:** 2.2.0
**Traces To:** MD-SCR v2.1.0
**Status:** Draft
**Last Updated:** 2026-04-25
**Project:** US Swing Trading System

---

## Test Summary

| Module | Test Count | Type | Coverage |
|---|---|---|---|
| `preset.py` | 20 | Unit | Serialization, validation, data structures, trading_styles, ai_query/ai_model (T17–T20) |
| `registry.py` | 6 | Unit | Registration, discovery, lookup |
| `indicator.py` | 16 | Unit | v1 equivalence, filter logic, scoring, RS line, RS rank, benchmark error |
| `ml.py` | 5 | Unit | Model loading, inference, feature extraction |
| `price_action.py` | 8 | Unit | Pattern detection (52w-high, volume breakout, NR7, EMA pullback, engulfing), scoring, edge cases |
| `llm_claude.py` | 15 | Unit | API mocking, legacy ranking path, tool-augmented multi-turn loop, reasoning capture/truncation (T11–T15) |
| `_tool_executor.py` | 10 | Unit | `get_candle_data` routing, allowlist, call cap, lookback/timeframe validation, slicing, JSON error encoding |
| `executor.py` | 22 | Unit | 3-stage pipeline, composite/weighted logic, AI config wiring (T21), ai_reasoning merge (T22) |
| `scheduler.py` | 6 | Unit | Cron scheduling, persistence |
| `manager.py` | 20 | Unit | CRUD, permissions, migration, style_filter |
| `storage.py` | 12 | Unit | Result I/O, feature cache, cost tracking |
| `utils.py` | 8 | Unit | Pre-filter, error classes |
| `gui/screener_panel.py` | 5 | Unit (pytest-qt) | Style filter combo, preset dropdown rebuild — Phase 5 |
| `gui/preset_builder.py` | 8 | Unit (pytest-qt) | Style checkboxes, AssignUsersWidget grant/revoke — Phase 5 |
| **Integration** | 15 | Integration | End-to-end, permissions, concurrency |
| **Total** | **176** | — | — |

---

## Unit Tests by Module

### `tests/screener/test_preset.py` (12 tests)

| ID | Objective | Input | Expected Output | Status |
|---|---|---|---|---|
| T01 | Preset.to_dict() serializes to JSON-compatible format | Preset instance | dict with ISO-8601 datetimes, string enums | Draft |
| T02 | Preset round-trip: from_dict(to_dict()) produces equal instance | Preset + dicts | Deserialized ≡ original | Draft |
| T03 | Composite preset with 2 groups validates correctly | Composite with groups | validate() returns None; no error | Draft |
| T04 | Weighted preset validates: weights sum ~1.0, threshold in [0, 1] | Weighted preset | validate() passes | Draft |
| T05 | Preset.validate() raises PresetValidationError on unknown screener_id | Preset with bad screener_id | PresetValidationError raised | Draft |
| T06 | Preset.validate() raises error on missing threshold (Weighted) | Weighted without threshold | PresetValidationError raised | Draft |
| T07 | Preset.validate() raises error on non-unique group IDs (Composite) | Composite with duplicate group_id | PresetValidationError raised | Draft |
| T08 | ScreenerRef.enabled flag toggles independently | ScreenerRef with enabled=True | can_set(enabled=False) | Draft |
| T09 | ScreenerGroup logic must be "AND" or "OR" | ScreenerGroup(logic="XOR") | enum validation error | Draft |
| T10 | Preset.from_dict() with missing optional fields uses defaults | dict without all fields | Defaults applied (empty description, etc.) | Draft |
| T11 | Preset.from_dict() rejects unknown top-level keys | dict with extra_field: 123 | Raises ValidationError or ignored (configurable) | Draft |
| T12 | Preset created_at/updated_at ISO-8601 format on disk | Preset written to file | File contains "2026-04-16T10:30:00Z" format | Draft |
| T13 | Preset with valid trading_styles serializes and round-trips correctly | `Preset(trading_styles=["swing", "day"])` | `to_dict()["trading_styles"] == ["swing", "day"]`; `from_dict()` produces equal instance | Draft |
| T14 | Preset with empty trading_styles (untagged) serializes to `[]` | `Preset(trading_styles=[])` | `to_dict()["trading_styles"] == []`; valid for all style filters | Draft |
| T15 | `Preset.validate()` raises `PresetValidationError` on unknown style value | `Preset(trading_styles=["scalp"])` | `PresetValidationError` raised; message contains `"scalp"` | Draft |
| T16 | `Preset.from_dict()` on JSON without `trading_styles` key defaults to `[]` | dict missing `"trading_styles"` key | `preset.trading_styles == []` (backward-compatible load) | Draft |

### `tests/screener/test_registry.py` (6 tests)

| ID | Objective | Input | Expected Output | Status |
|---|---|---|---|---|
| T01 | ScreenerRegistry.register() adds screener to registry | screener_id="test", class | registry contains screener | Draft |
| T02 | ScreenerRegistry.get() instantiates screener by ID | screener_id="indicator_composite" | Returns Screener instance | Draft |
| T03 | ScreenerRegistry.get() raises ScreenerNotFoundError on unknown ID | screener_id="nonexistent" | ScreenerNotFoundError raised | Draft |
| T04 | ScreenerRegistry.list_available() returns all registered screeners | — | dict[screener_id: name] with ≥4 entries | Draft |
| T05 | ScreenerRegistry double-register overwrites previous (no error) | register twice with same ID | Latest class registered | Draft |
| T06 | Multiple screener types coexist (indicator, ML, LLM) | all 3 types registered | list_available() returns all 3 | Draft |

### `tests/screener/test_indicator_screener.py` (8 tests)

| ID | Objective | Input | Expected Output | Status |
|---|---|---|---|---|
| T01 | v1 Equivalence: same config + bars → same results as v1 ScreenerEngine | v1 config, test bars | IndicatorScreener result ≡ v1 result | Draft |
| T02 | IndicatorScreener.apply() returns (bool, float) tuple per symbol | 3 symbols, bars | dict[symbol: (bool, float)] | Draft |
| T03 | IndicatorScreener handles missing candle data (empty list) gracefully | symbol with no bars | Symbol skipped (not in output) or (False, 0.0) | Draft |
| T04 | IndicatorScreener scores in [0, 1] range | all symbols | All scores ∈ [0, 1] | Draft |
| T05 | All v1 filters (volatility, RSI, range, breakout, volume) toggleable | config with each filter disabled | Disabled filter skipped; results differ | Draft |
| T06 | Disabled filters do not affect final score | volatility disabled; symbol fails volatility | Symbol may pass (no volatility penalty) | Draft |
| T07 | IndicatorScreener applies filters in documented order | — | Filters apply: volatility → RSI → range → breakout → volume | Draft |
| T08 | IndicatorScreener.batch_features() returns empty dict (not used) | symbols, bars | {} returned | Draft |
| T09 | RS line normalized to 1.0 at t=0 | 20 days stock bars + 20 days SPY bars | `rs_line[0] == 1.0` | Draft |
| T10 | RS line > 1.0 when stock outperforms SPY | stock +5% cumulative; SPY flat | `rs_line[-1] > 1.0` | Draft |
| T11 | RS slope positive → symbol passes slope filter | rising RS line over 20 days (`rs_slope_days=20`) | filter passes | Draft |
| T12 | RS slope negative → symbol filtered out | falling RS line over 20 days | filter fails | Draft |
| T13 | RS rank = 90.0 for a top-10% 252d performer | symbol 252d return at 90th pct of 500 universe returns | `rs_rank == 90.0` (±0.5) | Draft |
| T14 | `rs_min_percentile=70` passes only top-30% symbols | 100 symbols, 30 with rank ≥ 70 | exactly 30 symbols pass RS rank filter | Draft |
| T15 | `BenchmarkDataUnavailableError` raised when SPY rows absent | empty `price_1d` for `"SPY"` | raises `BenchmarkDataUnavailableError` with `"SPY"` in message | Draft |
| T16 | RS disabled when `rs_min_percentile=0, rs_slope_days=0` (backward compat) | any bars; RS params at defaults | all symbols pass RS check; no DB call for SPY | Draft |

### `tests/screener/test_ml_screener.py` (5 tests)

| ID | Objective | Input | Expected Output | Status |
|---|---|---|---|---|
| T01 | MLScreener loads model from config["model_path"] | config with model_path, valid file | Model loaded; apply() runs inference | Draft |
| T02 | MLScreener.apply() returns (bool, float) for each symbol | 3 symbols, bars | dict[symbol: (bool, float)] | Draft |
| T03 | MLScreener raises ScreenerError on missing model file | config with nonexistent path | ScreenerError raised | Draft |
| T04 | MLScreener.batch_features() extracts and returns features dict | symbols, bars | dict[symbol: {feature_name: value}] | Draft |
| T05 | MLScreener threshold configurable; symbols pass/fail based on score | config with threshold=0.7, scores | score ≥ 0.7 → (True, score); else (False, score) | Draft |

### `tests/screener/test_price_action_screener.py` (8 tests)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| T01 | `price_action.py` | Unit | apply() returns (bool, float) tuple per symbol for all input symbols with sufficient bars | 3 symbols, 50 bars each, default config | `dict[str, tuple[bool, float]]` with 3 entries; all scores ∈ [0, 1] | Draft |
| T02 | `price_action.py` | Unit | proximity_52w_high: stock at 95% of 252-bar max passes with min_ratio=0.90 | 252 bars; last close = 0.95 × max(closes) | Pattern fires; (True, score ≥ 0.2) | Draft |
| T03 | `price_action.py` | Unit | volume_breakout: close > 20-day high AND volume > 1.5× vol_ma triggers breakout | bars with last bar above prior 20-day high and vol surge | Pattern fires; (True, score ≥ 0.2) | Draft |
| T04 | `price_action.py` | Unit | nr7_compression: bar with smallest range of last 7 bars detected correctly | 7 bars; last bar has smallest (high − low) | Pattern fires | Draft |
| T05 | `price_action.py` | Unit | ema_pullback: close[-2] < EMA[-2] AND close[-1] > EMA[-1] (cross above) detected | 30 bars; last bar crosses above EMA(21) from below | Pattern fires | Draft |
| T06 | `price_action.py` | Unit | engulfing: bearish candle followed by larger bullish candle that engulfs it | bars[-2]: bear candle; bars[-1]: bull candle with open ≤ bars[-2].close AND close ≥ bars[-2].open | Pattern fires | Draft |
| T07 | `price_action.py` | Unit | Score = matched/enabled; threshold determines pass/fail correctly | 2 of 4 enabled patterns fire; threshold=0.4 | score = 0.5; passed = True | Draft |
| T08 | `price_action.py` | Unit | Symbol with insufficient bars (<2) is excluded from output entirely | symbol with 1 bar | Symbol absent from result dict; no exception | Draft |

### `tests/screener/test_llm_claude_screener.py` (10 tests)

| ID | Objective | Input | Expected Output | Status |
|---|---|---|---|---|
| T01 | LLMClaudeScreener.batch_features() extracts features without API call | symbols, bars | dict[symbol: {price, trend, RSI, ATR, support, resistance, volume}] | Draft |
| T02 | Features include required fields (price, trend, RSI, ATR, support, resistance) | computed features | All 7 fields present; types correct | Draft |
| T03 | LLMClaudeScreener.apply() calls Claude API with feature-rich prompt | mocked Claude API | API called once; prompt contains symbol names, features | Draft |
| T04 | LLMClaudeScreener parses Claude ranking response (JSON or text) | Claude response | dict[symbol: (True, score), ...] with scores ∈ [0, 1] | Draft |
| T05 | LLMClaudeScreener returns scores in [0, 1] range | all symbols | All scores ∈ [0, 1] | Draft |
| T06 | LLMClaudeScreener handles Claude API timeout (>30s) with fallback | mocked timeout | Returns (all symbols as passed=True, score=0) and logs WARNING | Draft |
| T07 | LLMClaudeScreener handles auth error (invalid API key) gracefully | mocked auth error | Catches exception, logs ERROR, returns fallback | Draft |
| T08 | LLMClaudeScreener handles rate limit error (429) with fallback | mocked rate limit | Catches exception, logs WARNING, returns fallback | Draft |
| T09 | LLMClaudeScreener logs API usage (tokens_in, tokens_out, cost_usd) | mock API call | APIUsageTracker.log_usage() called with tokens + cost | Draft |
| T10 | Cost threshold check: if monthly cost > $50, emit WARNING | tracked usage >$50/month | Warning logged with amount | Draft |

### `tests/screener/test_executor.py` (20 tests)

| ID | Objective | Input | Expected Output | Status |
|---|---|---|---|---|
| T01 | PresetExecutor.run_preset() loads preset and validates permissions | preset_id, user_id | Preset loaded; access check passed | Draft |
| T02 | run_preset() raises PresetAccessDenied on unauthorized user | user without access | PresetAccessDenied raised | Draft |
| T03 | Stage 1 pre-filter: filters price ≤ $5 | 500 symbols, bars (some with price <$5) | Filtered symbols excluded; count ~300–350 | Draft |
| T04 | Stage 1 pre-filter: filters volume < 1M | symbols with low volume | Low-volume symbols excluded | Draft |
| T05 | Stage 1 pre-filter: excludes halted stocks | halted stock in universe | Halted stock not in filtered list | Draft |
| T06 | Stage 1 execution time <1s | 500 symbols | Timing logged; <1000ms | Draft |
| T07 | Stage 2 parallel execution: calls all enabled screeners | 5 screeners in preset | All 5 screeners.apply() called | Draft |
| T08 | Stage 2 multiprocessing: CPU-bound screeners run in pool | Indicator + ML screeners | Pool.map() called; results collected | Draft |
| T09 | Stage 2 asyncio: I/O-bound screeners (LLM) run in event loop | LLMClaudeScreener in preset | asyncio.run() or event loop used | Draft |
| T10 | Composite preset: symbol passes if ANY group passes (OR logic) | 2 groups; symbol passes G1 but not G2 | Symbol included in results | Draft |
| T11 | Composite preset: symbol fails if ALL groups fail (implicit AND between groups) | 2 groups; symbol fails both | Symbol excluded | Draft |
| T12 | Composite preset result includes matching_groups list | symbol passed groups [G1, G2] | result[symbol]['matching_groups'] = [G1, G2] | Draft |
| T13 | Weighted preset score: Σ(score_i × weight_i) / Σ(weights) | 3 screeners, scores [0.8, 0.6, 0.9], weights [0.4, 0.3, 0.3] | score = (0.8×0.4 + 0.6×0.3 + 0.9×0.3) / 1.0 ≈ 0.77 | Draft |
| T14 | Weighted preset: symbol passes if score ≥ threshold | threshold=0.7; score=0.77 | (True, 0.77) returned | Draft |
| T15 | Weighted preset: disabled screeners excluded from sum | screener_enabled=False | Screener not in Σ(weights); skipped | Draft |
| T16 | Stage 3 LLM ranking skipped if not enabled in preset | enable_llm_ranking=False | LLMClaudeScreener.apply() not called | Draft |
| T17 | Stage 3 LLM ranking runs if enabled; returns top-N | enable_llm_ranking=True; top_n=5; ~20 symbols pass Stage 2 | Top 5 ranked symbols in result | Draft |
| T18 | Stage 3 LLM error (timeout) triggers fallback to Stage 2 results | mocked timeout | Returns Stage 2 results (unranked); logs WARNING | Draft |
| T19 | PresetExecutor emits screener_run_completed event on completion | — | Event signal emitted with preset_id + result | Draft |
| T20 | Empty result set (no symbols pass) completes without error | all symbols fail all filters | Empty results list; no exception | Draft |

### `tests/screener/test_scheduler.py` (6 tests)

| ID | Objective | Input | Expected Output | Status |
|---|---|---|---|---|
| T01 | ScreenerScheduler.schedule() accepts valid cron expression | "0 8 * * 1-5" | Job registered in APScheduler | Draft |
| T02 | ScreenerScheduler.schedule() validates cron syntax | invalid: "99 99 99 99 99" | CronError or ValueError raised | Draft |
| T03 | ScreenerScheduler persists schedules to JSON file | scheduled preset | ~/.usswing/screener_schedules.json contains entry | Draft |
| T04 | ScreenerScheduler._load_persisted_schedules() loads on startup | file with prior schedule | Jobs re-registered; listener active | Draft |
| T05 | ScreenerScheduler.unschedule() removes job and deletes from file | scheduled preset | Job removed; file entry deleted | Draft |
| T06 | APScheduler fires at scheduled time (simulated with mock time) | mock cron trigger | PresetExecutor.run_preset() called with manual=False | Draft |

### `tests/screener/test_manager.py` (15 tests)

| ID | Objective | Input | Expected Output | Status |
|---|---|---|---|---|
| T01 | PresetManager.create_preset() persists to admin path | admin preset | ~/.../ presets_admin/{id}.json created | Draft |
| T02 | create_preset() persists to user path | user preset, user_id="user1" | ~/.../ presets_user/user1/{id}.json created | Draft |
| T03 | create_preset() rejects admin preset from non-admin user | non-admin user, is_admin=True | PresetAccessDenied raised | Draft |
| T04 | create_preset() sets created_at and created_by | new preset | created_at ≠ None; created_by = user_id | Draft |
| T05 | PresetManager.load_preset() reads and deserializes JSON | preset_id, user_id | Preset instance returned | Draft |
| T06 | load_preset() raises PresetAccessDenied on unauthorized access | user2 loading user1's private preset | PresetAccessDenied raised | Draft |
| T07 | PresetManager.list_admin_presets() returns all admin presets (no filter) | — | list of Preset objects; all have is_admin=True | Draft |
| T08 | list_user_presets() returns user's own + shared presets | user_id | User's own presets + those with user_id in assigned_to | Draft |
| T09 | PresetManager.update_preset() raises error on non-creator edit | user2 updating user1 preset | PresetAccessDenied raised | Draft |
| T10 | update_preset() updates updated_at timestamp | existing preset | updated_at > previous value | Draft |
| T11 | PresetManager.delete_preset() removes preset file | preset_id | File deleted; FileNotFoundError on next load | Draft |
| T12 | delete_preset() removes results directory (preset_{id}/) | preset with prior runs | Directory deleted recursively | Draft |
| T13 | PresetManager.grant_access() adds users to assigned_to list | grant_access([user2, user3]) | preset.assigned_to contains both users | Draft |
| T14 | PresetManager.revoke_access() removes user from assigned_to | revoke_access(user2) | user2 no longer in assigned_to | Draft |
| T15 | migrate_v1_presets() creates user preset from v1 ScreenerConfig | user with v1 config in DB | User preset created with Indicator screener + v1 config | Draft |
| T16 | `list_admin_presets(style_filter="swing")` returns swing-tagged + untagged presets | 3 admin presets: `trading_styles=["swing"]`, `["day"]`, `[]` | 2 returned (swing + untagged); day-only excluded | Draft |
| T17 | `list_user_presets(user_id, style_filter="day")` filters user + shared presets | user's own: `["day"]` + `["position"]`; shared: `[]` | day-tagged + untagged returned; position-only excluded | Draft |
| T18 | `style_filter=None` (default) returns all presets unfiltered | mixed `trading_styles` presets | All presets returned regardless of style tags | Draft |
| T19 | Invalid `style_filter` value raises `ValueError` | `style_filter="scalp"` | `ValueError` raised; message contains `"scalp"` | Draft |
| T20 | Untagged preset (`trading_styles=[]`) appears in every filtered result | `style_filter="position"`; one untagged preset | Untagged preset included in returned list | Draft |

### `tests/screener/test_storage.py` (12 tests)

| ID | Objective | Input | Expected Output | Status |
|---|---|---|---|---|
| T01 | ScreenerResultsStorage.save_result() writes to correct path | ScreenerRunResult, preset_id | ~/.usswing/screener_results/preset_{id}/{date}.json created | Draft |
| T02 | save_result() atomic write (temp → rename) | write during shutdown simulation | No partial file; atomic or rollback | Draft |
| T03 | ScreenerResultsStorage.load_result() deserializes JSON | preset_id, date | ScreenerRunResult instance returned | Draft |
| T04 | load_result() raises FileNotFoundError on missing date | preset_id, nonexistent date | FileNotFoundError raised | Draft |
| T05 | load_result() handles corrupted JSON gracefully | corrupted JSON file | JSONDecodeError logged; exception raised | Draft |
| T06 | ScreenerResultsStorage.list_results() returns last 30 results | preset_id with 50 dated results | Returns 30 results; sorted by date desc | Draft |
| T07 | FeatureCache.get() returns cached features if <24h old | symbol, date | Features dict returned | Draft |
| T08 | FeatureCache.get() returns None if expired (>24h) | old cached features | None returned; cache considered stale | Draft |
| T09 | FeatureCache.set() stores features with timestamp | symbol, features dict | Features + timestamp persisted | Draft |
| T10 | APIUsageTracker.log_usage() logs tokens and cost | tokens_in=1000, tokens_out=500 | Entry added to usage log with calculated cost | Draft |
| T11 | APIUsageTracker cost = (tokens_in × 0.003 + tokens_out × 0.009) / 1000 | tokens_in=1000, out=500 | cost ≈ 0.0075 USD | Draft |
| T12 | Cost threshold check: monthly total > $50 emits WARNING | usage logged over $50 in month | Warning logged with cost amount | Draft |

### `tests/screener/test_utils.py` (8 tests)

| ID | Objective | Input | Expected Output | Status |
|---|---|---|---|---|
| T01 | PreFilter.apply() filters symbols with price ≤ $5 | symbol with close=4.99 | Symbol excluded from output | Draft |
| T02 | PreFilter.apply() filters symbols with volume < 1M | symbol with volume=900k | Symbol excluded | Draft |
| T03 | PreFilter.apply() handles missing bars gracefully | symbol with empty bar list | Symbol excluded; no exception | Draft |
| T04 | PreFilter output ~300 symbols from 500 (ballpark) | 500 symbols, random bars | len(filtered) ∈ [250, 350] | Draft |
| T05 | PreFilter execution time <1s | 500 symbols (no DB load) | Timing < 1000ms | Draft |
| T06 | ScreenerError base class hierarchy | error instances | is instance of ScreenerError | Draft |
| T07 | ScreenerNotFoundError raised on missing screener_id | registry.get("xyz") | ScreenerNotFoundError raised; message contains screener_id | Draft |
| T08 | PresetValidationError raised on invalid preset structure | bad preset, validate() | PresetValidationError raised; message describes issue | Draft |

### `tests/screener/test_screener_panel.py` (5 tests — Phase 5, pytest-qt)

**Parent SRDs:** SRD-SCR-007.001, SRD-SCR-007.010  
**Parent Module:** MD-SCR-007.010.M16

| ID | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|
| T01 | Unit | Style combo defaults to "All Styles" (index 0, `currentData() == None`) on panel creation | `ScreenerPanel` instantiated | `combo.currentData() is None` | Draft |
| T02 | Unit | Selecting "Swing Trading" triggers `list_admin_presets(style_filter="swing")` and `list_user_presets(user_id, style_filter="swing")` | `combo.setCurrentIndex(1)` | Both manager list methods called with `style_filter="swing"` | Draft |
| T03 | Unit | Selecting "All Styles" after a previous selection calls list methods with `style_filter=None` | combo changed to "Day Trading" then back to "All Styles" | Manager called with `style_filter=None` on second change | Draft |
| T04 | Unit | Preset dropdown item count matches filtered manager results | manager returns 3 filtered presets | Preset dropdown has 3 items (admin group) | Draft |
| T05 | Unit | Untagged preset (`trading_styles=[]`) appears in dropdown regardless of active style filter | manager has 1 untagged admin preset; `style_filter="position"` | Untagged preset present in dropdown | Draft |

### `tests/screener/test_preset_builder.py` (8 tests — Phase 5, pytest-qt)

**Parent SRDs:** SRD-SCR-007.011, SRD-SCR-007.012  
**Parent Module:** MD-SCR-007.011.M17

| ID | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|
| T01 | Unit | `_load_trading_styles(["swing", "day"])` checks Swing and Day; leaves Position unchecked | `["swing", "day"]` | `swing_cb.isChecked() == True`, `day_cb.isChecked() == True`, `position_cb.isChecked() == False` | Draft |
| T02 | Unit | `_collect_trading_styles()` returns only values with checked boxes | Swing and Position checked | Returns `["swing", "position"]` (order matches `_STYLE_OPTIONS`) | Draft |
| T03 | Unit | Checkboxes are disabled when builder opened in non-owner (read-only) mode | `editable=False` passed to `_build_style_section()` | All three `QCheckBox.isEnabled() == False` | Draft |
| T04 | Unit | Saving with no checkboxes checked persists `trading_styles=[]` on the preset | All checkboxes unchecked; Save clicked | `preset.trading_styles == []` passed to `PresetManager.update_preset()` | Draft |
| T05 | Unit | `AssignUsersWidget.load_existing()` renders one tag widget per user_id | `["user_a", "user_b"]` | Two `_UserTag` children visible in tag area | Draft |
| T06 | Unit | Typing a user_id and pressing Enter calls `grant_access()` and adds a valid (green) tag | input text = `"user_c"` + returnPressed | `manager.grant_access(preset_id, ["user_c"])` called; tag rendered with valid style | Draft |
| T07 | Unit | Clicking × on a tag calls `revoke_access()` immediately (not deferred to Save) | `_UserTag.removed` signal emitted for `"user_b"` | `manager.revoke_access(preset_id, "user_b")` called before any Save action | Draft |
| T08 | Unit | `grant_access()` raising `PresetAccessDenied` or `ValueError` renders error-styled tag | `manager.grant_access()` mocked to raise `ValueError` | Tag rendered with error style; no valid tag added | Draft |

---

## Integration Tests (15 tests)

### `tests/screener/test_integration.py`

| ID | Objective | Input | Expected Output | Status |
|---|---|---|---|---|
| T01 | Full preset execution: load → pre-filter → Stage 2 → Stage 3 → save | preset_id, user_id, 500 symbols | Result file created; verified content | Draft |
| T02 | Composite preset with 2 groups produces correct AND/OR logic | Composite with G1 (RSI), G2 (Volume) | Symbol passes if: (RSI AND ATR) OR Volume | Draft |
| T03 | Weighted preset with 3 screeners calculates correct weighted score | Weighted: Indicator (0.4), ML (0.3), LLM (0.3) | Final score = weighted average | Draft |
| T04 | v1 migration + execution produces identical results to v1 | migrated v1 config, same test bars | IndicatorScreener result ≡ v1 | Draft |
| T05 | Manual trigger overwrites same-day results (timestamp updated) | run preset twice same day | File overwrites; run_timestamp updated | Draft |
| T06 | Scheduled trigger stores with execution_mode="scheduled" | cron trigger simulated | Result has execution_mode="scheduled" | Draft |
| T07 | LLM ranking enabled: features extracted → cached → LLM called | enable_llm_ranking=True | Stage 2 results ranked; LLM result in file | Draft |
| T08 | LLM ranking disabled: Stage 2 results returned directly | enable_llm_ranking=False | LLM screener not called; Stage 2 only | Draft |
| T09 | LLM API timeout triggers fallback gracefully | mocked timeout | Completes with Stage 2 results; WARNING logged | Draft |
| T10 | Permission denied: User A cannot load User B's private preset | user_A, user_B preset (not shared) | PresetAccessDenied raised | Draft |
| T11 | Permission granted: User B can load User A's shared preset | user_A grants to user_B; user_B loads | Preset loads successfully | Draft |
| T12 | New user creation: new preset + execution completes | new user_id, new preset | Preset created; run_preset() succeeds | Draft |
| T13 | User deletion: preset and results directory cleaned up | delete_preset() called | File + directory deleted; no orphans | Draft |
| T14 | Multi-preset concurrent runs (3 presets) do not interfere | 3 presets run in parallel | All complete without data corruption; 3 result files created | Draft |
| T15 | Result persistence: save → restart app → load → verify identical | save result, close app, reopen, load | Loaded result ≡ saved result | Draft |

---

## Test Fixtures & Mocks

| Fixture | Purpose | Type | Notes |
|---|---|---|---|
| `sample_preset_composite` | Composite preset (2 groups) for testing | Fixture | Groups: G1 (RSI+ATR), G2 (Volume) |
| `sample_preset_weighted` | Weighted preset (3 screeners) for testing | Fixture | Screeners: Indicator, ML, LLM; weights [0.4, 0.3, 0.3] |
| `sample_bars_sp500` | 500 symbols × 500 bars (2 years) generated | Fixture | Generated procedurally (not downloaded); deterministic |
| `mock_claude_api` | Mocked Claude API responses | Mock (unittest.mock) | Returns fixed ranked list + tokens |
| `mock_db_manager` | Mocked DatabaseManager | Mock | fetch_bars() returns sample bars |
| `temp_home_dir` | Temporary ~/.usswing for file tests | Fixture (pytest tmpdir) | Cleaned up after each test |
| `mock_screener` | Generic mock Screener | Mock | apply() + batch_features() return fixed data |
| `mock_scheduler` | Mocked APScheduler | Mock | add_job(), start() are no-ops |
| `mock_preset_manager` | Mocked `PresetManager` | Mock | list methods return controlled preset lists for GUI tests |
| `preset_with_styles` | `Preset` factory with configurable `trading_styles` | Fixture | Parametrized: `["swing"]`, `["day","position"]`, `[]` |
| `qtbot` | pytest-qt bot for GUI interaction | pytest-qt built-in | Used in all Phase 5 GUI tests |

---

## Running Tests

```bash
# All Screener tests
pytest tests/screener/ -v

# Specific module
pytest tests/screener/test_executor.py -v

# Coverage report
pytest tests/screener/ --cov=src/us_swing/screener --cov-report=html

# Integration tests only
pytest tests/screener/test_integration.py -v

# Unit tests only (exclude integration)
pytest tests/screener/ -k "not integration" -v

# Fast subset (skip slow tests)
pytest tests/screener/ -m "not slow" -v
```

---

## Coverage Goals

| Module | Target | Rationale |
|---|---|---|
| preset.py | 100 | Data model; must be bulletproof |
| registry.py | 100 | Small, critical plugin system |
| indicator.py | 95 | v1 equivalence: edge cases hard to predict |
| executor.py | 95 | Complex 3-stage logic; error paths |
| manager.py | 95 | Permissions security-critical |
| All modules | ≥90 | Overall target |
| gui/screener_panel.py | ≥80 | UI logic; Phase 5 gate |
| gui/preset_builder.py | ≥80 | UI logic; Phase 5 gate |

---

## Test Order (Recommended)

1. test_preset.py — foundation
2. test_registry.py — plugin system
3. test_utils.py — utilities
4. test_indicator_screener.py through test_llm_claude_screener.py — screeners (parallel OK)
5. test_executor.py — orchestration
6. test_manager.py — preset management
7. test_storage.py — persistence
8. test_scheduler.py — scheduling
9. test_integration.py — end-to-end
10. test_screener_panel.py — GUI (Phase 5, requires pytest-qt)
11. test_preset_builder.py — GUI (Phase 5, requires pytest-qt)

---

## CI Integration

- **Pre-commit:** `pytest tests/screener/ -q` (fail if any test fails)
- **PR check:** Coverage ≥90%; fail if below
- **Nightly:** Full suite + performance benchmarks
- **Release:** All 142 tests pass + coverage ≥95%

---

**Status:** v2.1.0 Draft — FO-SCR-011 Phase 1 AI Stock Ranking test cases added: 4 in `test_preset.py` (T17–T20), 5 in `test_llm_claude_screener.py` (T11–T15), 10 in new `test_tool_executor.py` (T01–T10), 2 in `test_executor.py` (T21–T22). All 173 screener unit tests pass after Phase 1 implementation. GUI smoke (Preset Builder AI Query field, Results Table AI Reasoning column) deferred to Phase 5 pytest-qt.

---

## FO-SCR-011 Phase 1 Test Cases (added in v2.1.0)

### `tests/screener/test_preset.py` — additional 4 tests (T17–T20)

| ID | Objective | Status |
|---|---|---|
| T17 | `ai_query` / `ai_model` defaults and round-trip via `to_dict`/`from_dict` | Pass |
| T18 | Legacy JSON without `ai_query`/`ai_model` loads with defaults (backward-compat) | Pass |
| T19 | `validate()` rejects `ai_query` longer than 500 chars | Pass |
| T20 | Empty `ai_query` is always valid (legacy fallback path) | Pass |

### `tests/screener/test_tool_executor.py` — new file, 10 tests (T01–T10)

| ID | Objective | Status |
|---|---|---|
| T01 | Happy path: `get_candle_data` returns JSON with bars from `DatabaseManager.fetch_bars()` | Pass |
| T02 | Allowlist rejection: symbol not in `passing_symbols` returns `symbol_not_allowed` JSON | Pass |
| T03 | Per-symbol call cap: 4th call returns `tool_call_cap_exceeded`; other symbols unaffected | Pass |
| T04 | Invalid timeframe (e.g. `"5m"`) rejected with `invalid_timeframe` | Pass |
| T05 | `lookback_bars` out of `[1, 300]` rejected (parameterised: 0, –5, 301, 1000) | Pass |
| T06 | Unknown tool name rejected with `unknown_tool` | Pass |
| T07 | Malformed input (missing key) returns `invalid_input` | Pass |
| T08 | Weekly timeframe uses widened calendar-day span (10 bars × 8 days) | Pass |
| T09 | Returned bars sliced to last `lookback_bars` | Pass |
| T10 | Symbol comparison case-insensitive (lowercase input is uppercased) | Pass |

### `tests/screener/test_llm_claude_screener.py` — additional 5 tests (T11–T15)

| ID | Objective | Status |
|---|---|---|
| T11 | Non-empty `ai_query` routes to tool-augmented path; tools + system prompt sent to API | Pass |
| T12 | Multi-turn loop: `tool_use` response feeds tool_result back; second API call carries the result | Pass |
| T13 | Reasoning captured into `screener.last_reasoning` per symbol | Pass |
| T14 | Reasoning longer than 50 words truncated to 50 | Pass |
| T15 | Empty `ai_query` falls back to legacy single-shot path (no `tools` / `system` kwargs) | Pass |

### `tests/screener/test_executor.py` — additional 2 tests (T21–T22)

| ID | Objective | Status |
|---|---|---|
| T21 | Stage 3 LLM config carries `db`, `passing_symbols`, `ai_query`, `ai_model` per SRD-013.006 | Pass |
| T22 | `last_reasoning` side-channel merges into `result.results[sym]["ai_reasoning"]` per SRD-013.007 | Pass |

### SRD-SCR-013.009 — AI trade plan fields

| ID | Module | Type | Objective | Input | Expected | Status |
|---|---|---|---|---|---|---|
| UT-SCR-013.009.M06.T01 | MD-SCR-002.003.M06 | Positive | Valid plan kept | ranking entry with entry 222, stop 212, target 255 | `last_plan["NVDA"] == {entry: 222.0, stop: 212.0, target: 255.0}` | Pass |
| UT-SCR-013.009.M06.T02 | MD-SCR-002.003.M06 | Negative | Missing or bad value drops the plan | no target; stop "abc"; entry -5 | symbol absent from `last_plan`; score and reasoning still parsed | Pass |
| UT-SCR-013.009.M06.T03 | MD-SCR-002.003.M06 | Positive | Prompt asks for plan fields | build tool-path prompt | system prompt contains "entry", "stop", "target" | Pass |
| UT-SCR-013.009.M10.T01 | MD-SCR-003.001.M10 | Positive | Plan merged only where present | `last_plan` for AAPL only | AAPL has `ai_plan`; MSFT, GOOGL have none | Pass |


---

## FO-SCR-013 — Indicator Catalogue and Rule-List Screening

Test files: `tests/core/test_indicator_catalogue.py` (M23), `tests/core/test_indicator_rules_config.py` (M24), `tests/core/test_indicator_ta.py` (M25), `tests/core/test_indicator_evaluate.py` (M26), `tests/screener/test_indicator_screener.py` (M04), `tests/screener/test_executor.py` (M10).

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-SCR-015.001.M23.T01 | MD-SCR-015.001.M23 | Positive | Catalogue ids are unique and every available entry has a compute or context | `CATALOGUE` | no duplicate ids; available ⇒ `compute` or `context != "none"` | Pass |
| UT-SCR-015.001.M23.T02 | MD-SCR-015.001.M23 | Negative | Unknown id is rejected | `get_spec("nope")` | raises `IndicatorRuleError` | Pass |
| UT-SCR-015.002.M23.T01 | MD-SCR-015.001.M23 | Positive | Every param default lies inside its range | all `ParamSpec`s | `min ≤ default ≤ max` | Pass |
| UT-SCR-015.002.M23.T02 | MD-SCR-015.001.M23 | Negative | Out-of-range default is refused | `ParamSpec(default=0, min=1, max=5)` | raises `ValueError` | Pass |
| UT-SCR-015.003.M23.T01 | MD-SCR-015.001.M23 | Positive | Category order matches FO list | `list(Category)` | Price … Others in FO order | Pass |
| UT-SCR-015.003.M23.T02 | MD-SCR-015.001.M23 | Negative | Unknown category is refused | `Category("Crypto")` | raises `ValueError` | Pass |
| UT-SCR-015.013.M23.T01 | MD-SCR-015.001.M23 | Positive | All release-1 indicators exist and are available | 21 release-1 ids | each `get_spec(id).available is True` | Pass |
| UT-SCR-015.013.M23.T02 | MD-SCR-015.001.M23 | Negative | No release-1 entries in Dividends or Others | `CATALOGUE` | no spec with category Dividends or Others | Pass |
| UT-SCR-015.014.M23.T01 | MD-SCR-015.001.M23 | Positive | Intraday entries are unavailable with reason | 6 intraday ids | `available False`; reason "needs intraday data" | Pass |
| UT-SCR-015.014.M23.T02 | MD-SCR-015.001.M23 | Negative | Rule on an unavailable indicator is refused | config rule `rvol_5m` | `rules_from_config` raises `IndicatorRuleError` | Pass |
| UT-SCR-015.004.M24.T01 | MD-SCR-015.006.M24 | Positive | Missing params get catalogue defaults | rule `rsi` without params | `params == {"period": 14}` | Pass |
| UT-SCR-015.004.M24.T02 | MD-SCR-015.006.M24 | Negative | Rule cannot be changed in place | `rule.value = 5` | raises `FrozenInstanceError` | Pass |
| UT-SCR-015.005.M24.T01 | MD-SCR-015.006.M24 | Positive | Condition flags are correct | each `Condition` | `needs_to` only for between; `needs_value` false for crosses, price, is true | Pass |
| UT-SCR-015.005.M24.T02 | MD-SCR-015.006.M24 | Negative | Unknown condition string is refused | rule condition `"sideways"` | raises `IndicatorRuleError` | Pass |
| UT-SCR-015.005.M24.T03 | MD-SCR-015.006.M24 | Negative | Condition not allowed for the indicator is refused | `ema_50` with `between` | raises `IndicatorRuleError` | Pass |
| UT-SCR-015.006.M24.T01 | MD-SCR-015.006.M24 | Positive | Rule list round trip is lossless | 3 mixed rules | `rules_from_config(rules_to_config(r)) == r`; `schema == 2` | Pass |
| UT-SCR-015.006.M24.T02 | MD-SCR-015.006.M24 | Edge | Empty rule list round trips | `[]` | config `rules == []`; reads back `[]` | Pass |
| UT-SCR-015.006.M24.T03 | MD-SCR-015.006.M24 | Negative | Malformed rule list is refused | `{"schema": 2, "rules": "rsi"}` | raises `IndicatorRuleError` | Pass |
| UT-SCR-015.007.M24.T01 | MD-SCR-015.006.M24 | Positive | Full legacy dict maps to 6 rules | legacy 6-section dict | 6 rules; ATR `0.01 → 1.0`; RSI 30–70 p14 | Pass |
| UT-SCR-015.007.M24.T02 | MD-SCR-015.006.M24 | Edge | Empty config uses legacy defaults | `{}` | 5 enabled rules + `rs_index` disabled | Pass |
| UT-SCR-015.007.M24.T03 | MD-SCR-015.006.M24 | Negative | Disabled legacy sections stay disabled | `rsi.enabled=False` | `rsi` rule `enabled False` | Pass |
| UT-SCR-015.015.M24.T01 | MD-SCR-015.006.M24 | Positive | Summary of legacy defaults | `{}` | `"ATR ≥ 1.0%  ·  RSI 30–70 (14)  ·  $5–$5K  ·  Breakout 10  ·  Vol ≥ 1.0×"` | Pass |
| UT-SCR-015.015.M24.T02 | MD-SCR-015.006.M24 | Negative | Disabled rules are left out of the summary | all rules disabled | `""` | Pass |
| UT-SCR-015.015.M24.T03 | MD-SCR-015.006.M24 | Positive | Settings text labels one-parameter values and joins several | default RSI, Vol, Breakout, RS, MACD, Price rules | `period 14`, `MA 10`, `10 bars`, `slope 63 d`, `12 · 26 · 9`, `""` | Pass |
| UT-SCR-015.008.M25.T01 | MD-SCR-015.008.M25 | Positive | RSI matches TA-Lib Wilder RSI | 60 seeded closes, period 14 | last value equals `talib.RSI` | Pass |
| UT-SCR-015.008.M25.T02 | MD-SCR-015.008.M25 | Positive | ATR % equals Wilder ATR ÷ close × 100 | 60 seeded bars | matches `talib.ATR / close × 100` | Pass |
| UT-SCR-015.008.M25.T03 | MD-SCR-015.008.M25 | Positive | PPO signal and histogram follow formula | 80 closes, 12/26/9 | `hist == ppo − EMA(ppo, 9)` | Pass |
| UT-SCR-015.008.M25.T04 | MD-SCR-015.008.M25 | Negative | Too few bars gives NaN | 5 closes, RSI 14 | last value NaN | Pass |
| UT-SCR-015.009.M26.T01 | MD-SCR-015.009.M26 | Positive | Between is inclusive | RSI value exactly 30 and 70 | both pass | Pass |
| UT-SCR-015.009.M26.T02 | MD-SCR-015.009.M26 | Negative | Value outside band fails | RSI 75, band 30–70 | `(False, 75)` | Pass |
| UT-SCR-015.009.M26.T03 | MD-SCR-015.009.M26 | Positive | Cross above detected on the last bar | MACD below signal at −2, above at −1 | pass | Pass |
| UT-SCR-015.009.M26.T04 | MD-SCR-015.009.M26 | Negative | Older cross does not count | cross at −3, above since | fail | Pass |
| UT-SCR-015.009.M26.T05 | MD-SCR-015.009.M26 | Edge | Too few bars fails the rule | 10 bars, EMA 50 | `(False, None)` | Pass |
| UT-SCR-015.009.M26.T06 | MD-SCR-015.009.M26 | Positive | Price above EMA | rising series, `ema_20` price above | pass | Pass |
| UT-SCR-015.010.M04.T01 | MD-SCR-002.001.M04 | Positive | All rules pass | 2 lenient rules | `(True, 1.0)` | Pass |
| UT-SCR-015.010.M04.T02 | MD-SCR-002.001.M04 | Negative | One of two rules fails | 1 lenient + 1 impossible rule | `(False, 0.5)` | Pass |
| UT-SCR-015.010.M04.T03 | MD-SCR-002.001.M04 | Edge | Disabled rule is ignored | impossible rule with `enabled False` | `(True, 1.0)` | Pass |
| UT-SCR-015.010.M04.T04 | MD-SCR-002.001.M04 | Edge | No enabled rules | `{"schema": 2, "rules": []}` | every symbol `(True, 1.0)` | Pass |
| UT-SCR-015.011.M04.T01 | MD-SCR-002.001.M04 | Positive | RS rule passes the strongest symbol | 3 symbols + SPY, RS ≥ 60 | top return passes; weakest fails | Pass |
| UT-SCR-015.011.M04.T02 | MD-SCR-002.001.M04 | Negative | RS rule without benchmark bars | RS rule, no SPY | raises `BenchmarkDataUnavailableError` | Pass |
| UT-SCR-015.011.M04.T03 | MD-SCR-002.001.M04 | Edge | No RS rule needs no benchmark | RSI rule only, no SPY | no error | Pass |
| UT-SCR-015.012.M04.T01 | MD-SCR-002.001.M04 | Positive | Market cap rule passes large cap | cap 50e9, rule ≥ 10 ($B) | pass | Pass |
| UT-SCR-015.012.M04.T02 | MD-SCR-002.001.M04 | Negative | Symbol without cap fails | no cap entry | fail | Pass |
| UT-SCR-015.016.M04.T01 | MD-SCR-002.001.M04 | Positive | Detailed output keyed by rule label | RSI + EMA rules | keys `RSI`, `EMA(50)` | Pass |
| UT-SCR-015.017.M04.T01 | MD-SCR-002.001.M04 | Positive | Legacy config uses Wilder math | legacy dict, seeded bars | result equals manual TA-Lib evaluation | Pass |
| UT-SCR-015.017.M04.T02 | MD-SCR-002.001.M04 | Negative | Old private helpers are gone | import module | no `_rsi`, `_atr_pct`, `_volume_ratio`, `_is_breakout`; id `indicator_composite` still registered | Pass |
| UT-SCR-015.012.M10.T01 | MD-SCR-003.001.M10 | Positive | Executor passes market caps to screeners | `run_preset(market_caps={"AAA": 1e10})` with spy screener | screener config has `market_caps` | Pass |

## FO-SCR-014 — Price Action Pattern Catalogue and Rule-List Screening

Test files:
- `tests/core/test_price_pattern_catalogue.py` (M27)
- `tests/core/test_price_pattern_candles.py` (M28)
- `tests/core/test_price_pattern_breakouts.py` (M29)
- `tests/core/test_price_pattern_rules.py` (M30, M24)
- `tests/core/test_price_pattern_evaluate.py` (M31)
- `tests/screener/test_price_action_screener.py` (M08; the legacy T01–T07 stay as regression tests)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-SCR-016.001.M27.T01 | MD-SCR-016.001.M27 | Positive | Catalogue has 51 unique entries with valid defaults | `PATTERNS` | 51 ids, no duplicates; every `short` has no `_`; defaults inside ranges | Pass |
| UT-SCR-016.001.M27.T02 | MD-SCR-016.001.M27 | Negative | Unknown id is rejected | `get_pattern("nope")` | raises `PatternRuleError` | Pass |
| UT-SCR-016.002.M27.T01 | MD-SCR-016.001.M27 | Positive | Category sizes match the release list | count per `PatternCategory` | 11, 11, 5, 7, 8, 5, 4 | Pass |
| UT-SCR-016.002.M27.T02 | MD-SCR-016.001.M27 | Negative | Candle groups carry their direction | entries in Bearish candles | all `Direction.BEARISH`; none bullish | Pass |
| UT-SCR-016.003.M28.T01 | MD-SCR-016.003.M28 | Positive | Each candle entry matches when its TA-Lib signal fires (parametrised, 27 cases) | arrays with patched signal at last bar of the right sign | `evaluate_pattern` True | Pass |
| UT-SCR-016.003.M28.T02 | MD-SCR-016.003.M28 | Negative | Two-sided entries reject the opposite sign | signal −100 for `bullish_engulfing`, +100 for `bearish_engulfing` | both False | Pass |
| UT-SCR-016.003.M28.T03 | MD-SCR-016.003.M28 | Positive | Real bars give a TA-Lib bullish engulfing | 12 down bars + small red + large green engulfing bar | `bullish_engulfing` True, `bearish_engulfing` False | Pass |
| UT-SCR-016.004.M28.T01 | MD-SCR-016.003.M28 | Positive | `within` finds a signal 2 bars back | signal at bar −3, `within` 3 | True | Pass |
| UT-SCR-016.004.M28.T02 | MD-SCR-016.003.M28 | Negative | Default `within` 1 ignores older signals | signal at bar −3, `within` 1 | False | Pass |
| UT-SCR-016.005.M29.T01 | MD-SCR-016.005.M29 | Positive | Each new pattern matches its built series (parametrised, 20 cases) | one synthetic series per pattern | True | Pass |
| UT-SCR-016.005.M29.T02 | MD-SCR-016.005.M29 | Negative | Each new pattern rejects a flat series (parametrised, 20 cases) | flat bars, constant volume (NR4: widening ranges) | False | Pass |
| UT-SCR-016.005.M29.T03 | MD-SCR-016.005.M29 | Edge | Golden Cross with fast ≥ slow never matches | `fast` 100, `slow` 100 | False | Pass |
| UT-SCR-016.006.M29.T01 | MD-SCR-016.005.M29 | Positive | Legacy 4 patterns equal the old code | random seeded bars, 200 windows | same flags as the old helper functions (kept in the test) | Pass |
| UT-SCR-016.006.M29.T02 | MD-SCR-016.005.M29 | Negative | Legacy ids are unchanged | ids in `PATTERNS` | include `proximity_52w_high`, `volume_breakout`, `nr7_compression`, `ema_pullback` | Pass |
| UT-SCR-016.016.M29.T01 | MD-SCR-016.005.M29 | Negative | Double Top Pullback rejects a breakdown still falling away from the neck | Double Top series ending far below the neck | False | Pass |
| UT-SCR-016.016.M29.T02 | MD-SCR-016.005.M29 | Negative | Double Top Pullback rejects a close back above the neck | Pullback series whose last close is above the neck | False | Pass |
| UT-SCR-016.017.M29.T01 | MD-SCR-016.005.M29 | Negative | Double Bottom rejects a breakout older than `within` bars | Double Bottom series that broke out ~20 bars ago and stayed above the neck | False (True with `within` 20) | Pass |
| UT-SCR-016.018.M29.T01 | MD-SCR-016.005.M29 | Negative | Fib Sell rejects a bounce that closed above the zone | fall then bounce closing above the 61.8 % level | False | Pass |
| UT-SCR-016.018.M29.T02 | MD-SCR-016.005.M29 | Negative | Fib Sell rejects a bounce that has not reached the zone | fall then small bounce below the 50 % level | False | Pass |
| UT-SCR-016.018.M29.T03 | MD-SCR-016.005.M29 | Edge | Fib rejects a swing smaller than `min_move` | 5 % fall and bounce, `min_move` 10 | False | Pass |
| UT-SCR-016.007.M30.T01 | MD-SCR-016.007.M30 | Positive | Missing params get defaults | rule dict without params | params = catalogue defaults | Pass |
| UT-SCR-016.007.M30.T02 | MD-SCR-016.007.M30 | Negative | Rule cannot be changed in place | set `rule.enabled` | `FrozenInstanceError` | Pass |
| UT-SCR-016.008.M30.T01 | MD-SCR-016.007.M30 | Positive | Round trip is lossless | 3 rules, threshold 0.4 | same rules and 0.4 back; `schema` 2 | Pass |
| UT-SCR-016.008.M30.T02 | MD-SCR-016.007.M30 | Edge | Empty rule list round trips | `[]`, 0.2 | `[]`, 0.2 | Pass |
| UT-SCR-016.008.M30.T03 | MD-SCR-016.007.M30 | Negative | Non-numeric threshold is refused | `{"schema": 2, "rules": [], "threshold": "high"}` | `PatternRuleError` | Pass |
| UT-SCR-016.009.M30.T01 | MD-SCR-016.007.M30 | Positive | Legacy dict maps to 5 rules | full legacy `patterns` dict, threshold 0.4 | 5 rules in legacy order; `engulfing` → `bullish_engulfing`; params kept; 0.4 | Pass |
| UT-SCR-016.009.M30.T02 | MD-SCR-016.007.M30 | Positive | Empty config gives legacy defaults | `{}` | 52w + volume on, other 3 off; threshold 0.2 | Pass |
| UT-SCR-016.009.M30.T03 | MD-SCR-016.007.M30 | Negative | Bad legacy param is refused | `{"patterns": {"ema_pullback": {"ema_period": "x"}}}` | `PatternRuleError` | Pass |
| UT-SCR-016.010.M30.T01 | MD-SCR-016.007.M30 | Negative | Unknown pattern id raises | rule `{"pattern_id": "nope"}` | `PatternRuleError` | Pass |
| UT-SCR-016.010.M30.T02 | MD-SCR-016.007.M30 | Negative | Bad param value or non-list rules raise | `params {"within": "x"}`; `rules: "hammer"` | `PatternRuleError` | Pass |
| UT-SCR-016.010.M30.T03 | MD-SCR-016.007.M30 | Positive | A valid rule list for every catalogue id loads without error | one default rule per `PATTERNS` entry | 47 rules, no error | Pass |
| UT-SCR-016.014.M30.T01 | MD-SCR-016.007.M30 | Positive | Summary of legacy defaults | `{}` | `"PA ≥ 20%  ·  52wHigh  ·  VolBreak"` | Pass |
| UT-SCR-016.014.M30.T02 | MD-SCR-016.007.M30 | Negative | No enabled rules or bad config → empty text | all disabled; unknown id | `""` | Pass |
| UT-SCR-016.014.M24.T01 | MD-SCR-015.006.M24 | Positive | Indicator settings text unchanged after helper move | existing UT-SCR-015.015.M24.T03 inputs | same strings | Pass |
| UT-SCR-016.011.M31.T01 | MD-SCR-016.011.M31 | Positive | Out-of-range params are clamped | `within` 99 | evaluated as 5, no error | Pass |
| UT-SCR-016.011.M31.T02 | MD-SCR-016.011.M31 | Negative | Too few bars gives no match | 5 bars, VCP lookback 60 | False | Pass |
| UT-SCR-016.012.M08.T01 | MD-SCR-002.005.M08 | Positive | Score is matched ÷ enabled and passes at threshold | 4 rules, 1 matches, threshold 0.2 | `(True, 0.25)` | Pass |
| UT-SCR-016.012.M08.T02 | MD-SCR-002.005.M08 | Negative | Threshold outside 0–1 raises | threshold 1.5 | `ScreenerError` | Pass |
| UT-SCR-016.012.M08.T03 | MD-SCR-002.005.M08 | Edge | Disabled rule and short bar list | 1 disabled rule; symbol with 1 bar | disabled rule not counted; 1-bar symbol omitted; no enabled → score 0.0 | Pass |
| UT-SCR-016.013.M08.T01 | MD-SCR-002.005.M08 | Positive | Detailed output keyed by short label | Hammer + NR7 rules | keys `Hammer`, `NR7`; bool values | Pass |
| UT-SCR-016.015.M08.T01 | MD-SCR-002.005.M08 | Positive | No analysis-tool import; id unchanged | module source; registry | no `us_swing.analysis` import; `price_action` registered | Pass |

## FO-SCR-015 — Accumulation / Distribution Screener

Test files:
- `tests/screener/test_acc_dist_screener.py` (M32)
- `tests/gui/test_acc_dist_settings_dialog.py` (M33)

| ID | Module | Type | Objective | Input | Expected Output | Status |
|---|---|---|---|---|---|---|
| UT-SCR-017.001.M32.T01 | MD-SCR-017.001.M32 | Positive | Screener is registered | package source; class | `register("acc_dist", AccDistScreener)`; name "Accumulation / Distribution" | Pass |
| UT-SCR-017.002.M32.T01 | MD-SCR-017.001.M32 | Positive | Empty config reads as defaults | `{}` | equals `default_config()`; lookback int 20 | Pass |
| UT-SCR-017.003.M32.T01 | MD-SCR-017.001.M32 | Negative | Bad mode or out-of-range value raises (4 cases) | mode `sideways`, lookback 2, high factor 9, min score 1.5 | `ScreenerValidationError` naming the key | Pass |
| UT-SCR-017.004.M32.T01 | MD-SCR-017.001.M32 | Edge | Moves under the minimum move are flat | min move 2 % on 1.5 % / 1 % days | `(False, 0.0)` | Pass |
| UT-SCR-017.006.M32.T01 | MD-SCR-017.001.M32 | Positive | Accumulation passes | 8 rallies (6 at 1.5×), 7 drops (6 at 0.6×), near range low | `True`, score ≈ 0.80 | Pass |
| UT-SCR-017.006.M32.T02 | MD-SCR-017.001.M32 | Negative | Same bars fail Distribution | mode distribution, location off | `False`, score < 0.6 | Pass |
| UT-SCR-017.006.M32.T03 | MD-SCR-017.001.M32 | Positive | Distribution passes | rallies 0.6×, drops 1.5×, near range high | `True`, score ≈ 0.80 | Pass |
| UT-SCR-017.008.M32.T01 | MD-SCR-017.001.M32 | Positive | Detailed output and ratio | accumulation bars | keys RallyVol / DropVol / UD; RallyVol > 1.2, DropVol < 0.9, UD ≥ 1.3 | Pass |
| UT-SCR-017.008.M32.T02 | MD-SCR-017.001.M32 | Negative | Ratio limit blocks pass | min up/down ratio 5 | `False` | Pass |
| UT-SCR-017.009.M32.T01 | MD-SCR-017.001.M32 | Edge | Location filter | accumulation volumes near range high | fails with filter on, passes off | Pass |
| UT-SCR-017.010.M32.T01 | MD-SCR-017.001.M32 | Positive | Close-position check | rallies closing in the lower candle half | fails and lower score with check on; passes off | Pass |
| UT-SCR-017.011.M32.T01 | MD-SCR-017.001.M32 | Edge | Minimum days and short history | min rally days 9; 30 bars | `False`; symbol omitted | Pass |
| UT-SCR-017.013.M33.T01 | MD-SCR-017.013.M33 | Positive | Config round trip | distribution, lookback 30, location off | same dict back | Pass |
| UT-SCR-017.013.M33.T02 | MD-SCR-017.013.M33 | Positive | One input per setting | default dialog | inputs = `SETTINGS` keys; on/off keys are checkboxes | Pass |
| UT-SCR-017.013.M33.T03 | MD-SCR-017.013.M33 | Negative | Inputs are range-limited | lookback 999 | 120 | Pass |
| UT-SCR-017.013.M33.T04 | MD-SCR-017.013.M33 | Edge | Bad saved config and Reset | mode `sideways`; edits then Reset | defaults both times | Pass |
| UT-SCR-017.013.M33.T05 | MD-SCR-017.013.M33 | Positive | Builder wiring | group and weighted-row configure with an accepting dialog | display "Acc / Dist"; both store the returned config | Pass |

SRD-SCR-017.005 (relative volume) and .007 (score) are covered by T01 / T03 of .006 and T01 of .008.

