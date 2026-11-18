# Revision Note — RN-SCR-2.13.0-20261118

**Version:** 2.13.0
**Date:** 2026-11-18
**Tool:** SCR (with GUI)
**Artifact:** FO-SCR-018 / SRD-SCR-020.001–.009, SRD-GUI-022.020–.021
**Type:** Feature

---

## Summary

AI Ranking phase 3 adds company data and a blind bull vs bear review. Four new ticks — **Earnings surprise**, **Fundamentals**, **Short interest** and **Analyst changes** — fetch Yahoo Finance data (each part cached once per stock per day, and only the parts a ticked box needs) and add one line per stock to the STOCK CONTEXT block of the single ranking request. New red flags: an EPS miss below -1% ("EPS miss -3.5%"), short interest above 20% of float, and any downgrade in the last 7 days ("1 downgrade"). Fundamentals are shown only. With **Bull vs bear review** ticked (Claude Code CLI only), each final pick gets one CLI request with no tools after web research, 3 at a time. The reviewer sees only facts: price and trend, the ticked data, rule flags, headlines and research. It never sees the AI score, rank, reason, news tone, Query or other stocks. It returns up to 3 bull and 3 bear points and a verdict of Long, Short, Wait or Avoid with a confidence; Wait or Avoid adds a "Review: wait/avoid" flag. Scores and order do not change. Each review request and reply is in the AI transcript. The Edit Preset ticks now sit in two groups, Stock data and Top picks only. The detail shows new tags, a Fundamentals line, an Analyst changes list and a Bull vs bear box. Header tags now wrap onto more lines instead of scrolling sideways.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-SCR-020.002.M41 | `src/us_swing/core/stock_context/_company.py` | New: `CompanyLookup`, `CompanyFacts`, `AnalystChange`; cache `~/.usswing/company_cache.json` |
| MD-SCR-020.007.M42 | `src/us_swing/core/stock_context/_review.py` | New: `review_picks()`, `review_facts()`, `price_line()`, `Review`, `ReviewRun`, review prompt |
| MD-SCR-018.003.M37 | `src/us_swing/core/stock_context/_context.py`, `__init__.py` | Added: company fields, surprise / short / analyst levels and flags, text helpers, context line parts |
| MD-SCR-001.001.M01 | `src/us_swing/screener/preset.py` | Added: 5 kinds; review needs Claude |
| MD-SCR-003.001.M10 | `src/us_swing/screener/executor.py` | Added: company lookup, review step after research, `ai_review`, transcript turns |
| MD-GUI-022.001.M01 | `src/us_swing/gui/screener_panel.py`, `gui/screener_views.py` | Added: tick groups; company tags, Fundamentals, Analyst changes, Bull vs bear box; wrapping tag row |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-SCR-020.001 | New choices; review needs Claude | Implemented (approved by user 2026-11-18) |
| SRD-SCR-020.002 | Daily-cached Yahoo company facts, only ticked parts | Implemented (approved by user 2026-11-18) |
| SRD-SCR-020.003 | Surprise levels and miss flag | Implemented (approved by user 2026-11-18) |
| SRD-SCR-020.004 | Short interest flag; fundamentals shown only | Implemented (approved by user 2026-11-18) |
| SRD-SCR-020.005 | Analyst changes, target and downgrade flag | Implemented (approved by user 2026-11-18) |
| SRD-SCR-020.006 | Company facts in the context block | Implemented (approved by user 2026-11-18) |
| SRD-SCR-020.007 | Blind review per final pick, 3 at a time | Implemented (approved by user 2026-11-18) |
| SRD-SCR-020.008 | Review reply, verdict and flag | Implemented (approved by user 2026-11-18) |
| SRD-SCR-020.009 | Facts, review and transcript saved | Implemented (approved by user 2026-11-18) |
| SRD-GUI-022.020 | Two tick groups; review only with Claude | Implemented (approved by user 2026-11-18) |
| SRD-GUI-022.021 | Company tags and sections, Bull vs bear box | Implemented (approved by user 2026-11-18) |

---

## Tests

17 new UT cases Pass (14 UT-SCR-020.*, 3 UT-GUI-022.020–.021). 571 screener, core and related GUI tests pass. Ruff clean; mypy --strict clean on `core/stock_context` and `gui/screener_views.py`. Real checks: a live Yahoo lookup for NVDA and AMD returned all four parts in 15 s; one live Claude review for NVDA took 13.5 s and returned a readable Wait (low) verdict naming the missing data. The detail and the AI box were checked by screenshot in a real window, wide and narrow.

## Known

- Yahoo debt/equity comes as a percent; it is shown divided by 100 (16.97 → 0.17).
- The review is an AI opinion on the facts given; it does not change scores or order.
- `test_preset.py` T17/T18 and `test_llm_claude_screener.py` were already failing before this change.
- User app check: TODO T209.
