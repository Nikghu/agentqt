# Functional Overview — Desk Harness (DSK)

**Document ID:** FO-DSK
**Version:** 0.1.0
**Status:** Draft
**Last Updated:** 2026-11-05
**Project:** US Swing Trading System

> v0.2.0: FO-DSK-002–005 written in full as Draft for P5a (lean harness: registry, wake after run, gateway with budget, recorder); router, replay, Jev and HuggingFace later.
> v0.1.0: Tool created by architecture review. FO-DSK-001 written in full (phase P0a); FO-DSK-002–006 are outlines to be filled at their phase.

DSK is a general multi-agent "desk" harness. It runs as its own background process, wakes AI employees only on events or timers, records every step, and writes all output to `desk.db`. The market analytics tool (MKT) runs on top of it. Design source: https://claude.ai/artifact/FN2Q3279wCaZo7tQLKsK3E and https://claude.ai/artifact/1yGWa5z5e43bdPfZHU9K45.

---

## FO-DSK-001: Desk Process Shell

**Status:** Approved (user, 2026-11-05)
**Priority:** Must
**Phase:** P0a
**Depends on:** FO-INF-002 (candle data), Windows Task Scheduler pattern from FO-GUI-029

The system shall run the desk as a separate background process that the main app controls but does not host.

- The system shall start the desk as its own Windows task, so it runs even when the app is closed.
- The system shall keep all desk output in one SQLite file, `desk.db`, opened in WAL mode.
- The system shall let the app send commands (start, pause, resume, stop) only by writing rows to the `commands` table.
- The system shall show one of seven desk states: Running, Sleeping, Paused, Stopping, Stopped, Off, Error.
- The system shall save the last desk state on stop, so the Master User can resume it later.
- The system shall write a heartbeat, so the app can show Off or Error when the desk process is not alive.
- The system shall never block the app: the app only reads `desk.db` and writes `commands`.
- The system shall schedule the evening run after the US close (about 16:25 ET), using NY time inside the desk and IST for the Windows task.

## FO-DSK-002: Employee Registry and Job Descriptions

**Status:** Draft
**Priority:** Must
**Phase:** P5a (editing, rollback and HELM drafts in P6)
**Depends on:** FO-DSK-001

The system shall load each AI employee from two files written by people, and enforce the job file in code.

- The system shall keep each AI employee as a `soul.md` (mission, style, values) plus a `job.yaml` (triggers, output, models, call and cost caps, KPIs).
- The system shall check every `job.yaml` against a fixed schema and keep an employee with a bad file asleep.
- The system shall enforce `job.yaml` in code; it wins over `soul.md`, which is only the system prompt.
- The system shall keep the name, version and file hash of every loaded job description in `desk.db`.
- The system shall give agents no way to change job files.

### Acceptance Criteria

1. ATLAS loads from its two files; a broken `job.yaml` keeps it asleep with one clear log line.
2. `employees` in `desk.db` shows ATLAS with its version and hash.

## FO-DSK-003: Event Router, Market Clock and Wake Rules

**Status:** Draft
**Priority:** Must
**Phase:** P5a (wake after a desk run); P5b (events, priorities, deadlines, expiry, market clock)
**Depends on:** FO-DSK-001, FO-DSK-002

The system shall keep agents asleep and wake them only by rule. In P5a the only rule is "after the desk run".

- The system shall run a desk step "AI employees" after the market steps and wake each employee whose trigger is `after_run`.
- The system shall wake an employee at most once per data day.
- The system shall wake an employee only when its data is fresh.

### Acceptance Criteria

1. The evening run wakes ATLAS once; a second run on the same data day does not.
2. With stale data ATLAS stays asleep and the log says why.

## FO-DSK-004: LLM Gateway and Budget Guard

**Status:** Draft
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

**Status:** Draft
**Priority:** Must
**Phase:** P5a (recorder); P5b (sandbox replay)
**Depends on:** FO-DSK-004

The system shall record every agent step so any answer can be traced and checked later.

- The system shall record every agent step (employee, version, prompt, source, model, answer, check result, tokens, cost, time) in an append-only log.
- The system shall refuse any change to or deletion of a recorded step.

### Acceptance Criteria

1. One ATLAS run leaves its full prompt, answer, cost and time in `activity`.
2. An update or delete on `activity` fails.

## FO-DSK-006: Hiring Pipeline and Process Analytics

**Status:** Draft (outline)
**Priority:** Should
**Phase:** P6

- The system shall let HELM propose a new employee or process, which runs only after Master User approval.
- The system shall cap seats at 3 experts, 5 champions and 30 juniors; the Master User can raise a cap.
- The system shall run a new employee in shadow mode for two weeks before a second approval.
- The system shall let LEDGER report workload, cost and process-improvement ideas.
