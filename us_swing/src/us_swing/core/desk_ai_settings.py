"""
Module: MD-DSK-004.005.M13 — core/desk_ai_settings.py
Parent SRD: SRD-DSK-004.005
Also: SRD-DSK-011.031 (``messages_on``, off by default), SRD-DSK-011.042 (``escalation_on``,
off by default)
Also: SRD-DSK-009.023 (``memory_v2_on``, off by default)
Also: SRD-DSK-006.003 — seat caps per level; SRD-MKT-008.002 — trade target R multiple

Desk AI settings, separate from the AI notes settings: which sources may run, their
models, the monthly API budget and the daily Claude Code CLI token cap. Kept in
``desk_ai.json`` in the desk folder; the OpenRouter key is kept in the OS keychain.
Shared by the desk process and the GUI.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Final

from us_swing.core.desk_contract import desk_home

log = logging.getLogger(__name__)

SETTINGS_FILE: Final[str] = "desk_ai.json"
_KEY_SERVICE: Final[str] = "usswing_desk_openrouter"
_KEY_USER: Final[str] = "desk"


@dataclass(frozen=True)
class DeskAiSettings:
    """Desk AI settings; both sources start off, so no AI runs until the user sets it up."""

    openrouter_on: bool = False
    openrouter_model: str = ""
    claude_on: bool = False
    claude_model: str = "claude-haiku-5-5"
    monthly_budget_usd: float = 10.0
    claude_tokens_per_day: int = 200_000
    expert_cap: int = 8
    champion_cap: int = 5
    junior_cap: int = 30
    trade_target_r: float = 2.0
    messages_on: bool = False
    escalation_on: bool = False
    memory_v2_on: bool = False

    def __post_init__(self) -> None:
        """Refuse a budget, token cap, seat cap or R multiple that is not above 0."""
        if self.monthly_budget_usd <= 0 or self.claude_tokens_per_day <= 0:
            raise ValueError("budget and token cap must be above 0")
        if min(self.expert_cap, self.champion_cap, self.junior_cap) < 1:
            raise ValueError("seat caps must be at least 1")
        if self.trade_target_r <= 0:
            raise ValueError("trade target R multiple must be above 0")

    def cap(self, level: str) -> int | None:
        """Seat cap of ``level``; ``None`` for the lead level, which has no cap."""
        return {"expert": self.expert_cap, "champion": self.champion_cap,
                "junior": self.junior_cap}.get(level)


def load_settings(home: Path | None = None) -> DeskAiSettings:
    """Return the saved settings, or the defaults when the file is missing or broken."""
    path = (home or desk_home()) / SETTINGS_FILE
    if not path.exists():
        return DeskAiSettings()
    try:
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        known = {f.name for f in fields(DeskAiSettings)}
        return DeskAiSettings(**{k: v for k, v in data.items() if k in known})
    except (ValueError, TypeError) as exc:
        log.warning("[AI Desk] Desk AI settings file is not valid, using defaults: %s", exc)
        return DeskAiSettings()


def save_settings(settings: DeskAiSettings, home: Path | None = None) -> None:
    """Write the settings file."""
    folder = home or desk_home()
    folder.mkdir(parents=True, exist_ok=True)
    (folder / SETTINGS_FILE).write_text(json.dumps(asdict(settings), indent=2),
                                        encoding="utf-8")


def load_key() -> str:
    """Return the desk OpenRouter key, or an empty string."""
    try:
        import keyring  # noqa: PLC0415 — slow import, only when needed

        return keyring.get_password(_KEY_SERVICE, _KEY_USER) or ""
    except Exception as exc:  # noqa: BLE001 — no keychain means no key
        log.debug("[AI Desk] Keychain not available: %s", exc)
        return ""


def save_key(key: str) -> None:
    """Store the desk OpenRouter key, or remove it when ``key`` is blank."""
    try:
        import keyring  # noqa: PLC0415 — slow import, only when needed
    except ImportError:
        log.warning("[AI Desk] Keychain not available; OpenRouter key not saved")
        return
    if key.strip():
        keyring.set_password(_KEY_SERVICE, _KEY_USER, key.strip())
        return
    try:
        keyring.delete_password(_KEY_SERVICE, _KEY_USER)
    except Exception:  # noqa: BLE001, S110 — nothing stored is fine
        pass
