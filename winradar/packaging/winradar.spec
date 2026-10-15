# -*- mode: python -*-
# Đóng gói WinRadar thành thư mục chạy độc lập:  pyinstaller packaging/winradar.spec
# Muốn kèm sẵn Chromium: chạy "PLAYWRIGHT_BROWSERS_PATH=0 playwright install chromium" TRƯỚC khi đóng gói.
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = SPECPATH + "/.."

a = Analysis(
    [ROOT + "/packaging/launcher.py"],
    pathex=[ROOT],
    datas=[(ROOT + "/winradar/static", "winradar/static")] + collect_data_files("playwright"),
    hiddenimports=collect_submodules("uvicorn") + collect_submodules("winradar"),
    excludes=["tkinter", "pytest"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="WinRadar", console=True, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="WinRadar", upx=False)
