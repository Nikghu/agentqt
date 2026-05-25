# Artifact Conventions

Extracted from `process.md §2 (Document Hierarchy)` and `§14 (Numbering & Naming)`.

## Artifact Chain

Every feature follows this mandatory order — no skipping:

```
FO → SRD → DD → MD → UTCD → Code → Tests → RN
```

## Documentation Style — Compact Tables (Critical)

`process.md` §0 rules #3 and #7:
> Use compact table format for **SRD, MD, and UTCD** artifacts where possible. **Avoid verbose prose.** Keep process documents minimal — every edit must add specific value.

| Artifact | Style | Description-cell budget |
|---|---|---|
| **SRD, MD, UTCD** | Compact table rows | **One short sentence** per Description cell. No embedded SQL/code blocks. No `**Bold:**` topic labels inside cells. Reference style: `us_swing/docs/execution/SRD.md` sections 1–5. |
| **FO** | Bullet list per FO; intro paragraph allowed but tight | One bullet = one shall-statement. No multi-paragraph narration. |
| **DD** | Detailed prose / code blocks expected | Pseudo-code, state machines, transaction sequences belong here — not in SRD. |

**Rule of thumb:** If you're typing more than two sentences into a Description cell, it belongs in the DD instead. The SRD says *what*, the DD says *how*.

Common drift to avoid — these patterns violate the rule:
- `**Topic header:** Long explanation...` inside a table cell.
- Embedded `INSERT INTO ...` / `def foo(): ...` blocks in an SRD row.
- Restating the same constraint in Description, Constraints, and Notes.
- Multiple comma-separated IDs in a Parent cell — one Parent ID per row, always.

## ID Formats

| Artifact | Format | Example |
|---|---|---|
| Tool Code | 3-letter uppercase | `SCR`, `ANA`, `EXE`, `INF`, `GUI`, `MCP` |
| Functional Objective | `FO-<TOOL>-NNN` | `FO-SCR-001` |
| Software Requirement | `SRD-<TOOL>-NNN.NNN` | `SRD-SCR-001.003` |
| Design Document Item | `DD-<TOOL>-NNN.NNN.DNN` | `DD-SCR-001.003.D01` |
| Module | `MD-<TOOL>-NNN.NNN.MNN` | `MD-SCR-001.003.M02` |
| Unit Test Case | `UT-<TOOL>-NNN.NNN.MNN.TNN` | `UT-SCR-001.003.M02.T05` |
| Revision Note | `RN-<TOOL>-VER-YYYYMMDD` | `RN-SCR-1.0.0-20260301` |
| Issue | `ISS-<TOOL>-NNNN` | `ISS-SCR-0042` |

## SRD Status Guard (Critical)

| Status | Set By | Agent May Edit? |
|---|---|---|
| `Draft` | Agent | **Yes** |
| `Approved` | User only | No |
| `Implemented` | Agent | No |
| `Verified` | User only | No (frozen) |
| `Reopen` | User only | **Yes** |

**Only `Approved` SRDs may be implemented.** After implementation, set status → `Implemented`.

Before writing any SRD row, verify its parent `FO-<TOOL>-NNN` heading already exists in `FO.md` — create it first if missing.

## Document Storage Locations

| Artifact | Location |
|---|---|
| FO, SRD, DD, MD, UTCD, TRACE | `us_swing/docs/<tool>/` — rows in `<tool>/MD.md` must only carry IDs matching that tool's code (e.g. only `MD-EXE-*` in `execution/MD.md`); cross-tool impacts go in a plain-text note, not as ID rows |
| Revision Notes | `us_swing/docs/<tool>/revisions/RN-<TOOL>-VER-DATE.md` |
| Issue Reports | `us_swing/docs/<tool>/issues/ISS-<TOOL>-NNNN.md` |
| Source code | `us_swing/src/usswing/<tool>/` |
| Tests | `us_swing/tests/<tool>/` |

## Document Versioning

Semantic versioning on all docs: `MAJOR.MINOR.PATCH`
- `MAJOR` — breaking structural changes
- `MINOR` — new sections/requirements added
- `PATCH` — corrections, clarifications

## Active Tools

`us_swing` has 6 tools: `INF` `SCR` `ANA` `EXE` `GUI` `MCP`

Do **not** begin `BKT` (Backtesting) until EXE is complete and a BKT FO is approved.

## Definition of Done (14-point checklist)

- [ ] FO approved
- [ ] SRD written + approved
- [ ] DD written
- [ ] MD modules defined
- [ ] UTCD test cases written (before code)
- [ ] Code passes `ruff` + `mypy --strict`
- [ ] All UTCD tests pass ≥ 80% coverage
- [ ] Integration tests pass (if applicable)
- [ ] MCP schema validated (if MCP-exposed)
- [ ] TRACE.md updated
- [ ] Revision Note written
- [ ] Commit with proper convention
- [ ] `CONTEXT.md` updated
- [ ] `DEVLOG.md` updated (newest entry at top)
