# Revision Note — RN-DSK-0.14.0-20261113

**Version:** 0.14.0
**Date:** 2026-11-13
**Tool:** DSK
**Artifact:** FO-DSK-011, FO-DSK-002, FO-MKT-005, FO-MKT-006, FO-GUI-034, FO-GUI-035 / SRD-DSK-011.015–.032, SRD-DSK-011.003–.004, SRD-DSK-011.014, SRD-DSK-002.005, SRD-MKT-005.019–.023, SRD-MKT-006.013, SRD-GUI-034.070, SRD-GUI-035.015–.016
**Type:** Feature

---

## Summary

AI Desk v3 phase M1: employees can send messages to each other and get replies. Messages and threads are kept in `desk.db`, and each message goes through a six-step check before it is stored and wakes the receiver. The setup review can send an idea back to itself for a fix when the only failed check is the stop distance; the risk check then re-checks the fix in code. The messages switch is off by default, and the Threads tab in AI Desk shows today's threads.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-DSK-011.015.M29 | `src/us_swing/core/desk_messages.py` | New: messages and threads tables, 6-step check, receivers, guardrails, inbox block, reads for GUI |
| MD-GUI-035.016.M05 | `src/us_swing/gui/ai_desk_threads.py` | New: Threads tab, today's threads and the selected thread's messages (read-only) |
| MD-DSK-011.001.M27 | `src/us_swing/core/desk_msg.py` | Changed: Draft, with_messages, InboxReply |
| MD-DSK-003.004.M15 | `src/us_swing/core/desk_events.py` | Changed: message event with target |
| MD-DSK-002.001.M08 | `src/us_swing/core/desk_agents.py` | Changed: Facts.inbox, Talker and talker |
| MD-DSK-004.005.M13 | `src/us_swing/core/desk_ai_settings.py` | Changed: messages_on, off by default |
| MD-DSK-012.001.M28 | `src/us_swing/core/desk_registry.py` | Changed: idea_fix.v1 format |
| MD-DSK-003.006.M16 | `src/us_swing/desk/router.py` | Changed: addressed wake, waiting step until replies are read, release, expiry each pass |
| MD-DSK-003.001.M10 | `src/us_swing/desk/employees_step.py` | Changed: message wake with inbox facts, starter pays, refusals |
| MD-DSK-004.001.M11 | `src/us_swing/desk/gateway.py` | Changed: message turns |
| MD-DSK-004.003.M12 | `src/us_swing/desk/budget.py` | Changed: message turn budget checks |
| MD-DSK-005.001.M14 | `src/us_swing/desk/recorder.py` | Changed: message turns recorded with message id |
| MD-MKT-005.009.M05 | `src/us_swing/market/setup_review.py` | Changed: asks news review, holds up to 3 ideas, merges grades on inbox wake, fixed levels in listed frame |
| MD-MKT-005.012.M07 | `src/us_swing/market/risk_check.py` | Changed: stop-only veto sent back, fix checked in code, round 2, one send-back per idea per day |
| MD-MKT-006.005.M04 | `src/us_swing/market/news_review.py` | Changed: reply only, no new news_tags rows |
| MD-MKT-001.007.M04 | `src/us_swing/market/store.py` | Changed: idea_fixes table, put_rows |
| MD-MKT-013.001.M01 | `src/us_swing/market/watch.py` | Changed: fixed levels |
| MD-MKT-013.008.M02 | `src/us_swing/market/watch_flag.py` | Changed: fixed levels |
| MD-GUI-034.016.M15 | `src/us_swing/gui/ai_desk_settings.py` | Changed: Agent messages switch |
| MD-GUI-035.001.M01 | `src/us_swing/gui/ai_desk_team.py` | Changed: Threads tab added |
| MD-GUI-035.002.M02 | `src/us_swing/core/desk_team.py` | Changed: message rows in team read model |
| MD-GUI-035.006.M03 | `src/us_swing/gui/ai_desk_team_log.py` | Changed: message event rows with type, from, to, subject and state |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-DSK-011.003 | The core header holds id, thread, parent, type, sender, to and at, plus due and state (reopened: a send_back has a parent or starts a thread with a `to`) | Implemented |
| SRD-DSK-011.004 | An address is an employee id, `skill:<key>`, `champion:<key>`, `boss` or `master` (reopened: no parent on a send_back starts a thread) | Implemented |
| SRD-DSK-011.014 | Messages are stored and sent only through the M1 rows SRD-DSK-011.015–.032 (reopened) | Implemented |
| SRD-DSK-011.015 | Messages and threads are kept in `messages` and `threads` tables in `desk.db`, one `desk.msg/1` row each | Implemented |
| SRD-DSK-011.016 | The setup review, news review and risk check answers may carry an optional `messages` list of drafts | Implemented |
| SRD-DSK-011.017 | M1 accepts the types ask, reply and send_back; any other type is refused as not yet in use | Implemented |
| SRD-DSK-011.018 | A receiver is an active employee id or `skill:<key>`, the lowest id that holds the skill | Implemented |
| SRD-DSK-011.019 | Each draft is checked in order (format, type rules, receiver, guardrails, data block, then store and wake); a failed draft is refused alone | Implemented |
| SRD-DSK-011.020 | A thread holds at most 6 messages and 2 send-back rounds; an employee starts at most 20 messages a New York day | Implemented |
| SRD-DSK-011.021 | A reply answers exactly one open ask or send-back addressed to its sender, and each gets one reply | Implemented |
| SRD-DSK-011.022 | An employee may not ask or send back to an employee that is waiting on it in the same thread | Implemented |
| SRD-DSK-011.023 | An ask or send-back is due 10 minutes after it is stored and expires when no reply came by then | Implemented |
| SRD-DSK-011.024 | A stored ask, send-back or reply posts one `message` event addressed to its receiver | Implemented |
| SRD-DSK-011.025 | The router wakes only the addressed employee for a `message` event, outside its trigger list and run order | Implemented |
| SRD-DSK-011.026 | A woken employee's facts end with an inbox block of its open messages | Implemented |
| SRD-DSK-011.027 | A reply closes its parent as completed, failed or refused by its verdict and wakes the asker in the same run | Implemented |
| SRD-DSK-011.028 | When the receiver sleeps, is out of budget or fails, the desk replies refused with the reason at once | Implemented |
| SRD-DSK-011.029 | An employee's `step_done` waits while an ask or send-back it started is open | Implemented |
| SRD-DSK-011.030 | Tokens of a message turn count against the part and budget of the thread's starter, and each turn is recorded with its message id | Implemented |
| SRD-DSK-011.031 | Messages run only while `messages_on` is true in desk settings; it is false by default | Implemented |
| SRD-DSK-011.032 | Stored, refused and expired messages are logged with the `[Messages]` prefix | Implemented |
| SRD-DSK-002.005 | Talking skills also get their message drafts and a send function (reopened) | Implemented |
| SRD-MKT-005.019 | With messages on, the setup review may hold back up to 3 ideas and ask the news review about them | Implemented |
| SRD-MKT-005.020 | An idea vetoed only for its stop distance is sent back to the setup review, round 1 then round 2 | Implemented |
| SRD-MKT-005.021 | The setup review replies to a send-back with a new trigger and stop, or drops the idea with a reason | Implemented |
| SRD-MKT-005.022 | A fix is kept in `idea_fixes` and checked by the same code limits; a pass sets the `risk_check` row to pass | Implemented |
| SRD-MKT-005.023 | Every reader of the day's listed ideas uses the fixed trigger and stop when a passing fix exists | Implemented |
| SRD-MKT-006.013 | With messages on, the news review answers an ask in its inbox with one reply from its facts | Implemented |
| SRD-GUI-034.070 | Desk settings has an Agent messages switch, off by default, saved as `messages_on` | Implemented |
| SRD-GUI-035.015 | The event log shows each message event with its type, from and to, subject and state | Implemented |
| SRD-GUI-035.016 | A Threads view lists today's threads and shows the messages of the selected thread (read-only) | Implemented |

---

## Design Decisions

- Messages go to the risk check before the code veto: a stop-only veto is sent back, at most 2 rounds. The 10% code limit keeps the final say.
- The router stays serial. The 4 code and 2 AI worker counts are deferred to M6.
- Wake by message: no new run order.
- New rows under FO-DSK-011 instead of reopening FO-DSK-003.
- Left out by the no-unused rule: worker counts (to M6), priority from type (to M2), handover type (to M2/M5).
- Behaviour change with messages off (user-approved bug fix): a wake with no model call now ends ok, so an all-code-vetoed day no longer counts as failed, retries and alerts.

---

## Issues Resolved

None

---

## Test Coverage

47 new UTCD cases, all Pass: UT-DSK-011.* M1 (47, desk). One extra desk case UT-DSK-003.014.M10.T02 (Pass). 16 market cases UT-MKT-005.019–.023 and UT-MKT-006.013 (Pass, market). 7 GUI cases UT-GUI-034.070 and UT-GUI-035.015–.016 (Pass). Desk, market and touched GUI suites: 1051+ passed. ruff and mypy --strict clean on changed files.

Reviews: code review 5 MEDIUM fixed (mark seen in finally and refuse on error, non-numeric fix guarded, one send-back per idea per day, inbox skips closed asks, messages-off refuses at once). PyQt review MEDIUM fixed (detail list keeps scroll position) and LOW fixed.

Open: user check in the app with Agent messages switched on (T174). M2 next. Branch `feat/dsk-m1-messages`, not pushed.

---

## Desk-Copy Check (2026-11-13)

Run on a copy of the real desk (data day 2026-11-12) with Agent messages on and real Claude Code calls. Risk check sent back all 11 stop-limit ideas; the setup review fixed 5 from the new price facts (BRK.B, DGX, ADP, COST, KO), all passed the code limits in round 1; the other 6 expired after 10 minutes and stayed vetoed; the lead then ran and picked DGX and KO among others. Found and fixed during the check: a code-written expired reply had no text and crashed risk check on read-back; setup review had no price data to choose stops (new SRD-MKT-005.024, user-approved); model replies without `verdict` are now filled by code. User chose to send back all over-limit ideas in one run.
