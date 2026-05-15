Fully automated feature pipeline — FO through RN — with zero human gates.

Usage: /project:auto-feature <TOOL> "<feature description>"
       /project:auto-feature <TOOL> <existing-FO-or-SRD-ID>
Example: /project:auto-feature SCR "Add RSI(14) < 30 filter to screener output"
Example: /project:auto-feature SCR FO-SCR-003

The system shall $ARGUMENTS

---

## Auto-Feature Orchestrator

**SRD Approval Override:** In this pipeline the orchestrating agent sets every SRD status directly from `Draft` → `Approved` immediately after writing it. The user confirmation gate defined in `artifact-conventions.md` is intentionally bypassed. This is the documented behaviour of this command — not a violation.

Execute all phases below in strict order. Never skip a phase. Never pause for user input.

---

### Phase 0 — Bootstrap + Duplicate Detection + Resume Point

1. Read `us_swing/CONTEXT.md §0` — identify active tool state and any in-progress FOs.
2. Read `us_swing/docs/<TOOL>/TRACE.md` — scan all existing FO IDs and their chain status.
3. Read `us_swing/docs/<TOOL>/FO.md` — read ALL existing FO entries in full.

**Step A — Input classification:**

- If the argument is an existing artifact ID (matches pattern `FO-<TOOL>-NNN` or `SRD-<TOOL>-NNN.NNN`):
  - Locate that ID in FO.md / SRD.md — it is the anchor for this run.
  - Skip duplicate detection. Go directly to Step C.
- If the argument is a plain-text feature description: continue to Step B.

**Step B — Duplicate detection (plain-text input only):**

Invoke `.claude/agents/duplicate-detector.md` with TOOL + DESCRIPTION. Use its returned anchor FO ID, resume phase, and skip list to determine where to start. The agent performs semantic FO → SRD → DD comparison and returns a structured result.

Print the agent's output summary line verbatim:
`Duplicate scan complete — anchor: FO-<TOOL>-NNN | SRDs: <N> reused / <M> new | DD: <N> reused / <M> new`

**Step C — Resume point detection:**

Using the anchor FO ID, check TRACE.md row by row to find the first incomplete phase:

| What exists in TRACE for this FO | Resume at |
|---|---|
| FO only (no SRD row) | Phase 2 — write SRD |
| FO + SRD (no DD) | Phase 3 — write DD |
| FO + SRD + DD (no MD) | Phase 4 — write MD |
| FO → MD (no UTCD) | Phase 5 — write UTCD |
| FO → UTCD (no code files) | Phase 6 — implement code |
| FO → code (no tests) | Phase 7 — write tests |
| FO → tests (TRACE not updated) | Phase 8 — update TRACE |
| FO → TRACE (no RN) | Phase 9 — write RN |
| FO → RN (CONTEXT not updated) | Phase 10 — session artifacts |
| Fully complete | Print "FO-<TOOL>-NNN is already complete." and stop. |

Print a one-line note: `Resuming from Phase <N> — skipping Phases 0–<N-1>.` then jump to that phase.

---

### Phase 1 — FO (Functional Objective)

4. Assign next `FO-<TOOL>-NNN` ID.
5. Write the FO entry to `us_swing/docs/<TOOL>/FO.md`:
   - One-sentence testable outcome (non-technical, user-visible)
   - 2–4 acceptance criteria
   - Status: `Approved`
6. (Validator deferred — runs once after all phases written, see Phase 5a.)

---

### Phase 2 — SRD (Software Requirements)

7. Decompose the FO into 2–6 `SRD-<TOOL>-NNN.NNN` requirements.
8. Write all SRD rows to `us_swing/docs/<TOOL>/SRD.md` using the compact table format:
   `| ID | Parent FO | Priority | Description | Inputs | Outputs | Constraints |`
9. **Immediately set every new SRD status to `Approved`** — do not leave any row in `Draft`.

---

### Phase 3 — DD (Design Document)

11. For each SRD, write one or more `DD-<TOOL>-NNN.NNN.DNN` design items to `us_swing/docs/<TOOL>/DD.md`.
12. Each DD item covers: component, interface signature, data flow, external dependencies.
13. **If TOOL is `GUI`:** spawn `pyqt-architect` agent with the FO + SRD summary. Use its output as the DD blueprint. Apply the frameless-window pattern and `C.BTN_H` / `C.INPUT_H` constants.

---

### Phase 4 — MD (Module Decomposition)

15. Assign `MD-<TOOL>-NNN.NNN.MNN` IDs — one module per cohesive responsibility.
16. Write all MD rows to `us_swing/docs/<TOOL>/MD.md` using compact table format:
    `| ID | Parent SRD | File Path | Responsibility | Public API | Deps | MCP Exposed |`
17. File paths follow `us_swing/src/usswing/<tool>/` layout.

---

### Phase 5 — UTCD (Unit Test Case Definitions)

19. For every `Must`-priority SRD: write ≥ 1 positive test + ≥ 1 negative test.
20. For every `Should`-priority SRD: write ≥ 1 positive test.
21. Write all UT rows to `us_swing/docs/<TOOL>/UTCD.md` using compact table format:
    `| ID | Module | Type | Objective | Input | Expected Output | Status |`
22. All new rows start with `Status: Not Run`.

---

### Phase 5a — Validator + Pre-Code Phase Gate

23. Invoke `.claude/agents/artifact-validator.md` ONCE — TOOL + PHASES: `FO,SRD,DD,MD,UTCD` + IDs (all new IDs across phases). Must return GO before continuing.
    - If BLOCKED: fix the listed IDs, then re-invoke validator with PHASES limited to the fixed phase(s).
24. Invoke `.claude/agents/phase-gate.md` with TOOL + FO ID.
    - If GO: proceed to Phase 6.
    - If BLOCKED: fix all listed blockers, then re-run `phase-gate` until GO.

---

### Phase 6 — Code Implementation

For each MD module (process sequentially — one module at a time):

19. Write the source file to the path defined in MD.
20. File must open with the module header:
    ```python
    """
    Module: MD-<TOOL>-NNN.NNN.MNN — <Module Name>
    Parent SRD: SRD-<TOOL>-NNN.NNN
    """
    ```
21. All public functions/methods must have type annotations and Google-style docstrings.
22. Code must be compatible with `ruff check` + `mypy --strict`.
23. **Post-code review (mandatory — no exceptions):**
    - If the file is a PyQt6/GUI module → spawn `pyqt-code-writer` agent to implement, then `pyqt-code-reviewer` as safety net.
    - Otherwise → spawn `code-reviewer` agent.
    - If reviewer returns CRITICAL or HIGH issues → fix immediately, re-run reviewer.
    - If reviewer flags complexity MEDIUM+ → spawn `pyqt-code-simplifier`, then re-run reviewer.
24. After all reviewer issues are resolved → set the parent SRD status to `Implemented`.

---

### Phase 7 — Tests

25. Spawn `test-writer` agent with: UTCD.md path + MD.md path + source file paths.
26. Test files land in `us_swing/tests/<tool>/test_<module>.py` (one file per source module).
27. Every test function docstring must reference its UT ID: `UT-<TOOL>-NNN.NNN.MNN.TNN: <objective>`.
28. After tests are written, update `Status` column in UTCD.md: `Not Run` → `Pass` (if tests pass) or `Fail`.

---

### Phase 8 — TRACE Update

29. Update `us_swing/docs/<TOOL>/TRACE.md` — add one row per FO/SRD/DD/MD/UT chain.
30. No cell may be empty. Every row must trace: `FO → SRD → DD → MD → UT ID(s) → Status → RN`.
31. RN column: leave as `Pending` — it will be filled in Phase 9.

---

### Phase 9 — Revision Note

32. Write `us_swing/docs/<TOOL>/revisions/RN-<TOOL>-<version>-<YYYYMMDD>.md`.
33. Version: bump `PATCH` if bugfix or minor addition; bump `MINOR` if new FO introduced.
34. RN must include: summary, FO/SRD IDs covered, modules created/modified, test count, known limitations.
35. Update the `RN` column in TRACE.md with the RN ID.

---

### Phase 10 — Session Artifacts

36. Invoke `.claude/agents/session-finalizer.md` with TOOL + FO ID + one-line feature summary + type: feature — handles TRACE sync, CONTEXT.md §0 update, and DEVLOG entry automatically.
37. Create a single git commit:
    ```
    feat(<TOOL>): <short summary of the feature>

    Refs: <comma-separated MD IDs>
    ```

---

## Orchestration Rules

- **Never pause** between phases for user confirmation — execute all 10 phases end-to-end.
- **Never skip** a phase — partial chains are forbidden by the artifact conventions.
- **Spawn agents sequentially** — each phase may depend on artifacts from the prior phase.
- **SRD override is explicit** — `Draft → Approved` is set by this command, not the user. This is intentional.
- If any tool command (`ruff`, `mypy`, `pytest`) is available in the environment, run it after Phase 6 and 7 respectively. Report results but do not block on failures — note them in the RN instead.
