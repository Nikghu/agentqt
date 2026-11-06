# Design Document — Desk Harness (DSK)

**Document ID:** DD-DSK
**Version:** 0.2.0
**Status:** Draft
**Last Updated:** 2026-11-05
**Project:** US Swing Trading System

> v0.3.0: DD-DSK-002.001.D01 added — lean harness for P5a.
> v0.2.0: DD-DSK-001.001.D01 added — desk process shell (P0a).
> v0.1.0: Architecture review (pre-SRD). Records the locked decisions, package layout, `desk.db` contract and phase plan for DSK + MKT. DD items with IDs are added per phase once their SRDs exist.

---

## 0. Architecture Review (2026-11-05)

### 0.1 Locked decisions

| # | Decision | Source |
|---|---|---|
| 1 | LangGraph is the base. Our own harness sits on top: registry, task cards, event router, market clock, LLM gateway, recorder, budget guard, graph builder. | User, 2026-11-05 |
| 2 | Agents are plain typed Python functions, so LangGraph stays swappable. | Review |
| 3 | The desk runs as a separate process started by its own Windows task. The app can stop it. The last state is saved and can be resumed. | User, 2026-11-05 |
| 4 | The GUI only reads `desk.db`. It writes to only one table, `commands`. | User, 2026-11-05 |
| 5 | Two packages: `desk` (general harness, DSK) and `market` (market analytics, MKT). | User, Option A |
| 6 | The front-end design is approved before backend work (Market Floor + AI Desk, round-2 Option 1). | User, 2026-11-05 |
| 7 | Agents sleep by default and wake on events or timers. Code watchers are always on (MoE-style router). | User, 2026-11-05 |
| 8 | Every agent step is recorded in an append-only log. | User, 2026-11-05 |
| 9 | LLM sources: OpenRouter (main), Claude Code CLI (rare, subprocess with no window), HuggingFace (special models as tools), TypeSafe Jev (typed decisions, from P5a in shadow). | User, 2026-11-05 |
| 10 | Master User talks only to HELM. Hiring a new employee or adding a process needs Master approval. | User, 2026-11-05 |
| 11 | Job descriptions = `soul.md` + `job.yaml`. First versions are written by Claude Code; later HELM drafts and the Master approves. | User, 2026-11-05 |
| 12 | P1–P4 use no AI. New dependencies (`langgraph`, `langgraph-checkpoint-sqlite`) arrive only at P5a; `huggingface_hub`, `feedparser` at P5c. | Review |

### 0.2 Package layout and boundaries

| Path | Tool | Holds |
|---|---|---|
| `src/us_swing/desk/` | DSK | Process shell, state machine, command reader, scheduler, harness (from P5a). No market logic. |
| `src/us_swing/market/` | MKT | Funnel steps (regime, breadth, sectors, RS, flow, setups, score), employees (`market/employees/<name>/soul.md`, `job.yaml`). |
| `src/us_swing/core/desk_contract.py` | shared | Frozen, versioned DTOs and `Protocol`s for `desk.db` rows, plus a read-only repository the GUI uses. |
| `src/us_swing/gui/` | GUI | Market Floor and AI Desk workspaces. Reads through `core/desk_contract.py` only. |

Rules: `market` must not import `desk`, and `desk` must not import `market`. The desk finds MKT steps and employees through a registry that names Python entry points, using Protocols from `core/`. `gui` never imports `desk` or `market`. This follows the CQRS-lite pattern in `core/backtest_bridge.py`: one writer (the desk process), many readers.

### 0.3 `desk.db` contract

SQLite in WAL mode, kept in the user data folder next to the other app databases. The desk process is the only writer, except for `commands`. Every row DTO has a `schema_version`.

| Table | Writer | Reader | Holds | Phase |
|---|---|---|---|---|
| `desk_state` | desk | GUI | Current state (one of 7), heartbeat time, last run, saved resume point | P0a |
| `commands` | GUI | desk | start / pause / resume / stop requests, with a status the desk updates | P0a |
| `runs` | desk | GUI | One row per scheduled or event run: start, end, result | P0a |
| `regime_snapshot` | desk | GUI | Daily regime, volatility state, fear reading | P1 |
| `breadth_daily` | desk | GUI | Daily breadth figures | P1 |
| `sector_state` | desk | GUI | Sector and group RS, rotation quadrant | P2 |
| `ideas`, `idea_reasons` | desk | GUI, EXE (P7) | Ranked stocks, score parts, trigger prices, reasons | P3 |
| `data_products`, `product_snapshots` | desk | GUI | Catalog of every desk output, so Floor panels can show any of them without a GUI change | P0b / P1 |
| `briefs` | desk | GUI | HELM and expert briefs for the AI feed | P5b |
| `employees`, `seats` | desk | GUI | Roster, job description versions, open seats | P5a |
| `tasks`, `activity` | desk | GUI | Task cards and the append-only step log | P5a |
| `approvals`, `messages` | desk + GUI | both | Master approvals and HELM chat (GUI writes only new rows) | P5b |
| `budget` | desk | GUI | AI spend per day, month, employee | P5a |
| `canvas_pages` | desk | GUI | AI Canvas page versions | P5d |

### 0.4 Desk states

| State | Meaning |
|---|---|
| Running | A run is in progress |
| Sleeping | Process alive, waiting for the next timer or event |
| Paused | Process alive, timers held by the user |
| Stopping | Finishing the current step before saving |
| Stopped | Saved and exited by request; can be resumed |
| Off | No process, and no saved state |
| Error | Heartbeat missing or the last run failed |

### 0.5 Time

The desk works in NY time (`zoneinfo` "America/New_York"). Windows tasks are set in IST (memory: US DST vs IST). On 2026-11-05 EST applies, so IST = ET + 10:30. The evening run starts about 16:25 ET (02:55 IST).

### 0.6 Phase plan

| Step | Scope | Tool / FO | Gate |
|---|---|---|---|
| P0a | Desk shell: process, Windows task, states, commands, heartbeat, `desk.db` base tables | DSK / FO-DSK-001 | Start, pause, stop and resume work from a CLI with the app closed |
| P0b | GUI frames: Market Floor (5 tabs, AI feed column, adjustable panel grid, catalog, saved layouts) and AI Desk (section list, Command home) on sample data | GUI / new FO-GUI-034 | User approves the frames in the real window |
| P1 | Regime, breadth, fear | MKT / FO-MKT-001 | Numbers match a hand check on 3 dates |
| P2 | Sectors, groups, stock RS | MKT / FO-MKT-002 | Quadrants match a known reference week |
| P3 | Money flow, setups, score, ideas, triggers | MKT / FO-MKT-003 | Daily idea list appears on the Floor |
| P4 | Proof on past data | MKT / FO-MKT-004 | Top score band beats the S&P 500 average on forward returns |
| P5a | Harness + ATLAS | DSK / FO-DSK-002–005, MKT / FO-MKT-005 | One full recorded ATLAS run within budget |
| P5b | TIDE, PIVOT, SENTINEL, HELM, AI feed | MKT / FO-MKT-005 | HELM brief on the Floor each evening |
| P5c | SCOUT news | MKT / FO-MKT-006 | News tags on ideas |
| P5d | CANVAS pages and Studio | MKT / FO-MKT-007 | A sealed page renders with no network |
| P6 | Hiring pipeline, LEDGER, cost views | DSK / FO-DSK-006 | One shadow hire approved end to end |
| P7 | Link to Execution | MKT / FO-MKT-008 | Approved idea reaches EXE |

### 0.7 Questions and answers

| # | Question | Answer (user, 2026-11-05) |
|---|---|---|
| Q1 | Tool lists in `CLAUDE.md`, `artifact-conventions.md`, `workspace.md` and `process.md` §14.1 lack BKT, DSK and MKT (user-maintained files). | Open — user to update |
| Q2 | Which model is "Jev"? | Jev by TypeSafe AI: a typed decision model (Choice / Score with probability and confidence). Reached through Vercel AI Gateway or Cloudflare Workers AI. Add it at P5a as a 4th gateway source for junior and champion decisions, in shadow mode against a cheap OpenRouter model for 2 weeks; LEDGER compares accuracy and cost before any switch. |
| Q3 | Seat caps? | 3 experts / 5 champions / 30 juniors. Can be raised later from AI Desk settings. |
| Q4 | Monthly AI budget? | USD 10 per month while testing, cheap models only. Raise after the desk is set up. |
| Q5 | Does HELM trade by itself? | No. HELM proposes; the Master User approves or rejects every trade. |

---

## DD-DSK-001.001.D01 — Desk Process Shell (P0a)

**Traces:** SRD-DSK-001.001–.020

**Files.** Root `~/.usswing/desk/` (injectable): `desk.db`, `desk.lock`.

**Schema** (`schema_version` = 1, kept in `PRAGMA user_version`):

```
desk_state(id INTEGER PRIMARY KEY CHECK (id = 1), state TEXT, heartbeat_at TEXT,
           pid INTEGER, message TEXT, resume_point TEXT /* JSON */, updated_at TEXT)
commands(id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, created_at TEXT,
         status TEXT /* pending|done|rejected */, done_at TEXT, note TEXT)
runs(id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT /* evening|manual */, started_at TEXT,
     ended_at TEXT, result TEXT /* running|ok|failed|interrupted */, note TEXT)
```

Every connection runs `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000`. The desk opens one
connection for its life; the reader opens a short read-only connection (`mode=ro` URI) per call.

**Reader status rule** (`core/desk_contract.read_status`):

```
no file or no row                          -> Off
state in {Running, Sleeping, Paused, Stopping, Error}
    and now - heartbeat_at > 60 s          -> Error, message "not responding"
otherwise                                  -> stored state
```

**Command table** (state → allowed commands; anything else is `rejected` with the reason):

| State | pause | resume | stop | run_now |
|---|---|---|---|---|
| Sleeping | → Paused | reject | → Stopping | start manual run |
| Error | → Paused | reject | → Stopping | start manual run |
| Paused | reject | → Sleeping | → Stopping | reject |
| Running | → Paused after the run | reject | → Stopping | reject |

**Main loop** (`desk/process.DeskProcess.run`, clock and sleep injected):

```
take lock (msvcrt.locking on desk.lock) or log "[Desk] Already running" and exit 0
open store; if saved state is Stopped and not resume: exit 0          # SRD .013
set Sleeping, pid; mark open runs interrupted and queue one rerun      # SRD .014
sync evening task time (best effort)                                   # SRD .019
loop every 2 s:
    write heartbeat when 10 s passed                                   # SRD .009
    apply pending commands in id order                                 # SRD .010-.012
    if Stopping: save resume point {"last_run_id", "rerun"} , set Stopped, break
    if Paused: continue
    if rerun queued, run_now asked, or evening_due(now, last evening run): do_run()
release lock
```

`do_run` sets Running, inserts a `runs` row, calls each `DeskStep` (a `Protocol` in
`core/desk_contract.py`: `name: str`, `__call__(ctx) -> None`) in order, checking for a stop command
between steps. Step error → run `failed`, state Error with message `"<step> failed: <reason>"`.
All ok → run `ok`, state Sleeping. P0a registers no steps; MKT adds steps from P1.

**Evening due** (`desk/clock.evening_due`): same shape as SRD-BKT-001.009 — find today's 16:25 ET
on a weekday; due when it has passed and the last evening run started before it. Missed days are
not replayed, only today's.

**Windows tasks** (`desk/task.py`):

| Task | Trigger | Command |
|---|---|---|
| `USSwing_Desk` | `/sc onlogon` | `<exe> desk` |
| `USSwing_Desk_Evening` | `/sc weekly /d <days> /st HH:MM` — 16:20 ET Mon–Fri turned into local time and local days today (IST: TUE–SAT 02:50 in EST) | `<exe> desk` |

`<exe>` is `sys.executable` when frozen, else `pythonw.exe us_swing/run_gui.py` (adds `src/` to the path; the package is not installed in dev). `start` launches the same
command plus `--resume` with `DETACHED_PROCESS | CREATE_NO_WINDOW`. The sync step reads the task
time and days with `/query /xml` and re-creates the evening task when either differs.

**After code review (2026-11-05).**

- A side thread with its own connection writes the heartbeat every 10 s while steps run, so a long step never shows "not responding".
- On start, every pending command is rejected with "desk was not running", so old commands never replay.
- Any crash in the loop is logged, saved as Error "crashed: <reason>", and the process exits with code 1.
- A pause taken during a run that then fails is honoured: the desk goes to Paused and keeps the failure message.
- A pause clears a run-now from the same batch.
- The task time sync (`daily_check`) runs at start and after each evening run, so a clock change is fixed within one day.

## DD-DSK-002.001.D01 — Lean Harness: Registry, Wake Rule, Gateway, Budget, Recorder (P5a)

**Traces:** SRD-DSK-002.001–.005, SRD-DSK-003.001–.003, SRD-DSK-004.001–.005, SRD-DSK-005.001–.004

**Boundaries.** `desk` never imports `market`. Shared types live in `core/desk_agents.py`, and the employee list `EMPLOYEE_PATHS = ("us_swing.market.atlas:Atlas",)` lives in `core/desk_steps.py` (loaded by import path, like the steps). Agents are plain typed Python; LangGraph comes in P5b.

**Shared types** (`core/desk_agents.py`):

```
class FeedItem(frozen):  author, kind ("info" | "idea" | "approval"), text, data_day
class AgentContext(Protocol):
    home: Path
    def ask(self, facts: str, schema: type[T]) -> T | None      # gateway; None = no valid answer
class Employee(Protocol):
    name: str            # "ATLAS"
    folder: Path         # holds soul.md and job.yaml
    def facts(self, home: Path) -> Facts                       # Facts(text, data_day, fresh, why_stale)
    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]
```

**Job file** (`desk/registry.py`, pydantic, `extra="forbid"`):

```
name: ATLAS                 title: Market regime expert       version: 1
trigger: after_run          output: AtlasView (name only, for people)
models: {primary: {source: openrouter, model: ...}, backup: {source: claude, model: ...}}
calls_per_day: 3            monthly_cost_usd: 3.0             kpis: [list of strings]
```

`load_employee(emp)` reads both files, validates `job.yaml`, and returns `Hire(emp, spec, soul, hash)`. `hash` is the sha256 of both files. An error gives `None` plus `[AI Desk] <name> job file is not valid: <reason>`. `employees(name PK, title, version, hash, loaded_at)`: upsert per run; a new hash with the same version logs a warning.

**Wake rule** (`desk/employees_step.py`, desk step "AI employees", appended to `STEP_PATHS` after Ideas):

```
for emp in load_employees(EMPLOYEE_PATHS):
    hire = load_employee(emp)            -> skip when None
    if hire.spec.trigger != "after_run": continue
    facts = emp.facts(home)
    if not facts.fresh: log skip (facts.why_stale); continue
    if recorder.done_today(name, facts.data_day): continue   # a valid try exists for that day
    items = emp.act(Context(home, gateway(hire, run_id, facts.data_day)), facts)
    recorder.add_briefs(items)
```

Any exception inside one employee is logged with `log.exception` and the next employee runs.

**Gateway** (`desk/gateway.py`). `ask(facts, schema)`:

```
system  = soul.md + "\n\nAnswer with JSON only, matching this schema:\n" + schema.model_json_schema()
for model in (primary, backup):
    for attempt in (1, 2):
        if budget.refuse(hire, model): record refusal; return None
        text, usage = call(model.source, model.model, system, user)      # 90 s limit
        try: return schema.model_validate_json(first_json_object(text))   # record valid
        except: record invalid with error; user += "\n\nYour last answer was not valid: <error>"
return None
```

Sources: OpenRouter is called with `httpx` and `"usage": {"include": true}`, so the reply carries `usage.prompt_tokens`, `completion_tokens` and `cost`. Claude Code CLI uses the same headless command as the AI notes client (`core/notifications/_ai_client._run_with_timeout`); its JSON gives `usage` (input, cache and output tokens); `total_cost_usd` is ignored. A call error is recorded as an invalid try with the error text.

**Budget** (`desk/budget.py`), from `activity` only:

```
spent_month   = SUM(cost_usd) this calendar month (NY time)
refuse when   spent_month >= settings.monthly_budget_usd
          or  employee spent_month >= spec.monthly_cost_usd
          or  employee tries today >= spec.calls_per_day * 2      (2 tries per call)
          or  source == claude and claude tokens today >= settings.claude_tokens_per_day
```

Claude CLI runs on the user's subscription (user, 2026-11-06): its `cost_usd` is always recorded as 0 and only its tokens count, against the daily token cap. Only OpenRouter (API) calls carry cost.

**Desk AI settings** (`core/desk_ai_settings.py`, shared with the GUI). `desk_ai.json` in the desk folder holds `openrouter_on, openrouter_model, claude_on, claude_model, monthly_budget_usd (10.0), claude_tokens_per_day (200000)`. The key is stored with `keyring` (service `USSwing-Desk-OpenRouter`). `job.yaml` picks the source and model per employee; the settings can switch a source off, and an off source is skipped (an employee with both sources off makes no call). A missing file means the defaults (both off), so no AI runs until the user sets it up.

**Recorder** (`desk/recorder.py`):

```
activity(id INTEGER PK, run_id, employee, version, data_day, started, source, model, attempt,
         prompt, answer, valid INTEGER, error, tokens_in, tokens_out, cost_usd, seconds)
briefs(id INTEGER PK, created, data_day, author, kind, text)
CREATE TRIGGER activity_no_update BEFORE UPDATE ON activity BEGIN SELECT RAISE(ABORT, 'append-only'); END
(same for DELETE, and for briefs)
```

`done_today(name, day)` is true when a valid row exists for that employee and day. Log lines: `[AI Desk] ATLAS answered with <model> in 4.2 s, cost USD 0.0012`, `[AI Desk] ATLAS skipped: data for 2026-11-04 already done`, `[AI Desk] ATLAS refused: monthly budget USD 10.00 used up`.

**Limits in P5a.** One trigger only (`after_run`). No priorities, deadlines, expiry or market clock (P5b). No replay (P5b). No HuggingFace or Jev source. Job files are edited by hand (P6 adds editing, rollback and approval).

**After code review and the real run.** A call allows 4 tries (primary twice, backup twice), so `calls_per_day` counts 4 tries per call. Cost checks apply only to OpenRouter, so a used-up API budget never blocks the free Claude CLI. An OpenRouter reply without `usage.cost` fails that try, so spend is never unchecked. A day counts as done only once a brief is posted (`briefs`), so a crash after a valid answer is tried again. Model names starting with `-` are refused. Feed text is shown as plain text. AI Desk gets the desk folder from its poller; Cost & budget is rebuilt each time it opens. The keychain is not read while the window is built.

