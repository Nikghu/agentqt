Draft and write a Revision Note for a tool after implementation, fix, or refactor.

Usage: /project:rn <TOOL> <version>
Example: /project:rn EXE 1.0.0 — produces RN-EXE-1.0.0-20260423.md in us_swing/docs/execution/revisions/, updates TRACE.md RN column, and appends a one-line entry to DEVLOG.md

$ARGUMENTS

Steps:
0. Read `.claude/skills/dev-context.md` — RN ID format and storage location
1. Determine today's date (use `currentDate` from context). Compose the RN ID: `RN-<TOOL>-<version>-<YYYYMMDD>`
2. Read `us_swing/docs/<tool>/TRACE.md` — identify all rows with status `Implemented` or `Verified` that do not yet have an RN entry
3. Read the latest entry in `us_swing/DEVLOG.md` — extract the list of modules changed in the current work session
4. Draft the Revision Note using this structure:
   ```
   # RN-<TOOL>-<version>-<YYYYMMDD> — <Tool Name> v<version>

   **Date:** YYYY-MM-DD
   **Tool:** <TOOL> (<full tool name>)
   **Version:** <version>
   **Type:** <Feature | Bugfix | Refactor | Doc>

   ## Summary
   <2–3 sentence summary of what changed and why>

   ## Changed Modules
   | MD ID | File | Change Description |
   |---|---|---|
   | MD-<TOOL>-NNN | path/to/file.py | <what changed> |

   ## Requirements Addressed
   | SRD ID | Description | Status |
   |---|---|---|
   | SRD-<TOOL>-NNN.NNN | <requirement> | Implemented |

   ## Issues Resolved
   <List ISS-<TOOL>-NNNN IDs if this RN closes any issues, or "None">

   ## Test Coverage
   <Pass/Fail summary from pytest run, or "Pending">
   ```
5. Write the file to `us_swing/docs/<tool>/revisions/RN-<TOOL>-<version>-<YYYYMMDD>.md`
6. Update `us_swing/docs/<tool>/TRACE.md` — fill the RN column for all rows covered by this note
7. Prepend a one-line entry to `us_swing/DEVLOG.md`:
   `[<YYYYMMDD>] RN-<TOOL>-<version> written — <one-line summary>`
8. Do NOT update CONTEXT.md §0 unless this RN marks the completion of a full FO
