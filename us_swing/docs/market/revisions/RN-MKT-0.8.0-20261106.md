# Revision Note — RN-MKT-0.8.0-20261106

**Version:** 0.8.0
**Date:** 2026-11-06
**Tool:** MKT
**Artifact:** FO-MKT-007 (P5d) / SRD-MKT-007.001–.008; SRD-GUI-034.022–.026 (FO-GUI-034 reopened, status left at Reopen)
**Type:** Feature

---

## Summary

P5d AI report pages, on the P5a–P5c desk harness. Expert 6 (`report_page`, `emp-007`) writes one HTML page per data day from the lead brief, regime, sector and news views. The page is cleaned by an allow-list in `core/report_html.py`, saved as an append-only version in `canvas_pages`, and shown in AI Desk → Pages in a sealed preview. The user reopened FO-GUI-034: Studio renamed Pages, the Command chat is named by role (lead chat); its status is left at Reopen for the user to set back to Approved.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-MKT-007.003.M01 | `us_swing/src/us_swing/core/report_html.py` | New: allow-list HTML cleaner on `html.parser`; CSS cleaned until stable, no CSS escapes; only the first of a repeated attribute; `data:image` PNG/JPEG/GIF/WebP only; `sealed_document()` with CSP `default-src 'none'` |
| MD-MKT-007.001.M02 | `us_swing/src/us_swing/market/report_page.py` | New: `ReportPageSkill` (key `report_page`), needs `lead_brief`; reads the evening brief from the desk briefs table by SQL; never imports `desk` |
| MD-MKT-007.004.M03 | `us_swing/src/us_swing/market/store.py` | Changed: table `canvas_pages`, append-only with no-update and no-delete triggers; `add_page()` |
| MD-MKT-007.007.M04 | `us_swing/src/us_swing/market/employees/emp-007/` | New: default employee "Expert 6" (skill `report_page`, trigger `after_run`) |
| MD-GUI-034.022.M19 | `us_swing/src/us_swing/gui/ai_desk_pages.py` | New: Pages section; lists pages newest day first with versions; keyboard row change via `currentCellChanged` |
| MD-GUI-034.024.M20 | `us_swing/src/us_swing/gui/sealed_view.py` | New: sealed preview on a shared off-the-record profile; request filter allows only `data:` and `about:`; navigation blocked; JS, local files, remote URLs, storage, plugins, WebGL and DNS prefetch off |
| — | `us_swing/src/us_swing/core/desk_floor.py` | Changed: `report_pages()` and `report_page()` read functions |
| — | `us_swing/src/us_swing/core/desk_steps.py` | Changed: `report_page` skill path |
| — | `us_swing/src/us_swing/gui/ai_desk.py` | Changed: Pages live section, built only when first shown, so no web view starts with the desk |
| — | `us_swing/src/us_swing/gui/ai_desk_sections2.py` | Changed: `studio_frame` removed |
| — | `us_swing/src/us_swing/gui/ai_desk_sample.py` | Changed: generic names only (Lead 1, Expert 1–6, Champion 1–3, Engineer 1, Secretary 1) |
| — | `us_swing/src/us_swing/gui/floor_sample.py` | Changed: generic names only |
| — | `us_swing/USSwing.spec` | Changed: hidden import `us_swing.market.report_page` |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-MKT-007.001 | Report page facts: lead brief of the latest data day with its picks, plus the regime, sector and news views of that day. | Implemented |
| SRD-MKT-007.002 | Page answer: title up to 80 characters; one HTML page with inline CSS up to 200 KB; images only as inline data. | Implemented |
| SRD-MKT-007.003 | Code cleans the page: removes scripts, event handlers, outside or local links and images, and tags or attributes not on an allow list. | Implemented |
| SRD-MKT-007.004 | Each clean page is added to `canvas_pages` as a new version (data day, version, title, HTML, time). Append-only. No employee column, because a skill does not know its employee (reopened by user). | Implemented |
| SRD-MKT-007.005 | Missing, invalid or still over-size answer: no version and no brief; the last good version stays. | Implemented |
| SRD-MKT-007.006 | After a version is added, a short feed brief with the page title marks the day done. | Implemented |
| SRD-MKT-007.007 | Default expert employee `emp-007` ("Expert 6", trigger `after_run`); skill added to the skill list. | Implemented |
| SRD-MKT-007.008 | Log the data day, version, page size before and after cleaning, and items removed (`[Report]` prefix). | Implemented |
| SRD-GUI-034.022 | AI Desk "Studio" renamed "Pages"; lists report pages from `canvas_pages`, newest day first, with the versions of each day. | Implemented |
| SRD-GUI-034.023 | Choosing a version shows it in a sealed preview beside the list; cleaned again before it is shown. | Implemented |
| SRD-GUI-034.024 | Sealed preview uses its own off-the-record profile with JavaScript, local file access and remote URL access off. | Implemented |
| SRD-GUI-034.025 | Request filter in the sealed preview blocks every request except the page itself; each block logged at DEBUG. | Implemented |
| SRD-GUI-034.026 | With no page yet, the Pages section shows a short empty note instead of a blank preview. | Implemented |

---

## Design Decisions

- Expert 6 writes the page from the lead brief. The cleaner is an allow-list in `core/`, so the GUI reuses it.
- Page versions are append-only. A failed run keeps the last good version and the day can be tried again.
- The Pages section is built only when first shown, so no web view starts with the desk.
- The sealed preview uses its own off-the-record profile, with all active content and outside requests off. The page is cleaned again before it is shown.
- No employee column in the page row: a skill does not know its employee (user decision, SRD-MKT-007.004).
- `market` never imports `desk`. The page reads the evening brief from `desk.db` by SQL.
- Generic names only in sample data, code and tests.

---

## Issues Resolved

None

---

## Test Coverage

- UTCD MKT-007: 23 UT rows Pass (`tests/market/test_report_html.py`, `test_report_page.py`, 2 in `test_p5b_defaults.py`). UTCD GUI-034.022–.026: 9 UT rows Pass (`tests/gui/test_ai_desk_pages.py`, `test_sealed_view.py`).
- Updated old tests: UT-MKT-005.018.M09.T01 (skill list adds `report_page`); UT-GUI-034.010.M03.T02 (Pages is real, no sample tag).
- Full suite: 2326 passed, 12 failed (the same old failures, TODO T112), 2 skipped.
- Code review found 3 cleaner bypasses (CSS rebuilt `url(` after removal, duplicate `img` src, SVG fill `url()`) and a self-closed style tag. All fixed; tests UT-MKT-007.003.M01.T07–T08.
- PyQt review: web view built at desk open (fixed: built lazily); keyboard row change (`currentCellChanged`); profile reset on destroy; DNS prefetch off.
- Real run (desk copy in scratchpad; ideas day 2026-11-04 forced in the check script only, not in the app): Expert 6 answered with claude-haiku-5-5 in 12.3 s, 4525 tokens. Page 4 KB saved as version 1, 2 items removed, feed brief posted. Pages section checked in a real window with the sealed preview.
- Known limits: gateway time limit is 90 s, but the schema asks for 20–40 KB pages. An old `desk.db` view table still carries an old employee name (flag only, not changed).
