# Software Requirements — Desk Harness (DSK)

**Document ID:** SRD-DSK
**Version:** 0.3.0
**Status:** Draft
**Last Updated:** 2026-11-06
**Project:** US Swing Trading System

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
| SRD-DSK-001.013 | FO-DSK-001 | Must | A desk started by the Windows task exits at once when the saved state is Stopped. | saved state | exit | Only `start` clears Stopped | Implemented |
| SRD-DSK-001.014 | FO-DSK-001 | Must | On start, a run with no end time is marked interrupted and run again. | `runs` | new run | — | Implemented |
| SRD-DSK-001.015 | FO-DSK-001 | Must | The evening run is due on weekdays at 16:25 New York time and is caught up once if missed that day. | clock, last run | due flag | Pure function, clock passed in | Implemented |
| SRD-DSK-001.016 | FO-DSK-001 | Must | Each run is a `runs` row (kind, start, end, result, note) and calls the registered desk steps in order. | steps | row | Zero steps in P0a gives result ok | Implemented |
| SRD-DSK-001.017 | FO-DSK-001 | Must | A failed step ends the run as failed and sets Error with a short message; the next good run sets Sleeping. | exception | state | Process keeps running | Implemented |
| SRD-DSK-001.018 | FO-DSK-001 | Must | Install creates two Windows tasks: one at logon and one 5 minutes before each weekday evening run, set in local time and local days. | exe path | tasks | No console window | Implemented |
| SRD-DSK-001.019 | FO-DSK-001 | Should | Each desk start re-checks the evening task time and updates it after a US or local clock change. | clock | task | Skipped when not installed | Implemented |
| SRD-DSK-001.020 | FO-DSK-001 | Must | `python -m us_swing desk` runs the desk; `desk start/status/pause/resume/stop/run-now/install/uninstall` control it. | argv | exit code, text | `start` launches a detached process | Implemented |
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
| SRD-DSK-003.010 | FO-DSK-003 | Must | The employees woken by one event run as one LangGraph graph; an employee runs after the employees whose skills its skill needs. | woken employees, needs | run order | A loop in the needs keeps the whole graph asleep and is logged | Implemented |
| SRD-DSK-003.011 | FO-DSK-003 | Must | A failed or sleeping employee never stops the graph; those that need its view still run and their facts say the view is missing. | node result | facts note | — | Implemented |
| SRD-DSK-003.012 | FO-DSK-003 | Must | `langgraph` is a desk dependency and the installer bundles it for the frozen desk. | — | package | Only `desk` imports it | Implemented |

## FO-DSK-004: LLM Gateway and Budget Guard

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-DSK-004.001 | FO-DSK-004 | Must | Every model call goes through one gateway with two sources: OpenRouter and Claude Code CLI. | prompt, model | answer text, usage | 90 s time limit per call | Implemented |
| SRD-DSK-004.002 | FO-DSK-004 | Must | An answer must be JSON that matches the employee's output schema; a bad answer is retried once with the error, then the backup model is tried, then the step ends without output. | answer | typed result or none | Every try is recorded | Implemented |
| SRD-DSK-004.003 | FO-DSK-004 | Must | No call is made once this month's API spend reaches the desk budget or the employee's own monthly cap. | `activity` cost | allow or refuse | Default budget USD 10 per month; only OpenRouter (API) calls carry cost | Implemented |
| SRD-DSK-004.004 | FO-DSK-004 | Must | Claude Code CLI runs on the user's subscription: it is recorded with tokens and cost 0, and capped by tokens per day; per employee calls per day come from `job.yaml`. | `activity` tokens, count | allow or refuse | Default 200,000 CLI tokens per day | Implemented |
| SRD-DSK-004.005 | FO-DSK-004 | Must | Desk AI settings (sources on or off, models, budget, CLI token cap) are kept in `desk_ai.json` in the desk folder and the OpenRouter key in the Windows credential store. | settings | file, key | Separate from the AI notes settings | Implemented |

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
