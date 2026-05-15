Sync the TRACE.md traceability matrix for a tool after any phase completes.

Usage: /trace <TOOL>
Example: /trace EXE — reads all EXE artifact docs, fills missing cells in TRACE.md (FO→SRD→DD→MD→UT→Status→RN), and reports every row added or updated

$ARGUMENTS

Steps:
0. Read `.claude/skills/dev-context.md` — artifact ID formats and TRACE.md column structure
1. Read `us_swing/docs/<tool>/TRACE.md` — capture current state; note which rows exist and which cells are empty
2. Read `us_swing/docs/<tool>/FO.md` — collect all FO IDs
3. Read `us_swing/docs/<tool>/SRD.md` — map each SRD to its parent FO; note status
4. Read `us_swing/docs/<tool>/DD.md` — map each DD item to its parent SRD
5. Read `us_swing/docs/<tool>/MD.md` — map each module to its parent SRD
6. Read `us_swing/docs/<tool>/UTCD.md` — map each UT case to its parent MD module
7. For each FO ID:
   a. Find all SRD rows that reference it
   b. Find DD, MD, UT IDs that chain from each SRD
   c. Determine Status: use the lowest phase completed across that chain
      - `Draft` if any SRD is Draft
      - `Approved` if all SRDs Approved but no code
      - `Implemented` if code exists but no tests pass
      - `Verified` if all linked UTs pass
   d. Fill RN column if a revision note file exists in `us_swing/docs/<tool>/revisions/`
8. Write the updated TRACE.md — preserve existing verified rows, only add or fill cells
9. Report: list every row added and every cell updated (e.g. "FO-EXE-001: added UT column, updated Status Draft→Implemented")
10. Do NOT update CONTEXT.md or DEVLOG.md — trace sync is a narrow artifact task
