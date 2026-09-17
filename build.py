# -*- coding: utf-8 -*-
"""一键打包为单文件 EXE。"""
import os
import shutil
import sys
import time

import PyInstaller.__main__ as pyi

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

NAME = "科研数据归档助手"

EXCLUDES = [
    # 体积裁剪：仅保留 QtCore / QtGui / QtWidgets / QtSvg
    "PySide6.Qt3DAnimation", "PySide6.Qt3DCore", "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput", "PySide6.Qt3DLogic", "PySide6.Qt3DRender",
    "PySide6.QtBluetooth", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtDesigner", "PySide6.QtGraphs", "PySide6.QtHelp",
    "PySide6.QtHttpServer", "PySide6.QtLocation", "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets", "PySide6.QtNfc", "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    "PySide6.QtPositioning", "PySide6.QtQml", "PySide6.QtQuick",
    "PySide6.QtQuick3D", "PySide6.QtQuickControls2", "PySide6.QtQuickWidgets",
    "PySide6.QtRemoteObjects", "PySide6.QtScxml", "PySide6.QtSensors",
    "PySide6.QtSerialPort", "PySide6.QtSpatialAudio", "PySide6.QtSql",
    "PySide6.QtStateMachine", "PySide6.QtTest", "PySide6.QtTextToSpeech",
    "PySide6.QtUiTools", "PySide6.QtVirtualKeyboard", "PySide6.QtWebChannel",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineQuick",
    "PySide6.QtWebEngineWidgets", "PySide6.QtWebSockets", "PySide6.QtNetworkAuth",
    "PySide6.QtSvgWidgets", "PySide6.QtConcurrent",
    # Python 标准库裁剪
    "tkinter", "unittest", "pydoc", "doctest", "pdb", "lib2to3",
    "distutils", "setuptools", "pip", "test",
    # openpyxl 会可选地 import PIL（嵌图用）与 numpy，我们只导出纯文本台账，
    # 一并排除可省掉约 11MB；台账导出功能不受影响（已用 RDA_SELFTEST 验证）。
    "PIL", "numpy", "pandas", "matplotlib", "scipy", "IPython",
]

args = [
    "app.py",
    f"--name={NAME}",
    "--onefile",
    "--windowed",
    "--noconfirm",
    "--icon=app.ico",
    "--add-data=app.ico;.",
    "--add-data=app.png;.",
    "--distpath=out",
    "--workpath=wbuild",
    "--specpath=.",
    "--log-level=WARN",
] + [f"--exclude-module={m}" for m in EXCLUDES]

# 不做任何删除操作（部分受限环境会拦截删除），直接输出到全新目录
pyi.run(args)

src = os.path.join("out", NAME + ".exe")
final_dir = "dist"
final = os.path.join(final_dir, NAME + ".exe")
os.makedirs(final_dir, exist_ok=True)


def _copy_over(a: str, b: str, tries: int = 8, delay: float = 1.0):
    """覆盖写入最终产物；若目标被占用（软件正在运行 / 被杀软扫描）则重试。"""
    err = ""
    for _ in range(tries):
        try:
            shutil.copyfile(a, b)          # 覆盖写，不删除
            return True, ""
        except OSError as e:
            err = f"{type(e).__name__}: {e}"
            time.sleep(delay)
    return False, err


print("=" * 60)
if os.path.isfile(src):
    ok, err = _copy_over(src, final)
    if ok:
        print("BUILD OK ->", os.path.abspath(final),
              f"{os.path.getsize(final) / 1024 / 1024:.1f} MB")
    else:
        print("BUILD PARTIAL ->", os.path.abspath(src),
              f"{os.path.getsize(src) / 1024 / 1024:.1f} MB")
        print("!! 无法覆盖 dist/ 下的旧文件，它正被其他进程占用（通常是软件还在运行）。")
        print("   请关闭正在运行的软件后，把上面的新文件手动复制到 dist/ 覆盖，")
        print("   或直接重新执行 build.py。")
        print("   原始错误：", err)
        sys.exit(2)
else:
    print("BUILD FAILED")
    sys.exit(1)
