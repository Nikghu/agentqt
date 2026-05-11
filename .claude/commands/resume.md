Resume the current session for the us_swing project.

Usage: /project:resume
Example: /project:resume — loads AGENT_BOOT.md, reads CONTEXT.md §0 to surface the next pending task (e.g. "Implement EXE module oms.py — 8 SRDs Approved, 0 tests written")

Steps:
1. Read `AGENT_BOOT.md` (status + pointers)
2. Read `.claude/skills/workspace.md` (folder layout + project convention)
3. Read `.claude/skills/dev-context.md` (process rules, doc rules, reading guide)
4. Read `us_swing/CONTEXT.md` §0 (Immediate Next Step) and §2 (Artifact Status)
5. Confirm active project: `us_swing`
6. State the next task from §0 and confirm you are ready to proceed

$ARGUMENTS
