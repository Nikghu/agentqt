# Development Context — Process, Doc Rules & Reading Guide

> **Load this file for any Class D or S task.** Contains the dev lifecycle, artifact rules,
> doc read/write rules, scoped reading guidance, and common commands.
> Invoked automatically by all `/project:*` commands and by the prompt-evaluator reframed output.

---

## Development Process

Every task: `FO → SRD → DD → MD → UTCD → Code → Tests → TRACE → RN → Update CONTEXT.md & DEVLOG.md` (no skipping).

**Plan mode:** Use when spanning multiple artifact types (e.g., FO + SRD) or uncertain scope. Direct execution for single-artifact, fully scoped tasks.  
**At session end:** Update active project `CONTEXT.md` (artifact status, decisions, issues) and prepend entry to `DEVLOG.md`.

### Artifact Rules

| Artifact | ID Pattern | Location | Key Rule |
|----------|-----------|----------|----------|
| Functional Objective | `FO-<TOOL>-NNN` | `docs/<tool>/FO.md` | Testable, non-technical outcomes |
| Software Requirement | `SRD-<TOOL>-NNN.NNN` | `docs/<tool>/SRD.md` | Links to parent FO. Use **compact table format** |
| Design Document | `DD-<TOOL>-NNN.NNN.DNN` | `docs/<tool>/DD.md` | Interfaces, data flow, MCP schema |
| Module Decomposition | `MD-<TOOL>-NNN.NNN.MNN` | `docs/<tool>/MD.md` | File path, API, deps. Use **compact table format** |
| Unit Test Cases | `UT-<TOOL>-NNN.NNN.MNN.TNN` | `docs/<tool>/UTCD.md` | Write BEFORE code. Use **compact table format** |
| Traceability Matrix | — | `docs/<tool>/TRACE.md` | Update after every phase |
| Revision Note | `RN-<TOOL>-VER-DATE` | `docs/<tool>/revisions/` | Mandatory final step |

### Tool Codes

`INF` (Infrastructure) · `SCR` (Screener) · `ANA` (Analysis) · `BKT` (Backtesting) · `EXE` (Execution) · `GUI` (Graphical Interface) · `MCP` (MCP Server) · `RPT` (Reporting)

### Code Rules

- Module header: `"""Module: MD-<TOOL>-NNN.NNN.MNN — <Name>\nParent SRD: SRD-<TOOL>-NNN.NNN"""`
- Google-style docstrings, full type hints
- Must pass `ruff` + `mypy --strict`
- Tests: `tests/<tool>/test_<module>.py`, docstring refs UT ID
- Commit: `<type>(<tool>): <summary>\nRefs: MD-<TOOL>-NNN.NNN.MNN`

### SRD Requirement Status Rules (Agent Guard)

| Status | Agent May Edit Content? | Agent May Implement? |
|---|---|---|
| `Draft` | **Yes** | No — must be Approved first |
| `Approved` | No | **Yes** — implement, then set → `Implemented` |
| `Implemented` | No | N/A |
| `Verified` | No (frozen) | N/A |
| `Reopen` | **Yes** | No — must be re-Approved first |

### Compact Document Format

For SRD, MD, UTCD — prefer tables over prose:
- **SRD:** `| ID | Parent | P | Description | In | Out | Constraints |`
- **MD:** `| ID | Parent SRD | File | Responsibility | Public API | Deps | MCP |`
- **UTCD:** `| ID | Module | Type | Objective | Input | Expected Output |`

---

## Documentation Read/Write Rule

> **All artifact reads and writes must use `<project>/docs/<tool>/` exclusively.**

| Operation | Rule |
|-----------|------|
| **Read** | Only from `docs/<tool>/<artifact>.md` for the **specific tool you are actively working on**. Do not read docs for other tools unless the task explicitly spans them. |
| **Write** | Only to `docs/<tool>/<artifact>.md`. Never create or edit documentation outside this folder. |
| **Forbidden** | Never read or modify `requirements.md`, `idea.md`, or any root-level `.md` as a documentation source. They are frozen reference documents. |

### Scoped Reading — Read Only What the Task Needs

Do **not** read all docs at session start or for every prompt. Read only the artifact(s) directly impacted by the current task:

- Working on a single module → read only `docs/<tool>/SRD.md` + `MD.md` for that tool.
- Writing tests → read only `docs/<tool>/UTCD.md` + `MD.md`.
- Reviewing status → read only `docs/<tool>/TRACE.md`.
- Cross-tool impact → read only the two affected tools' docs, nothing else.

### Requirement Lookup — Priority Ladder

Only escalate to the next level if the current level is insufficient:

| Priority | When to use | What to read |
|----------|-------------|--------------|
| 1 — Task context | Always start here | The user's prompt + `CONTEXT.md` §0 |
| 2 — Traceability | Uncertain what's done | `docs/<tool>/TRACE.md` |
| 3 — Module spec | Need interface / file details | `docs/<tool>/MD.md` |
| 4 — Requirements | Need acceptance criteria | `docs/<tool>/SRD.md` (specific rows only) |
| 5 — Objectives | Need high-level intent | `docs/<tool>/FO.md` |
| ❌ Never | Stuck on where to write | Do **not** open `requirements.md` — use Priority 3–5 above |

---

## On-Demand Reading Guide

| When you need to... | Read this |
|---------------------|-----------|
| What's next | `us_swing/CONTEXT.md` §0 |
| Project vision | `us_swing/idea.md` |
| Process details | `process.md` §3-9 (specific section) |
| Implementation status | `<project>/docs/<tool>/TRACE.md` (active tool only) |
| Requirements | `<project>/docs/<tool>/SRD.md` (active tool, specific rows) |
| Recent work | `<project>/DEVLOG.md` (latest entry only) |
| Skill gaps | `skill.md` |
| Folder rules | `process.md` §14 |
| Add new tool | `process.md` §14.3.5 |

## Common Commands

```bash
pip install -e ".[dev]"                    # Install deps
python -m alm && python -m installer       # Tools: ALM viewer, Installer Gen
python us_swing/run_gui.py                 # Launch GUI (paper mode)
python -m us_swing health                  # Health check
ruff check us_swing/src/ us_swing/tests/ && mypy us_swing/src/ && pytest us_swing/tests/
```
