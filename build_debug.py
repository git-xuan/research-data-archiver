# -*- coding: utf-8 -*-
"""控制台调试版打包：用于捕获冻结后的启动异常。"""
import os
import shutil

import PyInstaller.__main__ as pyi

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

NAME = "rda_debug"
EXCLUDES = [
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
    "tkinter", "unittest", "pydoc", "doctest", "pdb", "lib2to3",
    "distutils", "setuptools", "pip", "test",
]

args = [
    "app.py",
    f"--name={NAME}",
    "--onefile",
    "--console",
    "--noconfirm",
    "--clean",
    "--add-data=app.ico;.",
    "--distpath=dist_dbg",
    "--workpath=build_dbg",
    "--specpath=.",
    "--log-level=WARN",
] + [f"--exclude-module={m}" for m in EXCLUDES]

for d in ("build_dbg", "dist_dbg"):
    shutil.rmtree(d, ignore_errors=True)

pyi.run(args)
print("DEBUG BUILD DONE")
