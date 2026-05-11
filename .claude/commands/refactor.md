Refactor or enhance an existing us_swing module.

Usage:
- Refactor: /project:refactor "<what to change> → <desired outcome>"
- Enhance: /project:refactor "Enhance <module>: Add <capability>. Input: <X>. Output: <Y>."

Examples:
- /project:refactor "Extract shared validation logic from screener/rule_engine.py into a reusable decorator in core/ — avoids duplication across SCR and ANA modules"
- /project:refactor "Enhance cache: Add 24-hour expiry — data older than 24 hours should be re-fetched automatically. Input: same symbol/date params. Output: same DataFrame schema."

$ARGUMENTS

Steps:
0. Read `.claude/skills/dev-context.md` — process rules, artifact formats, doc rules
1. Read the target module(s) and their MD entries
2. Check TRACE.md to understand what SRD requirements the module implements
3. Confirm refactor does not break any `Verified` SRD requirements
4. Implement the change
4a. Post-implementation review — invoke `.claude/agents/pyqt-code-reviewer.md` if changed files are GUI/PyQt6, or `.claude/agents/code-reviewer.md` if non-GUI. Fix any BLOCK issues before continuing.
5. Run `ruff check` + `mypy --strict` on changed files
6. Run `pytest us_swing/tests/ -q` — all existing tests must still pass
7. Update MD.md if module responsibilities or public API changed
8. Write a Revision Note
9. Invoke `.claude/agents/session-finalizer.md` with TOOL + affected FO IDs + one-line refactor summary + type: refactor — handles TRACE sync, CONTEXT.md §0 update, and DEVLOG entry
