# Revision Note — RN-SCR-2.12.0-20261118

**Version:** 2.12.0
**Date:** 2026-11-18
**Tool:** SCR (with GUI, INF)
**Artifact:** FO-SCR-017 / SRD-SCR-019.001–.007, SRD-GUI-022.018–.019, SRD-INF-011.004
**Type:** Feature

---

## Summary

AI Ranking phase 2 adds news and web research. With **News tone** ticked, the newest 8 Yahoo Finance headlines from the last 5 days (cached once a day per stock) go into the STOCK CONTEXT block, and the ranking AI returns a news tone from -1 to +1 per stock in the same request. Tone ≤ -0.3 is red and adds a "Negative news" flag; below 0 yellow; ≥ 0.3 green. With a context block the OpenRouter no-query path now asks for the same JSON array as the other paths. With **Web research for top picks** ticked (Claude Code CLI only), each final pick is researched by the CLI with only the web search tool, 3 at a time, 180 s each; the result is a summary of at most 60 words, up to 3 source links and any major risk, which adds a "Research: …" flag. Research does not change scores or order. The detail shows a news chip, a "News, last 5 days" list with linked titles, and a Web research box with source links. Earnings and news share a new daily cache file helper.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-SCR-019.002.M38 | `src/us_swing/core/stock_context/_news.py` | New: `NewsLookup`, `Headline`, Yahoo item parser |
| MD-SCR-019.005.M39 | `src/us_swing/core/stock_context/_research.py` | New: `research_picks()`, `Research` |
| MD-SCR-019.002.M40 | `src/us_swing/core/stock_context/_cache.py` | New: `DailyCache`; `_earnings.py` moved onto it |
| MD-SCR-018.003.M37 | `src/us_swing/core/stock_context/_context.py`, `__init__.py` | Added: news fields, `news_level()`, `apply_news_tone()`, news lines in the block |
| MD-SCR-001.001.M01 | `src/us_swing/screener/preset.py` | Added: `news`, `research` kinds; research needs Claude |
| MD-SCR-002.003.M06 | `src/us_swing/screener/screeners/cloud_ai.py` | Added: `news_tone` in rule and parser; array format on legacy path with context |
| MD-SCR-003.001.M10 | `src/us_swing/screener/executor.py` | Added: headlines, tone merge, research step; `news_lookup`, `research_runner` |
| MD-INF-011.001.M01 | `src/us_swing/core/notifications/_ai_client.py` | Added: `AiConfig.claude_tools` (WebSearch only) |
| MD-GUI-022.001.M01 | `src/us_swing/gui/screener_panel.py`, `gui/screener_views.py` | Added: News tone / Web research ticks; news chip, News list, Web research box |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-SCR-019.001 | News and research choices; research needs Claude | Implemented (approved by user 2026-11-18) |
| SRD-SCR-019.002 | Headlines, last 5 days, newest 8, cached daily | Implemented (approved by user 2026-11-18) |
| SRD-SCR-019.003 | Headlines in prompt; AI returns news tone | Implemented (approved by user 2026-11-18) |
| SRD-SCR-019.004 | News levels and flag | Implemented (approved by user 2026-11-18) |
| SRD-SCR-019.005 | Web research per final pick, 3 at a time | Implemented (approved by user 2026-11-18) |
| SRD-SCR-019.006 | Major risk flag; failed research skipped | Implemented (approved by user 2026-11-18) |
| SRD-SCR-019.007 | News, tone and research saved | Implemented (approved by user 2026-11-18) |
| SRD-INF-011.004 | Web search tool for one CLI request | Implemented (approved by user 2026-11-18) |
| SRD-GUI-022.018 | News tone and Web research ticks | Implemented (approved by user 2026-11-18) |
| SRD-GUI-022.019 | News chip, News list, Web research box | Implemented (approved by user 2026-11-18) |

---

## Tests

17 new UT cases Pass (13 UT-SCR-019.*, UT-INF-011.004.M01.T01, 3 UT-GUI-022.018–.019). 614 screener, core and related GUI tests pass. Ruff clean; mypy --strict clean on `core/stock_context` and the AI client. Real checks: one live web research run for NVDA took 27 s and returned a summary, a risk and 3 links; the Yahoo news endpoint was down during the session, and the run completed with no headlines and one warning. The detail and the AI box were checked by screenshot in a real window.

## Known

- Live Yahoo headlines could not be checked today (Yahoo news returned "currently down"); the parser covers both known Yahoo formats.
- Web research text is an AI summary of web pages and can be wrong; the source links are there to check it.
- `test_preset.py` T17/T18 and `test_llm_claude_screener.py` were already failing before this change.
- User app check: TODO T208.
