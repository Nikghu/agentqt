# Revision Note — RN-GUI-1.37.2-20261027

**Version:** 1.37.2
**Date:** 2026-10-27
**Tool:** GUI
**Artifact:** FO-GUI-000 / SRD-GUI-000.008
**Type:** Bugfix

---

## Summary

The app no longer freezes ("Not responding") while live ticks stream. The hidden Charts stock list stops rebuilding on every tick, theme colours come from memory instead of a disk read per lookup, and tick-driven view refreshes are sent at most every 250 ms.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-000.008.M01 | `us_swing/src/us_swing/gui/theme.py` | Theme id cached in memory |
| MD-GUI-000.008.M02 | `us_swing/src/us_swing/gui/chart_source_list.py` | No rebuild while hidden; catch-up on show |
| MD-GUI-000.008.M03 | `us_swing/src/us_swing/gui/app_service.py` | Tick view signals batched every 250 ms |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-000.008 | App stays responsive while live ticks stream | Implemented |

---

## Design Decisions

- Only tick slots are batched; fills, user actions and other events still emit at once.
- The first tick in a quiet spell starts the timer, so a price shows within 250 ms.

---

## Issues Resolved

ISS-GUI-0009 — app freezes while live ticks stream.

---

## Test Coverage

5 UT cases (UT-GUI-000.008.M01.T01–T02, M02.T01, M03.T01–T02) in `tests/gui/` — all Pass, all fail on the pre-fix code. 6 existing tick tests now flush before checking signals.
