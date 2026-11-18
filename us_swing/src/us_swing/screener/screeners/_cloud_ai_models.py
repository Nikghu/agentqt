"""
Module: MD-SCR-013.001.M19 — Cloud AI model registry.
Parent SRD: SRD-SCR-013.001
"""
from __future__ import annotations

from typing import Final

DEFAULT_MODEL: Final[str] = "anthropic/claude-haiku-4-5"
OPENROUTER_BASE: Final[str] = "https://openrouter.ai/api/v1"
ENV_API_KEY: Final[str] = "OPENROUTER_API_KEY"

# Top paid models by OpenRouter usage (April 2026 rankings) — (display_label, openrouter_model_id, supports_tool_use).
MODEL_PRESETS: Final[list[tuple[str, str, bool]]] = [
    ("Gemini 3 Flash    (fast, user pick)",      "google/gemini-3-flash-preview",     True),
    # Top 5 by usage
    ("Kimi K2.6         (#1 usage, balanced)",   "moonshotai/kimi-k2",                True),
    ("Claude Sonnet 4.6 (#2 usage, balanced)",   "anthropic/claude-sonnet-4-6",       True),
    ("DeepSeek V3.2     (#3 usage, fast)",       "deepseek/deepseek-chat-v3-2",       True),
    ("Claude Opus 4.7   (#4 usage, reasoning)",  "anthropic/claude-opus-4-7",         True),
    ("Gemini Flash 2.5  (#5 usage, fast)",       "google/gemini-2.5-flash-preview",   True),
    # Cheapest paid
    ("LFM2-24B          (cheapest, $0.03/M in)", "liquid/lfm-2-24b-a2b",              False),
    ("Qwen3.5 Flash     (cheap, $0.065/M in)",   "qwen/qwen3.5-flash",                True),
    # Legacy / always-on
    ("Claude Haiku 4.5  (fast, cheap)",          "anthropic/claude-haiku-4-5",        True),
    ("GPT-4o mini       (fast, cheap)",          "openai/gpt-4o-mini",                True),
    ("GPT-4o            (balanced)",             "openai/gpt-4o",                     True),
]

# Top 5 free models by OpenRouter usage (April 2026 rankings) — (display_label, openrouter_model_id, supports_tool_use).
FREE_MODEL_PRESETS: Final[list[tuple[str, str, bool]]] = [
    ("Nemotron 3 Super  (#1 free, NVIDIA)",      "nvidia/nemotron-3-super-120b-a12b:free",    False),
    ("Hy3 Preview       (#2 free, Tencent)",     "tencent/hy3-preview:free",                  False),
    ("Ling-2.6-1T       (#3 free, 1T params)",   "inclusionai/ling-2.6-1t:free",              False),
    ("Ling-2.6-flash    (#4 free, fast)",        "inclusionai/ling-2.6-flash:free",           False),
    ("MiniMax M2.5      (#5 free, agentic)",     "minimax/minimax-m2.5:free",                 False),
]

# Combined registry: (tier, display_label, model_id, tool_use)
# tier is "Free" or "Paid"
ALL_MODEL_PRESETS: Final[list[tuple[str, str, str, bool]]] = (
    [("Paid", label, mid, tools) for label, mid, tools in MODEL_PRESETS] +
    [("Free", label, mid, tools) for label, mid, tools in FREE_MODEL_PRESETS]
)

# Legacy Anthropic-native model IDs → OpenRouter IDs (used by Preset.from_dict).
LEGACY_MODEL_MIGRATION: Final[dict[str, str]] = {
    "claude-haiku-4-5-20251001":  "anthropic/claude-haiku-4-5",
    "claude-sonnet-4-6-20251022": "anthropic/claude-sonnet-4-6",
}


def supports_tool_use(model_id: str) -> bool:
    """Return True if the model is in the curated list AND supports tool use.

    Unknown (custom) models default to True — let the API surface the failure
    rather than over-restrict power users.
    """
    for _, mid, tools in MODEL_PRESETS + FREE_MODEL_PRESETS:
        if mid == model_id:
            return tools
    return True
