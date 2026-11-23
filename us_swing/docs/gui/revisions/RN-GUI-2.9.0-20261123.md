# Revision Note — RN-GUI-2.9.0-20261123

**Version:** 2.9.0
**Date:** 2026-11-23
**Tool:** GUI (+ EXE, see RN-EXE-1.42.0-20261123)
**Artifact:** FO-GUI-046 / SRD-GUI-046.001–.013
**Type:** Feature

---

## Summary

The GUI now shows custom indicator plugins. The trigger popup lists them after the built-in indicators, with one row per parameter. Settings has an Indicators section to import, export, remove, reload and check indicators, and a New indicator button that creates a VS Code project with an AI guide and a web API guide. Set up Python makes one shared Python environment for the projects.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-046.001.M01 | `src/us_swing/gui/strategy_builder_dialog.py` | Trigger popup lists plugins after built-ins; `Number` gives a number box, `Input` a dropdown |
| MD-GUI-046.003.M02 | `src/us_swing/gui/indicators_section.py`, `src/us_swing/gui/settings_panel.py`, `src/us_swing/gui/app_service.py` | Settings Indicators section: list, Import, Export, Remove, Reload, Check on S&P 500 Backtest Data; icon-only buttons with name tooltips; New indicator dialog |
| MD-GUI-046.007.M03 | `src/us_swing/gui/indicator_project.py`, `src/us_swing/gui/indicator_guides.py`, `src/us_swing/gui/guide_html.py` | Project folder with example, test, `.env`, `.vscode` files, `CLAUDE.md`, `USSWING_API.md` and `USSWING_API.html`; Open adds missing files; Help opens the web guide |
| MD-GUI-046.013.M04 | `src/us_swing/gui/indicator_python.py` | Set up Python: one shared venv with pandas, numpy and pytest |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-046.001 | Trigger popup lists loaded custom indicators after the built-ins | Implemented |
| SRD-GUI-046.002 | One popup row per parameter, same order, label, limits and default | Implemented |
| SRD-GUI-046.003 | Settings Indicators section lists indicators with name, version and status | Implemented |
| SRD-GUI-046.004 | Import picks a `.py` file, warns it runs code on this PC, adds it only when the check passes | Implemented |
| SRD-GUI-046.005 | Export copies a file, Reload re-reads all files, Remove asks first and names the strategies that use it | Implemented |
| SRD-GUI-046.006 | Check runs the indicator on an S&P 500 stock's Backtest Data and shows the last 20 values | Implemented |
| SRD-GUI-046.007 | New indicator creates a project folder with example, test file and VS Code settings | Implemented |
| SRD-GUI-046.008 | Each new project holds a `CLAUDE.md` AI guide with rules and the exact check command | Implemented |
| SRD-GUI-046.009 | New indicator opens an existing project or creates a new one | Implemented |
| SRD-GUI-046.010 | Each project holds the API guide as text and as a web page; Help opens the page in the browser | Implemented |
| SRD-GUI-046.011 | Opening a project adds any missing guide and VS Code files; user code is never changed | Implemented |
| SRD-GUI-046.012 | Each project recommends the Python and Claude Code VS Code extensions | Implemented |
| SRD-GUI-046.013 | Set up Python makes one shared environment with pandas, numpy and pytest | Implemented |

SRD rows are not edited (status Implemented). SRD-GUI-046.008–.013 were added by user request in chat on 2026-11-23.

---

## Design Decisions

- Indicator folders are shared by all users (user decision, 2026-11-23).
- Check reads Backtest Data for S&P 500 stocks: last 60 days of 3m, 15m and 30m, and 3 years of 1d and 1w. Stock symbols with a dot are read with a space (BRK.B reads as BRK B).
- The API guide is one Markdown text turned into one offline web page, so the text and the page cannot drift. No web fonts or scripts from the internet.
- One shared Python environment serves all projects. It is made from the PC's own Python (`py -3.11` first; the Windows Store stub is skipped).
- Import opens the project whose `.py` file changed last; else the projects folder; else home.
- The refused-start message for a missing plugin (SRD-EXE-022.014) shows in the Strategies tab, one popup per batch.

---

## Issues Resolved

None

---

## Test Coverage

- UT-GUI-046.* Pass. New cases: UT-GUI-046.003.M02.T03 (icon buttons), UT-GUI-046.004.M02.T04 (Import folder), UT-GUI-046.006.M02.T02–T03 (Check on S&P 500 stocks).
- Open app checks: TODO T232–T236 (user checks).
- Open question to the user: switch the Import dry run and `indicator check` (EXE side) from `candles.db` to Backtest Data?
