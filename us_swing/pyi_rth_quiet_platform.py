"""
Module: MD-GUI-000.007.M01 — PyInstaller runtime hook
Parent SRD: SRD-GUI-000.007

Runs before the bundled setuptools hook, which would otherwise flash a console window.
"""
from us_swing.gui.quiet_platform import install

install()
