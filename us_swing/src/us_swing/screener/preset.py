"""Module: MD-SCR-001.001.M01 — preset.py
Parent SRD: SRD-SCR-001.001–009, SRD-SCR-013.001

Preset dataclass + data model, serialization (to_dict / from_dict),
and structural validation (validate()).
ScreenerRef and ScreenerGroup are helper dataclasses.
"""
from __future__ import annotations

import logging
import re
import uuid

_log = logging.getLogger(__name__)
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from us_swing.screener.base import PresetValidationError
from us_swing.screener.screeners._cloud_ai_models import (
    DEFAULT_MODEL as _DEFAULT_AI_MODEL,
    LEGACY_MODEL_MIGRATION,
)

_VALID_STYLES:     frozenset[str] = frozenset({"swing", "day", "position"})
_VALID_TIMEFRAMES: frozenset[str] = frozenset({"1d", "1w"})
_AI_QUERY_MAX_LEN: int = 500
_MODEL_RE = re.compile(r"^[a-z0-9_.\-]+/[a-z0-9_.\-]+$")
_AI_PROVIDERS: frozenset[str] = frozenset({"openrouter", "claude"})
_AI_CONTEXT_KINDS: frozenset[str] = frozenset({"earnings", "sector"})


class PresetType(str, Enum):
    """Discriminates composite (AND/OR groups) vs weighted (scored) presets."""

    COMPOSITE = "composite"
    WEIGHTED = "weighted"


class GroupLogic(str, Enum):
    """Logical operator applied to screeners within a ScreenerGroup."""

    AND = "AND"
    OR = "OR"


@dataclass
class ScreenerRef:
    """Reference to a screener plugin within a preset or group."""

    screener_id: str
    enabled: bool = True
    weight: float | None = None
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScreenerGroup:
    """Named group of screeners with AND/OR logic (Composite presets only)."""

    group_id: str
    logic: GroupLogic = GroupLogic.AND
    screeners: list[ScreenerRef] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.logic, GroupLogic):
            try:
                self.logic = GroupLogic(self.logic)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid group logic '{self.logic}'. Must be 'AND' or 'OR'."
                ) from exc


@dataclass
class Preset:
    """Full preset definition — Composite or Weighted.

    Composite presets use ``groups`` (nested AND/OR logic).
    Weighted presets use ``screeners`` (flat list with per-screener weights).
    """

    id: str
    name: str
    preset_type: PresetType
    description: str = ""
    # Composite only
    groups: list[ScreenerGroup] = field(default_factory=list)
    # Weighted only
    screeners: list[ScreenerRef] = field(default_factory=list)
    threshold: float | None = None
    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = ""
    is_admin: bool = False
    assigned_to: list[str] = field(default_factory=list)
    trading_styles: list[str] = field(default_factory=list)
    timeframe: str = "1d"
    enable_llm_ranking: bool = False
    top_n: int = 5
    # AI-assisted ranking (SRD-SCR-013.001).  ai_query="" preserves the
    # legacy hardcoded-prompt path for backward compatibility.
    ai_query: str = ""
    ai_model: str = _DEFAULT_AI_MODEL
    # SRD-SCR-013.010: "openrouter" or "claude" (Claude Code CLI).
    ai_provider: str = "openrouter"
    # SRD-SCR-018.001: extra context for the AI ranking ("earnings", "sector").
    ai_context: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict with ISO-8601 UTC datetimes."""
        return {
            "id": self.id,
            "name": self.name,
            "preset_type": self.preset_type.value,
            "description": self.description,
            "groups": [_group_to_dict(g) for g in self.groups],
            "screeners": [_ref_to_dict(r) for r in self.screeners],
            "threshold": self.threshold,
            "created_at": _to_iso(self.created_at),
            "updated_at": _to_iso(self.updated_at),
            "created_by": self.created_by,
            "is_admin": self.is_admin,
            "assigned_to": list(self.assigned_to),
            "trading_styles": list(self.trading_styles),
            "timeframe": self.timeframe,
            "enable_llm_ranking": self.enable_llm_ranking,
            "top_n": self.top_n,
            "ai_query": self.ai_query,
            "ai_model": self.ai_model,
            "ai_provider": self.ai_provider,
            "ai_context": list(self.ai_context),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Preset":
        """Deserialize from a dict.  Unknown keys are silently ignored."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", ""),
            preset_type=PresetType(data.get("preset_type", "composite")),
            description=data.get("description", ""),
            groups=[_group_from_dict(g) for g in data.get("groups", [])],
            screeners=[_ref_from_dict(r) for r in data.get("screeners", [])],
            threshold=data.get("threshold"),
            created_at=_from_iso(data.get("created_at")),
            updated_at=_from_iso(data.get("updated_at")),
            created_by=data.get("created_by", ""),
            is_admin=data.get("is_admin", False),
            assigned_to=list(data.get("assigned_to", [])),
            trading_styles=list(data.get("trading_styles", [])),
            timeframe=data.get("timeframe", "1d"),
            enable_llm_ranking=data.get("enable_llm_ranking", False),
            top_n=data.get("top_n", 5),
            ai_query=data.get("ai_query", ""),
            ai_model=_load_ai_model(data),
            ai_provider=data.get("ai_provider", "openrouter"),
            ai_context=list(data.get("ai_context", [])),
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> None:
        """Validate preset structure.

        Raises:
            PresetValidationError: if the preset is structurally invalid.
        """
        _validate_trading_styles(self.trading_styles)
        if self.timeframe not in _VALID_TIMEFRAMES:
            raise PresetValidationError(
                f"Invalid timeframe '{self.timeframe}'. "
                f"Must be one of {sorted(_VALID_TIMEFRAMES)}."
            )
        _validate_ai_query(self.ai_query)
        _validate_ai_provider(self.ai_provider)
        _validate_ai_context(self.ai_context)
        if self.ai_provider == "openrouter":
            _validate_ai_model(self.ai_model)
        if self.preset_type == PresetType.COMPOSITE:
            _validate_composite(self)
        elif self.preset_type == PresetType.WEIGHTED:
            _validate_weighted(self)


# ---------------------------------------------------------------------------
# Private helpers — serialization
# ---------------------------------------------------------------------------

def _ref_to_dict(r: ScreenerRef) -> dict[str, Any]:
    return {
        "screener_id": r.screener_id,
        "enabled": r.enabled,
        "weight": r.weight,
        "config": r.config,
    }


def _group_to_dict(g: ScreenerGroup) -> dict[str, Any]:
    return {
        "group_id": g.group_id,
        "logic": g.logic.value,
        "screeners": [_ref_to_dict(r) for r in g.screeners],
    }


def _ref_from_dict(r: dict[str, Any]) -> ScreenerRef:
    return ScreenerRef(
        screener_id=r["screener_id"],
        enabled=r.get("enabled", True),
        weight=r.get("weight"),
        config=r.get("config", {}),
    )


def _group_from_dict(g: dict[str, Any]) -> ScreenerGroup:
    return ScreenerGroup(
        group_id=g["group_id"],
        logic=GroupLogic(g.get("logic", "AND")),
        screeners=[_ref_from_dict(r) for r in g.get("screeners", [])],
    )


def _to_iso(dt: datetime) -> str:
    """Serialize datetime to ISO-8601.  UTC datetimes use 'Z' suffix."""
    utc_offset = dt.utcoffset()
    if dt.tzinfo is not None and utc_offset is not None and utc_offset.total_seconds() == 0:
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return dt.isoformat()


def _from_iso(s: str | None) -> datetime:
    """Deserialize ISO-8601 string to a timezone-aware datetime."""
    if s is None:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# Private helpers — validation
# ---------------------------------------------------------------------------

def _validate_ai_query(query: str) -> None:
    """Empty query keeps the legacy ranking path; non-empty must be ≤ 500 chars."""
    if query and len(query) > _AI_QUERY_MAX_LEN:
        raise PresetValidationError(
            f"ai_query exceeds {_AI_QUERY_MAX_LEN} chars (got {len(query)})."
        )


def _validate_ai_model(model: str) -> None:
    """OpenRouter model IDs use the form 'provider/model-name'."""
    if model and not _MODEL_RE.match(model):
        raise PresetValidationError(
            f"ai_model must be 'provider/model-name' format, got {model!r}."
        )


def _validate_ai_provider(provider: str) -> None:
    if provider not in _AI_PROVIDERS:
        raise PresetValidationError(
            f"ai_provider must be one of {sorted(_AI_PROVIDERS)}, got {provider!r}."
        )


def _validate_ai_context(kinds: list[str]) -> None:
    unknown = set(kinds) - _AI_CONTEXT_KINDS
    if unknown:
        raise PresetValidationError(
            f"Unknown ai_context value(s): {sorted(unknown)}. "
            f"Valid values: {sorted(_AI_CONTEXT_KINDS)}."
        )


def _load_ai_model(data: dict[str, Any]) -> str:
    """Saved model; OpenRouter presets get old Anthropic-native IDs rewritten."""
    raw = str(data.get("ai_model", _DEFAULT_AI_MODEL))
    if data.get("ai_provider", "openrouter") != "openrouter":
        return raw
    return _migrate_ai_model(raw)


def _migrate_ai_model(raw: str) -> str:
    """Rewrite Anthropic-native model IDs to the OpenRouter equivalent."""
    return LEGACY_MODEL_MIGRATION.get(raw, raw)


def _validate_trading_styles(styles: list[str]) -> None:
    unknown = set(styles) - _VALID_STYLES
    if unknown:
        raise PresetValidationError(
            f"Unknown trading style(s): {sorted(unknown)}. "
            f"Valid values: {sorted(_VALID_STYLES)}."
        )


def _validate_composite(preset: Preset) -> None:
    group_ids = [g.group_id for g in preset.groups]
    if len(group_ids) != len(set(group_ids)):
        duplicates = [gid for gid in set(group_ids) if group_ids.count(gid) > 1]
        raise PresetValidationError(
            f"Composite preset has duplicate group IDs: {duplicates}"
        )
    for group in preset.groups:
        for ref in group.screeners:
            if not ref.screener_id or not ref.screener_id.strip():
                raise PresetValidationError(
                    f"screener_id must not be empty in group '{group.group_id}'."
                )


def _validate_weighted(preset: Preset) -> None:
    if preset.threshold is None:
        raise PresetValidationError(
            "Weighted preset requires a 'threshold' value in [0, 1]."
        )
    if not (0.0 <= preset.threshold <= 1.0):
        raise PresetValidationError(
            f"Weighted preset 'threshold' must be in [0, 1], got {preset.threshold}."
        )
    for ref in preset.screeners:
        if not ref.screener_id or not ref.screener_id.strip():
            raise PresetValidationError("screener_id must not be empty in weighted preset.")
    enabled = [r for r in preset.screeners if r.enabled and r.weight is not None]
    if enabled:
        total = sum(r.weight for r in enabled)  # type: ignore[misc]
        if not (0.95 <= total <= 1.05):
            raise PresetValidationError(
                f"Weighted preset enabled screener weights should sum to ~1.0, got {total:.4f}."
            )
