Close the current work session: write the Revision Note, sync all session docs, and optionally deliver changes to Git.

Usage: /project:finish <TOOL> <version>
Example: /project:finish EXE 1.4.0

$ARGUMENTS

## Step 1 — Collect Inputs

Parse TOOL and VERSION from $ARGUMENTS. If either is missing, ask the user before continuing.

Then ask the user for the following (use AskUserQuestion if possible, otherwise prompt inline):
- **FO_IDS** — which FO IDs were worked on this session (e.g. `FO-EXE-008, FO-EXE-009`)
- **SUMMARY** — one sentence describing what was done this session
- **TYPE** — `feature`, `bugfix`, or `refactor`

If the user skips any of these, infer them from `us_swing/CONTEXT.md §0` and the most recent `us_swing/DEVLOG.md` entry.

---

## Step 2 — Run Session Finalizer

Spawn the `session-finalizer` agent with these inputs:

```
TOOL:     <TOOL>
VERSION:  <version>
FO_IDS:   <FO_IDS>
SUMMARY:  <SUMMARY>
TYPE:     <TYPE>
```

Wait for the agent to complete. Display its full output report to the user.

---

## Step 3 — Git Delivery (Optional)

After the agent completes, ask the user:

> **"Push these changes to Git?"**
> Options: Yes · No

### If No — stop here. Session is closed.

### If Yes — run the full delivery flow:

**a. Determine branch name**
```
docs/<tool>-<version>
```
Example: `docs/exe-1.4.0`

**b. Stage only session-close files**
```powershell
git checkout -b docs/<tool>-<version>
git add us_swing/docs/<tool>/revisions/RN-<TOOL>-<version>-<YYYYMMDD>.md
git add us_swing/docs/<tool>/TRACE.md
git add us_swing/CONTEXT.md
git add us_swing/DEVLOG.md
```

**c. Commit**

Use this message format (HEREDOC via PowerShell):
```
docs(<tool>): session close — <SUMMARY>

RN: RN-<TOOL>-<version>-<YYYYMMDD>
FO(s): <FO_IDS>
Type: <TYPE>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

**d. Push**
```powershell
git push -u origin docs/<tool>-<version>
```

**e. Create PR**
```powershell
gh pr create `
  --title "docs(<tool>): session close v<version> — <SUMMARY>" `
  --body "## Session Close\n\n**RN:** RN-<TOOL>-<version>-<YYYYMMDD>\n**FO(s):** <FO_IDS>\n**Type:** <TYPE>\n\n## Files\n- Revision Note\n- TRACE.md\n- CONTEXT.md\n- DEVLOG.md\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)" `
  --base main
```

**f. Merge and delete branch**
```powershell
gh pr merge --merge --delete-branch
```

---

## Step 4 — Final Report

Output a concise summary:

```
FINISH COMPLETE
───────────────────────────────────────────
Session docs  : RN + TRACE + CONTEXT + DEVLOG written
Git           : PR merged → main  (branch docs/<tool>-<version> deleted)
               — or —
Git           : skipped (user declined)
───────────────────────────────────────────
```
