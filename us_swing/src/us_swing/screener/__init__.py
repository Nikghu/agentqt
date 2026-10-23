"""us_swing.screener — Preset-based screener framework (v2).

M15: Package init — registers all built-in screeners at import time and
exposes the migrate_v1_presets() convenience function for first-launch migration.
"""
# ---------------------------------------------------------------------------
# Core data model + protocol + registry
# ---------------------------------------------------------------------------
from us_swing.screener.base import (
    PreFilterError,
    PresetAccessDenied,
    PresetError,
    PresetNotFoundError,
    PresetValidationError,
    Screener,
    ScreenerError,
    ScreenerExecutionError,
    ScreenerNotFoundError,
    ScreenerValidationError,
)
from us_swing.screener.preset import GroupLogic, Preset, PresetType, ScreenerGroup, ScreenerRef
from us_swing.screener.registry import ScreenerRegistry

# ---------------------------------------------------------------------------
# Orchestration + management
# ---------------------------------------------------------------------------
from us_swing.screener.executor import PresetExecutor
from us_swing.screener.manager import PresetManager
from us_swing.screener.scheduler import ScreenerScheduler
from us_swing.screener.storage import APIUsageTracker, FeatureCache, ScreenerResultsStorage
from us_swing.screener.utils import PreFilter

# ---------------------------------------------------------------------------
# Built-in screener plugins
# ---------------------------------------------------------------------------
from us_swing.screener.screeners.acc_dist import AccDistScreener
from us_swing.screener.screeners.cloud_ai import CloudAIScreener
from us_swing.screener.screeners.indicator import IndicatorScreener
from us_swing.screener.screeners.llm_local import LLMLocalScreener
from us_swing.screener.screeners.mcp import MCPScreener
from us_swing.screener.screeners.ml import MLScreener
from us_swing.screener.screeners.price_action import PriceActionScreener

# ---------------------------------------------------------------------------
# Register built-in screeners (SRD-SCR-009.001 — runs once at import time).
# Registry ID "llm_claude_ranking" is preserved for backward compatibility
# with presets persisted before the OpenRouter migration.
# ---------------------------------------------------------------------------
ScreenerRegistry.register("indicator_composite", IndicatorScreener)
ScreenerRegistry.register("ml_ensemble_v3", MLScreener)
ScreenerRegistry.register("llm_claude_ranking", CloudAIScreener)
ScreenerRegistry.register("llm_local_mistral", LLMLocalScreener)
ScreenerRegistry.register("price_action", PriceActionScreener)
ScreenerRegistry.register("mcp", MCPScreener)
ScreenerRegistry.register("acc_dist", AccDistScreener)


# ---------------------------------------------------------------------------
# Migration convenience (SRD-SCR-009.001)
# ---------------------------------------------------------------------------
def migrate_v1_presets(manager: PresetManager, user_id: str, v1_config: dict) -> Preset:
    """Migrate a single user's v1 ScreenerConfig to a v2 Preset.

    Delegates to PresetManager.migrate_v1_presets(). Call once per user on
    first v2 launch; subsequent calls are safe (idempotent file writes).
    """
    return manager.migrate_v1_presets(user_id=user_id, v1_config=v1_config)


__all__ = [
    # Data model
    "Preset",
    "PresetType",
    "ScreenerRef",
    "ScreenerGroup",
    "GroupLogic",
    # Protocol
    "Screener",
    # Registry
    "ScreenerRegistry",
    # Orchestration
    "PresetExecutor",
    "PresetManager",
    "ScreenerScheduler",
    # Storage
    "ScreenerResultsStorage",
    "FeatureCache",
    "APIUsageTracker",
    # Utilities
    "PreFilter",
    # Plugins
    "IndicatorScreener",
    "MLScreener",
    "CloudAIScreener",
    "LLMLocalScreener",
    "PriceActionScreener",
    "MCPScreener",
    # Migration
    "migrate_v1_presets",
    # Errors
    "ScreenerError",
    "ScreenerNotFoundError",
    "ScreenerValidationError",
    "PresetError",
    "PresetValidationError",
    "PresetAccessDenied",
    "PresetNotFoundError",
    "ScreenerExecutionError",
    "PreFilterError",
]
