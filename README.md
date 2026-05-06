<div align="center">

```
 █████╗  ██████╗ ███████╗███╗   ██╗████████╗ ██████╗ ████████╗
██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝██╔═══██╗╚══██╔══╝
███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   ██║   ██║   ██║   
██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   ██║▄▄ ██║   ██║   
██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   ╚██████╔╝   ██║   
╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝    ╚══▀▀═╝    ╚═╝   
```

**A structured, multi-agent development framework for Claude Code**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![PyQt6](https://img.shields.io/badge/PyQt6-6.x-41CD52?style=flat-square&logo=qt&logoColor=white)](https://www.riverbankcomputing.com/software/pyqt/)
[![Claude Code](https://img.shields.io/badge/Claude_Code-Powered-D97757?style=flat-square)](https://claude.ai/code)
[![SDLC](https://img.shields.io/badge/SDLC-Waterfall-4A90D9?style=flat-square)](https://en.wikipedia.org/wiki/Waterfall_model)

</div>

---

`us_swing` — a US equity swing trading toolkit built with Python 3.11+ and PyQt6 — is the reference implementation that demonstrates the framework in a real, production-scale project.

---

## What Is AgentQT?

AgentQT is a full development operating system built on top of Claude Code — but its foundations are not new. They are borrowed directly from decades of proven software engineering practice.

### Built on Industry-Standard Engineering Principles

AgentQT encodes the Waterfall SDLC — one of the most proven and widely adopted models in enterprise and safety-critical software engineering — directly into Claude's workflow.

**Waterfall SDLC (Software Development Life Cycle)**

The Waterfall model — defined in the 1970s and still the backbone of regulated, safety-critical, and enterprise software — divides development into sequential, non-overlapping phases where each phase must be completed and signed off before the next begins. Every requirement, design decision, and test case is documented before code is written, creating a clear audit trail from business objective to deployed software.

```
Requirements → System Design → Implementation → Testing → Deployment → Maintenance
```

AgentQT maps this model directly onto every feature:

| Waterfall Phase | AgentQT Artifact | Enforced By |
|---|---|---|
| Requirements | FO + SRD (Functional Objective + Software Requirements) | SRD status guard — code blocked until `Approved` |
| System Design | DD (Design Document) | `artifact-validator` checks parent references |
| Module Design | MD (Module Definition) | File paths required before `phase-gate` passes |
| Test Planning | UTCD (Unit Test Case Document) | Written before code — TDD gate |
| Implementation | Code | Only after `phase-gate` returns GO |
| Verification | Tests pass ≥ 80% coverage | Coverage gate in CI |
| Release | RN (Revision Note) | Produced after every implementation block |

The key discipline borrowed from Waterfall: **no phase can be skipped, and each phase produces a document that the next phase depends on.** The `phase-gate` agent enforces this mechanically — it will block code generation if any upstream artifact is missing or unapproved.

### What AgentQT Adds on Top

The Waterfall model was designed for human teams following paper-based processes. AgentQT makes it executable by an AI agent:

- **11 specialized sub-agents** enforce each phase gate automatically — no human has to remember the process
- **12 slash commands** run full pipelines (FO through Revision Note) in one invocation
- **Hooks** keep the code index self-maintaining — agents orient from `MODULE_MAP.json` instead of reading full source files
- **Tiered model routing** — lightweight gates (Haiku) vs. design and code work (Sonnet) — keeps token costs proportional to task complexity

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
