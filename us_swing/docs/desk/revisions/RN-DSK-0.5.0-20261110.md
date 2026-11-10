# Revision Note — RN-DSK-0.5.0-20261110

**Version:** 0.5.0
**Date:** 2026-11-10
**Tool:** DSK (with GUI)
**Artifact:** FO-DSK-007 / SRD-DSK-007.001–.006, SRD-GUI-035.010–.011
**Type:** Feature

---

## Summary

The desk now tells the user about AI problems only the user can fix. A Claude login, OpenRouter key or credit problem, or a run where no employee gave a valid answer, raises one alert per day. The alert goes to Telegram (first user with Telegram on) and shows in the app as a red banner in AI Desk → Team at work and a Desk card in the AI feed, with the fix step. Once Claude fails to sign in, the rest of that run goes straight to the backup model. Alerts close by themselves after a later valid answer.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-DSK-007.001.M21 | `core/desk_alerts.py` (new) | Spot problems, alerts table, Telegram send, open alerts |
| MD-DSK-004.001.M11 | `desk/gateway.py` | Report problems; skip a source that failed to sign in this run |
| MD-DSK-003.001.M10 | `desk/employees_step.py` | Whole-run alert; pass the sender |
| MD-GUI-035.001.M01 | `gui/ai_desk_team.py` | Red alert banner |
| MD-GUI-034.054.M32 | `core/desk_feed.py` | Alert cards in the AI feed |
| — | `tests/conftest.py` | Tests never read the real users file for Telegram |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-DSK-007.001 | Spot login, key and credit problems | Implemented |
| SRD-DSK-007.002 | One alert per problem per day | Implemented |
| SRD-DSK-007.003 | Send to Telegram | Implemented |
| SRD-DSK-007.004 | Skip to backup for the rest of the run | Implemented |
| SRD-DSK-007.005 | Whole-run alert | Implemented |
| SRD-DSK-007.006 | Alerts close when fixed | Implemented |
| SRD-GUI-035.010 | Alert banner in Team at work | Implemented |
| SRD-GUI-035.011 | Alert card in the AI feed | Implemented |

## Tests

9 new tests Pass (8 DSK, 1 GUI). gui, desk, market and core suites: 1664 pass; 1 old sidebar test fails on main too.
