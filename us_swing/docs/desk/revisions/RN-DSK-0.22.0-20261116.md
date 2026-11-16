# Revision Note — RN-DSK-0.22.0-20261116

**Version:** 0.22.0
**Date:** 2026-11-16
**Tool:** DSK
**Artifact:** FO-DSK-004, FO-GUI-034, FO-MKT-002, FO-MKT-010 / SRD-DSK-004.011–.012, SRD-MKT-002.011–.013, SRD-MKT-010.023, SRD-GUI-034.086–.091
**Type:** Feature

---

## Summary

Review fixes and a redesign of AI Desk Command, on branch `fix/dsk-v3-review-part1`. The Claude Code CLI no longer has a per-employee daily token limit (only the desk-wide CLI count, 0 = no limit), and a CLI usage-limit error now skips CLI for the run, tries the backup source and gives the Master a plain reason in chat. The Command view has clearer panels, a discussions tree by day, and a Refresh button on Approvals waiting; the AI feed button sits in the right strip on Market Floor. The sector rotation map is readable with % values, and sectors are now measured against RSP (equal-weight S&P 500) instead of SPY; the regime stays on SPY.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-DSK-004.003.M12 | `src/us_swing/desk/budget.py` | CLI calls skip the per-employee day parts; desk-wide CLI tokens per day, 0 = no limit (SRD-DSK-004.011) |
| MD-DSK-004.001.M11 | `src/us_swing/desk/gateway.py` | CLI usage-limit or busy error stops CLI for the run, tries the backup source, keeps a plain reason (SRD-DSK-004.012) |
| MD-DSK-004.005.M13 | `src/us_swing/core/desk_ai_settings.py` | Desk-wide CLI tokens per day setting; 0 = no limit (SRD-DSK-004.011) |
| MD-MKT-010.003.M03 | `src/us_swing/market/lead_chat.py` | Failed chat reply names the reason when the desk knows it (SRD-MKT-010.023) |
| MD-GUI-034.016.M15 | `src/us_swing/gui/ai_desk_settings.py` | OpenRouter key box says Saved — type to replace when a key is stored (fix, no new SRD; UT-GUI-034.016.M15.T03) |
| MD-GUI-034.039.M26 | `src/us_swing/gui/ai_desk_chat.py` | Command panels, lead cards with coloured edge, red Not answered, one-bar composer (SRD-GUI-034.086); + and menu buttons, discussions grouped by day (SRD-GUI-034.088) |
| MD-GUI-034.034.M24 | `src/us_swing/gui/ai_desk_hiring.py` | Refresh button on Approvals waiting (SRD-GUI-034.087) |
| MD-GUI-034.004.M04 | `src/us_swing/gui/market_floor.py`, `src/us_swing/gui/floor_feed.py` | AI feed button in the right strip, shown on Market Floor only; feed 400 px; folding hides the whole card (SRD-GUI-034.089) |
| — (new asset) | `assets/icons/menu.svg` | Menu icon for the discussions list (SRD-GUI-034.088) |
| MD-GUI-034.012.M11 | `src/us_swing/core/desk_floor.py` | Sector rotation data: 5-day tails from `sector_daily`; values as % with a note (SRD-GUI-034.090–.091) |
| MD-GUI-034.047.M27 | `src/us_swing/gui/floor_charts.py` | Rotation map: short names, quadrant colours, labels apart, hover; Map / List switch with strength bars (SRD-GUI-034.090–.091) |
| MD-MKT-002.009.M05 | `src/us_swing/market/sector_step.py`, `src/us_swing/market/sectors.py` | Sector lines measured against RSP; one full recompute when the stored benchmark is not RSP (SRD-MKT-002.011–.012) |
| MD-MKT-004.002.M02 | `src/us_swing/market/proof.py` | Score proof uses RSP for sectors (SRD-MKT-002.011) |
| MD-MKT-001.013.M06 | `src/us_swing/market/candle_check.py` | Candle check fills RSP from Yahoo when it is behind (SRD-MKT-002.013) |
| MD-MKT-001.007.M04 | `src/us_swing/market/store.py` | `market_meta` table keeps the sector benchmark (SRD-MKT-002.012) |
| — (MD not mapped) | `src/us_swing/gui/app_service.py` | RSP added to the candle download, the Backtest Data download and the candle check (SRD-MKT-002.013) |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-DSK-004.011 | Claude Code CLI calls skip the per-employee day parts; only the desk-wide CLI tokens per day applies, and 0 means no limit | Implemented |
| SRD-DSK-004.012 | A CLI usage-limit or busy error stops CLI use for the run, tries the backup source and keeps a plain reason | Implemented |
| SRD-MKT-010.023 | A failed chat reply says why when the desk knows the reason (limit used up or Claude not available) | Implemented |
| SRD-GUI-034.086 | Command shows chat, approvals and today's runs in their own panels; lead replies are cards with a coloured edge; unanswered is marked Not answered in red | Implemented |
| SRD-GUI-034.087 | Approvals waiting has a Refresh button that reads the waiting approvals again at once | Implemented |
| SRD-GUI-034.088 | Lead chat has a + button for a new discussion and a menu button for the list; discussions are grouped by day, Today and Yesterday open | Implemented |
| SRD-GUI-034.089 | AI feed is 400 px wide and shown or hidden by an AI feed button in the right strip, shown only on Market Floor | Implemented |
| SRD-GUI-034.090 | Sector rotation panel shows names, a colour per quadrant, names apart, 5-day tails and hover numbers; Map / List switch shows strength bars | Implemented |
| SRD-GUI-034.091 | Rotation panel shows strength as % with a note under each view; hover text has no fund codes | Implemented |
| SRD-MKT-002.011 | Sector lines are measured against RSP instead of SPY (1, 3 and 6-month moves, RS-ratio, RS-momentum), in the desk step and the score proof; regime stays on SPY | Implemented |
| SRD-MKT-002.012 | When the stored sector benchmark is not RSP, all `sector_daily` rows are deleted once and every day is computed again | Implemented |
| SRD-MKT-002.013 | Candle download and Backtest Data download fetch RSP daily bars; candle check fills RSP from Yahoo when behind | Implemented |

---

## Design Decisions

- Claude CLI calls have no per-employee token limit; the desk-wide CLI count per day is the only cap (0 = no limit). OpenRouter calls keep the per-employee parts. Root cause from the log: Lead 2 plan used 32,732 of 30,000 tokens and the chat said it could not answer.
- A CLI usage-limit or busy error skips CLI for the rest of the run and tries the backup source; the reason kept for the user is plain text.
- Sectors are measured against RSP (equal-weight S&P 500); the market regime stays on SPY. Changing the stored benchmark deletes the old sector rows once and recomputes all days (`market_meta`).
- Default expert cap changed from 8 to 50 in commit 30e9e8c9, made before this session. Included as context only.
- Command discussions list open or closed state is not kept across restarts (optional, T188).
- The old Fold feed header button is still there; removal is a user decision (T183).

---

## Issues Resolved

None

---

## Test Coverage

- 17 new UTCD cases, all Pass: DSK 3 (UT-DSK-004.011 M12.T01–T02, UT-DSK-004.012 M11.T01); MKT 4 (UT-MKT-010.023 M03.T01, UT-MKT-002.011 M05.T01, UT-MKT-002.012 M05.T01, UT-MKT-002.013 M06.T01); GUI 10 (UT-GUI-034.016.M15.T03, .086 M26.T01, .087 M24.T01, .088 M26.T01–T02, .089 M04.T01, .090 M11.T01 and M27.T01–T02, .091 M27.T01).
- Desk, market and core: 1,757 pass after the CLI fix. AI Desk GUI tests: 186–188 pass per run; floor and strip tests: 74, 65 then 59 pass. Final run: 921 market, backtest and floor tests and 79 other affected tests pass.
- ruff clean on changed files. mypy clean on changed files, except pre-existing errors in `main_window.py` and `app_service.py` that are not on changed lines.
- One failing test not from this session: `tests/gui/test_sidebar_shell.py::test_main_window_lists_screens` (expects no Market Floor or AI Desk in the sidebar; same as T141, T187).

Known limits: the CLI usage-limit wording is not yet seen in a real message; the regex is unconfirmed (T186). RSP is only used after a TWS download and a desk run (T185). App checks are open in T182–T185.
