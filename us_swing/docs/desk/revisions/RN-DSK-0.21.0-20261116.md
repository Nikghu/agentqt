# Revision Note — RN-DSK-0.21.0-20261116

**Version:** 0.21.0
**Date:** 2026-11-16
**Tool:** DSK
**Artifact:** FO-DSK-013 (new), FO-DSK-006, FO-MKT-021 (M7b block), FO-MKT-010, FO-GUI-041 (M7b block), FO-GUI-034 / SRD-DSK-013.001–.024, SRD-DSK-006.028, SRD-MKT-021.007–.010, SRD-MKT-010.022, SRD-GUI-041.006–.010, SRD-GUI-034.085
**Type:** Feature

---

## Summary

AI Desk v3 phase M7b: the tool builder. With `tool_builder_on` on, the Master user asks for a small tool in AI Desk → Tools ("Request a tool"), or in Command chat, where the chat lead passes the wish on as one ask to `skill:tool_builder`. A new builder employee (default `emp-021`, "Champion 2", title Tool builder, reports to the planner) makes one AI call that writes one Python function `tool(symbol)` with 1–5 typed columns. Code checks the answer and the code against fixed rules (one `def tool(symbol)`, only listed names and attribute names, no import, class, `with`, `match`, no name or attribute that starts with `_`), saves each version once as `<desk>/tools/<name>/v<N>.py` with its SHA-256, and runs it in a separate process (multiprocessing spawn, as the backtest workers) with a 60-second limit and a 512 MB memory cap; only JSON comes back. Inside, the code sees only safe built-ins, `math`, a few statistics functions and three read-only functions (`daily_bars`, `intraday_bars`, `desk_rows`). Five checks run on up to 5 sample stocks and one made-up stock; a problem gets one more AI call (at most 2 per request). A version that passes waits for review: the Master user reads the request, the checks, sample rows and the code in Tools and presses Enable, which makes the registry tool `built.<name>`, its table format `<name>.v<N>` and its plan; the chat lead then lists that format and the planner runs the tool through the sandbox. A version whose file changed after review never runs. Nothing is switched on by itself. Off by default; off keeps the M7a desk as it was. Also fixed: a new hire's id now stays above every shipped default id, so a hire can never take the id of a default employee the desk adds later.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-DSK-013.001.M37 | `src/us_swing/core/desk_built_tools.py` (new) | `tool_requests` and `built_tools` tables, requests, answer model and checks, code rules, versions with SHA-256, sample stocks, Enable (with roll back) and Disable, reads |
| MD-DSK-013.010.M38 | `src/us_swing/desk/sandbox.py` (new) | Child process run with time limit, JSON back only, tool functions for the planner |
| MD-DSK-013.011.M39 | `src/us_swing/desk/sandbox_child.py` (new) | Memory cap, watchdog, rules checked again, safe names, one call per stock, value checks, deadline |
| MD-DSK-013.003.M40 | `src/us_swing/desk/tool_builder.py` (new) | Builder skill: chat asks to requests, facts, AI answer with one fix round, checks, reply, logs |
| MD-MKT-021.007.M02 | `src/us_swing/market/tool_reads.py` (new) | The three read functions for built tools |
| MD-DSK-012.001.M28 | `src/us_swing/core/desk_registry.py` | `built.*` rows kept on a desk start; write one tool or format, drop a format |
| MD-DSK-012.016.M32 | `src/us_swing/core/desk_tasks.py` | Make or drop the plan of one format |
| MD-DSK-012.021.M33 | `src/us_swing/desk/champions.py` | A tool may be a function, not only an import path |
| MD-DSK-012.018.M34 | `src/us_swing/desk/planner.py` | Enabled built tools join the tool paths |
| MD-DSK-003.004.M15 | `src/us_swing/core/desk_events.py` | Event kind `tool_request` (one per request) |
| MD-DSK-004.005.M13 | `src/us_swing/core/desk_ai_settings.py` | `tool_builder_on`, off by default |
| MD-DSK-001.021.M07 | `src/us_swing/core/desk_steps.py`, `src/us_swing/market/employees/emp-021/` (new), `USSwing.spec` | `tool_builder` skill path, read functions path, default builder, app build modules |
| MD-DSK-006.001.M18 | `src/us_swing/core/desk_hiring.py` | A new hire's id stays above the shipped default ids |
| MD-MKT-010.003.M03 | `src/us_swing/market/lead_chat.py` | Tool request hint for the chat lead |
| MD-GUI-041.001.M01 | `src/us_swing/gui/ai_desk_tools.py` | Request box, tool requests, built tools, review detail with the code, Enable and Disable |
| MD-GUI-034.016.M15 | `src/us_swing/gui/ai_desk_settings.py` | Tool builder check box |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-DSK-013.001 | A typed request is saved and posts one `tool_request` event | Implemented |
| SRD-DSK-013.002 | An ask to `skill:tool_builder` becomes one chat request | Implemented |
| SRD-DSK-013.003 | Every new request of the last day built in one wake; old ones ended | Implemented |
| SRD-DSK-013.004 | Builder facts: request, read functions, rules, built tools, taken names | Implemented |
| SRD-DSK-013.005 | One AI answer: name, title, about, 1–5 columns and code, or a refusal | Implemented |
| SRD-DSK-013.006 | Answer checks: name, title, about, columns | Implemented |
| SRD-DSK-013.007 | Code rules checked before a version runs | Implemented |
| SRD-DSK-013.008 | One fix round; at most 2 AI calls per request | Implemented |
| SRD-DSK-013.009 | Each version saved once with its SHA-256 | Implemented |
| SRD-DSK-013.010 | Separate process, 60 s, 512 MB, JSON back only | Implemented |
| SRD-DSK-013.011 | Only safe names and the read functions in the sandbox | Implemented |
| SRD-DSK-013.012 | One call per stock; an error or wrong value gives a reason | Implemented |
| SRD-DSK-013.013 | Code changed after review never runs | Implemented |
| SRD-DSK-013.014 | Five checks on sample stocks and a made-up stock | Implemented |
| SRD-DSK-013.015 | Review or failed; the builder never enables | Implemented |
| SRD-DSK-013.016 | One reply per chat request | Implemented |
| SRD-DSK-013.017 | Enable writes the registry tool, format and plan | Implemented |
| SRD-DSK-013.018 | Disable sets the tool off and removes its format and plan | Implemented |
| SRD-DSK-013.019 | A desk start keeps the `built.*` rows | Implemented |
| SRD-DSK-013.020 | The planner runs enabled built tools through the sandbox | Implemented |
| SRD-DSK-013.021 | `tool_builder_on`, off by default | Implemented |
| SRD-DSK-013.022 | Default builder `emp-021`, skill path, app build modules | Implemented |
| SRD-DSK-013.023 | Reads of requests, versions and code | Implemented |
| SRD-DSK-013.024 | `[Tool builder]` log lines | Implemented |
| SRD-DSK-006.028 | A new hire's id stays above the shipped default ids | Implemented |
| SRD-MKT-021.007 | `daily_bars` from Backtest Data | Implemented |
| SRD-MKT-021.008 | `intraday_bars` (15 or 30 minutes) | Implemented |
| SRD-MKT-021.009 | `desk_rows` from the data recipe menu | Implemented |
| SRD-MKT-021.010 | Plain data, input checks, read-only | Implemented |
| SRD-MKT-010.022 | Tool request hint for the chat lead | Implemented |
| SRD-GUI-041.006 | Request a tool box | Implemented |
| SRD-GUI-041.007 | Tool requests list | Implemented |
| SRD-GUI-041.008 | Built tools list | Implemented |
| SRD-GUI-041.009 | Review detail with checks, sample rows and code | Implemented |
| SRD-GUI-041.010 | Enable and Disable | Implemented |
| SRD-GUI-034.085 | Tool builder check box, off by default | Implemented |

---

## Design Decisions

- User decisions 2026-11-15: requests come from the Master user in AI Desk → Tools and in Command chat (not from refused table asks); a tool's code may call the desk's read-only functions itself; an enabled tool becomes a table format the chat lead can ask the planner for. Locked earlier: sandbox, Master code review, never switched on by itself.
- Recipe first is dropped: with the read functions inside the sandbox, a recipe tool would be a two-line tool reviewed the same way.
- The planner never calls a model and an employee holds one skill, so a new builder employee writes the code; it reports to the planner. Name and boss are data the Master user can change.
- The sandbox is a separate process started like the backtest workers; only JSON bytes come back, so the desk never unpickles child data. Safety comes from layers: the rule check (allow-lists of names and attribute names), the restricted built-ins, the separate process, the time limit, the Windows job object memory cap, read-only functions that return plain data, the SHA-256 binding, and the Master user's review before Enable.
- The fix for hire ids (SRD-DSK-006.028) was found while planning: a hire made before the desk adds a new default employee could take its id.
- Code review fixes (DD-DSK-013.001.D01 §17, DD-GUI-041.006.D01): the rule check never raises (no recursion; too-deep code is a problem line); a huge int is one wrong value; the child stops starting stocks before the limit so made rows reach the desk; the child reports whether its memory cap was set; only an over-long message is "too much output"; Enable rolls back a half-done write; stale requests are ended; a broken row is skipped; the GUI shows model text as plain text, confirms Enable and Disable, and takes its button rule from core.

---

## Issues Resolved

None

---

## Test Coverage

- `tests/desk/`: 76 UT-DSK-013 and UT-DSK-006.028 cases (67 + 9 added from the code review), all Pass, in `test_desk_built_tools.py`, `test_sandbox.py` (real child processes, including the time limit and the memory cap), `test_tool_builder.py`, `test_tool_builder_flow.py`, `test_desk_events.py` and `test_hiring.py`. `tests/desk` + `tests/core`: 1057 pass before the review fixes; after them `tests/desk`, `tests/core`, `tests/market` and `tests/integration` together: 1761 pass, 2 skipped.
- `tests/market/`: 10 UT-MKT-021.007–.010 and UT-MKT-010.022 cases Pass; `tests/market` + `tests/integration`: 695 pass, 2 skipped.
- `tests/gui/`: 13 UT-GUI-041.006–.010 and UT-GUI-034.085 cases Pass. Whole GUI suite in chunks of 8 files: 999 pass; one old failure not from M7b (`test_sidebar_shell.py::test_main_window_lists_screens`).
- Older tests updated for the new rules: `test_desk_events.py` (new event kind), `test_p5b_defaults.py` (new skill), `test_hiring.py` (a new hire's id is above the shipped ids).
- ruff and mypy --strict clean on the new and changed files.

Known limits: a single stock whose call never ends is stopped with the whole run at the 60-second limit; the memory cap is a Windows job object (elsewhere the run is logged as uncapped). The user checks the flow in the app (TODO T181).
