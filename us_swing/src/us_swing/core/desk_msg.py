"""
Module: MD-DSK-011.001.M27 — core/desk_msg.py
Parent SRD: SRD-DSK-011.001

The one desk message format, ``desk.msg/1``: a thread row, an envelope with the core header,
a body chosen by message type and meta keys that appear only when set. Every model refuses
unknown keys. M0 adds the format only; nothing stores or sends messages yet. Design:
DD-DSK-011.001.D01.
"""
from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    TypeAdapter,
    ValidationError,
    model_validator,
)

from us_swing.core.desk_registry import SCHEMA_ID, TOOL_REF

SCHEMA = "desk.msg/1"
MAX_ROWS = 200

Address = Annotated[str, StringConstraints(
    pattern=r"^(?:skill:[a-z0-9_]+|champion:[a-z0-9_]+|boss|master|[A-Za-z0-9_-]+)$")]
SchemaId = Annotated[str, StringConstraints(pattern=SCHEMA_ID)]
ToolRef = Annotated[str, StringConstraints(pattern=TOOL_REF)]
Subject = Annotated[str, StringConstraints(min_length=1, max_length=80, pattern=r"^[^\r\n]+$")]
Text = Annotated[str, StringConstraints(min_length=1, max_length=600)]
About = Annotated[list[Annotated[str, StringConstraints(min_length=1, max_length=40)]],
                  Field(max_length=20)]

_STRICT = ConfigDict(extra="forbid")
_DUE_TYPES = frozenset({"ask", "task", "send_back", "escalate", "meeting"})
_PARENT_TYPES = frozenset({"reply", "send_back", "decision"})
_NO_TO_TYPES = frozenset({"reply", "send_back"})


class State(str, Enum):
    """Message states, named as in A2A (SRD-DSK-011.012)."""

    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input_required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    REFUSED = "refused"
    EXPIRED = "expired"


class Thread(BaseModel):
    """One conversation: who pays, how many messages and send-back rounds (SRD-DSK-011.002)."""

    model_config = _STRICT

    id: int = Field(ge=1)
    starter: Address
    msgs: int = Field(ge=1)
    rounds: int = Field(default=0, ge=0)
    state: Literal["open", "closed"] = "open"
    opened: AwareDatetime
    closed: AwareDatetime | None = None


class Want(BaseModel):
    """What the asker needs: goal, where the work stops, inputs and the wanted format."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    goal: str = Field(min_length=1, max_length=120)
    done_when: str = Field(min_length=1, max_length=120)
    inputs: dict[str, Any]
    schema_id: SchemaId | None = Field(default=None, alias="schema")
    cols: list[str] | None = None
    tools: list[ToolRef] | None = None
    max_tokens: int = Field(default=0, ge=0)


class Verdict(BaseModel):
    """A result with an optional reason; agreed and disagreed only on a decision."""

    model_config = _STRICT

    result: str
    reason: str | None = Field(default=None, min_length=1, max_length=200)
    agreed: list[Address] | None = None
    disagreed: list[Address] | None = None


class Data(BaseModel):
    """A table in a schema-library format: rows as lists, or a reference with a row count."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_id: SchemaId = Field(alias="schema")
    cols: list[str] | None = None
    rows: list[list[Any]] | None = Field(default=None, max_length=MAX_ROWS)
    nulls: dict[str, str] | None = None
    ref: str | None = Field(default=None, min_length=1)
    n: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _rows_or_ref(self) -> Data:
        if (self.rows is None) == (self.ref is None):
            raise ValueError("a data block holds either rows or a ref, not both or neither")
        if (self.ref is None) != (self.n is None):
            raise ValueError("n is given with a ref and only with a ref")
        return self


class Flag(BaseModel):
    """A short warning about one symbol or topic."""

    model_config = _STRICT

    about: str = Field(min_length=1, max_length=40)
    note: str = Field(min_length=1, max_length=120)


class AiUse(BaseModel):
    """Tokens and model of the AI call that wrote the message."""

    model_config = _STRICT

    tok: int = Field(ge=0)
    model: str = Field(min_length=1)


class Meta(BaseModel):
    """Keys written only when they have a value (SRD-DSK-011.011)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    ai: AiUse | None = None
    used: list[ToolRef] | None = None
    secs: float | None = Field(default=None, gt=0)
    blocked: str | None = Field(default=None, min_length=1)
    schema_name: str | None = Field(default=None, alias="schema", pattern=r"^desk\.msg/\d+$")

    @model_validator(mode="after")
    def _not_default(self) -> Meta:
        if self.schema_name == SCHEMA:
            raise ValueError(f"meta schema is written only when it is not {SCHEMA}")
        return self


Flags = Annotated[list[Flag], Field(max_length=5)]


def _check_results(verdict: Verdict, allowed: tuple[str, ...], kind: str) -> None:
    if verdict.result not in allowed:
        raise ValueError(f"a {kind} verdict is one of: {', '.join(allowed)}")
    if kind != "decision" and (verdict.agreed or verdict.disagreed):
        raise ValueError("agreed and disagreed are allowed only on a decision")


class AskBody(BaseModel):
    """Ask: a question to another agent."""

    model_config = _STRICT

    type: Literal["ask"] = "ask"
    subject: Subject
    text: Text | None = None
    about: About | None = None
    want: Want | None = None

    @model_validator(mode="after")
    def _no_tools(self) -> AskBody:
        if self.want is not None and self.want.tools is not None:
            raise ValueError("want.tools is allowed only on a task")
        return self


class TaskBody(BaseModel):
    """Task: one task-card part sent to a champion."""

    model_config = _STRICT

    type: Literal["task"] = "task"
    card: str = Field(min_length=1, max_length=40)
    want: Want


class ReplyBody(BaseModel):
    """Reply: the answer to an ask or task; refused answers at once with a reason."""

    model_config = _STRICT

    type: Literal["reply"] = "reply"
    verdict: Verdict
    text: Text | None = None
    data: Data | None = None
    flags: Flags | None = None

    @model_validator(mode="after")
    def _content(self) -> ReplyBody:
        _check_results(self.verdict, ("done", "partial", "failed", "dropped", "refused"), "reply")
        if self.verdict.result == "refused":
            if self.verdict.reason is None:
                raise ValueError("a refused reply needs a reason")
        elif self.text is None and self.data is None:
            raise ValueError("a reply needs text or data")
        return self


class SendBackBody(BaseModel):
    """Send back: return work to fix or reject it."""

    model_config = _STRICT

    type: Literal["send_back"] = "send_back"
    verdict: Verdict
    text: Text | None = None

    @model_validator(mode="after")
    def _result(self) -> SendBackBody:
        _check_results(self.verdict, ("fix", "reject"), "send_back")
        return self


class HandoverBody(BaseModel):
    """Handover: pass work or facts on."""

    model_config = _STRICT

    type: Literal["handover"] = "handover"
    subject: Subject
    text: Text | None = None
    data: Data | None = None
    about: About | None = None
    flags: Flags | None = None

    @model_validator(mode="after")
    def _content(self) -> HandoverBody:
        if self.text is None and self.data is None:
            raise ValueError("a handover needs text or data")
        return self


class EscalateBody(BaseModel):
    """Escalate: raise a problem to the boss."""

    model_config = _STRICT

    type: Literal["escalate"] = "escalate"
    subject: Subject
    text: Text
    about: About | None = None
    flags: Flags | None = None


class MeetingBody(BaseModel):
    """Meeting: one-round huddle question to several agents."""

    model_config = _STRICT

    type: Literal["meeting"] = "meeting"
    subject: Subject
    text: Text


class DecisionBody(BaseModel):
    """Decision: closes a huddle with who agreed and who did not."""

    model_config = _STRICT

    type: Literal["decision"] = "decision"
    subject: Subject
    verdict: Verdict

    @model_validator(mode="after")
    def _result(self) -> DecisionBody:
        _check_results(self.verdict, ("decided",), "decision")
        return self


class FeedbackBody(BaseModel):
    """Feedback: a note on someone's work, with proof by reference."""

    model_config = _STRICT

    type: Literal["feedback"] = "feedback"
    subject: Subject
    text: Text
    data: Data | None = None


Body = Annotated[
    AskBody | TaskBody | ReplyBody | SendBackBody | HandoverBody | EscalateBody | MeetingBody
    | DecisionBody | FeedbackBody,
    Field(discriminator="type"),
]
_BODIES: dict[str, type[BaseModel]] = {
    m.model_fields["type"].default: m
    for m in (AskBody, TaskBody, ReplyBody, SendBackBody, HandoverBody, EscalateBody,
              MeetingBody, DecisionBody, FeedbackBody)
}


class Message(BaseModel):
    """One ``desk.msg/1`` envelope; the header type is the body type (SRD-DSK-011.003)."""

    model_config = _STRICT

    id: int = Field(ge=1)
    thread: int = Field(ge=1)
    parent: int | None = Field(default=None, ge=1)
    sender: Address
    to: Address | Annotated[list[Address], Field(min_length=1)] | None = None
    at: AwareDatetime
    due: AwareDatetime | None = None
    state: State
    body: Body
    meta: Meta | None = None

    @property
    def type(self) -> str:
        """The message type, taken from the body."""
        return self.body.type

    @model_validator(mode="after")
    def _header_rules(self) -> Message:
        kind = self.body.type
        if isinstance(self.to, list) and kind != "meeting":
            raise ValueError("to is a list only on a meeting")
        if kind in _NO_TO_TYPES and self.to is not None:
            raise ValueError(f"to is left out on a {kind}; the parent's sender gets it")
        if kind not in _NO_TO_TYPES and self.to is None:
            raise ValueError(f"a {kind} needs to")
        if self.due is not None and kind not in _DUE_TYPES:
            raise ValueError(f"a {kind} has no due time")
        if self.parent is None and kind in _PARENT_TYPES:
            raise ValueError(f"a {kind} needs a parent")
        return self


def dump(msg: Message) -> dict[str, Any]:
    """The message as JSON-ready data with no empty or default keys (SRD-DSK-011.011)."""
    data = msg.model_dump(mode="json", by_alias=True, exclude_none=True, exclude_defaults=True)
    data["body"]["type"] = msg.body.type
    return data


def load(data: dict[str, Any]) -> Message:
    """Read a message back; raises ``ValidationError`` on any broken rule."""
    return Message.model_validate(data)


def reason(exc: ValidationError) -> str:
    """The first validation error as one plain line."""
    first = exc.errors()[0]
    where = ".".join(str(p) for p in first["loc"])
    text = str(first["msg"]).removeprefix("Value error, ")
    return f"{where}: {text}" if where else text


def message_schema() -> dict[str, Any]:
    """JSON Schema of the whole envelope, for prompts (SRD-DSK-011.013)."""
    return Message.model_json_schema(by_alias=True)


def body_schema(kind: str) -> dict[str, Any]:
    """JSON Schema of one type's body; ``KeyError`` for an unknown type."""
    return _BODIES[kind].model_json_schema(by_alias=True)


def parse_body(data: dict[str, Any]) -> BaseModel:
    """Pick and check the body model by its ``type`` key."""
    body: BaseModel = TypeAdapter(Body).validate_python(data)
    return body
