# Revision Note — RN-DSK-0.15.0-20261113

**Version:** 0.15.0
**Date:** 2026-11-13
**Tool:** DSK
**Artifact:** FO-DSK-011, FO-DSK-007, FO-DSK-008, FO-MKT-013, FO-GUI-034, FO-GUI-035, FO-GUI-036 / SRD-DSK-011.014, .024, .033–.043, SRD-DSK-007.011, SRD-DSK-008.010, SRD-MKT-013.013, SRD-GUI-034.071, SRD-GUI-035.017, SRD-GUI-036.011
**Type:** Feature

---

## Summary

AI Desk v3 phase M2: an employee can send an escalate message to its boss (`reports_to`). If the boss does not answer in 5 minutes, the message moves up one level. When it passes the top boss, the Master user gets an "Escalation not answered" alert. A boss gets a short reply-only turn, and the reply is shown as an AI feed note. Employees can name a deputy who takes their messages when they cannot work. The watch flag also escalates a broken plan and stop or target touches. All of this is behind `escalation_on`, which is off by default.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-DSK-011.015.M29 | `src/us_swing/core/desk_messages.py` | Escalate accepted, boss address, 5-minute move up, deputy hand, reply-only handling, escalation logs |
| MD-DSK-003.004.M15 | `src/us_swing/core/desk_events.py` | Message priority from type (escalate 0); repost key with `again` |
| MD-DSK-003.006.M16 | `src/us_swing/desk/router.py` | Roster and send passed to the move-up check on each pass |
| MD-DSK-003.001.M10 | `src/us_swing/desk/employees_step.py` | Boss reply-only turn, reply as feed note, deputy tried before refusal |
| MD-DSK-004.005.M13 | `src/us_swing/core/desk_ai_settings.py` | `escalation_on` setting, off by default |
| MD-DSK-007.001.M21 | `src/us_swing/core/desk_alerts.py` | Kind `escalation`: "Escalation not answered" alert |
| MD-DSK-008.001.M22 | `src/us_swing/core/desk_employee.py` | Optional `deputy` in employee file, with checks |
| MD-MKT-013.008.M02 | `src/us_swing/market/watch_flag.py` | Escalate to boss for a broken plan and stop or target touch |
| MD-GUI-034.016.M15 | `src/us_swing/gui/ai_desk_settings.py` | Escalation switch under Agent messages |
| MD-GUI-035.016.M05 | `src/us_swing/gui/ai_desk_threads.py` | Reason lines for moved-up escalates and deputy hands |
| MD-GUI-036.001.M01 | `src/us_swing/gui/ai_desk_setup.py` | Deputy picker in the Profile tab |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-DSK-011.014 | Messages are stored and sent only through the M1 and M2 rows (reopened) | Implemented |
| SRD-DSK-011.024 | A stored ask, send-back or reply posts one `message` event to its receiver (reopened) | Implemented |
| SRD-DSK-011.033 | With escalation on, the escalate type is accepted; handover and other types stay refused | Implemented |
| SRD-DSK-011.034 | The address `boss` means the sender's `reports_to` employee | Implemented |
| SRD-DSK-011.035 | Message priority from type: escalate 0, every other type 1 | Implemented |
| SRD-DSK-011.036 | An escalate is due 5 minutes after it reaches a boss, then moves to that boss's boss | Implemented |
| SRD-DSK-011.037 | Each move up writes `meta.blocked` and counts as one thread message | Implemented |
| SRD-DSK-011.038 | An escalate does not count toward the 20 messages a day | Implemented |
| SRD-DSK-011.039 | A boss woken only by escalates gets a reply-only turn | Implemented |
| SRD-DSK-011.040 | A reply to an escalate is an AI feed note and changes no plan or trade | Implemented |
| SRD-DSK-011.041 | A message goes once to the receiver's deputy when the receiver cannot work | Implemented |
| SRD-DSK-011.042 | Escalation and deputy routing run only while `escalation_on` and `messages_on` are true | Implemented |
| SRD-DSK-011.043 | A move up, a deputy hand and a Master alert are logged with the `[Messages]` prefix | Implemented |
| SRD-DSK-007.011 | An escalation that passes the top boss with no reply raises an "Escalation not answered" alert | Implemented |
| SRD-DSK-008.010 | The employee file has an optional `deputy` field, checked on save | Implemented |
| SRD-MKT-013.013 | With escalation on, a broken verdict or stop or target touch also escalates to the boss | Implemented |
| SRD-GUI-034.071 | Desk settings has an Escalation switch under Agent messages, off by default | Implemented |
| SRD-GUI-035.017 | Threads shows an escalate's moves up and a deputy hand with their reason | Implemented |
| SRD-GUI-036.011 | The Profile tab has a Deputy picker listing the other employees and None | Implemented |

---

## Design Decisions

- Escalate goes to the boss first. Each level gets 5 minutes; past the top boss, the Master user is alerted.
- Escalates are free of the 20-a-day cap, but the 6-message thread cap still applies.
- The boss's answer is a reply-only turn. The reply is a feed note only; it never changes a plan or trade.
- A deputy is tried once before a message is refused. A deputy hand restarts the 10-minute reply window.
- The handover message type is moved to M5.
- Known difference: the SRD-DSK-007.011 alert stays open for the day, not "closed when the thread gets a reply". Needs user OK.

---

## Issues Resolved

None

---

## Test Coverage

37 new UTCD cases, all Pass: UT-DSK-011.033–.043 and UT-DSK-007.011, UT-DSK-008.010 M2 (30, desk); UT-MKT-013.013 M2 (3, market); UT-GUI-034.071, UT-GUI-035.017, UT-GUI-036.011 M2 (4, GUI).

One M1 case updated: UT-DSK-011.017.M29.T02 (escalate is dropped while off). M1 console card list test fixed.

Known old failures, not from M2: 11 tests in `tests/analysis/test_candle_builder.py` and `tests/screener/test_preset.py` fail on main too. `tests/screener/test_llm_claude_screener.py` imports a missing module.

Code review fixes: an escalate is not refused when the boss cannot answer; a deputy hand restarts the due time; a move up leaves room for the reply.
