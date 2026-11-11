"""
Module: MD-DSK-004.001.M11 — desk/gateway.py
Parent SRD: SRD-DSK-004.001
Also: SRD-DSK-004.002 (schema check, retry, backup), SRD-DSK-002.003 (soul is the prompt,
job file picks the models), SRD-DSK-005.005 (resend a recorded prompt for a replay),
SRD-DSK-007.001 (raise an alert for a login, key or credit problem), SRD-DSK-007.004 (skip a
source that failed to sign in for the rest of the run), SRD-DSK-004.008, .009 (each try is paid
from a budget part; a ticket try is paid by the raiser and stops at the ticket cap)

The one way AI employees reach a model. Sources: OpenRouter (API, has cost) and Claude
Code CLI (subscription: tokens only, cost 0). Every answer must be JSON matching the
employee's schema; a bad answer is retried once, then the backup model is tried.
Every try is recorded.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from us_swing.core.desk_employee import DEFAULT_MODEL
from us_swing.core.desk_agents import T
from us_swing.core.desk_ai_settings import DeskAiSettings
from us_swing.core.desk_alerts import Sender, classify, raise_alert
from us_swing.core.notifications._ai_client import OPENROUTER_URL, _run_with_timeout
from us_swing.desk.budget import Budget, Part
from us_swing.desk.recorder import Attempt, Recorder, ny_now
from us_swing.desk.registry import Hire, ModelChoice

log = logging.getLogger(__name__)

TIMEOUT_S = 90.0
_SOURCE_NAMES = {"openrouter": "OpenRouter", "claude": "Claude Code CLI"}
# (desk folder, run id) → sources that failed to sign in during that run
_BROKEN: dict[tuple[str, int], set[str]] = {}


@dataclass(frozen=True)
class Reply:
    """A model's answer text and usage; cost is 0 for Claude Code CLI."""

    text: str
    tokens_in: int
    tokens_out: int
    cost_usd: float


Caller = Callable[[str, str, str, str, str], Reply]


def call_model(source: str, model: str, system: str, user: str, key: str) -> Reply:
    """Send one request to ``source``; raise ``RuntimeError`` with a plain reason on failure."""
    if source == "openrouter":
        return _openrouter(model, system, user, key)
    return _claude(model, system, user)


def _openrouter(model: str, system: str, user: str, key: str) -> Reply:
    if not key:
        raise RuntimeError("OpenRouter key missing")
    response = httpx.post(
        OPENROUTER_URL, headers={"Authorization": f"Bearer {key}"},
        json={"model": model, "usage": {"include": True},
              "messages": [{"role": "system", "content": system},
                           {"role": "user", "content": user}]},
        timeout=TIMEOUT_S)
    try:
        reply: dict[str, Any] = response.json()
    except ValueError:
        reply = {}
    if response.status_code != 200:
        message = (reply.get("error") or {}).get("message", "")
        raise RuntimeError(f"HTTP {response.status_code} {message}".strip())
    try:
        text = str(reply["choices"][0]["message"]["content"] or "")
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("unexpected reply") from None
    usage = reply.get("usage") or {}
    if usage.get("cost") is None:
        raise RuntimeError("OpenRouter reported no cost, so the budget cannot be checked")
    return Reply(text, int(usage.get("prompt_tokens") or 0),
                 int(usage.get("completion_tokens") or 0), float(usage["cost"]))


def _claude(model: str, system: str, user: str) -> Reply:
    exe = shutil.which("claude")
    if exe is None:
        raise RuntimeError("Claude Code CLI is not installed on this PC")
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    with tempfile.TemporaryDirectory(prefix="usswing_desk_") as work_dir:
        prompt_file = Path(work_dir) / "system_prompt.txt"
        prompt_file.write_text(system, encoding="utf-8")
        command = [
            exe, "-p", "--safe-mode", "--tools", "", "--system-prompt-file", str(prompt_file),
            "--model", model, "--effort", "low", "--output-format", "json",
            "--no-session-persistence", "--permission-prompts", "none",
        ]
        stdout, stderr, code = _run_with_timeout(command, user, work_dir, env, TIMEOUT_S)
    return parse_claude(stdout, stderr, code)


def parse_claude(stdout: str, stderr: str, code: int) -> Reply:
    """Read the CLI's JSON output; its cost is ignored (subscription)."""
    try:
        reply: dict[str, Any] = json.loads(stdout)
    except ValueError:
        detail = (stderr or stdout).strip().splitlines()
        raise RuntimeError(detail[-1] if detail else f"exit code {code}") from None
    if reply.get("is_error") or not reply.get("result"):
        reason = reply.get("api_error_status") or reply.get("result") or reply.get("subtype")
        raise RuntimeError(str(reason or "empty answer"))
    usage = reply.get("usage") or {}
    tokens_in = sum(int(usage.get(k) or 0) for k in (
        "input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    return Reply(str(reply["result"]).strip(), tokens_in, int(usage.get("output_tokens") or 0),
                 0.0)


def json_part(text: str) -> str:
    """Return the text from the first ``{`` to the last ``}`` (models often add words)."""
    start, end = text.find("{"), text.rfind("}")
    return text[start:end + 1] if 0 <= start < end else text


def system_prompt(soul: str, schema: type[BaseModel]) -> str:
    """The soul text followed by the answer rules."""
    return (f"{soul.strip()}\n\nAnswer with one JSON object only, no other text, matching "
            f"this JSON schema:\n{json.dumps(schema.model_json_schema())}")


@dataclass(frozen=True)
class Answered:
    """Summary of the last valid answer, for the run log."""

    model: str
    seconds: float
    tokens: int
    cost_usd: float


class Gateway:
    """``AgentContext`` for one employee run: home plus a checked, recorded ``ask``."""

    def __init__(self, home: Path, hire: Hire, recorder: Recorder, settings: DeskAiSettings,
                 key: str, run_id: int, data_day: str, caller: Caller = call_model,
                 clock: Callable[[], datetime] = ny_now, replay: bool = False,
                 shadow: bool = False, send: Sender | None = None,
                 part: Part | None = None) -> None:
        """Bind the employee, the run and the sources; ``caller`` is injectable for tests.

        With ``replay`` every try is recorded as a replay, so it never counts as a wake;
        with ``shadow`` every try is marked as a shadow try (SRD-DSK-006.004).
        ``part`` is the budget part the tries are paid from; by default the employee's plan.
        """
        spec = hire.spec
        self._part = part or Part("plan", spec.id, spec.name, spec.tokens_per_day)
        self._replay = replay
        self._shadow = shadow
        self._send = send
        self._home = home
        self._hire = hire
        self._rec = recorder
        self._settings = settings
        self._key = key
        self._run_id = run_id
        self._day = data_day
        self._caller = caller
        self._clock = clock
        self._budget = Budget(recorder, settings, clock)
        self.answered: Answered | None = None
        self.refused: str | None = None

    @property
    def home(self) -> Path:
        """The desk folder."""
        return self._home

    def ask(self, facts: str, schema: type[T]) -> T | None:
        """Return a checked answer, or ``None`` after all tries fail or a cap refuses."""
        system = system_prompt(self._hire.soul, schema)
        spec = self._hire.spec
        attempt = 0
        for choice in (spec.models.primary, spec.models.backup):
            model = self._model(choice)
            if model is None:
                continue
            if choice.source in self._broken():
                log.info("[AI Desk] %s skips %s: it could not sign in earlier in this run",
                         spec.name, _SOURCE_NAMES[choice.source])
                continue
            user = facts
            for _ in range(2):
                why = self._budget.refusal(spec.id, spec.name, spec.monthly_cost_usd,
                                           spec.calls_per_day, choice.source, self._part)
                if why:
                    self.refused = why
                    log.warning("[AI Desk] %s not asked: %s", spec.name, why)
                    return None
                attempt += 1
                result, error = self._try(choice.source, model, system, user, schema, attempt)
                if result is not None:
                    return result
                if choice.source in self._broken():
                    break
                user = f"{facts}\n\nYour last answer was not valid: {error}. Answer again."
        return None

    def _broken(self) -> set[str]:
        home = str(self._home)
        for key in [k for k in _BROKEN if k[0] == home and k[1] != self._run_id]:
            del _BROKEN[key]
        return _BROKEN.setdefault((home, self._run_id), set())

    def _report(self, source: str, error: str) -> None:
        """Raise an alert and stop using ``source`` this run when the error needs the user."""
        kind = classify(source, error)
        if kind is None or self._replay:
            return
        self._broken().add(source)
        raise_alert(self._home, kind, source, self._run_id,
                    f"{self._hire.spec.name}: {error}", self._clock(), self._send)

    def _model(self, choice: ModelChoice) -> str | None:
        s = self._settings
        on = s.openrouter_on if choice.source == "openrouter" else s.claude_on
        if not on:
            log.info("[AI Desk] %s is off in desk AI settings; %s skips it",
                     _SOURCE_NAMES[choice.source], self._hire.spec.name)
            return None
        model = choice.model
        if model == DEFAULT_MODEL:
            model = s.openrouter_model if choice.source == "openrouter" else s.claude_model
        if not model or model.startswith("-"):
            log.info("[AI Desk] No %s model set in desk AI settings",
                     _SOURCE_NAMES[choice.source])
            return None
        return model

    def _try(self, source: str, model: str, system: str, user: str, schema: type[T],
             attempt: int) -> tuple[T | None, str]:
        started = self._clock()
        began = time.monotonic()
        reply = Reply("", 0, 0, 0.0)
        result: T | None = None
        call_failed = True
        try:
            reply = self._caller(source, model, system, user, self._key)
            call_failed = False
            result = schema.model_validate_json(json_part(reply.text))
            error = ""
        except ValidationError as exc:
            error = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
                              for e in exc.errors()[:3])
        except Exception as exc:  # noqa: BLE001 — any source failure is one failed try
            error = str(exc) or type(exc).__name__
        seconds = round(time.monotonic() - began, 2)
        spec = self._hire.spec
        self._rec.add(Attempt(
            self._run_id, spec.id, spec.name, spec.version, self._day,
            started.isoformat(timespec="seconds"), source, model, attempt,
            f"{system}\n\n---\n\n{user}", reply.text, result is not None, error,
            reply.tokens_in, reply.tokens_out, reply.cost_usd, seconds, int(self._replay),
            int(self._shadow), self._part.name, self._part.payer, self._part.ticket))
        if result is not None:
            self.answered = Answered(model, seconds, reply.tokens_in + reply.tokens_out,
                                     reply.cost_usd)
        else:
            log.warning("[AI Desk] %s answer %d from %s was not valid: %s", spec.name, attempt,
                        model, error)
            if call_failed:
                self._report(source, error)
        return result, error


class ReplayGateway(Gateway):
    """A gateway for ``desk replay`` only: tries are marked as replays, and it can send a
    recorded prompt again. Skills never get this object, so they cannot set a prompt."""

    def resend(self, system: str, user: str, schema: type[T], source: str,
               model: str) -> T | None:
        """Send a recorded prompt again to one model (one retry); caps apply as usual."""
        spec = self._hire.spec
        text = user
        for attempt in (1, 2):
            why = self._budget.refusal(spec.id, spec.name, spec.monthly_cost_usd,
                                       spec.calls_per_day, source, self._part)
            if why:
                self.refused = why
                return None
            result, error = self._try(source, model, system, text, schema, attempt)
            if result is not None:
                return result
            text = f"{user}\n\nYour last answer was not valid: {error}. Answer again."
        return None
