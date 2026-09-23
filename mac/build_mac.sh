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
# 首次打开说明：写进 dmg，让拿到安装包的人自己看得懂怎么放行
write_firstrun_note() {
  cat > "$1" <<'NOTE'
科研数据归档助手 —— 首次打开说明
==================================

这个应用没有购买 Apple 开发者证书做「公证」，所以 macOS 第一次会拦它。
这是正常的，不是因为文件坏了。按下面任一种方式放行，只需一次。

方式一（推荐，不用敲命令）
  1. 先按正常流程把「科研数据归档助手」拖进「应用程序」文件夹
  2. 双击打开它，会弹出「无法打开 / 无法验证开发者」的提示
  3. 点「完成」，然后打开  系统设置 → 隐私与安全性
  4. 往下滚到「安全性」一栏，会看到「已阻止使用"科研数据归档助手"…」
  5. 点旁边的「仍要打开」，再确认一次「仍要打开」，输入开机密码
  6. 之后就能像正常软件一样双击打开了

方式二（熟悉终端的话，一条命令搞定）
  打开「终端」，粘贴执行：

      xattr -cr "/Applications/科研数据归档助手.app"

  然后双击即可。

注意
  · macOS 15 (Sequoia) 及以后，Apple 取消了「右键 → 打开」这个老办法，
    所以别再用右键了，请走上面方式一或方式二。
  · 应用本身不含联网、上传等行为，数据全部在本机处理。

系统要求
  · Apple Silicon 机器请用文件名带 arm64 的安装包
  · Intel 机器请用文件名带 x86_64 的安装包
  · 建议 macOS 12 及以上
NOTE
}

if [ "$SKIP_DMG" != "1" ]; then
  echo "== 生成 dmg"
  # 做一个标准的分发目录：App + 指向 /Applications 的软链 + 首次打开说明，
  # 用户打开 dmg 后直接把 App 拖进去即可。
  STAGE="dist-mac/.dmg-stage"
  rm -rf "$STAGE"
  mkdir -p "$STAGE"
  cp -R "$APP_PATH" "$STAGE/"
  ln -s /Applications "$STAGE/Applications"
  write_firstrun_note "$STAGE/首次打开请看这里.txt"
  rm -f "dist-mac/$APP_NAME.dmg"
  hdiutil create -volname "$APP_NAME" -srcfolder "$STAGE" \
                 -ov -format UDZO "dist-mac/$APP_NAME.dmg"
  rm -rf "$STAGE"
  echo "== 生成: dist-mac/$APP_NAME.dmg"
fi

# 单独再放一份说明到 dist-mac/，方便连同 zip 一起转发
write_firstrun_note "dist-mac/首次打开请看这里.txt"

cat <<'EOT'

------------------------------------------------------------------
完成。

首次打开若被 Gatekeeper 拦下（提示"无法验证开发者"），任选一种：
  A. 系统设置 → 隐私与安全性 → 往下滚到「安全性」→ 点「仍要打开」
     （macOS 15 起 Apple 已取消"右键 → 打开"这个老办法，别再用右键）
  B. 终端执行： xattr -cr "/Applications/科研数据归档助手.app"

dmg 里已附《首次打开请看这里.txt》，转发给同事时对方照着做即可。
要彻底免掉这一步，需要在 Apple 开发者账号下做 codesign + notarize（见 README）。

跨平台一致性提示：分类名中的 "/" 会被替换为全角"／"，
这样 Windows 与 macOS 归档出来的目录名完全一致，便于同一份数据在两平台间流转。
------------------------------------------------------------------
EOT
