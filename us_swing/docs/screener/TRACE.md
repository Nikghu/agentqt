# Traceability Matrix — Screener (SCR)

**Document ID:** TRACE-SCR
**Version:** 2.2.0
**Traces To:** FO-SCR v2.1.0, SRD-SCR v2.3.0, DD-SCR v2.1.0, MD-SCR v2.2.0, UTCD-SCR v2.1.0
**Status:** Draft
**Last Updated:** 2026-05-06 (SRD-SCR-014.008 + MD-SCR-014.008.M20 added for ai_model_store.py)
**Project:** US Swing Trading System

---

## Executive Summary

| Document | Version | Count | Status |
|---|---|---|---|
| FO-SCR | 2.1.0 | 11 Functional Objectives | Draft |
| SRD-SCR | 2.1.0 | 86 Software Requirements | Draft |
| DD-SCR | 2.1.0 | 21 Design Descriptions | Draft |
| MD-SCR | 2.1.0 | 18 Module Definitions | Draft |
| UTCD-SCR | 2.1.0 | 138 Unit Tests + 15 Integration Tests | Draft |

**Total Coverage:** 357 traceability items across all artifact types.

---

## FO → SRD Coverage

| FO ID | Title | Parent SRDs | SRD Count |
|---|---|---|---|
| FO-SCR-001 | Flexible Preset Framework | SRD-001.001–009 | 9 |
| FO-SCR-002 | Plugin-Based Screener Architecture | SRD-002.001–008 | 8 |
| FO-SCR-003 | Three-Stage Execution Pipeline | SRD-003.001–008 | 8 |
| FO-SCR-004 | Hybrid Execution Modes | SRD-004.001–006 | 6 |
| FO-SCR-005 | User-Accessible Preset Management | SRD-005.001–008 | 8 |
| FO-SCR-006 | LLM Ranking Layer & Cost Tracking | SRD-006.001–007 | 7 |
| FO-SCR-007 | GUI Preset Builder | SRD-007.001–012 | 12 |
| FO-SCR-008 | Result Persistence & History | SRD-008.001–005 | 5 |
| FO-SCR-009 | Backward Compatibility & v1 Migration | SRD-009.001–004 | 4 |
| FO-SCR-010 | Relative Strength vs Benchmark | SRD-012.001–005 | 5 |
| FO-SCR-011 | AI-Assisted Stock Ranking (Phase 1) | SRD-013.001–008 | 8 |
| — | Cross-Cutting (Error, Performance) | SRD-010, 011 | 10 |
| **Total** | — | — | **86** |

---

## SRD → DD Coverage

| SRD Section | Description | Parent DD | DD Count |
|---|---|---|---|
| SRD-001 — Preset Model | Dataclass, serialization, validation | DD-SCR-001.001.D01 | 1 |
| SRD-001.009 — trading_styles | `trading_styles` field + validation | DD-SCR-001.009.D01 | 1 |
| SRD-002 — Screener Plugins | Protocol, registry, built-in types | DD-SCR-002.001.D01 | 1 |
| SRD-003 — Execution Pipeline | 3-stage orchestration | DD-SCR-003.001.D01 | 1 |
| SRD-004 — Execution Modes | Scheduled + on-demand execution | (in D03) | — |
| SRD-005 — Preset Management | CRUD, permissions | DD-SCR-004.001.D01 | 1 |
| SRD-005.004 — style_filter | `style_filter` param on list methods | DD-SCR-005.004.D01 | 1 |
| SRD-006 — LLM & Cost | Feature cache, API tracking | DD-SCR-006.001.D01 | 1 |
| SRD-007 — GUI | Builder components | DD-SCR-007.001.D01 | 1 |
| SRD-007.010 — Style filter dropdown | Style filter `QComboBox` in Screener Panel | DD-SCR-007.010.D01 | 1 |
| SRD-007.011 — Style checkboxes | Trading style checkboxes in Preset Builder | DD-SCR-007.011.D01 | 1 |
| SRD-007.012 — Assign Users | Tokenized user assignment in Preset Builder | DD-SCR-007.012.D01 | 1 |
| SRD-008 — Persistence | Result storage, history | (in D06) | — |
| SRD-009 — Migration | v1 preset migration | (in D04) | — |
| SRD-010 — Error Handling | Error hierarchy, handling | (cross-module) | — |
| SRD-011 — Performance | Monitoring, timing | (cross-module) | — |
| **Total** | — | — | **20** |

---

## DD → MD Coverage

| DD ID | Design | Modules (Primary) | Module Count |
|---|---|---|---|
| D01 — Preset Model | Preset serialization, validation | M01 (preset.py), M03 (registry.py) | 2 |
| D01 — Screener Protocol | Screener interface, registry | M02 (base.py), M03 (registry.py) | 2 |
| D01 — Execution Pipeline | PresetExecutor orchestration | M10 (executor.py), M14 (utils.py) | 2 |
| D01 — PresetManager | CRUD + permissions | M12 (manager.py) | 1 |
| D01 — Scheduler | Cron scheduling | M11 (scheduler.py) | 1 |
| D01 — Result Storage | File I/O, caching, cost tracking | M13 (storage.py) | 1 |
| D01 — LLM Integration | Claude API ranking | M06 (cloud_ai.py) | 1 |
| D01 — RS Calculations | RS line, RS rank, BenchmarkDataUnavailableError | M04 (indicator.py) | 1 |
| D01 — GUI Architecture | Preset builder panel | (deferred) | 0 |
| — | Screener Plugins | M04 (indicator), M05 (ml), M06 (cloud_ai), M07–09 (optional) | 6 |
| — | Package Integration | M15 (__init__.py) | 1 |
| **Total** | — | — | **15** |

---

## MD → UT Coverage

| Module | UT File | Unit Test Count | Integration Tests | Total Coverage |
|---|---|---|---|---|
| M01: preset.py | test_preset.py | 16 | 2 | 18 |
| M02: base.py | (protocol, no direct tests) | — | 1 | 1 |
| M03: registry.py | test_registry.py | 6 | 1 | 7 |
| M04: indicator.py | test_indicator_screener.py | 8 | 2 | 10 |
| M05: ml.py | test_ml_screener.py | 5 | 1 | 6 |
| M06: cloud_ai.py | test_llm_claude_screener.py | 10 | 3 | 13 |
| M10: executor.py | test_executor.py | 20 | 5 | 25 |
| M11: scheduler.py | test_scheduler.py | 6 | 1 | 7 |
| M12: manager.py | test_manager.py | 20 | 3 | 23 |
| M13: storage.py | test_storage.py | 12 | 2 | 14 |
| M14: utils.py | test_utils.py | 8 | 2 | 10 |
| M16: gui/screener_panel.py | test_screener_panel.py | 5 (Phase 5) | — | 5 |
| M17: gui/preset_builder.py | test_preset_builder.py | 8 (Phase 5) | — | 8 |
| **Total** | — | **112** | **23** | **135** |

---

## Comprehensive Trace: FO → Implementation

### FO-SCR-001: Flexible Preset Framework

```
FO-001
  ├─ SRD-001.001: Preset dataclass with fields
  │   ├─ DD-SCR-001.001: @dataclass Preset
  │   │   ├─ MD-SCR-M01: src/screener/preset.py
  │   │   │   ├─ UT: test_preset.py T01
  │   │   │   └─ UT: test_preset.py T02 (round-trip)
  ├─ SRD-001.002: ScreenerRef dataclass
  │   ├─ DD-SCR-001.001: @dataclass ScreenerRef
  │   │   ├─ MD-SCR-M01: src/screener/preset.py
  │   │   │   └─ UT: test_preset.py T06–T08
  ├─ SRD-001.003: ScreenerGroup dataclass
  │   ├─ DD-SCR-001.001: @dataclass ScreenerGroup
  │   │   ├─ MD-SCR-M01: src/screener/preset.py
  │   │   │   └─ UT: test_preset.py T09
  ├─ SRD-001.004–005: Serialization + validation
  │   ├─ DD-SCR-001.001: to_dict(), from_dict(), validate()
  │   │   ├─ MD-SCR-M01: src/screener/preset.py
  │   │   │   └─ UT: test_preset.py T01–T12
  ├─ SRD-001.006–008: Composite/Weighted result structures
  │   ├─ DD-SCR-003.001: _apply_composite_logic(), _apply_weighted_logic()
  │   │   ├─ MD-SCR-M10: src/screener/executor.py
  │   │   │   └─ UT: test_executor.py T10–T15
  │   │   └─ IT: test_integration.py T02–T03 (composite/weighted logic)
```

### FO-SCR-002: Plugin-Based Screener Architecture

```
FO-002
  ├─ SRD-002.001: Screener protocol
  │   ├─ DD-SCR-002.001: class Screener(Protocol)
  │   │   ├─ MD-SCR-M02: src/screener/base.py
  │   │   │   └─ UT: (protocol verification in registry + screener tests)
  ├─ SRD-002.002: ScreenerRegistry
  │   ├─ DD-SCR-002.001: class ScreenerRegistry
  │   │   ├─ MD-SCR-M03: src/screener/registry.py
  │   │   │   └─ UT: test_registry.py T01–T06
  ├─ SRD-002.003: IndicatorScreener (v1 refactor)
  │   ├─ DD-SCR-002.001: class IndicatorScreener(Screener)
  │   │   ├─ MD-SCR-M04: src/screener/screeners/indicator.py
  │   │   │   └─ UT: test_indicator_screener.py T01–T08
  │   │   └─ IT: test_integration.py T04 (v1 equivalence)
  ├─ SRD-002.004: MLScreener
  │   ├─ DD-SCR-002.001: class MLScreener(Screener)
  │   │   ├─ MD-SCR-M05: src/screener/screeners/ml.py
  │   │   │   └─ UT: test_ml_screener.py T01–T05
  │   │   └─ IT: test_integration.py T03 (weighted with ML)
  ├─ SRD-002.005: CloudAIScreener (for ranking)
  │   ├─ DD-SCR-002.001: class CloudAIScreener(Screener)
  │   │   ├─ MD-SCR-M06: src/us_swing/screener/screeners/cloud_ai.py
  │   │   │   └─ UT: test_llm_claude_screener.py T01–T10
  │   │   └─ IT: test_integration.py T07–T09 (LLM ranking workflows)
  ├─ SRD-002.006–008: LLMLocal, PriceAction, MCP (optional stubs)
  │   └─ Status: Deferred to Phase 2+
```

### FO-SCR-003: Three-Stage Execution Pipeline

```
FO-003
  ├─ SRD-003.001: PreFilter class
  │   ├─ DD-SCR-003.001: class PreFilter
  │   │   ├─ MD-SCR-M14: src/screener/utils.py
  │   │   │   └─ UT: test_utils.py T01–T05
  ├─ SRD-003.002–005: PresetExecutor 3-stage pipeline
  │   ├─ DD-SCR-003.001: run_preset(), _run_stage2(), _run_stage3()
  │   │   ├─ MD-SCR-M10: src/screener/executor.py
  │   │   │   └─ UT: test_executor.py T01–T20
  │   │   └─ IT: test_integration.py T01–T09 (all pipeline variations)
  ├─ SRD-003.006: Composite preset logic
  │   ├─ DD-SCR-003.001: _apply_composite_logic()
  │   │   └─ UT: test_executor.py T10–T12
  ├─ SRD-003.007: Weighted preset logic
  │   ├─ DD-SCR-003.001: _apply_weighted_logic()
  │   │   └─ UT: test_executor.py T13–T15
  ├─ SRD-003.008: ScreenerRunResult dataclass
  │   ├─ DD-SCR-003.001: @dataclass ScreenerRunResult
  │   │   ├─ MD-SCR-M13: src/screener/storage.py
  │   │   │   └─ UT: test_storage.py T01–T03
```

### FO-SCR-004: Hybrid Execution Modes

```
FO-004
  ├─ SRD-004.001: ScreenerScheduler (cron)
  │   ├─ DD-SCR-004.001: class ScreenerScheduler
  │   │   ├─ MD-SCR-M11: src/screener/scheduler.py
  │   │   │   └─ UT: test_scheduler.py T01–T06
  │   │   └─ IT: test_integration.py T06 (cron trigger)
  ├─ SRD-004.002–003: On-demand manual trigger
  │   ├─ DD-SCR-003.001: run_preset(..., manual=True)
  │   │   └─ IT: test_integration.py T05 (manual overwrite)
  ├─ SRD-004.004–006: Result file storage + events
  │   ├─ DD-SCR-006.001: ScreenerResultsStorage.save_result()
  │   │   ├─ MD-SCR-M13: src/screener/storage.py
  │   │   │   └─ UT: test_storage.py T01–T06
```

### FO-SCR-005: User-Accessible Preset Management

```
FO-005
  ├─ SRD-005.001–008: PresetManager (CRUD + permissions)
  │   ├─ DD-SCR-004.001: class PresetManager
  │   │   ├─ MD-SCR-M12: src/screener/manager.py
  │   │   │   └─ UT: test_manager.py T01–T15
  │   │   └─ IT: test_integration.py T10–T13 (permissions, workflows)
```

### FO-SCR-006: LLM Ranking & Cost Tracking

```
FO-006
  ├─ SRD-006.001: batch_features() (feature extraction)
  │   ├─ DD-SCR-006.001: class FeatureCache
  │   │   ├─ MD-SCR-M06: src/us_swing/screener/screeners/cloud_ai.py
  │   │   │   └─ UT: test_llm_claude_screener.py T01–T02
  ├─ SRD-006.002–003: Feature caching (24h TTL)
  │   ├─ DD-SCR-006.001: class FeatureCache
  │   │   ├─ MD-SCR-M13: src/screener/storage.py
  │   │   │   └─ UT: test_storage.py T07–T10
  ├─ SRD-006.004–007: APIUsageTracker + cost threshold
  │   ├─ DD-SCR-006.001: class APIUsageTracker
  │   │   ├─ MD-SCR-M13: src/screener/storage.py
  │   │   │   └─ UT: test_storage.py T11–T12
```

### FO-SCR-007: GUI Preset Builder

```
FO-007
  ├─ SRD-007.001–009: GUI components
  │   ├─ DD-SCR-007.001: (ScreenerPanel, PresetBuilderPanel — deferred, UI framework TBD)
  │   │   └─ Status: Phase 5 (not in MVP unit tests)
  ├─ SRD-007.010: Style filter dropdown in Screener Panel
  │   ├─ DD-SCR-007.010.D01: QComboBox above preset selector
  │   │   └─ Status: Design complete; implementation Phase 5
  ├─ SRD-007.011: Trading Style checkboxes in Preset Builder
  │   ├─ DD-SCR-007.011.D01: QGroupBox + QCheckBox × 3, editable/read-only modes
  │   │   └─ Status: Design complete; implementation Phase 5
  ├─ SRD-007.012: Assign Users tokenized input in Preset Builder
  │   ├─ DD-SCR-007.012.D01: AssignUsersWidget (immediate grant/revoke on token add/remove)
  │   │   └─ Status: Design complete; implementation Phase 5
```

### FO-SCR-001 (amendment): trading_styles Field

```
FO-001
  ├─ SRD-001.009: trading_styles field in Preset
  │   ├─ DD-SCR-001.009.D01: list[Literal["swing","day","position"]], default []
  │   │   ├─ MD-SCR-M01: src/screener/preset.py (amended)
  │   │   │   └─ UT: test_preset.py (T13–T16 TBD in UTCD update)
```

### FO-SCR-005 (amendment): style_filter on list Methods

```
FO-005
  ├─ SRD-005.004: style_filter param on list_admin_presets / list_user_presets
  │   ├─ DD-SCR-005.004.D01: _apply_style_filter() helper; empty list passes filter
  │   │   ├─ MD-SCR-M12: src/screener/manager.py (amended)
  │   │   │   └─ UT: test_manager.py (T16–T19 TBD in UTCD update)
```

### FO-SCR-008: Result Persistence & History

```
FO-008
  ├─ SRD-008.001–005: ScreenerResultsStorage
  │   ├─ DD-SCR-006.001: class ScreenerResultsStorage
  │   │   ├─ MD-SCR-M13: src/screener/storage.py
  │   │   │   └─ UT: test_storage.py T01–T06
  │   │   └─ IT: test_integration.py T15 (persistence)
```

### FO-SCR-009: Backward Compatibility & v1 Migration

```
FO-009
  ├─ SRD-009.001–004: v1 migration + IndicatorScreener equivalence
  │   ├─ DD-SCR-001.001: Preset.migrate_v1_presets()
  │   │   ├─ MD-SCR-M12: src/screener/manager.py
  │   │   │   └─ UT: test_manager.py T15
  │   ├─ DD-SCR-002.001: IndicatorScreener(v1 filters)
  │   │   ├─ MD-SCR-M04: src/screener/screeners/indicator.py
  │   │   │   └─ UT: test_indicator_screener.py T01 (v1 equivalence)
  │   │   └─ IT: test_integration.py T04 (migration + execution)
```

---

### FO-SCR-010: Relative Strength vs Benchmark

```
FO-010
  ├─ SRD-012.001: RS line per symbol (stock_close / spy_close, normalised to 1.0)
  │   ├─ DD-SCR-002.001: compute_rs_line() in IndicatorScreener
  │   │   ├─ MD-SCR-002.001.M04: src/us_swing/screener/screeners/indicator.py
  │   │   │   └─ UT: test_indicator_screener.py T01–T08
  ├─ SRD-012.002: RS percentile rank — universe-wide 252d return, scipy percentileofscore
  │   ├─ DD-SCR-002.001: compute_rs_rank() in IndicatorScreener
  │   │   ├─ MD-SCR-002.001.M04: src/us_swing/screener/screeners/indicator.py
  │   │   │   └─ UT: test_indicator_screener.py T01–T08
  ├─ SRD-012.003: rs_min_percentile + rs_slope_days config params; backward-compat defaults
  │   ├─ DD-SCR-002.001: IndicatorScreener config schema extension
  │   │   └─ MD-SCR-002.001.M04: src/us_swing/screener/screeners/indicator.py
  ├─ SRD-012.004: BenchmarkDataUnavailableError — raised when SPY bars absent
  │   ├─ DD-SCR-002.001: BenchmarkDataUnavailableError definition in indicator.py
  │   │   └─ MD-SCR-002.001.M04: src/us_swing/screener/screeners/indicator.py
  ├─ SRD-012.005: RS rank computed once per run (vectorised numpy/pandas; <2 s for 500 symbols)
  │   ├─ DD-SCR-002.001: vectorised RS rank batch computation
  │   │   └─ MD-SCR-002.001.M04: src/us_swing/screener/screeners/indicator.py
```

### FO-SCR-010 Coverage Summary

| SRD | DD | MD | UT File | Tests | Status |
|---|---|---|---|---|---|
| SRD-012.001 | DD-SCR-002.001 | M04 | test_indicator_screener.py | T01–T08 | Draft |
| SRD-012.002 | DD-SCR-002.001 | M04 | test_indicator_screener.py | T01–T08 | Draft |
| SRD-012.003 | DD-SCR-002.001 | M04 | test_indicator_screener.py | T01–T08 | Draft |
| SRD-012.004 | DD-SCR-002.001 | M04 | test_indicator_screener.py | T01–T08 | Draft |
| SRD-012.005 | DD-SCR-002.001 | M04 | test_indicator_screener.py | T01–T08 | Draft |

---

## Test Coverage Summary

| Category | Count | Coverage % | Status |
|---|---|---|---|
| Unit Tests | 98 | — | Draft |
| Integration Tests | 15 | — | Draft |
| Total Tests | 113 | — | Draft |
| SRD → Code Mapping | 77/77 | 100% | ✅ |
| FO → SRD Mapping | 9/9 | 100% | ✅ |
| Code → Test Mapping | 15/15 | 100% | ✅ (GUI modules pending Phase 5) |

---

## Implementation Readiness

| Dimension | Status | Evidence |
|---|---|---|
| Requirements Complete | ✅ | All 9 FOs → 77 SRDs traced |
| Design Complete | ✅ | 20 DD sections covering all SRDs |
| Modules Defined | ✅ | 17 MD entries with dependencies |
| Tests Specified | ✅ | 127 UTs + 15 ITs with clear acceptance criteria |
| v1 Equivalence Defined | ✅ | Indicator screener equiv + migration test (T04) |
| Backward Compatibility Defined | ✅ | v1 migration process + removal plan |

---

## Known Deferred Items

| Item | Reason | Target Phase |
|---|---|---|
| GUI component tests | UI framework TBD | Phase 5+ |
| Performance stress tests | Not enforced in MVP | Phase 2+ |
| Distributed scheduler | Single APScheduler | Future |
| Price Action screener | Optional | Phase 2+ |
| MCP screener | Stub/extensibility point | Phase 3+ |

---

**Status:** v2.0.1 DD complete for trading-style feature. Ready for MD and UTCD updates.

**Prepared by:** Architecture Review (2026-04-16)  
**Last Updated:** 2026-04-24  
**Next Step:** Implementation Phase — coding begins with Phase 1 (preset.py trading_styles + manager.py style_filter), then Phase 5 GUI (screener_panel.py, preset_builder.py)

---

## FO-SCR-011 Trace (Phase 1 AI Stock Ranking)

```
FO-011
  ├─ SRD-013.001: Preset.ai_query / ai_model fields
  │   ├─ DD-SCR-011.001.D21
  │   │   ├─ MD-SCR-001.001.M01: src/us_swing/screener/preset.py
  │   │   │   └─ UT: test_preset.py T17–T20
  ├─ SRD-013.002: get_candle_data tool schema
  │   └─ DD-SCR-011.001.D21 (provider-agnostic schema)
  │       └─ MD-SCR-002.003.M06: src/us_swing/screener/screeners/cloud_ai.py
  │           └─ UT: test_llm_claude_screener.py T11
  ├─ SRD-013.003: CandleToolExecutor
  │   ├─ DD-SCR-011.001.D21
  │   │   ├─ MD-SCR-011.001.M18: src/us_swing/screener/screeners/_tool_executor.py
  │   │   │   └─ UT: test_tool_executor.py T01–T10
  ├─ SRD-013.004: per-symbol call cap (default 3)
  │   └─ MD-SCR-011.001.M18
  │       └─ UT: test_tool_executor.py T03
  ├─ SRD-013.005: multi-turn tool_use loop
  │   ├─ DD-SCR-011.001.D21
  │   │   ├─ MD-SCR-002.003.M06: src/us_swing/screener/screeners/cloud_ai.py
  │   │   │   └─ UT: test_llm_claude_screener.py T11–T15
  ├─ SRD-013.006: PresetExecutor passes db + passing_symbols + ai_query/ai_model
  │   ├─ DD-SCR-011.001.D21
  │   │   ├─ MD-SCR-003.001.M10: src/us_swing/screener/executor.py
  │   │   │   └─ UT: test_executor.py T21
  ├─ SRD-013.007: ai_reasoning side-channel merged into result.results[sym]
  │   ├─ DD-SCR-011.001.D21
  │   │   ├─ MD-SCR-003.001.M10: src/us_swing/screener/executor.py
  │   │   │   └─ UT: test_executor.py T22
  ├─ SRD-013.008: GUI — AI Query field + AI Reasoning column
  │   ├─ DD-SCR-011.001.D21
  │   │   ├─ MD-SCR-007.010.M16: src/us_swing/screener/gui/screener_panel.py
  │   │   │   └─ UT: deferred (Phase 5 pytest-qt smoke)
```

### FO-SCR-011 Coverage Summary

| SRD | DD | MD | UT File | Tests | Status |
|---|---|---|---|---|---|
| SRD-013.001 | D21 | M01 | test_preset.py | T17–T20 (4) | Draft → Pass |
| SRD-013.002 | D21 | M06 | test_llm_claude_screener.py | T11 | Draft → Pass |
| SRD-013.003 | D21 | M18 | test_tool_executor.py | T01–T10 | Draft → Pass |
| SRD-013.004 | D21 | M18 | test_tool_executor.py | T03 | Draft → Pass |
| SRD-013.005 | D21 | M06 | test_llm_claude_screener.py | T11–T15 (5) | Draft → Pass |
| SRD-013.006 | D21 | M10 | test_executor.py | T21 | Draft → Pass |
| SRD-013.007 | D21 | M10 | test_executor.py | T22 | Draft → Pass |
| SRD-013.008 | D21 | M16 | (deferred Phase 5) | — | Pending |

**Test totals added by FO-SCR-011:** 22 unit tests across 4 modules.

### FO-SCR-012 Coverage Summary (SRD-SCR-014)

| SRD | DD | MD | UT File | Tests | Status |
|---|---|---|---|---|---|
| SRD-014.001 | — | M13 (storage.py) | test_storage.py | — | Approved |
| SRD-014.002 | — | M13 (storage.py) | test_storage.py | — | Approved |
| SRD-014.003 | — | M06 (cloud_ai.py) | test_llm_claude_screener.py | — | Approved |
| SRD-014.004 | — | MD-SCR-014.004.M22 (ai_transcript_panel.py) | (deferred Phase 5) | — | Approved |
| SRD-014.005 | — | MD-SCR-014.004.M22 (ai_transcript_panel.py) | (deferred Phase 5) | — | Approved |
| SRD-014.006 | — | M16 (screener_panel.py) | (deferred Phase 5) | — | Approved |
| SRD-014.007 | — | M16 (screener_panel.py) | (deferred Phase 5) | — | Approved |
| SRD-014.008 | — | MD-SCR-014.008.M20 (ai_model_store.py) | (pending) | — | Implemented |

---

**Status:** v2.1.0 — FO-SCR-011 (Phase 1 AI Stock Ranking) traced through SRD/DD/MD/UTCD. All 22 new unit tests pass; GUI smoke deferred to Phase 5.
