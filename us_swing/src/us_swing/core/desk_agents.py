"""
Module: MD-DSK-002.001.M08 — core/desk_agents.py
Parent SRD: SRD-DSK-002.001
Also: SRD-DSK-002.005 (skills get only their folder, facts and an ask function),
SRD-DSK-002.006 (generic levels), SRD-DSK-002.008 (skill needs)

Shared types for AI skills. Code knows only skills, named by what they do. Who uses a
skill (name, title, level, reporting line) is data in each employee's own files, which
the Master user can change at any time. The desk harness (``desk``) and the tools that
provide skills (such as ``market``) both import these, so neither imports the other.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

FEED_KINDS = ("info", "idea", "approval", "morning", "evening")  # evening: rows before 2026-11-11
Level = Literal["lead", "expert", "champion", "junior"]
LEVELS: tuple[Level, ...] = ("lead", "expert", "champion", "junior")


@dataclass(frozen=True)
class Facts:
    """What a skill reads before its employee is woken; ``fresh`` False keeps it asleep."""

    text: str
    data_day: str
    fresh: bool
    why_stale: str = ""


@dataclass(frozen=True)
class FeedItem:
    """One brief for the AI feed; the desk adds the employee's name when it is stored."""

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
    """What a skill may use while it acts: the desk folder and the gateway."""

    @property
    def home(self) -> Path: ...

    def ask(self, facts: str, schema: type[T]) -> T | None: ...


class Skill(Protocol):
    """Work an employee can do; ``key`` names the skill in employee job files.

    ``needs`` lists the skill keys whose views this skill reads, so the desk runs those
    first; it is about the work, never about who does it. ``answer`` is the base answer
    schema, which a replay uses to check new answers.
    """

    key: str
    needs: tuple[str, ...]
    answer: type[BaseModel]

    def facts(self, home: Path) -> Facts: ...

    def act(self, ctx: AgentContext, facts: Facts) -> list[FeedItem]: ...
