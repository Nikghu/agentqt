# Revision Note — RN-EXE-1.42.0-20261123

**Version:** 1.42.0
**Date:** 2026-11-23
**Tool:** EXE (+ GUI, see RN-GUI-2.9.0-20261123)
**Artifact:** FO-EXE-022 / SRD-EXE-022.001–.017
**Type:** Feature

---

## Summary

Custom indicator plugins are finished end to end. A user writes an indicator in Python with the public `usswing` library, which now lives in `us_swing/sdk/`. The app checks the file, loads it into one shared registry, and uses it in live trading and replay, with a failure guard and a Telegram alert. A testing kit, the `indicator check` command and an HTML chart preview help the user test the file.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-EXE-022.001.M01 | `sdk/usswing/__init__.py`, `_parameters.py`, `_indicator.py` | New public library (`USSwingIndicator`, `Number`, `Input`, `compute`); `candles()` always gives a `datetime` column (replay used `ts`) |
| MD-EXE-022.005.M02 | `src/us_swing/core/indicator_plugins/_check.py` | New plugin check: class and field checks, labels, name, dry run on 3 stocks |
| MD-EXE-022.008.M03 | `src/us_swing/core/indicator_plugins/_registry.py`, `src/us_swing/gui/app_service.py` | Shared folder `~/.usswing/plugins/indicators`; `load()` and `move_user_folders()`; load at start and on reload |
| MD-EXE-022.010.M04 | `src/us_swing/core/indicator_plugins/_runner.py`, `src/us_swing/execution/strategy_engine/_evaluator.py`, `src/us_swing/core/expr/series.py` | Plugin call by name for live (last value) and replay (full series) |
| MD-EXE-022.012.M05 | `src/us_swing/core/indicator_plugins/_guard.py`, `src/us_swing/execution/strategy_engine/_engine.py`, `src/us_swing/gui/app_service.py`, `src/us_swing/gui/strategies_pane.py`, `src/us_swing/core/notifications/_events.py`, `_formatters.py` | 2 s limit, one warning per candle, stop users after 3 failures in a row, Telegram alert, refused start for a missing plugin |
| MD-EXE-022.015.M06 | `sdk/usswing/testing.py`, `src/us_swing/core/indicator_plugins/_cli.py`, `src/us_swing/__main__.py` | Testing kit (`load_candles`, `run`); command `indicator check <file> [--symbols] [--days] [--trace]` |
| MD-EXE-022.017.M07 | `sdk/usswing/dev.py` | `preview()` writes and opens an HTML chart with candles, indicator and debug values |

Packaging: `USSwing.spec` ships `sdk/usswing/*.py`; `pyproject.toml` `mypy_path` includes `sdk`.

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-EXE-022.001 | Package `usswing` exports `USSwingIndicator`, `Number` and `Input` | Implemented |
| SRD-EXE-022.002 | `Number` and `Input` describe one parameter each; bad default raises an error | Implemented |
| SRD-EXE-022.003 | Subclass declares name, description, version, output type and parameters; `calculate()` gives one value per candle | Implemented |
| SRD-EXE-022.004 | `candles()`, `parameter()` and `debug_value()` helpers; candles are read-only | Implemented |
| SRD-EXE-022.005 | Plugin check refuses bad structure, duplicate or built-in names, and `usswing.dev` imports | Implemented |
| SRD-EXE-022.006 | Plugin check refuses a `calculate()` that reads a label not in `parameters` | Implemented |
| SRD-EXE-022.007 | Plugin check dry run on 3 stocks: one value per candle, no error, under 2 s per stock | Implemented |
| SRD-EXE-022.008 | Files kept in `~/.usswing/plugins/indicators/`, shared by all users; old per-user folders moved once (wording changed 2026-11-23) | Implemented |
| SRD-EXE-022.009 | Files that pass the check go into the registry at start and on reload; a broken file never stops the app | Implemented |
| SRD-EXE-022.010 | Trigger expressions call a plugin by name with arguments in `parameters` order | Implemented |
| SRD-EXE-022.011 | Live uses the last value; replay uses the full series from the same `calculate()` | Implemented |
| SRD-EXE-022.012 | Plugin error or timeout gives no signal for that candle and one warning | Implemented |
| SRD-EXE-022.013 | Three failures in a row stop every strategy that uses the plugin and alert the user | Implemented |
| SRD-EXE-022.014 | A strategy that names a plugin not loaded cannot start; the message names the plugin | Implemented |
| SRD-EXE-022.015 | Testing kit: `load_candles()` reads local candles; `run()` returns series and debug values | Implemented |
| SRD-EXE-022.016 | `indicator check <file>` runs the check, prints the result, can save a CSV | Implemented |
| SRD-EXE-022.017 | `usswing.dev.preview(...)` opens a browser chart (Could) | Implemented |

---

## Design Decisions

- The `usswing` library lives in `us_swing/sdk/` so `src/` holds only the app. The import name stays `usswing`.
- One indicator folder is shared by all users (user decision, 2026-11-23). Old `plugins/<user id>/` folders are moved once; a clash or locked item stays and is tried again next start.
- `candles()` always gives a `datetime` column, so live and replay code match.
- A failed plugin call gives no signal for that candle. Three failures in a row stop the users of that plugin, and open trades stay managed.
- `indicator check` and the Import dry run still read `candles.db`. Asked to the user whether they should read Backtest Data instead.
- `sdk/usswing/testing.py` and `_cli.py` must import `us_swing.data` first (db and data import cycle).

---

## Issues Resolved

None

---

## Test Coverage

- UT-EXE-022.* Pass (49 cases in TRACE). New cases: UT-EXE-022.003.M01.T04, .008.M03.T01–T03, .012.M05.T04, .014.M05.T03.
- Open checks: TODO T232–T236 (user app checks). The frozen exe console output of `indicator check` is not yet tried after an installer build.
- Known limits: a hung plugin thread is freed only by restart. The RSP Symbol Type gives the stock's own candles (same as built-ins).
