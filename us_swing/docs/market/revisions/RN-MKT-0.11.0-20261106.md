# Revision Note — RN-MKT-0.11.0-20261106

**Version:** 0.11.0
**Date:** 2026-11-06
**Tool:** MKT (with GUI)
**Artifact:** FO-MKT-010 (P9) / SRD-MKT-010.001–.008; SRD-GUI-034.039–.041 (FO-GUI-034 still at Reopen)
**Type:** Feature

---

## Summary

P9 adds a real lead chat to AI Desk → Command. The Master types a question and presses Ask. The app saves it as an append-only `chat` row and posts a `chat_question` event. The desk process wakes a new lead-level chat employee ("Lead 2", `emp-008`, skill `lead_chat`). It answers from the latest lead brief facts, the last 10 trading days of picks with their paper results, and the last 6 chat turns. The answer is one text of at most 1500 characters. When no valid answer comes, a failed reply is saved. The chat has no tools and only explains; it never approves, rejects or trades. Only the chat employee's monthly cost cap and the desk budget limit it.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-MKT-010.001.M01 | `us_swing/src/us_swing/core/desk_chat.py` | New: append-only `chat` table with one reply per question; `ask_question()`, `open_question()`, `add_reply()`, `chat_turns()`, `question_note()` |
| MD-MKT-010.002.M02 | `us_swing/src/us_swing/core/desk_events.py` | Changed: event kind `chat_question` (priority 0, 2-minute deadline, 30-minute expiry); one key per question |
| MD-MKT-010.003.M03 | `us_swing/src/us_swing/market/lead_chat.py` | New: `LeadChatSkill`, `LeadChatAnswer`, `FAILED_TEXT` |
| MD-MKT-010.007.M04 | `us_swing/src/us_swing/market/employees/emp-008/`, `core/desk_steps.py` | New default employee "Lead 2" (lead, `lead_chat`, trigger `chat_question`, 200 calls a day, USD 3 a month); skill path |
| MD-GUI-034.039.M26 | `us_swing/src/us_swing/gui/ai_desk_chat.py`, `gui/ai_desk_sections.py`, `gui/ai_desk.py` | New `ChatPanel` in Command; `command_frame(name, approvals, chat)` |
| — | `us_swing/USSwing.spec` | Changed: hidden imports `us_swing.market.lead_chat`, plus `us_swing.market.pick_results`, which P8 missed |
| — | `us_swing/tests/desk/test_desk_events.py`, `tests/market/test_p5b_defaults.py` | Changed: event kinds and skill list now include the chat (intended) |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-MKT-010.001 | A Master question is saved as a `chat` row and posts one `chat_question` event. | Implemented |
| SRD-MKT-010.002 | `chat_question`: priority 0, 2-minute deadline, 30-minute expiry, one event per question. | Implemented |
| SRD-MKT-010.003 | The chat skill answers the oldest open question from today's facts, recent picks with paper results and recent turns. | Implemented |
| SRD-MKT-010.004 | The answer is at most 1500 characters, saved as a lead reply linked to its question. | Implemented |
| SRD-MKT-010.005 | No valid answer: a failed reply is saved. | Implemented |
| SRD-MKT-010.006 | The answer is only text; no chat code approves, rejects or trades. | Implemented |
| SRD-MKT-010.007 | Default lead-level chat employee `emp-008` ("Lead 2") with trigger `chat_question`. | Implemented |
| SRD-MKT-010.008 | `[Chat]` log lines with the question number and seconds. | Implemented |
| SRD-GUI-034.039 | Command → Lead chat shows the turns with the chat employee's current name. | Implemented |
| SRD-GUI-034.040 | Ask box and button; disabled when empty or while a question waits. | Implemented |
| SRD-GUI-034.041 | 2-second check while waiting: answer, failed reply, start-the-desk or expired note. | Implemented |

---

## Design Decisions

- User answers (2026-11-06): the desk process answers; context is today plus the last 10 days of picks; answers only; budget only; a new lead-level chat employee rather than one employee holding two skills.
- `calls_per_day` is 200 because every employee file needs a number; the cost cap does the real limiting.
- The chat reuses the lead brief's facts, so it sees the same data the lead used in the evening.
- A shadow chat employee never replies (shadow only records), so its questions expire after 30 minutes. This is by design.
- Review fixes (both reviewers approved): the turn list is rebuilt only when it changes and scrolls to the newest turn; a Command section rebuilt while a question waits keeps checking; a unique index allows only one reply per question.

---

## Test Results

- New tests: 17 MKT (`tests/market/test_lead_chat.py`, including an end-to-end desk run with a fake model) and 7 GUI (`tests/gui/test_ai_desk_chat.py`); all Pass.
- Real check on a copy of the desk: Lead 2 was seeded, and one real question was answered through the Claude CLI in 12.7 s.
- Full suite: see DEVLOG.

---

## Open

- T131: user check. Restart the desk first, so `emp-008` is seeded and the new code runs.
