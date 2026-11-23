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
from us_swing.core.indicator_plugins._guard import GUARD, PluginCallError, PluginGuard
from us_swing.core.indicator_plugins._registry import (
    REGISTRY,
    IndicatorRegistry,
    PluginStatus,
    builtin_names,
    plugin_dir,
)
from us_swing.core.indicator_plugins._runner import (
    NoCandleData,
    PluginArgError,
    last_value,
    run_plugin,
    values_from_args,
)

__all__ = [
    "GUARD", "REGISTRY", "CheckReport", "IndicatorRegistry", "NoCandleData", "PluginArgError",
    "PluginCallError", "PluginGuard", "PluginSpec", "PluginStatus", "builtin_names",
    "check_file", "frame_source", "last_value", "plugin_dir", "run_plugin", "values_from_args",
]
