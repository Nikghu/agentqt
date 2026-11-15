"""
Module: MD-DSK-012.018.M34 — desk/planner.py
Parent SRD: SRD-DSK-012.018
Also: SRD-DSK-012.019 (refusals), .020 (unmade columns), .022 (wave 2 gets wave 1 keys),
.024 (merge and check), .025 (reply), .026 (failure rows), .027 (retire alert),
.028 (``task_cards_on``), .031 (log lines)

The task planner skill (AI Desk v3 M6). It answers each table ask in its inbox with exactly
one reply and never calls a model: it finds the saved plan of the asked format, writes a
task card, runs the plan's parts through the tool groups in two waves, merges the parts on
the key, checks every value against its column, and replies with the table and a reason for
every empty value. A refused ask and a failed part are kept in the failure log.
Design: DD-DSK-012.012.D01.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from us_swing.core import desk_steps
from us_swing.core.desk_agents import AgentContext, Facts, FeedItem, talker
from us_swing.core.desk_ai_settings import load_settings
from us_swing.core.desk_alerts import Sender, raise_alert
from us_swing.core.desk_hiring import employees
from us_swing.core.desk_memory import log_failure
from us_swing.core.desk_messages import read_message
from us_swing.core.desk_msg import AskBody, Data, Draft, Flag, InboxReply, Message, Verdict
from us_swing.core.desk_registry import TableFormat, get_format, list_tools
from us_swing.core.desk_research import holder
from us_swing.core.desk_tasks import (
    RETIRE_AFTER,
    RETIRED,
    CardPart,
    Plan,
    PlanPart,
    close_card,
    get_plan,
    group_label,
    note_result,
    open_card,
    ready_formats,
)
from us_swing.desk.champions import DEFAULT_SECS, FAILED, OK, SKIPPED, PartResult, run_wave
from us_swing.desk.recorder import ny_now

log = logging.getLogger(__name__)

KEY = "task_planner"
MAX_KEYS = 30
MAX_FLAGS = 5
OFF = "task cards are off"
NOT_AVAILABLE = "not available"
NO_KEYS = "no asked symbol has data"
ERROR = "the planner hit an error"
_Pairs = Sequence[tuple[PlanPart, PartResult]]


class _Refusal(Exception):
    """The ask cannot be worked; the text is the reason."""


@dataclass(frozen=True)
class _Ask:
    """A checked ask: its format, plan, wanted columns (key first) and keys."""

    fmt: TableFormat
    plan: Plan
    cols: list[str]
    keys: list[str]


def _name(home: Path, emp: str) -> str:
    return next((e.name for e in employees(home) if e.id == emp), emp)


def _symbols(value: object) -> list[str]:
    """Upper-cased symbols in the asked order, without blanks and repeats."""
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        return []
    out: list[str] = []
    for item in value:
        symbol = item.strip().upper()
        if symbol and symbol not in out:
            out.append(symbol)
    return out


def _check(home: Path, body: AskBody) -> _Ask:
    """The ask ready to work, or a ``_Refusal`` with the reason (SRD-DSK-012.019)."""
    want = body.want
    if want is None or want.schema_id is None:
        ready = ", ".join(f.id for f in ready_formats(home)) or "none"
        raise _Refusal(f"no table format named; ready formats: {ready}")
    fmt, plan = get_format(home, want.schema_id), get_plan(home, want.schema_id)
    if fmt is None or plan is None:
        raise _Refusal(f"no ready plan for {want.schema_id}")
    if plan.status == RETIRED:
        raise _Refusal(f"the plan for {fmt.id} is retired: {plan.why}")
    names = [c.name for c in fmt.columns]
    unknown = next((c for c in want.cols or [] if c not in names), None)
    if unknown is not None:
        raise _Refusal(f"unknown column {unknown} in {fmt.id}")
    cols = [n for n in names if n == fmt.key or want.cols is None or n in want.cols]
    keys = _symbols(want.inputs.get("symbols"))
    if not 1 <= len(keys) <= MAX_KEYS:
        raise _Refusal(f"give 1 to {MAX_KEYS} symbols in inputs.symbols")
    return _Ask(fmt, plan, cols, keys)


def _trim(part: PlanPart, cols: Sequence[str]) -> PlanPart | None:
    """The part with only the wanted columns; ``None`` when it fills none of them."""
    tools = {tool: kept for tool, made in part.tools.items()
             if (kept := [c for c in made if c in cols])}
    return part.model_copy(update={"tools": tools}) if tools else None


def _run_parts(home: Path, ask: _Ask) -> list[tuple[PlanPart, PartResult]]:
    """Wave 1 alone, then wave 2 together on the keys wave 1 returned (SRD-DSK-012.022)."""
    paths = {name: path for name, (path, _secs) in desk_steps.TOOL_PATHS.items()}
    limits = {t.name: t.secs or DEFAULT_SECS for t in list_tools(home, "active")}
    parts = [p for p in (_trim(part, ask.cols) for part in ask.plan.parts) if p is not None]
    first = [p for p in parts if p.wave == 1]
    rest = [p for p in parts if p.wave > 1]
    done = run_wave(home, first, ask.keys, paths, limits, ask.fmt.key)
    key_part = done[0]
    keys_ok = [k for k in ask.keys if k in key_part.rows] if key_part.status == OK else []
    if keys_ok:
        more = run_wave(home, rest, keys_ok, paths, limits, ask.fmt.key)
    else:
        why = NO_KEYS if key_part.status == OK else "the first part failed"
        more = [PartResult(p.id, SKIPPED, reason=why) for p in rest]
    return list(zip(first + rest, done + more, strict=True))


def _fits(value: object, kind: str) -> bool:
    if kind == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    return isinstance(value, str)


def _merge(ask: _Ask, pairs: _Pairs) -> tuple[list[list[Any]], dict[str, str], int]:
    """Rows in the asked order, a reason for every empty value, and the wrong-value count
    (SRD-DSK-012.020, .024)."""
    key_part = pairs[0][1]
    source = {col: (tool, result) for part, result in pairs
              for tool, made in part.tools.items() for col in made}
    kinds = {c.name: c.type for c in ask.fmt.columns}
    rows: list[list[Any]] = []
    nulls: dict[str, str] = {}
    wrong = 0
    for key in ask.keys:
        if key not in key_part.rows:
            nulls[key] = (key_part.reason if key_part.status != OK
                          else key_part.missing.get(f"{key}.{ask.fmt.key}", "")) or "no data"
            continue
        row: list[Any] = [key]
        for col in ask.cols[1:]:
            tool, result = source.get(col, ("", None))
            value = None
            if result is None:
                nulls[col] = NOT_AVAILABLE
            elif result.status != OK:
                nulls[col] = result.reason or "not run"
            else:
                value = result.rows.get(key, {}).get(col)
                if value is None:
                    nulls[f"{key}.{col}"] = result.missing.get(f"{key}.{col}") or "no value"
                elif not _fits(value, kinds[col]):
                    nulls[f"{key}.{col}"] = f"wrong value from {tool}"
                    wrong += 1
                    value = None
            row.append(value)
        rows.append(row)
    return rows, nulls, wrong


def _verdict(ask: _Ask, pairs: _Pairs, rows: int, nulls: dict[str, str],
             wrong: int) -> tuple[str, str]:
    """``done``, ``partial`` or ``failed`` with one short reason line (SRD-DSK-012.025)."""
    bits = [f"{group_label(part.group)} failed: {result.reason}"
            for part, result in pairs if result.status == FAILED]
    if not rows:
        why = next(iter(nulls.values()), "")
        return "failed", bits[0] if bits else f"{NO_KEYS}: {why}" if why else NO_KEYS
    lost = len(ask.keys) - rows
    if lost:
        bits.append(f"{lost} of {len(ask.keys)} symbols not found")
    if wrong:
        bits.append(f"{wrong} wrong value{'' if wrong == 1 else 's'} left empty")
    return ("partial" if bits else "done"), "; ".join(bits)


def _refused(parent: int, reason: str) -> Draft:
    return Draft(type="reply", parent=parent,
                 verdict=Verdict(result="refused", reason=reason[:200]))


def _failed(parent: int, reason: str) -> Draft:
    return Draft(type="reply", parent=parent, text=reason[:600],
                 verdict=Verdict(result="failed", reason=reason[:200]))


def _reply(parent: int, ask: _Ask, status: str, reason: str, rows: list[list[Any]],
           nulls: dict[str, str], pairs: _Pairs) -> Draft:
    if not rows:
        return _failed(parent, reason)
    verdict = Verdict(result=status, reason=reason[:200] or None)
    shown = {row[0] for row in rows}
    flags = [Flag(about=key[:40], note=note[:120]) for _part, result in pairs
             for key, note in result.flags.items() if key in shown and note][:MAX_FLAGS]
    subset = len(ask.cols) < len(ask.fmt.columns)
    data = Data.model_validate({"schema": ask.fmt.id, "cols": ask.cols if subset else None,
                                "rows": rows, "nulls": nulls or None})
    return Draft(type="reply", parent=parent, verdict=verdict, data=data, flags=flags or None)


def _card_parts(pairs: _Pairs) -> list[CardPart]:
    return [CardPart(id=part.id, wave=part.wave, group=part.group, tools=sorted(part.tools),
                     cols=[c for tool in sorted(part.tools) for c in part.tools[tool]],
                     rows=len(result.rows), status=result.status, secs=round(result.secs, 2),
                     reason=result.reason)
            for part, result in pairs]


class TaskPlannerSkill:
    """Builds asked tables from registered tools: one reply per ask, no AI call."""

    key = KEY
    needs: tuple[str, ...] = ()
    answer = InboxReply
    talks = True

    def __init__(self, clock: Callable[[], datetime] = ny_now,
                 send: Sender | None = None) -> None:
        """Set the clock and the alert sender (Telegram when ``None``)."""
        self._clock = clock
        self._send = send

    def facts(self, home: Path) -> Facts:
        """Always ready; the tools say themselves when they have no data."""
        return Facts("Table asks", self._clock().date().isoformat(), True)

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]:
        """Answer each ask in the inbox with one reply draft (SRD-DSK-012.018)."""
        talk = talker(ctx)
        if talk is None:
            return []
        for message_id in facts.inbox:
            msg = read_message(ctx.home, message_id)
            if msg is None or not isinstance(msg.body, AskBody):
                continue
            try:
                draft = self._work(ctx.home, msg, msg.body, facts.data_day)
            except Exception:  # noqa: BLE001 — one bad ask must not drop the other replies
                log.exception("[Task cards] A table ask could not be worked")
                draft = _failed(msg.id, ERROR)
            talk.send(draft)
        return []

    def _work(self, home: Path, msg: Message, body: AskBody, day: str) -> Draft:
        now = self._clock()
        asker = _name(home, msg.sender)
        if not load_settings(home).task_cards_on:
            log.info("[Task cards] Ask from %s refused: %s", asker, OFF)
            return _refused(msg.id, OFF)
        spec = holder(home, KEY)
        owner = spec.id if spec is not None else KEY
        try:
            ask = _check(home, body)
        except _Refusal as why:
            self._failure(home, owner, f"Ask refused: {why}", day, now)
            log.info("[Task cards] Ask from %s refused: %s", asker, why)
            return _refused(msg.id, str(why))
        card = open_card(home, msg.id, msg.sender, owner, ask.fmt.id, ask.cols, ask.keys, now)
        started = time.monotonic()
        try:
            pairs = _run_parts(home, ask)
            rows, nulls, wrong = _merge(ask, pairs)
            status, reason = _verdict(ask, pairs, len(rows), nulls, wrong)
            draft = _reply(msg.id, ask, status, reason, rows, nulls, pairs)
            secs = time.monotonic() - started
            close_card(home, card, status, _card_parts(pairs), len(rows), reason, self._clock(),
                       secs)
        except Exception:
            self._abandon(home, card)
            raise
        if status == "done":
            log.info("[Task cards] Card %d for %s: %s, %d stock(s), done in %.1f s", card, asker,
                     ask.fmt.id, len(rows), secs)
        else:
            log.warning("[Task cards] Card %d for %s is %s: %s", card, asker, status, reason)
        self._record(home, owner, ask.fmt.id, pairs, day, now)
        return draft

    def _abandon(self, home: Path, card: int) -> None:
        """Close a card whose work raised, so it never stays working."""
        try:
            close_card(home, card, "failed", [], 0, ERROR, self._clock(), 0.0)
        except Exception:  # noqa: BLE001 — the failed reply still goes out
            log.exception("[Task cards] Could not close card %d", card)

    def _record(self, home: Path, owner: str, format_id: str, pairs: _Pairs, day: str,
                now: datetime) -> None:
        """Keep the failed parts and count the card for its plan (SRD-DSK-012.026, .027).

        The table is already built, so a problem here is logged and the reply still goes out.
        """
        failed = [(part, result) for part, result in pairs if result.status == FAILED]
        for part, result in failed:
            self._failure(home, owner, f"{format_id}: {group_label(part.group)} failed: "
                                       f"{result.reason}", day, now)
        last = failed[0][1].reason if failed else ""
        try:
            if note_result(home, format_id, bool(failed), last, now):
                log.warning("[Task cards] Plan for %s retired after %d failed cards", format_id,
                            RETIRE_AFTER)
                raise_alert(home, "plan_retired", format_id, 0,
                            f"The plan for {format_id} had a failed part {RETIRE_AFTER} times in "
                            f"a row. Last problem: {last}", now, self._send)
        except Exception:  # noqa: BLE001 — the reply still goes out
            log.exception("[Task cards] Could not count the card for the plan of %s", format_id)

    @staticmethod
    def _failure(home: Path, owner: str, text: str, day: str, now: datetime) -> None:
        """Keep one failure row; a memory problem never stops the reply (SRD-DSK-012.026)."""
        try:
            log_failure(home, owner, text, day, now)
        except Exception:  # noqa: BLE001 — the reply still goes out
            log.exception("[Task cards] Could not keep a failure row")
