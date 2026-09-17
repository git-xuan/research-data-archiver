#!/bin/bash
# ---------------------------------------------------------------------------
# 科研数据归档助手 —— macOS 免打包直接运行
#
# 双击本文件即可（若提示无法打开，先在终端执行：chmod +x mac/*.sh mac/*.command）
# 首次运行会自动创建虚拟环境并安装 PySide6（约 1~2 分钟），之后每次秒开。
#
# 想生成可分发的 .app / .dmg，请改用：bash mac/build_mac.sh
# ---------------------------------------------------------------------------
cd "$(dirname "$0")/.." || exit 1
ROOT="$(pwd)"

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "没有找到 python3。请先安装 Python 3.10 以上版本：https://www.python.org/downloads/macos/"
  echo "（或执行： brew install python）"
  read -r -p "按回车键退出…" _
  exit 1
fi

VENV=".venv-mac"
if [ ! -d "$VENV" ]; then
  echo "== 首次运行：创建虚拟环境"
  "$PYTHON" -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

if ! python -c "import PySide6" >/dev/null 2>&1; then
  echo "== 安装依赖（仅首次，约 1~2 分钟）…"
  python -m pip install --quiet --upgrade pip
  if [ -f requirements.txt ]; then
    python -m pip install --quiet -r requirements.txt
  else
    python -m pip install --quiet PySide6 openpyxl
  fi
fi

echo "== 启动 科研数据归档助手"
exec python app.py
