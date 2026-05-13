Resume the current session for the us_swing project.

Usage: /project:resume
Example: /project:resume — loads AGENT_BOOT.md, reads CONTEXT.md §0 to surface the next pending task (e.g. "Implement EXE module oms.py — 8 SRDs Approved, 0 tests written")

Steps:
1. Read `AGENT_BOOT.md` (status + pointers)
2. Read `.claude/skills/workspace.md` (folder layout + project convention)
3. Read `.claude/skills/dev-context.md` (process rules, doc rules, reading guide)
4. Read `us_swing/CONTEXT.md` §0 (Immediate Next Step) and §2 (Artifact Status)
5. Run RAG context query via PowerShell:
   `$env:VOYAGE_API_KEY = [System.Environment]::GetEnvironmentVariable('VOYAGE_API_KEY','User'); python .claude/rag/resume_context.py`
   Read the output — it surfaces the most relevant recent DEVLOG sessions semantically.
   Use it to supplement §0 with historical decisions and patterns, not to replace it.
   If Qdrant DB is missing or the script errors, skip silently and continue.
6. Confirm active project: `us_swing`
7. State the next task from §0 and confirm you are ready to proceed

$ARGUMENTS
