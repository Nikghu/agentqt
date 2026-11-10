# Revision Note — RN-GUI-1.11.0-20261107

**Version:** 1.11.0
**Date:** 2026-11-07
**Tool:** GUI
**Artifact:** FO-GUI-034 / SRD-GUI-034.053–.058
**Type:** Feature

---

## Summary

The Market Floor AI feed now shows typed cards as in the approved design: a coloured type label (Result, Ask, Answer, Desk), sender, ET time with India time on hover, short text with More, and action buttons. Filter tabs All, Ideas, Asks (with count) and Alerts. Trade pick Asks can be approved or rejected right in the feed, with the same rules as AI Desk → Command. Buttons open Charts on the stock or the right AI Desk section.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-034.054.M32 | `core/desk_feed.py` (new) | Feed cards from desk.db; shared `approve_pick` / `reject_pick` |
| MD-GUI-034.054.M32 | `core/desk_floor.py` | `feed_cards()` and `home` |
| MD-GUI-034.054.M32 | `gui/ai_desk_hiring.py` | `TradePickRow` uses the shared approve and reject (same behaviour) |
| MD-GUI-034.053.M31 | `gui/floor_feed.py` | Typed cards, filter tabs, live dot, footer, action signals |
| MD-GUI-034.053.M31 | `gui/market_floor.py`, `gui/main_window.py` | Sink, chart and section signals, reload on decision and show |
| MD-GUI-034.054.M32 | `gui/floor_sample.py` | Sample feed cards |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-034.053 | Typed card look with cut text and More | Implemented |
| SRD-GUI-034.054 | Cards from briefs, picks, hires, lead replies, failed runs | Implemented |
| SRD-GUI-034.055 | Filter tabs All, Ideas, Asks n, Alerts | Implemented |
| SRD-GUI-034.056 | Approve, Reject, Open in Charts, Open Hiring, Open chat | Implemented |
| SRD-GUI-034.057 | Head with live dot; footer opens AI Desk → Command | Implemented |
| SRD-GUI-034.058 | Reload after a run, a decision and on show | Implemented |

---

## Design Decisions

- The second tab is named Ideas (user choice); it shows Result cards.
- Trigger and Alert cards are not built: no live price trigger and no desk alert source yet. Alerts shows failed runs.
- Approve and reject live in `core/desk_feed.py` (GUI-owned) so the MKT module `core/desk_trades.py` is unchanged.
- Review fix: the old feed body is freed with `deleteLater` because a card can still be in its own click handler; the body is rebuilt only when the cards changed.

---

## Tests

9 new tests Pass (`tests/gui/test_floor_feed_cards.py`); 2 older feed tests moved to cards. GUI, market and desk suites: all pass except the old sidebar list test (same on main).
