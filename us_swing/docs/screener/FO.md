# Functional Objectives — Screener (SCR)

**Document ID:** FO-SCR
**Version:** 2.2.0
**Status:** Draft
**Last Updated:** 2026-04-30
**Project:** US Swing Trading System

> Traces to: `us_swing/requirements.md` §8, §12, §21.3, §22

---

## FO-SCR-001: Flexible, Composable Preset Framework for Multi-Type Stock Screening
- **Status:** Approved

- The system shall support **multiple screener types** (indicator-based, ML models, LLM Claude ranking, local LLM, price action, MCP tools) as interchangeable plugins.
- Users and admins shall be able to create **presets** — collections of screeners combined via **Composite** (AND/OR group logic) or **Weighted** (ensemble voting) paradigms.
- **Composite presets:** Multiple groups of screeners combined via OR; within each group, screeners combined via AND. A symbol passes if any group passes entirely.
- **Weighted presets:** Each screener receives a weight; combined score = Σ(screener_score × weight) / Σ(weights). Symbol passes if score ≥ threshold.
- Each preset shall be independently configurable with per-screener settings (e.g., RSI range, ATR period, LLM temperature, threshold).
- Each preset shall include a `trading_styles` tag indicating the applicable trading strategies (e.g., "swing", "day", "position"). An empty tag means the preset is untagged and visible to all users regardless of style filter.
- **Acceptance Criteria:**
  - A Composite preset with 2 groups (Group1: RSI + ATR, Group2: Volume) runs without error and returns correct AND/OR logic results.
  - A Weighted preset with 3 screeners (indicator, ML, LLM) and weights {0.4, 0.3, 0.3} correctly calculates combined score.
  - Preset definitions are serializable to/from JSON with no data loss.
  - Users can toggle screener enable/disable within a preset without rebuilding.

---

## FO-SCR-002: Plugin-Based Screener Architecture
- **Status:** Approved

- All screener implementations shall conform to a **Screener protocol** defining:
  - `apply(symbols, bars, config)` — filter and score symbols; returns `{symbol: (passed: bool, score: 0–1)}`.
  - `batch_features(symbols, bars, config)` — optional; extract features for LLM ranking.
- Built-in screener types:
  - **Indicator screener:** Technical indicators (RSI, ATR, Bollinger Bands, MACD, Range Compression, Breakout Proximity, Volume Spike). Wraps v1 filter logic.
  - **ML screener:** Trained offline; inference only. Loads model, extracts features, returns predictions.
  - **LLM Claude screener:** Uses Claude API for ranking (optional Stage 3). Extracts features, calls Claude with ranked list request.
  - **LLM Local screener:** Local LLM via ollama or similar. Same interface as Claude screener.
  - **Price Action screener:** Pattern recognition (support bounce, range breakout, trend). Detects chart patterns.
  - **MCP screener:** External MCP tools for specialized analysis.
- Screeners shall be registered in a **ScreenerRegistry** for discovery and instantiation.
- **Acceptance Criteria:**
  - A new screener type can be added (registered) without modifying core execution logic.
  - All built-in screeners implement `apply()` with identical input/output signature.
  - Indicator screener produces identical results to v1 ScreenerEngine with same config.
  - LLM screener gracefully handles API timeouts/errors with fallback (skip ranking, return unranked results).

---

## FO-SCR-003: Three-Stage Execution Pipeline with Optional LLM Ranking
- **Status:** Approved

- Preset execution shall follow a **3-stage pipeline:**
  - **Stage 1 (Pre-Filter):** Quick, single-threaded filter (price > $5, volume > 1M, not halted). Output: ~300 symbols pass from ~500. Time: <1 sec.
  - **Stage 2 (Parallel Execution):** Run screeners in parallel (CPU-bound via multiprocessing, I/O-bound via asyncio). Apply preset logic (Composite AND/OR or Weighted scoring). Output: ~20 symbols pass. Time: 5–30 sec.
  - **Stage 3 (Optional LLM Ranking):** If preset includes LLM screener, extract features once (batch), call LLM, return ranked top-N. Time: 500ms–2s.
- Total execution time for S&P 500: **<2 minutes**.
- Stage 3 is **optional** — only runs if preset includes LLM screener; can be toggled per preset.
- **Acceptance Criteria:**
  - Pre-filter reduces 500 symbols to 250–350 in <1 sec (no database load times).
  - Parallel Stage 2 completes in <30 sec for 300 symbols with 5 screeners active.
  - LLM Stage 3 ranks top-20 symbols in <2 sec (including feature extraction and API call).
  - Total pipeline for full S&P 500 with all stages <2 min.

---

## FO-SCR-004: Hybrid Execution Modes — Scheduled & On-Demand
- **Status:** Approved

- The system shall support **two execution modes:**
  - **Scheduled Daily Batch:** Runs automatically at a user-configurable cron expression (default 08:00 EST on trading days). Results persisted to file.
  - **On-Demand Manual:** User clicks "Run Screener Now" in GUI; runs immediately, even if cron already ran today. Overwrites same-day results.
- Results shall be **persisted to file** (not database): `~/.usswing/screener_results/preset_{id}/{date}.json`.
- Each result file contains: run timestamp, execution mode, passed symbols, scores, per-screener details, optional LLM ranking.
- Cron scheduler shall listen for scheduled times and invoke `PresetExecutor.run_preset()` automatically.
- **Acceptance Criteria:**
  - Cron job fires at configured time; `run_preset()` is called within 10 seconds of trigger.
  - On-demand run triggered at 10:00 AM completes and overwrites 08:00 AM same-day results.
  - Results file is created within 100ms of run completion.
  - Scheduler persists cron expressions to config; survives app restart.

---

## FO-SCR-005: User-Accessible Preset Management with Admin Curation
- **Status:** Approved

- System shall support **two preset classes:**
  - **Admin presets:** System-curated, read-only to all users. Stored in `~/.usswing/screener_results/presets_admin/`. Admin users can create/update.
  - **User presets:** Private by default; created in `~/.usswing/screener_results/presets_user/{user_id}/`. Users can share presets with other users (permission grant).
- Presets shall include metadata: `name`, `description`, `created_by`, `created_at`, `updated_at`, `is_shared`, `assigned_to` (list of user_ids), `trading_styles` (list of applicable trading styles: "swing", "day", "position"; empty = untagged, visible to all).
- Preset creator (admin or user) shall be able to tag a preset with one or more trading styles at creation or edit time. A preset tagged for multiple styles is visible under each.
- `list_user_presets()` and `list_admin_presets()` shall accept an optional `style_filter` parameter; untagged presets are always included regardless of filter.
- PresetManager shall support CRUD operations: `create_preset()`, `load_preset()`, `list_user_presets()`, `list_admin_presets()`, `update_preset()`, `delete_preset()`, `grant_access()`, `revoke_access()`.
- GUI shall display separate sections for Admin Presets (read-only) and User Presets (editable).
- **Acceptance Criteria:**
  - Admin user creates a preset "Daily RSI + ML" and marks it as admin preset. All other users can view and run it, not edit.
  - User A creates a private preset "My Custom Screener", then shares it with User B. User B can load and run it.
  - User A cannot edit User B's preset unless explicitly granted; deletion is restricted to creator + admin.
  - Permission system rejects unauthorized access attempts with clear error messages.
  - A preset tagged `["swing", "position"]` appears when filtering by "swing" and when filtering by "position", but not when filtering by "day".
  - An untagged preset (empty `trading_styles`) appears under every style filter including "All Styles".

---

## FO-SCR-006: LLM Ranking Layer with Cost Tracking
- **Status:** Approved

- If a preset includes an **LLM screener**, a **ranking layer** shall execute after Stage 2:
  - Extract features from top-N symbols that passed Stage 2 (batch feature extraction, reusable).
  - Call Claude API (or local LLM) with prompt: "Rank these stocks for swing trading setup. Return ranked list with scores 0–1."
  - Parse LLM response; return ranked list with top-N selection (e.g., top 5).
  - **Cost tracking:** Log each LLM API call with tokens used; accumulate per preset per month. Emit warning if monthly cost exceeds $50 (configurable threshold).
  - **Feature caching:** Cache extracted features per symbol per day (24h TTL); reuse for multiple runs same day.
- LLM ranking is **optional per preset** — can be toggled on/off via preset config.
- If LLM API fails or times out, gracefully fallback: skip ranking, return Stage 2 results (unranked) with warning log.
- **Acceptance Criteria:**
  - LLM screener extracts features in batch (not per-symbol) and caches for reuse.
  - Cost tracking accumulates tokens and emits monthly reports.
  - Feature cache expires after 24h; new features extracted after expiry.
  - LLM API timeout (>30s) triggers fallback; screener completes with Stage 2 results only.
  - Cost threshold alert fires when monthly usage exceeds limit.

---

## FO-SCR-007: GUI Preset Builder — Drag-and-Drop Composable Interface
- **Status:** Approved

- GUI shall provide a **Screener panel** with:
  - **Style filter dropdown:** "All Styles", "Swing Trading", "Day Trading", "Position Trading". Filters the preset selector; untagged presets always appear.
  - **Preset selector:** Dropdown list (Admin Presets, User Presets, Create New), filtered by selected style.
  - **"Run Now" button:** Triggers immediate `run_preset()` for selected preset.
  - **Results view:** Table showing passed symbols, scores, per-screener details, optional LLM ranking.
  - **Preset builder (for editing user presets):**
    - **Drag-and-drop interface** to add/remove screeners in groups (for Composite) or list (for Weighted).
    - **Toggle AND/OR logic** per group (Composite only).
    - **Per-screener config panel:** Collapsible sections for each screener with parameter inputs (RSI range, ATR period, weight, threshold, etc.).
    - **Preview pane:** Shows preset structure and logic before saving.
    - **Trading Style selector:** Multi-select checkboxes (Swing, Day, Position) to tag the preset's applicable styles. Unselected = untagged.
    - **Assign Users field:** Tokenized input to add user IDs; calls `grant_access()`. Existing assigned users shown as removable tags; removal calls `revoke_access()`.
  - **Optional: "Save as" button** to clone a preset.
- Builder shall be **simple but flexible:** No code required for basic use (drag-and-drop); power users can edit JSON directly if needed.
- GUI refresh after preset execution: Auto-populate results table, show "Run completed at HH:MM:SS" timestamp.
- **Acceptance Criteria:**
  - User can add 2 screeners to a group, toggle AND logic, and see structure in preview.
  - Parameter changes (e.g., RSI min) update in real-time preview.
  - "Run Now" button invokes screener and displays results within 2 minutes for full S&P 500.
  - Preset save persists to JSON file; reload on app restart recovers preset.
  - Selecting "Swing Trading" in the style filter updates the preset dropdown to show only swing-tagged and untagged presets.
  - Creator tags a preset with "Day" and "Swing"; both tags are saved and displayed correctly in read-only view for other users.
  - Creator assigns User B via the Assign Users field; User B immediately gains access without restart.

---

## FO-SCR-008: Result Persistence & Historical Tracking
- **Status:** Approved

- Screener results shall be **file-persisted** (not database) for each preset per date:
  - Path: `~/.usswing/screener_results/preset_{id}/{date}.json` (date = YYYY-MM-DD).
  - Structure: `{run_timestamp, execution_mode, total_symbols, passed_count, results: [{symbol, passed, score, details}], llm_ranking: [...]}`
- GUI shall display **recent results** (last 30 days) for each preset with date selector.
- Users can **export results** to CSV (symbol, score, details, ranking).
- Results are **read-only** (immutable) once written; no post-hoc edits.
- **Acceptance Criteria:**
  - After a screener run, a JSON file is created at the correct path within 100ms.
  - Subsequent runs on the same date/preset overwrite the file (timestamp updated).
  - GUI date selector shows all available dates with results; clicking loads historical result.
  - CSV export includes all columns from result object without truncation.

---

## FO-SCR-009: Backward Compatibility — v1 Presets Auto-Migrated
- **Status:** Approved

- On first v2 launch, system shall **auto-migrate** all user v1 `ScreenerConfig` instances from `users.settings_json` to v2 presets:
  - Create one admin preset "Legacy v1" containing v1 filter config.
  - Per-user v1 config → auto-create private preset "{user_name}'s v1 Settings".
  - Mapped ScreenerConfig fields → equivalent v1 Indicator screener with same parameters.
- v1 `ScreenerEngine` class shall be **removed entirely** (no deprecation period); v1 results in database are kept read-only.
- Docs and GUI references to v1 shall be removed.
- **Acceptance Criteria:**
  - On first v2 run, migration completes without errors; all user v1 configs converted to presets.
  - "Legacy v1" admin preset runs and produces identical results to v1 ScreenerEngine with same config (test with known input/output).
  - v1 code is deleted; no conditional "if v1 else v2" logic remains.

---

## FO-SCR-010: Relative Strength vs Benchmark Screening
- **Status:** Approved

- The system shall compute each stock's **relative strength (RS)** vs the configured benchmark symbol (default: SPY) as a first-class screener parameter for filtering and ranking the top 20 candidates.
- **RS Line:** Daily ratio of `stock_close / spy_close`, normalized to 1.0 at the start of the lookback window. A rising RS line indicates the stock is outperforming the market.
- **RS Percentile Rank:** Each symbol's 252-trading-day (1-year) return, ranked as a percentile across all S&P 500 constituents in the universe (0–100). Higher = stronger relative performer vs peers.
- RS parameters shall be configurable per screener instance: `rs_min_percentile` (float, 0–100), `rs_slope_days` (int, lookback window for RS line slope sign check).
- If benchmark data is unavailable (SPY not yet bootstrapped), the screener shall raise a clear `BenchmarkDataUnavailableError` rather than silently skipping.
- **Acceptance Criteria:**
  - Indicator screener with `rs_min_percentile=70` passes only stocks whose 252-day RS rank is ≥ 70th percentile across the full universe.
  - RS line slope check over `rs_slope_days=20` correctly identifies stocks where `rs_line[-1] > rs_line[-20]`.
  - With SPY data absent from DB, screener raises `BenchmarkDataUnavailableError` naming the missing symbol.
  - RS rank is computed across all universe symbols, not just those that passed pre-filter.
  - Setting `rs_min_percentile=0` and `rs_slope_days=0` disables RS filtering entirely (backward compatible with v1 presets).

---

## FO-SCR-011: AI-Assisted Stock Ranking with Tool-Augmented Reasoning (Phase 1)
- **Status:** Approved

- The system shall extend the existing **Stage 3 LLM ranking layer** so that, after Stage 2 produces a filtered set of passing symbols, an AI provider analyses those symbols against a **user-authored natural-language query** (e.g. "find bullish breakout candidates with strong momentum") and returns a ranked list with **per-stock reasoning** (≤50 words each).
- The AI provider shall have **on-demand tool access to candle data** via a `get_candle_data` tool: `{symbol: str, timeframe: "1d" | "1w", lookback_bars: int (1–300)}`. The tool is backed by `DatabaseManager.fetch_bars()` and is restricted to symbols that passed Stage 2.
- The Phase 1 implementation shall use **Anthropic Claude Haiku 4.5** (`claude-haiku-4-5-20251001` snapshot, configurable per-preset) running a multi-turn `tool_use` agentic loop until the model returns `stop_reason="end_turn"`.
- Tool calls shall be capped at **3 per symbol per run** to prevent runaway loops; excess calls return an error to the model and the run continues with partial data.
- The user-authored query shall be a per-preset configuration field (`Preset.ai_query`, 1–500 chars) editable in the GUI Preset Builder. Existing presets default to an empty query and continue to work via the legacy hardcoded ranking prompt.
- Each ranked symbol shall include a `reasoning` string (≤50 words) explaining the AI's rationale (e.g. "Strong breakout above 50d MA, RSI healthy at 58, weekly volume 1.8× average"). The reasoning shall surface in the GUI results table as a new "AI Reasoning" column with full text in tooltip.
- The architecture shall remain **provider-agnostic** so Phase 2 (multi-provider single-choice) and Phase 3 (parallel orchestration with consensus) can extend it without rework. Specifically: the tool definition, multi-turn loop pattern, and reasoning JSON contract are designed to be portable to other providers (OpenAI function calling, Gemini tool use).
- **Acceptance Criteria:**
  - A preset with `ai_query="find bullish breakout candidates"` and `enable_llm_ranking=True` runs end-to-end on Stage 2 output and returns top-N symbols with per-stock reasoning.
  - Claude successfully invokes `get_candle_data` for at least one symbol during a typical run; returned bars match `DatabaseManager.fetch_bars()` output exactly.
  - Tool calls for symbols that did not pass Stage 2 are rejected by `CandleToolExecutor` with a clear error returned to the model.
  - The 3-call-per-symbol cap is enforced; the 4th call for any single symbol returns an error and the run completes with partial data.
  - `ScreenerRunResult.results[sym]["ai_reasoning"]` is populated with ≤50-word strings for each ranked symbol; empty for symbols that did not pass Stage 2 or when AI ranking did not run.
  - Existing presets without `ai_query` continue to function under the legacy ranking path with no behavioural change.
  - GUI: editing a preset reveals the "AI Query" `QLineEdit` when "Enable AI Ranking" is on; the field round-trips through preset save/load.
  - GUI: results table renders the "AI Reasoning" column with 60-char preview and full-text tooltip.

---

## FO-SCR-012: AI Transparency Transcript Panel
- **Status:** Approved

- When a preset has AI ranking enabled (`enable_llm_ranking=True`), the Screener Panel shall display a **read-only AI Transcript Panel** below the results table showing the complete conversation between the system and the AI provider:
  - The **system prompt** sent to the model.
  - The **initial user message** (serialised pre-extracted features JSON).
  - Each **assistant turn** — text content and any tool calls made (with arguments).
  - Each **tool result** returned to the model (candle data fetched per symbol).
  - The **final assistant response** (ranked list + reasoning).
  - A **token summary bar**: total input tokens, total output tokens, and estimated cost for the run.
- The panel shall be **hidden** when the active preset has `enable_llm_ranking=False` or when no run result is loaded.
- The full transcript (all turns) shall be **persisted** inside `ScreenerRunResult` so that loading a historical result date replays the complete AI conversation for that run.
- **Acceptance Criteria:**
  - After an AI-ranking run, the transcript panel appears below the results table showing all conversation turns in order.
  - System prompt, initial user message, each tool call/result pair, and the final response are all rendered as labelled, read-only blocks.
  - The token summary bar displays input token count, output token count, and estimated cost calculated from run metadata.
  - Selecting a past result date from the date picker loads and displays that run's transcript (or shows an empty panel if the run pre-dates this feature).
  - The panel is absent (`.hide()`) when viewing a result from a non-AI preset, or when `ai_transcript` is empty.
  - System prompt block is collapsed by default to avoid dominating the view; a toggle button expands it.

---

## FO-SCR-013: Indicator Catalogue and Rule-List Screening
- **Status:** Approved (user, 2026-10-22)
- **Extends:** FO-SCR-001 (preset framework), FO-SCR-002 (IndicatorScreener), FO-SCR-010 (RS vs benchmark). Does not replace them.

- The system shall keep one shared **indicator catalogue** in `core/` that lists every screener indicator with its name, category, description, parameters (default, min, max) and allowed conditions.
- The catalogue shall group indicators into categories: Price, Momentum, Trend, Volatility, Volume, Relative strength, Fundamentals, Dividends, Others.
- Adding a new daily indicator shall need only a catalogue entry and a compute function — no GUI or screener-engine change.
- The indicator screener config shall store an ordered **rule list**; each rule holds indicator id, condition, value, optional upper value, parameters and an enabled flag.
- The screener shall read old presets that store the legacy `filters` dict by mapping its 6 sections (volatility, rsi, range, breakout, volume, rs_index) to equivalent rules.
- A symbol shall pass only when every enabled rule passes; its score shall be the fraction of enabled rules that pass.
- The first release shall support these daily indicators: Price, ATR %, RSI, Breakout (N-bar high), Volume ratio, RVOL (1 Day), RS Index, EMA(20/50/100/200), Price/EMA(20/50/100), MACD, MACD Histogram, MACD Signal Line, PPO, PPO Histogram, PPO Signal Line, Market Cap.
- ATR and RSI shall use standard Wilder smoothing (TA-Lib), as SRD-SCR-002.003 already requires.
- Intraday indicators (RVOL 3/5/10 Min, Short-Term Volume 3/5/10 Min) shall be listed as unavailable with the reason "needs intraday data" until an intraday data source exists.
- The screener Details summary shall be built from the catalogue, so new indicators show without code changes.
- **Acceptance Criteria:**
  - An old preset with the 6-section `filters` dict loads as 6 rules with the same thresholds and enabled flags.
  - A rule list with RSI between 30 and 70 passes only symbols whose Wilder RSI(14) is in that band.
  - A MACD rule "crosses above signal" passes a symbol only when the MACD line crossed above its signal line on the last bar.
  - A disabled rule does not change pass/fail or score.
  - Adding a test-only catalogue entry makes it usable in a rule without editing the screener.
  - Rules on unavailable indicators are rejected with a clear error.

---

## FO-SCR-014: Price Action Pattern Catalogue and Rule-List Screening
- **Status:** Approved (user, 2026-10-22)
- **Extends:** FO-SCR-002 / SRD-SCR-002.007 (PriceActionScreener, 5 patterns). Does not replace them.

- The system shall keep one shared **price action pattern catalogue** in `core/` that lists every pattern with its name, category, direction (bullish / bearish / neutral), description and parameters (default, min, max).
- The catalogue shall group patterns into: Bullish candles, Bearish candles, Neutral candles, Breakout, Trend, Volatility, Chart shapes.
- The first release shall offer 27 candlestick patterns computed with TA-Lib and 20 breakout / trend / volatility / chart-shape patterns computed from daily OHLCV bars.
- The 4 existing non-candle patterns (Near 52-Week High, Volume Breakout, NR7, EMA Pullback) shall keep their ids, parameters and results.
- Adding a new pattern shall need only a catalogue entry and a detect function — no GUI or screener-engine change.
- The price action screener config shall store an ordered **rule list** (pattern id, parameters, enabled flag) plus the pass threshold.
- The screener shall read old presets that store the legacy `patterns` dict and map its 5 sections to equivalent rules, keeping the threshold.
- A symbol's score shall stay matched ÷ enabled patterns, and it shall pass when the score is at least the threshold.
- The screener Details summary shall be built from the catalogue.
- *(Added 2026-10-22, user request)* The catalogue shall offer Double Top (breakdown) and Double Top Pullback (retest of the broken neck) as bearish chart shapes for sell setups, and Double Bottom shall match only a recent breakout.
- *(Added 2026-10-22, user request)* The catalogue shall offer Fibonacci retracement patterns — Sell (bounce up into the zone after a fall) and Buy (dip into the zone after a rise) — with a settable zone, default 50–61.8 %.
- **Acceptance Criteria:**
  - An old preset with the 5-section `patterns` dict loads as 5 rules with the same parameters, on/off states and threshold.
  - A bar series that TA-Lib flags as a bullish engulfing matches Bullish Engulfing and not Bearish Engulfing.
  - With 4 patterns enabled, 1 matched and threshold 20%, the symbol passes with score 0.25.
  - A disabled pattern does not change pass/fail or score.
  - Adding a test-only catalogue entry makes it usable in a rule without editing the screener.
  - An unknown pattern id is rejected with a clear error.
