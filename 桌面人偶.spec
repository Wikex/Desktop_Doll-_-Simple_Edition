# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=collect_data_files('rapidocr_onnxruntime') + [
        ('app_icon.ico', '.'),
        ('qt.conf', '.'),
        ('config.json', '.'),
        ('skins', 'skins'),
    ],
    hiddenimports=[
        'win32com.client',
        'pythoncom',
        'pywintypes',
        'cv2',
        'numpy',
        'mss',
        'uiautomation',
        'comtypes',
        'PIL.Image',
        'PIL.ImageGrab',
        'psutil',
    ],
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
    name='桌面人偶',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['app_icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='桌面人偶',
)
