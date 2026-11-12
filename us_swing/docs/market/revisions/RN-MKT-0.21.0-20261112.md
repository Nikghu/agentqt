# Revision Note — RN-MKT-0.21.0-20261112

**Version:** 0.21.0
**Date:** 2026-11-12
**Tool:** MKT
**Artifact:** FO-MKT-019, FO-DSK-010 (SRD-DSK-010.016), FO-GUI-040 / SRD-MKT-019.001–.014, SRD-DSK-010.016, SRD-GUI-040.001–.004
**Type:** Feature

---

## Summary

The strategy test research skill (`emp-017`, "Expert 14") tests one strategy card on all Backtest Data daily bars for S&P 500 members. Code checks the AI recipe, runs a 2R replay with a 10-day exit, compares it with a fixed baseline and passes a card only with at least 30 trades, average R above 0.2 and above the baseline. The Master can raise a test from the AI Desk Cards tab, which is new in the GUI. The lead plan now lists untested cards.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-MKT-019.001.M01 | `us_swing/src/us_swing/market/strategy_test.py` | New research skill: recipe, check, replay, verdict steps, save, lesson and logs |
| MD-MKT-019.003.M02 | `us_swing/src/us_swing/market/card_recipe.py` | New recipe model, daily block menu and recipe check |
| MD-MKT-019.005.M03 | `us_swing/src/us_swing/market/card_replay.py` | New replay on Backtest Data, fixed baseline and pass rule |
| MD-MKT-019.009.M04 | `us_swing/src/us_swing/core/desk_cards.py` | New cards and `card_tests` store, open tests and lead untested block |
| MD-MKT-019.009.M04 | `us_swing/src/us_swing/market/lead_brief.py` | Lead plan facts add the untested cards block (SRD-MKT-019.011) |
| MD-MKT-019.012.M05 | `us_swing/src/us_swing/market/employees/emp-017/employee.md` | New default strategy test employee `emp-017` |
| MD-MKT-019.012.M05 | `us_swing/src/us_swing/core/desk_steps.py` | `strategy_test` skill path added to `SKILL_PATHS` |
| MD-MKT-019.012.M05 | `USSwing.spec` | Build includes the strategy test skill and employee files |
| MD-DSK-010.001.M25 | `us_swing/src/us_swing/core/desk_research.py` | `raise_owner_test` raises an approved `strategy_test` ticket for one card (SRD-DSK-010.016) |
| MD-GUI-040.001.M01 | `us_swing/src/us_swing/gui/ai_desk_cards.py` | New Cards section: card table, detail, latest test, Test button and its log |
| MD-GUI-034.009.M08 | `us_swing/src/us_swing/gui/ai_desk.py` | Cards section added to the REVIEW group with live refresh |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-MKT-019.001 | The strategy test skill works tickets in four steps: recipe, check, replay and verdict | Implemented |
| SRD-MKT-019.002 | A topic naming a missing card ends the ticket `failed` | Implemented |
| SRD-MKT-019.003 | The recipe call returns side, entry blocks, entry type, stop type and unmapped parts | Implemented |
| SRD-MKT-019.004 | Code checks every block and setting; unknown parts end the ticket `failed` | Implemented |
| SRD-MKT-019.005 | The replay runs the recipe on all Backtest Data daily bars of S&P 500 members | Implemented |
| SRD-MKT-019.006 | The baseline uses the same exit on a fixed sample without the entry blocks | Implemented |
| SRD-MKT-019.007 | Code scores the test and passes it only at 30+ trades, average R above 0.2 and above the baseline | Implemented |
| SRD-MKT-019.008 | The verdict call writes 2 to 3 short lines | Implemented |
| SRD-MKT-019.009 | The test is saved in `card_tests`; gain is yes only on a pass | Implemented |
| SRD-MKT-019.010 | A passing card adds one candidate lesson, never active by itself | Implemented |
| SRD-MKT-019.011 | The lead plan lists cards not yet tested and the strategy test topic form | Implemented |
| SRD-MKT-019.012 | Default employee `emp-017` ships with its skill path in `SKILL_PATHS` and the app build | Implemented |
| SRD-MKT-019.013 | The skill never changes a live strategy, setting, signal or trade | Implemented |
| SRD-MKT-019.014 | Each step logs the card, the step and its outcome | Implemented |
| SRD-DSK-010.016 | The Master user can raise a `strategy_test` ticket for one card; approved at once, paid by the lead | Implemented |
| SRD-GUI-040.001 | AI Desk has a Cards tab listing strategy cards with latest test result, trades and average R | Implemented |
| SRD-GUI-040.002 | Selecting a card shows its details, latest test table and verdict | Implemented |
| SRD-GUI-040.003 | A Test button raises a `strategy_test` ticket for the selected card | Implemented |
| SRD-GUI-040.004 | Each Test click and its outcome is logged | Implemented |

---

## Design Decisions

- Pass rule is set in code only: at least 30 trades, average R above 0.2 and above the baseline. The AI never changes pass or fail.
- Replay uses daily bars only and one open trade per stock at a time; nothing is read from `candles.db`.
- Entries that gap past the stop at the next open are skipped by design.
- Owner ticket cap is 20,000 tokens; the replay is limited to 10 minutes.
- A passing card adds a candidate lesson only; the skill never changes a live strategy.

---

## Issues Resolved

None

---

## Test Coverage

- UT-MKT-019.* (36 cases): Pass
- UT-DSK-010.016.M25.T01–T03 (3 cases): Pass
- UT-GUI-040.* (6 cases): Pass
- Market, desk and core suites: 1177 pass. AI Desk GUI tests: 109 pass. ruff clean; mypy clean on new files.
- Real-data timing: loading 500 stocks about 16 s; replay about 15–30 s.
- Sample results: RSI ≤ 35 on 40 stocks, 655 trades, +0.17R, fail. Bull flag, 60 trades, +0.21R, pass.
- User check T171 pending (needs a strategy card first, T168).
