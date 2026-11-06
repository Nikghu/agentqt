# Revision Note — RN-DSK-0.4.0-20261106

**Version:** 0.4.0
**Date:** 2026-11-06
**Tool:** DSK (+ GUI)
**Artifact:** FO-DSK-006 / SRD-DSK-006.001–.010; FO-GUI-034 / SRD-GUI-034.027–.033
**Type:** Feature

---

## Summary

P6 desk: hiring pipeline, shadow mode, seat caps and a weekly report. The Master user starts a hire in AI Desk → Hiring by choosing a skill the code knows, a level, a name and a model; the new employee folder gets `status: shadow`. For 14 data days a shadow employee answers the same facts as the skill's holder, but its answer is only checked and recorded (`activity.shadow = 1`); the skill's act is never called, so no views, picks or briefs come from it. The Hiring section shows a shadow report (days, valid share, tokens, cost, agreement with the holder) and Replace / Add / Reject buttons; each decision is kept in an append-only `approvals` table and changes only the `status:` and `version:` lines of `job.yaml`. Retired employees are not loaded. Seat caps are 8 experts, 5 champions and 30 juniors, editable in Desk settings. A new desk step "Weekly report" writes one code-only report per week (first run on or after Friday, New York) shown in AI Desk → Reports. No AI proposes hires and the report costs nothing.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-DSK-006.001.M18 | `us_swing/src/us_swing/core/desk_hiring.py` | New: start hire, refuse reasons, seat count, hires list, shadow report, agreement, decisions, `approvals` table |
| MD-DSK-006.004.M19 | `us_swing/src/us_swing/desk/shadow.py` | New: ask and record only for a shadow employee, 14 data days, one answer per day |
| MD-DSK-006.009.M20 | `us_swing/src/us_swing/desk/weekly_report.py` | New: desk step "Weekly report" and `desk_reports` table |
| MD-DSK-002.002.M09 | `us_swing/src/us_swing/desk/registry.py` | Changed: `status` (active / shadow / retired) and `hired_on`; retired not loaded |
| MD-DSK-003.001.M10 | `us_swing/src/us_swing/desk/employees_step.py` | Changed: shadow employees go to `run_shadow()` |
| MD-DSK-005.001.M14 | `us_swing/src/us_swing/desk/recorder.py` | Changed: `activity.shadow` column, `shadow_days()` |
| MD-DSK-004.001.M11 | `us_swing/src/us_swing/desk/gateway.py` | Changed: `shadow` flag marks tries |
| MD-DSK-004.005.M13 | `us_swing/src/us_swing/core/desk_ai_settings.py` | Changed: seat caps 8 / 5 / 30 and `cap()` |
| MD-DSK-001.021.M07 | `us_swing/src/us_swing/core/desk_steps.py` | Changed: "Weekly report" step after "AI employees" |
| MD-GUI-034.027.M21 | `us_swing/src/us_swing/gui/ai_desk_hiring.py` | New: Hiring section and Command approvals box |
| MD-GUI-034.032.M22 | `us_swing/src/us_swing/gui/ai_desk_sections3.py`, `core/desk_floor.py` | Changed: Reports from `desk_reports` (sample until the first one) |
| MD-GUI-034.033.M23 | `us_swing/src/us_swing/gui/ai_desk_settings.py` | Changed: seat cap fields; a cap below the current count is refused |
| MD-GUI-034.009.M08 | `us_swing/src/us_swing/gui/ai_desk.py`, `ai_desk_sections.py`, `ai_desk_sample.py` | Changed: Command, Hiring and Reports are live sections; sample hiring and approvals removed |
| — | `us_swing/USSwing.spec` | Hidden import `us_swing.desk.weekly_report` |

---

## Tests

- 23 DSK UT (`tests/desk/test_hiring.py`) and 13 GUI UT (`tests/gui/test_ai_desk_hiring.py`), all Pass.
- Updated: UT-DSK-003.001.M10.T03 (Weekly report is now the last step); UT-GUI-034.010.M03.T02 (Hiring is real, no Sample tag).
- Full suite: 2365 passed, 12 old failures (T112), 2 skipped. Exit code 9 at the end also happens on clean main.
- Real window: Hiring section on a temporary desk with one ready hire — list, report (82% agreement), Replace on and Add off as the rules say.

---

## Known Limits

- The code reviewers stopped early on the account usage limit; the review was done by hand. Run them again after the limit resets.
- A decision while the desk is reading employee files can make one run skip that employee (the file is read again next run).
- Agreement uses only short typed values; a skill whose answer is mostly free text agrees 100% by default.
- With two holders of one skill, the report shows both rows but the agreement of the last one.
