# Module Decomposition — Market Analytics (MKT)

**Document ID:** MD-MKT
**Version:** 0.9.0
**Status:** Draft
**Last Updated:** 2026-11-11
**Project:** US Swing Trading System

> v0.23.0: M05, M07, M04 (news and store), M01 and M02 (watch) changed for AI Desk v3 M1 (2026-11-13).
> v0.22.0: MD-MKT-019.001.M01, .003.M02, .005.M03, .009.M04, .012.M05 added — strategy test research; lead_brief changed (2026-11-12).
> v0.21.0: MD-MKT-018.001.M01, .002.M02, .006.M03 added — book to strategy research (step F); M08 lead_brief changed.
> v0.20.0: MD-MKT-017.001.M01, .004.M02, .006.M03 added — sentiment research (step F); M08 lead_brief changed.
> v0.19.0: MD-MKT-016.001.M01 and .004.M02 added — pick post-mortem research (step F).
> v0.18.0: MD-MKT-015.001.M01, .002.M02, .004.M03, .005.M04 added — setup tuning research (step F).
> v0.17.0: MD-MKT-014.001.M01–M02 added — lead research tickets (step E).
> v0.16.0: MD-MKT-013.*.M01–M04 added — intraday watchers and check-in notes (step D).
> v0.15.0: MD-MKT-012.*.M01–M03 added — learning from pick results (step C).
> v0.14.0: MD-MKT-001.013.M06 added — candle check and Yahoo desk copy; M08 morning brief (Autonomous desk step A, 2026-11-11).
> v0.13.0: MD-MKT-011.*.M01–M06 added — ask the desk for new data (P10).
> v0.12.0: MD-MKT-010.*.M01–M04 added — lead chat (P9).
> v0.11.0: MD-MKT-009.*.M01–M06 added — pick results (P8).
> v0.10.0: MD-MKT-008.*.M01–M02 added — link to Execution (P7).
> v0.9.0: MD-MKT-007.*.M01–M04 added — AI report pages (P5d).
> v0.8.0: MD-MKT-006.*.M01–M06 added — news, economic calendar and event risk (P5c).
> v0.7.0: MD-MKT-005.*.M04–M09 added — sector/flow view, setup review, risk limits, risk check, lead brief, defaults (P5b).
> v0.6.0: MD-MKT-005.*.M01–M03 added — regime view skill (P5a).
> v0.5.0: MD-MKT-004.*.M01–M03 added — proof on past data (P4).
> v0.4.0: MD-MKT-003.*.M01–M07 added — money flow, setups, readiness score and ideas (P3).
> v0.3.0: MD-MKT-002.*.M01–M05 added — sector strength, rotation and stock RS (P2).
> v0.2.0: MD-MKT-001.*.M01–M05 added — regime, breadth and fear (P1).
> v0.1.0: Empty. Rows are added per phase, starting with the first FO of this tool.

---

## FO-MKT-001: Market Regime, Breadth and Fear

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-MKT-001.001.M01 | SRD-MKT-001.001 | `us_swing/src/us_swing/market/candles.py` | Read-only daily bars for SPY and S&P 500 members | `CandleReader`, `member_symbols()` | `sqlite3`, `pandas`, `core.backtest_bridge` | No |
| MD-MKT-001.002.M02 | SRD-MKT-001.002 | `us_swing/src/us_swing/market/regime.py` | Pure rules: regime, volatility, breadth, fear | `regime_series()`, `volatility_series()`, `breadth_frame()`, `fear_reading()` | `pandas`, `numpy` | No |
| MD-MKT-001.005.M03 | SRD-MKT-001.005 | `us_swing/src/us_swing/market/vix.py` | Fetch daily VIX and VIX3M from Yahoo Finance | `fetch_vix()` | `yfinance` | No |
| MD-MKT-001.007.M04 | SRD-MKT-001.007 | `us_swing/src/us_swing/market/store.py` | Market tables in `desk.db` | `MarketStore` | `sqlite3` | No |
| MD-MKT-001.011.M05 | SRD-MKT-001.011 | `us_swing/src/us_swing/market/step.py` | Desk step: incremental compute and save | `RegimeStep` | M01–M04, `core.desk_contract` | No |
| MD-MKT-001.013.M06 | SRD-MKT-001.013 | `us_swing/src/us_swing/market/candle_check.py` | Desk step "Candle check": target day, stocks behind, Yahoo fill into the desk copy, stop the run when still behind | `CandleCheckStep`, `CandleCheckError`, `last_closed_day()`, `topup_rows()`, `fetch_daily()` | M01, M04, `core.desk_alerts`, `core.symbols`, `yfinance` | No |

SRD coverage: .001 by M01; .002, .003, .004, .006 by M02; .005 by M03; .007 by M04; .008, .009, .010, .011, .012 by M05; .013, .014, .016, .017 by M06; .014 also M04 (`candle_topup`); .015 by M01 (`CandleReader(topup=)`), M04 (`trim_topup`) and `market/regime_view.py` (`latest_spy_day`).

Changed for .015: `step.py`, `sector_step.py`, `idea_step.py`, `pick_results.py` pass `topup=` to `CandleReader`; `setup_review.ideas_day`, `regime_view`, `sector_view` pass the store to `latest_spy_day`. `core/desk_steps.py` (MD-DSK-001.021.M07) puts the Candle check first.

## FO-MKT-002: Sector Strength and Rotation

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-MKT-002.001.M01 | SRD-MKT-002.001 | `us_swing/src/us_swing/market/candles.py` | Sector of each member (added to the P1 reader) | `member_sectors()` | `core.backtest_bridge` | No |
| MD-MKT-002.002.M02 | SRD-MKT-002.002 | `us_swing/src/us_swing/market/sectors.py` | Pure rules: sector lines, relative moves, rank, RS-ratio, RS-momentum, quadrant | `sector_lines()`, `sector_table()`, `quadrant()` | `pandas`, `numpy` | No |
| MD-MKT-002.006.M03 | SRD-MKT-002.006 | `us_swing/src/us_swing/market/rs.py` | Pure rules: stock RS score, rating and sector rank | `rs_scores()`, `rs_table()` | `pandas`, `numpy` | No |
| MD-MKT-002.008.M04 | SRD-MKT-002.008 | `us_swing/src/us_swing/market/store.py` | `sector_daily` and `stock_rs` tables (added to the P1 store) | `SectorRow`, `StockRsRow`, `MarketStore.write_sector_days()`, `stored_sector_dates()` | `sqlite3` | No |
| MD-MKT-002.009.M05 | SRD-MKT-002.009 | `us_swing/src/us_swing/market/sector_step.py` | Desk step "Sectors" | `SectorStep` | M01–M04, `core.desk_contract` | No |

SRD coverage: .001 by M01; .002, .003, .004, .005 by M02; .006, .007 by M03; .008 by M04; .009, .010 by M05.

## FO-MKT-003: Money Flow, Setups, Readiness Score and Ideas

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-MKT-003.001.M01 | SRD-MKT-003.001 | `us_swing/src/us_swing/market/candles.py` | Volume in the daily bars (added to the P1 reader) | `DailyBars.volumes` | `pandas` | No |
| MD-MKT-003.002.M02 | SRD-MKT-003.002 | `us_swing/src/us_swing/market/flow.py` | Pure rules: liquidity and money flow | `dollar_volume()`, `money_flow()`, `roll()` | `pandas`, `numpy` | No |
| MD-MKT-003.003.M03 | SRD-MKT-003.003 | `us_swing/src/us_swing/market/setups.py` | Pure rules: long and short setups with trigger, stop and tightness | `long_setups()`, `short_setups()`, `long_candidates()`, `short_candidates()` | `pandas`, `numpy` | No |
| MD-MKT-003.005.M04 | SRD-MKT-003.005 | `us_swing/src/us_swing/market/score.py` | Score parts, penalty, ideas, Watch and reasons | `score_frame()`, `readiness_score()`, `pick_ideas()` | M02, M03 | No |
| MD-MKT-003.009.M05 | SRD-MKT-003.009 | `us_swing/src/us_swing/market/earnings.py` | Next earnings dates from Yahoo Finance | `next_earnings()` | `yfinance` | No |
| MD-MKT-003.010.M06 | SRD-MKT-003.010 | `us_swing/src/us_swing/market/store.py` | `stock_score`, `ideas` and `idea_reasons` tables (added to the P1 store) | `ScoreRow`, `IdeaRow`, `ReasonRow`, `MarketStore.write_idea_days()`, `stored_idea_dates()` | `sqlite3` | No |
| MD-MKT-003.011.M07 | SRD-MKT-003.011 | `us_swing/src/us_swing/market/idea_step.py` | Desk step "Ideas" | `IdeaStep` | M01–M06, `core.desk_contract` | No |

SRD coverage: .001 by M01 and M02; .002 by M02; .003, .004 by M03; .005, .006, .007, .008 by M04; .009 by M05; .010 by M06; .011, .012 by M07.

## FO-MKT-004: Proof on Past Data

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-MKT-004.001.M01 | SRD-MKT-004.001 | `us_swing/src/us_swing/market/proof_data.py` | Read the Backtest Data daily files into daily bars | `read_daily()`, `history_years()` | `pandas`, `pyarrow` | No |
| MD-MKT-004.002.M02 | SRD-MKT-004.002 | `us_swing/src/us_swing/market/proof.py` | Replay, forward returns, groups, pass rule, report and run | `replay()`, `forward_returns()`, `group_stats()`, `verdict()`, `report_text()`, `run_proof()` | M01, P1–P3 modules | No |
| MD-MKT-004.006.M03 | SRD-MKT-004.006 | `us_swing/src/us_swing/market/store.py` | `proof_run` and `proof_stats` tables (added to the P1 store) | `ProofRunRow`, `ProofStatRow`, `MarketStore.write_proof()`, `latest_proof()` | `sqlite3` | No |

SRD coverage: .001 by M01; .002, .003, .004, .005, .007, .008, .009 by M02; .006 by M03.

Cross-tool: `desk proof` (SRD-DSK-001.022) is in `desk/cli.py` (MD-DSK-001.020.M06) with `PROOF_PATH` in `core/desk_steps.py` (MD-DSK-001.021.M07); the Score proof panel (SRD-GUI-034.014) is MD-GUI-034.014.M13.

## FO-MKT-005: AI Experts, Risk Manager and Trade Manager

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-MKT-005.001.M01 | SRD-MKT-005.001 | `us_swing/src/us_swing/market/regime_view.py` | Regime view skill: facts, answer schema and act | `RegimeViewSkill`, `RegimeView` | `core.desk_agents`, M02 | No |
| MD-MKT-005.003.M02 | SRD-MKT-005.003 | `us_swing/src/us_swing/market/store.py` | `regime_view` table (added to the P1 store) | `RegimeViewRow`, `MarketStore.write_regime_view()` | `sqlite3` | No |
| MD-MKT-005.005.M03 | SRD-MKT-005.005 | `us_swing/src/us_swing/market/employees/emp-001/` | Default expert-level employee files for the regime view |  — | — | No |

SRD coverage: .001, .002, .004 by M01; .003 by M02; .005 by M03.

### P5b — sector/flow view, setup review, risk check, lead brief

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-MKT-005.006.M04 | SRD-MKT-005.006 | `us_swing/src/us_swing/market/sector_view.py` | Sector/flow view skill: facts, answer schema and act | `SectorViewSkill`, `SectorView` | `core.desk_agents`, M02 | No |
| MD-MKT-005.009.M05 | SRD-MKT-005.009 | `us_swing/src/us_swing/market/setup_review.py` | Setup review skill: facts, grades and act | `SetupReviewSkill`, `SetupReview`, `SetupGrade` | `core.desk_agents`, M02 | No |
| MD-MKT-005.011.M06 | SRD-MKT-005.011 | `us_swing/src/us_swing/market/risk_limits.py` | Hard risk limits as constants and the code veto rules | `code_vetoes()`, `MIN_TRIGGER_USD`, `STOP_MIN_PCT`, `STOP_MAX_PCT`, `MAX_PER_SECTOR_SIDE` | — | No |
| MD-MKT-005.012.M07 | SRD-MKT-005.012 | `us_swing/src/us_swing/market/risk_check.py` | Risk check skill: code vetoes first, then AI vetoes | `RiskCheckSkill`, `RiskVetoes`, `RiskVeto` | `core.desk_agents`, M02, M06 | No |
| MD-MKT-005.014.M08 | SRD-MKT-005.014 | `us_swing/src/us_swing/market/lead_brief.py` | Lead brief skill: picks from passed ideas and the morning brief (feed kind `morning`; SRD-MKT-005.015–.016) | `LeadBriefSkill`, `LeadBrief`, `LeadPick` | `core.desk_agents`, M02, M06 | No |
| MD-MKT-005.017.M09 | SRD-MKT-005.017 | `us_swing/src/us_swing/market/employees/emp-002/` … `emp-005/` | Default employee files for the four new skills | — | — | No |

Changed: M01 (`needs`, `answer`); M02 (`sector_view`, `setup_review`, `risk_check`, `lead_picks` tables); `market/step.py` (MD-MKT-001.*) posts `regime_change` through `core/desk_events.py`.

SRD coverage: .006–.007 by M04, .008 by M04 and M02; .009–.010 by M05 (.010 also M02); .011 by M06; .012 by M07, .013 by M07 and M02; .014–.015 by M08, .016 by M08 and M02; .017 by M09; .018 by MD-DSK-001.021.M07 (`core/desk_steps.py`).

## FO-MKT-006: News, Economic Calendar and Event Risk

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-MKT-006.001.M01 | SRD-MKT-006.001 | `us_swing/src/us_swing/market/news.py` | Fetch and read stock and market RSS headlines | `fetch_symbol()`, `fetch_market()`, `parse_feed()`, `Headline`, `NEWS_FEEDS` | `httpx`, `feedparser` | No |
| MD-MKT-006.001.M02 | SRD-MKT-006.001 | `us_swing/src/us_swing/market/news_step.py` | Desk step "News": fetch, keep once, delete old, log | `NewsStep` | M01, M05 | No |
| MD-MKT-006.004.M03 | SRD-MKT-006.004 | `us_swing/src/us_swing/core/econ_calendar.py` | Yearly economic calendar data and trading-day helper (shared with the Floor) | `EconEvent`, `events_between()`, `next_trading_day()`, `COVERED_YEARS` | `data.market_calendar` | No |
| MD-MKT-006.005.M04 | SRD-MKT-006.005 | `us_swing/src/us_swing/market/news_review.py` | News review skill: facts, answer, code rows, points and final score | `NewsReviewSkill`, `NewsReview`, `NewsTag`, `news_points()` | `core.desk_agents`, M03, M05 | No |
| MD-MKT-006.008.M05 | SRD-MKT-006.008 | `us_swing/src/us_swing/market/store.py` | `news_items` and `news_tags` tables (added to the P1 store) | `NewsItemRow`, `NewsTagRow`, `MarketStore.add_news()`, `MarketStore.delete_news_before()` | `sqlite3` | No |
| MD-MKT-006.011.M06 | SRD-MKT-006.011 | `us_swing/src/us_swing/market/employees/emp-006/` | Default expert-level employee files for the news review | — | — | No |

Changed: MD-MKT-005.012.M07 (`risk_check.py`: needs and facts add the news review) and MD-MKT-005.014.M08 (`lead_brief.py`: needs, facts and final column), for SRD-MKT-006.010, SRD-MKT-005.012 and SRD-MKT-005.014; `core/desk_steps.py` (MD-DSK-001.021.M07) gets the News step and `news_review` skill paths.

SRD coverage: .001 by M01 and M02; .002, .003, .012 by M02 (with M01, M05); .004 by M03; .005–.007, .009 by M04; .008 by M04 and M05; .010 by MD-MKT-005.012.M07 and MD-MKT-005.014.M08; .011 by M06.

## FO-MKT-007: AI Report Pages

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-MKT-007.003.M01 | SRD-MKT-007.003 | `us_swing/src/us_swing/core/report_html.py` | Allow-list HTML cleaner and sealed page shell (shared with the GUI) | `clean_page()`, `CleanPage`, `sealed_document()`, `MAX_PAGE_BYTES` | `html.parser` | No |
| MD-MKT-007.001.M02 | SRD-MKT-007.001 | `us_swing/src/us_swing/market/report_page.py` | Report page skill: facts, answer, clean, store, feed brief, log | `ReportPageSkill`, `ReportPage` | `core.desk_agents`, M01, M03 | No |
| MD-MKT-007.004.M03 | SRD-MKT-007.004 | `us_swing/src/us_swing/market/store.py` | Append-only `canvas_pages` table (added to the P1 store) | `MarketStore.add_page()` | `sqlite3` | No |
| MD-MKT-007.007.M04 | SRD-MKT-007.007 | `us_swing/src/us_swing/market/employees/emp-007/` | Default expert-level employee files for report pages | — | — | No |

SRD coverage: .001–.002 and .005–.006, .008 by M02; .003 by M01; .004 by M03; .007 by M04 and MD-DSK-001.021.M07 (`core/desk_steps.py` gets the `report_page` skill path).

## FO-MKT-008: Link to Execution

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-MKT-008.001.M01 | SRD-MKT-008.001 | `us_swing/src/us_swing/core/desk_trades.py` | Trade picks, target, state and expiry, trade approval rows, approved picks (shared with the GUI and app) | `TradePick`, `DeskTradeSink`, `pick_target()`, `pick_expiry()`, `pick_state()`, `trade_picks()`, `record_trade_decision()`, `record_trade_outcome()`, `approved_picks()` | `sqlite3`, `core.desk_hiring`, `core.econ_calendar` | No |
| MD-MKT-008.002.M02 | SRD-MKT-008.002 | `us_swing/src/us_swing/core/desk_ai_settings.py` | `trade_target_r` setting (added to MD-DSK-004.005.M13) | `DeskAiSettings.trade_target_r` | — | No |

SRD coverage: .001 and .003–.006 by M01; .002 by M01 and M02.

## FO-MKT-009: Pick Results

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-MKT-009.001.M01 | SRD-MKT-009.001 | `us_swing/src/us_swing/market/pick_results.py` | Paper rule and the Pick results desk step | `paper_result()`, `PaperResult`, `PickResultsStep` | `market.candles`, `core.desk_trades`, `core.desk_ai_settings`, M02 | No |
| MD-MKT-009.004.M02 | SRD-MKT-009.004 | `us_swing/src/us_swing/market/store.py` | `pick_results` table (added to the P1 store) | `PickResultRow`, `MarketStore.replace_pick_results()` | `sqlite3` | No |
| MD-MKT-009.005.M03 | SRD-MKT-009.005 | `us_swing/src/us_swing/core/desk_results.py` | Real trade rows and the shared results view | `record_pick_trade()`, `results_view()`, `results_lines()`, `ResultsView`, `Group` | `sqlite3`, `core.desk_trades`, `core.desk_hiring` | No |
| MD-MKT-009.005.M04 | SRD-MKT-009.005 | `us_swing/src/us_swing/gui/app_service.py` | AI Desk cycle closed → real trade row | `_record_desk_trade()` | M03 | No |
| MD-MKT-009.007.M05 | SRD-MKT-009.007 | `us_swing/src/us_swing/desk/weekly_report.py` | Pick results section (added to MD-DSK-006.009.M20) | `build_report()` | M03 | No |
| MD-MKT-009.001.M06 | SRD-MKT-009.001 | `us_swing/src/us_swing/core/desk_steps.py` | Step path after News (so after Ideas) | `STEP_PATHS` | — | No |

SRD coverage: .001–.003 and .008 by M01 and M06; .004 by M02; .005 by M03 and M04; .006 by M03; .007 by M05.

## FO-MKT-010: Lead Chat

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-MKT-010.001.M01 | SRD-MKT-010.001 | `us_swing/src/us_swing/core/desk_chat.py` | Append-only chat table, questions, replies and notes (shared by the GUI and the desk) | `ChatTurn`, `ask_question()`, `open_question()`, `add_reply()`, `chat_turns()`, `question_note()` | `sqlite3`, `core.desk_events` | No |
| MD-MKT-010.002.M02 | SRD-MKT-010.002 | `us_swing/src/us_swing/core/desk_events.py` | `chat_question` event kind and per-question key (added to MD-DSK-003.004.M15) | `EVENT_RULES`, `post_event()` | — | No |
| MD-MKT-010.003.M03 | SRD-MKT-010.003 | `us_swing/src/us_swing/market/lead_chat.py` | Lead chat skill: facts, answer, reply row, log | `LeadChatSkill`, `LeadChatAnswer`, `FAILED_TEXT` | `core.desk_agents`, M01, `core.desk_results`, `market.lead_brief` | No |
| MD-MKT-010.007.M04 | SRD-MKT-010.007 | `us_swing/src/us_swing/market/employees/emp-008/`, `core/desk_steps.py` | Default chat employee files and the skill path | `SKILL_PATHS` | — | No |

SRD coverage: .001 by M01; .002 by M02; .003–.006 and .008 by M03; .007 by M04.

## FO-MKT-011: Ask the Desk for New Data

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-MKT-011.001.M01 | SRD-MKT-011.001 | `us_swing/src/us_swing/core/desk_data_asks.py` | Append-only data requests and asked products, and their decisions (shared by the GUI and the desk) | `DataRequest`, `AskedProduct`, `ask_data()`, `open_request()`, `add_asked()`, `waiting_products()`, `failed_products()`, `approved_products()`, `decide_product()` | `sqlite3`, `core.desk_events`, M03 | No |
| MD-MKT-011.002.M02 | SRD-MKT-011.002 | `us_swing/src/us_swing/core/desk_events.py` | `data_request` event kind and per-request key (added to MD-DSK-003.004.M15) | `EVENT_RULES`, `post_event()` | — | No |
| MD-MKT-011.004.M03 | SRD-MKT-011.004 | `us_swing/src/us_swing/core/desk_recipes.py` | Fixed menu, recipe model, check, read-only run and recipe in words | `MENU`, `DataRecipe`, `RecipeFilter`, `check_recipe()`, `run_recipe()`, `recipe_words()` | `pydantic`, `sqlite3` | No |
| MD-MKT-011.003.M04 | SRD-MKT-011.003 | `us_swing/src/us_swing/market/data_recipe.py` | Data recipe skill: facts, answer, asked product row, log | `DataRecipeSkill`, `DataRecipeAnswer` | `core.desk_agents`, M01, M03 | No |
| MD-MKT-011.007.M05 | SRD-MKT-011.007 | `us_swing/src/us_swing/core/desk_floor.py` | Approved asked products in the Floor catalog and their rows (added to MD-GUI-034.011.M10) | `DeskFloorData.products()`, `DeskFloorData.rows()` | M01, M03 | No |
| MD-MKT-011.008.M06 | SRD-MKT-011.008 | `us_swing/src/us_swing/market/employees/emp-009/`, `core/desk_steps.py` | Default data employee files and the skill path | `SKILL_PATHS` | — | No |

## FO-MKT-012: Learning from Pick Results

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-MKT-012.002.M01 | SRD-MKT-012.002 | `us_swing/src/us_swing/market/lesson_reflect.py` | Stats of closed picks by tag, reflect skill, answer form, candidates kept, log | `LessonReflectSkill`, `LessonReflect`, `stats_text()` | `core.desk_lessons` | No |
| MD-MKT-012.004.M02 | SRD-MKT-012.004 | `us_swing/src/us_swing/market/employees/emp-010/`, `core/desk_steps.py` | Default reflect employee and the `lesson_reflect` skill path | — | M01 | No |
| MD-MKT-012.005.M03 | SRD-MKT-012.005 | `us_swing/src/us_swing/market/setup_review.py`, `news_review.py`, `risk_check.py`, `lead_brief.py` | Lessons block at the end of the facts of the four pick makers | — | `core.desk_lessons` | No |

Changed: MD-MKT-009.001.M01 (`pick_results.py`: calls `review_lessons()` after writing results — SRD-DSK-009.002, .007).

SRD coverage: 012.001–.003 and .006 by M01; .004 by M02; .005 by M03.

## FO-MKT-013: Intraday Watchers and Check-in Notes

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-MKT-013.001.M01 | SRD-MKT-013.001 | `us_swing/src/us_swing/market/watch.py` | Read today's 3-minute bars; trigger, stop and target, volume, gap, SPY and headline watchers; flags and alerts | `run_watch()`, `today_bars()` | `core.desk_watch`, `core.desk_alerts`, `market.candles`, `market.news` | No |
| MD-MKT-013.008.M02 | SRD-MKT-013.008 | `us_swing/src/us_swing/market/watch_flag.py` | Flag skill: facts for the oldest unanswered flag, verdict form, verdict row, feed item, broken alert, log | `WatchFlagSkill`, `WatchVerdict` | `core.desk_watch`, M01 | No |
| MD-MKT-013.010.M03 | SRD-MKT-013.010 | `us_swing/src/us_swing/market/checkin_note.py` | Check-in skill: plan, trades, SPY and flags since the last check-in; note form; feed item | `CheckinNoteSkill`, `CheckinNote` | `core.desk_watch`, M01 | No |
| MD-MKT-013.011.M04 | SRD-MKT-013.011 | `us_swing/src/us_swing/market/employees/emp-011/`, `emp-012/`, `core/desk_steps.py` | Default watcher and market lead employees and their skill paths | — | M02, M03 | No |

SRD coverage: 013.001–.007 by M01; .008, .009, .012 by M02; .010 by M03; .011 by M04.

## FO-MKT-014: Lead Research Tickets

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-MKT-014.001.M01 | SRD-MKT-014.001 | `us_swing/src/us_swing/market/lead_brief.py` | `tickets` field in the lead brief answer, research block in the facts, tickets handed to the queue | `LeadBrief.tickets` | `core.desk_research` | No |
| MD-MKT-014.001.M02 | SRD-MKT-014.001 | `us_swing/src/us_swing/market/checkin_note.py` | `tickets` field in the check-in answer, research block in the facts, tickets handed to the queue | `CheckinNote.tickets` | `core.desk_research` | No |

SRD coverage: 014.001, .004, .005 by M01 and M02; .002 and .003 are checked in `core.desk_research` (MD-DSK-010.001.M25) and tested through M01.

## FO-MKT-015: Setup Tuning Research

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-MKT-015.001.M01 | SRD-MKT-015.001 | `us_swing/src/us_swing/market/setup_tuning.py` | Research skill: pick step, run steps, verdict, candidate lesson, logs | `SetupTuningSkill`, `TuningPlan`, `TuningVerdict` | `core.desk_research`, `core.desk_lessons`, M02–M04 | No |
| MD-MKT-015.002.M02 | SRD-MKT-015.002 | `us_swing/src/us_swing/market/setup_knobs.py` | Named setup limits with default and range; change checks | `Knob`, `KNOBS`, `knob_value`, `check_changes` | — | No |
| MD-MKT-015.004.M03 | SRD-MKT-015.004 | `us_swing/src/us_swing/market/tuning_replay.py` | 5-year replay of one desk setup, result rows, gain rule | `Row`, `replay_setup`, `table_text`, `gain` | `market.setups`, `market.proof_data`, `market.pick_results` | No |
| MD-MKT-015.005.M04 | SRD-MKT-015.005 | `us_swing/src/us_swing/market/tuning_strategy.py` | Strategy knobs, renamed copies, backtest run, R per trade | `strategy_knobs`, `apply_changes`, `stop_problem`, `pick_stocks`, `run_strategy` | `backtest` (loaded in the run), `core.backtest_bridge` | No |

SRD coverage: .001, .003, .008–.012 by M01; .002 by M02 (read by `market/setups.py`, MD-MKT-003.003.M03); .004, .006, .007 by M03; .005 by M04 (rows by M03 `Row`). Cross-tool: M04 runs the BKT engine through its public service; no BKT file changes.

## FO-MKT-016: Pick Post-Mortem Research

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-MKT-016.001.M01 | SRD-MKT-016.001 | `us_swing/src/us_swing/market/post_mortem.py` | Research skill: pick, gather and study steps, lessons, follow-ups, logs | `PostMortemSkill`, `PickChoice`, `PostMortem` | `core.desk_research`, `core.desk_lessons`, `market.lesson_reflect`, M02 | No |
| MD-MKT-016.004.M02 | SRD-MKT-016.004 | `us_swing/src/us_swing/market/post_mortem_facts.py` | Stored facts per pick, daily bars from Backtest Data then candles.db, price path | `pick_records`, `pick_bars`, `path_line` | `market.proof_data`, `market.candles` | No |

SRD coverage: .001–.003, .006–.011 by M01; .004 and .005 by M02. Cross-tool: M01 calls DSK `raise_follow_ups()` (MD-DSK-010.001.M25, SRD-DSK-010.015).

## FO-MKT-017: Sentiment Research

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-MKT-017.001.M01 | SRD-MKT-017.001 | `us_swing/src/us_swing/market/sentiment.py` | Research skill: pick, gather and judge steps, result, gain, logs | `SentimentSkill`, `StockChoice`, `SentimentJudge` | `core.desk_research`, `core.desk_watch`, M02, M03 | No |
| MD-MKT-017.004.M02 | SRD-MKT-017.004 | `us_swing/src/us_swing/market/sentiment_news.py` | Stored headlines first, fetch only gaps within the budget, record lines | `Gathered`, `gather_news` | `market.news`, `market.store` | No |
| MD-MKT-017.006.M03 | SRD-MKT-017.006 | `us_swing/src/us_swing/market/sentiment_cards.py` | `sentiment_cards` table, saving cards, the lead's cards block | `save_cards`, `cards_block` | `core.desk_contract` | No |

SRD coverage: .001–.003, .005, .008–.010 by M01; .004 by M02; .006 and .007 by M03. Changed: `market/lead_brief.py` (MD-MKT-005.014.M08) adds `cards_block()` to its facts — SRD-MKT-017.007.

## FO-MKT-018: Book to Strategy Research

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-MKT-018.001.M01 | SRD-MKT-018.001 | `us_swing/src/us_swing/market/book_strategy.py` | Research skill: read and card steps, quote check, result, gain, logs | `BookStrategySkill`, `StrategyCard` | `core.desk_research`, M02, M03 | No |
| MD-MKT-018.002.M02 | SRD-MKT-018.002 | `us_swing/src/us_swing/market/book_text.py` | Topic form, books folder and Gutenberg source, readers, chapter split | `BookRef`, `parse_topic`, `load_text`, `chapter` | `market.news`, `pypdf` | No |
| MD-MKT-018.006.M03 | SRD-MKT-018.006 | `us_swing/src/us_swing/market/book_cards.py` | `strategy_cards` and `books_read` tables, read check, lead books block | `already_read`, `save_card`, `books_block` | `core.desk_contract` | No |

SRD coverage: .001, .007, .009, .011, .012 by M01; .002–.005 by M02; .006, .008, .010 by M03 (quote check in M01). Changed: `market/lead_brief.py` (MD-MKT-005.014.M08) adds `books_block()` — SRD-MKT-018.010.

## FO-MKT-019: Strategy Test Research

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-MKT-019.001.M01 | SRD-MKT-019.001 | `us_swing/src/us_swing/market/strategy_test.py` | Research skill: recipe, check, replay and verdict steps, save, lesson, logs | `StrategyTestSkill`, `CardVerdict` | `core.desk_research`, `core.desk_lessons`, M02, M03, M04 | No |
| MD-MKT-019.003.M02 | SRD-MKT-019.003 | `us_swing/src/us_swing/market/card_recipe.py` | Recipe answer model, daily block menu and recipe check (SRD-MKT-019.004) | `Recipe`, `block_menu`, `check_recipe` | `core.indicator_rules`, `core.price_patterns` | No |
| MD-MKT-019.005.M03 | SRD-MKT-019.005 | `us_swing/src/us_swing/market/card_replay.py` | Replay on Backtest Data, baseline and score with the pass rule (SRD-MKT-019.006–.007) | `load_data`, `replay`, `baseline`, `score`, `Score`, `score_text` | `market.proof_data`, `market.pick_results`, `core.indicator_rules`, `core.price_patterns` | No |
| MD-MKT-019.009.M04 | SRD-MKT-019.009 | `us_swing/src/us_swing/core/desk_cards.py` | Cards and `card_tests` store, open tests, lead untested block (SRD-MKT-019.011); read by the GUI | `CardRow`, `CardTest`, `cards`, `card`, `save_test`, `latest_tests`, `open_test_cards`, `untested_block` | `core.desk_contract` | No |
| MD-MKT-019.012.M05 | SRD-MKT-019.012 | `us_swing/src/us_swing/market/employees/emp-017/employee.md`, `core/desk_steps.py`, `USSwing.spec` | Default strategy test employee, skill path and app build entry | `SKILL_PATHS["strategy_test"]` | `core.desk_hiring` | No |

SRD coverage: .001, .002, .008, .009 (save), .010, .013, .014 by M01; .003–.004 by M02; .005–.007 by M03; .009, .011 by M04; .012 by M05. Changed: `market/lead_brief.py` (untested cards block, SRD-MKT-019.011).

## FO-MKT-005 / FO-MKT-006 (AI Desk v3 M1): Asks, Send-Back Fixes and News Replies

No new module. Changed: MD-MKT-005.009.M05 (`market/setup_review.py`: `talks`, held ideas with at most 3 asked, merge on an inbox wake, fixed levels in `listed_frame` — SRD-MKT-005.019, .021, .023), MD-MKT-005.012.M07 (`market/risk_check.py`: stop send-back, code-only fix check, round 2 — .020, .022), MD-MKT-006.005.M04 (`market/news_review.py`: inbox reply only — 006.013), MD-MKT-001.007.M04 (`market/store.py`: `idea_fixes` table, `FIXED` join, `put_rows()` — 005.022, .023), MD-MKT-013.001.M01 (`market/watch.py`) and MD-MKT-013.008.M02 (`market/watch_flag.py`): fixed levels — 005.023.

Cross-tool: the skills use DSK `core/desk_msg.py` (`Draft`, `InboxReply`) and `core/desk_agents.talker()`.
