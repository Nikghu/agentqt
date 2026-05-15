# RN-AGT-1.0.0-20260511 — Agent Framework v1.0.0

**Date:** 2026-05-11
**Tool:** AGT (Agent Framework)
**Version:** 1.0.0
**Type:** Refactor

## Summary

Introduced a dedicated `.claude/skills/` folder to separate agent-invoked inline skills from user-triggered slash commands in `.claude/commands/`. Four existing commands (`dev-context`, `workspace`, `hookify`, `trace`) were reclassified and moved to skills. A new `code-writer` skill was added to embed PyQt6 and Python coding patterns inline, reducing dependency on the `pyqt-code-writer` agent for smaller writes. `pyqt-comment-analyzer` was also migrated from commands to skills to reflect its auto-invoke nature.

## Changed Files

| File | Change |
|---|---|
| `.claude/skills/dev-context.md` | Moved from `commands/` — process + doc rules, auto-loaded Class D/S |
| `.claude/skills/workspace.md` | Moved from `commands/` — folder layout, loaded on demand |
| `.claude/skills/hookify.md` | Moved from `commands/` — periodic hook maintenance |
| `.claude/skills/trace.md` | Moved from `commands/` — TRACE.md sync, agent-invoked |
| `.claude/skills/pyqt-comment-analyzer.md` | Moved from `commands/` — comment rot detection |
| `.claude/skills/code-writer.md` | New — generic code writing skill with PyQt6 + Python rules |
| `AGENT_BOOT.md` | Updated §2 skills table, §7, §9, §10 registry — all skill references corrected |
| `.claude/agents/pyqt-code-reviewer.md` | Updated invocation reference for `pyqt-comment-analyzer` |
| `.claude/agents/prompt-evaluator.md` | Updated `dev-context` path to `skills/` |
| `.claude/commands/doc-check.md` | Updated `dev-context` path |
| `.claude/commands/fix-issue.md` | Updated `dev-context` path |
| `.claude/commands/new-feature.md` | Updated `dev-context` path |
| `.claude/commands/refactor.md` | Updated `dev-context` path |
| `.claude/commands/resume.md` | Updated `dev-context` + `workspace` paths |
| `.claude/commands/review.md` | Updated `dev-context` + `workspace` paths |
| `.claude/commands/rn.md` | Updated `dev-context` path |
| `.claude/commands/write-tests.md` | Updated `dev-context` path |
| `agentqt_templates/option_a/README.md` | Added `skills/` block, removed `trace` from commands table |
| `agentqt_templates/option_c/README.md` | Added `skills/` block, removed `trace` from commands table, updated `.claude/` description |
| `agentqt_templates/COMPARE.md` | Added `skills/` to Option A and Option C pre-built lists |

## Issues Resolved

None

## Test Coverage

N/A — framework configuration change, no production code modified
