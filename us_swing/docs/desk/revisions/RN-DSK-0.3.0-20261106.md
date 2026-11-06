# Revision Note — RN-DSK-0.3.0-20261106

**Version:** 0.3.0
**Date:** 2026-11-06
**Tool:** DSK
**Artifact:** FO-DSK-002, FO-DSK-003, FO-DSK-005 / SRD-DSK-002.008–.009, SRD-DSK-003.004–.012, SRD-DSK-005.005–.007
**Type:** Feature

---

## Summary

P5b desk: events, the router and replay. Tools and the desk post events with `post_event()` (`core/desk_events.py`). Each event has a kind, a priority (P0 to P2), a deadline and an expiry. The router (`desk/router.py`) handles waiting events by priority, marks late and expired ones, and does not wake an employee again within 30 minutes of its last wake (P0 excepted). The woken employees run as one LangGraph graph, in the order their skills' `needs` set. The market clock posts `market_open` and `market_close` on NYSE trading days. `desk replay <run>` re-sends a recorded run through a replay gateway; replay tries are not counted in the live calls per day.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-DSK-003.004.M15 | `us_swing/src/us_swing/core/desk_events.py` | New: `events` table, event kinds and priority, deadline and expiry rules, `post_event()` |
| MD-DSK-003.006.M16 | `us_swing/src/us_swing/desk/router.py` | New: expire, order and handle events; 30-minute rule; LangGraph run order |
| MD-DSK-005.005.M17 | `us_swing/src/us_swing/desk/replay.py` | New: `desk replay` re-sends recorded prompts and reports old and new checks |
| MD-DSK-002.001.M08 | `us_swing/src/us_swing/core/desk_agents.py` | Changed: `needs` added to the Skill protocol; feed kind `evening` |
| MD-DSK-002.002.M09 | `us_swing/src/us_swing/desk/registry.py` | Changed: `trigger` may be a list of event kinds; an unknown kind keeps the employee asleep |
| MD-DSK-003.001.M10 | `us_swing/src/us_swing/desk/employees_step.py` | Changed: posts `after_run`, then calls the router |
| MD-DSK-001.015.M03 | `us_swing/src/us_swing/desk/clock.py` | Changed: `market_events_due()` for 09:30 and 16:00 New York time on NYSE trading days |
| MD-DSK-001.010.M04 | `us_swing/src/us_swing/desk/process.py` | Changed: posts due clock events each tick; starts an `event` run when the router has work |
| MD-DSK-004.001.M11 | `us_swing/src/us_swing/desk/gateway.py` | Changed: `ReplayGateway` subclass (one retry; replay tries marked) |
| MD-DSK-005.001.M14 | `us_swing/src/us_swing/desk/recorder.py` | Changed: `replay` column on `activity`; `last_wake()` ignores replay tries |
| MD-DSK-001.020.M06 | `us_swing/src/us_swing/desk/cli.py` | Changed: `desk replay <run> [--employee] [--model]` |
| MD-MKT-001.011.M05 | `us_swing/src/us_swing/market/step.py` | Cross-tool: regime step posts `regime_change` through `core/desk_events.py` |
| — | `pyproject.toml` | `langgraph>=1.2,<2` dependency |
| — | `us_swing/USSwing.spec` | `langgraph` and `langchain_core` added to `collect_submodules` for the frozen desk |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-DSK-002.008 | Each skill names the skill keys whose views it needs; by function only. | Implemented |
| SRD-DSK-002.009 | `trigger` in `job.yaml` may be one event kind or a list. | Implemented |
| SRD-DSK-003.004 | Events kept in `events` with kind, priority, data day, deadline, expiry and state. | Implemented |
| SRD-DSK-003.005 | Kinds: `after_run` (P1), `regime_change` (P0), `market_open` and `market_close` (P2). | Implemented |
| SRD-DSK-003.006 | The router handles waiting events by priority, then by created time. | Implemented |
| SRD-DSK-003.007 | Past expiry: expired and not handled. Past deadline: late. Both logged. | Implemented |
| SRD-DSK-003.008 | Market clock posts `market_open` at 09:30 and `market_close` at 16:00 New York time, once per day. | Implemented |
| SRD-DSK-003.009 | No second wake within 30 minutes of the last wake, except by P0. | Implemented |
| SRD-DSK-003.010 | Employees woken by one event run as one LangGraph graph; an employee runs after the ones its skill needs. | Implemented |
| SRD-DSK-003.011 | A failed or sleeping employee never stops the graph; dependants note the missing view. | Implemented |
| SRD-DSK-003.012 | `langgraph` is a desk dependency; only `desk` imports it; the frozen build bundles it. | Implemented |
| SRD-DSK-005.005 | `desk replay <run>` re-sends recorded prompts, with the recorded or given model, for all or one employee. | Implemented |
| SRD-DSK-005.006 | Replay tries are marked as replay; no views, picks, briefs or events are written. | Implemented |
| SRD-DSK-005.007 | Replay report per employee: old and new pass the check, and which fields differ. ASCII; exit 1 when the run is not found. | Implemented |

---

## Design Decisions

- Skills name the views they need by function only (`needs`). Run order never uses `reports_to` or employee names.
- Repeat posts are ignored: clock and regime events once per kind per data day; `after_run` once per run. The P5a rule (one brief per data day) still stops a second wake.
- Each LangGraph node opens its own recorder and gateway, because a `sqlite3` connection must stay on its own thread. `max_concurrency: 1` keeps one model call at a time.
- LangSmith tracing is off (`LANGSMITH_TRACING=false`), so nothing leaves the PC.
- Skills get only the normal gateway, so a skill cannot pick its own system prompt. Only replay uses `ReplayGateway`.
- After code review (DD-DSK-003.004.D01):
  - A graph error (outside a node) is logged and the event is closed with the note `failed`.
  - An event skipped for a loop in `needs` is closed with the note `loop in needs`.
  - The desk loop logs and carries on when the event check itself fails.
  - Clock events are due only in the 30 minutes after 09:30 or 16:00, so a late start posts no stale event.
  - Replay tries do not count in the live calls-per-day quota; their cost and CLI tokens still count.
  - Replay splits the recorded prompt at the last separator, so a `soul.md` with `---` lines is safe.
  - Two employees with the same skill never wait for each other.

---

## Issues Resolved

None

---

## Test Coverage

- UTCD P5b rows for FO-DSK-002, -003 and -005: 48 in `docs/desk/UTCD.md`, all Pass.
- P5b overall (desk and market): 76 UTCD cases plus 10 extra, all Pass.
- Full suite: 2236 passed, 12 failed (the same old failures, T112), 2 skipped.
- Coverage of new modules 86–100% (total 95%).
- `langgraph` imports with tracing off (UT-DSK-003.012.M16.T01).
