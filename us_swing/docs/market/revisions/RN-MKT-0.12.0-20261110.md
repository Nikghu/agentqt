# Revision Note — RN-MKT-0.12.0-20261110

**Version:** 0.12.0
**Date:** 2026-11-10
**Tool:** MKT (with GUI)
**Artifact:** FO-MKT-011 (P10) / SRD-MKT-011.001–.009; SRD-GUI-034.042–.044
**Type:** Feature

---

## Summary

P10 lets the Master ask the desk for a new Market Floor panel in plain words. The Add panel catalog has an "Ask the desk for new data" box. The app saves the request as an append-only `data_requests` row and posts a `data_request` event. The desk wakes a new data employee ("Expert 7", `emp-009`, skill `data_recipe`). It fills a recipe from a fixed menu: one source (scores, ideas, stock RS, sectors, pick results), columns, filters, sort and row limit. Code checks the recipe against the menu and runs it read-only on the latest data day. The model never writes SQL. The proposed panel waits in AI Desk → Approvals waiting with its recipe in words and 5 preview rows. Approve adds it to the Floor catalog, marked "(asked)". Its rows are worked out again each time it is shown, so it has the new day's data after each evening run. A request the desk cannot build shows its reason for one day.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-MKT-011.004.M03 | `us_swing/src/us_swing/core/desk_recipes.py` | New: the fixed menu, `DataRecipe`, `RecipeFilter`, `check_recipe()`, `run_recipe()` (read-only, values bound), `recipe_words()` |
| MD-MKT-011.001.M01 | `us_swing/src/us_swing/core/desk_data_asks.py` | New: append-only `data_requests` and `asked_products` tables; `ask_data()`, `open_request()`, `add_asked()`, `waiting_products()`, `approved_products()`, `failed_products()`, `decide_product()` |
| MD-MKT-011.002.M02 | `us_swing/src/us_swing/core/desk_events.py` | Changed: event kind `data_request` (priority 0, 5-minute deadline, 2-hour expiry); one key per request |
| MD-MKT-011.003.M04 | `us_swing/src/us_swing/market/data_recipe.py` | New: `DataRecipeSkill`, `DataRecipeAnswer` |
| MD-MKT-011.007.M05 | `us_swing/src/us_swing/core/desk_floor.py` | Changed: approved asked panels in `products()` and `rows()` |
| MD-MKT-011.008.M06 | `us_swing/src/us_swing/market/employees/emp-009/`, `core/desk_steps.py` | New default employee "Expert 7" (expert, `data_recipe`, trigger `data_request`, 20 calls a day, USD 3 a month); skill path |
| MD-GUI-034.042.M37 | `us_swing/src/us_swing/gui/floor_dialogs.py`, `gui/market_floor.py` | Changed: Ask box and button in the Add panel catalog; the catalog refreshes its products each time it opens |
| MD-GUI-034.043.M38 | `us_swing/src/us_swing/core/desk_feed.py`, `gui/floor_feed.py`, `gui/ai_desk_hiring.py` | Changed: asked panel Ask cards with Approve and Reject; failed request cards in Approvals waiting |
| — | `us_swing/USSwing.spec` | Changed: hidden import `us_swing.market.data_recipe` |
| — | `us_swing/tests/desk/test_desk_events.py`, `tests/market/test_p5b_defaults.py` | Changed: event kinds and skill list now include P10 (intended) |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-MKT-011.001 | A Floor data request is saved as a `data_requests` row and posts one `data_request` event. | Implemented |
| SRD-MKT-011.002 | `data_request`: priority 0, 5-minute deadline, 2-hour expiry, one event per request. | Implemented |
| SRD-MKT-011.003 | The data recipe skill turns the oldest open request into a recipe from the fixed menu. | Implemented |
| SRD-MKT-011.004 | Code checks each recipe and runs it read-only on the latest data day, at most 100 rows. | Implemented |
| SRD-MKT-011.005 | Each answer adds one `asked_products` row, proposed or failed with the reason. | Implemented |
| SRD-MKT-011.006 | Approve or reject is one `approvals` row of kind `data_product`; a second decision is refused. | Implemented |
| SRD-MKT-011.007 | Approved panels are in the Floor catalog, with rows from the latest data day each time. | Implemented |
| SRD-MKT-011.008 | Default data employee `emp-009` ("Expert 7") with trigger `data_request`. | Implemented |
| SRD-MKT-011.009 | `[Data]` log lines with the request number. | Implemented |
| SRD-GUI-034.042 | Ask box and button in the Floor Add panel catalog, with a sent note. | Implemented |
| SRD-GUI-034.043 | Approvals waiting lists each proposed panel with recipe words, 5 preview rows, Approve and Reject. | Implemented |
| SRD-GUI-034.044 | A failed request shows its reason for one day, without buttons. | Implemented |

---

## Design Decisions

- User answers (2026-11-07): the AI fills a safe recipe (no free SQL); preview, then approve; refresh after each evening run; ask from the Floor catalog. FO and SRDs approved by the user on 2026-11-10.
- Table and column names come only from the menu in code; filter values and the row limit are bound as parameters; the database is opened read-only.
- The scores source joins `stock_rs` so a request can filter by sector (for example "long scores above 80 in Technology").
- The menu and the request code live in `core`, so the GUI never imports `market` and the desk never imports `gui`.
- Ask is the default button while the box has text, so Enter sends the request instead of adding the selected panel.
- Review fixes (both reviewers approved): the decision check and insert run inside one locked transaction (`BEGIN IMMEDIATE`); the sent note hides once a new request is typed.

---

## Test Results

- New tests: 25 MKT (`tests/market/test_data_recipe.py`, including an end-to-end desk run with a fake model and an SQL injection check) and 7 GUI (`tests/gui/test_floor_data_ask.py`); all Pass. Coverage: `desk_recipes.py` 100%, `desk_data_asks.py` 96%, `data_recipe.py` 97%.
- Full suite (project venv): 2523 passed, 2 skipped, 14 failed. Two failures were the intended list tests, now updated and passing. The other 12 also fail without P10 (T112 and the sidebar test). `tests/screener/test_llm_claude_screener.py` cannot be collected, because it imports a module that is not in git; it was left out of the run.

---

## Open

- T135: user check. Restart the desk first, so `emp-009` is seeded. Then ask for a panel from the Floor Add panel box, approve it in AI Desk → Command, and add it to a Floor tab.
