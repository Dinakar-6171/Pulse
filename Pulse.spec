# PyInstaller onedir release spec for Pulse on Windows.
from pathlib import Path
import os

ROOT = Path(SPECPATH)
DEBUG_BUILD = os.environ.get("PULSE_DEBUG_BUILD", "").lower() in {"1", "true", "yes"}

analysis = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(ROOT / "assets"), "assets")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "unittest"],
    noarchive=False,
)

pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="Pulse",
    debug=DEBUG_BUILD,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=DEBUG_BUILD,
    disable_windowed_traceback=not DEBUG_BUILD,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "assets" / "logo.ico"),
)

collection = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Pulse",
)
