#!/bin/bash
# ---------------------------------------------------------------------------
# 科研数据归档助手 —— macOS 一键打包脚本
#
# 用法（在 macOS 上，于本项目根目录执行）：
#     bash mac/build_mac.sh
# 可选环境变量：
#     ARCH=universal2    # 同时支持 Intel 与 Apple Silicon（需 universal2 版 Python）
#     ARCH=arm64         # 仅 Apple Silicon
#     PYTHON=/usr/bin/python3
#     SKIP_DMG=1         # 只出 .app，不生成 .dmg
#
# 前置条件：
#   1) 已安装 Xcode 命令行工具（提供 iconutil / hdiutil）：
#        xcode-select --install
#   2) 已安装 Python 3.10+（python.org 版或 Homebrew 均可）
#
# 产物：
#   dist-mac/科研数据归档助手.app     ← 绿色应用，拖进「应用程序」即可
#   dist-mac/科研数据归档助手.dmg     ← 便于分发（除非 SKIP_DMG=1）
#
# 注意：PyInstaller 不是交叉编译器，.app 只能在 macOS 上生成，
#       且产物的 CPU 架构与构建机一致（或在 ARCH=universal2 时同时支持两者）。
# ---------------------------------------------------------------------------
set -euo pipefail

APP_NAME="科研数据归档助手"
BUNDLE_ID="cn.rdarchiver.app"
ARCH="${ARCH:-}"
PYTHON="${PYTHON:-python3}"
SKIP_DMG="${SKIP_DMG:-0}"

# 切到项目根目录（本脚本位于 mac/ 下）
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
echo "== 项目目录: $ROOT"

# 1) 虚拟环境 ---------------------------------------------------------------
VENV=".venv-mac"
if [ ! -d "$VENV" ]; then
  echo "== 创建虚拟环境"
  "$PYTHON" -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
python -m pip install --quiet --upgrade pip
echo "== 安装依赖（requirements.txt + pyinstaller）"
# 统一走 requirements.txt，保证与 Windows 版依赖一致。
# 特别注意 openpyxl：「数据台账」导出官方表结构 xlsx 必需，早先漏装过。
if [ -f requirements.txt ]; then
  python -m pip install --quiet -r requirements.txt
else
  python -m pip install --quiet PySide6 openpyxl
fi
python -m pip install --quiet pyinstaller

# 自检：确认关键依赖真的能导入，避免打出一个「功能残缺」的包
python - <<'PYCHK'
import importlib, sys
missing = []
for m in ("PySide6", "openpyxl"):
    try:
        importlib.import_module(m)
    except Exception as e:                                            # noqa: BLE001
        missing.append("%s (%s)" % (m, e))
if missing:
    sys.exit("!! 依赖自检失败，缺少：" + "、".join(missing))
print("== 依赖自检通过：PySide6 / openpyxl 均可导入")
PYCHK

# 2) 生成图标 ---------------------------------------------------------------
if [ -d "icon.iconset" ] && command -v iconutil >/dev/null 2>&1; then
  echo "== 由 icon.iconset 生成 app.icns"
  iconutil -c icns icon.iconset -o app.icns
fi

# 3) 打包 -------------------------------------------------------------------
ARGS=(
  app.py
  "--name=$APP_NAME"
  --windowed
  --onedir
  --noconfirm
  --clean
  "--osx-bundle-identifier=$BUNDLE_ID"
  --distpath=dist-mac
  --workpath=wbuild-mac
  --specpath=.
  --log-level=WARN
)
[ -f app.icns ] && ARGS+=("--icon=app.icns")
[ -f app.ico ]  && ARGS+=("--add-data=app.ico:.")
[ -f app.png ]  && ARGS+=("--add-data=app.png:.")
[ -n "$ARCH" ]  && ARGS+=("--target-architecture=$ARCH")

# 体积裁剪：只保留 QtCore / QtGui / QtWidgets / QtSvg
EXCLUDES=(
  Qt3DAnimation Qt3DCore Qt3DExtras Qt3DInput Qt3DLogic Qt3DRender
  QtBluetooth QtCharts QtDataVisualization QtDesigner QtGraphs QtHelp
  QtHttpServer QtLocation QtMultimedia QtMultimediaWidgets QtNfc
  QtOpenGL QtOpenGLWidgets QtPdf QtPdfWidgets QtPositioning QtQml QtQuick
  QtQuick3D QtQuickControls2 QtQuickWidgets QtRemoteObjects QtScxml QtSensors
  QtSerialPort QtSpatialAudio QtSql QtStateMachine QtTest QtTextToSpeech
  QtUiTools QtVirtualKeyboard QtWebChannel QtWebEngineCore QtWebEngineQuick
  QtWebEngineWidgets QtWebSockets QtNetworkAuth QtSvgWidgets QtConcurrent
)
for m in "${EXCLUDES[@]}"; do ARGS+=("--exclude-module=PySide6.$m"); done
for m in tkinter unittest pydoc doctest pdb lib2to3 distutils setuptools pip test; do
  ARGS+=("--exclude-module=$m")
done
# openpyxl 会「可选地」import PIL / numpy 用于嵌图，我们只导出纯文本台账，
# 排除掉可以显著减小体积（Windows 侧实测省约 11MB）。
for m in PIL numpy pandas matplotlib scipy IPython; do
  ARGS+=("--exclude-module=$m")
done

echo "== 开始打包（架构: ${ARCH:-本机}）"
pyinstaller "${ARGS[@]}"

APP_PATH="dist-mac/$APP_NAME.app"
[ -d "$APP_PATH" ] || { echo "!! 打包失败：未找到 $APP_PATH"; exit 1; }
echo "== 生成: $APP_PATH"

# 4) 生成 dmg（可选） -------------------------------------------------------
if [ "$SKIP_DMG" != "1" ]; then
  echo "== 生成 dmg"
  # 做一个标准的分发目录：App + 指向 /Applications 的软链，
  # 用户打开 dmg 后直接把 App 拖进去即可。
  STAGE="dist-mac/.dmg-stage"
  rm -rf "$STAGE"
  mkdir -p "$STAGE"
  cp -R "$APP_PATH" "$STAGE/"
  ln -s /Applications "$STAGE/Applications"
  rm -f "dist-mac/$APP_NAME.dmg"
  hdiutil create -volname "$APP_NAME" -srcfolder "$STAGE" \
                 -ov -format UDZO "dist-mac/$APP_NAME.dmg"
  rm -rf "$STAGE"
  echo "== 生成: dist-mac/$APP_NAME.dmg"
fi

cat <<'EOT'

------------------------------------------------------------------
完成。首次运行若被 Gatekeeper 拦下（提示"未验证的开发者"），任选一种：

  A. 右键点图标 → 打开 → 再点"打开"（只需一次）
  B. 终端执行： xattr -dr com.apple.quarantine "应用程序/科研数据归档助手.app"
  C. 正式分发请在 Apple 开发者账号下做 codesign + notarize

跨平台一致性提示：分类名中的 "/" 会被替换为全角"／"，
这样 Windows 与 macOS 归档出来的目录名完全一致，便于同一份数据在两平台间流转。
------------------------------------------------------------------
EOT
