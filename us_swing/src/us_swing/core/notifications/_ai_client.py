"""
Module: MD-INF-011.001.M01 — AI Notes Client
Parent SRD: SRD-INF-011.001

Sends one short request to the user's default AI, Claude Code CLI or OpenRouter, and
tries the other provider when AI Fallback is on. Sync: callers run it off the GUI thread.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

_log = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_NAMES = {"claude": "Claude Code CLI", "openrouter": "OpenRouter"}


@dataclass(frozen=True, slots=True)
class AiConfig:
    """What ``ask_ai`` needs from the user's AI notes settings."""

    claude_on: bool = True
    claude_model: str = "claude-sonnet-5-5"
    openrouter_on: bool = False
    openrouter_model: str = ""
    openrouter_key: str = ""
    default: str = "claude"
    fallback: bool = False


@dataclass(frozen=True, slots=True)
class AiAnswer:
    """The answer text and who gave it, or an error when no provider answered."""

    text: str = ""
    provider: str = ""
    seconds: float = 0.0
    error: str = ""


def provider_name(provider: str) -> str:
    """The user-facing name of a provider id."""
    return _NAMES.get(provider, provider)


def ask_ai(
    config: AiConfig, instruction: str, facts: str, timeout_s: float = 90.0
) -> AiAnswer:
    """Ask the default AI, then the other one when fallback is on (SRD-INF-011.003).

    Args:
        config: Provider ticks, models, key, default and fallback.
        instruction: What the AI must do with the facts.
        facts: The data the answer is based on.
        timeout_s: Time limit for each provider.

    Returns:
        The answer, or an ``AiAnswer`` whose ``error`` names each failure. Never raises.
    """
    callers: dict[str, Callable[[AiConfig, str, str, float], str]] = {
        "claude": _ask_claude, "openrouter": _ask_openrouter,
    }
    ticked = {"claude": config.claude_on, "openrouter": config.openrouter_on}
    other = "openrouter" if config.default == "claude" else "claude"
    order = [config.default]
    if config.fallback and all(ticked.values()):
        order.append(other)

    reasons: list[str] = []
    for provider in order:
        if not ticked.get(provider):
            reasons.append(f"{provider_name(provider)}: not ticked")
            continue
        start = time.monotonic()
        try:
            text = callers[provider](config, instruction, facts, timeout_s)
        except Exception as exc:
            reason = str(exc) or type(exc).__name__
            reasons.append(f"{provider_name(provider)}: {reason}")
            _log.warning("[AI] %s did not answer: %s", provider_name(provider), reason)
            continue
        return AiAnswer(text=text, provider=provider, seconds=time.monotonic() - start)
    return AiAnswer(error="; ".join(reasons))


def _ask_claude(config: AiConfig, instruction: str, facts: str, timeout_s: float) -> str:
    """Run the Claude Code CLI headless with no tools and no saved session (SRD-INF-011.001)."""
    exe = shutil.which("claude")
    if exe is None:
        raise RuntimeError("not installed on this PC")
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    with tempfile.TemporaryDirectory(prefix="usswing_ai_") as work_dir:
        prompt_file = Path(work_dir) / "system_prompt.txt"
        prompt_file.write_text(instruction, encoding="utf-8")
        command = [
            exe, "-p", "--safe-mode", "--tools", "", "--system-prompt-file", str(prompt_file),
            "--model", config.claude_model, "--effort", "low", "--output-format", "json",
            "--no-session-persistence", "--permission-prompts", "none",
        ]
        stdout, stderr, code = _run_with_timeout(
            command, f"{instruction}\n\n{facts}", work_dir, env, timeout_s
        )
    try:
        reply = json.loads(stdout)
    except ValueError:
        detail = (stderr or stdout).strip().splitlines()
        raise RuntimeError(detail[-1] if detail else f"exit code {code}") from None
    if reply.get("is_error") or not reply.get("result"):
        reason = reply.get("api_error_status") or reply.get("result") or reply.get("subtype")
        raise RuntimeError(str(reason or "empty answer"))
    return str(reply["result"]).strip()


def _run_with_timeout(
    command: list[str], stdin: str, cwd: str, env: dict[str, str], timeout_s: float
) -> tuple[str, str, int]:
    """Run ``command``; on timeout kill it and its child processes."""
    process = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", cwd=cwd, env=env,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        stdout, stderr = process.communicate(stdin, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        _kill_tree(process)
        raise RuntimeError(f"no answer in {timeout_s:.0f} seconds") from None
    return stdout, stderr, process.returncode


def _kill_tree(process: subprocess.Popen[str]) -> None:
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(process.pid)], capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False,
        )
    process.kill()
    process.communicate()


def _ask_openrouter(config: AiConfig, instruction: str, facts: str, timeout_s: float) -> str:
    """Call OpenRouter chat completions with the user's key and model (SRD-INF-011.002)."""
    if not config.openrouter_key or not config.openrouter_model:
        raise RuntimeError("API key or model missing")
    response = httpx.post(
        OPENROUTER_URL,
        headers={"Authorization": f"Bearer {config.openrouter_key}"},
        json={
            "model": config.openrouter_model,
            "messages": [
                {"role": "system", "content": instruction},
                {"role": "user", "content": facts},
            ],
        },
        timeout=timeout_s,
    )
    try:
        reply = response.json()
    except ValueError:
        reply = {}
    if response.status_code != 200:
        message = (reply.get("error") or {}).get("message", "")
        raise RuntimeError(f"HTTP {response.status_code} {message}".strip())
    try:
        text = reply["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("unexpected reply") from None
    if not text:
        raise RuntimeError("empty answer")
    return str(text).strip()
