# Revision Note — RN-GUI-2.1.1-20261117

**Version:** 2.1.1
**Date:** 2026-11-17
**Tool:** GUI
**Artifact:** FO-GUI-004 / SRD-GUI-004.014 / ISS-GUI-0021
**Type:** Fix

---

## Summary

A manual Run now on a screener preset no longer sends the Telegram "screener approved" message. The scheduled daily run still sends it. The Execution list refreshes after both.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-GUI-004.001.M01 | `src/us_swing/gui/app_service.py` | Changed: `notify_screener_results_updated(send_message=True)`; pick-change refresh uses it |
| MD-GUI-004.001.M01 | `src/us_swing/gui/screener_panel.py` | Changed: `_on_run_finished()` sends the message only for a scheduled run |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-GUI-004.014 | Only a scheduled screener run sends the "screener approved" message | Implemented (approved by user 2026-11-17) |

---

## Tests

UT-GUI-004.001.M01.T26–T27 added and T17 updated: all Pass. Screener, pick and notification GUI tests: 203 passed. Ruff and mypy error counts are the same as before the change.

## Known

- The Acc / Dist "Distribution" preset showing 0 matches is not a bug (see ISS-GUI-0021).
