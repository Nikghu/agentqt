Diagnose and fix a bug in the us_swing project.

Usage: /project:fix-issue <module_or_function> — Expected: <what should happen>. Actual: <what happens instead>.
Example: /project:fix-issue cache.get() — Expected: fetch missing days and merge when requested end_date > cached end_date. Actual: returns cached subset silently without re-fetching — creates ISS-INF-NNNN, applies fix, verifies with pytest, writes Revision Note

$ARGUMENTS

Steps:
0. Read `.claude/skills/dev-context.md` — process rules, artifact formats, doc rules
1. Read the relevant source file and its MD entry in `us_swing/docs/<tool>/MD.md`

1a. SRD dependency check:
    - Read `us_swing/docs/<tool>/SRD.md` — find all SRD rows whose Parent FO/scope covers the buggy module (use the MD Parent SRD field as the link).
    - Determine root cause category:

    | Root cause | Action |
    |---|---|
    | Code diverged from an Approved SRD | Fix code only — SRD stays Approved, no cascade needed |
    | SRD itself describes the wrong behaviour | Set SRD status → `Reopen`, fix SRD first, then cascade (see 1b) |
    | Bug is in a scope gap — no SRD covers this case | Write a new SRD row for the missing case (status → `Approved`), then fix code |

    Print: `SRD root cause: <code diverged | SRD wrong | scope gap> — <SRD-<TOOL>-NNN.NNN>`

1b. Cascade check (only if SRD was Reopened or a new SRD row was added):
    - Read `us_swing/docs/<tool>/DD.md` — update any DD item that described the incorrect behaviour.
    - Read `us_swing/docs/<tool>/UTCD.md` — update any test case whose Expected Output was written against the wrong behaviour. Mark updated rows `Status: Not Run`.
    - Complete all artifact updates before touching any source code.
    - Invoke `.claude/agents/artifact-validator.md` for each artifact phase updated (SRD / DD / UTCD). All must return GO before proceeding.

2. Read existing tests in `us_swing/tests/<tool>/test_<module>.py`
3. Reproduce the issue by tracing the code path
4. Propose the fix with reasoning
5. Implement the fix
5a. Post-fix review — invoke `.claude/agents/pyqt-code-reviewer.md` if the fixed file is GUI/PyQt6, or `.claude/agents/code-reviewer.md` if non-GUI. Fix any BLOCK issues before continuing.
6. Run `pytest us_swing/tests/ -q` and confirm the failing test now passes
7. Create an issue file at `us_swing/docs/<tool>/issues/ISS-<TOOL>-NNNN.md`
8. Write a Revision Note at `us_swing/docs/<tool>/revisions/`
9. Update TRACE.md — set Status of the affected SRD row to `Implemented` (or back to `Approved` if re-opened and re-fixed)
10. Invoke `.claude/agents/session-finalizer.md` with TOOL + affected FO IDs + one-line fix summary + type: bugfix — handles TRACE sync, CONTEXT.md §0 update, and DEVLOG entry
