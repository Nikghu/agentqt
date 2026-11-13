# Design Document — Desk Harness (DSK)

**Document ID:** DD-DSK
**Version:** 0.5.0
**Status:** Draft
**Last Updated:** 2026-11-11
**Project:** US Swing Trading System

> v0.16.0: DD-DSK-011.033.D01 added — escalation and deputies (AI Desk v3 M2, 2026-11-13).
> v0.15.0: DD-DSK-011.015.D01 added — messages and the reply path (AI Desk v3 M1, 2026-11-13).
> v0.14.0: DD-DSK-011.001.D01 and DD-DSK-012.001.D01 added — message format, tool registry and schema library (AI Desk v3 M0, 2026-11-13).
> v0.13.0: DD-DSK-010.016.D01 added — owner-raised strategy test ticket (2026-11-12).
> v0.12.0: DD-DSK-010.015.D01 added — follow-up tickets from research skills (step F).
> v0.11.0: DD-DSK-010.001.D01 added — token split and research queue (Autonomous desk step E (2026-11-11)).
> v0.10.0: DD-DSK-003.020.D01 added — check-ins and watchers (Autonomous desk step D (2026-11-11)).
> v0.9.0: DD-DSK-009.001.D01 added — desk memory: lessons, learning loop and Memory view (Autonomous desk step C (2026-11-11)).
> v0.8.0: DD-DSK-003.014.D01 added — baton by `step_done` events, retries, partial plan, LangGraph removed (Autonomous desk step B, 2026-11-11).
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

## DD-DSK-003.014.D01 — Baton: `step_done` Events, Retries and Partial Plan (Autonomous desk step B)

**Traces:** SRD-DSK-003.010–.012, .014–.019, SRD-DSK-007.008. Design page §5: https://claude.ai/artifact/J7AexvWdqDNujADoc9dJkJ. Supersedes the "Run order with LangGraph" part of DD-DSK-003.004.D01; the market steps keep their fixed order (user, 2026-11-11: AI employees only).

**Words.** A *trigger* is any event an employee listens to (`after_run`, `market_close`, …). Its *chain* is the employees whose `trigger` holds the trigger's kind. A *step* is one employee's turn in a chain.

**Tables** (`core/desk_events.py`; columns added on open when missing, so old `desk.db` files load):

```
events  + parent INTEGER NULL   # trigger id, only for step_done
        + due    TEXT NULL      # not handled before this time (retries); NULL = now
steps(event_id INTEGER, employee TEXT, tries INTEGER, result TEXT, updated TEXT,
      PRIMARY KEY (event_id, employee))
result: 'running' | 'ok' | 'slept' | 'failed' | 'skipped'

post_step_done(con, trigger: Event, employee, tries, result, now, due=None)
    key = "step_done|<trigger.id>|<employee>|<tries>"   INSERT OR IGNORE
    priority, data_day, deadline, expires copied from the trigger; state 'waiting'
```

`step_done` is not in `EVENT_KINDS`: no tool may post it and no job file may listen to it (SRD-DSK-003.014). The router finishes a `step_done` like any event (done, late or expired).

**Wake result.** `Wake = Callable[[Hire, Event, bool, tuple[str, ...]], str]` (employee, trigger, retry, missing names) returns:

| Case in `EmployeesStep._wake` | Result |
|---|---|
| Valid answer (`gateway.answered`) or already answered today | `ok` |
| Facts not fresh, shadow employee, budget or cap refused, 30-minute rule | `slept` |
| No valid answer, or an exception | `failed` |

`retry` is True when `tries > 1`. The last argument holds the names of failed or skipped steps; when it is not empty, each brief the employee writes gets the first line `Partial plan: no view from <name>, <name>.` (names come from the job files). The lead's facts already say "not available today" for each missing view (`views_text`), so the model knows.

**Router pass** (`desk/router.py`, one thread, no LangGraph):

```
handle():
    expire()
    while (event := next waiting event with due <= now, by priority, created):
        trigger = event if event.parent is None else load(event.parent)
        chain = listeners(trigger.kind)
        if event is the trigger and order(chain) has a loop: finish(event, 'loop in needs'); continue
        note = advance(trigger, chain)
        finish(event, done|late, note)          # after the wakes, so a cut pass is redone

advance(trigger, chain):
    for hire in run_order(chain):               # needs order; same skill never waits
        row = steps[trigger.id, hire.id]
        if row is ok/slept/skipped, or failed with tries == 3: continue
        if row is running: row = failed try (app closed mid-wake, SRD-DSK-003.019)
        if row is failed and now < row.updated + 5 min: continue      # retry not due
        needs = ids that hire waits for (as _edges today)
        bad   = needs whose result is failed (3 tries) or skipped
        if bad and hire.level != 'lead': write skipped; log once; continue
        if any need not settled: continue      # settled = ok, slept, skipped, failed x3
        if not bad and any need not ok/slept: continue
        tries = (row.tries if row else 0) + 1
        write running(tries)
        retry = tries > 1                       # skips 30-min and once-per-day rules
        if not retry and too_soon(hire, trigger): result = 'slept'
        else: result = wake(hire, trigger, retry, names of bad)
        if result == 'failed' and tries < 3:
            write failed(tries); post_step_done(..., due = now + 5 min)
        else:
            write result; post_step_done(..., due = None)
            if result == 'failed': raise_alert('partial', source = hire.id, ...)
    if chain settled: set trigger note to 'chain full' or 'chain partial'
```

A need is settled when its result is `ok`, `slept`, `skipped` or `failed` after 3 tries. An ordinary employee wakes only when all needs are `ok` or `slept` (SRD-DSK-003.015, .011). If any need failed or was skipped, it is skipped too, so skips flow down the chain (SRD-DSK-003.017). The employee at level `lead` waits until all needs are settled, then runs once with the missing names (SRD-DSK-003.018). If the lead itself fails 3 times, no plan is posted.

**Retries.** The 30-minute rule (SRD-DSK-003.009) and the once-per-data-day check are skipped when `tries > 1`. The wait comes from the `due` time on the `step_done` row. Between passes, the morning run may end; the desk loop's `has_work` (waiting events with `due <= now`) then starts an `event` run 5 minutes later. `has_work` treats every due `step_done` as work.

**Resume** (SRD-DSK-003.019). The chain lives only in `events` and `steps`. When the app closes mid-pass, the event being handled stays `waiting`. At the next start, `advance` is run again: finished steps are skipped, and a `running` row counts as a failed try. A chain whose events have expired stops quietly; each expiry is logged as today.

**Alert** (`core/desk_alerts.py`, kind `partial`). Title: "Desk plan is partial". Text: "<name> failed 3 times: <last error>". Fix: "Open AI Desk → Team at work → Event log to see the error; the next run tries again." The same once-a-day-per-source rule and the same Telegram rule apply. `_fixed('partial')` returns True when a later event has the note `chain full`. The last error is the newest `activity.error` of that employee in the run.

**Log lines** (`[AI Desk]`):
- `<name> failed; trying again in 5 minutes (try 2 of 3)`
- `<name> failed 3 times; the steps that need it will not run`
- `<name> will not run: it needs <name>, which failed`
- `The lead is writing a partial plan without <names>`

**LangGraph removed** (SRD-DSK-003.012). Remove `langgraph` from `pyproject.toml`, and remove `langgraph` and `langchain_core` from `USSwing.spec` `collect_submodules`. Remove the `LANGSMITH_TRACING` line and `_GraphState`. The run order uses `graphlib` from the standard library, as the loop check already does.

**After code review.**
- A retry whose `step_done` expires (the chain's expiry passed before the next try) is marked failed and raises the `partial` alert, so the user still hears about it.
- `waiting_count(home, now)` counts only due events, so the desk loop does not rebuild the router every 2 s during a retry wait.

## DD-DSK-009.001.D01 — Desk Memory: Lessons, Learning Loop and Memory View (Autonomous desk step C)

**Traces:** SRD-DSK-009.001–.009, SRD-MKT-012.001–.006, SRD-GUI-037.001–.004. Design page §8: https://claude.ai/artifact/J7AexvWdqDNujADoc9dJkJ. User answers (2026-11-11): lessons only for pick makers; active at 5 cases (backtest check later, step E/F); one reflect call a day after pick results.

**Boundaries.** All lesson rules live in `core/desk_lessons.py`, because the market skills (MKT), the desk loop (DSK) and the GUI all use them. It reads the market tables in `desk.db` with plain SQL and never imports `market`. Risk check code, EXE capital and approval code never import it (SRD-DSK-009.005, checked by a source scan test).

**Tables** (`desk.db`, made on open):

```
lessons(id INTEGER PK, text, tags TEXT /* JSON {key: value} */, claim 'better'|'worse',
        proof TEXT /* JSON ["date|side|symbol", ...] */, cases INTEGER, avg_r REAL,
        confidence REAL, status 'candidate'|'active'|'retired', made, active_on,
        last_confirmed, retired_on, pinned INTEGER, author 'desk'|'master', why TEXT)
lesson_uses(day, skill, lesson_id, PRIMARY KEY (day, skill, lesson_id))
lesson_edits(id INTEGER PK, lesson_id, action 'pin'|'unpin'|'edit'|'retire'|'delete',
             text, created, applied NULL, note)      # GUI writes only new rows
memory_state(key PRIMARY KEY, value)                 # 'reflected_closed' = count at last reflect
```

**Tags.** `TAG_KEYS = ("side", "setup", "regime", "sector", "grade", "tone")`. A lesson holds 1 to 3 of them. Each closed pick gets its tags by joining `pick_results` (status stop, target or time) with `ideas` (setup, sector), `regime_snapshot` (regime on the pick date), `setup_review` (grade) and `news_tags` (tone), all on (date, side, symbol). A missing value is left out. A pick matches a lesson when every lesson tag is equal to the pick's tag.

```
cases(home) -> list[Case(key, day, tags, r)]           # closed paper picks
check(tags, claim, cases) -> Proof(n, avg_r, agree, confidence)
    m = matching cases; base = mean r of all cases
    avg_r = mean r of m; agree = avg_r < base (worse) or avg_r > base (better)
    confidence = share of m with r on the claimed side of base
```

**Add a candidate** (`add_candidate(home, text, tags, claim, proof, now)`, SRD-DSK-009.003). A kept, not retired lesson with the same tags and claim gets the new text and proof, and is checked again. Otherwise a new candidate row is added. Then `check()` runs. With `n >= 5` and `agree`, the lesson becomes active at once (`active_on = last_confirmed = now`).

**Daily review** (`review_lessons(home, now)`), called at the end of the "Pick results" step:

```
candidate: n >= 5 and agree        -> active
           made older than 30 days -> retired ("not proved in 30 days")
active (not pinned):
    later = matching cases dated after active_on whose day+skill is in lesson_uses
    a new later case on the claimed side            -> last_confirmed = now
    len(later) >= 10 and check(later) does not agree -> retired ("later picks do not back it")
    last_confirmed older than 90 days                -> retired ("not confirmed in 90 days")
cases, avg_r, confidence are refreshed for every non-retired lesson
```

**Lessons block** (`lessons_block(home, skill, day) -> str`, SRD-DSK-009.004 and .006). It takes the active lessons that match at least one of `day`'s ideas, puts pinned ones first, then sorts by confidence, keeps at most 5, and cuts at 800 tokens (3,200 characters, 4 characters a token). It writes one `lesson_uses` row for each lesson shown and returns an empty string when there is none. The text looks like this:

```
Lessons from past picks (use them only to be stricter: lower a grade, add a veto or
skip a pick; never loosen a rule):
- L-17: Pullback longs in a high volatility regime fail more often (8 cases, average -0.42R).
```

**Edits** (`add_edit(home, lesson_id, action, text, now)` from the GUI; `apply_edits(home, now) -> int` in the desk loop, SRD-DSK-009.008). Each `DeskProcess.tick()` applies pending rows oldest first. Pin and unpin set `pinned`. Edit sets the text and `author = 'master'`. Retire sets `status = 'retired'`. Delete removes the row and its `lesson_uses`. An unknown lesson id sets the note "lesson not found". Every row gets `applied = now`. `apply_edits` first checks for a pending row with one SELECT, so the 2-second tick stays cheap.

**Reflect skill** (`market/lesson_reflect.py`, key `lesson_reflect`, needs `()`):

```
facts: closed = cases(home); fresh when len(closed) > memory_state.reflected_closed
       text = stats table (count, win rate, average R by each tag key and value, n >= 2)
            + today's newly closed picks with tags and R + active lessons (id, text)
answer: LessonReflect{lessons: list[Candidate] (max 3)}
        Candidate{text: str (<=200), tags: dict[TagKey, str] (1-3), claim: Literal[better, worse],
                  picks: list[str] (1-20)}
act:   drop picks not in closed; drop a candidate with no pick left -> add_candidate each;
       set reflected_closed = len(closed); log "[Memory] Kept %d candidate lesson(s), dropped %d"
       returns one info brief "New candidate lessons: ..." when one was kept
```

The default employee `emp-010` ("Expert 8", title "Learning analyst", level expert, reports to the lead `emp-005`, trigger `after_run`, 3 calls a day, USD 2 a month) ships in `market/employees/emp-010/employee.md`. The skill path is added to `SKILL_PATHS`. The once-per-data-day rule and the budget guard work as for every employee, so a refused call just sleeps.

**Pick makers** (SRD-MKT-012.005). `setup_review`, `news_review`, `risk_check` and `lead_brief` add `lessons_block(home, KEY, day)` as the last part of `Facts.text`. `regime_view` and `sector_view` do not change.

**Memory view** (`gui/ai_desk_memory.py`, SRD-GUI-037.*). `MemoryView(QWidget)` reads `lesson_rows(home, status)`, `pending_edits(home)` and `proof_rows(home, lesson_id)` from core on each refresh, in the GUI thread like Results (small read-only SQLite reads). It has a status filter (Active, Candidate, Retired), a table (Status, Pinned, Lesson, Tags, Cases, Avg R, Confidence, Last confirmed), and the buttons Pin/Unpin, Edit, Retire and Delete (Delete asks first). Each button calls `add_edit`; Edit uses the text box under the table and Save text (no dialog). A lesson with a pending edit shows "applies at the next desk tick" in its status cell. The proof list under the table shows date, side, stock and R for the chosen lesson. In `gui/ai_desk.py`, "Memory" joins the review group after "Results" and `_LIVE_SECTIONS`.

**Log lines** (`[Memory]`): "New candidate lesson L-%d: %s", "Lesson L-%d is active (%d cases)", "Lesson L-%d retired: %s", "Kept %d candidate lesson(s), dropped %d".

**After code review (step C).**
- `with_lessons` returns the plain facts and logs a warning on any memory error, so a lesson problem never stops a pick maker.
- A desk candidate never replaces the text of a Master-edited or pinned lesson; only its proof is updated.
- A candidate like a lesson retired in the last 90 days stays a candidate (no retire and re-activate loop).
- A pinned candidate is never retired after 30 days; `lessons.id` uses AUTOINCREMENT so a deleted id is not reused.
- The reflect prompt lists at most the 50 newest closed picks.
- Known gap: a pick made before the last confirmation but closed after it does not refresh the confirmation (90-day rule only).

## DD-DSK-003.020.D01 — Check-ins and Watchers (Autonomous desk step D)

**Traces:** SRD-DSK-003.020–.025, SRD-DSK-007.009, SRD-MKT-013.001–.012, SRD-GUI-038.001–.003. Design page §4 and §6: https://claude.ai/artifact/J7AexvWdqDNujADoc9dJkJ. User answers (2026-11-11): prices from the app's intraday candles; the stop/target watcher covers all open trades; watchers every 5 minutes; an AI note at each check-in.

**Data flow.**

```
app (GUI)  LiveBarWorker ──3m bars──▶ candles.db price_3m      (now also desk plan stocks + SPY)
           trade cycles  ──every 60 s / on change──▶ desk.db open_trades
desk loop  every 5 min in market hours ─▶ market.watch.run_watch(home, now)
               reads price_3m, ideas, lead_picks, open_trades, news_items
               ─▶ watch_flags row + feed note + watch_flag event (+ alert for stop/target)
router     watch_flag (P0) ─▶ employee with skill watch_flag  ─▶ verdict row, feed note, alert if broken
clock      market_checkin 10:00 / 12:30 / 15:30 ET (P2) ─▶ employee with skill checkin_note ─▶ note
```

**Shared tables** (`core/desk_watch.py`, made on open):

```
watch_flags(id INTEGER PK AUTOINCREMENT, day, hour, kind, symbol, detail, price REAL, created,
            verdict NULL, note NULL, answered NULL, UNIQUE (day, hour, kind, symbol))
open_trades(symbol, side 'long'|'short', entry REAL, stop REAL, target REAL NULL, strategy,
            updated)                                   # written only by the app
FLAG_KINDS = trigger_hit, stop_touch, target_touch, volume_spike, gap, regime_move, headline
add_flag(home, kind, symbol, detail, price, now) -> int | None   # None when the hour key exists
flagged_today(home, kind, symbol, day) -> bool                    # once-a-day kinds
next_flag(home, day) -> Flag | None                               # oldest without verdict
answer_flag(home, flag_id, verdict, note, now); flags_since(home, since) -> list[Flag]
add_note(home, text, day, now)            # briefs row, author "Watchers", employee_id ""
write_open_trades(home, rows, now); open_trades(home) -> list[OpenTrade]
desk_live_symbols(home, day) -> list[str] # listed ideas + lead picks of the newest day <= day, then SPY
```

The `hour` is the New York hour, so the UNIQUE key gives "once per stock and kind an hour" (SRD-DSK-003.022). `add_flag` posts the `watch_flag` event with the flag id as its per-event id, and adds the code feed note: `"<symbol>: <label> at <price> — <detail>"` (SRD-DSK-003.021, .024).

**Events** (`core/desk_events.py`): `market_checkin` P2, no deadline, 30-minute expiry, keyed per slot (`market_checkin|<day>|1000`). `watch_flag` P0, deadline 5 minutes, expiry 30 minutes, keyed per flag id. Both are added to `_PER_ID`.

**Clock** (`desk/clock.py`): `CHECKINS = (10:00, 12:30, 15:30)`. `checkins_due(now) -> list[(day, slot)]` is due in the 30 minutes after each time on trading days. `in_market_hours(now)` is true from 09:30 to 16:00 ET on trading days.

**Desk loop** (`desk/process.py`, `_event_tick`). It posts the check-ins that are due, with `_posted` keyed by (kind, day, slot). When `in_market_hours(now)` holds and 5 minutes have passed since the last pass, it calls `self._watch(home, now)` in a try/except and logs a failure (SRD-DSK-003.023). The watcher comes from `core/desk_steps.WATCH_PATH = "us_swing.market.watch:run_watch"` through `load_watch()`, so `desk` never imports `market`. The CLI passes `watch=load_watch()`. After the pass, the normal `has_work` check starts an `event` run for the new flags.

**Watchers** (`market/watch.py`, `run_watch(home, now, candles=CANDLE_DB) -> int`):

```
day = today in ET; plan = listed ideas of the newest ideas day <= day (side, symbol, trigger, stop)
picks = lead_picks of that day; trades = open_trades(home)
bars = 3m bars of today (ET) for plan + trade symbols + SPY, read-only from price_3m (UTC text)
fresh = symbols whose newest bar is at most 15 minutes old          (SRD-MKT-013.001)
prev_close = last daily close before today (CandleReader + candle_topup)
trigger_hit   long: max high >= trigger; short: min low <= trigger; once a day   (.002)
stop_touch    long: last bar low <= stop; short: last bar high >= stop           (.003)
target_touch  long: last bar high >= target; short: last bar low <= target       (.003)
volume_spike  last volume >= 3 × mean of the 20 bars before it                   (.004)
gap           |first open / prev_close − 1| > 3%; once a day                     (.005)
regime_move   |SPY last close / prev_close − 1| > 1.5%; once per direction a day (.006)
headline      every 15 min, picks + trade symbols: news.fetch_symbol(); a title not in
              news_items for that symbol and not flagged today; published after 09:30 ET  (.007)
stop_touch / target_touch also raise_alert('trade_stop' | 'trade_target', source = symbol)
returns the number of new flags; logs "[Watch] %d new flag(s): %s"                 (DSK .025)
```

**Flag skill** (`market/watch_flag.py`, key `watch_flag`, needs `()`). Facts are fresh when `next_flag(home, day)` exists. They hold the flag, its plan (an idea with trigger, stop, setup and reasons, or a trade with entry, stop and target), the last 12 bars, and the rule "AI never places a trade". The answer is `WatchVerdict{verdict: holds | watch | broken, note: str (<= 300)}`. Act stores it with `answer_flag`, returns a feed item `"<symbol> <label>: <verdict> — <note>"`, raises `raise_alert('plan_broken', source = symbol)` when broken, and logs `[Watch] <symbol> <kind>: <verdict>`.

**Check-in skill** (`market/checkin_note.py`, key `checkin_note`). Facts are fresh on a trading day. They hold the plan stocks against their triggers (last price, distance %), the open trades against stop and target, the SPY move against the previous close, and the flags since the last check-in note (or since 09:30). The answer is `CheckinNote{note: str (<= 600)}`, and the feed item is `"Check-in <HH:MM>: <note>"`.

**Defaults** (`market/employees/`):
- `emp-011` "Expert 9": title Market watcher, level expert, skill `watch_flag`, trigger `watch_flag`, 40 calls a day, USD 3 a month.
- `emp-012` "Lead 3": title Market lead, level lead, skill `checkin_note`, trigger `market_checkin`, 3 calls a day, USD 2 a month.

Both are added to `SKILL_PATHS` and `USSwing.spec`.

**Alerts** (`core/desk_alerts.py`), each once per kind, stock and day:
- `trade_stop` "Trade at stop": "Check the trade in Execution; the desk does not close it."
- `trade_target` "Trade at target": "Check the trade in Execution."
- `plan_broken` "Plan broken": "Read the desk's note in Market Floor before you act."

**App** (`gui/app_service.py`). `_start_live_bar_worker` uses `list(dict.fromkeys(held + filtered + desk_live_symbols(desk_home(), today)))[:100]`, and logs `[Live] Added %d desk stock(s) to the live feed`. `_publish_open_trades()` turns the `_tc_query.open_cycles()` snapshots into rows: side from direction, stop = `effective_stop or hard_stop_loss`, and the target. It calls `write_open_trades`, and runs at start, in `_on_cycle_symbols_changed` (queued to the GUI thread) and on the 60-second market-status timer. Errors are logged at warning level and never stop the app.

**After code review (step D).**
- Stop and target touches look at the bars of the last 10 minutes (passes run every 5 minutes on 3-minute bars) and are flagged once a day per trade level, so a trade sitting past its stop does not wake the AI every hour.
- A stop of 0 means the trade has no stop; it is never treated as a level.
- Once-a-day flags keep their key in a `tag` column, so the stored detail (gap %, SPY %) stays readable in the feed and the prompt.
- A gap is judged only when the day's 09:30 bar is there (first bar no later than 09:36).
- Each watcher runs in its own try/except, so one failing watcher never stops the pass.
- The flag skill answers the flag it showed in its facts; a flag with no valid answer is closed as `none`, so newer flags are not stuck behind it.
- The app writes open trades only when the list changed, on a short background thread, so a busy `desk.db` never blocks the GUI or the trade-cycle thread; held stocks come first in the 100-symbol live feed.
- Tests point `desk_home()` at a temp folder (root conftest), so no test writes the real `desk.db`.

## DD-DSK-010.001.D01 — Token Split and Research Queue (Autonomous desk step E)

**Traces:** SRD-DSK-004.006–.010, SRD-DSK-007.010, SRD-DSK-010.001–.014, SRD-MKT-014.001–.005, SRD-GUI-039.001–.005. Design page §7 and §9 (stop rules R1–R8): https://claude.ai/artifact/J7AexvWdqDNujADoc9dJkJ. User answers (2026-11-11): per-employee daily tokens split 50/20/30; a ticket of 10,000 tokens or less is approved by itself; the cap is hard and the raising lead's research part pays; waiting tickets show in AI Desk and on Telegram; step E is the queue only — research skills come in step F, so tests use a fake skill.

**Data flow.**

```
lead skill (lead_brief, checkin_note)   facts += research block (tokens left, open tickets, results)
      answer.tickets ─▶ core.desk_research.raise_tickets(home, skill_key, asks, now)
                          rules ─▶ tickets row: approved (auto) | waiting (+ alert) | refused (log)
app (GUI)  AI Desk → Research ─▶ ticket_edits row (approve | reject | cap)
desk loop  every tick: apply_ticket_edits, expire_waiting
           no event work and quiet ─▶ event run with one research step
              ResearchRunner: pick ticket ─▶ cap checks ─▶ doer skill.step(gateway, ticket)
              gateway part = research, payer = raiser, ticket = id ─▶ activity row
              end ─▶ tickets status + research_done event
```

**Token split** (`desk/budget.py`, `desk/recorder.py`, `desk/gateway.py`).

```
JobSpec.tokens_per_day: int = 60_000 (ge 1_000)        # core/desk_employee.py, optional field
SHARES = {"plan": 0.5, "market": 0.2, "research": 0.3}
MARKET_KINDS = ("market_checkin", "watch_flag")
Part(name, payer, payer_name, tokens_per_day, ticket=None, ticket_cap=None)   # frozen
part_cap(part) = int(part.tokens_per_day * SHARES[part.name])
activity + columns part TEXT, payer TEXT, ticket INTEGER            # added on open (_ADDED)
Recorder.part_tokens(day, payer, part)   SUM(tokens_in + tokens_out) where COALESCE(payer, employee) = payer
                                         and COALESCE(part, 'plan') = part, live tries only
Recorder.ticket_tokens(ticket), Recorder.ticket_seconds(ticket)
Budget.refusal(..., part) adds, after the old checks:
    part_tokens(day, payer, part) >= part_cap      -> "<payer_name> <part> tokens for today used up"
    ticket and ticket_tokens(ticket) >= ticket_cap -> "ticket <id> reached its cap of <n> tokens"
```

`EmployeesStep._wake` builds `Part("market" if event.kind in MARKET_KINDS else "plan", spec.id, spec.name, spec.tokens_per_day)`. The gateway takes `part` (default: plan of its own employee), passes it to the budget and writes `part`, `payer` and `ticket` on every `Attempt`. A refusal for a used-up part is logged as `[Budget] <name>: <part> tokens for today used up (<used> of <cap>)` (SRD-DSK-004.010); the old caps of SRD-DSK-004.003/.004 are checked first, as now. Old rows without `part` count as plan.

**Tables** (`core/desk_research.py`, made on open):

```
tickets(id INTEGER PK AUTOINCREMENT, kind, topic, goal, done_test, token_cap INTEGER,
        step_cap INTEGER DEFAULT 8, time_cap_min INTEGER DEFAULT 60, raised_by, raised_by_name,
        status, made, approved_by NULL, approved NULL, started NULL, ended NULL,
        tokens INTEGER DEFAULT 0, steps INTEGER DEFAULT 0, biggest INTEGER DEFAULT 0,
        quiet_steps INTEGER DEFAULT 0, last_call TEXT DEFAULT '', state TEXT DEFAULT '{}',
        result TEXT DEFAULT '', end_reason TEXT DEFAULT '', gain INTEGER NULL, updated)
ticket_edits(id INTEGER PK AUTOINCREMENT, ticket_id, action 'approve'|'reject'|'cap',
             token_cap INTEGER NULL, made, applied NULL)
STATUSES = waiting, approved, running, paused, done, failed, stuck, rejected, expired
KINDS = setup_tuning, post_mortem, stock_study, sentiment, book_to_strategy, strategy_test
AUTO_CAP = 10_000; CAP_RANGE = 1_000..100_000; PER_DAY = 3; WAIT_DAYS = 3; REPEAT_DAYS = 30
PARK_AFTER = 3; PARK_DAYS = 30; QUIET = 20 minutes
```

**Raising** (`raise_tickets(home, skill_key, asks, now) -> list[str]`, one note per ask):

```
raiser = active employee file with skill = skill_key; none or level != lead -> refuse all
for ask in asks[:3]:
    kind not in KINDS                       -> "unknown kind"            (SRD-MKT-014.002)
    token_cap outside CAP_RANGE             -> "cap out of range"        (SRD-MKT-014.003)
    tickets made by raiser today (ET) >= 3  -> "3 tickets a day"         (SRD-DSK-010.002)
    same kind + goal (lower case, spaces squeezed) open, or done in 30 days -> "repeat"  (.006)
    topic parked: >= 3 tickets on the topic ended done|failed|stuck with gain = 0,
                  the last of them in the last 30 days                -> "topic parked" (.007)
    insert; cap <= 10_000 and kind != book_to_strategy -> approved by 'auto'            (.003)
            else waiting + raise_alert('ticket_waiting', source=str(id), detail=goal + cap)
    log "[Research] <name> raised ticket <id> (<kind>, <cap> tokens): approved|waiting|refused: <why>"
```

`TicketAsk` (pydantic, `extra="forbid"`): `kind: str (<= 30)`, `topic: str (3–60)`, `goal: str (10–300)`, `done_test: str (10–300)`, `token_cap: int`. The fields are plain, so a bad kind or cap only drops that ticket and never makes the whole answer invalid.

**Research block** (`with_research(text, home, skill_key, now) -> str`). For the active employee holding `skill_key` (from the employee files), it appends: research tokens used and left today (from `activity` and the holder's `tokens_per_day`), the open tickets (id, kind, goal, status), and the worked tickets (done, failed, stuck) of the last 30 days (goal, status, gain yes, no or not known, first 150 characters of the result). It closes with the ticket rules: at most 3, kinds, cap range, auto approval up to 10,000, book tickets wait. The block is cut to 2,400 characters (about 600 tokens). It returns `text` unchanged when there is no holder or no `desk.db`.

**Edits and expiry** (desk tick, `desk/process.py`):
- `apply_ticket_edits(home, now)` applies each unapplied edit to a waiting ticket. `approve` → approved by `master` (a given cap replaces the old one), `reject` → rejected and ended, `cap` → new cap, still waiting. An edit on a ticket that is no longer waiting is marked applied with no change.
- `expire_waiting(home, now)` sets waiting tickets older than 3 days to expired.
- `pause_running(home, why, now)` runs once in `DeskProcess.start`, with why "app closed" (SRD-DSK-010.012).

**Alert** (`core/desk_alerts.py`). Kind `ticket_waiting` is titled "Research ticket waiting", with the fix text "Approve or reject it in AI Desk → Research." Its source is the ticket id, so there is one alert per ticket. `_fixed` closes it once that ticket's status is no longer waiting (SRD-DSK-007.010).

**Event** (`core/desk_events.py`): `research_done` is P2, with no deadline and a 1-day expiry, keyed per ticket id (added to `_PER_ID`). Nobody listens to it yet, so the router closes it as "nobody listens". Step F may use it.

**Research skill contract** (`core/desk_research.py`):

```
class ResearchSkill(Skill, Protocol):
    kinds: tuple[str, ...]          # ticket kinds it can work
    step_tokens: int                # tokens one step is expected to use
    def step(self, ctx: AgentContext, ticket: Ticket) -> StepResult | None: ...
StepResult(note: str, call: str, outcome: 'go' | 'done' | 'failed', gain: bool | None, state: dict)
```

`note` is the new finding of the step ("" means nothing new), and `call` is a short text of the tool call the step made. None ship in step E.

**Runner** (`desk/research.py`, `ResearchRunner`, built from the same loaders as `EmployeesStep`).

```
quiet(home, now):  no waiting event (due or not) and no watch_flags row created in the last 20 min
has_work(home, now): quiet and a ticket in running | paused | approved whose payer has research
                     tokens left today; otherwise a running ticket is paused ("market work")
__call__(ctx):     one step of the next ticket: running, then paused, then approved (oldest)
    doer = active hire whose skill is a ResearchSkill with ticket.kind in kinds
        none -> stays approved; "[Research] No employee can work <kind> tickets yet", once a day
    need = max(skill.step_tokens, ticket.biggest)
    token_cap - tokens < need       -> end done "token cap"        (R2, SRD-DSK-010.010)
    steps >= step_cap               -> end done "step cap"
    ticket_seconds >= time_cap_min  -> end done "time cap"
    status running (started set on the first step); gateway(part=research, payer=raised_by,
        ticket=id, ticket_cap=token_cap); result = skill.step(gateway, ticket)
    gateway.refused                 -> ticket cap: end done "token cap"; else paused with the
                                       reason and no research for 15 minutes
    tokens = ticket_tokens(id); biggest = max(biggest, step tokens); steps += 1; state saved
    result None or note ""          -> quiet_steps += 1, else 0 and note added to result
    quiet_steps >= 2 or (call and call == last_call) -> end stuck   (R5, SRD-DSK-010.011)
    outcome done | failed           -> end with that status and gain  (R4)
end(ticket, status, reason): ended, end_reason, gain; post research_done (ticket id); log
```

**After code review (step E).** `raise_tickets` and `with_research` catch every error and log it, so a queue problem never loses the lead's answer or facts. The runner's step catches every error, logs it and waits 15 minutes, so the desk never goes to Error for research. A pause for a used-up part pauses only that ticket. A ticket ended at a cap has gain not known and never counts towards parking a topic.

The desk loop (`_event_tick`) runs the runner only when `has_work` from events is false. Market work always comes first, and research runs one step per tick, so a new flag or plan event pauses research after the current step (R7, SRD-DSK-010.012). The research step runs inside a normal `event` run, so run kinds do not change (SRD-DSK-003.013). The runner lives in `desk`, so `desk/cli.py` builds it with the same events loaders and passes `research=` to `DeskProcess`.

**Logs** (`[Research]`): raised (with result), approved (auto or Master), rejected, expired, started, paused (why), ended (status, reason, tokens). Approve, reject and cap from the app are logged by the GUI (SRD-GUI-039.005).

**Lead skills** (`market/lead_brief.py`, `market/checkin_note.py`). Each skill gets `tickets: list[TicketAsk] = Field(default_factory=list, max_length=3)` in its answer. `facts` wraps the text with `with_research(..., KEY, now)` after `with_lessons`. `act` calls `raise_tickets(ctx.home, KEY, answer.tickets, now)` when the list is not empty. The skills never start research work (SRD-MKT-014.005).

**GUI** (`gui/ai_desk_research.py`, `ResearchView`, section "Research" in the TEAM group after "Team at work", and in `_LIVE_SECTIONS`).
- Top line: each active lead's research tokens used and left today (`lead_research(home, day)`).
- Table with columns Status, Kind, Goal, Cap, Spent, Raised by, Made, in the order waiting, running and paused, approved, then ended in the last 7 days (`ticket_rows(home, now)`). A ticket with an unapplied edit shows "applies at the next desk tick".
- Buttons Approve, Reject and Change cap, enabled only for a waiting ticket. Change cap asks for a number from 1,000 to 100,000. Each button writes one `add_ticket_edit()` row and logs `[Research] Ticket <id> approved|rejected|cap set to <n> from the app`.
- The detail label under the table shows, for the selected ticket, its done test and, once ended, its result and end reason.
- The GUI reads `desk.db` read-only and writes only `ticket_edits`. The AI Desk is the Master user's view, as for Memory.

## DD-DSK-010.015.D01 — Follow-up Tickets from Research Skills (Autonomous desk step F)

**Traces:** SRD-DSK-010.015. `raise_follow_ups(home, lead_id, asks, now, send=None)` in `core/desk_research.py` looks up the employee file whose id is `lead_id` (the `raised_by` of the research ticket). Not an active lead → every ask is refused with "the raising lead is no longer an active lead". Otherwise each ask runs through `_raise_one()` exactly as in `raise_tickets()`, so limits, repeats, parked topics, auto approval and the waiting alert all count against that lead. Errors are logged and every ask is refused; the caller's work is never lost. Full use in DD-MKT-016.001.D01 §5.

## DD-DSK-010.016.D01 — Owner-Raised Strategy Test Ticket

**Traces:** SRD-DSK-010.016. `core/desk_research.raise_owner_test(home, card_id, now)` raises one `strategy_test` ticket for card `SC-<card_id>` in the name of the active lead that holds `lead_brief`, so the test uses that lead's research budget. It runs `_refusal()` (kind, cap, 3 a day, no repeat of an open or recent ticket), inserts the row as `approved` with `approved_by = "master"`, logs `[Research] Master raised ticket N (strategy test): approved` and returns `"ticket N approved"` or `"refused: <why>"`. No lead → `"refused: no active lead holds the lead plan"`. Full design: DD-MKT-019.001.D01.

## DD-DSK-011.001.D01 — Message Format `desk.msg/1` (AI Desk v3 M0)

**Traces:** SRD-DSK-011.001–.014. Source: schema draft 2, https://claude.ai/artifact/BjxpjycTC6CtGbNPzoX62f. All models live in `core/desk_msg.py` (Pydantic v2, every model `extra="forbid"`). M0 adds models only; storage (`messages`, `threads` tables) and the split into header columns and body JSON come in M1.

**Models.**

```
SCHEMA = "desk.msg/1"
State(str, Enum): submitted, working, input_required, completed, failed, canceled, refused, expired
MsgType = Literal[ask, task, reply, send_back, handover, escalate, meeting, decision, feedback]
Address = str, pattern  ^(skill:[a-z0-9_]+|champion:[a-z0-9_]+|boss|master|[A-Za-z0-9_-]+)$
                        (the last branch is the employee id pattern of core/desk_employee.py)

Thread:  id int>=1 · starter Address · msgs int>=1 · rounds int>=0 · state open|closed
         · opened AwareDatetime · closed AwareDatetime | None
Want:    goal str<=120 · done_when str<=120 · inputs dict · schema SchemaId? · cols list[str]?
         · tools list[ToolRef]? · max_tokens int>=0 = 0
Verdict: result str · reason str<=200? · agreed list[Address]? · disagreed list[Address]?
Data:    schema SchemaId · cols list[str]? · rows list[list[Any]] (<=200)? · nulls dict[str,str]?
         · ref str? · n int>=1?        exactly one of rows / ref; n required with ref, only with ref
Flag:    about str<=40 · note str<=120
Meta:    ai {tok int>=0, model str}? · used list[ToolRef]? · secs float>0? · blocked str? · schema str?
         (schema must match ^desk\.msg/\d+$ and differ from SCHEMA)
```

`SchemaId` and `ToolRef` patterns come from `core/desk_registry.py` (one rule for both modules).

**Body by type** (each a model with `type: Literal[...]`; `Body` is their union with `Field(discriminator="type")`):

| type | Required | Optional | Verdict results |
|---|---|---|---|
| ask | subject | text, about, want | — |
| task | card, want | — | — |
| reply | verdict; text or data unless refused | text, data, flags | done, partial, failed, dropped, refused (refused needs reason) |
| send_back | verdict | text | fix, reject |
| handover | subject; text or data | text, data, about, flags | — |
| escalate | subject, text | about, flags | — |
| meeting | subject, text | — | — |
| decision | subject, verdict | — | decided; agreed and disagreed allowed only here |
| feedback | subject, text | data | — |

Limits (SRD-DSK-011.007): subject 1–80 chars, no newline; text 1–600; about at most 20 items; flags at most 5. `want.tools` is refused on every body except task (SRD-DSK-011.008): ask's validator checks it.

**Envelope.** `Message`: `id int>=1 · thread int>=1 · parent int? · sender Address · to Address | list[Address] | None · at AwareDatetime · due AwareDatetime? · state State · body Body · meta Meta?`. The header field `type` is `body.type` (property), so type is written once. Envelope checks, first failure wins:

```
to is a list            -> only when type is meeting
to missing              -> only when type is reply or send_back (code takes the parent's sender in M1)
to set                  -> refused on reply and send_back
due set                 -> only on ask, task, send_back, escalate, meeting
parent missing          -> refused on reply, send_back and decision
```

**JSON.** `dump(msg) -> dict` is `model_dump(mode="json", exclude_none=True, exclude_defaults=True)`, then `type` added back on the body (it is the discriminator, so it is never a default). `load(data) -> Message` is `Message.model_validate(data)`. So empty and default keys are never written (SRD-DSK-011.011) and dump → load gives an equal model. A `ValidationError` is turned into one plain line by `reason(exc)`: the first error's field path and message.

**JSON Schema.** `message_schema() -> dict` returns `Message.model_json_schema()`; `body_schema(type) -> dict` returns the schema of one body model, for prompts (SRD-DSK-011.013).

**No behaviour change** (SRD-DSK-011.014): no desk, market or GUI module imports `desk_msg` in M0.

## DD-DSK-012.001.D01 — Tool Registry and Schema Library (AI Desk v3 M0)

**Traces:** SRD-DSK-012.001–.011. `core/desk_registry.py` (Pydantic v2, `extra="forbid"`); no `desk`, `market` or `gui` import at module level. Seed sources are read through import paths, the same way `core/desk_steps.py` loads steps.

**Names** (SRD-DSK-012.002):

```
TOOL_NAME  ^(?:[a-z0-9_]+\.[a-z0-9_]+|mcp:[a-z0-9_]+/[a-z0-9_]+)$      step.regime · mcp:backtest/bt_run
TOOL_REF   TOOL_NAME + @<int>                                       step.regime@1
SCHEMA_ID  ^[a-z0-9_]+\.v[0-9]+$                                    scores.v1
```

**Models.**

```
Tool (desk.tool/1):   name TOOL_NAME · kind code|mcp · version int>=1 · description str<=300
                      · input_schema (alias inputSchema) dict · output_schema (alias outputSchema)
                        dict | SCHEMA_ID | None · ai bool · status active|off
                      check: kind mcp <=> name starts "mcp:"
Column:               name [a-z0-9_]+ · type text|number · meaning str<=120
TableFormat (desk.schema/1): id SCHEMA_ID · title str · columns list[Column] (>=1, unique names)
                      properties name, version from id
```

Models dump with `by_alias=True`, so a tool row has the MCP field names `inputSchema` and `outputSchema`.

**Tables** in `desk.db` (SRD-DSK-012.004), made with `CREATE TABLE IF NOT EXISTS` by `_connect(home)`:

```
tools   (name TEXT, version INTEGER, kind TEXT, status TEXT, body TEXT, updated TEXT,
         PRIMARY KEY (name, version))
schemas (name TEXT, version INTEGER, body TEXT, updated TEXT, PRIMARY KEY (name, version))
```

`body` is the model's JSON; the other columns are copies for filtering. Times are `utc_text()`.

**Seed** (`seed_tools()` and `seed_formats()`, pure, no database):

| Source | Tool rows | Detail |
|---|---|---|
| `STEP_PATHS` | `step.<key>`, code, ai false | key = class name without `Step`, in snake case (`CandleCheckStep` → `candle_check`); description = the class `name` attribute; input `{"type": "object", "properties": {}}`; no output |
| `SKILL_PATHS` keys that are in research `KINDS` | `research.<kind>`, code kind, ai true | description = first docstring line of the skill class; input = `TicketAsk` JSON Schema |
| recipe `MENU` | `data.recipe`, code, ai false | input = `DataRecipe` JSON Schema; description from `DataRecipe` |
| recipe `MENU` | formats `<source>.v1` | title = source label; columns in menu order with their text or number type; meaning = column name in words |
| `us_swing.mcp.backtest_tools` `TOOL_NAMES` | `mcp:backtest/<tool>`, mcp, ai false | input from `func_metadata(BacktestTools.<tool>, skip_names=["self"]).arg_model.model_json_schema()` (the MCP server's own schema builder); description = first docstring line |

All seed rows are version 1, status active. The short server name `backtest` is used, as in the design page.

**Fill** (SRD-DSK-012.009). `fill_registry(home, now) -> tuple[int, int]` in one transaction:

```
for each seed tool:   INSERT ... ON CONFLICT(name, version) DO UPDATE kind, status='active', body, updated
for each seed format: same on schemas
UPDATE tools SET status='off', body=<body with status off> WHERE status='active' AND (name, version) not in seed
log.info("[Tools] Registry ready: %d tool(s), %d table format(s)", tools, formats)   (SRD-DSK-012.011)
return counts
```

A second fill gives the same rows (only `updated` moves). Rows are never deleted.

**Read** (SRD-DSK-012.010): `list_tools(home, status=None) -> list[Tool]` ordered by name; `get_tool(home, name, version=None) -> Tool | None` (newest version when none is given); `list_formats(home) -> list[TableFormat]`; `get_format(home, schema_id) -> TableFormat | None`. Read functions on a missing `desk.db` return empty results without making the file.

**Desk start.** `DeskProcess.start()` calls `fill_registry(self._home, now)` after `pause_running`, inside `try/except Exception` with `log.exception("[Tools] Could not fill the tool registry")`, so a registry problem never stops the desk. Nothing else reads the registry in M0.

## DD-DSK-011.015.D01 — Messages and the Reply Path (AI Desk v3 M1)

**Traces:** SRD-DSK-011.003, .004, .014–.032 (DSK); MKT and GUI parts in DD-MKT-005.019.D01 and DD-GUI-035.015.D01. User decisions 2026-11-13: the router stays serial; wake by message, no new run order; send back before the code veto; new rows rather than reopened FO-DSK-003 rows. Design page: https://claude.ai/artifact/8QdHMR5XoScLNN9HEtbB3A.

**1. Format change (M0 rows .003/.004).** In `core/desk_msg.py` the parent rule becomes: reply and decision need a parent; a send_back has either a parent (and no `to`) or a `to` (and no parent, so it starts a thread); `to` is left out only on reply and on a send_back with a parent. New model `Draft` (what an agent writes): `type`, `to?`, `parent?`, `subject?`, `text?`, `about?`, `want?`, `verdict?`, `data?`, `flags?`, all `extra="forbid"`. `with_messages(schema)` returns a cached subclass of `schema` with `messages: list[Draft] = Field(default_factory=list, max_length=5)` and a field description that names the M1 types and the inbox rule. `InboxReply` is a model with only `messages` (1–5), for a wake that only has to answer.

**2. Tables** (`core/desk_messages.py`, made by `_connect(home)` with `CREATE TABLE IF NOT EXISTS`):

```
messages (id INTEGER PRIMARY KEY, thread INTEGER, parent INTEGER, type TEXT, sender TEXT,
          receiver TEXT, at TEXT, due TEXT, state TEXT, body TEXT, meta TEXT, seen TEXT,
          data_day TEXT)
threads  (id INTEGER PRIMARY KEY, starter TEXT, msgs INTEGER, rounds INTEGER, state TEXT,
          opened TEXT, closed TEXT)
```

`body` is the body JSON without `type` (type is the column, written once); `receiver` is the resolved employee id; `seen` is set when the receiver's wake has shown the row in its inbox. A stored row reads back as `desk_msg.Message` (`to` = receiver for ask and a first send_back).

**3. Accept** — `accept(home, drafts, sender, roster, now, data_day) -> list[str]` (one result line per draft), called by the employees step after `skill.act()` when the gateway holds drafts. `roster` is the list of `(id, skill key, level)` of active employees. Each draft, in order, first failure refuses it alone (SRD-DSK-011.019):

```
1 format     body = draft minus type/to/parent, parse_body({type, **body}); Message model check
2 type       type not in {ask, reply, send_back}      -> "type <t> is not in use yet"
3 receiver   ask / first send_back: to = employee id (active) or skill:<key> (active holder,
             lowest id);  reply / send_back with parent: receiver = parent's sender
             other forms or nobody                     -> "nobody can take <to>"
4 guardrails reply: parent open (submitted), addressed to sender, no reply yet   (.021)
             thread msgs < 6; send_back rounds < 2; sender started < 20 today  (.020)
             no loop: receiver has an open ask/send_back in this thread to sender (.022)
5 data       data.schema must be a format in the registry (get_format)         
6 store      insert row (state submitted, due = now + 10 min for ask/send_back) and thread
             row/counts; a reply sets the parent state completed | failed | refused by verdict
             (done/partial -> completed, failed/dropped -> failed, refused -> refused);
             post_message(con, id, receiver, data_day, now)                  (.024, .027)
log  [Messages] Emp 3 asked Emp 6 (thread 101)   |   [Messages] A message from Emp 3 was refused: <why>
```

"Started" means the first message of a thread (`parent IS NULL`) by that sender on that New York day.

**4. Event.** `core/desk_events.py` gets `EVENT_RULES["message"] = EventRule(1, timedelta(minutes=10), timedelta(hours=2))`, a new `target` column (added like `parent` and `due`), `Event.target`, and `post_message(con, message_id, receiver, data_day, now)` with key `message|<id>`.

**5. Router** (`desk/router.py`).

```
_listeners(event): message -> [hire whose id == event.target]; others as today
_handle_one(event): message -> result = wake(hire, event, False, ()); then _release(con); note
_try: a message event skips _too_soon (SRD-DSK-011.025)
after a chain step ends ok:  open_started(home, emp) -> write step "waiting", no step_done (.029)
_advance: a "waiting" step is not settled and is not woken again
handle(): at the start and after every event -> expire_due(home, now) and _release(con)
_release(con): every "waiting" step whose employee has no open started message ->
               _end(con, trigger, hire, tries, "ok")  (posts its step_done; the chain goes on)
```

`Recorder.last_wake` ignores rows with a `message` id, so a message turn never makes the 30-minute gap block the employee's own chain wake.

**6. Wake for a message** (`desk/employees_step.py`, kind `message`):

```
msgs  = inbox(home, emp)                        # receiver == emp and seen IS NULL
facts = skill.facts(home); not fresh -> refuse_inbox(home, msgs, why_stale, now); "slept"
facts = replace(facts, text = facts.text + inbox_text(msgs, names), inbox = ids)   (.026)
part  = Part("plan" or "market", starter id, starter name, starter tokens_per_day,
             message=<event message id>)                                       (.030)
gateway(talk = messages_on and skill.talks); items = skill.act(gateway, facts)
accept(home, gateway.drafts, emp, ...); mark_seen(msgs)
asked and nothing answered -> refuse_inbox(msgs, gateway.refused or "no valid answer"); "failed"
gateway.refused          -> refuse_inbox(msgs, reason); "slept"
else "ok"     (a code-only turn with no ask is ok)
```

`refuse_inbox` writes, for each open ask or send_back in `msgs`, a reply row by code in the receiver's name with verdict refused and the reason, and wakes the asker (SRD-DSK-011.028). `expire_due(home, now)` does the same for open rows past `due`, with verdict failed, reason "no reply within 10 minutes" and the parent set to expired (SRD-DSK-011.023). A normal chain wake also runs `accept` after `act`.

**7. Inbox block** (SRD-DSK-011.026), one block per row, ids plus current names from the roster:

```
INBOX — answer only what is asked here; leave your other work as it is.
#101 ask from emp-003 (Expert 3, setup review), about NVDA:
  Any earnings date or big news in the next 5 days?
  Reply with a message of type reply and parent 101.
#202 reply from emp-003 to your #201: done
  data idea_fix.v1: long AMD trigger 158.2 stop 146.0
```

**8. Gateway and skills.** `Gateway(talk: bool = False)`: `ask()` sends `with_messages(schema)` when talk is on and the schema has no `messages` field yet, and puts the answer's messages into `self.drafts`; `send(draft)` adds a code-written draft. A skill opts in with `talks = True`; `core/desk_agents.talker(ctx)` returns the context when it has `talk` and `drafts` and talk is on, else `None` (test fakes and replays stay as they are). `Facts` gains `inbox: tuple[int, ...] = ()`.

**9. Settings** (SRD-DSK-011.031). `DeskAiSettings.messages_on: bool = False`. Off: no gateway is built with talk, no `messages` field reaches any prompt, the employees step never calls `accept`, and the router never sees a `message` event, so the run is as today.

**10. Reads for the GUI.** `thread_rows(home, day)` (threads of a day, newest first, with tokens summed from `activity.message` of their messages) and `messages_of(home, thread)`; read-only, empty without a database.

**11. Registry.** Format `idea_fix.v1` (side, symbol, trigger, stop) is added to the seed formats, so step 5 accepts a fix reply.

**After code review (M1).** A message wake marks its inbox seen in a `finally`, and an error refuses the open asks at once, so no step stays waiting. `inbox()` leaves out asks and send-backs that are no longer open. With messages off, a message wake refuses its open asks with "agent messages are off". `open_started()` is also true while a reply to the employee is not yet read, so its turn ends only after it has seen the reply. Risk check sends one send-back per idea and data day (`sent_on()`), and a fix with levels that are not numbers is recorded as not fixed. A normal wake with no model call now ends `ok` (user, 2026-11-13): an all-vetoed day no longer counts as failed, retries or alerts.

**Desk-copy check (2026-11-13).** On a copy of the real desk with real model calls, the setup review wrote good fix replies but left out `verdict`. `accept()` now fills a missing reply verdict before the checks: a reply to a send-back without data becomes dropped with its text as the reason; any other reply becomes done. A reply written by code (refused or expired) also carries its reason as `text`, so it reads back as a valid `desk.msg/1` reply.

## DD-DSK-011.033.D01 — Escalation and Deputies (AI Desk v3 M2)

**Traces:** SRD-DSK-011.014, .024, .033–.043, SRD-DSK-007.011, SRD-DSK-008.010 (DSK); MKT part in DD-MKT-013.013.D01, GUI part in DD-GUI-034.071.D01. User decisions 2026-11-13: watch flag alerts at once and also escalates; 5 minutes per level; escalate free of the 20-a-day cap; boss answers in a reply-only turn; the reply is a note only; handover waits for M5.

**1. Roster.** `desk_messages.Person` gains `boss: str | None = None` (from `reports_to`) and `deputy: str | None = None`. The employees step builds it from active hires; the router gets the same roster.

**2. Accept** — `accept(..., escalation: bool = False)`. The employees step passes `messages_on and escalation_on`.

```
type escalate, escalation off -> dropped quietly (debug log), not refused
type escalate, escalation on  -> allowed (handover and the rest still "not in use yet")
to "boss"     -> sender's Person.boss when that boss is in the roster          (.034)
               no boss -> row stored with receiver "master", state input_required,
                          and the alert of 007.011 is raised after the commit
guardrails    -> escalate skips the 20-started-a-day count (.038); 6 per thread holds
store         -> escalate: state submitted, due = now + 5 min                   (.036)
event         -> post_message(priority = 0 for escalate, else 1)                (.035)
```

**3. Replies to an escalate** (.040). A reply may answer an open ask, send_back or escalate (`_OPEN`). A reply whose parent is an escalate (by AI or by code) is stored with `seen` set at once and posts no event: the sender is not woken. `open_started` still counts only ask and send_back, so an escalate never holds the sender's step.

**4. Move up** — `expire_due(home, now, roster=(), send=None)` (.036, .037). For each submitted escalate past `due`:

```
next = boss of the current receiver (Person.boss), in roster, not the sender
thread msgs < 6 and next  -> receiver = next, due = now + 5 min, seen = NULL,
                             meta.blocked += "<name> did not answer in 5 minutes",
                             threads.msgs + 1, post_message(again=next)
else                      -> state input_required, receiver master, meta.blocked as above,
                             raise_alert("escalation", source=<thread id>, ...)      (007.011)
log  [Messages] Escalation from Expert 9 moved up to Lead 2 | ... reached the Master user
```

Other submitted rows past `due` expire as in M1.

**5. Deputy** — `hand_to_deputy(home, rows, person, roster, why, now) -> list[MessageRow]` (.041). It returns the rows it could not hand:

```
for each submitted ask / send_back / escalate in rows:
  person.deputy in roster, != person.id, row.handed is NULL
      -> receiver = deputy, handed = person.id, seen = NULL,
         meta.blocked += "<name> could not work: <why>; sent to deputy <deputy name>",
         post_message(again=deputy)
  else keep it for refuse_inbox
```

The new `messages.handed` column (added by `ALTER TABLE` when missing) makes a row move to a deputy only once, so a deputy's own deputy is never followed. `mark_seen(..., receiver=emp)` marks only rows still addressed to `emp`, so a handed row stays unseen for the deputy.

**6. Wake** (`desk/employees_step.py`). `_answer_inbox` splits the inbox. With escalation on, escalates go to `_answer_escalations` and the rest to the M1 path. Each M1 `refuse_inbox` call for sleep, budget, error or no valid answer becomes `_refuse()`: it calls `hand_to_deputy` first when escalation is on, then refuses what is left. "Messages off" still refuses at once.

```
_answer_escalations(rows):                                            (.039)
  text  = "Problems raised to you by people who report to you. Reply to each; your
           reply is shown to the Master user as a note.\n" + inbox_text(rows)
  gateway(talk off, part of the thread starter)  -> ask(text, InboxReply)
  drafts = replies only; accept(..., escalation=True)
  for each stored reply -> FeedItem("info", "<subject>: <reply text or verdict>")  (.040)
  no answer -> _refuse(rows, why)
```

The boss's own skill and its facts are not used.

**7. Events** (`core/desk_events.py`). `post_message(..., priority: int | None = None, again: str = "")`: the priority defaults to the rule's 1, and `again` adds `|<again>` to the key so a moved or handed row can post a new event.

**8. Alerts** (`core/desk_alerts.py`). New kind `escalation` ("Escalation not answered"; fix: "Read the thread in AI Desk → Team at work → Threads"). It stays open for the day like the market alerts, because a thread that passed the top boss can take no more replies. This differs from the SRD constraint "closed when the thread gets a reply" and is flagged to the user.

**9. Employee file** (`core/desk_employee.py`, SRD-DSK-008.010). `JobSpec.deputy: str | None = None`. `render` leaves `deputy` out when it is `None`, so old files stay the same. `save_employee` refuses "the deputy cannot be the employee itself" and "no employee <id> for deputy".

**10. Settings.** `DeskAiSettings.escalation_on: bool = False` (.042). With it off: escalate drafts are dropped, no deputy hand happens, and there are no escalate rows to move, so the run is as in M1.
