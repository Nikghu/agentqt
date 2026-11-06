"""
Module: MD-DSK-002.001.M08 — core/desk_agents.py
Parent SRD: SRD-DSK-002.001
Also: SRD-DSK-002.005 — employees get only their folder, facts and an ask function

Shared types for AI employees. The desk harness (``desk``) and the tools that provide
employees (such as ``market``) both import these, so neither imports the other.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

FEED_KINDS = ("info", "idea", "approval")


@dataclass(frozen=True)
class Facts:
    """What an employee reads before it is woken; ``fresh`` False keeps it asleep."""

    text: str
    data_day: str
    fresh: bool
    why_stale: str = ""


@dataclass(frozen=True)
class FeedItem:
    """One brief for the AI feed."""

    author: str
    kind: str
    text: str
    data_day: str

    def __post_init__(self) -> None:
        """Refuse an empty text or an unknown kind."""
        if not self.text.strip():
            raise ValueError("feed item without text")
        if self.kind not in FEED_KINDS:
            raise ValueError(f"unknown feed kind {self.kind}")


class AgentContext(Protocol):
    """What an employee may use while it acts: its desk folder and the gateway."""

    @property
    def home(self) -> Path: ...

    def ask(self, facts: str, schema: type[T]) -> T | None: ...


class Employee(Protocol):
    """An AI employee: ``folder`` holds its ``soul.md`` and ``job.yaml``."""

    name: str
    folder: Path

    def facts(self, home: Path) -> Facts: ...

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]: ...
