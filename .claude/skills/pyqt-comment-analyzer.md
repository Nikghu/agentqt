Analyze PyQt6 code comments for accuracy, completeness, and comment rot. Advisory only — does not edit files.

**Invoke only when `pyqt-code-reviewer` explicitly flags comment issues.**
**Skip when reviewer did not flag comments — do not run speculatively.**

$ARGUMENTS

## Analysis Framework

Work inline — read the flagged file, apply the checks below, report findings back.

### 1. Factual Accuracy
- Verify claims against the actual code
- Check parameter and return descriptions against implementation
- Flag outdated references to signals, slots, or widget behavior

### 2. Completeness
- Check whether complex logic has enough explanation
- Verify important side effects and edge cases are documented
- Ensure public APIs and custom signals have clear descriptions

### 3. Long-Term Value
- Flag comments that only restate the code (low-value)
- Identify fragile comments that will rot quickly
- Surface TODO / FIXME / HACK debt

### 4. Misleading Elements
- Comments that contradict the code
- Stale references to removed behavior
- Over-promised or under-described behavior

## Output Format

Report findings grouped by severity. Do not edit any files — report only.

**Severity levels:** `Inaccurate` · `Stale` · `Incomplete` · `Low-value`

After reporting, the main agent applies fixes and re-runs `pyqt-code-reviewer`.
