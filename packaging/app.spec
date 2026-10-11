# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Icarus Server Mod Manager (onedir build).

Build from the project root:
    pyinstaller --noconfirm --clean --distpath packaging/dist --workpath packaging/build packaging/app.spec
"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

SPEC_DIR = Path(SPECPATH).resolve()
ROOT = SPEC_DIR.parent

datas = [(str(ROOT / "app.py"), "app")]
binaries = []
hiddenimports = collect_submodules("icarus_manager") + [
    "paramiko",
    "pyarrow.vendored.version",
]

for package in ("streamlit", "altair", "repak"):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

datas += copy_metadata("streamlit")

icon = None
if sys.platform == "win32":
    icon = str(SPEC_DIR / "icon.ico")
elif sys.platform == "darwin" and (SPEC_DIR / "icon.icns").is_file():
    icon = str(SPEC_DIR / "icon.icns")

analysis = Analysis(
    [str(SPEC_DIR / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "watchdog"],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="IcarusServerModManager",
    debug=False,
    strip=False,
    upx=False,
    console=True,
    icon=icon,
    version=str(SPEC_DIR / "version_info.txt") if sys.platform == "win32" else None,
)
collect = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="IcarusServerModManager",
)
