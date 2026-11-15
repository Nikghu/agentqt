"""
Module: MD-DSK-013.003.M40 — desk/tool_builder.py
Parent SRD: SRD-DSK-013.003
Also: SRD-DSK-013.002 (chat asks become requests), .004 (facts), .005 (answer or refusal), .008
(one fix round), .014 (checks on sample stocks), .015 (states), .016 (one reply per chat
request), .021 (switch), .024 (log lines)

The tool builder skill (AI Desk v3 M7b). For each new request it asks the model once for one
small Python tool, saves the answer as a new version, checks the code against the rules and
runs it in the sandbox on sample stocks; a problem gets one more AI call with the problems. A
version that passes all 5 checks waits for the Master user's review: this skill never enables a
tool. A chat request gets one reply with the result. Design: DD-DSK-013.001.D01.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path

from us_swing.core.desk_agents import AgentContext, Facts, FeedItem, Talker, talker
from us_swing.core.desk_ai_settings import load_settings
from us_swing.core.desk_built_tools import (
    ALLOWED_ATTRS,
    ALLOWED_BUILTINS,
    CHANGED,
    CHECKS,
    MADE_UP,
    MAX_CODE,
    MAX_LINES,
    MAX_REQUEST,
    OFF,
    REVIEW,
    SAMPLES,
    STATS_NAMES,
    BuiltTool,
    Check,
    ToolAnswer,
    ToolRequest,
    add_request,
    built_tool_rows,
    check_answer,
    check_code,
    checked_code,
    expire_requests,
    get_built,
    new_requests,
    sample_symbols,
    save_version,
    set_checks,
    set_request,
    stale_requests,
    taken_names,
)
from us_swing.core.desk_hiring import employees
from us_swing.core.desk_messages import inbox, read_message
from us_swing.core.desk_msg import AskBody, Draft, Verdict
from us_swing.core.desk_recipes import MENU
from us_swing.core.desk_research import holder
from us_swing.desk.recorder import ny_now
from us_swing.desk.sandbox import RunResult, run_code
from us_swing.desk.sandbox_child import NO_MEMORY

log = logging.getLogger(__name__)

KEY = "tool_builder"
MAX_CALLS = 2
NOTHING = "no tool request"
NO_ANSWER = "the model gave no answer"
ERROR = "the builder hit an error"
NOT_RUN = "not run"
MAX_LINE = 160
Runner = Callable[..., RunResult]
_HOW = ("Write one small Python tool. The desk calls tool(symbol) once per stock; it returns "
        "{<column>: <value>, ...}: a number or a short text for each of your columns.")
_READS = (
    "- daily_bars(symbol, days=260) -> [{\"day\", \"open\", \"high\", \"low\", \"close\", "
    "\"volume\"}], oldest first, up to 1300 days",
    "- intraday_bars(symbol, minutes=30, days=10) -> [{\"time\", \"open\", \"high\", \"low\", "
    "\"close\", \"volume\"}], minutes 15 or 30, up to 60 days, New York times",
    "- desk_rows(source, symbol=None, days=1) -> [{\"date\", <columns>}], oldest first, up to "
    "60 data days; sectors takes no symbol, the other sources need one:")
_RULES = (
    "- One top-level def tool(symbol); at the top only def statements, constants and a "
    "docstring.",
    f"- Use only these names: {', '.join(ALLOWED_BUILTINS)}, math, {', '.join(STATS_NAMES)} "
    "and the read functions.",
    f"- Use only these attribute names: {', '.join(sorted(ALLOWED_ATTRS))}.",
    "- No import, class, with, yield, global, nonlocal, match, async or decorators; no name or "
    "attribute that starts with _; no text that holds __.",
    f"- At most {MAX_CODE} characters and {MAX_LINES} lines.",
    "- raise ValueError(\"short reason\") when a stock lacks data; return None for one value you "
    "cannot work out.",
    "- A number is an int or a float; a text has at most 200 characters.")
_REFUSE = ("If the request cannot be built with these functions (for example it needs news or "
           "the internet), leave code empty and give the reason in refuse.")


def _name(home: Path, emp: str) -> str:
    if emp == "master":
        return "the Master user"
    return next((e.name for e in employees(home) if e.id == emp), emp)


def facts_text(home: Path, req: ToolRequest) -> str:
    """The request, the read functions, the code rules, the built tools and the taken format
    names; never a tool's code or a file path (SRD-DSK-013.004)."""
    lines = [f"Tool request #{req.id} from {_name(home, req.asker)}: {req.text}"]
    if req.symbols:
        lines.append(f"Sample stocks: {', '.join(req.symbols)}")
    lines += ["", _HOW, "Read functions (read-only; they return plain lists and dicts):",
              *_READS, *(f"  - {key}: {', '.join(src.columns)}" for key, src in MENU.items()),
              "Rules:", *_RULES, ""]
    built = built_tool_rows(home, 20)
    lines.append("Built tools:" + ("" if built else " none"))
    lines += [f"- {t.name} v{t.version} ({t.state}): {t.title}: "
              f"{', '.join(c.name for c in t.columns)}" for t in built]
    lines += [f"Taken format names: {', '.join(sorted(taken_names(home)))}", _REFUSE]
    return "\n".join(lines)


def _retry_text(base: str, problems: Sequence[str], code: str) -> str:
    lines = [base, "", "Your last answer had these problems:", *(f"- {p}" for p in problems)]
    if code:
        lines += ["", "Your last code:", code]
    return "\n".join(lines)


def _ask_text(body: AskBody) -> str:
    want = body.want
    request = want.inputs.get("request") if want is not None else None
    if isinstance(request, str) and request.strip():
        return request.strip()[:MAX_REQUEST]
    if want is not None and want.goal.strip():
        return want.goal.strip()[:MAX_REQUEST]
    return (body.text or body.subject).strip()[:MAX_REQUEST]


def _ask_symbols(body: AskBody) -> list[str]:
    found = body.want.inputs.get("symbols") if body.want is not None else None
    if not isinstance(found, list):
        return []
    return list(dict.fromkeys(s.strip().upper() for s in found
                              if isinstance(s, str) and s.strip()))[:SAMPLES]


def _cell(value: object) -> str:
    if value is None:
        return "-"
    return f"{value:g}" if isinstance(value, float) else str(value)


def _sample_lines(symbols: Sequence[str], result: RunResult, names: Sequence[str]) -> list[str]:
    rows = {str(r["symbol"]): r for r in result.rows}
    lines = []
    for symbol in symbols:
        row = rows.get(symbol)
        if row is not None:
            text = ", ".join(f"{n} {_cell(row.get(n))}" for n in names)
        else:
            text = result.missing.get(symbol) or result.error or "no value"
        lines.append(f"{symbol}: {text}"[:MAX_LINE])
    return lines


def run_checks(home: Path, tool: BuiltTool, given: Sequence[str], run: Runner = run_code,
               backtest: Path | None = None) -> tuple[list[Check], list[str]]:
    """Run a saved version on up to 5 sample stocks and one made-up stock; give the 5 checks
    and one sample line per stock (SRD-DSK-013.014)."""
    samples = sample_symbols(home, given)
    symbols = [*samples, MADE_UP]
    code = checked_code(home, tool)
    result = (RunResult(error=CHANGED) if code is None
              else run(home, code, tool.columns, symbols, backtest=backtest))
    names = [c.name for c in tool.columns]
    checks = [Check(check=CHECKS[0], ok=True), _time_check(result),
              *_result_checks(result, samples, names)]
    return checks, _sample_lines(symbols, result, names)


def _time_check(result: RunResult) -> Check:
    """Time and memory: the run ended, no stock was cut at the time limit and none ran out of
    memory."""
    if result.error:
        return Check(check=CHECKS[1], ok=False, note=result.error)
    if result.cut:
        return Check(check=CHECKS[1], ok=False,
                     note=f"{len(result.cut)} stock(s) not run: the time limit was reached")
    out = next((s for s, why in result.missing.items() if why == NO_MEMORY), "")
    return Check(check=CHECKS[1], ok=not out, note=f"{out}: {NO_MEMORY}" if out else "")


def _result_checks(result: RunResult, samples: Sequence[str],
                   names: Sequence[str]) -> list[Check]:
    """Full row, value types and no data; all "not run" when the run ended with an error."""
    if result.error:
        return [Check(check=c, ok=False, note=NOT_RUN) for c in CHECKS[2:]]
    full = any(r["symbol"] in samples and all(r.get(n) is not None for n in names)
               for r in result.rows)
    if full:
        row_note = ""
    else:
        row_note = "no stock got every column" if samples else "no sample stocks"
    wrong = f"{result.wrong[0].replace('.', ' ')}: wrong value" if result.wrong else ""
    crash = result.missing.get(MADE_UP, "") if MADE_UP in result.crashed else ""
    return [Check(check=CHECKS[2], ok=full, note=row_note),
            Check(check=CHECKS[3], ok=not wrong, note=wrong),
            Check(check=CHECKS[4], ok=not crash, note=f"{MADE_UP}: {crash}" if crash else "")]


def _reply(parent: int, state: str, reason: str, tool: BuiltTool | None) -> Draft:
    """The one reply to a chat request (SRD-DSK-013.016)."""
    if state == "done" and tool is not None:
        text = (f"Tool {tool.title} ({tool.name} v{tool.version}) is built and waits for the "
                f"Master's review in AI Desk → Tools: {tool.passed} of {len(CHECKS)} checks "
                "passed.")
        return Draft(type="reply", parent=parent, text=text[:600], verdict=Verdict(result="done"))
    result = "refused" if state == "refused" else "failed"
    return Draft(type="reply", parent=parent, text=reason[:600],
                 verdict=Verdict(result=result, reason=reason[:200] or None))


class ToolBuilderSkill:
    """Writes small tools the Master user asks for and checks them; never enables one."""

    key = KEY
    needs: tuple[str, ...] = ()
    answer = ToolAnswer
    talks = True

    def __init__(self, clock: Callable[[], datetime] = ny_now, run: Runner = run_code,
                 backtest: Path | None = None) -> None:
        """Set the clock, the sandbox runner and the Backtest Data folder; tests inject them."""
        self._clock = clock
        self._run = run
        self._backtest = backtest

    def facts(self, home: Path) -> Facts:
        """Fresh while the tool builder is on and a request or an ask waits (SRD-DSK-013.003).

        Off, the facts are not fresh, so the desk refuses each ask with the reason.
        """
        now = self._clock()
        day = now.date().isoformat()
        if not load_settings(home).tool_builder_on:
            return Facts("Tool builder", day, False, OFF)
        me = holder(home, KEY)
        asks = inbox(home, me.id) if me is not None else []
        waiting = new_requests(home, now)
        if not waiting and not asks and not stale_requests(home, now):
            return Facts("Tool builder", day, False, NOTHING)
        return Facts(f"Tool requests waiting: {len(waiting)}", day, True)

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        """Turn chat asks into requests, then build every new request, oldest first."""
        talk = talker(ctx)
        now = self._clock()
        for message_id in facts.inbox:
            msg = read_message(ctx.home, message_id)
            if msg is None or not isinstance(msg.body, AskBody):
                continue
            add_request(ctx.home, "chat", msg.id, msg.sender, _ask_text(msg.body),
                        _ask_symbols(msg.body), now)
        expire_requests(ctx.home, now)
        for req in new_requests(ctx.home, now):
            self._build(ctx, req, talk)
        return []

    def _build(self, ctx: AgentContext, req: ToolRequest, talk: Talker | None) -> None:
        home = ctx.home
        set_request(home, req.id, "building", "", self._clock())
        try:
            state, reason, tool = self._make(ctx, req, talk)
        except Exception:
            log.exception("[Tool builder] Request #%d hit an error", req.id)
            state, reason, tool = "failed", ERROR, None
        set_request(home, req.id, state, reason, self._clock(), tool.id if tool else None)
        if state == "done" and tool is not None:
            log.info("[Tool builder] Tool %s v%d waits for review: %d of %d checks passed",
                     tool.name, tool.version, tool.passed, len(CHECKS))
        else:
            log.info("[Tool builder] Request #%d %s: %s", req.id, state, reason)
        if req.message is not None and talk is not None:
            talk.send(_reply(req.message, state, reason, tool))

    def _ask(self, ctx: AgentContext, text: str, talk: Talker | None) -> ToolAnswer | None:
        """One AI call; messages the model adds are dropped (SRD-DSK-013.008)."""
        start = len(talk.drafts) if talk is not None else 0
        answer = ctx.ask(text, ToolAnswer)
        if talk is not None:
            del talk.drafts[start:]
        return answer

    def _make(self, ctx: AgentContext, req: ToolRequest,
              talk: Talker | None) -> tuple[str, str, BuiltTool | None]:
        """At most 2 AI calls: the answer, then one fix with the problems (SRD-DSK-013.008)."""
        home = ctx.home
        base = facts_text(home, req)
        text, last, problems = base, None, ["no usable answer"]
        for _ in range(MAX_CALLS):
            answer = self._ask(ctx, text, talk)
            if answer is None:
                return "failed", NO_ANSWER, last
            if answer.refuse.strip():
                return "refused", answer.refuse.strip(), last
            problems = check_answer(home, answer)
            if not problems:
                last, problems = self._version(home, req, answer)
                if last.state == REVIEW:
                    return "done", "", last
            text = _retry_text(base, problems, answer.code)
        return "failed", f"the tool failed its checks: {problems[0]}", last

    def _version(self, home: Path, req: ToolRequest,
                 answer: ToolAnswer) -> tuple[BuiltTool, list[str]]:
        """Save the answer as a version, check its code and run its checks; give the version
        and its problems (SRD-DSK-013.007, .009, .014, .015)."""
        tool = save_version(home, req.id, answer, self._clock())
        problems = check_code(answer.code)
        if problems:
            checks = [Check(check=CHECKS[0], ok=False, note=problems[0]),
                      *(Check(check=c, ok=False, note=NOT_RUN) for c in CHECKS[1:])]
            set_checks(home, tool.id, checks, [])
        else:
            checks, sample = run_checks(home, tool, req.symbols, self._run, self._backtest)
            set_checks(home, tool.id, checks, sample)
            problems = [f"{c.check}: {c.note}" for c in checks if not c.ok]
        saved = get_built(home, tool.id) or tool
        if saved.state != REVIEW:
            log.info("[Tool builder] Tool %s v%d failed its checks: %s", saved.name,
                     saved.version, problems[0] if problems else "")
        return saved, problems
