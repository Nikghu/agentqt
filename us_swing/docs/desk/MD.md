# Module Decomposition — Desk Harness (DSK)

**Document ID:** MD-DSK
**Version:** 0.4.0
**Status:** Draft
**Last Updated:** 2026-11-11
**Project:** US Swing Trading System

> v0.19.0: MD-DSK-009.010.M30 and MD-DSK-009.021.M31 added; M23, M27, M11, M10, M13, M04 changed (AI Desk v3 M3, 2026-11-13).
> v0.18.0: No new module; M29, M15, M16, M10, M13, M21, M22 changed (AI Desk v3 M2, 2026-11-13).
> v0.17.0: MD-DSK-011.015.M29 added; M27, M28, M15, M16, M10, M11, M12, M14, M08, M13 changed (AI Desk v3 M1, 2026-11-13).
> v0.16.0: MD-DSK-011.001.M27 and MD-DSK-012.001.M28 added; M04 changed (AI Desk v3 M0, 2026-11-13).
> v0.15.0: MD-DSK-010.001.M25 gains `raise_owner_test` (SRD-DSK-010.016, 2026-11-12).
> v0.14.0: M25 changed — `raise_follow_ups()` for SRD-DSK-010.015 (step F).
> v0.13.0: MD-DSK-010.001.M25 and MD-DSK-010.008.M26 added — token split and research queue (step E); M04, M06, M10, M11, M12, M14, M15, M21, M22 changed.
> v0.12.0: MD-DSK-003.021.M24 added — watch flags and open trades (step D); M03, M04, M06, M07, M15, M21 changed.
> v0.11.0: MD-DSK-009.001.M23 added — lessons (step C); M04 applies lesson edits.
> v0.10.0: Autonomous desk step B (2026-11-11): M15 `steps` table, `parent`/`due` columns, `post_step_done()`; M16 baton without LangGraph; M10 wake returns ok/slept/failed, retry flag and partial-plan line; M21 `partial` alert kind.
> v0.9.0: Autonomous desk step A (2026-11-11): M03 morning due, M04 parent watch, M05 old-task clean-up only, M06 `--parent`, M21 `candles` alert.
> v0.8.0: MD-DSK-008.001.M22 added — employee file, versions, draft test.
> v0.7.0: MD-DSK M18–M20 added — hiring, shadow, weekly report (P6).
> v0.6.0: MD-DSK M15–M17 added — events, router with LangGraph, replay (P5b).
> v0.5.0: MD-DSK-002–005 M08–M14 added — lean harness (P5a).
> v0.4.0: MD-DSK-001.020.M06 and .021.M07 also cover SRD-DSK-001.022 (`desk proof`).
> v0.3.0: MD-DSK-001.021.M07 added.
> v0.2.0: MD-DSK-001.*.M01–M06 added — desk process shell (P0a).
> v0.1.0: Empty.

---

## FO-DSK-001: Desk Process Shell

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-DSK-001.004.M01 | SRD-DSK-001.004 | `us_swing/src/us_swing/core/desk_contract.py` | Shared desk types, read-only status reader and command sender used by the app | `DeskState`, `CommandKind`, `DeskStatus`, `DeskStep`, `desk_home()`, `read_status()`, `send_command()` | `sqlite3` | No |
| MD-DSK-001.001.M02 | SRD-DSK-001.001 | `us_swing/src/us_swing/desk/store.py` | Opens `desk.db` (WAL), creates tables, writes state, heartbeat, commands and runs | `DeskStore` | `sqlite3`, M01 | No |
| MD-DSK-001.015.M03 | SRD-DSK-001.015 | `us_swing/src/us_swing/desk/clock.py` | Pure time rules: morning run due, trading day, market clock events | `morning_due()`, `is_trading_day()`, `market_events_due()` | `zoneinfo` | No |
| MD-DSK-001.010.M04 | SRD-DSK-001.010 | `us_swing/src/us_swing/desk/process.py` | Single-instance main loop, command handling, runs, parent watch, stop and resume | `DeskProcess`, `pid_alive()` | M01–M03 | No |
| MD-DSK-001.018.M05 | SRD-DSK-001.018 | `us_swing/src/us_swing/desk/task.py` | Delete the old desk Windows tasks; launch a detached desk | `remove_old_tasks()`, `launch()` | `subprocess` | No |
| MD-DSK-001.020.M06 | SRD-DSK-001.020 | `us_swing/src/us_swing/desk/cli.py` | `desk` sub-commands for `python -m us_swing` | `main(argv)` | M01, M04, M05 | No |

| MD-DSK-001.021.M07 | SRD-DSK-001.021 | `us_swing/src/us_swing/core/desk_steps.py` | Step list and loader; desk CLI passes the steps | `STEP_PATHS`, `load_steps()` | `importlib` | No |

**SRD coverage per module** (one Parent SRD per row above; each module also covers):

| Module | Covers SRDs |
|---|---|
| MD-DSK-001.004.M01 | SRD-DSK-001.004, .005, .006, .007 |
| MD-DSK-001.001.M02 | SRD-DSK-001.001, .002, .003, .016 (run rows), .015 (`runs_since`) |
| MD-DSK-001.015.M03 | SRD-DSK-001.015, SRD-DSK-003.013 (run kinds counted) |
| MD-DSK-001.010.M04 | SRD-DSK-001.008, .009, .010, .011, .012, .013, .014, .016, .017, .019 (parent watch), SRD-DSK-003.013 |
| MD-DSK-001.018.M05 | SRD-DSK-001.018 |
| MD-DSK-001.020.M06 | SRD-DSK-001.020, .022 (`desk proof`), .019 (`--parent`) |
| MD-DSK-001.004.M01 | also SRD-DSK-001.020 (`launch_desk(parent=)`) |

## FO-DSK-002–005: Lean Harness (P5a)

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-DSK-002.001.M08 | SRD-DSK-002.001 | `us_swing/src/us_swing/core/desk_agents.py` | Shared skill types and generic levels used by desk and tools | `Skill`, `AgentContext`, `Facts`, `FeedItem`, `LEVELS` | `pydantic` | No |
| MD-DSK-002.002.M09 | SRD-DSK-002.002 | `us_swing/src/us_swing/desk/registry.py` | Employee folders in the desk folder: seed defaults, load and check files, skills by key; `roster` table | `JobSpec`, `Hire`, `seed_employees()`, `default_folders()`, `load_employee()`, `load_employees()`, `record_employees()` | M08, `yaml`, `pydantic` | No |
| MD-DSK-003.001.M10 | SRD-DSK-003.001 | `us_swing/src/us_swing/desk/employees_step.py` | Desk step "AI employees" with the wake rule | `EmployeesStep` | M09, M11, M14 | No |
| MD-DSK-004.001.M11 | SRD-DSK-004.001 | `us_swing/src/us_swing/desk/gateway.py` | Model calls, schema check, retry and backup | `Gateway`, `call_model()` | M12, M14, `httpx` | No |
| MD-DSK-004.003.M12 | SRD-DSK-004.003 | `us_swing/src/us_swing/desk/budget.py` | Budget and call caps from `activity` | `Budget` | M14 | No |
| MD-DSK-004.005.M13 | SRD-DSK-004.005 | `us_swing/src/us_swing/core/desk_ai_settings.py` | Desk AI settings file and OpenRouter key (shared with the GUI) | `DeskAiSettings`, `load_settings()`, `save_settings()`, `load_key()`, `save_key()` | `keyring` | No |
| MD-DSK-005.001.M14 | SRD-DSK-005.001 | `us_swing/src/us_swing/desk/recorder.py` | Append-only `activity` and `briefs` | `Recorder`, `Attempt` | `sqlite3` | No |

SRD coverage: 002.001 by M08 and M09 (skills by key); 002.002–.004, .006, .007 by M09; 002.005 by M08 and M10; 003.001–.003 by M10; 004.001, .002 by M11; 004.003, .004 by M12; 004.005 by M13; 005.001–.004 by M14 (005.004 also M10).

Cross-tool: `core/desk_steps.py` (MD-DSK-001.021.M07) gets `SKILL_PATHS`, `DEFAULT_EMPLOYEE_PACKAGES` and the "AI employees" step path.

## FO-DSK-002, -003, -005: Events, Market Clock, LangGraph Order and Replay (P5b)

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-DSK-003.004.M15 | SRD-DSK-003.004 | `us_swing/src/us_swing/core/desk_events.py` | `events` and `steps` tables, event kinds and rules, posting from any tool, `step_done` posting for the router | `EVENT_KINDS`, `EVENT_RULES`, `Event`, `post_event()`, `post_step_done()` | `sqlite3` | No |
| MD-DSK-003.006.M16 | SRD-DSK-003.006 | `us_swing/src/us_swing/desk/router.py` | Expire, order and handle events; move each chain on by `step_done` events in needs order, with retries, skips and the lead's partial run | `Router`, `run_order()` | M09, M14, M15, M21, `graphlib` | No |
| MD-DSK-005.005.M17 | SRD-DSK-005.005 | `us_swing/src/us_swing/desk/replay.py` | Re-send a recorded run's prompts and compare the answers | `replay()`, `ReplayLine` | M09, M11, M14 | No |

Changed P0a/P5a modules: M08 (`needs`, `answer`, feed kind `evening`), M09 (trigger list), M10 (posts `after_run`, then calls the router), M03 (`market_events_due()`), M04 (posts clock events, `event` runs), M11 (`Gateway.resend()`), M14 (`replay` column, `last_wake()`), M06 (`desk replay`).

SRD coverage: 002.008 by M08 and M16; 002.009 by M09; 003.004, .005 by M15; 003.006, .007, .009–.011 by M16 (.009 also M14); 003.008 by M03 and M04; 003.012 by M16 with `pyproject.toml` and `USSwing.spec`; 005.005–.007 by M17 (.005 also M11 and M06; .006 also M14). Step B (2026-11-11): 003.010, .011, .015–.019 by M16; .014 by M15 and M16; .012 by M16 with `pyproject.toml` and `USSwing.spec` (LangGraph removed); 007.008 by M21 and M16.

Cross-tool: `market/step.py` posts `regime_change` through M15 (see MKT DD-MKT-005.006.D01).

## FO-DSK-006: Hiring Pipeline and Process Analytics

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-DSK-006.001.M18 | SRD-DSK-006.001 | `us_swing/src/us_swing/core/desk_hiring.py` | Start hires, seat check, list hires, shadow report, agreement, decisions and `approvals` | `start_hire()`, `list_hires()`, `shadow_report()`, `agreement()`, `decide()`, `seat_counts()` | `core.desk_steps`, `core.desk_ai_settings`, `yaml` | No |
| MD-DSK-006.004.M19 | SRD-DSK-006.004 | `us_swing/src/us_swing/desk/shadow.py` | Ask and record only for a shadow employee, 14 data days | `run_shadow()`, `SHADOW_DAYS` | M11, M14 | No |
| MD-DSK-006.009.M20 | SRD-DSK-006.009 | `us_swing/src/us_swing/desk/weekly_report.py` | Desk step "Weekly report": code-only weekly process and cost report | `WeeklyReportStep`, `build_report()` | `sqlite3` | No |

Changed: MD-DSK-002.002.M09 (`registry.py`: `status`, `hired_on`, retired not loaded — SRD-DSK-006.008), MD-DSK-004.005.M13 (`desk_ai_settings.py`: seat caps — SRD-DSK-006.003), the recorder and gateway (`activity.shadow`), `employees_step.py` (shadow path) and `core/desk_steps.py` (MD-DSK-001.021.M07: "Weekly report" step path).

SRD coverage: .001, .002, .005–.007 by M18 (.005 also M19); .003 by M13 and M18; .004 by M19; .008 by M09; .009 by M20; .010 by M18, M19 and M20.

## FO-DSK-007: AI Problem Alerts

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-DSK-007.001.M21 | SRD-DSK-007.001 | `us_swing/src/us_swing/core/desk_alerts.py` | Spot user problems, store one alert a day, send to Telegram, list open alerts | `classify()`, `raise_alert()`, `open_alerts()`, `run_outcome()`, `send_telegram()` | `core.desk_contract`, `httpx`, `keyring` | No |

Changed: MD-DSK-004.001.M11 (`gateway.py`: `_report`, per-run skip, `send=` — SRD-DSK-007.001, .004) and MD-DSK-003.001.M10 (`employees_step.py`: `_check_run`, `send=` — SRD-DSK-007.005).

SRD coverage: .001–.003 and .006 by M21; .001 and .004 by M11; .005 by M10 and M21; .007 by M21 (`candles` kind, closed by a later ok run) and MD-MKT-001.013.M06 (raises it).

## FO-DSK-008: Employee File and Versions

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-DSK-008.001.M22 | SRD-DSK-008.001 | `us_swing/src/us_swing/core/desk_employee.py` | Employee file rules, read and write, migration, versions, restore, draft test, known models | `JobSpec`, `EmployeeFile`, `parse()`, `render()`, `read_employee()`, `migrate_all()`, `save_employee()`, `versions()`, `restore()`, `try_draft()`, `known_models()` | `core.desk_contract`, `core.desk_hiring`, `core.desk_ai_settings`, `yaml`, `pydantic` | No |

Changed: MD-DSK-002.002.M09 (`registry.py`: rules from core, reads `employee.md`, migrates on seed — SRD-DSK-008.001, .003, .004), MD-DSK-006.001.M18 (`core/desk_hiring.py`: writes `employee.md` — .007), MD-DSK-005.005.M17 (`replay.py`, `cli.py`: `--draft` — .008), shipped `market/employees/*/employee.md` (.004). Cross-tool note: `core/desk_team.py` (GUI module MD-GUI-035.002.M02) reads through `read_employee`.

SRD coverage: .001–.003, .005, .006, .009 by M22; .004 by M09; .007 by M18; .008 by M17 and M22.

## FO-DSK-009: Desk Memory — Lessons

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-DSK-009.001.M23 | SRD-DSK-009.001 | `us_swing/src/us_swing/core/desk_lessons.py` | Lesson tables, closed pick cases and tags, check, add, daily review, lessons block, edits, rows for the GUI | `Lesson`, `Case`, `cases()`, `check()`, `add_candidate()`, `review_lessons()`, `lessons_block()`, `add_edit()`, `apply_edits()`, `lesson_rows()`, `proof_rows()` | `sqlite3`, `core.desk_contract` | No |

Changed: MD-DSK-001.010.M04 (`desk/process.py`: `tick()` calls `apply_edits()` — SRD-DSK-009.008).

SRD coverage: 009.001–.007 and .009 by M23; .008 by M23 and M04.

Cross-tool: MKT `market/pick_results.py` calls `review_lessons()`; MKT pick-making skills call `lessons_block()`; GUI `gui/ai_desk_memory.py` calls `lesson_rows()`, `proof_rows()` and `add_edit()`.

## FO-DSK-003 (step D): Check-ins and Watchers

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-DSK-003.021.M24 | SRD-DSK-003.021 | `us_swing/src/us_swing/core/desk_watch.py` | Watch flags with the hourly key, flag events and code feed notes, open trades, desk live symbols | `Flag`, `OpenTrade`, `add_flag()`, `flagged_today()`, `next_flag()`, `answer_flag()`, `flags_since()`, `add_note()`, `write_open_trades()`, `open_trades()`, `desk_live_symbols()` | M15, `sqlite3` | No |

Changed: M03 (`desk/clock.py`: `CHECKINS`, `checkins_due()`, `in_market_hours()`), M04 (`desk/process.py`: posts check-ins, watcher pass every 5 minutes), M06 (`desk/cli.py`: passes `watch=load_watch()`), M07 (`core/desk_steps.py`: `WATCH_PATH`, `load_watch()`, two skill paths), M15 (`core/desk_events.py`: `market_checkin`, `watch_flag`), M21 (`core/desk_alerts.py`: `trade_stop`, `trade_target`, `plan_broken`).

SRD coverage: 003.020 by M03 and M04; .021, .022, .024 by M24 and M15; .023 by M04, M06 and M07; .025 by MKT M01; 007.009 by M21.

## FO-DSK-010 (step E): Token Split and Research Queue

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-DSK-010.001.M25 | SRD-DSK-010.001 | `us_swing/src/us_swing/core/desk_research.py` | Ticket tables, raise rules, auto approval and alert, research block, edits, expiry, pause, research skill contract, rows for the GUI; owner-raised strategy test ticket (SRD-DSK-010.016) | `Ticket`, `TicketAsk`, `StepResult`, `ResearchSkill`, `KINDS`, `raise_tickets()`, `with_research()`, `add_ticket_edit()`, `apply_ticket_edits()`, `expire_waiting()`, `pause_running()`, `ticket_rows()`, `pending_ticket_edits()`, `lead_research()`, `raise_owner_test` | `sqlite3`, M15, M21, M22 | No |
| MD-DSK-010.008.M26 | SRD-DSK-010.008 | `us_swing/src/us_swing/desk/research.py` | Quiet test, ticket pick, doer by kind, cap checks, one step, stall and done checks, pause, end and `research_done` event | `ResearchRunner` (`has_work()`, `__call__()`), `quiet()` | M25, M11, M14, M16 | No |

Changed: M12 (`desk/budget.py`: `Part`, `SHARES`, `part_cap()`, part and ticket checks — SRD-DSK-004.007, .009, .010), M14 (`desk/recorder.py`: `part`, `payer`, `ticket` columns, `part_tokens()`, `ticket_tokens()`, `ticket_seconds()` — .008), M11 (`desk/gateway.py`: takes `part`, records it — .008, .009), M10 (`desk/employees_step.py`: market or plan part by event kind — .008), M22 (`core/desk_employee.py`: `tokens_per_day` — .006), M04 (`desk/process.py`: applies ticket edits and expiry each tick, pauses on start, runs research when quiet — 010.004, .005, .008, .012), M06 (`desk/cli.py`: passes the runner), M15 (`core/desk_events.py`: `research_done` — 010.013), M21 (`core/desk_alerts.py`: `ticket_waiting` — 007.010).

SRD coverage: 004.006 by M22; .007 and .010 by M12; .008 by M14, M11 and M10; .009 by M12 and M11; 007.010 by M21 and M25; 010.001–.007 by M25; .008–.011 and .013 by M26 (with M04, M15); .012 by M26 and M25; .014 by M25 and M26.

Cross-tool: MKT `market/lead_brief.py` and `market/checkin_note.py` call `with_research()` and `raise_tickets()`; GUI `gui/ai_desk_research.py` calls `ticket_rows()`, `pending_ticket_edits()`, `lead_research()` and `add_ticket_edit()`.

Changed (step F): M25 gains `raise_follow_ups()` — SRD-DSK-010.015; MKT `market/post_mortem.py` calls it.

## FO-DSK-011 / FO-DSK-012 (AI Desk v3 M0): Message Format and Tool Registry

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-DSK-011.001.M27 | SRD-DSK-011.001 | `us_swing/src/us_swing/core/desk_msg.py` | `desk.msg/1` models: thread, envelope, body by type, want, verdict, data block, meta, states; JSON dump and load; JSON Schema export | `SCHEMA`, `State`, `Thread`, `Message`, `Body`, `Want`, `Verdict`, `Data`, `Flag`, `Meta`, `dump()`, `load()`, `reason()`, `parse_body()`, `message_schema()`, `body_schema()` | `pydantic`, M28 | No |
| MD-DSK-012.001.M28 | SRD-DSK-012.001 | `us_swing/src/us_swing/core/desk_registry.py` | `desk.tool/1` and `desk.schema/1` models, name rules, `tools` and `schemas` tables, seed from steps, research skills, recipe menu and Backtest MCP, fill on desk start, read functions | `TOOL_NAME`, `TOOL_REF`, `SCHEMA_ID`, `Tool`, `Column`, `TableFormat`, `seed_tools()`, `seed_formats()`, `fill_registry()`, `list_tools()`, `get_tool()`, `list_formats()`, `get_format()` | `sqlite3`, `pydantic`, M01, M07, M25, MKT `core/desk_recipes.py`, MCP `mcp/backtest_tools.py` (import path only) | No |

Changed: M04 (`desk/process.py`: `start()` calls `fill_registry()` — SRD-DSK-012.009).

SRD coverage: 011.001–.014 by M27; 012.001–.008, .010 and .011 by M28; .009 by M28 and M04.

## FO-DSK-011 (AI Desk v3 M1): Messages and the Reply Path

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-DSK-011.015.M29 | SRD-DSK-011.015 | `us_swing/src/us_swing/core/desk_messages.py` | `messages` and `threads` tables, the 6-step check, receivers, guardrails, store and wake, refusals, expiry, inbox block, open-started check, reads for the GUI | `accept()`, `inbox()`, `inbox_text()`, `mark_seen()`, `refuse_inbox()`, `expire_due()`, `open_started()`, `read_message()`, `thread_rows()`, `messages_of()`, `Roster`, `ThreadRow`, `MessageRow` | `sqlite3`, M27, M28, M15 | No |

Changed: M27 (`core/desk_msg.py`: send_back parent-or-to rule, `Draft`, `with_messages()`, `InboxReply` — 011.003, .004, .016), M28 (`core/desk_registry.py`: format `idea_fix.v1` — 011.019), M15 (`core/desk_events.py`: `message` rule, `target` column, `post_message()` — .024), M16 (`desk/router.py`: addressed wake, no rewake gap, waiting step and release, expiry each pass — .025, .029, .023), M10 (`desk/employees_step.py`: message wake, inbox facts, payer part, accept drafts, refusals — .026, .028, .030, .031), M11 (`desk/gateway.py`: `talk`, `drafts`, `send()`, message id on tries — .016, .030), M12 (`desk/budget.py`: `Part.message` — .030), M14 (`desk/recorder.py`: `message` column, `last_wake` skips message turns — .025, .030), M08 (`core/desk_agents.py`: `Facts.inbox`, `talker()` — .016, .026), M13 (`core/desk_ai_settings.py`: `messages_on` — .031).

SRD coverage: 011.003, .004 and .016 by M27; .014, .015, .017–.024, .026, .027 and .032 by M29; .025 by M16 and M14; .028 by M10 and M29; .029 by M16 and M29; .030 by M10, M11, M12 and M14; .031 by M13, M10 and M11.

## FO-DSK-011 (AI Desk v3 M2): Escalation and Deputies

No new module. Changed: M29 (`core/desk_messages.py`: `Person.boss` and `.deputy`, escalate accept, `boss` address, 5-minute move up in `expire_due()`, `hand_to_deputy()`, `handed` column, `mark_seen(receiver=)`, replies to escalates wake nobody — 011.014, .033, .034, .036–.038, .040, .041, .043), M15 (`core/desk_events.py`: `post_message(priority=, again=)` — .035), M16 (`desk/router.py`: roster and send passed to `expire_due()` — .036), M10 (`desk/employees_step.py`: roster with boss and deputy, `_answer_escalations()`, `_refuse()` with deputy first, `escalation` passed to `accept()` — .039–.042), M13 (`core/desk_ai_settings.py`: `escalation_on` — .042), M21 (`core/desk_alerts.py`: kind `escalation` — 007.011), M22 (`core/desk_employee.py`: `JobSpec.deputy`, deputy checks, `render` leaves out an empty deputy — 008.010).

SRD coverage: 011.014, .033, .034, .036–.038, .041 and .043 by M29; .035 by M15 and M29; .036 also by M16; .039 and .040 by M10 and M29; .042 by M13 and M10; 007.011 by M21 and M29; 008.010 by M22.

## FO-DSK-009 (AI Desk v3 M3): Memory v2

| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |
|---|---|---|---|---|---|---|
| MD-DSK-009.010.M30 | SRD-DSK-009.010 | `us_swing/src/us_swing/core/desk_memory.py` | `memory.db` file and tables, lesson move, clean write, core block, recall, view scores, review, edits, reads for the GUI | `MEMORY_DB`, `connect()`, `read_only()`, `move_lessons()`, `write()`, `core_block()`, `recall()`, `open_views_due()`, `score_view()`, `review()`, `add_edit()`, `apply_edits()`, `memory_rows()`, `Memory` | `sqlite3`, M23, M27 | No |
| MD-DSK-009.021.M31 | SRD-DSK-009.021 | `us_swing/src/us_swing/desk/memory_cleanup.py` | Weekly clean-up step: one call per lead or expert with notes, actions applied by code | `MemoryCleanupStep`, `Cleanup` | M30, M11, M10, M20 | No |

Changed: M23 (`core/desk_lessons.py`: `connect()` and `_read_only()` open `memory.db` — 009.011), M27 (`core/desk_msg.py`: `Remember`, `with_remember()` — .013), M11 (`desk/gateway.py`: `remember`, `notes` — .013), M10 (`desk/employees_step.py`: core block and recall in facts, write notes after act — .016, .017, .014), M13 (`core/desk_ai_settings.py`: `memory_v2_on` — .023), M04 (`desk/process.py`: applies memory edits — .022). `core/desk_steps.py` adds the view check and clean-up step paths.

SRD coverage: .010–.012, .014–.020, .022 and .024 by M30; .011 also by M23; .013 by M27, M11 and M10; .016 and .017 also by M10; .021 by M31; .022 also by M04; .023 by M13, M10, M31.
