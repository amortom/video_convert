# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['D:\\code\\convert\\gui_converter.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('TERMINAL_FORMAT_SPEC.md', '.'),
        (r'D:\tools\python\lib\site-packages\customtkinter', 'customtkinter/'),
        (r'D:\tools\python\lib\site-packages\tkinterdnd2', 'tkinterdnd2/')
    ],
    hiddenimports=['sv_ttk', 'tkinterdnd2', 'customtkinter', 'mp4_converter', 'cv2', 'PIL'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['scipy', 'matplotlib'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='BK7258VideoConverter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
