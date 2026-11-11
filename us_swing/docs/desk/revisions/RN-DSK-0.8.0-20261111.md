# Revision Note — RN-DSK-0.8.0-20261111

**Version:** 0.8.0
**Date:** 2026-11-11
**Tool:** DSK
**Artifact:** FO-DSK-003, FO-DSK-007 / SRD-DSK-003.010–.012, SRD-DSK-003.014–.019, SRD-DSK-007.008
**Type:** Feature

---

## Summary

Step B of the autonomous desk: the AI employees now pass the work on by `step_done` events, and the router wakes the next employee when its needs are met. A failed step gets 2 retries, 5 minutes apart; after that the steps that need it are skipped and the lead writes a short "Partial plan" note, with one alert per failed step per day. LangGraph is removed from the desk, so the installer is smaller.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-DSK-003.006.M16 | `src/us_swing/desk/router.py` | Baton: `step_done` events, retries, skips and the lead's partial run; LangGraph removed |
| MD-DSK-003.004.M15 | `src/us_swing/core/desk_events.py` | Adds `steps` table, `parent` and `due` columns on `events`, `post_step_done()` |
| MD-DSK-003.001.M10 | `src/us_swing/desk/employees_step.py` | Reports each turn end so the router can post `step_done` |
| MD-DSK-007.001.M21 | `src/us_swing/core/desk_alerts.py` | "Desk plan is partial" alert, once per failed step per day |
| — | `pyproject.toml` | `langgraph` dependency removed |
| — | `USSwing.spec` | `langgraph` and `langchain_core` removed from hidden imports |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-DSK-003.010 | Employees woken by one event run one at a time, in needs order | Implemented |
| SRD-DSK-003.011 | A sleeping employee does not stop the chain; its dependants see the view as missing | Implemented |
| SRD-DSK-003.012 | The desk does not use `langgraph`; it is removed from the dependencies and the installer | Implemented |
| SRD-DSK-003.014 | An employee's turn end posts a `step_done` event | Implemented |
| SRD-DSK-003.015 | The router wakes a listening employee once all its needs have a valid `step_done` | Implemented |
| SRD-DSK-003.016 | A failed employee is retried at most 2 times, 5 minutes apart, then its step is failed | Implemented |
| SRD-DSK-003.017 | After a failed step, its dependants are not woken and the chain stops | Implemented |
| SRD-DSK-003.018 | The lead runs once more and writes a plan marked partial | Implemented |
| SRD-DSK-003.019 | A chain cut off by closing the app carries on at the next start | Implemented |
| SRD-DSK-007.008 | A stopped chain raises one "Desk plan is partial" alert | Implemented |

---

## Design Decisions

- The chain moves by `step_done` events, not by one LangGraph graph. The run order check uses `graphlib` from the standard library.
- A step still "running" at restart counts as a failed try.
- A budget refusal counts as "slept", so the chain does not stop (user kept the default).
- The partial-plan alert is closed by the next chain that finishes in full.

---

## Issues Resolved

None

---

## Test Coverage

Step B UTCD cases: UT-DSK-003.010.M16.T01–T04, UT-DSK-003.011.M16.T01–T03, UT-DSK-003.012.M16.T01–T02, UT-DSK-003.014.M15.T01–T04, UT-DSK-003.014.M16.T01, UT-DSK-003.014.M10.T01, UT-DSK-003.015.M16.T01–T04, UT-DSK-003.016.M16.T01–T04, UT-DSK-003.017.M16.T01–T02, UT-DSK-003.018.M16.T01–T03, UT-DSK-003.018.M10.T01, UT-DSK-003.019.M16.T01–T03, UT-DSK-007.008.M21.T01–T03. Total 35, all Pass. Desk suite: 254 passed. Full suite: 12 failed, the same as before (TODO T112), plus a collection error in `tests/screener/test_llm_claude_screener.py` (missing module, TODO T136).
