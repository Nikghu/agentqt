# ISS-EXE-0015 — Disabled strategies vanish from the Strategies list

**Date:** 2026-11-22
**Tool:** EXE (seen in GUI Strategies tab)
**Status:** Fixed (code), app check pending (TODO T224)

## Symptom

BOSS_Short_New and BOSS_Long_New (used in backtests on 2026-11-16) were gone from the Strategies tab. Earlier, BOSS_Long and another BOSS strategy were lost the same way.

## Root cause

The strategy engine saved its status by replacing the whole strategies table with the strategies it held in memory. The engine never holds Disabled strategies, and did not hold new ones until it reloaded. On 2026-11-20 11:47:02 ET (a broker cancel of an EW sell) the table was rewritten and every Disabled strategy was deleted. The same rewrite could also put back old rules for an edited or deleted strategy.

## Fix

- The engine status save updates only each strategy's run state (`set_run_state`), never the whole table.
- The Strategies tab reloads the engine after adding or deleting a strategy.

The deleted rules could not be recovered (backups are older; deleted rows are overwritten).

## Tests

UT-EXE-011.001.M01.T08.
