# Functional Overview — Desk Harness (DSK)

**Document ID:** FO-DSK
**Version:** 0.1.0
**Status:** Draft
**Last Updated:** 2026-11-05
**Project:** US Swing Trading System

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

**Status:** Draft (outline)
**Priority:** Must
**Phase:** P5a

- The system shall keep each AI employee as a `soul.md` (mission, style, values) plus a `job.yaml` (triggers, inputs, output schema, tools, models, cost cap, KPIs).
- The system shall enforce `job.yaml` in code; it wins over `soul.md`.
- The system shall version job descriptions, allow rollback, and never let an agent edit its own.

## FO-DSK-003: Event Router, Market Clock and Wake Rules

**Status:** Draft (outline)
**Priority:** Must
**Phase:** P5a

- The system shall keep agents asleep and wake them only on events or timers.
- The system shall give every event a market phase, priority (P0–P2), deadline and expiry.
- The system shall not wake the same agent twice for the same event within 30 minutes, and shall check data freshness first.

## FO-DSK-004: LLM Gateway and Budget Guard

**Status:** Draft (outline)
**Priority:** Must
**Phase:** P5a

- The system shall call models through one gateway: OpenRouter (main), Claude Code CLI (rare heavy jobs), HuggingFace (special models as tools).
- The system shall check every answer against its output schema, retry once, then use a backup model.
- The system shall stop AI calls when the daily or monthly budget is used up.

## FO-DSK-005: Activity Recorder and Replay

**Status:** Draft (outline)
**Priority:** Must
**Phase:** P5a

- The system shall record every agent step (input, prompt, model, output, tokens, cost, time) in an append-only log.
- The system shall replay a recorded run in a sandbox for debugging.

## FO-DSK-006: Hiring Pipeline and Process Analytics

**Status:** Draft (outline)
**Priority:** Should
**Phase:** P6

- The system shall let HELM propose a new employee or process, which runs only after Master User approval.
- The system shall run a new employee in shadow mode for two weeks before a second approval.
- The system shall let LEDGER report workload, cost and process-improvement ideas.
