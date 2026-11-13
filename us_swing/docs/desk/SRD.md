# Software Requirements — Desk Harness (DSK)

**Document ID:** SRD-DSK
**Version:** 0.7.2
**Status:** Draft
**Last Updated:** 2026-11-11
**Project:** US Swing Trading System

> v0.15.2: SRD-DSK-011.001–.014 and 012.001–.011 Implemented 2026-11-13.
> v0.15.1: SRD-DSK-011.001–.014 and 012.001–.011 approved by user 2026-11-13.
> v0.15.0: AI Desk v3 M0 (user, 2026-11-13): SRD-DSK-011.001–.014 and 012.001–.011 added as Draft (trimmed by user to rows M0 uses) — message format, tool registry and schema library.
> v0.14.2: SRD-DSK-010.016 Implemented 2026-11-12.
> v0.14.1: SRD-DSK-010.016 approved by user 2026-11-12.
> v0.14.0: Strategy test (user, 2026-11-12): SRD-DSK-010.016 added as Draft — owner-raised strategy test ticket.
> v0.13.2: SRD-DSK-010.015 Implemented (2026-11-11).
> v0.13.1: SRD-DSK-010.015 approved by user 2026-11-11.
> v0.13.0: Autonomous desk step F (user, 2026-11-11): SRD-DSK-010.015 added as Draft — follow-up tickets from research skills.
> v0.12.2: Step E rows Implemented (20, 2026-11-11).
> v0.12.1: SRD-DSK-004.006–.010, 007.010 and 010.001–.014 approved by user 2026-11-11.
> v0.12.0: Autonomous desk step E (user, 2026-11-11): SRD-DSK-004.006–.010, 007.010 and 010.001–.014 added as Draft — token split and research queue.
> v0.11.2: Step D rows Implemented (7, 2026-11-11).
> v0.11.1: SRD-DSK-003.020–.025 and 007.009 approved by user 2026-11-11.
> v0.11.0: Autonomous desk step D (user, 2026-11-11): SRD-DSK-003.020–.025 and 007.009 added as Draft — check-ins and watchers.
> v0.10.2: SRD-DSK-009.001–.009 Implemented 2026-11-11.
> v0.10.1: SRD-DSK-009.001–.009 approved by user 2026-11-11.
> v0.10.0: Autonomous desk step C (user, 2026-11-11): SRD-DSK-009.001–.009 added as Draft — memory v1.
> v0.9.4: Step B rows SRD-DSK-003.010–.012, .014–.019 and 007.008 Implemented 2026-11-11.
> v0.9.3: SRD-DSK-003.010–.012 approved by user 2026-11-11.
> v0.9.2: SRD-DSK-003.010–.012 reopened by user 2026-11-11 and reworded (events instead of one LangGraph graph; failed step stops the chain; LangGraph removed).
> v0.9.1: Step B rows SRD-DSK-003.014–.019 and 007.008 approved by user 2026-11-11.
> v0.9.0: Autonomous desk step B (user, 2026-11-11): baton `step_done` events; SRD-DSK-003.014–.019 and 007.008 added as Draft. SRD-DSK-003.010–.012 need Reopen (one LangGraph graph replaced by events; dependents of a failed step no longer run).
> v0.8.2: Step A rows Implemented 2026-11-11.
> v0.8.1: Step A rows approved by user 2026-11-11.
> v0.8.0: Autonomous desk step A (user, 2026-11-10): SRD-DSK-001.013/.015/.018/.019/.020 and 007.005 reopened and reworded (morning run, desk lives with the app); SRD-DSK-003.013 and 007.007 added as Draft.
> v0.7.2: SRD-DSK-008.001–.009 Implemented 2026-11-10 (employee.md, versions, draft test).
> v0.7.1: SRD-DSK-008.001–.009 approved by user 2026-11-10.
> v0.7.0: SRD-DSK-008.001–.009 added as Draft — employee.md, shared rules, migration, versions, draft test.
> v0.6.1: SRD-DSK-006.001–.010 approved by user 2026-11-06.
> v0.6.0: SRD-DSK-006.001–.010 added as Draft — hiring pipeline, shadow, seat caps, weekly report (P6).
> v0.5.1: SRD-DSK-002.001/.002/.004/.005 reworded and .006–.007 added — skills by key, identity as data, generic levels (asked by user, 2026-11-06).
> v0.5.0: SRD-DSK-002.001–.005, 003.001–.003, 004.001–.005, 005.001–.004 added as Draft (P5a harness).
> v0.4.0: SRD-DSK-001.022 added as Draft — `desk proof` sub-command (for MKT P4).
> v0.3.0: SRD-DSK-001.021 added as Draft — desk loads registered steps (for MKT P1).
> v0.2.0: SRD-DSK-001.001–.020 added — desk process shell (FO-DSK-001, phase P0a).
> v0.1.0: Empty.

---

## FO-DSK-001: Desk Process Shell

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-DSK-001.001 | FO-DSK-001 | Must | The desk keeps its data in `~/.usswing/desk/desk.db`, opened in WAL mode with a busy timeout. | folder | `desk.db` | Folder injectable for tests | Implemented |
| SRD-DSK-001.002 | FO-DSK-001 | Must | The desk creates the `desk_state`, `commands` and `runs` tables on first open and records a schema version. | — | tables | Re-open never loses rows | Implemented |
| SRD-DSK-001.003 | FO-DSK-001 | Must | `desk_state` holds one row: state, heartbeat time, process id, message and saved resume point. | — | row | Times stored as UTC ISO text | Implemented |
| SRD-DSK-001.004 | FO-DSK-001 | Must | The desk state is one of Running, Sleeping, Paused, Stopping, Stopped, Off, Error. | — | `DeskState` | Shared enum in `core/desk_contract.py` | Implemented |
| SRD-DSK-001.005 | FO-DSK-001 | Must | The app sends pause, resume, stop and run-now only by adding a pending row to `commands`. | kind | command id | App never writes other desk tables | Implemented |
| SRD-DSK-001.006 | FO-DSK-001 | Must | A read-only reader reports Off when there is no `desk.db` or no state row. | path | `DeskStatus` | Never creates the file | Implemented |
| SRD-DSK-001.007 | FO-DSK-001 | Must | The reader reports Error "not responding" when a live state has a heartbeat older than 60 seconds. | row, now | `DeskStatus` | Stopped and Off never go stale | Implemented |
| SRD-DSK-001.008 | FO-DSK-001 | Must | Only one desk process runs at a time; a second one exits at once without touching state. | lock file | exit | Lock is released when the process dies | Implemented |
| SRD-DSK-001.009 | FO-DSK-001 | Must | The running desk writes a heartbeat every 10 seconds. | clock | `desk_state` | — | Implemented |
| SRD-DSK-001.010 | FO-DSK-001 | Must | The desk reads pending commands every 2 seconds, applies them in order and marks each done or rejected with a reason. | `commands` | status | A command not valid in the current state is rejected | Implemented |
| SRD-DSK-001.011 | FO-DSK-001 | Must | Pause holds all timers and resume returns the desk to Sleeping. | command | state | Commands still read while Paused | Implemented |
| SRD-DSK-001.012 | FO-DSK-001 | Must | Stop moves to Stopping, finishes the current step, saves the resume point, sets Stopped and exits. | command | state | No step is cut half way | Implemented |
| SRD-DSK-001.013 | FO-DSK-001 | Must | A desk started without `--resume` exits at once when the saved state is Stopped; the app and `desk start` launch with `--resume`, which clears it. | saved state | exit | Reopened 2026-11-10: no desk Windows task any more | Implemented |
| SRD-DSK-001.014 | FO-DSK-001 | Must | On start, a run with no end time is marked interrupted and run again. | `runs` | new run | — | Implemented |
| SRD-DSK-001.015 | FO-DSK-001 | Must | The morning run is due on NYSE trading days from 04:00 to 16:00 New York time until one ends ok that day; a failed try is repeated after 15 minutes, at most 3 tries a day. | clock, today's morning runs | due flag | Pure function, clock passed in; reopened 2026-11-10: replaces the 16:25 evening run | Implemented |
| SRD-DSK-001.016 | FO-DSK-001 | Must | Each run is a `runs` row (kind, start, end, result, note) and calls the registered desk steps in order. | steps | row | Zero steps in P0a gives result ok | Implemented |
| SRD-DSK-001.017 | FO-DSK-001 | Must | A failed step ends the run as failed and sets Error with a short message; the next good run sets Sleeping. | exception | state | Process keeps running | Implemented |
| SRD-DSK-001.018 | FO-DSK-001 | Must | The desk has no Windows tasks; each desk start deletes the old `USSwing_Desk` and `USSwing_Desk_Evening` tasks when they exist. | task names | none | No console window; a missing task is not an error; reopened 2026-11-10 | Implemented |
| SRD-DSK-001.019 | FO-DSK-001 | Must | A desk launched with `--parent PID` checks every poll that the process is alive and, when it is gone, stops as on a Stop command. | parent pid | Stopping state | Reopened 2026-11-10: replaces the evening task re-check; the unfinished run is caught up at the next start | Implemented |
| SRD-DSK-001.020 | FO-DSK-001 | Must | `python -m us_swing desk [--resume] [--parent PID]` runs the desk; `desk start/status/pause/resume/stop/run-now/proof/replay` control it. | argv | exit code, text | `start` launches a detached process; reopened 2026-11-10: `install`/`uninstall` removed | Implemented |
| SRD-DSK-001.021 | FO-DSK-001 | Must | The desk loads its steps from the step list in `core/desk_steps.py`, and each step gets the desk folder in its context. | step list | steps | A step that fails to load is logged and left out | Implemented |
| SRD-DSK-001.022 | FO-DSK-001 | Must | `desk proof` runs the score proof on past data and prints its report. | argv | report text, exit code | Loaded by import path; exit 1 when there is no data | Implemented |

## FO-DSK-002: Employee Registry and Job Descriptions

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-DSK-002.001 | FO-DSK-002 | Must | Code knows skills only, by key, through the skill list in `core/desk_steps.py`; each employee's `job.yaml` names the skill it uses. | skill list, job files | skills | `desk` never imports a tool directly; an unknown skill keeps that employee asleep | Implemented |
| SRD-DSK-002.002 | FO-DSK-002 | Must | `job.yaml` must match a fixed schema: id, name, title, level, reports_to, skill, version, trigger, primary and backup model, calls per day, monthly cost cap and KPIs. | `job.yaml` | job spec | A bad file keeps that employee asleep and is logged | Implemented |
| SRD-DSK-002.003 | FO-DSK-002 | Must | Trigger, models and caps come only from `job.yaml`; `soul.md` is used only as the system prompt. | job spec | rules in code | — | Implemented |
| SRD-DSK-002.004 | FO-DSK-002 | Must | Each loaded id, name, title, level, reporting line, skill, version and file hash is kept in `roster` in `desk.db`. | job spec | `roster` rows | A changed file with the same version is logged as a warning | Implemented |
| SRD-DSK-002.005 | FO-DSK-002 | Must | Skills get only the desk folder, their facts and an ask function, with no way to write employee files. | — | — | Editing and rollback from AI Desk come in P6 | Implemented |
| SRD-DSK-002.006 | FO-DSK-002 | Must | Name, title, level (lead, expert, champion, junior) and reporting line are data in `job.yaml`; code, tests and labels use no employee names, and records key on a stable id. | `job.yaml` | identity | Asked by user 2026-11-06; a repeated id keeps the second folder asleep | Implemented |
| SRD-DSK-002.007 | FO-DSK-002 | Must | Employee files live in `<desk>/employees/<id>/`; shipped defaults with generic level names are copied there only when missing. | default folders | employee folders | Never overwrites the Master user's edits | Implemented |
| SRD-DSK-002.008 | FO-DSK-002 | Must | Each skill names the skill keys whose views it needs; these are about function, never about employees or reporting lines. | skill | needs list | Empty for P5a skills; an unknown key is logged and left out | Implemented |
| SRD-DSK-002.009 | FO-DSK-002 | Must | `trigger` in `job.yaml` may be one event kind or a list of event kinds. | `job.yaml` | trigger list | A single value, as in P5a files, still loads | Implemented |

## FO-DSK-003: Event Router, Market Clock and Wake Rules

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-DSK-003.001 | FO-DSK-003 | Must | A desk step "AI employees" runs after "Ideas" and wakes each employee whose trigger is `after_run`. | desk run | employee runs | One failing employee never fails the run | Implemented |
| SRD-DSK-003.002 | FO-DSK-003 | Must | An employee wakes at most once per data day. | `activity` | skip or wake | A failed day may be tried again on the next run | Implemented |
| SRD-DSK-003.003 | FO-DSK-003 | Must | An employee wakes only when its facts say the data is fresh. | facts | skip or wake | The reason for a skip is logged | Implemented |
| SRD-DSK-003.004 | FO-DSK-003 | Must | Wake-ups are events kept in `events` in `desk.db` with kind, priority, data day, created time, deadline, expiry and state (waiting, done, late, expired). | event | `events` row | Only the router changes the state | Implemented |
| SRD-DSK-003.005 | FO-DSK-003 | Must | Event kinds are `after_run` (P1), `regime_change` (P0), `market_open` (P2) and `market_close` (P2). | — | kinds | `regime_change` is posted when today's rule regime differs from the day before | Implemented |
| SRD-DSK-003.006 | FO-DSK-003 | Must | The router handles waiting events by priority, then by created time. | `events` | wake order | P0 first | Implemented |
| SRD-DSK-003.007 | FO-DSK-003 | Must | An event past its expiry is marked expired and not handled; one handled after its deadline is marked late; both are logged. | event, clock | state, log line | Expiry: P0 2 h, P1 6 h, P2 30 min; deadline: P0 15 min, P1 2 h, P2 none | Implemented |
| SRD-DSK-003.008 | FO-DSK-003 | Must | While the desk runs, a market clock posts `market_open` at 09:30 and `market_close` at 16:00 New York time on NYSE trading days. | clock | events | Uses the app's NYSE calendar; each is posted once per day | Implemented |
| SRD-DSK-003.009 | FO-DSK-003 | Must | An employee is not woken again within 30 minutes of its last wake, except by a P0 event. | `activity` | skip or wake | The once-per-data-day rule still applies to `after_run` | Implemented |
| SRD-DSK-003.010 | FO-DSK-003 | Must | The employees woken by one event run one at a time in needs order, driven by `step_done` events (SRD-DSK-003.015). | woken employees, needs | run order | A loop in the needs keeps the chain asleep and is logged; reopened 2026-11-11: no LangGraph graph | Implemented |
| SRD-DSK-003.011 | FO-DSK-003 | Must | A sleeping employee never stops the chain; those that need its view still run and their facts say the view is missing. | `step_done` row | facts note | A failed employee stops the chain instead (SRD-DSK-003.017); reopened 2026-11-11 | Implemented |
| SRD-DSK-003.012 | FO-DSK-003 | Must | The desk does not use `langgraph`; it is removed from the desk dependencies and the installer. | — | package | Reopened 2026-11-11: removed by step B | Implemented |
| SRD-DSK-003.013 | FO-DSK-003 | Must | Run kinds are `morning`, `manual` and `event`; runs kept as `evening` stay readable as history. | `runs` | kinds | Only `morning` and `manual` runs call the market steps | Implemented |
| SRD-DSK-003.014 | FO-DSK-003 | Must | When an employee's turn ends, the router posts a `step_done` event naming the employee, its trigger event and whether it gave a valid result. | employee result | `events` row | Takes the priority, data day and expiry of its trigger event; only the router posts it | Implemented |
| SRD-DSK-003.015 | FO-DSK-003 | Must | For one trigger event, the router wakes a listening employee once every employee it needs has a valid `step_done` for that event. | `events` | wake | Needs not woken by that event count as met; a loop in the needs keeps the chain asleep and is logged | Implemented |
| SRD-DSK-003.016 | FO-DSK-003 | Must | An employee with no valid result is woken again at most twice, 5 minutes apart, then its step is marked failed. | `step_done` row | retry or failed | Tries are kept in `desk.db`; retries skip the 30-minute gap and the once-per-data-day rule | Implemented |
| SRD-DSK-003.017 | FO-DSK-003 | Must | When a step has failed, employees that need it, directly or through others, are not woken and the chain stops there. | failed step | skips, log line | Each skipped employee is logged once | Implemented |
| SRD-DSK-003.018 | FO-DSK-003 | Must | When a chain stops, the employee at level `lead` still runs once and posts a short plan marked partial that lists the missing views. | stopped chain | partial plan | No partial plan when the lead's own step failed | Implemented |
| SRD-DSK-003.019 | FO-DSK-003 | Should | A chain cut off by closing the app carries on from its `step_done` rows at the next start while its trigger event has not expired. | `events` | resumed chain | Finished employees are not woken again | Implemented |
| SRD-DSK-003.020 | FO-DSK-003 | Must | On NYSE trading days the market clock posts `market_checkin` at 10:00, 12:30 and 15:30 New York time, once per time. | clock | events | P2; due only in the 30 minutes after each time, like the open and close events | Implemented |
| SRD-DSK-003.021 | FO-DSK-003 | Must | Each watcher flag is a `watch_flags` row and a `watch_flag` event for it. | flag | row, event | P0, deadline 5 min, expiry 30 min; one event per flag | Implemented |
| SRD-DSK-003.022 | FO-DSK-003 | Must | A flag for the same stock and flag kind within an hour of the last one is not stored again. | flag | skip | Once per stock, kind and New York hour | Implemented |
| SRD-DSK-003.023 | FO-DSK-003 | Must | While the desk runs in market hours and is not paused, it runs the watchers every 5 minutes. | clock | watcher pass | A failing watcher is logged; the others still run | Implemented |
| SRD-DSK-003.024 | FO-DSK-003 | Must | Each new flag adds a code-made feed note with the stock, flag kind and price. | flag | brief | Shown even when no AI answers | Implemented |
| SRD-DSK-003.025 | FO-DSK-003 | Should | Each watcher pass that finds flags logs how many and of which kinds. | pass | log line | `[Watch]` prefix | Implemented |

## FO-DSK-004: LLM Gateway and Budget Guard

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-DSK-004.001 | FO-DSK-004 | Must | Every model call goes through one gateway with two sources: OpenRouter and Claude Code CLI. | prompt, model | answer text, usage | 90 s time limit per call | Implemented |
| SRD-DSK-004.002 | FO-DSK-004 | Must | An answer must be JSON that matches the employee's output schema; a bad answer is retried once with the error, then the backup model is tried, then the step ends without output. | answer | typed result or none | Every try is recorded | Implemented |
| SRD-DSK-004.003 | FO-DSK-004 | Must | No call is made once this month's API spend reaches the desk budget or the employee's own monthly cap. | `activity` cost | allow or refuse | Default budget USD 10 per month; only OpenRouter (API) calls carry cost | Implemented |
| SRD-DSK-004.004 | FO-DSK-004 | Must | Claude Code CLI runs on the user's subscription: it is recorded with tokens and cost 0, and capped by tokens per day; per employee calls per day come from `job.yaml`. | `activity` tokens, count | allow or refuse | Default 200,000 CLI tokens per day | Implemented |
| SRD-DSK-004.005 | FO-DSK-004 | Must | Desk AI settings (sources on or off, models, budget, CLI token cap) are kept in `desk_ai.json` in the desk folder and the OpenRouter key in the Windows credential store. | settings | file, key | Separate from the AI notes settings | Implemented |
| SRD-DSK-004.006 | FO-DSK-004 | Must | Each employee has a daily token budget `tokens_per_day` in its employee file. | employee file | budget | Default 60,000 when missing; tokens in + out of all sources; the caps of SRD-DSK-004.003/.004 still apply | Implemented |
| SRD-DSK-004.007 | FO-DSK-004 | Must | The daily budget is split into three parts: plan 50%, market hours 20% and research 30%. | budget | three parts | Fixed split; unused tokens of one part never move to another | Implemented |
| SRD-DSK-004.008 | FO-DSK-004 | Must | A call counts against market hours when woken by a check-in or watcher flag, against research when it works a ticket, and against plan otherwise. | event, ticket | part | The part is kept on each `activity` row | Implemented |
| SRD-DSK-004.009 | FO-DSK-004 | Must | No call is made once its part is used up for the day; a ticket call is paid from the raising lead's research part, not the doer's. | `activity` tokens | allow or refuse | A refusal is handled like other budget refusals (SRD-DSK-003.018) | Implemented |
| SRD-DSK-004.010 | FO-DSK-004 | Should | A call refused for a used-up part logs the employee, the part and the tokens used. | refusal | log line | `[Budget]` prefix | Implemented |

## FO-DSK-005: Activity Recorder and Replay

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-DSK-005.001 | FO-DSK-005 | Must | Every gateway try is written to `activity` with run, employee, version, data day, source, model, prompt, answer, check result, error, tokens, cost and time. | try | `activity` row | — | Implemented |
| SRD-DSK-005.002 | FO-DSK-005 | Must | `activity` and `briefs` are append-only; the database refuses updates and deletes. | — | — | Database triggers | Implemented |
| SRD-DSK-005.003 | FO-DSK-005 | Must | Briefs for the AI feed are kept in `briefs` with time, data day, author, kind and text. | feed item | `briefs` row | — | Implemented |
| SRD-DSK-005.004 | FO-DSK-005 | Should | Each employee run logs the employee, model, result, cost and time. | run | log line | `[AI Desk]` prefix | Implemented |
| SRD-DSK-005.005 | FO-DSK-005 | Must | `desk replay <run>` sends the recorded prompts of that run again through the gateway, with the recorded model or one given by `--model`, for all employees or one given by `--employee`. | run id, options | answers | Budget and caps apply as for normal calls | Implemented |
| SRD-DSK-005.006 | FO-DSK-005 | Must | A replay writes its tries to `activity` marked as replay, and writes no views, picks, briefs or events. | replay | `activity` rows | Replay tries never count as a wake | Implemented |
| SRD-DSK-005.007 | FO-DSK-005 | Must | The replay report prints, per employee, whether the old and new answers pass the check and which typed fields differ. | answers | report text, exit code | ASCII only; exit 1 when the run is not found | Implemented |

## FO-DSK-006: Hiring Pipeline and Process Analytics

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-DSK-006.001 | FO-DSK-006 | Must | Starting a hire creates a new employee folder with the next free id, the chosen skill, level, name and model, and status `shadow`. | skill, level, name, model | employee folder | Soul copied from the skill's shipped default; the Master User may edit it later | Implemented |
| SRD-DSK-006.002 | FO-DSK-006 | Must | A hire is refused when the skill is unknown, the name is already used, or the level's seat cap is full. | request | reason | Active and shadow employees count against the cap | Implemented |
| SRD-DSK-006.003 | FO-DSK-006 | Must | Seat caps default to 8 experts, 5 champions and 30 juniors and are kept in the desk settings. | settings | caps | The lead level has no cap | Implemented |
| SRD-DSK-006.004 | FO-DSK-006 | Must | A shadow employee wakes with its skill's holder and gets the same facts, but its answer is only checked and recorded. | event, facts | `activity` rows marked shadow | The skill's act is never called, so no views, picks, briefs or events are written | Implemented |
| SRD-DSK-006.005 | FO-DSK-006 | Must | A shadow ends after 14 data days with a recorded shadow answer, and the hire becomes ready for a decision. | `activity` | hire state | A failed or missing answer still counts as a day only when the facts were fresh | Implemented |
| SRD-DSK-006.006 | FO-DSK-006 | Must | The shadow report gives, for the hire and the holder over the same days, the share of valid answers, tokens, cost and agreement. | `activity` | report rows | Agreement compares the short typed values of both valid answers on the same day; free text is left out | Implemented |
| SRD-DSK-006.007 | FO-DSK-006 | Must | A decision Replace, Add or Reject is kept in an append-only `approvals` table and applied to the employee files. | decision | `approvals` row, statuses | Replace retires the holder; Add only when the skill has no active holder; Reject retires the hire; no decision before ready | Implemented |
| SRD-DSK-006.008 | FO-DSK-006 | Must | A retired employee never wakes, and its records stay. | status | — | Status `active` is the default for files without one | Implemented |
| SRD-DSK-006.009 | FO-DSK-006 | Must | The first desk run on or after each Friday (New York) writes one weekly report by code: calls, valid share, tokens, cost and failures per employee, and shadow progress. | `activity`, employees | `desk_reports` row | No AI call; one report per week | Implemented |
| SRD-DSK-006.010 | FO-DSK-006 | Should | Starting a hire, the end of a shadow, each decision and each weekly report are logged. | event | log line | `[Hiring]` and `[Report]` prefixes | Implemented |

## FO-DSK-007: AI Problem Alerts

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-DSK-007.001 | FO-DSK-007 | Must | A failed model call whose error is a Claude login, OpenRouter key or credit problem raises an alert with a plain fix step. | call error | `alerts` row | Answers in the wrong form never raise one | Implemented |
| SRD-DSK-007.002 | FO-DSK-007 | Must | An alert is stored once per kind, source and New York day. | alert | row | Repeats the same day are dropped | Implemented |
| SRD-DSK-007.003 | FO-DSK-007 | Must | A new alert is sent to Telegram for the first user with Telegram on. | alert | message | A failed or off Telegram keeps the alert in the app | Implemented |
| SRD-DSK-007.004 | FO-DSK-007 | Must | After a source fails to sign in, the rest of that run skips it and uses the backup model. | run | calls | The next run tries the source again | Implemented |
| SRD-DSK-007.005 | FO-DSK-007 | Must | A morning or manual run whose employees made calls but gave no valid answer raises a whole-run alert. | run calls | alert | Holds the call count and last error; reopened 2026-11-10: wording only | Implemented |
| SRD-DSK-007.006 | FO-DSK-007 | Must | An alert stays open for a day until a later valid answer (same source for sign-in problems) closes it. | alerts, activity | open alerts | Read-only for the GUI | Implemented |
| SRD-DSK-007.007 | FO-DSK-007 | Must | A run stopped by the candle check raises a "Candles not up to date" alert with the number of stocks still behind. | check result | alert | Same once-per-day and Telegram rules; closed by the next run that passes the check | Implemented |
| SRD-DSK-007.008 | FO-DSK-007 | Must | A chain stopped by a failed step raises one "Desk plan is partial" alert naming the failed step and its last error. | failed step | alert | Same once-per-day and Telegram rules; closed by the next chain that finishes in full | Implemented |
| SRD-DSK-007.009 | FO-DSK-007 | Must | A stop or target touch on an open trade, or a plan judged broken, raises an alert with the stock and price. | flag, verdict | alert | Kinds `trade_stop`, `trade_target`, `plan_broken`; same once-per-day and Telegram rules | Implemented |
| SRD-DSK-007.010 | FO-DSK-007 | Must | A ticket that waits for the user's approval raises a "Research ticket waiting" alert with its goal and token cap. | ticket | alert | One alert per ticket; same Telegram rule; closed when the ticket is approved, rejected or expired | Implemented |

## FO-DSK-008: Employee File and Versions

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-DSK-008.001 | FO-DSK-008 | Must | An employee is one `employee.md`: YAML front matter with the job fields, body with the system prompt. | folder | job, prompt | Same fields and rules as `job.yaml` (SRD-DSK-002.002) | Implemented |
| SRD-DSK-008.002 | FO-DSK-008 | Must | The job rules and the employee file read and write live in `core`, used by the desk and the app. | file text | checked job | The app never imports `desk` | Implemented |
| SRD-DSK-008.003 | FO-DSK-008 | Must | A folder with `job.yaml` and `soul.md` but no `employee.md` is turned into `employee.md` once; the old files move to `history/`. | old folder | `employee.md` | Version unchanged; runs on desk load and Team setup open | Implemented |
| SRD-DSK-008.004 | FO-DSK-008 | Must | Shipped default employees are `employee.md` files, copied only when missing. | defaults | folders | Master user edits never overwritten | Implemented |
| SRD-DSK-008.005 | FO-DSK-008 | Must | Saving an employee checks it, raises the version by one and keeps the old file as `history/v<N>.md`. | job, prompt | new file | A wrong file is refused with the first reason; nothing written | Implemented |
| SRD-DSK-008.006 | FO-DSK-008 | Should | Restoring an old version saves its content as the next version. | version | new file | History is never deleted | Implemented |
| SRD-DSK-008.007 | FO-DSK-008 | Must | Starting a hire writes `employee.md` from the skill's default employee. | hire | `employee.md` | Status shadow, as today | Implemented |
| SRD-DSK-008.008 | FO-DSK-008 | Should | `desk replay RUN --employee ID --draft FILE` resends the employee's recorded question with the draft prompt. | draft file | answer, valid | Tries recorded as replay; no views, picks or briefs written | Implemented |
| SRD-DSK-008.009 | FO-DSK-008 | Must | A level change is refused when the new level's seats are full. | level | reason | Same caps as hiring (SRD-DSK-006.002) | Implemented |

## FO-DSK-009: Desk Memory — Lessons

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-DSK-009.001 | FO-DSK-009 | Must | Each lesson is a `lessons` row with id, text, tags, claim (better or worse), proof picks, cases, average R, confidence, status, made, last confirmed, pinned and author. | lesson | `lessons` row | Status is candidate, active or retired; author is desk or Master | Implemented |
| SRD-DSK-009.002 | FO-DSK-009 | Must | Code makes a candidate active when at least 5 closed picks match its tags and their average R is on its claimed side of the all-picks average. | `lessons`, pick results | status | A candidate not proved in 30 days is retired | Implemented |
| SRD-DSK-009.003 | FO-DSK-009 | Must | A new candidate with the same tags and claim as a kept lesson updates that lesson instead of adding a row. | candidate | updated row | Weekly merge of similar lessons comes later | Implemented |
| SRD-DSK-009.004 | FO-DSK-009 | Must | Each pick-making skill gets at most 5 active lessons whose tags match the day's ideas, pinned first, then by confidence. | `lessons`, ideas | lessons text | At most 800 tokens; the text says lessons may only make the answer stricter | Implemented |
| SRD-DSK-009.005 | FO-DSK-009 | Must | Lessons are prompt text only; risk limits, stop size, capital and approval code never read `lessons`. | — | — | Checked by a test | Implemented |
| SRD-DSK-009.006 | FO-DSK-009 | Must | The lessons shown to each skill on each data day are kept in `lesson_uses`. | shown lessons | `lesson_uses` rows | — | Implemented |
| SRD-DSK-009.007 | FO-DSK-009 | Must | An active lesson retires when 10 later matching picks shown it no longer back its claim, or when no new case backs it for 90 days. | `lessons`, `lesson_uses`, pick results | status | Pinned lessons never retire by themselves | Implemented |
| SRD-DSK-009.008 | FO-DSK-009 | Must | The Master's pin, unpin, edit text, retire and delete arrive as new `lesson_edits` rows that the desk applies at its next tick. | `lesson_edits` | `lessons` | The GUI writes only new rows; an edited lesson keeps its id and numbers | Implemented |
| SRD-DSK-009.009 | FO-DSK-009 | Should | A new candidate, a lesson made active and a retired lesson are each logged. | lesson | log line | `[Memory]` prefix | Implemented |

## FO-DSK-010: Research Queue

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-DSK-010.001 | FO-DSK-010 | Must | Each ticket is a `tickets` row with id, kind, topic, goal, done test, token cap, step cap, time cap, raised by, status, made, approved by, tokens spent, steps, result and end reason. | ticket | `tickets` row | Status is waiting, approved, running, paused, done, failed, stuck, rejected or expired | Implemented |
| SRD-DSK-010.002 | FO-DSK-010 | Must | Only lead-level employees may raise tickets, at most 3 a day each. | ticket | row or refusal | Level read from the employee file; no names in code | Implemented |
| SRD-DSK-010.003 | FO-DSK-010 | Must | A ticket with a token cap of 10,000 or less is approved by the desk at once; a bigger one waits for the user. | ticket | status | Approved by `auto` or `master`; book tickets always wait | Implemented |
| SRD-DSK-010.004 | FO-DSK-010 | Must | The Master's approve, reject and change of token cap arrive as new `ticket_edits` rows that the desk applies at its next tick. | `ticket_edits` | `tickets` | Same pattern as SRD-DSK-009.008; an approve may carry a new cap | Implemented |
| SRD-DSK-010.005 | FO-DSK-010 | Must | A waiting ticket not approved within 3 days expires. | `tickets` | status | — | Implemented |
| SRD-DSK-010.006 | FO-DSK-010 | Must | A ticket with the same kind and goal as a ticket done in the last 30 days is not added. | ticket | refusal | The raiser's next prompt shows the old result | Implemented |
| SRD-DSK-010.007 | FO-DSK-010 | Must | A topic with 3 ended tickets that gave no gain is parked for 30 days, and new tickets on it are refused. | `tickets` | parked topic | Gain is the yes/no the skill gives at the end | Implemented |
| SRD-DSK-010.008 | FO-DSK-010 | Must | The desk runs one approved ticket at a time, oldest first, only when no plan run is active and no watcher flag came in the last 20 minutes. | `tickets`, events | ticket run | Outside market hours and on weekends the app-open time counts as quiet | Implemented |
| SRD-DSK-010.009 | FO-DSK-010 | Must | A ticket is worked by the active employee whose skill handles its kind, one AI call per step. | ticket | steps | A kind with no such employee stays approved and is logged once a day | Implemented |
| SRD-DSK-010.010 | FO-DSK-010 | Must | A ticket ends as done or failed when its done test is met or clearly failed, and as done at its token, step or time cap with what it found. | step result | status, result | Token cap is hard: no step starts that may pass it | Implemented |
| SRD-DSK-010.011 | FO-DSK-010 | Must | A ticket ends as stuck after two steps with no new result, or the same tool call twice in a row. | steps | status | — | Implemented |
| SRD-DSK-010.012 | FO-DSK-010 | Must | A watcher flag, a plan run, a used-up research part or the app closing pauses the running ticket after its current step; it resumes at the next quiet gap. | events | status paused | Its state is saved in `tickets` | Implemented |
| SRD-DSK-010.013 | FO-DSK-010 | Must | An ended ticket posts a `research_done` event with its id, status and result. | ticket | event | — | Implemented |
| SRD-DSK-010.014 | FO-DSK-010 | Should | Raise, approve, start, pause and end of each ticket are logged. | ticket | log line | `[Research]` prefix | Implemented |
| SRD-DSK-010.015 | FO-DSK-010 | Must | A research skill may hand follow-up tickets to the queue in the name of the lead that raised its own ticket. | asks, ticket | ticket rows | Rules .002–.007 apply to that lead; never in the doer's name | Implemented |
| SRD-DSK-010.016 | FO-DSK-010 | Must | The Master user can raise a `strategy_test` ticket for one card from the app; it is approved at once and paid by the lead that holds the lead plan skill. | card id | ticket row | Rules .002 and .005–.007 apply; refused when no active lead | Implemented |

## FO-DSK-011: Agent Messages

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-DSK-011.001 | FO-DSK-011 | Must | Every message is one `desk.msg/1` envelope made of a core header, a body and optional meta, and belongs to one thread. | message | model | Pydantic v2 in `core/desk_msg.py`; the schema name is written only when it is not `desk.msg/1` | Implemented |
| SRD-DSK-011.002 | FO-DSK-011 | Must | A thread holds id, starter, message count, send-back rounds, state, opened and closed. | thread | model | Id is the first message id; starter is the payer; state is open or closed | Implemented |
| SRD-DSK-011.003 | FO-DSK-011 | Must | The core header holds id, thread, parent, type, sender, to and at, plus due and state. | header | model | Parent omitted on a first message; due only on ask, task, send_back, escalate and meeting | Implemented |
| SRD-DSK-011.004 | FO-DSK-011 | Must | An address is an employee id, `skill:<key>`, `champion:<key>`, `boss` or `master`. | address | valid or reason | Ids only, never names; a list only on meeting; omitted on reply and send_back | Implemented |
| SRD-DSK-011.005 | FO-DSK-011 | Must | The type is one of ask, task, reply, send_back, handover, escalate, meeting, decision and feedback, and it picks the body model. | type, body | body model | Each body refuses unknown keys | Implemented |
| SRD-DSK-011.006 | FO-DSK-011 | Must | Each type's body has the required and optional fields of the type table in the DD. | body | valid or reason | A missing required field is refused | Implemented |
| SRD-DSK-011.007 | FO-DSK-011 | Must | Body fields keep their size limits. | body | valid or reason | Subject 80 chars one line; text 600; about 20; flags 5 with note 120; reason 200 | Implemented |
| SRD-DSK-011.008 | FO-DSK-011 | Must | A want holds goal, done test, inputs and optional schema, columns, tools and token cap. | want | model | Goal and done test 120 chars each; tools only on task | Implemented |
| SRD-DSK-011.009 | FO-DSK-011 | Must | A verdict result is allowed only for its type. | verdict | valid or reason | reply: done, partial, failed, dropped, refused; send_back: fix, reject; decision: decided with agreed and disagreed | Implemented |
| SRD-DSK-011.010 | FO-DSK-011 | Must | A data block names a schema-library format and holds either rows as lists or a reference with a row count. | data | model | Rows at most 200; both or neither is refused; columns only for a subset | Implemented |
| SRD-DSK-011.011 | FO-DSK-011 | Must | Meta holds only ai, used, secs, blocked and schema, each written only when it has a value. | meta | JSON | Dump leaves out empty and default keys | Implemented |
| SRD-DSK-011.012 | FO-DSK-011 | Must | Message states are submitted, working, input_required, completed, failed, canceled, refused and expired. | state | enum | Names follow A2A | Implemented |
| SRD-DSK-011.013 | FO-DSK-011 | Must | The envelope and each body type export as JSON Schema. | — | JSON Schema | For prompts; matches what the models accept | Implemented |
| SRD-DSK-011.014 | FO-DSK-011 | Must | M0 adds the format only; no desk step, skill or table sends or stores messages. | — | — | Checked by the existing desk tests | Implemented |

## FO-DSK-012: Tools and Task Cards

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-DSK-012.001 | FO-DSK-012 | Must | Each tool is a `desk.tool/1` row with name, kind, version, description, input schema, output schema, ai and status. | tool | model | Pydantic v2 in `core/desk_registry.py`; kind is code or mcp; status is active or off | Implemented |
| SRD-DSK-012.002 | FO-DSK-012 | Must | Own tool names are `group.tool` and MCP tool names are `mcp:server/tool`; a versioned reference adds `@<version>`. | name | valid or reason | Lower case letters, digits and underscores only | Implemented |
| SRD-DSK-012.003 | FO-DSK-012 | Must | Each table format is a `desk.schema/1` row with id `<name>.v<N>`, title and columns. | format | model | Each column has a name, type and meaning; a change makes a new version | Implemented |
| SRD-DSK-012.004 | FO-DSK-012 | Must | Tools and formats are kept in `tools` and `schemas` tables in `desk.db`. | rows | tables | Key is name and version; created if missing | Implemented |
| SRD-DSK-012.005 | FO-DSK-012 | Must | Each desk step in the step list is a code tool `step.<key>`. | step list | tool rows | Read from `STEP_PATHS`; key from the class name | Implemented |
| SRD-DSK-012.006 | FO-DSK-012 | Must | Each research skill is an AI tool `research.<kind>`. | skill list | tool rows | Skills whose key is a research kind | Implemented |
| SRD-DSK-012.007 | FO-DSK-012 | Must | The data recipe is a code tool `data.recipe`, and each recipe source is a format `<source>.v1`. | recipe menu | tool and format rows | Input schema from the recipe model; columns from the menu | Implemented |
| SRD-DSK-012.008 | FO-DSK-012 | Must | Each Backtest MCP tool is an MCP tool `mcp:backtest/<tool>`. | MCP tool list | tool rows | Input schema from the MCP server's own tool list | Implemented |
| SRD-DSK-012.009 | FO-DSK-012 | Must | On each desk start the registry is filled from the lists above without copies. | lists | rows | A seeded tool no longer in code is set off, never deleted | Implemented |
| SRD-DSK-012.010 | FO-DSK-012 | Must | Read functions list tools and formats and get one by name. | name | rows | Read-only; used by the registry check and later phases | Implemented |
| SRD-DSK-012.011 | FO-DSK-012 | Should | Filling the registry is logged with the tool and format counts. | counts | log line | `[Tools]` prefix | Implemented |
