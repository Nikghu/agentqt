# AgentQT

**A structured, multi-agent development framework for Claude Code** — bringing deterministic engineering discipline (requirements, traceability, quality gates) to AI-assisted Python/PyQt6 projects.

`us_swing` — a US equity swing trading toolkit built with Python 3.11+ and PyQt6 — is the reference implementation that demonstrates the framework in a real, production-scale project.

---

## What Is AgentQT?

Most Claude Code setups are a single `CLAUDE.md` file with a few rules. AgentQT is a full development operating system: 11 specialized sub-agents, 12 slash commands, 4 always-on rule files, and lifecycle hooks — all wired together so Claude never loses context, never skips a quality gate, and every line of code traces back to a documented requirement.

The framework lives entirely in `.claude/` and is portable — drop it into any Python/PyQt6 project.

---

## Framework Architecture

The `.claude/` folder is the framework:

| Layer | Files | Purpose |
|---|---|---|
| **Rules** | `.claude/rules/*.md` | Always-on constraints loaded into every session: code style, artifact conventions, testing standards, traceability |
| **Agents** | `.claude/agents/*.md` | 11 specialized sub-agents with fixed model assignments and narrow, non-overlapping scopes |
| **Commands** | `.claude/commands/*.md` | 12 slash commands that orchestrate full feature pipelines from objective to revision note |
| **Hooks** | `.claude/hooks/*.py/.ps1` | Automatic side-effects: code index refresh after every `.py` edit, review reminders |

---

## The Artifact Chain

Every feature follows a mandatory, validated pipeline before a single line of code is written:

```
FO → SRD → DD → MD → UTCD → Code → Tests → RN
(objective) (requirements) (design) (modules) (test cases)          (revision note)
```

- **FO** defines *what* to build and why
- **SRD** specifies exact requirements with Must/Should/Could priority — only `Approved` SRDs can be implemented
- **DD** documents *how* — data flow, class design, edge cases
- **UTCD** test cases are written *before* code (TDD-aligned)
- `artifact-validator` checks ID chains and parent references after every phase — GO/NO-GO gate
- `phase-gate` verifies all SRDs are Approved and test cases exist before implementation starts
- `session-finalizer` auto-syncs `TRACE.md`, `CONTEXT.md`, and `DEVLOG.md` at session end

---

## The Agent Roster

Each agent has a fixed model, a fixed scope, and fires only at the right moment in the pipeline:

| Agent | Model | Role |
|---|---|---|
| `prompt-evaluator` | Sonnet | Classifies and reframes every dev prompt before any file is read |
| `duplicate-detector` | Haiku | Scans existing artifacts before writing new ones — prevents re-inventing |
| `artifact-validator` | Haiku | ID chain integrity check after every artifact write |
| `phase-gate` | Haiku | Pre-code readiness gate: SRDs Approved? UTCD complete? |
| `pyqt-architect` | Sonnet | GUI design decisions — panels, signals, layout — before any code |
| `pyqt-code-writer` | Sonnet | Writes new PyQt6 files from architect blueprint |
| `pyqt-code-reviewer` | Sonnet | Post-code gate: thread safety, security, quality — no GUI file ships without this |
| `pyqt-code-simplifier` | Sonnet | Complexity reduction — only when reviewer signals MEDIUM+ complexity |
| `code-reviewer` | Sonnet | Same post-code gate for all non-GUI Python modules |
| `test-writer` | Sonnet | Implements UTCD test cases with full ID traceability |
| `session-finalizer` | Haiku | TRACE.md + CONTEXT.md + DEVLOG sync at every session end |

---

## Why AgentQT

**The core problem with vanilla AI coding:** Each session starts cold. The AI has no memory of what was built, why decisions were made, or what comes next. Requirements drift, code diverges from intent, and there is no audit trail.

**What AgentQT solves:**

- **Zero context loss between sessions** — `AGENT_BOOT.md` + `CONTEXT.md §0` + `DEVLOG.md` give any agent or human a full picture in one read
- **Requirements drive code, not the other way around** — coding is blocked until the SRD is Approved; the `phase-gate` agent enforces this automatically
- **Full traceability** — `TRACE.md` links FO → SRD → DD → MD → UT → RN in one table; `artifact-validator` catches broken chains
- **Token efficiency by design** — Haiku handles all lightweight gates (validation, duplicate detection, session sync); Sonnet only fires for design and code work
- **Self-maintaining code index** — `refresh_skeleton.py` hook updates `MODULE_MAP.json` after every `.py` edit; agents query it instead of reading full source files
- **SRD status as a living contract** — `Draft → Approved → Implemented → Verified` statuses enforce who can change what and when

---

## Comparison

| Approach | Traceability | Context Retention | Quality Gates | Token Efficiency | Repeatability |
|---|---|---|---|---|---|
| Plain prompts | None | None | None | Wasteful | Low |
| Single `CLAUDE.md` | None | Minimal | Ad-hoc | Moderate | Moderate |
| `CLAUDE.md` + memory | Partial | Good | Ad-hoc | Moderate | Moderate |
| **AgentQT** | Full FO→RN | Persistent + structured | Automated, multi-stage | Optimized by tier | High |

**Rating: 9 / 10**

AgentQT scores 9/10 for solo and small-team projects lasting more than a few weeks: the AI never loses context, requirements are enforced before code is written, every module is traceable, and token costs are managed by tier routing. The one point deducted is for onboarding cost — 11 agents, 12 commands, 4 rule files, and a skeleton extractor is a real investment that only pays off on projects with depth and longevity.

---

## Reference Implementation — `us_swing`

`us_swing` is a production-scale US equity swing trading platform built entirely using AgentQT. It demonstrates every framework feature across a 6-tool architecture:

```
agentqt/
├── AGENT_BOOT.md                    # AI agent entry point
├── CLAUDE.md                        # AI team instructions
├── pyproject.toml                   # Build config & dependencies
│
├── us_swing/                        # Reference project (swing trading toolkit)
│   ├── idea.md                      #   Vision & roadmap
│   ├── requirements.md              #   Frozen requirements source
│   ├── CONTEXT.md                   #   Current dev state
│   ├── DEVLOG.md                    #   Session journal
│   ├── run_gui.py                   #   GUI launcher
│   │
│   ├── docs/                        #   Artifact docs (FO→RN per tool)
│   │   ├── infrastructure/          #     INF — data engine, DB, broker
│   │   ├── screener/                #     SCR — stock screener
│   │   ├── analysis/                #     ANA — strategy engine
│   │   ├── execution/               #     EXE — order execution
│   │   ├── gui/                     #     GUI — PyQt6 interface
│   │   └── mcp/                     #     MCP — AI agent protocol
│   │
│   ├── src/us_swing/                #   Python package (src layout)
│   ├── tests/                       #   pytest suite (mirrors src/)
│   └── tools/skeleton_extractor/    #   Code index generator
│
├── alm/                             # ALM traceability viewer (PyQt6)
├── installer/                       # Windows installer generator
└── .claude/                         # AgentQT framework (agents, rules, commands, hooks)
```

---

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e ".[dev]"
python us_swing/run_gui.py      # Launch the reference GUI
python -m pytest us_swing/tests # Run the test suite
```
