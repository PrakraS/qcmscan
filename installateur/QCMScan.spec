# -*- mode: python ; coding: utf-8 -*-
# Recette PyInstaller : dossier autonome (Python + Qt + OpenCV inclus),
# sans console. Compilé par le workflow GitHub Actions, ou à la main :
#   pyinstaller installateur/QCMScan.spec --noconfirm

import os
import sys

from PyInstaller.utils.win32.versioninfo import (FixedFileInfo,
                                                 StringFileInfo,
                                                 StringStruct, StringTable,
                                                 VarFileInfo, VarStruct,
                                                 VSVersionInfo)

sys.path.insert(0, os.path.dirname(SPECPATH))
from qcmscan.version import __version__  # noqa: E402

# Métadonnées Windows de l'exécutable (Propriétés > Détails) : leur
# absence est un signal de suspicion pour les antivirus.
_nums = tuple(int(x) for x in __version__.split(".")) + (0,)
INFOS_VERSION = VSVersionInfo(
    ffi=FixedFileInfo(filevers=_nums, prodvers=_nums),
    kids=[
        StringFileInfo([StringTable("040C04B0", [
            StringStruct("CompanyName", "QCMScan (PrakraS)"),
            StringStruct("FileDescription",
                         "QCMScan - QCM papier à correction "
                         "automatique par scan"),
            StringStruct("FileVersion", __version__),
            StringStruct("ProductName", "QCMScan"),
            StringStruct("ProductVersion", __version__),
            StringStruct("LegalCopyright",
                         "PrakraS - github.com/PrakraS/qcmscan"),
            StringStruct("OriginalFilename", "QCMScan.exe"),
        ])]),
        VarFileInfo([VarStruct("Translation", [1036, 1200])]),
    ])

a = Analysis(
    ["../main.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="QCMScan",
    icon="qcmscan.ico",
    version=INFOS_VERSION,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,          # UPX augmente les faux positifs antivirus
    name="QCMScan",
)
