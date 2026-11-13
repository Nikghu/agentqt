# Revision Note — RN-DSK-0.16.0-20261113

**Version:** 0.16.0
**Date:** 2026-11-13
**Tool:** DSK
**Artifact:** FO-DSK-009, FO-MKT-012, FO-GUI-034, FO-GUI-037 / SRD-DSK-009.010–.024, SRD-MKT-012.007–.008, SRD-GUI-034.072, SRD-GUI-037.005–.008
**Type:** Feature

---

## Summary

AI Desk v3 phase M3: memory v2. Desk memory moves to a new `memory.db` next to `desk.db`, and the lesson tables move there once. Notes and views are stored per employee, with a core block (track record, pinned notes, open views) and up to 10 recalled notes in each lead or expert wake. Views are checked after 10 trading days at ±1%, and notes are scored and retired by their results. The Master can pin, unpin or retire notes in AI Desk → Memory. All of this except the lesson move is behind `memory_v2_on`, which is off by default.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-DSK-009.010.M30 | `src/us_swing/core/desk_memory.py` | New: `memory.db` (WAL), memories table with FTS5, write rules, core block, recall, scores, status and expiry |
| MD-DSK-009.021.M31 | `src/us_swing/desk/memory_cleanup.py` | New: weekly clean-up step, one call per lead or expert with notes |
| MD-MKT-012.007.M04 | `src/us_swing/market/view_check.py` | New: view check step after Pick results; due views against daily closes, then scores and review |
| MD-DSK-009.001.M23 | `src/us_swing/core/desk_lessons.py` | Lesson tables read and written in `memory.db`; one-time move from `desk.db`, with `desk.db` fallback before the move |
| MD-DSK-011.001.M27 | `src/us_swing/core/desk_msg.py` | `remember` field on answers; bad items dropped (`with_remember`) |
| MD-DSK-004.005.M13 | `src/us_swing/core/desk_ai_settings.py` | `memory_v2_on` setting, off by default |
| MD-DSK-004.001.M11 | `src/us_swing/desk/gateway.py` | Private notes per employee; `kept_notes()` |
| MD-DSK-003.001.M10 | `src/us_swing/desk/employees_step.py` | Core block and recall in lead and expert wakes; notes written from answers |
| MD-DSK-001.010.M04 | `src/us_swing/desk/process.py` | Note edits applied per tick |
| MD-DSK-001.021.M07 | `src/us_swing/core/desk_steps.py` | View check step after Pick results; Memory clean-up step after Weekly report |
| MD-GUI-037.001.M01 | `src/us_swing/gui/ai_desk_memory.py` | Kind and Employee filters, NotesPanel, core block box, Pin / Unpin / Retire |
| MD-GUI-034.016.M15 | `src/us_swing/gui/ai_desk_settings.py` | Memory v2 switch in Desk settings |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-DSK-009.010 | Desk memory lives in `memory.db` next to `desk.db`, WAL mode, `desk.db` attached for pick cases | Implemented |
| SRD-DSK-009.011 | Lesson tables move once from `desk.db` to `memory.db`; lessons read the same before and after | Implemented |
| SRD-DSK-009.012 | Each memory is a row with owner, kind (note or view), text, symbol, direction, status, right, wrong, pinned; FTS5 index | Implemented |
| SRD-DSK-009.013 | Lead and expert answers may carry a `remember` list (at most 3; text at most 200 characters) | Implemented |
| SRD-DSK-009.014 | At most 3 new memories per employee per day; the rest are dropped | Implemented |
| SRD-DSK-009.015 | Each memory is added, updated or unchanged; an opposite open view retires the old one; pinned notes never change | Implemented |
| SRD-DSK-009.016 | Lead and expert wakes get a core block (track record, pinned notes, open and wrong views of 10 days), at most 1,200 characters | Implemented |
| SRD-DSK-009.017 | Lead and expert wakes get up to 10 active notes recalled by symbol, kept in `memory_uses` | Implemented |
| SRD-DSK-009.018 | A checked view adds one right or one wrong to each note recalled to its owner that day | Implemented |
| SRD-DSK-009.019 | A note with 5+ checks and under 40% right is weak and leaves recall; 3 right checks is proven | Implemented |
| SRD-DSK-009.020 | An active or weak note that is not pinned or proven retires 30 days after it was made or last updated | Implemented |
| SRD-DSK-009.021 | Once a week each lead and expert with notes gets one clean-up call (keep, merge, retire), applied by code | Implemented |
| SRD-DSK-009.022 | Master's pin, unpin and retire arrive as `memory_edits` rows and apply at the next tick | Implemented |
| SRD-DSK-009.023 | Remember fields, core block, recall, scores and clean-up run only while `memory_v2_on` is true | Implemented |
| SRD-DSK-009.024 | Lesson move, dropped drafts, weak, proven and retired notes and each clean-up are logged with `[Memory]` | Implemented |
| SRD-MKT-012.007 | A desk step after Pick results checks each open view 10 trading days after it was made; ±1% is right or wrong | Implemented |
| SRD-MKT-012.008 | The same step updates note scores and statuses; a failing check never stops the run | Implemented |
| SRD-GUI-034.072 | Desk settings has a Memory v2 switch, off by default, saved as `memory_v2_on` | Implemented |
| SRD-GUI-037.005 | Memory section has a Kind filter (Lessons, Notes, Views); Notes and Views list owner, text, symbol, status, right, wrong | Implemented |
| SRD-GUI-037.006 | Notes and Views have an Employee filter from the live employee list; All is the default | Implemented |
| SRD-GUI-037.007 | Choosing an employee shows its core block, read-only | Implemented |
| SRD-GUI-037.008 | Pin, Unpin and Retire on a chosen note write `memory_edits` rows; views have no buttons | Implemented |

---

## Design Decisions

- Own views are checked after 10 trading days at ±1%. Right at +1% or more its way; wrong at 1% or more the other way.
- A note under 40% right after 5 checks leaves recall. 3 right checks makes a note proven.
- The lesson move into `memory.db` runs whatever the switch is.
- Default top agents: lead and expert levels.
- Failure log moved to M6. Knowledge and preference kinds wait for M4 and M7.
- `lesson_reflect` stays daily.
- Code review fixes listed in DD-DSK-009.010.D01 §13.

---

## Issues Resolved

None

---

## Test Coverage

60 M3 UTCD cases, all Pass: UT-DSK-009.010–.024 (43, desk), UT-MKT-012.007–.008 (7, market), UT-GUI-034.072 and UT-GUI-037.005–.008 (10, GUI).

Desk, market and core suites: 1,384 pass. AI Desk GUI tests: 231 pass. 7 old tests updated (lesson tables now in `memory.db`; step order has 2 new steps).

Known, not from M3: 11 old failures in `tests/analysis/test_candle_builder.py` and `tests/screener/test_preset.py`, and a screener import error (`test_llm_claude_screener.py`). These exist on main and were not run here.
