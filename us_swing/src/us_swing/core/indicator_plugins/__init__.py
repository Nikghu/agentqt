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

__all__ = ["CheckReport", "PluginSpec", "check_file", "frame_source"]
