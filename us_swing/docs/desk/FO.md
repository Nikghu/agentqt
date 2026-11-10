# Functional Overview â€” Desk Harness (DSK)

**Document ID:** FO-DSK
**Version:** 0.2.0
**Status:** Draft
**Last Updated:** 2026-11-06
**Project:** US Swing Trading System

> v0.6.0: Autonomous desk step A (user, 2026-11-10): FO-DSK-001 desk runs only while the app is open and runs in the morning (no evening run); FO-DSK-003 morning run by event; FO-DSK-007 candles alert. Older acceptance lines that say "evening run" describe the run in place when they were written.
> v0.5.0: FO-DSK-008 Implemented (user approved 2026-11-10; code and tests done).
> v0.4.0: FO-DSK-008 added as Draft — one employee.md file, versions and draft test (user, 2026-11-10).
> v0.3.0: FO-DSK-006 written in full as Draft for P6 (Master-started hires, 14-evening shadow, seat caps 8/5/30, weekly code report); no employee names.
> v0.2.1: FO-DSK-002 adds employee identity as data and generic levels; no employee names (user, 2026-11-06).
> v0.2.0: FO-DSK-002â€“005 written in full as Draft for P5a (lean harness: registry, wake after run, gateway with budget, recorder); router, replay, Jev and HuggingFace later.
> v0.1.0: Tool created by architecture review. FO-DSK-001 written in full (phase P0a); FO-DSK-002â€“006 are outlines to be filled at their phase.

DSK is a general multi-agent "desk" harness. It runs as its own background process, wakes AI employees only on events or timers, records every step, and writes all output to `desk.db`. The market analytics tool (MKT) runs on top of it. Design source: https://claude.ai/artifact/FN2Q3279wCaZo7tQLKsK3E and https://claude.ai/artifact/1yGWa5z5e43bdPfZHU9K45.

---

## FO-DSK-001: Desk Process Shell

**Status:** Approved (user, 2026-11-05)
**Priority:** Must
**Phase:** P0a
**Depends on:** FO-INF-002 (candle data), Windows Task Scheduler pattern from FO-GUI-029

The system shall run the desk as a separate background process that the main app controls but does not host.

- The system shall start the desk when the app opens and stop it when the app closes; the desk runs only while the app is open, weekends too (user, 2026-11-10; replaces "own Windows task").
- The system shall keep all desk output in one SQLite file, `desk.db`, opened in WAL mode.
- The system shall let the app send commands (start, pause, resume, stop) only by writing rows to the `commands` table.
- The system shall show one of seven desk states: Running, Sleeping, Paused, Stopping, Stopped, Off, Error.
- The system shall save the last desk state on stop, so the Master User can resume it later.
- The system shall write a heartbeat, so the app can show Off or Error when the desk process is not alive.
- The system shall never block the app: the app only reads `desk.db` and writes `commands`.
- The system shall run the day's market steps and AI employees once per trading day in the morning, from pre-market (04:00 ET), using NY time inside the desk; there is no evening run (user, 2026-11-10).

## FO-DSK-002: Employee Registry and Job Descriptions

**Status:** Implemented for P5a (approved by user 2026-11-06)
**Priority:** Must
**Phase:** P5a (editing, rollback and lead drafts in P6)
**Depends on:** FO-DSK-001

The system shall load each AI employee from two files written by people, and enforce the job file in code.

- The system shall keep each AI employee as a `soul.md` (mission, style, values) plus a `job.yaml` (id, name, title, level, reporting line, skill, trigger, models, call and cost caps, KPIs).
- The system shall treat name, title, level and reporting line as data the Master user can change at any time; code knows only skills and generic levels (lead, expert, champion, junior).
- The system shall keep employee files in the desk folder and add shipped defaults only when missing, never overwriting them.
- The system shall check every `job.yaml` against a fixed schema and keep an employee with a bad file asleep.
- The system shall enforce `job.yaml` in code; it wins over `soul.md`, which is only the system prompt.
- The system shall keep the name, version and file hash of every loaded job description in `desk.db`.
- The system shall give agents no way to change job files.

### Acceptance Criteria

1. The default regime view employee loads from its two files; a broken `job.yaml` keeps it asleep with one clear log line.
2. `roster` in `desk.db` shows the employee's id, name, level, skill, version and hash.
3. Renaming an employee or changing its level or boss in `job.yaml` needs no code change.

## FO-DSK-003: Event Router, Market Clock and Wake Rules

**Status:** Implemented for P5a (approved by user 2026-11-06); P5b part Implemented (approved by user 2026-11-06)
**Priority:** Must
**Phase:** P5a (wake after a desk run); P5b (events, priorities, deadlines, expiry, market clock, LangGraph)
**Depends on:** FO-DSK-001, FO-DSK-002

The system shall keep agents asleep and wake them only by rule. In P5a the only rule is "after the desk run"; P5b adds events and a market clock.

- The system shall run a desk step "AI employees" after the market steps and wake each employee whose trigger is `after_run`.
- The system shall wake an employee at most once per data day.
- The system shall wake an employee only when its data is fresh.
- The system shall route wake-ups as events with a kind, a priority (P0 to P2), a deadline and an expiry.
- The system shall handle events by priority, drop expired events and log late ones.
- The system shall post market open and close events from a market clock on NYSE trading days.
- The system shall not wake the same employee again within 30 minutes, except for P0 events.
- The system shall run the employees woken by one event as one LangGraph graph, where a skill runs after the skills whose views it needs.
- The system shall start the morning run by event, not by a fixed clock: the app is open, the market day has reached pre-market, and the candles are checked; a run that fails is tried again later the same day (Autonomous desk step A, user 2026-11-10).

### Acceptance Criteria

1. The morning run wakes the regime view employee once; a second run on the same data day does not.
2. With stale data the employee stays asleep and the log says why.
3. A P0 event is handled before waiting P1 and P2 events; an expired event is not handled and the log says so.
4. A second wake of the same employee within 30 minutes is refused unless the event is P0.
5. In the morning run the lead runs last; when one expert fails, the others still run and the lead's facts say which view is missing.

## FO-DSK-004: LLM Gateway and Budget Guard

**Status:** Implemented for P5a (approved by user 2026-11-06)
**Priority:** Must
**Phase:** P5a (OpenRouter, Claude Code CLI); later (HuggingFace, TypeSafe Jev)
**Depends on:** FO-DSK-002

The system shall send every model call through one gateway that checks the answer and the spend.

- The system shall call models through one gateway with two sources in P5a: OpenRouter and Claude Code CLI.
- The system shall keep desk AI settings separate from the AI notes settings: sources, models, backup, budget and caps.
- The system shall check every answer against the employee's output schema, retry once, then try the backup model.
- The system shall make no call once the monthly budget (start: USD 10) or the employee's own cap is used up.
- The system shall cap Claude Code CLI calls per day, because their cost is not reported.

### Acceptance Criteria

1. A bad answer is retried once and then sent to the backup model; both tries are recorded.
2. With the budget used up, no call is made and the log says so.

## FO-DSK-005: Activity Recorder and Replay

**Status:** Implemented for P5a (approved by user 2026-11-06); P5b part Implemented (approved by user 2026-11-06)
**Priority:** Must
**Phase:** P5a (recorder); P5b (sandbox replay)
**Depends on:** FO-DSK-004

The system shall record every agent step so any answer can be traced and checked later.

- The system shall record every agent step (employee, version, prompt, source, model, answer, check result, tokens, cost, time) in an append-only log.
- The system shall refuse any change to or deletion of a recorded step.
- The system shall replay a recorded run in a sandbox: send the same prompts again, with the same or another model, and compare the answers.
- The system shall keep a replay away from the real views, picks and AI feed.

### Acceptance Criteria

1. One regime view run leaves its full prompt, answer, tokens, cost and time in `activity`.
2. An update or delete on `activity` fails.
3. `desk replay <run>` re-sends the run's prompts and prints, per employee, whether the new answer passes the check and how it differs.
4. After a replay, the views, picks and AI feed are unchanged.

## FO-DSK-006: Hiring Pipeline and Process Analytics

**Status:** Implemented (approved by user 2026-11-06)
**Priority:** Should
**Phase:** P6
**Depends on:** FO-DSK-002–005, FO-GUI-034

The system shall let the Master User try a new employee safely before it does real work, and show each week how the desk works and what it costs. A new hire always uses a skill the code already knows; its name, level, model and soul are data the Master User controls. No AI proposes hires, and the weekly report is made by code with no AI cost.

- The system shall let the Master User start a hire by choosing an existing skill, a level, a name and a model.
- The system shall cap seats at 8 experts, 5 champions and 30 juniors, counting shadow hires; the Master User can change a cap in Desk settings.
- The system shall run a new hire in shadow for 14 evenings: it answers the same facts as the skill's current holder, but its answers never reach the views, picks or AI feed.
- The system shall compare each shadow hire with the current holder by valid answers, tokens, cost and agreement.
- The system shall let the Master User replace the holder, add the hire, or reject it once the shadow ends, and keep a record of every decision.
- The system shall make a weekly process and cost report by code (workload, cost, failures and shadow results) and show it in AI Desk.

### Acceptance Criteria

1. A hire started in AI Desk → Hiring is refused when its level's seat cap is full.
2. During shadow, the hire's answers are recorded but the views, picks and AI feed show only the holder's work.
3. After 14 evenings the shadow report shows valid answers, tokens, cost and agreement for the hire and the holder.
4. One shadow hire goes end to end: started, 14 evenings, approved as Replace; from the next evening only the new hire does the work.
5. Every Friday a weekly report appears in AI Desk → Reports with no AI call.

## FO-DSK-007: AI Problem Alerts

**Status:** Implemented (approved by user 2026-11-10)
**Priority:** Must
**Depends on:** FO-DSK-004 (gateway), FO-INF-010 (Telegram), FO-GUI-035 (Team at work)
**Source:** User 2026-11-10: the evening run of 2026-11-09 failed for every employee because the Claude login expired, and nobody was told. User chose app + Telegram, login/key and whole-run problems, and skip to the backup.

The system shall tell the Master User when the AI desk hits a problem only the user can fix.

- The system shall spot a Claude login, OpenRouter key or AI credit problem in a model call.
- The system shall raise one alert per problem per day, in the app and on Telegram.
- The system shall stop trying a source that could not sign in for the rest of that run and use the backup model.
- The system shall raise an alert when no employee of a run gave a valid answer.
- The system shall raise an alert when the morning run stops because the candles are not up to date (user, 2026-11-10).
- The system shall close an alert in the app once the problem is fixed.

### Acceptance Criteria

1. With the Claude login expired, the next evening run sends one Telegram message and shows a red banner and an AI feed card with the fix.
2. In that run each later employee goes straight to OpenRouter when it is on.
3. After `claude auth login` and one valid Claude answer, the banner and card are gone.

## FO-DSK-008: Employee File and Versions

**Status:** Implemented
**Priority:** Must
**Depends on:** FO-DSK-002 (registry), FO-DSK-005 (replay), FO-DSK-006 (hiring)
**Source:** User 2026-11-10: edit each AI employee in a Team setup tab; all details in one .md file; new hires added by themselves. Design: https://claude.ai/artifact/CSVvoYH32gNQzivr8L9bbE (Option 1).

The system shall keep each AI employee in one readable file that the Master user can change safely.

- The system shall keep each employee in one `employee.md`: settings at the top, system prompt below.
- The system shall move an employee kept as `job.yaml` and `soul.md` into `employee.md` once, by itself, losing nothing.
- The system shall check an employee file with one set of rules shared by the desk and the app.
- The system shall keep every earlier version of an employee file and let the Master user bring one back.
- The system shall give each new hire its own `employee.md`.
- The system shall try a changed prompt on the employee's last recorded run without saving it.

### Acceptance Criteria

1. After the update every employee folder has `employee.md`, the old files sit in `history/`, and the evening run works as before.
2. Saving a change raises the version, keeps the old file, and the next wake uses the new prompt.
3. A file with a wrong value is refused with a plain reason, and the employee stays as it was.
4. A new hire's folder holds `employee.md`.
