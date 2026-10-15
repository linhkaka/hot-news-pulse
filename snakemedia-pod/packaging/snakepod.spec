# -*- mode: python -*-
# Đóng gói SNAKEMEDIA POD thành thư mục chạy độc lập:  pyinstaller packaging/snakepod.spec
# Muốn kèm sẵn Chromium: chạy "PLAYWRIGHT_BROWSERS_PATH=0 playwright install chromium" TRƯỚC khi đóng gói.
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = SPECPATH + "/.."

a = Analysis(
    [ROOT + "/packaging/launcher.py"],
    pathex=[ROOT],
    datas=[(ROOT + "/snakepod/static", "snakepod/static")] + collect_data_files("playwright"),
    hiddenimports=collect_submodules("uvicorn") + collect_submodules("snakepod"),
    excludes=["tkinter", "pytest"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="SnakemediaPOD", console=True, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="SnakemediaPOD", upx=False)
