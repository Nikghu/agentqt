# USMarket Swing Trading Toolkit

**An end-to-end, modular platform for US equity swing trading** — encompassing analysis, screening, backtesting, and execution.

Built with Python 3.11+, PyQt6, and MCP (Model Context Protocol) for dual human + AI-agent operation.

---

## 🤖 AI Agent — Start Here

> **Read [`AGENT_BOOT.md`](AGENT_BOOT.md) — that is the ONLY file you need to begin.**

---

## Project Structure

```
usmarket-swing-trading/              ← workspace root
├── AGENT_BOOT.md                    # AI agent entry point
├── CLAUDE.md                        # AI team instructions (committed)
├── pyproject.toml                   # Build config & dependencies
│
├── us_swing/                        # Active project
│   ├── idea.md                      #   Vision & roadmap
│   ├── requirements.md              #   Frozen requirements source
│   ├── CONTEXT.md                   #   Current dev state
│   ├── DEVLOG.md                    #   Session journal
│   ├── run_gui.py                   #   GUI launcher
│   ├── USSwing.spec                 #   PyInstaller build spec
│   │
│   ├── docs/                        #   Artifact docs (per tool)
│   │   ├── infrastructure/          #     INF — data, DB, broker
│   │   ├── screener/                #     SCR — stock screener
│   │   ├── analysis/                #     ANA — strategy engine
│   │   ├── execution/               #     EXE — order execution
│   │   ├── gui/                     #     GUI — PyQt6 interface
│   │   └── mcp/                     #     MCP — AI agent protocol
│   │
│   ├── src/us_swing/                #   Python package (src layout)
│   │   ├── analysis/                #     Strategy engine
│   │   ├── broker/                  #     IBKR client & pacing
│   │   ├── config/                  #     App settings
│   │   ├── data/                    #     Market data engine & providers
│   │   ├── db/                      #     Database manager & schema
│   │   ├── gui/                     #     PyQt6 panels & main window
│   │   ├── monitoring/              #     Health, alerts, connectivity
│   │   ├── screener/                #     Screener framework & strategies
│   │   ├── universe/                #     S&P 500 universe manager
│   │   └── user/                    #     User profile manager
│   │
│   ├── tests/                       #   pytest suite (mirrors src/)
│   └── tools/skeleton_extractor/    #   Dev tool — code index generator
│
├── alm/                             # ALM traceability viewer (PyQt6)
├── installer/                       # Windows installer generator
└── .claude/                         # Claude Code config (agents, rules, hooks)
```

---

## Claude Code Framework

This project runs on a purpose-built Claude Code framework — a structured, multi-agent development system layered on top of Anthropic's Claude Code CLI. It replaces the typical "chat with an AI and hope for the best" workflow with a deterministic, traceable engineering process.

### What It Is

The entire `.claude/` folder is the framework:

| Layer | Files | Purpose |
|---|---|---|
| **Rules** | `.claude/rules/*.md` | Always-on constraints: code style, artifact conventions, testing standards, traceability |
| **Agents** | `.claude/agents/*.md` | 11 specialized sub-agents with fixed model assignments and narrow scopes |
| **Commands** | `.claude/commands/*.md` | 12 slash commands that orchestrate full feature pipelines |
| **Hooks** | `.claude/hooks/*.py/.ps1` | Automatic side-effects: skeleton index refresh after every `.py` edit, review reminders |

### How It Works — The Artifact Chain

Every feature follows a mandatory, validated pipeline before a single line of code is written:

```
FO (objective) → SRD (requirements) → DD (design) → MD (modules)
  → UTCD (test cases) → Code → Tests → RN (revision note)
```

- **FO** defines *what* to build
- **SRD** specifies *exact requirements* with Must/Should/Could priority — only `Approved` SRDs can be implemented
- **DD** documents *how* to build it — data flow, class design, edge cases
- **UTCD** test cases are written *before* code (TDD-aligned)
- The `artifact-validator` agent checks ID chains and parent references after every phase — GO/NO-GO gate
- The `phase-gate` agent verifies all SRDs are Approved and test cases exist before implementation starts
- The `session-finalizer` agent auto-syncs `TRACE.md`, `CONTEXT.md`, and `DEVLOG.md` at session end

### The Agent Roster

Each agent has a fixed model, a fixed scope, and is invoked only at the right moment:

| Agent | Model | When |
|---|---|---|
| `prompt-evaluator` | Sonnet | Classifies and reframes every dev prompt before any file is read |
| `duplicate-detector` | Haiku | Scans existing FO/SRD/DD before writing new artifacts — prevents re-inventing |
| `artifact-validator` | Haiku | ID chain integrity check after every artifact write |
| `phase-gate` | Haiku | Pre-code readiness: all SRDs Approved, UTCD complete? |
| `pyqt-architect` | Sonnet | GUI design decisions — panels, signals, layout — before any GUI code |
| `pyqt-code-writer` | Sonnet | Writes new PyQt6 files from architect blueprint |
| `pyqt-code-reviewer` | Sonnet | Post-code gate: thread safety, security, quality — no GUI file ships without this |
| `pyqt-code-simplifier` | Sonnet | Complexity reduction — invoked only when reviewer signals MEDIUM+ complexity |
| `code-reviewer` | Sonnet | Same gate for all non-GUI Python modules |
| `test-writer` | Sonnet | Implements UTCD test cases with full ID traceability |
| `session-finalizer` | Haiku | TRACE.md + CONTEXT.md + DEVLOG sync at session end |

### Why This Approach

**The core problem with vanilla AI coding:** Each session starts cold. The AI has no memory of what was built, why, or what the next step is. Decisions get re-made, code drifts from requirements, and there is no trail of *why* something was built a certain way.

**What this framework solves:**

- **Zero context loss between sessions** — `AGENT_BOOT.md` + `CONTEXT.md §0` + `DEVLOG.md` give any agent (or human) a full picture in one read
- **Requirements drive code, not the other way around** — you cannot start coding until the SRD is Approved; the agent enforces this automatically
- **Every module traces back to a business objective** — `TRACE.md` links FO → SRD → DD → MD → UT → RN in one table; broken traceability is caught by `artifact-validator`
- **Token efficiency is designed in** — Haiku agents handle lightweight gates (validation, duplicate detection, session sync); Sonnet only fires for design and code work; reading rules are scoped (CLAUDE.md §1 specifies exactly which files to read per prompt class)
- **Hooks make the index self-maintaining** — `refresh_skeleton.py` runs after every `.py` edit and updates `MODULE_MAP.json`; agents never need to read full source files to get oriented
- **The artifact chain is a living contract** — SRD statuses (`Draft → Approved → Implemented → Verified`) enforce who can change what and when

### Comparison to Alternative Approaches

| Approach | Traceability | Context Retention | Code Quality Gates | Token Efficiency | Repeatability |
|---|---|---|---|---|---|
| **No framework** (plain prompts) | None | None | None | Wasteful | Low |
| **Single CLAUDE.md** (basic rules only) | None | Minimal | Ad-hoc | Moderate | Moderate |
| **CLAUDE.md + memory** (notes only) | Partial | Good | Ad-hoc | Moderate | Moderate |
| **This framework** (full artifact chain + agents) | Full FO→RN | Persistent + structured | Automated, multi-stage | Optimized by tier | High |

**Rating: 9 / 10**

The framework reaches 9/10 because it delivers on all four axes that matter for a long-running solo/small-team technical project: the AI never loses context, requirements are enforced before code is written, every module is traceable, and token costs are managed by routing cheap tasks to Haiku. The missing point is the onboarding cost — setting up 11 agents, 12 commands, 4 rule files, and a skeleton extractor is a non-trivial investment that only pays off on projects lasting more than a few weeks.

---

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e ".[dev]"
python us_swing/run_gui.py      # Launch GUI
python -m pytest us_swing/tests # Run tests
```
