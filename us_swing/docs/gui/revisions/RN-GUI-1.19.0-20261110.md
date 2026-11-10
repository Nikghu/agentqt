# Revision Note — RN-GUI-1.19.0-20261110

**Version:** 1.19.0
**Date:** 2026-11-10
**Tool:** GUI
**Artifact:** FO-GUI-036 / SRD-GUI-036.001–.008
**Type:** Feature

---

## Summary

AI Desk has a new Team setup section after Team at work. The list on the left shows every employee in the desk folder; the form has tabs Prompt, Profile, Model, Limits & wake and History. Save shows the new version and says it applies from the next wake; Restore brings back an old version; Test on yesterday runs the unsaved prompt in the background with one real AI call. The Team at work side pane is trimmed to a short summary with an Edit in Team setup link.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-036.001.M01 | `gui/ai_desk_setup.py` (new) | Team setup section: employee list, tabbed form, save, history, test on yesterday |
| MD-GUI-034.059.M33 | `gui/ai_desk.py` | Team setup tab; Edit link wiring to Team setup |
| MD-GUI-035.007.M04 | `gui/ai_desk_team_pane.py` | `ProfilePane` trimmed to name, role, state, Model line, month bar, This run and Prompt / Answer peek; `edit_requested` signal |
| MD-GUI-035.001.M01 | `gui/ai_desk_team.py` | Re-emits `edit_requested` from the side pane |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-036.001 | Team setup tab lists every employee in the desk folder | Implemented |
| SRD-GUI-036.002 | Picked employee opens in a tabbed form; skill read-only | Implemented |
| SRD-GUI-036.003 | Prompt tab edits the prompt; answer rules shown read-only | Implemented |
| SRD-GUI-036.004 | Model tab picks main and backup source and model; Other for free text | Implemented |
| SRD-GUI-036.005 | Save shows the reason or the new version and "applies from the next wake"; unsaved changes asked about | Implemented |
| SRD-GUI-036.006 | History tab lists versions, shows a picked prompt, restores it (asks first) | Implemented |
| SRD-GUI-036.007 | Test on yesterday runs in the background, one real AI call; off when no recorded run | Implemented |
| SRD-GUI-036.008 | Team at work side pane shows a summary with Edit in Team setup | Implemented |

---

## Design Decisions

- Side pane keeps a short summary only; all editing lives in Team setup.
- Confirm dialogs use the shared `gui.popups.confirm`.
- Review fixes: the running test stays in the module set; reload on show keeps a running test; Restore warns about unsaved edits.

---

## Issues Resolved

None

---

## Test Coverage

UT-GUI-036.001–.008: 15 cases, all Pass. Full `tests/gui`: 884 pass. Before the popup fix 2 failed; after it the only failure is `test_sidebar_shell::test_main_window_lists_screens`, which already fails on main (T141). `test_sidebar_shell::test_footer_all_users_and_missing_user` failed once in one baseline run; treated as pre-existing and flaky.

---

## Follow-up (same day)

Team setup shows level, status, model source and None with a capital first letter (Active, Expert, OpenRouter, None). Stored values in `employee.md` stay lowercase; each list item keeps the value as data. Commit 5552d6c0.
