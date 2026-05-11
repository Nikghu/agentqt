Start a new feature for the us_swing project following the full artifact chain.

Usage: /project:new-feature <tool> "<FO description>"
Example: /project:new-feature SCR "Filter stocks where RSI(14) < 30 AND daily volume > 2× 20-day average, returning DataFrame [symbol, rsi, volume_ratio, close]" — produces FO-SCR-NNN, SRD entries, DD design, MD modules, and UTCD test cases before any code is written

The system shall $ARGUMENTS

Steps (mandatory order — no skipping):
0. Read `.claude/skills/dev-context.md` — process rules, artifact formats, doc rules
0a. Invoke `.claude/agents/duplicate-detector.md` with TOOL + feature description — use the returned anchor FO ID and skip list before proceeding. If a full duplicate is found, stop and report to user.
1. Read `us_swing/docs/<tool>/FO.md` — understand existing FOs and assign next ID
2. Write the new FO entry with acceptance criteria
2a. Invoke `.claude/agents/artifact-validator.md` — Phase: FO, IDs: new FO ID. Must return GO before continuing.
3. Decompose into SRD requirements (status: Draft)
3a. Invoke `.claude/agents/artifact-validator.md` — Phase: SRD, IDs: new SRD IDs. Must return GO before continuing.
4. Write DD design items
   4a. If tool is `GUI` and the implementation path is not already specified in the DD: invoke `.claude/agents/pyqt-architect.md` to produce the design blueprint (files, signal flow, build order, widget layout). Covers both feature-level and new-tool scope.
4b. Invoke `.claude/agents/artifact-validator.md` — Phase: DD, IDs: new DD IDs. Must return GO before continuing.
5. Define MD modules with file paths and public API
5a. Invoke `.claude/agents/artifact-validator.md` — Phase: MD, IDs: new MD IDs. Must return GO before continuing.
6. Write UTCD test cases (before any code)
6a. Invoke `.claude/agents/artifact-validator.md` — Phase: UTCD, IDs: new UT IDs. Must return GO before continuing.
7. Present artifact summary and await user approval of SRDs before implementing
7a. Once user approves — invoke `.claude/agents/phase-gate.md` with TOOL + FO ID. Must return GO before writing any code.
8. Once phase-gate returns GO — implement:
   - GUI/PyQt6 modules → invoke `pyqt-code-writer` to write each file, then `pyqt-code-reviewer` as safety net
   - Non-GUI modules → Claude main implements, then `code-reviewer`
9. Invoke `.claude/agents/session-finalizer.md` with TOOL + FO ID + summary + type: feature
