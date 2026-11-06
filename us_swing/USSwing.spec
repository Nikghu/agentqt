# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

a = Analysis(
    ['run_gui.py'],
    pathex=['src'],
    binaries=[],
    datas=[('assets', 'assets'), ('src/us_swing/gui/resources', 'us_swing/gui/resources'),
           ('src/us_swing/market/employees', 'us_swing/market/employees')],
    hiddenimports=['talib.stream',
                   # loaded by import path in core/desk_steps.py
                   'us_swing.market.step', 'us_swing.market.sector_step',
                   'us_swing.market.idea_step', 'us_swing.market.proof',
                   'us_swing.desk.employees_step', 'us_swing.market.regime_view',
                   'us_swing.market.sector_view', 'us_swing.market.setup_review',
                   'us_swing.market.risk_check', 'us_swing.market.lead_brief',
                   # the desk router imports LangGraph when it first runs a graph
                   *collect_submodules('langgraph'), *collect_submodules('langchain_core')],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['pyi_rth_quiet_platform.py'],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='USSwing',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['F:\\USMarket_Backtesting\\installer\\assets\\icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='USSwing',
)
