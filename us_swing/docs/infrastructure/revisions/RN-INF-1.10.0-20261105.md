# Revision Note — RN-INF-1.10.0-20261105

**Tool:** INF (+ GUI wiring)
**Version:** 1.10.0
**Date:** 2026-11-05
**Type:** feature
**Author:** Claude Opus 5.5 under user direction
**Phase:** Daily Telegram briefs (proposal Option A, Phase 1)

---

## Summary

The bot no longer says "USSwing started" on every launch. Instead it sends a Morning brief once per US trading day in pre-market (04:00–09:30 ET, 14:30–20:00 IST in US winter), also on a late launch in that window. The brief shows SPY, QQQ and IWM pre-market move against the official previous close, VIX, open trades with unrealized P&L, waiting signals, the last screener run, and, when AI notes are on, a 2–3 line AI note that is dropped if it uses a number not in the facts. The Day-end report now lists each trade closed in the New York day, win rate, best and worst trade, from 16:05 ET until midnight ET. A per-user send log in `~/.usswing/notify_state.json` stops a second send after a restart. Settings → Telegram: the Tool started tick is now Morning brief.

## Changes

| File | Change |
|---|---|
| `core/notifications/_briefs.py` | New: `brief_due`, `day_end_due`, `is_trading_day`, `SendLog`, `brief_facts`, `numbers_ok` |
| `core/notifications/_events.py` | `MarketQuote`, `TradeLine`, `MorningBriefEvent`; `DayEndPnLEvent` gains `session_date`, `trades` |
| `core/notifications/_formatters.py` | Morning brief and Day-end v2 text |
| `gui/morning_brief.py` | New: Yahoo quotes, AI note, background send |
| `gui/app_service.py` | No startup message; brief and day-end triggers; day-end from closed trade cycles of the ET day; send log marked only after the worker takes the message |
| `gui/notification_worker.py` | `publish_event` returns whether it queued the event |
| `gui/settings_panel.py`, `gui/user_store.py`, `data/models.py` | `notify_morning_brief` toggle |
| `tests/conftest.py` | Send log points at a temp file in tests |

## Requirements

FO-INF-012 and SRD-INF-012.001–.006 approved by user 2026-11-05 → Implemented. SRD-INF-012.005 window widened to midnight ET after review.

## Verification

- Notification, brief and Telegram tests pass (UT-INF-012.*, UT-INF-010.001.M09.*); full suite: 1841 pass, 11 fail. The same 11 fail on a clean copy of the previous commit (candle builder, screener preset); `tests/screener/test_llm_claude_screener.py` imports a removed module and was left out.
- Live: a brief built at 09:20 ET with real Yahoo data showed QQQ −1.20% against the official close 691.95; with Claude (Sonnet 5.5) the AI note used only fact numbers.
- Review (pyqt-code-reviewer): 2 HIGH and 2 MEDIUM fixed (mark only after send, stale quotes, day-end after 20:00); multi-user point not applicable (active user is fixed at start).

## Known limits

- `NYSE_HOLIDAYS` covers 2026 only and has no early-close days; 2027 needs a table update.
- The app must be open in pre-market; no auto start.
- `UserProfile.notify_tool_started` is still saved but no longer read.
