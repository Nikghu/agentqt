"""
Module: MD-DSK-004.001.M11 — desk/gateway.py
Parent SRD: SRD-DSK-004.001
Also: SRD-DSK-004.002 (schema check, retry, backup), SRD-DSK-002.003 (soul is the prompt,
job file picks the models)

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

from us_swing.core.desk_agents import T
from us_swing.core.desk_ai_settings import DeskAiSettings
from us_swing.core.notifications._ai_client import OPENROUTER_URL, _run_with_timeout
from us_swing.desk.budget import Budget
from us_swing.desk.recorder import Attempt, Recorder, ny_now
from us_swing.desk.registry import Hire, ModelChoice

log = logging.getLogger(__name__)

TIMEOUT_S = 90.0
DEFAULT_MODEL = "default"
_SOURCE_NAMES = {"openrouter": "OpenRouter", "claude": "Claude Code CLI"}


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
                 clock: Callable[[], datetime] = ny_now) -> None:
        """Bind the employee, the run and the sources; ``caller`` is injectable for tests."""
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
            user = facts
            for _ in range(2):
                why = self._budget.refusal(spec.name, spec.monthly_cost_usd, spec.calls_per_day,
                                           choice.source)
                if why:
                    self.refused = why
                    log.warning("[AI Desk] %s not asked: %s", spec.name, why)
                    return None
                attempt += 1
                result, error = self._try(choice.source, model, system, user, schema, attempt)
                if result is not None:
                    return result
                user = f"{facts}\n\nYour last answer was not valid: {error}. Answer again."
        return None

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
        try:
            reply = self._caller(source, model, system, user, self._key)
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
            self._run_id, spec.name, spec.version, self._day,
            started.isoformat(timespec="seconds"), source, model, attempt,
            f"{system}\n\n---\n\n{user}", reply.text, result is not None, error,
            reply.tokens_in, reply.tokens_out, reply.cost_usd, seconds))
        if result is not None:
            self.answered = Answered(model, seconds, reply.tokens_in + reply.tokens_out,
                                     reply.cost_usd)
        else:
            log.warning("[AI Desk] %s answer %d from %s was not valid: %s", spec.name, attempt,
                        model, error)
        return result, error
