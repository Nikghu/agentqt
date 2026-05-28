# AGENT BOOT — USMarket Swing Trading Toolkit

> **Active project:** `us_swing`. Do not read `requirements.md`, `process.md`, or `skill.md` unless directed below.

---

## §1 — Prompt Classification

Classify every prompt before reading any file or invoking any agent:

| Class | Trigger | Agents | File reads |
|---|---|---|---|
| **Q** | General question, no project work | None | None |
| **N** | Status check, "what's next?", navigation | None | `CONTEXT.md §0` only |
| **D** | Code, docs, tests, bug fix, any dev task | `prompt-evaluator` first, then routing below | Per dev-context.md |
| **S** | First prompt of a new session | `prompt-evaluator` first, then routing below | Full `AGENT_BOOT.md` once |

---

## §2 — Agent Registry

11 active agents. Model assignments are fixed — do not override:

**Workflow quality agents (Haiku — lightweight, always-on during command execution):**

| Agent | Model | Purpose | Invoke |
|---|---|---|---|
| `prompt-evaluator` | Sonnet | Classify D/S prompts, identify tool+phase, reframe or ask clarifying questions | Always first for D/S |
| `duplicate-detector` | Haiku | Semantic FO→SRD→DD scan before writing any artifact — returns anchor FO ID and skip list | Start of `new-feature` and `auto-feature` |
| `artifact-validator` | Haiku | Checks ID chains, parent references, and numbering gaps after each artifact-write phase — returns GO/NO-GO | After every FO/SRD/DD/MD/UTCD write in `new-feature`, `auto-feature`, `fix-issue` |
| `phase-gate` | Haiku | Pre-code readiness check — verifies all SRDs Approved, UTCD complete for Must-priority SRDs, MD file paths defined | Before Phase 6 (code) in `new-feature` and `auto-feature` |
| `session-finalizer` | Haiku | Writes RN, syncs TRACE.md, updates CONTEXT.md §0, prepends DEVLOG entry at session end | Final step of `new-feature`, `auto-feature`, `fix-issue`, `refactor`; invoked by `/project:finish` |

**Implementation agents (Sonnet — code writing and review):**

| Agent | Model | Purpose | Invoke |
|---|---|---|---|
| `pyqt-architect` | Sonnet | GUI design decisions: what to add, how to add it — panels, signals, widget layout, new tools. Enforces modern-classic design language. Self-scales: feature blueprint or system ADR. | Any GUI design question or before implementing a DD/MD block |
| `pyqt-code-writer` | Sonnet | Writes new PyQt5 files from architect blueprint — patterns baked in (thread safety, theme constants, frameless windows, signal/slot wiring) | After architect produces blueprint; before pyqt-code-reviewer |
| `pyqt-code-reviewer` | Sonnet | Post-code gate for all PyQt5 files: thread safety, security, quality checklist | After every PyQt5 write/edit |
| `pyqt-code-simplifier` | Sonnet | Complexity reduction — called only on reviewer signal | When reviewer flags MEDIUM+ complexity |
| `test-writer` | Sonnet | Implement UTCD test cases with full traceability | When UTCD phase begins for a module |
| `code-reviewer` | Sonnet | Post-code gate for non-GUI Python files | After every non-GUI write/edit |

**Skills (inline — no agent spawn):**

| Skill | Purpose | Invoke |
|---|---|---|
| `code-writer` | Generic code writing — PyQt6 patterns for GUI files, Python rules for all files | Before writing any new or significantly rewritten source file |
| `pyqt-comment-analyzer` | Comment accuracy and rot detection — advisory, read-only | When `pyqt-code-reviewer` flags comment issues |
| `hookify` | Scan transcript for hook-worthy patterns, implement approved rules | Explicit user request only — never during dev |
| `rag-query` | Semantic DEVLOG search — `python .claude/rag/query.py "<topic>"` surfaces relevant history via vector recall + rerank-2.5 | Ad-hoc historical lookup |

---

## §3 — Routing Decision Tree

```
Incoming prompt
│
├── Class Q → answer directly, read nothing, invoke no agents
│
├── Class N → read CONTEXT.md §0, answer, invoke no agents
│
└── Class D / S
    │
    ├── Step 1: prompt-evaluator (always — Sonnet)
    │   ├── S-class: evaluator runs session boot (CONTEXT.md §0 + RAG DEVLOG) internally
    │   ├── D/S-class: evaluator runs docs_query + skeleton extractor, returns Context Package
    │   └── If ambiguous → stop and ask user before continuing
    │
    ├── Step 2: Architecture? (only if design is not already in a DD document)
    │   ├── GUI feature or tool — design path not yet clear → pyqt-architect (Sonnet)
    │   └── Bug fix / refactor / test-only / DD already specifies files → skip architect agent
    │
    ├── Step 3: Implementation
    │   ├── New PyQt5 file from blueprint → pyqt-code-writer
    │   ├── Existing PyQt5 file — substantial new GUI blocks being added → pyqt-code-writer for new sections; Claude main for surrounding edits
    │   └── Bug fix / refactor / non-GUI file → Claude main
    │
    ├── Step 4: Post-code review (always — no exceptions)
    │   ├── PyQt5 file changed → pyqt-code-reviewer
    │   └── Non-GUI Python file changed → code-reviewer
    │
    ├── Step 5: Conditional follow-ups (only on reviewer signal)
    │   ├── CRITICAL or HIGH issues → fix, re-run reviewer
    │   ├── Complexity MEDIUM+ → pyqt-code-simplifier → re-run reviewer
    │   └── Comment issues flagged → /pyqt-comment-analyzer (skill, inline)
    │
    └── Step 6: Tests (only in UTCD phase)
        └── UTCD.md exists and phase is active → test-writer
```

---

## §4 — Code Orientation Rule

Each source subfolder contains a `MODULE_MAP.json` index of all classes, method signatures, and docstrings. Never read it directly — use the query CLI via Bash instead:

```bash
# What classes/methods exist in a module?
python -m skeleton_extractor query --overview screener

# Full skeleton of one class
python -m skeleton_extractor query --class PresetExecutor

# Single method signature + docstring
python -m skeleton_extractor query --symbol run_preset --class PresetExecutor

# Find any symbol by name substring
python -m skeleton_extractor query --find schedule

# All symbols in a specific file
python -m skeleton_extractor query --file executor.py
```

**Only `Read()` a source file section when you need to edit or deeply understand a specific function body. Never read a full source file for orientation.**

Run from `us_swing/tools/` with `PYTHONPATH=us_swing/tools`. The cache auto-refreshes via hook after every Claude edit to a `.py` file.

---

## §5 — Token Budget Guidelines

| Tier | Model | Use for | Never use for |
|---|---|---|---|
| Cheap | Haiku | Prompt evaluation; artifact validation; duplicate detection; phase gate checks; session finalisation | Any code write/edit task |
| Standard | Sonnet | All code writing, code review, GUI design, feature blueprint, simplification, test writing | — |

**Default for uncertainty:** Sonnet.

---

## §6 — When NOT to Invoke Sub-agents

These are the most important rules for token efficiency:

- **Bug fix on a single module** → skip the architect agent entirely
- **Refactor within one file** → skip the architect agent; run reviewer after
- **Comment-only or doc-only change** → skip all agents including `artifact-validator` and `session-finalizer`
- **Test-only change** → skip code-reviewer; invoke test-writer directly
- **Class Q / N prompts** → skip prompt-evaluator and all agents
- **pyqt-code-simplifier** → never invoke proactively; only when reviewer signals complexity
- **`/project:hookify`** → never invoke during development; only on explicit user request
- **`duplicate-detector`** → skip when input is an existing artifact ID (FO-TOOL-NNN) — anchor already known
- **`artifact-validator`** → skip for code-only or test-only changes where no artifact files were written
- **`phase-gate`** → skip for bug fixes and refactors on already-Implemented SRDs
- **`session-finalizer`** → skip for read-only tasks (doc-check, review, trace) — only needed when artifacts or code changed

---

## §7 — Workspace & Project Convention

> Folder tree and project template → read `.claude/skills/workspace.md` only when needed:
> architecture review (`/project:review`) or adding a new project/tool.
> Routine fix/test/refactor tasks do **not** need this.

---

## §8 — Project & Status

Modular Python 3.11+ platform for US equity swing trading: Analysis, Screening, Backtesting, Execution. Dual interface: PyQt5 GUI + MCP (AI agent protocol). Namespace package: `usswing.*`.

**Active project:** `us_swing` (all new work here)

**Full current state:** `us_swing/CONTEXT.md §0` — read this, not AGENT_BOOT, for current status.

---

## §9 — Dev Process, Doc Rules & Reading Guide

> **Class D/S tasks only:** Read `.claude/skills/dev-context.md` before acting.
> Contains: artifact chain, ID formats, tool codes, code rules, SRD status guard,
> compact doc formats, doc read/write rules, scoped reading, priority ladder, and common commands.
>
> All `/project:*` commands load this automatically. For ad-hoc Class D prompts the
> prompt-evaluator reframed output will include the instruction to read it.

### §9.1 — Compact-Doc Rule (do not miss)

`process.md` §0 rule #3: **SRD, MD, and UTCD are compact-table artifacts.** One short sentence per Description cell. No embedded SQL/Python code blocks, no `**Bold:**` topic headers, no multi-paragraph prose. Algorithmic detail (state machines, transaction sequences, pseudo-code) belongs in DD — never SRD. Reference style: `us_swing/docs/execution/SRD.md` sections 1–5 (NOT sections 6–8, which drifted verbose). FO allows a short intro paragraph + bullet requirements; DD is the only artifact where detailed prose is expected. See `.claude/rules/artifact-conventions.md` § "Documentation Style — Compact Tables" for the full rule.

---

## §10 — Slash Command Registry

Commands live in `.claude/commands/`; skills live in `.claude/skills/`. Prompt-evaluator treats these as Class D unless otherwise noted.

| Command | Phase trigger | Agent invocations |
|---|---|---|
| `/project:new-feature` | FO → UTCD + implementation | `duplicate-detector` (start); `artifact-validator` after each artifact phase; `pyqt-architect` if GUI; `pyqt-code-writer` + `pyqt-code-reviewer` for GUI; `code-reviewer` for non-GUI; `phase-gate` before code; `session-finalizer` at end |
| `/project:auto-feature` | FO → RN (fully automated, no gates) | Same as new-feature plus all phases run unattended — skips SRD approval prompt |
| `/project:write-tests` | UTCD → pytest | `test-writer` |
| `/project:fix-issue` | Bug → RN | `artifact-validator` after cascade artifact updates; `code-reviewer` or `pyqt-code-reviewer` post-fix; `session-finalizer` at end |
| `/project:refactor` | Code improvement | `pyqt-code-reviewer` post-edit for GUI files; `code-reviewer` for non-GUI; `session-finalizer` at end |
| `/project:finish` | Session close: RN + TRACE + CONTEXT + DEVLOG + optional Git PR | `session-finalizer` (handles all four steps); git flow runs inline if user confirms |
| `/project:review` | Pre-implementation architecture | `pyqt-architect` (Sonnet) |
| `/project:rn` | Standalone RN only — use when session-finalizer was already run or skipped | None — doc-only, no code |
| `/project:doc-check` | Anytime — read-only audit | None — never modifies files |
| `code-writer` | Before writing any new or significantly rewritten source file | None — inline skill, no agent spawn |
| `pyqt-comment-analyzer` | When reviewer flags comment issues | None — inline skill, no agent spawn |
| `trace` | Manual sync — for ad-hoc phase completions or standalone TRACE repairs | None — doc-only, no code |
| `hookify` | Periodic hook maintenance | None — inline skill, implements rules via `update-config` |
| `workspace` | Workspace orientation — new session, architecture review, or adding a tool | None — read-only orientation |

**Session close — preferred path:**
- `/project:finish <TOOL> <version>` — the single end-of-session command. Writes the RN, syncs TRACE, updates CONTEXT and DEVLOG, then offers a Git branch → PR → merge flow. Use this at the end of every feature, fix, or refactor session.

**Maintenance fallbacks (`trace`, `rn`, `doc-check`) — use only when `finish` was skipped or partial:**
- `/project:trace` — manual TRACE repair only; or after `write-tests` / `rn` runs that don't auto-invoke `session-finalizer`
- `/project:rn <TOOL> <version>` — standalone RN when `session-finalizer` has already been run or skipped this session
- `/project:doc-check <TOOL>` — read-only audit before starting a new FO on a tool
