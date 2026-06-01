# USMarket Swing Trading Toolkit — Claude Instructions

**Active project:** `us_swing`. Do NOT work on `pilot1` unless explicitly directed.
**ToDo Backlog:** Maintain the running task list in `us_swing/TODO.md` — add/close rows each session; keep descriptions ≤50 words with module + priority.

## Step 1 — Classify Every Prompt First

Classify before reading any file, then **emit a one-line classification header** as your very first output:

```
[Class: <Q|N|D|S> · Tool: <TOOL|N/A> · Phase: <Phase|N/A>]
```

Examples: `[Class: D · Tool: EXE · Phase: Code]` · `[Class: Q · Tool: N/A · Phase: N/A]`

| Class | Trigger | Action |
|-------|---------|--------|
| **Q** | General question, no project work needed | Read nothing |
| **N** | Status check, "what's next?", navigation | Read `AGENT_BOOT.md` §2 only |
| **D** | Code, docs, tests, bug fix, any dev task | Read `AGENT_BOOT.md` §2–§4, then active tool docs only |
| **S** | First prompt of a new session | Read full `AGENT_BOOT.md` once |

Never read `requirements.md`, `idea.md`, `process.md`, or `skill.md` unless `AGENT_BOOT.md` §5 directs you to.

## Step 2 — Evaluate Before Acting (Class D and S)

Before executing any **Class D or S** prompt, delegate to the `prompt-evaluator` agent (`.claude/agents/prompt-evaluator.md`, runs on Sonnet):

1. Pass the raw prompt to the agent
2. The agent classifies, identifies the active tool and artifact phase, checks clarity, and returns a reframed structured prompt with scoped file reads
3. If the agent asks clarifying questions — stop and surface them to the user before proceeding
4. Only act on the **reframed prompt**, not the original

Skip this step for **Class Q and N** — those are lightweight and need no reframing.

## Session-End Rule

Update `us_swing/CONTEXT.md` §0 and prepend to `us_swing/DEVLOG.md` before finishing every session.

## Date Handling

If `currentDate` appears stale, flag in session-end note. Do not modify `CLAUDE.md`.

## Plan Mode

- Multi-artifact or uncertain scope → plan mode first.
- Single-artifact, fully scoped → direct execution.

## Always-On Rules

The following `.claude/rules/` files are loaded automatically and apply to every coding task:

- `.claude/rules/code-style.md` — ruff, mypy, package layout, file headers, commit convention
- `.claude/rules/testing.md` — pytest conventions, UTCD IDs, coverage gates, no DB mocking
- `.claude/rules/artifact-conventions.md` — FO→SRD→DD→MD→UTCD→Code→RN chain, ID formats, SRD status guard, DoD checklist
- `.claude/rules/traceability.md` — TRACE.md structure and update rules
- `.claude/rules/logging.md` — user-facing log message language, level guidelines, `[Topic]` prefix convention

## Custom Slash Commands

Available via `/project:<name>`:

| Command | Purpose |
|---|---|
| `/project:write-tests` | Implement UTCD tests for a module |
| `/project:new-feature` | Start new feature from FO through UTCD |
| `/project:auto-feature` | Fully automated FO → RN pipeline — no human gates, SRD approval auto-set |
| `/project:fix-issue` | Diagnose and fix a bug with full artifact trail |
| `/project:refactor` | Refactor or enhance a module safely |
| `/project:finish` | Close the session — writes RN, syncs TRACE + CONTEXT + DEVLOG, optional Git PR → merge |
| `/project:review` | Architecture review before implementing a tool |
| `/project:trace` | Sync TRACE.md after any phase completes — fills all FO→RN columns |
| `/project:rn` | Draft and write a Revision Note for a tool after implementation or fix |
| `/project:doc-check` | Read-only consistency check across all tool docs — IDs, cross-refs, SRD status guard |
| `/project:hookify` | Scan conversation for PyQt6 behavior patterns and write hook rules to settings.json — periodic maintenance only |
| `/project:workspace` | Load full workspace folder orientation — tree, layout, conventions |
| `/project:pyqt-comment-analyzer` | Analyze PyQt6 comments for accuracy and comment rot — advisory only, invoke when pyqt-code-reviewer flags comments |
| `/project:push-updates` | Publish a GitHub release after building the installer — creates tag, uploads .exe + .sha256, patches manifest |

## Maintenance

`CLAUDE.md` is updated by the user only, not by the AI agent.
