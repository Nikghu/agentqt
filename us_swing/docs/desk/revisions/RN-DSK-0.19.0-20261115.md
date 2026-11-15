# Revision Note — RN-DSK-0.19.0-20261115

**Version:** 0.19.0
**Date:** 2026-11-15
**Tool:** DSK
**Artifact:** FO-DSK-012 (M6 part), FO-MKT-021, FO-MKT-010, FO-GUI-041, FO-GUI-034 / SRD-DSK-012.012–.031, SRD-MKT-021.001–.006, SRD-MKT-010.020–.021, SRD-GUI-041.001–.005, SRD-GUI-034.079–.080
**Type:** Feature

---

## Summary

AI Desk v3 phase M6: planner and task cards. With `task_cards_on` (and agent messages) on, an employee can ask the task planner for a table in a ready format for up to 30 stocks. The planner makes no AI call: it finds the saved plan of the format, opens a task card, runs the key tool first and then the other tool groups together on up to 4 code workers, merges the parts on the stock, checks every value against its column and replies with the table and a reason for every empty value. The first format is `setup_table.v1` (symbol, close, rs_rank, atr_pct, side, setup, trigger, stop, earn_days), filled by five read-only table tools. The lead chat is the first user: with Chat sessions on, its one team ask may go to the planner, and the table comes back as the chat update, written by code. A refused ask and a failed part are kept in a failure log; three cards in a row with a failed part retire the plan and raise one alert until the next desk start. AI Desk has a new read-only Tools tab. Off by default; off keeps the M5 desk as it was.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-DSK-012.016.M32 | `src/us_swing/core/desk_tasks.py` (new) | `task_plans` and `task_cards` tables, plan from the made-by tools, fill on desk start, cards, fail count and retire, close of cards left working, reads |
| MD-DSK-012.021.M33 | `src/us_swing/desk/champions.py` (new) | Tool groups: run one part with one retry, run a wave on up to 4 workers with time limits |
| MD-DSK-012.018.M34 | `src/us_swing/desk/planner.py` (new) | Planner skill: checks and refusals, card, waves, merge and check, reply, failure rows, retire alert, logs |
| MD-DSK-012.001.M28 | `src/us_swing/core/desk_registry.py` | `Tool.secs`, `Column.by`, `TableFormat.key`, `ToolResult`; table tools and `setup_table.v1` seeded |
| MD-DSK-001.021.M07 | `src/us_swing/core/desk_steps.py`, `src/us_swing/market/employees/emp-019/` (new), `USSwing.spec` | `TOOL_PATHS`, `task_planner` skill path, default planner employee, app build modules |
| MD-DSK-004.005.M13 | `src/us_swing/core/desk_ai_settings.py` | `task_cards_on`, off by default |
| MD-DSK-009.010.M30 | `src/us_swing/core/desk_memory.py` | `log_failure()`, `failure_rows()` (kind `failure`, never in a prompt) |
| MD-DSK-007.001.M21 | `src/us_swing/core/desk_alerts.py` | Alert kind `plan_retired`, closed once the plan is active again |
| MD-DSK-001.010.M04 | `src/us_swing/desk/process.py` | Desk start closes cards left working and makes the plans again |
| MD-MKT-021.001.M01 | `src/us_swing/market/table_tools.py` (new) | Five read-only table tools |
| MD-MKT-010.001.M01 | `src/us_swing/core/desk_chat.py` | `TeamReply.table`, `table_text()` |
| MD-MKT-010.003.M03 | `src/us_swing/market/lead_chat.py` | Table hint with the ready formats; table reply posted as the update with no AI call |
| MD-GUI-041.001.M01 | `src/us_swing/gui/ai_desk_tools.py` (new) | Tools tab: tools, table formats with plan state, task cards with parts, failure log |
| MD-GUI-034.009.M08 | `src/us_swing/gui/ai_desk.py` | Tools tab in the SETUP group before Desk settings |
| MD-GUI-034.039.M26 | `src/us_swing/gui/ai_desk_chat.py` | `table_html()`: table lines in a chat bubble show as a table |
| MD-GUI-034.016.M15 | `src/us_swing/gui/ai_desk_settings.py` | Task cards check box, enabled only with Agent messages |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-DSK-012.012 | A tool row may hold `secs`, its time limit | Implemented |
| SRD-DSK-012.013 | Table tools return a tool result with rows, missing reasons, flags and `isError` | Implemented |
| SRD-DSK-012.014 | A format column may name the tool that makes it; the first column is the key | Implemented |
| SRD-DSK-012.015 | Five table tools with time limits and `setup_table.v1` are seeded | Implemented |
| SRD-DSK-012.016 | One saved plan per format with an active key tool: wave 1 key group, wave 2 other groups; made again on each desk start | Implemented |
| SRD-DSK-012.017 | Each worked ask is one `task_cards` row | Implemented |
| SRD-DSK-012.018 | The `task_planner` skill answers each ask with one reply and makes no AI call | Implemented |
| SRD-DSK-012.019 | Asks with no format, no active plan, an unknown column or not 1 to 30 symbols are refused | Implemented |
| SRD-DSK-012.020 | A column whose tool is missing or off is empty with "not available" | Implemented |
| SRD-DSK-012.021 | A tool is called only by its tool group, for its part's tools and columns | Implemented |
| SRD-DSK-012.022 | Wave 2 parts run together on at most 4 workers, on the keys wave 1 returned | Implemented |
| SRD-DSK-012.023 | One retry per raising call; a failed or late part ends failed with its reason | Implemented |
| SRD-DSK-012.024 | Rows merged on the key in the asked order; wrong values emptied with a reason | Implemented |
| SRD-DSK-012.025 | Reply with the data block, a reason per empty value, up to 5 flags, done / partial / failed | Implemented |
| SRD-DSK-012.026 | Each refused ask and failed part adds one failure row in the planner's name | Implemented |
| SRD-DSK-012.027 | 3 cards in a row with a failed part retire the plan with one alert | Implemented |
| SRD-DSK-012.028 | Task cards run only with `task_cards_on` and `messages_on`; off by default | Implemented |
| SRD-DSK-012.029 | Default planner employee (`emp-019`, "Champion 1", trigger `message`) and build paths | Implemented |
| SRD-DSK-012.030 | Reads of plans, latest cards, ready formats and failure rows | Implemented |
| SRD-DSK-012.031 | Done, partial, failed, refused cards and a retired plan are logged with `[Task cards]` | Implemented |
| SRD-MKT-021.001 | `data.daily_close`: last daily close | Implemented |
| SRD-MKT-021.002 | `technical.rs_rank`: RS rating of the latest data day | Implemented |
| SRD-MKT-021.003 | `technical.atr_pct`: 14-day ATR as a percent of the close | Implemented |
| SRD-MKT-021.004 | `technical.setup`: better-scored side with setup, trigger and stop | Implemented |
| SRD-MKT-021.005 | `calendar.earnings`: trading days to the next earnings date, flag at 5 or fewer | Implemented |
| SRD-MKT-021.006 | Table tools only read, make no AI call and return a tool result | Implemented |
| SRD-MKT-010.020 | With task cards on, the lead's ask hint lists the ready formats and how to ask the planner | Implemented |
| SRD-MKT-010.021 | A table reply becomes the chat update as text written by code | Implemented |
| SRD-GUI-041.001 | Tools tab lists the registry tools | Implemented |
| SRD-GUI-041.002 | Tools tab lists the table formats, made-by tools and plan state | Implemented |
| SRD-GUI-041.003 | Tools tab lists the latest 50 task cards | Implemented |
| SRD-GUI-041.004 | A picked card shows one line per part | Implemented |
| SRD-GUI-041.005 | Tools tab lists the latest 50 failure rows | Implemented |
| SRD-GUI-034.079 | Table lines in a chat bubble show as a table | Implemented |
| SRD-GUI-034.080 | Task cards check box in Desk settings, off by default | Implemented |

---

## Design Decisions

- User decisions 2026-11-14: the planner is one employee (renamable, in the reporting tree) and the tool runners are code tool groups; the lead chat asks first; an ask with no ready format is refused and logged, with no AI planning; only the parts of one card run in parallel, the router stays serial.
- Parts are code calls inside the planner's turn and live on the task card; the M0 `task` message type and `champion:` address are still unused.
- `setup_table.v1` has a `side` column (the desk trades both sides); close and ATR come from the same daily bars as the day's views.
- The default planner is named "Champion 1" (every shipped default has a generic level name) with title "Task planner", and its only trigger is `message`.
- The table hint shows only when an active employee holds the planner skill, so the lead never asks a planner that does not exist.
- Research tickets (FO-DSK-010, FO-MKT-014) were not touched: nothing needs a table there in M6.
- Code review fixes (DD-DSK-012.012.D01 §13): an ask whose work raises gets a failed reply and its card is closed; cards left working are closed at desk start; each tool keeps its own empty-value reasons; a failed reply keeps the first reason; a missing candle file gives a plain reason; a row with no score never wins.
- Kept as designed: one failing tool fails its whole part; a timed-out worker thread ends by itself; failure rows are kept with no clean-up (M7 reads them).

---

## Issues Resolved

None

---

## Test Coverage

- `tests/desk/`: 72 UT-DSK-012.012–.031 cases (6 added from the code review), all Pass. `tests/desk` + `tests/core`: 908 pass.
- `tests/market/`: 24 UT-MKT-021 and UT-MKT-010.020–.021 cases (1 added from the code review), all Pass. `tests/market`: all pass after two default-employee tests were updated for `emp-019` and the `task_planner` skill.
- `tests/gui/`: 11 UT-GUI-041 and UT-GUI-034.079–.080 cases, all Pass; 3 older AI Desk section-count tests updated for the Tools tab. Run in chunks: all pass except items that are not from M6 — `test_sidebar_shell.py::test_main_window_lists_screens` (that file and `main_window.py` are untouched on this branch) and 22 `test_chart_workspace.py` errors that appear only when it runs after other files in one run (it passes alone).
- ruff and mypy --strict clean on the new and changed source files.

Known limits: the user checks the flow in the app (TODO T179).
