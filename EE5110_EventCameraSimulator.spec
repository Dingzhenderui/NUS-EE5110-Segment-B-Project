# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

ROOT = Path.cwd()

datas = [
    (str(ROOT / 'src' / 'event_camera_sim'), 'event_camera_sim'),
    (str(ROOT / 'assets'), 'assets'),
]
binaries = []
hiddenimports = [
    'cv2',
    'numpy',
    'h5py',
    'event_camera_sim',
    'PySide6',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'shiboken6',
]

# Collect h5py
h5_ret = collect_all('h5py')
datas += h5_ret[0]
binaries += h5_ret[1]
hiddenimports += h5_ret[2]

a = Analysis(
    [str(ROOT / 'run_app.py')],
    pathex=[str(ROOT / 'src')],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'pandas',
        'pytest',
        'setuptools',
        'pip',
        'PySide6.QtQml',
        'PySide6.QtQuick',
        'PySide6.QtDesigner',
        'PySide6.Qt3DCore',
        'PySide6.QtSpatialAudio',
        'PySide6.QtTest',
        'PySide6.QtHelp',
        'PySide6.QtBluetooth',
        'PySide6.QtNfc',
        'PySide6.QtPositioning',
        'PySide6.QtSensors',
        'PySide6.QtSerialPort',
        'PySide6.QtSql',
        'PySide6.QtWebChannel',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets',
    ],
    noarchive=False,
    optimize=0,
)

# Crucial binary/data filter:
# 1. Exclude Anaconda's outdated icu*.dll which conflicts with Windows 10/11 system icuuc.dll needed by Qt6Core.dll
# 2. Exclude QML and debug objects that exceed Windows MAX_PATH (260 chars)
def safe_entry(entry):
    path_str = str(entry[0]).lower()
    dest_str = str(entry[1]).lower()
    name = Path(entry[0]).name.lower()

    if name.startswith('icu') and name.endswith('.dll'):
        return False
    if 'qml' in path_str or 'qml' in dest_str:
        return False
    if 'objects-debug' in path_str or 'objects-debug' in dest_str:
        return False
    if len(str(ROOT / 'dist' / 'EventCameraSimulator' / '_internal' / entry[1])) > 240:
        return False
    return True

a.datas = [d for d in a.datas if safe_entry(d)]
a.binaries = [b for b in a.binaries if safe_entry(b)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='EventCameraSimulator',
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
    icon=str(ROOT / 'assets' / 'icon.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='EventCameraSimulator',
)
