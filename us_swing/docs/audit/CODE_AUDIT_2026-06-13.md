# us_swing — Code Audit (Performance, Concurrency, Broker, Dead Code)

**Date:** 2026-06-13
**Scope:** Read-only analysis. No code was changed.
**Goal:** Lightweight, scalable, professional tool. Find performance issues, race
conditions, the 1–2 second GUI hang, broker-logic problems, and dead/badly-written code.
**Severity policy (from the request):** Tool performance and broker logic = **High**.
Everything else = **Medium**. Low items are intentionally omitted.

Each finding below is written so it can be pasted directly as an issue description:
it has a location, the symptom, the root cause, the evidence, and a fix direction.

---

## How the live system is wired (mental model)

This matters for every finding, so read it first.

- The app runs on the **Qt GUI thread** (`AppService` + panels).
- `StrategyEngine` is a **QThread** that owns its **own asyncio loop**; it evaluates
  strategies and places orders.
- `TradeCycleService` runs a **second background thread** with its own asyncio loop;
  it accumulates ticks and persists cycle state.
- `LiveBarWorker` and `LiveTickWorker` are **two more QThreads**, each with its own
  asyncio loop and its own `ib_insync` connection.
- **One SQLite file** (`candles.db`) holds *everything* — price tables, `trades`,
  `trade_cycles`, `users`, `universe` (`app_service.py:1591`). It is read and written
  from all of the threads above.

So at any moment up to four threads touch the same SQLite file, and the GUI thread
both reads that file directly and reacts to signals from the worker threads.

---

## Severity summary

| ID | Severity | Category | Title |
|----|----------|----------|-------|
| H1 | High | Performance | GUI freezes 1–2 s: heavy intraday candle read on the GUI thread |
| H2 | High | Performance / Scalability | Strategy evaluation re-aggregates 1m history twice per symbol, every tick, uncached |
| H3 | High | Broker / Reliability | One SQLite file written from 4 threads with no `busy_timeout` → "database is locked" |
| H4 | High | Broker | `IBKRClient.unsubscribe_realtime_bars` is broken — subscriptions leak |
| H5 | High | Broker / Performance | Order-accept ledger write runs synchronously on the caller (GUI) thread |
| M1 | Medium | Concurrency | Tick-accumulator fields read/written outside the lock → double flush |
| M2 | Medium | Dead code | `swing_trader_data.py` (944 lines) is unused |
| M3 | Medium | Dead code | `analysis/` live-engine stack appears superseded by `execution/` |
| M4 | Medium | Performance | Full position-table refresh on every tick; 5 GUI slots per tick |
| M5 | Medium | Performance | New `sqlite3.connect` opened on every candle read (no reuse) |
| M6 | Medium | Concurrency | `IBKRClient` status/realtime callbacks fire on the ib loop thread with no marshaling |
| G1 | Medium | Performance | Position / Watchlist / Market-Watch tables full-reset on **every tick** (supersedes M4) |
| G2 | Medium | Performance | Synchronous candle DB reads on the GUI thread in Settings / Screener / Chart panels |
| S1 | Medium (low) | Dead/duplicate code | Indicator math duplicated (`analysis/indicators.py` vs screener inline) with a stale comment |

---

# HIGH

## H1 — GUI freezes 1–2 s: heavy intraday candle read on the GUI thread

**Category:** Performance (this is the reported "tool hangs for 1–2 seconds").
**Files:**
- `gui/execution_panel.py:769-799` (`_on_live_bar`, `_refresh_current`, `_render`, `_update_data`)
- `gui/execution_panel.py:755-758` (90 s fallback timer)
- `gui/app_service.py:3068-3174` (`get_intraday_candles_for_symbol`)
- `gui/chart_panel.py:714-716` (`_load_chart` → `get_candles_for_symbol`, lighter variant)

**Symptom:** The window stalls for ~1–2 seconds, periodically and after live updates.

**Root cause:** The intraday chart reload runs a **heavy synchronous DB read on the GUI
thread**. `get_intraday_candles_for_symbol` (`app_service.py:3068`) opens SQLite, pulls
up to **10,000** `price_1m` rows plus all `price_3m`/`price_15m` rows for the symbol,
then does Python-side parsing, bucket aggregation, and `json.dumps`. This is invoked:

1. On **every live candle close** for the viewed symbol — `svc.live_bar_data_updated`
   → `_on_live_bar` → `_update_data("3m")` **and** `_update_data("15m")`
   (`execution_panel.py:769-773`), i.e. two full reads back-to-back.
2. On a **90-second `QTimer`** (`_CHART_REFRESH_MS = 90_000`, `execution_panel.py:714`)
   → `_refresh_current` → again two full reads (`execution_panel.py:775-779`).
3. On symbol change → `_render` (`execution_panel.py:781-786`).

Because the GUI event loop is blocked during each read, the user sees a freeze. The
freeze is worse because this read **competes for the same `candles.db` file** with
`LiveBarWorker`, which is writing `price_3m`/`price_15m` bars at the same time (see H3).

**Evidence:** `_update_data` and `_render` are plain widget methods (no QThread), and they
call `self._svc.get_intraday_candles_for_symbol(...)` directly. The 90 s timer alone
guarantees a periodic stall even when idle.

**Fix direction:** Move the read off the GUI thread (QThread / `QThreadPool` worker that
emits the parsed result via signal), and/or cache the parsed series and only fetch the
delta since the last bar instead of re-reading 10k rows each time. Cap `limit_1m` to what
the chart actually shows. The same pattern applies to `chart_panel.py:716`.

---

## H2 — Strategy evaluation re-aggregates 1m history twice per symbol, every tick, uncached

**Category:** Performance / Scalability (engine = tool performance → High).
**Files:**
- `execution/strategy_engine/_engine.py:415-437` (`_fanout`)
- `execution/strategy_engine/_engine.py:197-231` (`_evaluate_ctx`, runs every second)
- `execution/intraday_candle_loader.py:130-168` (`load_execution_frames`,
  `load_latest_execution_bar`) and `:68-95` (`assemble_execution_bars`)

**Symptom:** CPU and DB load grow linearly with universe size; the engine thread does far
more work per cycle than necessary. At a few hundred symbols this becomes the bottleneck.

**Root cause:** For each symbol, evaluation calls **both** providers:
`_get_latest_bar(symbol, tf)` then `_get_candles_df(symbol)`
(`_engine.py:419` and `:424`; also `:225` and `:228`). Internally:

- `load_latest_execution_bar` → `assemble_execution_bars(symbol, primary_tf)` →
  `db.fetch_bars(symbol, "1m", 30 days)` + `aggregate_timeframe` + `db.fetch_bars(symbol, tf)`.
- `load_execution_frames` → `assemble_execution_bars` **again** for `3m` **and** `15m`
  (so the primary TF is aggregated a **second** time), plus `load_stored_frames` does two
  more `fetch_bars` for `1d` and `1w` (400-day window).

So a single symbol evaluation does roughly **6+ DB queries and 3 full 1m→Nm aggregations**,
and the primary timeframe is aggregated twice. There is **no caching** between the
latest-bar call and the frames call, between ticks, or between strategies — `_fanout`
re-derives everything from scratch on each candle close, and `_evaluate_ctx` does the same
every second for every in-scope symbol.

**Evidence:** `assemble_execution_bars` recomputes from raw 1m on every call
(`intraday_candle_loader.py:90-95`); the engine calls it once via `_get_latest_bar` and
again (per TF) via `_get_candles_df` for the same symbol in the same pass.

**Fix direction:** Build the frames once per symbol per pass and derive the "latest bar"
from the already-built frame instead of a second `assemble_execution_bars`. Add a short-TTL
cache keyed by `(symbol, tf, last_bar_time)` so repeated ticks reuse the aggregation.
Consider incremental aggregation (append the new bar) instead of re-reading 30 days of 1m.

---

## H3 — One SQLite file written from 4 threads with no `busy_timeout`

**Category:** Broker / order-persistence reliability → High.
**Files:**
- `db/manager.py:61-78` (engine created with only `check_same_thread=False`)
- `gui/app_service.py:1591-1594` (trades + cycles share the candle-DB engine)
- `execution/live_bar_worker.py:329-341` (`_write_rows` sets WAL only on its own raw conn)

**Symptom:** Intermittent `sqlite3.OperationalError: database is locked`. Many call sites
swallow exceptions and return `[]` (e.g. the candle readers), so the visible effect is
**silently missing data, dropped order/cycle writes, or a chart that briefly shows nothing**,
rather than a clean error.

**Root cause:** All tables live in one SQLite file. Writers run concurrently from:
the **GUI thread** (`on_order_accepted` → `insert_trade`, see H5), the **engine loop**
(fills → `insert_trade`/`update_trade_fill`), the **trade-cycle loop** (cycle inserts and
the 500 ms tick flush → `update_live`), and **LiveBarWorker** (bar inserts). The SQLAlchemy
engine in `DatabaseManager` sets **no `busy_timeout`** and **no `journal_mode`**. SQLite
permits only one writer at a time; without `busy_timeout`, a second concurrent writer fails
**immediately** instead of waiting. (LiveBarWorker sets `PRAGMA journal_mode=WAL` on its own
connection, which helps reads, but does not set a busy timeout for the SQLAlchemy writers.)

**Evidence:** `db/manager.py:69-77` shows the only connect arg is `check_same_thread`.
Grep for `busy_timeout`/`journal_mode` across `src/` returns only the LiveBarWorker raw
connection and schema-introspection PRAGMAs — nothing on the shared engine.

**Fix direction:** On the shared engine, enable WAL and a busy timeout once at startup
(e.g. a `connect` event that runs `PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;`,
or pass `connect_args={"timeout": 5}` plus a WAL pragma). Consider serialising `trades`/
`trade_cycles` writes through a single writer. Separately, audit the `except Exception:
return []` blocks so genuine lock errors are at least logged, not hidden.

---

## H4 — `IBKRClient.unsubscribe_realtime_bars` is broken

**Category:** Broker logic → High.
**File:** `broker/client.py:188-190`

**Symptom:** Realtime-bar subscriptions are never actually cancelled; they leak on the IBKR
side. Over a session this consumes market-data lines and can exhaust the subscription cap.

**Root cause:** The method passes the **bound method object** to `cancelRealTimeBars`
instead of the live subscription handle:

```python
def unsubscribe_realtime_bars(self, symbol: str) -> None:
    # ib_insync tracks by contract; simplified: cancel all RDB subscriptions
    self._ib.cancelRealTimeBars(self._ib.reqRealTimeBars)   # <-- passes the method, not a bars handle
```

`subscribe_realtime_bars` (`client.py:182-186`) also never stores the handle returned by
`reqRealTimeBars`, so there is nothing to cancel even if the call were correct. This API is
used by `analysis/live_engine.py:83` and `:103` (see M3 — that caller may itself be legacy).

**Fix direction:** Track `{symbol: bars_handle}` on subscribe and pass the stored handle to
`cancelRealTimeBars`. If this code path is dead (M3), delete it instead. The current
`LiveBarWorker._apply_symbol_update` (`live_bar_worker.py:152-160`) already does this
correctly and can be the reference.

---

## H5 — Order-accept ledger write runs synchronously on the caller (GUI) thread

**Category:** Broker / Performance → High.
**Files:**
- `execution/broker_adapter.py:60-82` (`submit` → `on_order_accepted`)
- `execution/order_ingestion.py:133-152` (`on_order_accepted` → `ledger.insert_trade`)
- `gui/app_service.py:1965-1978` (`execute_signal`) and `:2230-2275` (`force_exit_position`)

**Symptom:** A manual order (executing a pending signal, manual/auto exit) does a SQLite
write on the GUI thread. On its own it is small, but combined with H3 the write can block
on the file lock and stall the UI, or raise "database is locked".

**Root cause:** `BrokerAdapter.submit` is called directly on the GUI thread for manual paths
(`execute_signal`, `force_exit_position` both call `self._submitter.submit(...)`).
`submit` calls `ingestion.on_order_accepted`, which calls `ledger.insert_trade` — a
synchronous DB write — before returning. (The *fill* resolution is correctly deferred to the
engine loop via `_schedule_on_engine_loop`, so that part is fine; only the accept-time insert
runs on the caller thread.)

**Evidence:** `broker_adapter.py:81` calls `on_order_accepted` inline; `order_ingestion.py:145`
calls `self._ledger.insert_trade(...)`. The callers at `app_service.py:1977` and `:2275` are
plain GUI methods.

**Fix direction:** Route manual submits through the engine loop the same way fills are
(`call_soon_threadsafe`), or move the accept-time insert onto a writer thread. Fixing H3
(busy timeout) reduces the worst case but does not remove the GUI-thread write.

---

# MEDIUM

## M1 — Tick-accumulator fields read/written outside the lock → double flush

**Category:** Concurrency.
**File:** `execution/trade_cycle/_service.py:541-563` (`_handle_tick`)

**Symptom:** Under bursty ticks for the same symbol, a cycle can be flushed/persisted twice
in quick succession, or a `flush_handle` timer can be scheduled while another flush is in
flight. Not corrupting (single-threaded asyncio loop), but wasteful and can double-emit
`CycleUpdated`.

**Root cause:** The accumulator snapshot is taken under `self._accs_lock`, but then
`acc.last_persist_at`, `acc.dirty`, and `acc.flush_handle` are read and the flush is
scheduled **outside** the lock (`_service.py:553-560`). Two `_handle_tick` tasks for the
same symbol interleave at the `await` points and can both pass the throttle gate.

**Fix direction:** Compute the throttle decision and set/clear `flush_handle` inside the
same locked section, or guard the accumulator with a per-cycle asyncio lock so only one
flush path is active per cycle.

---

## M2 — `swing_trader_data.py` (944 lines) is unused

**Category:** Dead code.
**File:** `src/us_swing/swing_trader_data.py`

**Symptom:** 944 lines of dead weight; misleads anyone navigating the tree.

**Evidence:** Grep for `swing_trader_data` / `SwingTraderData` across the whole repo matches
**only** the skeleton-cache index (`.skeleton_cache/skeleton.json`) — no import in `src/`,
`tests/`, or `__main__`.

**Fix direction:** Confirm once more (it is large, so double-check no dynamic import), then
delete. If it is kept as a reference, move it out of `src/`.

---

## M3 — `analysis/` live-engine stack appears superseded by `execution/`

**Category:** Dead / legacy code.
**Files:** `analysis/live_engine.py`, `analysis/db_persister.py`, `analysis/exit_manager.py`,
`analysis/strategy_engine.py`, exported from `analysis/__init__.py`.

**Symptom:** Two parallel "live engine" implementations. The running app uses the
`execution/` path (`StrategyEngine` in `execution/strategy_engine`, `LiveBarWorker`,
`LiveTickWorker`); the `analysis/` `LiveEngine`/`DatabasePersister`/`ExitManager` are only
referenced within `analysis/` itself and its `__init__`. `analysis/live_engine.py` is also
the only caller of the broken `unsubscribe_realtime_bars` (H4).

**Caution:** Confirm the screener/indicator code does not pull `StrategyConfig` or indicators
from `analysis/` before removing — `analysis/strategies/*` reference
`analysis.strategy_engine.StrategyConfig`. Quarantine and run the test suite first.

**Fix direction:** If unused by the live app, remove the `LiveEngine`/`DatabasePersister`
stack (and the dead `client.py` realtime API in H4 with it), or clearly mark `analysis/` as
"indicators only".

---

## M4 — Full position-table refresh on every tick; 5 GUI slots per tick

**Category:** Performance.
**Files:** `gui/app_service.py:2819-2825` (`_on_position_tick`), `:2531-2537` (tick fan-out)

**Symptom:** Each incoming tick triggers up to five GUI-thread slots, and
`_on_position_tick` emits `positions_updated` per matching tick, refreshing the whole
position view. At a high tick rate this is steady GUI churn that competes with H1.

**Root cause:** `tick_price` is connected to five handlers (`_record_market_price`,
`_on_watchlist_tick`, `_on_position_tick`, `_on_cycle_tick`, `pending_tick`) and the position
handler emits a broad `positions_updated` rather than an incremental cell update.

**Fix direction:** Coalesce ticks (e.g. a ~250 ms `QTimer` that emits once for the batch),
and update only the changed row/cell (`dataChanged` for the LTP/PnL columns) instead of a
full refresh.

---

## M5 — New `sqlite3.connect` on every candle read (no reuse)

**Category:** Performance.
**Files:** `gui/app_service.py` candle readers — `:2961, :2975, :3002, :3046, :3101, :3228, :3371`

**Symptom:** Repeated connection setup/teardown on hot read paths; small per call but it
compounds with H1 (called twice per live update) and adds file-lock churn against the live
writer (H3).

**Fix direction:** Reuse a single read connection (or the existing `DatabaseManager` engine
pool) for these reads instead of opening a fresh raw connection each time. Combine with the
off-thread move from H1.

---

## M6 — `IBKRClient` status/realtime callbacks fire on the ib loop thread with no marshaling

**Category:** Concurrency (latent).
**File:** `broker/client.py:285-306` (`_emit_status`, `_on_realtime_bar`), `:257-262` (`_on_disconnect`)

**Symptom:** Callbacks registered via `on_status_change` / `on_realtime_bar` are invoked
**synchronously on the ib_insync loop thread**. If any registered callback touches a Qt
widget directly, that is a cross-thread GUI mutation (crash/undefined behaviour). Today the
live GUI uses `LiveBarWorker`/`LiveTickWorker` (which emit Qt signals), so this is latent,
not active — but the seam offers no protection for future callers.

**Fix direction:** Document that these callbacks run off the GUI thread, and have GUI
consumers route them through a Qt signal (`QueuedConnection`) the way the worker classes do.
Also note `_on_disconnect` starts the reconnect loop via `asyncio.ensure_future`, which
assumes a running loop on that thread — fine today, but fragile if reused.

---

# Verified OK (not flagged — documented so they are not re-investigated)

These looked risky but are implemented correctly:

- **Cycle/monitoring events → GUI are thread-safe.** `active_cycles_panel.py:546-549` bridges
  the in-process bus to the model through a Qt signal with
  `Qt.ConnectionType.QueuedConnection`, so events published on background threads are
  marshaled to the GUI thread. The `_InProcessBus` itself runs handlers synchronously, but
  the handler here is just `signal.emit`, which is safe across threads.
- **SimBroker fill scheduling is correctly bridged.** It is constructed with
  `scheduler=self._schedule_on_engine_loop` (`app_service.py:1233`), which uses
  `loop.call_soon_threadsafe`, so fills land on the engine loop regardless of the submitting
  thread — the accept-then-fill ordering holds even for GUI-thread submits.
- **Order-ingestion context map is lock-guarded.** `order_ingestion.py` guards `_context`
  with a `threading.Lock` and registers context *before* placing the order, so a fill that
  races ahead of acceptance still resolves. `insert_trade` is idempotent (`INSERT OR IGNORE`).
- **`DatabaseManager` cross-thread use is intentional** (`check_same_thread=False`, one
  connection per call). The gap is only the missing `busy_timeout`/WAL (H3), not the
  threading model.

---

# Suggested fix order

1. **H1** — biggest user-visible win (kills the 1–2 s hang). Off-thread the chart read + cache.
2. **H3** — set WAL + `busy_timeout` on the shared engine; cheap, removes a class of silent failures.
3. **H2** — de-duplicate and cache strategy-evaluation aggregation; unblocks scaling the universe.
4. **H5** — route manual submits through the engine loop.
5. **H4** — fix or delete the broken unsubscribe.
6. **M1–M6** — clean up after the High items.

---

# GUI & SCREENER PASS (extension — 2026-06-13)

A second pass over the larger GUI files and the `screener/` tree, hunting specifically for
(a) blocking calls on the GUI thread and (b) full model-reset churn. Two Medium findings;
the rest came back clean (documented at the end so they are not re-checked).

## G1 — Position / Watchlist / Market-Watch tables full-reset on every tick (supersedes M4)

**Category:** Performance.
**Files:**
- `gui/position_table_model.py:55-59` (`refresh` → `beginResetModel`)
- `gui/dashboard_panel.py:819-820`, `:927-928` (watchlist models `refresh` → `beginResetModel`)
- driven per tick from `gui/app_service.py:2819-2825` (`_on_position_tick` → `positions_updated`)
  and `:2738-2757` (`_on_watchlist_tick` → `watchlist_updated` / `market_watch_updated`)
- consumed at `gui/dashboard_panel.py:1422` / `:1492-1494` (positions) and `:1051`, `:1203`
  (watchlist / market watch)

**Symptom:** During live ticking the Positions, Watchlist, and Market-Watch tables visibly
**flicker, lose row selection, and reset scroll position**, and the GUI does more work than
needed each tick. This adds to the GUI-thread load behind H1.

**Root cause:** Each tick emits a broad table-level signal that calls `model.refresh(items)`,
and every `refresh()` does a full `beginResetModel()` / `endResetModel()`. A full reset tears
down and rebuilds the entire view (every row, delegate, and any embedded row widgets), even
though only the LTP / change / PnL cells of one row actually changed. With many subscribed
symbols and a fast tick stream this is continuous churn on the GUI thread.

**Evidence / the correct pattern already exists here:** `active_cycles_model`
(`active_cycles_model.py:192-239`) does it right — `on_pending_tick` and `on_cycle_updated`
compare fields and emit `dataChanged` for **only the changed cells** of the affected row, no
reset. The position and watchlist models should mirror that.

**Fix direction:** Replace the per-tick `refresh()`/full-reset with a targeted per-row,
per-column `dataChanged` update (and use `beginInsertRows`/`beginRemoveRows` only when the row
set actually changes). Optionally coalesce ticks behind a ~250 ms timer (the M4 point) so even
the cell updates are batched. This removes the flicker and the selection/scroll loss.

## G2 — Synchronous candle DB reads on the GUI thread in Settings / Screener / Chart panels

**Category:** Performance (same class as H1, lighter payloads).
**Files:**
- `gui/settings_panel.py:777` — `get_candle_symbol_coverage()` (a `GROUP BY` over `price_1d`)
  runs on the GUI thread when the coverage view opens.
- `gui/screener_panel.py:569` — `get_candles_for_symbol(symbol, tf, 500)` runs on the GUI
  thread when a scan result is selected (mini-chart preview).
- `gui/chart_panel.py:716` — `get_candles_for_symbol(...)` on symbol change (already noted under H1).

**Symptom:** A short stall when opening the Settings coverage view or selecting a screener
result, proportional to DB size. Much smaller than H1 (these are daily reads, not the 10k-row
intraday aggregation), but the same anti-pattern and the same file-lock contention with the
live writer (H3).

**Fix direction:** Move these reads onto a worker thread (the screener already has a
`QThread` worker it could reuse) or cache results, and reuse a shared read connection (M5).

## Verified clean in this pass (do not re-investigate)

- **Screener scan is correctly off-thread.** `screener_panel._PresetRunWorker`
  (`screener_panel.py:235-305`) and `_ModelValidateWorker` (`:347`) are `QThread`s; the heavy
  `get_candle_symbols` / `get_candles_bulk` / preset execution run inside `run()`, not on the
  GUI thread.
- **Screener network + retry is safe.** `screener/screeners/cloud_ai.py:417` uses `time.sleep`
  for 429 back-off, but only inside a `ThreadPoolExecutor` (`executor.py:215` confirms
  screeners never run on the asyncio loop). No GUI-thread or event-loop blocking.
- **`screener/storage.py`, `manager.py`, `scheduler.py`** only do small JSON `read_text`
  loads — negligible, and not on a per-tick path.
- **`main_window.py` startup is clean** — no synchronous DB / network / `connectAsync` calls
  on the GUI thread during construction.
- **`active_cycles_model`** is the reference implementation for incremental table updates.
- **Modal dialogs** (`settings_panel.py:235/243/465/475`, etc.) use `.exec()`, which is
  intentional blocking for a modal — not a defect.

**Still not read line-by-line** (low likelihood of High/Medium perf or broker issues):
`strategy_builder_dialog.py` (1271), `scheduler_dialog.py` (831), `ai_transcript_panel.py`
(521), `theme.py` (1136, pure QSS/colour), `position_monitor_panel.py`, `log_viewer_panel.py`,
the GUI `*_store.py` helpers, and the deeper internals of `screener/screeners/*` beyond the
blocking-call scan above.

---

# FULL-TREE SWEEP (extension — 2026-06-14)

A final pass to cover the remaining packages (`data/`, `core/monitoring_session/`,
`monitoring/`, `universe/`, `user/`, `config/`, `analysis/`, the rest of `screener/`, and the
remaining GUI dialogs). Result: the business/infrastructure libraries are **clean and
well-written**. One low-end Medium nit (S1) and two things worth recording so they are not
re-investigated.

## S1 — Indicator math is duplicated, behind a stale comment

**Category:** Dead / duplicate code (quality).
**Files:** `analysis/indicators.py` (`ema`, `atr`, `rsi` — proper, pure, on `OHLCVBar`)
vs `screener/screeners/indicator.py:30-73` (inline `_rsi`, `_atr_pct`, `_volume_ratio`).

**Symptom:** Two implementations of RSI/ATR that can drift apart. The screener copy carries the
comment *"analysis/indicators.py not yet implemented"* (`indicator.py:30`) — but that module
**is** implemented, so the comment is wrong and the duplication is unnecessary. (Note the two
RSIs even differ slightly in their insufficient-data handling: `analysis` returns `NaN`, the
screener returns `50.0`.)

**Fix direction:** Point the screener at `analysis/indicators.py` (adapting the bar type) or,
if that crosses a tool boundary, move the shared math into `core/` and delete one copy. Remove
the stale comment. Confirm the chosen RSI semantics on purpose rather than by accident.

## Confirmed clean — do not re-investigate

- **Price tables are properly indexed.** `db/schema.py:34-158` — every `price_*` table has a
  `(symbol, datetime)` primary key **and** a matching compound index. So the heavy reads in
  H1/H2 are index-supported; the cost is row volume + Python aggregation + threading, **not**
  a missing index. Do not waste time adding indexes.
- **`data/engine.py`** (bootstrap, incremental update, `aggregate_timeframe`) — clean async,
  bounded concurrency, pure aggregation. No issues.
- **`MonitoringRepository`** (`core/monitoring_session/_repository.py`) — clean SQLAlchemy with
  a single atomic eviction transaction. It is one more writer to the shared DB file (already
  accounted for in H3); no separate defect.
- **`universe/store.py`** — clean; network fetch (Wikipedia + yfinance thread pool) runs from a
  worker, writes the CSV atomically (tmp + rename).
- **`monitoring/connectivity.py`** — probes on a worker `QThread`, emits only on state flip.
  (Minor: it spawns a fresh `QThread` every 15 s rather than reusing one — Low, ignored.)
- **`screener/executor.py`** — clean 3-stage pipeline; Stage 2 runs screeners in a
  `ThreadPoolExecutor`; sensible LLM fallback. Off the GUI thread (driven by the panel worker).
- **`scheduler_dialog.py` `time.sleep()` calls are safe** — they run inside `_FillWorker.run()`
  (a `QThread`), not on the GUI thread. (That worker auto-types IBKR credentials into TWS via
  Windows SendInput and is marked TEMP — a security/quality topic outside this audit's
  perf/broker scope, noted only for awareness.)
- **`strategy_builder_dialog.py`** — only modal `.exec()`; no blocking DB/network on the GUI
  thread.

---

# Coverage of this audit (be honest about what was read)

This was a **targeted** review driven by the severity policy (High = tool performance +
broker logic), **not** a line-by-line read of every file. ~130 source files exist.

**Read in depth (High-scope hot/broker paths):**
`broker/` (`client`, `ibkr`, `broker`, `sim`, `pacing`); `execution/` core
(`strategy_engine/_engine.py`, `_router.py`, `order_ingestion.py`, `broker_adapter.py`,
`broker_factory.py`, `risk_manager.py`, `pending_signal_store.py`, `event_bus.py`,
`live_bar_worker.py`, `live_tick_worker.py`, `intraday_candle_loader.py`,
`trade_cycle/_service.py`, `trade_cycle/_repository.py` head); `db/manager.py`;
`core/monitoring_session/_events.py`; the hot sections of `gui/app_service.py` and the
chart panels.

**Result on the broker/execution core:** clean. The router, risk gate, broker factory,
SimBroker scheduling, and pending-signal store are correctly written and correctly locked
(engine-loop-confined). The High findings above are at the *boundaries* — DB engine config
(H3), GUI-thread reads (H1, H5), per-tick re-aggregation (H2), and one stale broker API (H4)
— not in the trading logic itself.

**Reviewed in the GUI & Screener pass** (targeted for blocking calls + model-reset churn —
see the extension section, findings G1/G2): `gui/dashboard_panel.py`, `gui/settings_panel.py`,
`gui/main_window.py`, `gui/position_table_model.py`, `gui/active_cycles_model.py`,
`gui/execution_panel.py`, `gui/chart_panel.py`, `gui/screener_panel.py`,
`gui/active_cycles_panel.py`; and `screener/` (`executor.py`, `manager.py`, `storage.py`,
`scheduler.py`, `screeners/cloud_ai.py`). Note: these were scanned for the two target
patterns, not audited line-by-line for every concern.

**Reviewed in the full-tree sweep (2026-06-14):** `db/schema.py`, `data/engine.py`,
`core/monitoring_session/_repository.py`, `monitoring/connectivity.py`, `universe/store.py`,
`analysis/indicators.py`, `screener/screeners/indicator.py`, `screener/executor.py`,
`gui/strategy_builder_dialog.py`, `gui/scheduler_dialog.py`, plus a tree-wide pattern scan for
blocking calls / broad excepts / `while True` loops across all of `src/`.

**Remaining unread — trivial, non-logic files only** (data containers, type stubs, and pure
layout/QSS — very low value to audit for perf/broker): `*/MODULE_MAP.json` (generated),
the `_dto.py` / `_enums.py` / `_protocols.py` / `_schema.py` definition modules across
`execution/` and `core/`, `data/models.py` (dataclasses), `gui/theme.py` (QSS/colours),
the GUI `*_store.py` JSON helpers, `gui/_types.py`, `gui/log_bridge.py`,
`gui/position_monitor_panel.py`, `gui/log_viewer_panel.py`, `gui/ai_transcript_panel.py`,
`data/providers/dummy_provider.py`, `scripts/_smoke_lifecycle.py`, and the small
`screener/screeners/*` plugins (`ml.py`, `llm_local.py`, `mcp.py`, `price_action.py`).
None of these sit on the live broker/perf hot path; a quick targeted scan of each turned up
nothing in scope.

**Net:** every logic-bearing module across all six tools has now been read or pattern-scanned.
The conclusion held throughout: the business/infrastructure libraries are clean; all High
findings are at the GUI↔engine boundary and in DB concurrency, not in the trading logic.

*Analysis only — no source files were modified.*
