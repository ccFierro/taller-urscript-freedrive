
# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Taller_FreeDrive (GUI + UR RTDE)
# Usage:
#   pyinstaller Taller_FreeDrive.spec
#
# Output:
#   dist/Taller_FreeDrive/  (one-folder build)
#
# Notes:
# - Includes data files: fondo.png, control_loop_configuration.xml
# - Collects package data/binaries for: rtde, ttkbootstrap, PIL
# - Windowed build (no console). Change 'console=True' if you want a console.

import sys
from PyInstaller.utils.hooks import collect_all

# Collect package data/binaries/hidden imports
rtde_datas, rtde_binaries, rtde_hidden = collect_all('rtde')
ttk_datas, ttk_binaries, ttk_hidden = collect_all('ttkbootstrap')
pil_datas, pil_binaries, pil_hidden = collect_all('PIL')

block_cipher = None

a = Analysis(
    ['Taller_FreeDrive.py'],
    pathex=[],
    binaries=rtde_binaries + ttk_binaries + pil_binaries,
    datas=rtde_datas + ttk_datas + pil_datas + [
        ('fondo.png', '.'),
        ('control_loop_configuration.xml', '.'),
        # If you have other static assets, add them here as ('src_path','dest_relpath')
    ],
    hiddenimports=rtde_hidden + ttk_hidden + pil_hidden + [
        'ttkbootstrap.constants',
        'PIL.ImageTk',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='Taller_FreeDrive',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,   # GUI app
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,       # put a path to an .ico if desired
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='Taller_FreeDrive'
)
