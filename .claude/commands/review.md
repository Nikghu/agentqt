Architecture review before implementing a new tool or major module.

Usage: /project:review <TOOL>
Example: /project:review SCR — reviewing the Screener docs before starting implementation

Before implementing $ARGUMENTS, read in this order:
0. `.claude/skills/workspace.md` — folder layout and project convention
1. `.claude/skills/dev-context.md` — process rules, artifact formats, doc rules
2. `us_swing/docs/<tool>/FO.md` — understand objectives
3. `us_swing/docs/<tool>/SRD.md` — scan `Approved` requirements only (skip `Draft`)
4. `us_swing/docs/<tool>/MD.md` — list all modules and their file paths
5. `us_swing/docs/<tool>/UTCD.md` — count tests and confirm scope
6. `us_swing/docs/<tool>/TRACE.md` — check what is already implemented vs remaining

Then summarize:
- First module to implement (lowest MD ID with no `Implemented` status)
- INF/core dependencies required
- Total test count and how many are `Not Run`
- Any `Approved` SRDs blocked by missing dependencies
