# Revision Note — RN-MKT-0.7.0-20261106

**Version:** 0.7.0
**Date:** 2026-11-06
**Tool:** MKT
**Artifact:** FO-MKT-006 (P5c) / SRD-MKT-006.001–.012; reopened SRD-MKT-003.005, SRD-MKT-005.012, SRD-MKT-005.014; SRD-GUI-034.018–.021
**Type:** Feature

---

## Summary

P5c news and event risk, on the P5a/P5b desk harness (RN-DSK-0.3.0-20261106). A desk step "News" runs after "Ideas" and keeps stock and market headlines. A yearly economic calendar (FOMC, CPI, jobs, PCE, GDP) lists the events. A news review expert gives each listed idea a tone and points, and the final score is 0.9 × the P3 score + news points. The risk check and the lead brief read the news view, and the Floor shows Latest news, News tags and Calendar. Yahoo Finance news is down, so headlines come from Yahoo per-stock RSS and CNBC / Yahoo market RSS.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-MKT-006.001.M01 | `us_swing/src/us_swing/market/news.py` | New: fetch and read RSS headlines (`fetch_symbol()`, `fetch_market()`, `parse_feed()`), httpx 10 s timeout |
| MD-MKT-006.001.M02 | `us_swing/src/us_swing/market/news_step.py` | New: desk step "News" (`NewsStep`), 90 s total budget, 30-day keep, re-date seen-again headlines |
| MD-MKT-006.004.M03 | `us_swing/src/us_swing/core/econ_calendar.py` | New: FOMC, CPI, jobs, PCE, GDP for 2026-11 to 2027-12; `events_between()`, `next_trading_day()`; year-aware NYSE closures 2026–2027 |
| MD-MKT-006.005.M04 | `us_swing/src/us_swing/market/news_review.py` | New: `NewsReviewSkill` (key `news_review`), tone per idea for its side, points 10/6/2, −3 before a high event, final score |
| MD-MKT-006.008.M05 | `us_swing/src/us_swing/market/store.py` | Changed: tables `news_items` and `news_tags` |
| MD-MKT-006.011.M06 | `us_swing/src/us_swing/market/employees/emp-006/` | New: default employee "Expert 5" (`news_review`, `after_run`) |
| MD-MKT-005.012.M07 | `us_swing/src/us_swing/market/risk_check.py` | Changed: needs and facts add the news review (tone, points, final score) |
| MD-MKT-005.014.M08 | `us_swing/src/us_swing/market/lead_brief.py` | Changed: needs, facts and a final score column for passed ideas |
| MD-GUI-034.018.M17 | `us_swing/src/us_swing/core/desk_floor.py` | Changed: Latest news, News tags and Calendar products read from `desk.db` and the calendar |
| MD-GUI-034.021.M18 | `us_swing/src/us_swing/gui/floor_layouts.py` | Changed: default "News & Calendar" tab with three panels |
| MD-DSK-001.021.M07 | `us_swing/src/us_swing/core/desk_steps.py` | Changed: News step and `news_review` skill path |
| — | `pyproject.toml` | Changed: `feedparser>=6.0` |
| — | `USSwing.spec` | Changed: hidden imports `us_swing.market.news_step`, `us_swing.market.news_review`, `feedparser` |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-MKT-006.001 | Desk step "News" after "Ideas" keeps Yahoo headlines of the last 3 days for each listed idea. | Implemented |
| SRD-MKT-006.002 | Market headlines of the last 24 hours from fixed public RSS feeds (at most 30). | Implemented |
| SRD-MKT-006.003 | A headline is kept once; headlines older than 30 days are deleted on each run. | Implemented |
| SRD-MKT-006.004 | Yearly economic calendar in code: date, New York time, name and importance. | Implemented |
| SRD-MKT-006.005 | News review facts: listed ideas with headlines, market headlines, rule regime and events of the next 5 trading days. | Implemented |
| SRD-MKT-006.006 | News review answer: tone per listed idea and a reason up to 120 characters; market note up to 400 characters. | Implemented |
| SRD-MKT-006.007 | News points: 10 positive, 6 neutral, 2 negative; −3 before a high event; never below 0. | Implemented |
| SRD-MKT-006.008 | Final score = 0.9 × P3 score + news points, kept in `news_tags`. | Implemented |
| SRD-MKT-006.009 | The news review market note goes to the AI feed. | Implemented |
| SRD-MKT-006.010 | Risk check and lead brief read the news view; facts show tone, reason and final score. | Implemented |
| SRD-MKT-006.011 | Default employee `emp-006` "Expert 5" (`after_run`); skill added to the skill list. | Implemented |
| SRD-MKT-006.012 | The News step logs stocks fetched, headlines kept, failed feeds and rows deleted. | Implemented |
| SRD-MKT-003.005 | Score parts scaled by 100/90, because news is not in the P3 score (reworded). | Implemented |
| SRD-MKT-005.012 | Risk check facts include the news view (reopened). | Implemented |
| SRD-MKT-005.014 | Lead facts include the news view and final score (reopened). | Implemented |
| SRD-GUI-034.018 | "Latest news" panel shows real headlines from `desk.db`, without the Sample tag. | Implemented |
| SRD-GUI-034.019 | "News tags" panel lists listed ideas of the latest day with tone, reason, points and final score. | Implemented |
| SRD-GUI-034.020 | "Calendar" panel shows economic events of the next 10 trading days. | Implemented |
| SRD-GUI-034.021 | Default News & Calendar tab holds Latest news, News tags and Calendar. | Implemented |

---

## Design Decisions

- Headlines come from Yahoo per-stock RSS, not yfinance news (down). Market headlines come from CNBC top/economy and Yahoo SPY feeds.
- The tone is judged for the idea's side: for a short, good company news is negative. This is said in the soul and in the schema field description, so the points code needs no side flip.
- News points and the event penalty are applied by code, even when the AI gives no answer.
- A failed news review retry keeps the day's earlier real tags.
- A headline seen again on a later day moves to that day, so the story stays in the day's facts.
- The economic calendar is in `core/` because both `market` and the Floor read it.
- NYSE closures are year-aware (2026–2027). The app-wide `data/market_calendar.py` list still has no year (TODO T125).
- No employee names in code or tests. The default is "Expert 5"; the Master user can rename it.

---

## Issues Resolved

None

---

## Test Coverage

- UTCD MKT-006: 43 rows in `docs/market/UTCD.md`, all Pass. UTCD GUI-034.018–.021: 10 rows, all Pass.
- SRD-MKT-003.005, SRD-MKT-005.012 and SRD-MKT-005.014 reopened rows are covered by UTCD MKT-006.010 and the existing P3 and P5b rows; all Pass.
- Full suite: 2291 passed, 12 failed (the same old failures, TODO T112), 2 skipped. Coverage of new and changed modules 95–100% (total 98%).
- Real run 2026-11-06 (Claude Code CLI, claude-haiku-5-5), data day 2026-11-04: 203 headlines kept (20 stocks and 30 market headlines), no feed failed. All 5 AI answers valid on the first try; about 30,700 tokens; cost 0. Code-review fixes and real-run details: DD-MKT-006.001.D01, "After the real run" and "After code review".
