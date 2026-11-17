# Issue Report — ISS-GUI-0019

**Tool:** GUI
**Severity:** Medium (top section of a screen scrolls out of view)
**Status:** Resolved (user check pending)
**Date Opened:** 2026-11-16
**Date Resolved:** 2026-11-16
**Resolution:** SRD-GUI-019.011 (Draft); RN with the part 2 close-out
**Reporter:** User — "not sure how this bar came … if i scroll down the top section get hide. its happening for all section of left panel"

---

## Symptom

An extra up-down scroll bar showed at the right edge of every sidebar screen. Scrolling down hid the screen's top section (on Backtest: the Run / Stocks / Screener / Strategy / Account row).

## Root Cause

| Point | Detail |
|---|---|
| Outer scroll area | SRD-GUI-019.010 (ISS-GUI-0015) put all screens in one scroll area so a wide screen cannot widen the window. It scrolled up-down as well. |
| Tallest screen wins | The screen holder takes the largest minimum of all screens; wrapped text on AI Desk and Backtest made it 1250 px in a 990 px window, so every screen got a 260 px scroll. |

**SRD root cause:** SRD-GUI-019.010 covered width only and said nothing about height. SRD-GUI-019.011 added.

## Fix

| File | Change |
|---|---|
| `gui/main_window.py` | New `_WidthOnlyBox` holds the screens: asks for their minimum width only, sizes them to the window height; up-down bar off |
| `gui/ai_desk.py` | Follow-up: each AI Desk section sits in its own up-down scroll area; before, the outer scroll hid that Desk settings was taller than the window, and the fix squeezed its check boxes |
| `tests/gui/test_ai_desk.py` | UT-GUI-019.011.M04.T01 |
| `tests/gui/test_side_panels_exit_drawer.py` | UT-GUI-019.011.M03.T01; T01 of 019.010 updated for the holder |

Checked with the real Backtest, Market Floor and AI Desk screens at 1790 × 990: scroll range 0 on all three, header on top.

## User step

Restart the app and open each sidebar screen (T189).
