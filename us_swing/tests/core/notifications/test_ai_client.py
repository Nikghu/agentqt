"""Unit tests for the AI notes client (MD-INF-011.001.M01)."""
from __future__ import annotations

import dataclasses
import json
from typing import Any

import httpx
import pytest

from us_swing.core.notifications import _ai_client
from us_swing.core.notifications._ai_client import AiConfig, ask_ai

_BOTH = AiConfig(openrouter_on=True, openrouter_model="m", openrouter_key="sk-k")


@pytest.fixture()
def claude(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Fake claude exe; ``state["reply"]`` is the CLI stdout, calls are recorded."""
    state: dict[str, Any] = {"reply": json.dumps({"is_error": False, "result": " OK "})}
    monkeypatch.setattr(_ai_client.shutil, "which", lambda _n: "claude.exe")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")

    def _run(command: list[str], stdin: str, *_a: Any) -> tuple[str, str, int]:
        state["command"], state["stdin"] = command, stdin
        state["env"] = _a[1]
        return state["reply"], "", 0

    monkeypatch.setattr(_ai_client, "_run_with_timeout", _run)
    return state


@pytest.fixture()
def router(monkeypatch: pytest.MonkeyPatch) -> list[httpx.Request]:
    """Fake OpenRouter that answers "Hi"; requests are recorded."""
    seen: list[httpx.Request] = []
    transport = httpx.MockTransport(lambda request: (
        seen.append(request),
        httpx.Response(200, json={"choices": [{"message": {"content": "Hi"}}]}),
    )[1])

    def _post(url: str, **kwargs: Any) -> httpx.Response:
        with httpx.Client(transport=transport) as client:
            return client.post(url, **kwargs)

    monkeypatch.setattr(_ai_client.httpx, "post", _post)
    return seen


def test_claude_answer(claude: dict[str, Any]) -> None:
    """UT-INF-011.001.M01.T01: Claude answer is read from the CLI JSON."""
    answer = ask_ai(AiConfig(), "Say OK", "facts")

    assert (answer.text, answer.provider, answer.error) == ("OK", "claude", "")
    assert "ANTHROPIC_API_KEY" not in claude["env"]
    assert claude["stdin"].startswith("Say OK")
    assert "--no-session-persistence" in claude["command"]


@pytest.mark.parametrize("reply", [
    json.dumps({"is_error": True, "result": "Not logged in"}), "not json",
])
def test_claude_error(claude: dict[str, Any], reply: str) -> None:
    """UT-INF-011.001.M01.T02: CLI error JSON becomes an error text."""
    claude["reply"] = reply
    answer = ask_ai(AiConfig(), "Say OK", "facts")
    assert answer.text == "" and answer.error.startswith("Claude Code CLI:")


def test_claude_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """UT-INF-011.001.M01.T02: a missing claude exe becomes an error text."""
    monkeypatch.setattr(_ai_client.shutil, "which", lambda _n: None)
    assert "not installed" in ask_ai(AiConfig(), "Say OK", "facts").error


def test_openrouter_answer(router: list[httpx.Request]) -> None:
    """UT-INF-011.002.M01.T01: OpenRouter answer is read from chat completions."""
    answer = ask_ai(AiConfig(claude_on=False, openrouter_on=True, openrouter_model="m",
                             openrouter_key="sk-k", default="openrouter"), "Say hi", "facts")

    assert (answer.text, answer.provider) == ("Hi", "openrouter")
    assert router[0].headers["Authorization"] == "Bearer sk-k"
    assert json.loads(router[0].content)["model"] == "m"


def test_fallback_used(claude: dict[str, Any], router: list[httpx.Request]) -> None:
    """UT-INF-011.003.M01.T01: Fallback uses the other provider when the default fails."""
    claude["reply"] = json.dumps({"is_error": True, "result": "limit"})
    answer = ask_ai(dataclasses.replace(_BOTH, fallback=True), "Say hi", "facts")
    assert answer.provider == "openrouter" and answer.error == ""


def test_no_fallback_when_off(claude: dict[str, Any], router: list[httpx.Request]) -> None:
    """UT-INF-011.003.M01.T02: no fallback when it is off."""
    claude["reply"] = json.dumps({"is_error": True, "result": "limit"})
    answer = ask_ai(_BOTH, "Say hi", "facts")
    assert router == [] and "limit" in answer.error

