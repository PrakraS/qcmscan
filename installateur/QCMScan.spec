# -*- mode: python ; coding: utf-8 -*-
# Recette PyInstaller : dossier autonome (Python + Qt + OpenCV inclus),
# sans console. Compilé par le workflow GitHub Actions, ou à la main :
#   pyinstaller installateur/QCMScan.spec --noconfirm

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
