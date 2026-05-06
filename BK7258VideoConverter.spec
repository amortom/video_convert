# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['D:\\code\\convert\\gui_converter.py'],
    pathex=[],
    binaries=[],
    datas=[('TERMINAL_FORMAT_SPEC.md', '.'), (r'D:\tools\python\lib\site-packages\sv_ttk', 'sv_ttk')],
    hiddenimports=['sv_ttk'],
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
    name='BK7258VideoConverter',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='BK7258VideoConverter',
)
