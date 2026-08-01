# -*- mode: python ; coding: utf-8 -*-
import tomllib
from pathlib import Path

from PyInstaller.utils.hooks import collect_all
from PyInstaller.utils.hooks import collect_data_files

PROJECT_NAME = "24K-GoldTracker"
PROJECT_VERSION = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
BUILD_NAME = f"{PROJECT_NAME}-{PROJECT_VERSION}"

datas = []
binaries = []
hiddenimports = ['matplotlib.backends.backend_tkagg', 'openpyxl.cell._writer']
datas += [('assets/gold_tracker.png', 'assets')]
datas += collect_data_files('certifi')
datas += collect_data_files('matplotlib')
tmp_ret = collect_all('yfinance')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['build_entry.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
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
    name=BUILD_NAME,
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
    icon="assets/gold_tracker.ico",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=BUILD_NAME,
)
