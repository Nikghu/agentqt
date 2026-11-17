# Revision Note — RN-GUI-2.0.0-20261117

**Version:** 2.0.0
**Date:** 2026-11-17
**Tool:** GUI (also DSK, MKT, EXE)
**Artifact:** FO-GUI-034 – FO-GUI-041, FO-DSK-001 – FO-DSK-013, FO-MKT-001 – FO-MKT-021, FO-EXE-021 (all removed)
**Type:** Removal

---

## Summary

The AI Desk and the Market Floor were removed, because the AI Desk was not built correctly. The Market Floor went with it, since all of its real data came from `desk.db`, which only the desk wrote. The app now has 5 screens: Dashboard, Screener, Execution, Charts and Backtest. The Telegram AI notes (FO-GUI-033) stay; they never used desk code. Decision note: `docs/audit/DESK_REMOVAL_2026-11-17.md`. Restore point: git tag `desk-final`.

---

## Steps and PRs

| Step | Work | PR |
|---|---|---|
| 0 | Tag `desk-final`; back up `~/.usswing/desk` to `~/.usswing/desk_backup_20261117` | — |
| 1 | Decision note and TODO rows | #155 |
| 2 | Cut desk and Floor links from the app | #156 |
| 3 | Delete desk and Floor code and tests (295 files) | #157 |
| 4 | Clean the PyInstaller spec, `pyproject.toml` and MODULE_MAP files | #158 |
| 5 | Remove the desk docs and rows (this note) | #159 |
| 6 | Delete the AI Desk strategy row (no cycles or saved signals existed), `~/.usswing/desk` and `floor_layouts.json`; backups in `desk_backup_20261117` | #160 |

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-018.005.M03 | `src/us_swing/gui/main_window.py` | Changed: no Market Floor or AI Desk page, no desk poller or desk process |
| MD-GUI-019.001.M01 | `src/us_swing/gui/side_panels.py` | Changed: AI feed button removed from the right strip |
| MD-GUI-000.002 | `src/us_swing/gui/app_service.py` | Changed: AI Desk strategy, desk picks, open-trade sharing, desk live symbols, desk trade results and RSP download removed |
| MD-EXE-015.002.M01 | `src/us_swing/execution/broker_adapter.py` | Changed: no special stop and target for `ai_desk` entries |
| MD-EXE-011.001.M01 | `src/us_swing/execution/strategy_engine/_engine.py` | Changed: `ai_desk` strategy type no longer skipped |
| — | `src/us_swing/__main__.py` | Changed: `desk` command removed |
| — | `desk/`, `market/`, `core/desk_*.py`, `gui/ai_desk*.py`, `gui/floor_*.py`, `gui/market_floor.py`, `gui/desk_control.py`, `gui/sealed_view.py`, `core/econ_calendar.py`, `core/report_html.py`, `execution/desk_signals.py` | Removed |
| — | `USSwing.spec`, `pyproject.toml` | Changed: desk hidden imports, employee files, `feedparser` and `pypdf` removed |

---

## Docs

| Doc | Change |
|---|---|
| `docs/desk/`, `docs/market/`, `docs/agt/` | Removed |
| `docs/gui/` FO, SRD, DD, MD, UTCD, TRACE | FO-GUI-034 – FO-GUI-041 sections and rows removed; MD-GUI-019.011.M04 and UT-GUI-019.011.M04.T01 removed |
| `docs/gui/DD.md` | Scheduler part of DD-GUI-034.068.D01 kept as DD-GUI-029.007.D01 (SRD-GUI-029.007–.008) |
| `docs/execution/` FO, SRD, DD, MD, UTCD, TRACE | FO-EXE-021 and its rows removed |
| `TODO.md` | 63 desk rows Dropped; T141, T187 Closed; T193 – T196 Done |

Version history lines and older revision notes that name desk IDs are kept as history.

---

## Tests

| Run | Result |
|---|---|
| Non-GUI pytest | 1138 passed; 11 failed (`test_candle_builder.py`, `test_preset.py`), the same as on main |
| GUI pytest (6 chunks) | All passed; `test_strategy_builder_dialog.py` errors only as the first file of a run (existing db/data import loop) |
| PyInstaller package | `dist/USSwing` built; no desk files inside |
| App start | Checked by the user after step 2 |

---

## Known Gaps

- SRD-GUI-018.012 and SRD-GUI-019.011 (kept FOs) still name the AI Desk as an example in their text; they are Implemented, so the user must Reopen them to edit.
- MD-GUI-018.012.M05 note mentions the AI Desk; `Sidebar.add_sub_nav()` now has no user.
- `test_llm_claude_screener.py` imports a module that was never in git (not desk related).
