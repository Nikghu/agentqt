# Revision Note — RN-DSK-0.17.0-20261113

**Version:** 0.17.0
**Date:** 2026-11-13
**Tool:** DSK
**Artifact:** FO-MKT-010, FO-GUI-034 / SRD-MKT-010.006, SRD-MKT-010.009–.019, SRD-GUI-034.073–.076
**Type:** Feature

---

## Summary

AI Desk v3 phase M4: chat sessions. With `sessions_on` on, each lead chat question is saved into a session (new after 2 hours quiet or on a new New York day, unless a session is chosen). A session closes after 24 hours quiet or on New discussion; at the next chat wake the lead writes a short summary and up to 3 memory notes. With agent messages on, the lead may send one ask per question and its reply becomes one Update row in the chat. The setting is off by default and off keeps the P9 chat.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-MKT-010.001.M01 | `src/us_swing/core/desk_chat.py` | `chat_sessions` table, `chat.session` column, session functions, `update` rows, team note |
| MD-MKT-010.003.M03 | `src/us_swing/market/lead_chat.py` | Session facts, closing summaries, one ask, updates; `LeadChatSummary` |
| MD-DSK-004.005.M13 | `src/us_swing/core/desk_ai_settings.py` | `sessions_on` setting, off by default |
| MD-GUI-034.016.M15 | `src/us_swing/gui/ai_desk_settings.py` | Chat sessions switch in Desk settings |
| MD-GUI-034.039.M26 | `src/us_swing/gui/ai_desk_chat.py` | Session list, New discussion, Update bubbles, "Waiting for the team" note |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-MKT-010.006 | Chat answer has text only; one ask allowed when sessions and agent messages are on (reopened) | Implemented |
| SRD-MKT-010.009 | `sessions_on` desk setting, off by default; off works as in P9 | Implemented |
| SRD-MKT-010.010 | Each question saved with a session: chosen one, else open session quiet under 2 hours on the same NY day, else new | Implemented |
| SRD-MKT-010.011 | A question in a closing or closed session opens it again | Implemented |
| SRD-MKT-010.012 | Session quiet 24 hours, or New discussion, marks it closing | Implemented |
| SRD-MKT-010.013 | Answer facts use the session summary and last 6 session turns | Implemented |
| SRD-MKT-010.014 | At a chat wake, one call per closing session writes a summary of at most 400 characters; at most 2 a wake | Implemented |
| SRD-MKT-010.015 | Summary answer carries up to 3 memory notes, kept only while Memory v2 is on | Implemented |
| SRD-MKT-010.016 | With sessions and agent messages on, one ask per question; first ask kept | Implemented |
| SRD-MKT-010.017 | Ask reply saved as one `update` chat row (at most 1500 characters); refused or expired gets code text, no AI call | Implemented |
| SRD-MKT-010.018 | Question note shows "Waiting for the team" while its ask has no reply | Implemented |
| SRD-MKT-010.019 | Session summary and update log lines carry the session or question number, `[Chat]` prefix | Implemented |
| SRD-GUI-034.073 | Desk settings has a Chat sessions switch, off by default, saved as `sessions_on` | Implemented |
| SRD-GUI-034.074 | With sessions on, lead chat shows a session list, newest first; choosing one shows its turns | Implemented |
| SRD-GUI-034.075 | New discussion button marks the shown session closing; next question starts a new session | Implemented |
| SRD-GUI-034.076 | Update rows show as lead bubbles marked "Update"; note shows "Waiting for the team" | Implemented |

---

## Design Decisions

- Summaries are written by the AI (one call per closing session) at the next chat wake.
- One team ask per question, and only with sessions and agent messages on.
- Summary and Master preferences go to the lead's memory only while Memory v2 is on.
- Session list and New discussion button in the Command chat.
- Defaults chosen (no user answer): new session rule uses the New York date; the day brief waits for M5; no new event kind (closing sessions are summarised at the next chat wake).
- Review fixes: bad text makes no empty session; an empty session makes no AI call; a concurrent `ALTER` is tolerated; `add_update` returns false when the question is missing; the kept ask's parent is cleared; the GUI polls 3 more ticks after the answer; switching sessions off stops summaries and updates.

---

## Issues Resolved

None

---

## Test Coverage

- `tests/market/test_lead_chat_sessions.py`: 30 tests, all Pass.
- `tests/gui/test_ai_desk_chat_sessions.py`: 9 tests, all Pass.
- Market and desk suites: 576 pass. AI Desk GUI suite: 192 pass.

Known limits: a summary only appears after the next question; one wake shares the gateway refused flag; asking a new question while "Waiting for the team" moves the note to the new question.
