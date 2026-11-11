# Revision Note — RN-MKT-0.15.0-20261111

**Version:** 0.15.0
**Date:** 2026-11-11
**Tool:** MKT
**Artifact:** FO-MKT-013 / SRD-MKT-013.001–.012
**Type:** Feature

---

## Summary

Step D of the autonomous desk, market side: intraday watchers now read 3-minute bars and headlines. They flag trigger hits, stop and target touches, volume spikes, gaps, SPY moves and new headlines. A default expert "Expert 9" (`emp-011`) judges each flag, and a default lead "Lead 3" (`emp-012`) writes check-in notes.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-MKT-013.001.M01 | `src/us_swing/market/watch.py` | New: reads today's bars; trigger, stop/target, volume, gap, SPY and headline watchers |
| MD-MKT-013.008.M02 | `src/us_swing/market/watch_flag.py` | New: flag skill; holds, watch or broken verdict |
| MD-MKT-013.010.M03 | `src/us_swing/market/checkin_note.py` | New: check-in skill; note at each check-in time |
| MD-MKT-013.011.M04 | `src/us_swing/market/employees/emp-011/`, `emp-012/` | New: default employees Expert 9 and Lead 3 |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-MKT-013.001 | Watchers read the latest 3-minute bars of plan stocks, open trades and SPY | Implemented |
| SRD-MKT-013.002 | Trigger watcher flags a listed idea when its bar reaches the trigger | Implemented |
| SRD-MKT-013.003 | Stop and target watcher flags open trades when a bar touches them | Implemented |
| SRD-MKT-013.004 | Volume watcher flags a last bar at least 3 times the 20-bar average | Implemented |
| SRD-MKT-013.005 | Gap watcher flags a first bar more than 3% from the previous close | Implemented |
| SRD-MKT-013.006 | Regime watcher flags SPY more than 1.5% up or down | Implemented |
| SRD-MKT-013.007 | News watcher flags new headlines every 15 minutes | Implemented |
| SRD-MKT-013.008 | Flag skill asks if the plan still holds | Implemented |
| SRD-MKT-013.009 | Flag answer is a typed form; broken raises an alert | Implemented |
| SRD-MKT-013.010 | Check-in skill writes a note of at most 600 characters | Implemented |
| SRD-MKT-013.011 | Default employees `emp-011` and `emp-012` ship when missing | Implemented |
| SRD-MKT-013.012 | Each flag answer logs the stock, kind and verdict | Implemented |

---

## Design Decisions

- Watchers add no data of their own; they read bars and headlines only.
- Expert 9 and Lead 3 use generic names; the Master may rename them.
- The code feed note is shown even when no AI answers.

---

## Issues Resolved

None

---

## Test Coverage

UT-MKT-013.* — 31 cases, all Pass. Full suite: 12 failed (same as TODO T112), plus the old collection error in `tests/screener/test_llm_claude_screener.py` (TODO T136).
