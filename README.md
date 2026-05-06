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

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e ".[dev]"
python us_swing/run_gui.py      # Launch GUI
python -m pytest us_swing/tests # Run tests
```
