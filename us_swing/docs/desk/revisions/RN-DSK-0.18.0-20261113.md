# Revision Note — RN-DSK-0.18.0-20261113

**Version:** 0.18.0
**Date:** 2026-11-13
**Tool:** DSK
**Artifact:** FO-MKT-020, FO-GUI-034, FO-GUI-035 / SRD-MKT-020.001–.024, SRD-GUI-034.077–.078, SRD-GUI-035.018
**Type:** Feature

---

## Summary

AI Desk v3 phase M5: company day. With `company_day_on` on, the desk runs a day routine: code builds a stand-up, a huddle runs only when the regime view and sector/flow disagree, the lead's answer gives a day call that is checked 5 trading days later, and one AI call at day-end writes the handover and one feedback line per expert. Off by default, and off keeps the M4 desk as it was. The setting is behind a Company day switch in Desk settings; the Command header shows Day call and Handover tiles, and Team at work shows a day strip.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-MKT-020.001.M02 | `src/us_swing/core/desk_ai_settings.py` | `company_day_on` setting, off by default |
| MD-MKT-020.002.M01 | `src/us_swing/core/desk_day.py` (new) | Day rows, stand-up, clash, day call and votes, results, handover, GUI reads |
| MD-MKT-020.004.M03 | `src/us_swing/market/lead_brief.py` | Stand-up first in facts, huddle call and wait, huddle block, day call in answer |
| MD-MKT-020.007.M04 | `src/us_swing/core/desk_messages.py` | Meeting to a list of receivers, one row each in one thread |
| MD-MKT-020.009.M05 | `src/us_swing/market/regime_view.py`, `src/us_swing/market/sector_view.py` | Reply-only answer to a meeting in the inbox |
| MD-MKT-020.014.M06 | `src/us_swing/market/decision_check.py` (new) | Decision check step: SPY and sector results, vote results |
| MD-MKT-020.018.M10 | `src/us_swing/desk/employees_step.py` | Day-call line after memory blocks; `meetings` flag |
| MD-MKT-020.019.M07 | `src/us_swing/core/desk_events.py`, `src/us_swing/core/desk_team.py`, `src/us_swing/desk/process.py` | `day_end` event kind, label and once-a-day posting |
| MD-MKT-020.020.M08 | `src/us_swing/market/day_end.py` (new) | Day-end skill: facts, handover and feedback answer, rows, memory notes, feed item |
| MD-MKT-020.023.M09 | `src/us_swing/market/employees/emp-018/` (new), `src/us_swing/core/desk_steps.py`, `USSwing.spec` | Default day-end employee, skill and step paths, app build modules |
| MD-GUI-034.016.M15 | `src/us_swing/gui/ai_desk_settings.py` | Company day switch in Desk settings |
| MD-GUI-034.078.M40 | `src/us_swing/gui/ai_desk_day.py` (new), `src/us_swing/gui/ai_desk.py` | Day call and Handover tiles in the Command header |
| MD-GUI-035.018.M06 | `src/us_swing/gui/ai_desk_day.py` (new), `src/us_swing/gui/ai_desk_team.py` | Day strip in Team at work |
| MD-GUI-035.001.M01 | `src/us_swing/gui/ai_desk_team.py` | Day strip placed above the view switch |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-MKT-020.001 | `company_day_on` setting, off by default; off means M4 behaviour | Implemented |
| SRD-MKT-020.002 | `desk.db` day tables (day_brief, decisions, decision_votes), written only by `core/desk_day.py` | Implemented |
| SRD-MKT-020.003 | Code builds the stand-up from the handover and the five views; no AI call | Implemented |
| SRD-MKT-020.004 | Lead brief facts start with the stand-up, at most 1,200 characters | Implemented |
| SRD-MKT-020.005 | Clash: Downtrend with no defensive sector, or Uptrend with only defensive sectors | Implemented |
| SRD-MKT-020.006 | On a clash, one huddle a day to the two view holders; the lead waits, no AI call | Implemented |
| SRD-MKT-020.007 | Meeting to up to 3 receivers, one row each in one thread, due in 10 minutes | Implemented |
| SRD-MKT-020.008 | A meeting closes on one reply or the 10-minute expiry; no send-back | Implemented |
| SRD-MKT-020.009 | View skills answer a meeting once, in their inbox, at most 600 characters | Implemented |
| SRD-MKT-020.010 | Lead waits while a huddle is open, then runs with a huddle block of replies | Implemented |
| SRD-MKT-020.011 | Lead answer gives a day call: market, 1 to 3 sectors from the saved list, note | Implemented |
| SRD-MKT-020.012 | Day call kept in `decisions`, check due 5 trading days later; a rerun replaces it, a checked call is kept | Implemented |
| SRD-MKT-020.013 | Votes: regime view on market, sector/flow on sectors; stored in `decision_votes` | Implemented |
| SRD-MKT-020.014 | Decision check desk step checks each due day call; a failure never stops the run | Implemented |
| SRD-MKT-020.015 | Market result from SPY move over 5 trading days (Uptrend, Downtrend, Choppy rules) | Implemented |
| SRD-MKT-020.016 | Sector result from favoured sectors against SPY by 0.5 points | Implemented |
| SRD-MKT-020.017 | Agreeing vote takes the part's result; disagreeing vote the opposite; neutral stays neutral | Implemented |
| SRD-MKT-020.018 | With Memory v2 on, one day-call line in the core block: checked, right, wrong | Implemented |
| SRD-MKT-020.019 | `day_end` event posted once per closed day with no handover, from 16:00 New York time | Implemented |
| SRD-MKT-020.020 | Day-end facts from code: day call, picks and results, watch flags, check-ins, open trades | Implemented |
| SRD-MKT-020.021 | Day-end answer: handover of 1 to 5 lines, at most one feedback line per expert skill | Implemented |
| SRD-MKT-020.022 | Handover, feedback and code summary kept in `day_brief`; feedback to memory; feed item | Implemented |
| SRD-MKT-020.023 | Default lead-level employee `emp-018` ("Lead 3", skill `day_end`) and its build paths | Implemented |
| SRD-MKT-020.024 | Each company day step logs one `[Company day]` line; no trade is placed, changed or closed | Implemented |
| SRD-GUI-034.077 | Desk settings has a Company day check box, off by default | Implemented |
| SRD-GUI-034.078 | With company day on, Command header shows Day call and Handover tiles | Implemented |
| SRD-GUI-035.018 | With company day on, Team at work shows a day strip: Stand-up, Huddle, Plan, Market hours, Day-end | Implemented |

---

## Design Decisions

- Stand-up is built by code (0 AI calls per day).
- Huddle runs only when the regime view and sector/flow disagree, at most one a day, and only when the roster holds both view skills (a refused meeting would leave no plan).
- The lead's day call (market plus 1 to 3 sectors) is logged with each expert's vote and checked after 5 trading days against SPY and the sector lines.
- One lead AI call at day-end (new employee `emp-018`, "Lead 3") writes the handover and one feedback line per expert into memory.
- Meetings to several receivers use one row per receiver in one thread; closed meetings stay out of the inbox.
- A checked day call is never reset by a rerun.
- Behind `company_day_on`, off by default. No FO-MKT-005 rows reopened.
- Review fixes: rich text escaped in the GUI tiles.

---

## Issues Resolved

None

---

## Test Coverage

- `tests/market/` and `tests/desk/`, `tests/core/`, integration: 67 FO-MKT-020 UT cases, all Pass. Combined suites: 1489 pass.
- `tests/gui/`: 7 UT cases for SRD-GUI-034.077–.078 and SRD-GUI-035.018, all Pass. AI Desk GUI suite: 247 pass.
- ruff and mypy --strict clean on changed files.

Known limits: real-AI behaviour of the stand-up, huddle and day-end is checked by the user in the app (TODO T178).
