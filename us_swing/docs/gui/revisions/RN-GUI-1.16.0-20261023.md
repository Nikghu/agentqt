# Revision Note — RN-GUI-1.16.0-20261023

**Version:** 1.16.0
**Date:** 2026-10-23
**Tool:** GUI
**Artifact:** FO-GUI-018 / SRD-GUI-018.008–.011
**Type:** Feature

---

## Summary

The IBKR feed toggle in the title bar moves into a Connections panel at the bottom of the left sidebar. The panel shows Internet, IBKR Feed and Market rows, with a power button to connect or disconnect. During auto-connect the Feed row shows the attempt number and a countdown; the Market row shows the time to the close or the next open. In mini mode the panel is a single plug button with a worst-status dot.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-018.008.M04 | `us_swing/src/us_swing/gui/sidebar.py` | `_ConnectionsPanel` added; mini plug button with worst-status dot; `set_feed_retry()` / `clear_feed_retry()`; `market_text()` |
| MD-GUI-018.005.M03 | `us_swing/src/us_swing/gui/main_window.py` | `_FeedToggle` removed from the title bar; auto-connect loop calls `set_feed_retry()` / `clear_feed_retry()` (timing unchanged) |
| MD-GUI-017.001.M02 | `us_swing/src/us_swing/gui/theme.py` | Connections rules in `_sidebar_qss`; `feed_hover_*` colour keys removed; scrollbar add-page / sub-page fix (committed separately as d893458b) |
| MD-GUI-018.008.M04 | `us_swing/assets/icons/plug.svg` | New plug icon (Lucide 0.460.0, ISC licence) |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-018.008 | Connections panel above the footer with Internet, IBKR Feed and Market rows and a power button; title bar feed toggle removed | Implemented |
| SRD-GUI-018.009 | Feed row shows attempt number and countdown while auto-connect retries; power button tries at once | Implemented |
| SRD-GUI-018.010 | Market row shows session and time to close or next open, skipping weekends and NYSE holidays | Implemented |
| SRD-GUI-018.011 | Mini mode shows a plug button with worst-status dot and tooltip; click acts like the power button | Implemented |

---

## Design Decisions

- The power button asks for confirmation before disconnecting; it is disabled while a probe runs.
- "Try now" is offered between auto-connect retries.
- Mini mode uses one plug button with a worst-status dot (offline > retrying > not connected > live), not a badge per row.
- Retry timing is unchanged; the panel only displays it.
- The Market countdown uses Eastern Time and is DST-safe.

---

## Issues Resolved

None

---

## Test Coverage

8 new tests in `tests/gui/test_sidebar_shell.py` (UT-GUI-018.008.M04.T01–T04, UT-GUI-018.009.M04.T01, UT-GUI-018.010.M04.T01–T02, UT-GUI-018.011.M04.T01), all Pass. GUI suite: 313 passed. ruff clean on the changed files; mypy --strict clean on `sidebar.py`; `main_window.py` mypy errors fell from 34 to 31 (all pre-existing). pyqt-code-reviewer APPROVED; its DST countdown and redundant restyle findings were fixed. The panel was rendered in all states for a visual check. Not yet checked by the user in the running app.
