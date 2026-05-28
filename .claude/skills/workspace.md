# Workspace Layout & Project Convention

> Load this file when you need folder orientation: new session (resume), architecture review,
> or adding a new project/tool. Not needed for routine fix/test/refactor tasks.

## Workspace Tree

```
USMarket_Backtesting/              ← workspace root
├── AGENT_BOOT.md                  ← AI entry point (status + pointers)
├── CLAUDE.md                      ← team instructions (committed)
├── CLAUDE.local.md                ← personal overrides (gitignored)
├── process.md                     ← generic dev process (all projects)
├── skill.md                       ← generic skills inventory
├── PROMPTS.md                     ← reusable prompt patterns
├── pyproject.toml / README.md
│
├── .claude/                       ← Claude control center (committed)
│   ├── settings.json              ← permissions + config
│   ├── settings.local.json        ← personal permissions (gitignored)
│   ├── commands/                  ← custom slash commands (/project:<name>)
│   │   ├── new-feature.md / fix-issue.md / refactor.md
│   │   ├── write-tests.md / review.md / rn.md
│   │   ├── doc-check.md / auto-feature.md
│   │   ├── finish.md              ← session close: RN + TRACE + CONTEXT + DEVLOG + optional Git PR
│   ├── rules/                     ← modular always-on instruction files
│   ├── skills/                    ← auto-invoked workflow skills
│   │   ├── dev-context.md         ← process + doc rules (Class D/S)
│   │   ├── workspace.md           ← this file — folder layout (on demand)
│   │   ├── code-writer.md         ← PyQt6 + Python code writing patterns
│   │   ├── hookify.md             ← hook maintenance skill
│   │   ├── trace.md               ← TRACE.md sync skill
│   │   └── pyqt-comment-analyzer.md
│   └── agents/                    ← subagent personas
│
├── alm/                           ← ALM traceability viewer — see alm/CLAUDE.md
│
├── installer/                     ← Windows Installer Generator — see installer/CLAUDE.md
│
└── us_swing/                      ← US Swing project (active)
    ├── idea.md, CONTEXT.md, DEVLOG.md, requirements.md  ← READ-ONLY frozen source
    ├── run_gui.py                  ← GUI launcher (adds src/ to sys.path)
    ├── docs/                      ← FO/SRD/DD/MD/UTCD/TRACE per tool
    │   ├── infrastructure/        ← INF
    │   ├── screener/              ← SCR
    │   ├── analysis/              ← ANA
    │   ├── execution/             ← EXE
    │   ├── gui/                   ← GUI
    │   └── mcp/                   ← MCP
    └── src/
        └── us_swing/              ← Python package (`import us_swing`) — src layout
            ├── __init__.py / __main__.py
            └── gui/               ← PyQt6 GUI modules (theme, panels, main_window, …)
```

## Project Convention (template for new projects)

All projects follow this layout. When a new project is added, use this template:

```
<project>/
├── CLAUDE.md        ← project-level team instructions (committed)
├── idea.md          ← vision & roadmap
├── CONTEXT.md       ← current dev state (update every session)
├── DEVLOG.md        ← session history (prepend new entry every session)
├── requirements.md  ← READ-ONLY frozen source; never read or modify
│
├── .claude/         ← Claude control center (committed)
│   ├── settings.json         ← permissions + config
│   ├── commands/             ← custom slash commands
│   ├── rules/                ← modular always-on instruction files
│   ├── skills/               ← auto-invoked workflow skills
│   └── agents/               ← subagent personas
│
├── docs/
│   └── <tool>/      ← one subfolder per tool code (INF, SCR, ANA, EXE, GUI, MCP, …)
│       ├── FO.md / SRD.md / DD.md / MD.md / UTCD.md / TRACE.md
│       ├── issues/
│       └── revisions/
├── src/
│   └── <pkg>/       ← Python package root (src layout: `import <pkg>`)
├── tests/           ← pytest suite (mirrors src/ structure)
└── data/            ← local cache / fixtures (if applicable)
```
