Verify cross-document consistency for all artifacts in a tool directory. Read-only — reports issues, does not auto-fix.

Usage: /project:doc-check <TOOL>
Example: /project:doc-check SCR — reads all SCR docs, checks ID cross-references, SRD status guard compliance, TRACE.md coverage, and ID numbering gaps; outputs a PASS/FAIL checklist

$ARGUMENTS

Steps:
0. Read `.claude/skills/dev-context.md` — artifact ID formats, SRD status guard rules, TRACE.md column structure
1. Read all six artifact files for the tool (in this order to build the reference map):
   - `us_swing/docs/<tool>/FO.md`
   - `us_swing/docs/<tool>/SRD.md`
   - `us_swing/docs/<tool>/DD.md`
   - `us_swing/docs/<tool>/MD.md`
   - `us_swing/docs/<tool>/UTCD.md`
   - `us_swing/docs/<tool>/TRACE.md`
2. Run the following checks and record PASS or FAIL with specific offending IDs:

   **Chain integrity**
   - [ ] Every SRD entry references a valid FO ID that exists in FO.md
   - [ ] Every DD entry references a valid SRD ID that exists in SRD.md
   - [ ] Every MD entry references a valid SRD ID that exists in SRD.md
   - [ ] Every UTCD entry references a valid MD ID that exists in MD.md

   **ID numbering**
   - [ ] No duplicate IDs within any artifact file
   - [ ] No numbering gaps (e.g. SRD-SCR-001.001 exists but SRD-SCR-001.002 is missing while SRD-SCR-001.003 exists)

   **SRD status guard**
   - [ ] No SRD with status `Draft` or `Reopen` has a corresponding code file referenced in MD.md
   - [ ] All SRDs with status `Implemented` or `Verified` appear in TRACE.md

   **TRACE.md coverage**
   - [ ] Every FO ID in FO.md has at least one row in TRACE.md
   - [ ] No TRACE.md row has an empty FO, SRD, or MD cell (DD may be sparse for simple modules)
   - [ ] All `Verified` TRACE rows have an RN entry

   **File existence spot-check**
   - [ ] For each MD row, confirm the listed source file path exists under `us_swing/src/usswing/<tool>/`
   - [ ] For each RN ID in TRACE.md, confirm the file exists under `us_swing/docs/<tool>/revisions/`

3. Output a formatted checklist:
   ```
   DOC-CHECK RESULTS — <TOOL> — <date>
   ══════════════════════════════════════
   Chain integrity
     [PASS] SRD→FO references    — all N SRDs reference valid FO IDs
     [FAIL] DD→SRD references    — DD-SCR-002.001.D01 references SRD-SCR-002.001 which does not exist
   ...
   ══════════════════════════════════════
   Summary: N checks passed, N failed
   Action needed: <list of IDs to fix, or "None">
   ```
4. If ALL checks pass: state "All consistency checks passed — no action needed"
5. Do NOT modify any files. Do NOT update CONTEXT.md or DEVLOG.md.
   If the user wants fixes applied, they should run the relevant `/project:*` command or ask explicitly.
