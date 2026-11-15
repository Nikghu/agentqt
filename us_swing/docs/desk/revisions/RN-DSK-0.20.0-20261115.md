# Revision Note — RN-DSK-0.20.0-20261115

**Version:** 0.20.0
**Date:** 2026-11-15
**Tool:** DSK
**Artifact:** FO-DSK-006 (M7a part), FO-GUI-034 / SRD-DSK-006.011–.027, SRD-GUI-034.081–.084
**Type:** Feature

---

## Summary

AI Desk v3 phase M7a: hire proposals. With `hire_proposals_on` (and agent messages) on, a new weekly report wakes a new desk secretary (default `emp-020`, "Expert 15", title Desk secretary). Code finds hire needs in the desk's own records over the last 10 data days: failing employees (under 70% valid answers with at least 5 tries), costly employees (cost per valid answer over 3 times the desk middle) and needed skills that no active employee holds, and writes the evidence. The secretary makes one AI call to pick up to 2 of these candidates, a model for each and a short reason. Each pick is saved as a waiting proposal and sent to the secretary's boss as one ask carrying a `hire_proposal.v1` row. The boss answers in a short reply-only turn (its own skill does not run), and its reply sets the proposal's view: done agrees, refused does not. The Master user sees each proposal in Command → Approvals waiting and the Market Floor feed (Approve starts the trial hire in shadow with the next free generic name; Reject is kept) and in a new Proposals list in Hiring. The existing 14-data-day shadow and Replace / Add / Reject stay gate 2. About 2 AI calls a week, none without a candidate. Off by default; off keeps the M6 desk as it was.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-DSK-006.012.M35 | `src/us_swing/core/desk_proposals.py` (new) | Need rules, candidates, `hire_proposals` table, the boss's view, gate 1 decision, reads and card text |
| MD-DSK-006.016.M36 | `src/us_swing/desk/secretary.py` (new) | Secretary skill: facts, one AI pick, checks, save and ask, code-only inbox, weekly no-answer sweep, logs |
| MD-DSK-003.001.M10 | `src/us_swing/desk/employees_step.py` | Proposal asks in the short reply-only turn shared with escalations; views noted; refused by code while off |
| MD-DSK-006.009.M20 | `src/us_swing/desk/weekly_report.py` | Posts `weekly_report` after a new report while hire proposals are on |
| MD-DSK-003.004.M15 | `src/us_swing/core/desk_events.py` | Event kind `weekly_report` |
| MD-DSK-012.001.M28 | `src/us_swing/core/desk_registry.py` | `hire_proposal.v1` format seeded |
| MD-DSK-006.001.M18 | `src/us_swing/core/desk_hiring.py` | `default_level()` |
| MD-DSK-004.005.M13 | `src/us_swing/core/desk_ai_settings.py` | `hire_proposals_on`, off by default |
| MD-DSK-001.021.M07 | `src/us_swing/core/desk_steps.py`, `src/us_swing/market/employees/emp-020/` (new), `USSwing.spec` | `hire_review` skill path, default secretary, app build module |
| MD-DSK-009.010.M30 | `src/us_swing/core/desk_memory.py` | Docstring only: the secretary reads the week's failure rows |
| MD-GUI-034.054.M32 | `src/us_swing/core/desk_feed.py` | One Ask card per waiting proposal |
| MD-GUI-034.053.M31 | `src/us_swing/gui/floor_feed.py` | Approve and Reject on proposal cards |
| MD-GUI-034.027.M21 | `src/us_swing/gui/ai_desk_hiring.py` | Proposals list in Hiring |
| MD-GUI-034.016.M15 | `src/us_swing/gui/ai_desk_settings.py` | Hire proposals check box |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-DSK-006.011 | A new weekly report posts one `weekly_report` event while hire proposals are on | Implemented |
| SRD-DSK-006.012 | Failing need: under 70% valid answers with at least 5 AI tries in 10 data days | Implemented |
| SRD-DSK-006.013 | Costly need: cost per valid answer over 3 times the desk middle | Implemented |
| SRD-DSK-006.014 | Empty need: a needed skill no active employee holds | Implemented |
| SRD-DSK-006.015 | Candidates with evidence written by code, and the drop rules | Implemented |
| SRD-DSK-006.016 | Secretary facts; no AI call without a candidate | Implemented |
| SRD-DSK-006.017 | Up to 2 picks with a known model and a short reason | Implemented |
| SRD-DSK-006.018 | Each pick saved and sent to the boss as one ask with a `hire_proposal.v1` row | Implemented |
| SRD-DSK-006.019 | `hire_proposal.v1` in the schema library | Implemented |
| SRD-DSK-006.020 | Proposal asks answered in a short reply-only turn | Implemented |
| SRD-DSK-006.021 | The boss's reply sets the view; a code reply gives none | Implemented |
| SRD-DSK-006.022 | Approve starts the trial hire with the next free generic name | Implemented |
| SRD-DSK-006.023 | Reject closes the proposal | Implemented |
| SRD-DSK-006.024 | Runs only with `hire_proposals_on` and `messages_on`, off by default | Implemented |
| SRD-DSK-006.025 | Default secretary `emp-020`, skill path and app build module | Implemented |
| SRD-DSK-006.026 | Reads and card text | Implemented |
| SRD-DSK-006.027 | `[Hiring]` log lines | Implemented |
| SRD-GUI-034.081 | Proposal Ask card in Approvals waiting and the Market Floor feed | Implemented |
| SRD-GUI-034.082 | Approve and Reject; a refusal shows its reason | Implemented |
| SRD-GUI-034.083 | Proposals list in Hiring | Implemented |
| SRD-GUI-034.084 | Hire proposals check box, off by default | Implemented |

---

## Design Decisions

- User decisions 2026-11-15: M7 in two steps, hire proposals first and the tool builder (M7b) after M7a is merged; an AI secretary writes the proposals and its boss gives a view; needs from failing employees, costly employees and needed skills nobody holds.
- Evidence numbers are written by code; the model only picks candidate ids, a known model and a short reason, and it sends no messages of its own.
- An ask has no data block in `desk.msg/1`, so the `hire_proposal.v1` row rides in the ask's `want` (`want.schema` names the format, `want.inputs` holds the row).
- The card shows as soon as the proposal is made, with "Waiting for <boss>'s view" until the reply; the Master user may decide at any time.
- Gate 1 Approve uses the existing `start_hire()`; no AI writes the employee file. Gate 2 is the existing shadow report and Replace / Add / Reject.
- "Missed moves" are not used: the desk has no such data today.
- Doc fixes: FO-DSK-006 now says 14 data days (not evenings) and that no AI starts a hire.
- Code review fixes (DD-DSK-006.011.D01 §12, DD-GUI-034.081.D01): Approve claims the proposal before the hire starts, so one proposal never starts two hires; strict reads where a lock must not look like "no proposal"; a view still pending after a day becomes "no answer" at the next weekly turn; the boss turn runs only while the switches are on; a card decided elsewhere turns its buttons off; the chosen proposal stays chosen in Hiring.
- Kept as designed: in one message wake a later turn's result hides an earlier one, as before M7a.

---

## Issues Resolved

None

---

## Test Coverage

- `tests/desk/`: 48 UT-DSK-006.011–.027 cases (41 + 7 added during coding and review), all Pass. `tests/desk` + `tests/core`: 956 pass.
- `tests/market/`: 669 pass, after `test_p5b_defaults` was updated for the `hire_review` skill.
- `tests/gui/`: 10 UT-GUI-034.081–.084 cases (8 + 2 from the GUI review), all Pass. Run in chunks: files 1–50 all pass (468) after `test_ai_desk_console.py` was updated for the new Proposals card. Files 51–100 ran in smaller chunks after Claude Code stopped one run because the computer was low on memory: all pass except two old problems not from M7a — `test_sidebar_shell.py::test_main_window_lists_screens` (failed before this branch too) and `test_strategy_store.py`, which cannot be imported when it loads first in a run (a circular import between `db/manager.py` and `data/engine.py`; those files are unchanged). `test_chart_workspace.py` alone: 24 pass.
- `tests/integration/`: 8 pass, 2 skipped.
- Four older tests updated: `test_desk_events.py` (new event kind), `test_desk_registry.py` (new format), `test_p5b_defaults.py` (new skill) and `test_ai_desk_console.py` (new Proposals card).
- ruff and mypy --strict clean on the new and changed files.

Known limits: the default expert cap (8) is below the shipped expert count (15 with the secretary), so an expert trial is refused until the Master user raises Expert seats in Desk settings; the card shows that reason. The user checks the flow in the app (TODO T180).
