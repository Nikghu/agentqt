"""
Module: MD-EXE-022.005.M02 — custom indicator plugins
Parent SRD: SRD-EXE-022.005

Check, registry, runner and guard for user indicators written with ``usswing``.
Nothing here imports the execution package at load time, so the engine can use it.
"""
from us_swing.core.indicator_plugins._check import (
    CheckReport,
    PluginSpec,
    check_file,
    frame_source,
)
from us_swing.core.indicator_plugins._registry import (
    REGISTRY,
    IndicatorRegistry,
    PluginStatus,
    builtin_names,
    plugin_dir,
)

__all__ = [
    "REGISTRY", "CheckReport", "IndicatorRegistry", "PluginSpec", "PluginStatus",
    "builtin_names", "check_file", "frame_source", "plugin_dir",
]
