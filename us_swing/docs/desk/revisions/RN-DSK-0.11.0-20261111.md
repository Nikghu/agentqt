# Revision Note — RN-DSK-0.11.0-20261111

**Version:** 0.11.0
**Date:** 2026-11-11
**Tool:** DSK
**Artifact:** FO-DSK-004, FO-DSK-007, FO-DSK-010 / SRD-DSK-004.006–.010, SRD-DSK-007.010, SRD-DSK-010.001–.014
**Type:** Feature

---

## Summary

Step E of the autonomous desk: each employee now has a daily token budget, split into plan (50%), market hours (20%) and research (30%) parts. Lead employees can raise research tickets, which wait for the Master user or are approved by the desk if small. An approved ticket is worked in quiet time, one AI step per desk tick, and stops at its token, step or time cap.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-DSK-010.001.M25 | `src/us_swing/core/desk_research.py` | New: ticket table rules, raise, auto approval, expiry, repeat and parked-topic checks, research block, Master edits, pause, lead research line |
| MD-DSK-010.008.M26 | `src/us_swing/desk/research.py` | New: research runner; one step per quiet tick, doer by skill kind, caps, stuck and done checks, `research_done` event |
| MD-DSK-004.003.M12 | `src/us_swing/desk/budget.py` | Changed: daily budget split 50/20/30 into plan, market and research parts; ticket calls paid by the raiser; `[Budget]` log on refusal |
| MD-DSK-005.001.M14 | `src/us_swing/desk/recorder.py` | Changed: `part`, `payer` and `ticket` columns on `activity` rows; part and ticket totals |
| MD-DSK-004.001.M11 | `src/us_swing/desk/gateway.py` | Changed: each try is paid from its budget part; a ticket try stops at the ticket cap |
| MD-DSK-003.001.M10 | `src/us_swing/desk/employees_step.py` | Changed: market part for check-in and watcher wakes, plan part otherwise |
| MD-DSK-001.010.M04 | `src/us_swing/desk/process.py` | Changed: applies ticket edits and expiry each tick; pauses running tickets at start; runs research when quiet; queue errors back off |
| MD-DSK-001.020.M06 | `src/us_swing/desk/cli.py` | Changed: passes the research runner to the desk loop |
| MD-DSK-008.001.M22 | `src/us_swing/core/desk_employee.py` | Changed: `tokens_per_day` field in the employee file, default 60,000 |
| MD-DSK-003.004.M15 | `src/us_swing/core/desk_events.py` | Changed: `research_done` event rule |
| MD-DSK-007.001.M21 | `src/us_swing/core/desk_alerts.py` | Changed: Research ticket waiting alert |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-DSK-004.006 | Each employee has a daily token budget `tokens_per_day` in its employee file (default 60,000) | Implemented |
| SRD-DSK-004.007 | The daily budget is split into plan 50%, market hours 20% and research 30%; unused tokens never move | Implemented |
| SRD-DSK-004.008 | A call is paid from market hours when woken by a check-in or watcher flag, from research when it works a ticket, otherwise from plan | Implemented |
| SRD-DSK-004.009 | No call once its part is used up; a ticket call is paid from the raising lead's research part | Implemented |
| SRD-DSK-004.010 | A call refused for a used-up part logs the employee, the part and the tokens used | Implemented |
| SRD-DSK-007.010 | A ticket waiting for the user's approval raises a "Research ticket waiting" alert with its goal and token cap | Implemented |
| SRD-DSK-010.001 | Each ticket is a `tickets` row with its goal, done test, caps, raiser, status, approver, spend, steps and result | Implemented |
| SRD-DSK-010.002 | Only lead-level employees raise tickets, at most 3 a day each | Implemented |
| SRD-DSK-010.003 | A ticket with a token cap of 10,000 or less is approved by the desk at once; a bigger one, or any book ticket, waits | Implemented |
| SRD-DSK-010.004 | Master approve, reject and cap changes arrive as `ticket_edits` rows applied at the next desk tick | Implemented |
| SRD-DSK-010.005 | A waiting ticket not approved within 3 days expires | Implemented |
| SRD-DSK-010.006 | A ticket with the same kind and goal as one done in the last 30 days is refused | Implemented |
| SRD-DSK-010.007 | A topic with 3 ended tickets that gave no gain is parked for 30 days | Implemented |
| SRD-DSK-010.008 | The desk runs one approved ticket at a time, oldest first, only when no event waits and no watcher flag came in the last 20 minutes | Implemented |
| SRD-DSK-010.009 | A ticket is worked by the active employee whose skill handles its kind, one AI call per step | Implemented |
| SRD-DSK-010.010 | A ticket ends as done or failed at its done test, or as done at its token, step or time cap; the token cap is hard | Implemented |
| SRD-DSK-010.011 | A ticket ends as stuck after two steps with no new result, or the same tool call twice in a row | Implemented |
| SRD-DSK-010.012 | A watcher flag, a plan run, a used-up research part or app close pauses the running ticket after its current step | Implemented |
| SRD-DSK-010.013 | An ended ticket posts a `research_done` event with its id, status and result | Implemented |
| SRD-DSK-010.014 | Raise, approve, start, pause and end of each ticket are logged with the `[Research]` prefix | Implemented |

---

## Design Decisions

- A queue or block error never loses the lead's answer; the answer is kept and the error is logged.
- A runner error backs off for 15 minutes, so the desk never goes to Error.
- A refusal that is not a cap (for example a used-up part) pauses the ticket and backs off for 15 minutes.
- Pause is by ticket id, so one ticket never pauses another.
- A ticket that ended at a cap has an unknown gain, so it does not count towards parking a topic.
- The results block in the lead's facts shows worked tickets only.
- No research skill ships in this step (step F). Approved tickets wait with a log line until a doer skill exists.

---

## Issues Resolved

None

---

## Test Coverage

UT-DSK-004.006–.010 (10 cases), UT-DSK-007.010 (2 cases), UT-DSK-010.001–.014 (34 cases): 46 cases, all Pass. Files: `test_desk_research.py`, `test_research.py`, `test_budget_split.py`. `test_desk_events.py` kind list updated. Full suite: no new failures; the 12 failures are the old ones in TODO T112; `tests/screener/test_llm_claude_screener.py` ignored (old import error, TODO T136). The execution folder crashes the process in one long full run on Windows but passes 375/375 alone.
