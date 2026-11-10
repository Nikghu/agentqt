# Design Document — Desk Harness (DSK)

**Document ID:** DD-DSK
**Version:** 0.4.0
**Status:** Draft
**Last Updated:** 2026-11-06
**Project:** US Swing Trading System

> v0.7.0: DD-DSK-001.015.D02 added — morning run, desk lives with the app (Autonomous desk step A, 2026-11-10); §0.1 #3 and §0.5 updated.
> v0.6.0: DD-DSK-008.001.D01 added — employee.md file, migration, versions, draft test.
> v0.5.0: DD-DSK-006.001.D01 added — hiring pipeline, shadow and weekly report (P6).
> v0.4.0: DD-DSK-003.004.D01 added — events, market clock, LangGraph run order and replay (P5b).
> v0.3.1: P5a section rewritten without employee names: skills by function, employees as data in the desk folder, generic levels (user, 2026-11-06).
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
| 3 | The desk runs as a separate process. Since 2026-11-10 the app starts it on open and stops it on close (no desk Windows task). The last state is saved and can be resumed. | User, 2026-11-05; changed 2026-11-10 |
| 4 | The GUI only reads `desk.db`. It writes to only one table, `commands`. | User, 2026-11-05 |
| 5 | Two packages: `desk` (general harness, DSK) and `market` (market analytics, MKT). | User, Option A |
| 6 | The front-end design is approved before backend work (Market Floor + AI Desk, round-2 Option 1). | User, 2026-11-05 |
| 7 | Agents sleep by default and wake on events or timers. Code watchers are always on (MoE-style router). | User, 2026-11-05 |
| 8 | Every agent step is recorded in an append-only log. | User, 2026-11-05 |
| 9 | LLM sources: OpenRouter (main), Claude Code CLI (rare, subprocess with no window), HuggingFace (special models as tools), TypeSafe Jev (typed decisions, from P5a in shadow). | User, 2026-11-05 |
| 10 | Master User talks only to the lead. Hiring a new employee or adding a process needs Master approval. | User, 2026-11-05 |
| 11 | Job descriptions = `soul.md` + `job.yaml`. First versions are written by Claude Code; later the lead drafts and the Master approves. | User, 2026-11-05 |
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
| `briefs` | desk | GUI | Lead and expert briefs for the AI feed | P5a |
| `employees`, `seats` | desk | GUI | Roster, job description versions, open seats | P5a |
| `tasks`, `activity` | desk | GUI | Task cards and the append-only step log | P5a |
| `approvals`, `messages` | desk + GUI | both | Master approvals and lead chat (GUI writes only new rows) | P5b |
| `budget` | desk | GUI | AI spend per day, month, employee | P5a |
| `canvas_pages` | desk | GUI | Report page versions (append-only) | P5d |

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

The desk works in NY time (`zoneinfo` "America/New_York"). Since 2026-11-10 the daily run is the morning run (from 04:00 ET pre-market, see DD-DSK-001.015.D02); the 16:25 ET evening run is gone. The app's start tasks are set in the PC's local time, 60 minutes before the 09:30 ET open.

### 0.6 Phase plan

| Step | Scope | Tool / FO | Gate |
|---|---|---|---|
| P0a | Desk shell: process, Windows task, states, commands, heartbeat, `desk.db` base tables | DSK / FO-DSK-001 | Start, pause, stop and resume work from a CLI with the app closed |
| P0b | GUI frames: Market Floor (5 tabs, AI feed column, adjustable panel grid, catalog, saved layouts) and AI Desk (section list, Command home) on sample data | GUI / new FO-GUI-034 | User approves the frames in the real window |
| P1 | Regime, breadth, fear | MKT / FO-MKT-001 | Numbers match a hand check on 3 dates |
| P2 | Sectors, groups, stock RS | MKT / FO-MKT-002 | Quadrants match a known reference week |
| P3 | Money flow, setups, score, ideas, triggers | MKT / FO-MKT-003 | Daily idea list appears on the Floor |
| P4 | Proof on past data | MKT / FO-MKT-004 | Top score band beats the S&P 500 average on forward returns |
| P5a | Harness + first expert (regime view skill) | DSK / FO-DSK-002–005, MKT / FO-MKT-005 | One full recorded regime view run within budget |
| P5b | Sector/flow and setup experts, risk manager, lead | MKT / FO-MKT-005 | Lead brief on the Floor each evening |
| P5c | News review and economic calendar | MKT / FO-MKT-006 | News tags on ideas |
| P5d | AI report pages and the AI Desk Pages section | MKT / FO-MKT-007 | A sealed page renders with no network |
| P6 | Hiring pipeline, LEDGER, cost views | DSK / FO-DSK-006 | One shadow hire approved end to end |
| P7 | Link to Execution | MKT / FO-MKT-008 | Approved idea reaches EXE |
| P8 | Pick results: paper and real results, breakdowns, Results section, weekly report | MKT / FO-MKT-009 | Every lead pick has a paper result; a closed AI Desk trade has a real result |
| P9 | Lead chat: Master questions in Command answered by a lead-level chat employee | MKT / FO-MKT-010 | A question in Command gets a recorded answer |
| P10 | Ask the desk for new data: request in the Floor catalog, recipe from a fixed menu, preview and approval | MKT / FO-MKT-011 | An approved asked panel shows the latest day's rows |

### 0.7 Questions and answers

| # | Question | Answer (user, 2026-11-05) |
|---|---|---|
| Q1 | Tool lists in `CLAUDE.md`, `artifact-conventions.md`, `workspace.md` and `process.md` §14.1 lack BKT, DSK and MKT (user-maintained files). | Open — user to update |
| Q2 | Which model is "Jev"? | Jev by TypeSafe AI: a typed decision model (Choice / Score with probability and confidence). Reached through Vercel AI Gateway or Cloudflare Workers AI. Add it at P5a as a 4th gateway source for junior and champion decisions, in shadow mode against a cheap OpenRouter model for 2 weeks; LEDGER compares accuracy and cost before any switch. |
| Q3 | Seat caps? | 3 experts / 5 champions / 30 juniors. Can be raised later from AI Desk settings. |
| Q4 | Monthly AI budget? | USD 10 per month while testing, cheap models only. Raise after the desk is set up. |
| Q5 | Does the lead trade by itself? | No. The lead proposes; the Master User approves or rejects every trade. |

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

**Boundaries.** `desk` never imports `market`. Shared types live in `core/desk_agents.py`. Code knows **skills** only, named by function: `SKILL_PATHS = {"regime_view": "us_swing.market.regime_view:RegimeViewSkill"}` and `DEFAULT_EMPLOYEE_PACKAGES = ("us_swing.market",)` live in `core/desk_steps.py` (loaded by import path, like the steps). Employee names, titles and reporting lines are data the Master user can change; docs and code use skills (by function) and generic levels (lead, expert, champion, junior) only (user, 2026-11-06). Agents are plain typed Python; LangGraph comes in P5b.

**Shared types** (`core/desk_agents.py`):

```
class FeedItem(frozen):  kind ("info" | "idea" | "approval"), text, data_day   # the desk adds id + name
class AgentContext(Protocol):
    home: Path
    def ask(self, facts: str, schema: type[T]) -> T | None      # gateway; None = no valid answer
class Skill(Protocol):
    key: str             # "regime_view" — what the work is, never who does it
    def facts(self, home: Path) -> Facts                       # Facts(text, data_day, fresh, why_stale)
    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]
```

**Job file** (`desk/registry.py`, pydantic, `extra="forbid"`):

```
id: emp-001                 # stable key in every record; never shown, never changed
name: Expert 1              title: Expert          level: expert   (lead|expert|champion|junior)
reports_to: <id> | null     skill: regime_view     version: 2
trigger: after_run
models: {primary: {source: openrouter, model: ...}, backup: {source: claude, model: ...}}
calls_per_day: 3            monthly_cost_usd: 3.0             kpis: [list of strings]
```

**Employee files** live in `<desk>/employees/<id>/` (`soul.md`, `job.yaml`). Each run first copies any shipped default folder (`<package>/employees/*`) that is missing there; it never overwrites, so the Master user's edits stay. `load_employees(home, SKILL_PATHS)` reads every folder: bad files, an unknown skill or a repeated id keep that folder asleep with one warning. `soul.md` may use `{name}` and `{title}`, filled from `job.yaml`, so a rename needs only the job file. `Hire(spec, soul, skill, hash)`; `hash` is the sha256 of both files. `roster(id PK, name, title, level, reports_to, skill, version, hash, loaded_at)`: upsert per run; a new hash with the same version logs a warning. Shipped defaults use generic level names ("Expert 1").

**Wake rule** (`desk/employees_step.py`, desk step "AI employees", appended to `STEP_PATHS` after Ideas):

```
seed_employees(home, default_folders(DEFAULT_EMPLOYEE_PACKAGES))
for hire in load_employees(home, SKILL_PATHS):
    if hire.spec.trigger != "after_run": continue
    facts = hire.skill.facts(home)
    if not facts.fresh: log skip (facts.why_stale); continue
    if recorder.done_today(name, facts.data_day): continue   # a valid try exists for that day
    items = hire.skill.act(Context(home, gateway(hire, run_id, facts.data_day)), facts)
    recorder.add_briefs(items, hire.spec.id, hire.spec.name)
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

Records use the stable id (`activity.employee`, `briefs.employee_id`) plus the name at that time (`activity.employee_name`, `briefs.author`), so a rename never wakes an employee twice or splits its costs. `done_on(id, day)` is true when that employee posted a brief for the day. Log lines use the current name: `[AI Desk] <name> answered with <model> in 4.2 s, 3,400 tokens`, `[AI Desk] <name> already answered for 2026-11-04`, `[AI Desk] <name> not asked: monthly budget USD 10.00 used up`.

**Limits in P5a.** One trigger only (`after_run`). No priorities, deadlines, expiry or market clock (P5b). No replay (P5b). No HuggingFace or Jev source. Job files are edited by hand (P6 adds editing, rollback and approval).

**After code review and the real run.** A call allows 4 tries (primary twice, backup twice), so `calls_per_day` counts 4 tries per call. Cost checks apply only to OpenRouter, so a used-up API budget never blocks the free Claude CLI. An OpenRouter reply without `usage.cost` fails that try, so spend is never unchecked. A day counts as done only once a brief is posted (`briefs`), so a crash after a valid answer is tried again. Model names starting with `-` are refused. Feed text is shown as plain text. AI Desk gets the desk folder from its poller; Cost & budget is rebuilt each time it opens. The keychain is not read while the window is built.

## DD-DSK-003.004.D01 — Events, Market Clock, LangGraph Run Order and Replay (P5b)

**Traces:** SRD-DSK-002.008–.009, SRD-DSK-003.004–.012, SRD-DSK-005.005–.007

**Boundaries.** `desk` still never imports `market`. Tools post events through `core/desk_events.py`; only `desk/router.py` imports `langgraph`. The market clock uses the app's NYSE calendar in `data/market_calendar.py`, which `core` already uses. LangSmith tracing stays off: the desk process sets `LANGSMITH_TRACING=false` before it imports `langgraph`, so nothing leaves the PC.

**Skill additions** (`core/desk_agents.py`):

```
class Skill(Protocol):
    key: str
    needs: tuple[str, ...]          # skill keys whose views this skill reads; () for none
    answer: type[BaseModel]         # base answer schema; replay checks new answers with it
    def facts(self, home) -> Facts
    def act(self, ctx, facts) -> list[FeedItem]
FEED_KINDS = ("info", "idea", "approval", "evening")
```

`needs` is about function only (for example, the lead brief needs the risk check). It never names an employee and never uses `reports_to`. A skill may ask with a narrower subclass of `answer` built for the day (for example, one whose sector field allows only that day's sectors).

**Job file.** `trigger: after_run` or `trigger: [after_run, market_close]`. The loader turns either form into a tuple and checks each kind against `EVENT_KINDS`; an unknown kind keeps that employee asleep with a warning. P5a files load unchanged.

**Events** (`core/desk_events.py`, shared by tools and the desk):

```
events(id INTEGER PK, key UNIQUE, kind, priority, data_day, created, deadline, expires,
       state ('waiting'|'done'|'late'|'expired'), handled, note)
key = "<kind>|<data_day>", or "after_run|<data_day>|<run_id>" for after_run

EVENT_RULES = {               priority  deadline   expiry
    "regime_change":            P0,     15 min,    2 h
    "after_run":                P1,      2 h,      6 h
    "market_open":              P2,     none,     30 min
    "market_close":             P2,     none,     30 min }

post_event(home, kind, data_day, now, run_id=None) -> bool   # INSERT OR IGNORE on key
```

Clock and regime events come once per kind and data day, so a second desk start or a rebuild of past regime days never posts a second one. `after_run` comes once per run; the P5a once-per-data-day rule (brief posted) still stops a second wake, and a failed day is still tried again on the next run. `regime_change` is posted by the market regime step (cross-tool note in MKT): after its rows are written, it compares the latest day's regime with the day before and posts when they differ. Only the router changes `state`.

**Router** (`desk/router.py`), called by the "AI employees" step and by the desk loop:

```
def handle(home, run_id, now, hires):
    expire: UPDATE waiting events SET state='expired' WHERE expires < now   (log each)
    for event in waiting ORDER BY priority, created:
        woken = [h for h in hires if event.kind in h.spec.trigger]
        if woken: run_graph(event, woken)
        state = 'late' if event.deadline and now_after > event.deadline else 'done'
        (log "late" with the minutes past the deadline)

def has_work(home, now, hires) -> bool     # waiting events that some employee listens to
```

Events nobody listens to are marked done without a run (debug log only), so the clock does not create empty runs.

**Run order with LangGraph** (`run_graph`):

```
by_skill = {skill key: [nodes]} for the woken employees
check:    graphlib.TopologicalSorter(edges).prepare()  — on CycleError log once, wake nobody
graph = StateGraph(GraphState)          # GraphState: {"done": Annotated[list[str], add]}
for node in woken: graph.add_node(node.id, wake_fn(node))
for node in woken:
    before = [n.id for k in node.skill.needs for n in by_skill.get(k, [])]
    graph.add_edge(before or START, node.id)          # list = wait for all of them
    terminal nodes -> END
graph.compile().invoke({"done": []}, {"max_concurrency": 1})
```

A needs key with no woken employee (asleep, not hired, or another trigger) is left out of the edges, and the skill finds the view missing when it reads `desk.db` for the data day, so its facts say so. `wake_fn` wraps the P5a wake rule (fresh facts, once per data day for `after_run`, 30-minute rule, gateway, briefs) in `try/except`. A failed node logs with `log.exception`, returns normally and so never stops the graph. Each node opens its own `Recorder` and gateway, because LangGraph may run a node on a worker thread and a `sqlite3` connection must stay on its own thread. `max_concurrency: 1` keeps one model call at a time, within the caps.

**30-minute rule.** `Recorder.last_wake(id)` = latest `started` in `activity` for that employee with `replay = 0`. When it is less than 30 minutes ago and the event is not P0, the employee is not woken: `[AI Desk] <name> woke 12 minutes ago; next wake after 30 minutes`.

**"AI employees" step** (P5a M10, changed). It posts `after_run` with the run's start date in New York as its day, then seeds and loads employees as before and calls `router.handle`. A regime change posted earlier in the same run is handled first, because it is P0. The step, router and gateway share one injectable clock, so the 30-minute rule and `activity.started` agree. `has_work(home)` first counts waiting events in SQL and reads the employee files only when there is one, because the desk loop asks every 2 seconds.

**Market clock** (`desk/clock.py` + `desk/process.py`):

```
def market_events_due(now) -> list[(kind, day)]:
    now_et on an NYSE trading day (get_exchange_status at noon == "open"):
        09:30 <= now_et        -> ("market_open",  today)
        16:00 <= now_et        -> ("market_close", today)
```

Each `tick()`, when not running or paused, posts what is due (`post_event` ignores repeats), then, if `router.has_work`, starts a run of kind `event` that calls only `router.handle` (not the market steps), and ends it like any run. An open event that expires while the desk is off is marked expired on the next start. Only the evening run calls the market steps.

**Replay** (`desk/replay.py`, `desk replay <run> [--employee ID] [--model NAME]`):

```
tries = activity WHERE run_id = run AND replay = 0, grouped per employee
for employee:
    first = its first try (the prompt without any retry text); old = its last valid try, else last
    hire = loaded employee with that id  (missing -> report "employee not found", no call)
    system, user = first.prompt.split("\n\n---\n\n", 1)
    new = ReplayGateway.resend(system, user, hire.skill.answer, first.source, --model or first.model)
    report: employee name, old valid?, new valid?, fields that differ (top-level names)
```

`ReplayGateway` is a `Gateway` subclass used only by the replay. Its `resend` sends one prompt to one model with one retry, under the same budget and caps, and its tries are written with `replay = 1` (column added on open, default 0). Skills only ever get the plain `Gateway`, so a skill can never choose its own system prompt. A replay never calls `act`, so it writes no views, picks, briefs or events. The report is ASCII; the exit code is 1 when the run has no recorded tries.

**After code review.**
- An error while running a graph (outside a node) is logged, and the event is closed with the note `failed`, so it is not retried every tick. An event skipped for a loop in needs is closed with the note `loop in needs`.
- The desk loop logs and carries on when the event check itself fails.
- Clock events are due only in the 30 minutes after 09:30 or 16:00, so a desk started later posts no stale event.
- Replay tries do not count in the live calls-per-day quota; their cost and CLI tokens still count.
- The replay splits the recorded prompt at the last separator, so a `soul.md` with `---` lines is safe.
- Two employees with the same skill never wait for each other.

**Dependency.** `langgraph>=1.2,<2` in `pyproject.toml`. `USSwing.spec` adds `langgraph` and `langchain_core` to `collect_submodules` for the frozen desk (checked with T121).

## DD-DSK-006.001.D01 — Hiring Pipeline, Shadow and Weekly Report (P6)

**Traces:** SRD-DSK-006.001–.010; GUI SRD-GUI-034.027–.033

**Files.**

| File | What |
|---|---|
| `core/desk_hiring.py` | Start a hire, seat check, list hires, shadow report, agreement, decisions, `approvals` table; in `core` because the GUI makes hires and decisions and the desk reads them |
| `desk/shadow.py` | `run_shadow()`: ask and record only, for an employee with status `shadow` |
| `desk/weekly_report.py` | `WeeklyReportStep` (desk step "Weekly report", after "AI employees"), `desk_reports` table |
| `desk/registry.py` | `JobSpec` gets `status` (`active` default, `shadow`, `retired`) and `hired_on`; retired employees are not loaded |
| `desk/recorder.py`, `desk/gateway.py` | `activity.shadow` column (added on open, default 0); `Gateway(shadow=True)` marks tries |
| `desk/employees_step.py` | `_wake` sends shadow employees to `run_shadow()` |
| `core/desk_ai_settings.py` | `expert_cap` 8, `champion_cap` 5, `junior_cap` 30 |
| `gui/ai_desk_hiring.py` | Hiring section and the Command approvals box |
| `gui/ai_desk_sections3.py`, `core/desk_floor.py` | Reports section from `desk_reports` |
| `gui/ai_desk_settings.py` | Seat cap fields |

**Employee status** (in `job.yaml`, data the Master user controls):

```
status: active | shadow | retired      # missing -> active
hired_on: YYYY-MM-DD                   # only on hires made through the pipeline
```

**Start a hire** (`start_hire(home, skill, level, name, source, model, today)`):

```
refuse when: skill not in SKILL_PATHS; level == "lead"; name used by any employee (case-insensitive);
             count(level, status in active|shadow) >= cap(level)
id   = "emp-" + 3 digits, one above the highest number in <desk>/employees
soul = soul.md of the shipped default employee with the same skill
job  = that default's job.yaml with id, name, title = level title, level, version 1,
       status shadow, hired_on today, models.primary = (source, model); reports_to kept
write both files; log [Hiring] <name> started in shadow for <skill>
```

**Shadow run** (`run_shadow(hire, facts, gateway, recorder)`, called from `EmployeesStep._wake` after the fresh-facts check):

```
days = distinct data_day of this employee's shadow tries
if len(days) >= 14: return                      # ready; no more calls
if facts.data_day in days: return               # one answer per data day
gateway.ask(facts.text, hire.skill.answer)      # tries written with shadow = 1
if len(days) + 1 == 14: log [Hiring] <name> finished the shadow and is ready for a decision
```

`skill.act` is never called, so no views, picks, briefs or events come from a shadow. The run order is unchanged: a shadow employee runs after the skills its skill needs.

**Shadow report** (`shadow_report(home, hire_id) -> list[ReportRow]`), over the hire's shadow days:

```
holders = active employees with the same skill (not the hire)
row(hire):   days, valid share = days with a valid try / days, tokens, cost
row(holder): the same, from its live tries (shadow 0, replay 0) on those days
agreement    = mean over days where both have a valid answer of
               jaccard(short_values(hire answer), short_values(holder answer))
short_values = {"path=value"} for bool, number, and text of at most 20 characters;
               list items keyed by side+symbol when present, else by position
None ("-") when there is no holder or no common day
```

**Decisions** (`decide(home, hire_id, decision, now)`), table in `desk.db`:

```
approvals(id INTEGER PK, created TEXT, kind TEXT, subject TEXT, decision TEXT, detail TEXT)
triggers approvals_no_update / approvals_no_delete
replace: holders -> retired; hire -> active      (refused when the hire is not ready)
add:     hire -> active                          (refused while the skill has an active holder)
reject:  hire -> retired                         (allowed at any time)
```

Status changes edit only the `status:` and `version:` lines of `job.yaml` (version + 1), so the Master user's comments stay. The approvals row is written first; a file error is logged with `[Hiring]`.

**Weekly report** (`WeeklyReportStep`, `name = "Weekly report"`):

```
friday = latest Friday <= today (New York)
if desk_reports has week == friday: return
period = Saturday before friday .. friday (by activity.started, New York)
text:  per employee (current name): calls, valid share, tokens, cost, failed tries
       totals; shadow hires: days done of 14, ready or not
INSERT desk_reports(week, created, title "Weekly report <friday>", text)
log [Report] Weekly report for <friday> written: <n> employee(s), cost USD <x>
```

No AI call. The GUI Reports section lists `desk_reports` newest first; sample reports show only while there are none.

**Seat caps** live in `desk_ai.json` (`expert_cap`, `champion_cap`, `junior_cap`, each at least 1). Desk settings refuses a cap below the current count of active and shadow employees at that level.

**GUI Hiring** (`hiring_frame(name, home)`, a live section): table Name · Skill · Level · Model · Started · Shadow days · Status (status shadow, ready, active or retired). Below: the Start hire form (skill combo from `SKILL_PATHS`, level combo expert/champion/junior, name, source combo, model text) with a status line for the refusal reason; the chosen hire's report table (Who · Days · Valid · Tokens · Cost · Agreement); Replace, Add and Reject buttons, enabled as in the decision rules. Command → Approvals waiting lists ready hires; a click opens Hiring.

## DD-DSK-007.001.D01 — AI Problem Alerts

**Traces:** SRD-DSK-007.001–.006.

**Store.** New table `alerts(id, key UNIQUE, created, kind, source, run_id, title, text, fix, sent)` in `desk.db`, created by `core/desk_alerts.py`. `key = kind|source|NY day` gives one row per problem per day (`INSERT OR IGNORE`).

**Spotting.** `classify(source, error)`: `credit` for 402 or credit words; `login` (source `claude`) or `key` (other sources) for sign-in words (authenticate, auth login, not logged in, oauth, 401, unauthorized, invalid api key, no auth credentials). Anything else is a normal bad answer.

**Gateway.** After a failed try, `Gateway._report` classifies the error; a user problem adds the source to a per-run set (`_BROKEN[(home, run_id)]`) and calls `raise_alert`. `ask()` skips a source in that set (no second try either) and goes to the backup. Replays never alert.

**Whole run.** `EmployeesStep.__call__` ends with `_check_run`: `run_outcome(run_id)` = real calls, valid calls, last error; calls > 0 and valid = 0 raises `run_failed`.

**Telegram.** `send_telegram(text)`: `telegram_target()` reads `~/.usswing/users.json` (first user with `telegram_enabled` and a chat id) and the token from the keychain service `usswing_telegram` (the same place the GUI keeps it), then posts `sendMessage` with a 10 s timeout. Success sets `sent = 1`. The sender is injectable (`send=`) on `Gateway`, `EmployeesStep` and `raise_alert`; tests point `USERS_FILE` at a temp folder.

**Open alerts.** `open_alerts(home, now)`: rows from the last 24 hours with no later valid `activity` row (same source for login, key and credit). Shown by the GUI as a red banner in Team at work and a Desk card in the AI feed (SRD-GUI-035.010–.011).

## DD-DSK-008.001.D01 — Employee File and Versions

**Traces:** SRD-DSK-008.001–.009.

**File.** `<desk>/employees/<id>/employee.md`:

```
---
id: emp-006
name: Expert 5
... (every JobSpec field, same names as job.yaml)
---
You are {name}, {title} ...   <- system prompt (soul)
```

Front matter is the text between the first two `---` lines, read with `yaml.safe_load`; the body after the second `---` (one leading newline dropped) is the prompt. `{name}` and `{title}` stay as placeholders in the file and are filled at load, as today.

**Shared rules (`core/desk_employee.py`).** `JobSpec`, `ModelChoice`, `Models` move here from `desk/registry.py` (registry re-imports them, so other `desk` code is unchanged). `EmployeeFile(spec, prompt, text)`; `parse(text) -> EmployeeFile` raises `ValueError` with the first plain reason; `render(spec, prompt) -> str` writes the front matter with `yaml.safe_dump(sort_keys=False)` in JobSpec field order; `read_employee(folder) -> EmployeeFile | None` reads `employee.md`, else the old pair (no write). The roster hash is sha256 of the file text.

**Migration.** `migrate_folder(folder) -> bool`: when `employee.md` is missing and both old files exist and pass the rules, write `employee.md` from them, then move `job.yaml` and `soul.md` into `history/` as `v<N>-job.yaml` / `v<N>-soul.md`. `migrate_all(home)` loops the folders and logs `[AI Desk] Moved %d employee(s) to employee.md`. Called by `registry.seed_employees` and by Team setup when it opens. A folder whose old files fail the rules is left as is (it stays asleep, as today).

**Defaults.** `market/employees/emp-NNN/` hold one `employee.md` each (made from the old pair; the comment header kept as YAML comments). `seed_employees` copies a folder only when `<desk>/employees/<id>` is missing.

**Save.** `save_employee(home, emp_id, fields, prompt) -> str`: build the spec with `version = old + 1`, check it with `JobSpec`, check seats when the level changes (`desk_hiring.seat_counts` and the caps in `desk_ai_settings`), then copy the old `employee.md` to `history/v<old>.md` and write the new one through a temp file + `os.replace`. Returns `""` or the reason. `id` and `skill` cannot change. `versions(folder) -> list[Version(number, saved, path)]` lists `history/v<N>.md` plus the current file. `restore(home, emp_id, number)` reads that version and calls `save_employee` with its fields and prompt, so it becomes the next version.

**Registry.** `load_employee(folder)` calls `read_employee`; hash input is the file text. Every event still reloads the folder, so a save applies from the next wake.

**Hiring.** `start_hire` reads the default `employee.md`, sets id, name, level, status shadow, models, hired_on and version 1, and writes `employee.md` with `render`. `_set_status` writes through the same save path (version + 1, history kept).

**Draft test.** `desk/cli.py _replay` accepts `--draft FILE`. `replay(..., draft=Path)` parses the draft with `parse`, builds `system = gateway.system_prompt(filled draft prompt, schema)`, keeps the recorded user part and resends with the draft's main model. It prints the usual report plus the new answer text. `core/desk_employee.try_draft(home, emp_id, text, timeout=180) -> DraftResult(valid, answer, note)` writes the draft to a temp file and runs `desk_command() + ["replay", run, "--employee", id, "--draft", path]` with no window, reading stdout; the run is the employee's newest run with recorded tries in `activity`. It returns a note when there is no such run.

**Models list.** `known_models(home) -> dict[source, list[str]]`: `default`, the desk settings model of each source, and the models seen in `activity` for that source.

## DD-DSK-001.015.D02 — Morning Run and Desk Lifetime (Autonomous desk step A)

**Traces:** SRD-DSK-001.013, .015, .018, .019, .020, SRD-DSK-003.013, SRD-DSK-007.005, .007. Design page: https://claude.ai/artifact/J7AexvWdqDNujADoc9dJkJ. Supersedes the evening run and Windows tasks of DD-DSK-001.001.D01.

**Run kinds.** `morning` (the daily run: every desk step), `manual` (run-now and the catch-up of an interrupted run), `event` (only the event handler). Old `evening` rows stay in `runs` and `briefs` and are read as history (labels map `evening` → "Evening run").

**Morning due (`desk/clock.py`).** Pure function, clock passed in:

```
MORNING_START = 04:00 ET, MORNING_END = 16:00 ET, RETRY_AFTER = 15 min, MAX_TRIES = 3

morning_due(now, runs):          # runs = (kind, started_at, result) of the last day
    et = now in ET
    if not is_trading_day(et.date) or not (MORNING_START <= et.time < MORNING_END): False
    today = runs of kind morning or manual started today at or after 04:00 ET
    if any(result == "ok" for today): False          # a manual ok run counts as done
    tries = [r for r in today if kind == morning and result == "failed"]
    if len(tries) >= MAX_TRIES: False
    last = newest morning start today
    return last is None or now - last >= RETRY_AFTER
```

`interrupted` and `running` morning rows do not count as tries: an interrupted run is caught up at once as `manual` (SRD-DSK-001.014), and an ok manual run closes the day. The trading-day check uses the app's NYSE calendar (2026 holidays only, T125).

**Loop (`desk/process.py`).** `tick()` order: heartbeat → commands → parent check → `rerun`/`run_now` → `morning_due(now, store.runs_since(now - 1 day))` → event tick. `daily_check` now runs once at start only (old-task clean-up).

**Parent watch.** `DeskProcess(parent_alive=...)`. When it returns False the desk logs `[Desk] The app has closed; stopping the desk` and goes to Stopping; between steps of a run `_commands_during_run` also returns stop, so the run ends `interrupted` and `rerun` is saved (caught up at the next start). `pid_alive(pid)` (Windows): `OpenProcess(SYNCHRONIZE)` then `WaitForSingleObject(h, 0) == WAIT_TIMEOUT`; no handle = gone, except access denied (error 5) = alive. Elsewhere `os.kill(pid, 0)`.

**CLI.** `desk [--resume] [--parent PID]`; `install`/`uninstall` removed. `launch_desk(resume=True, parent=None)` adds `--parent <pid>`. Start-up `daily_check` = `task.remove_old_tasks()`: `schtasks /delete /tn USSwing_Desk /f` and `USSwing_Desk_Evening`; "cannot find" is not an error; failures are logged once as a warning.

**App close.** The app sends Stop through `commands` from a short thread and waits at most 2 s; if that fails, the parent watch stops the desk within one poll (2 s). The scheduled close task (`taskkill /IM USSwing.exe /F`) also kills the frozen desk, which runs as `USSwing.exe desk`; its open run is marked interrupted and caught up at the next start.

**Candles alert (`core/desk_alerts.py`).** New kind `candles`: title "Candles not up to date", fix "Open Settings → Candle data and press Update now with TWS connected; the desk tries again in 15 minutes." Raised by the MKT candle check (DD-MKT-001.013.D01) with the run id. `open_alerts` closes a `candles` alert when a later `morning` or `manual` run ended `ok` (compared in UTC: `runs.started_at > utc_text(created)`). Whole-run alert (SRD-DSK-007.005) is unchanged in code; it fires for any run whose employees step ran.
