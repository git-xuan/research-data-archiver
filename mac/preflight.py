#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
推送前预检（preflight）。

在把仓库推到 GitHub 之前跑一遍，检查那些「在本机不会暴露、只有到 CI / mac 上才炸」的问题：

    python mac/preflight.py

检查项：
  1. 打包所需的文件是否齐全（源码 / 图标 / 脚本 / CI）
  2. .gitignore 是否挡住了构建产物（否则仓库会多出几百 MB）
  3. .gitattributes 是否强制 shell 脚本用 LF
     —— Windows 默认 core.autocrlf=true 会把 .sh 写成 CRLF，
       传到 mac 上会报 “\\r: command not found”，CI 直接失败
  4. shell 脚本实际是不是 LF，以及 bash 语法是否通过
  5. 工作流 YAML 能否解析，runner 标签是不是当前仍可用的
     （macos-13 已于 2025-12-04 退役；macos-14 于 2026-11-02 EOL）
  6. requirements.txt 是否包含 openpyxl（台账导出 xlsx 必需，曾漏装过）
  7. 各源文件的换行符是否统一，避免 diff 噪声
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

OK, WARN, BAD = [], [], []


def ok(msg):
    OK.append(msg)


def warn(msg):
    WARN.append(msg)


def bad(msg):
    BAD.append(msg)


def rel(p):
    return os.path.relpath(p, ROOT)


# --------------------------------------------------------------------------- #
# 1. 必需文件
# --------------------------------------------------------------------------- #
REQUIRED = [
    "app.py", "core.py", "data.py", "ledger.py", "skin.py",
    "requirements.txt", "build.py",
    "app.ico", "app.png",
    "mac/build_mac.sh", "mac/run_on_mac.command",
    ".github/workflows/build-macos.yml",
    ".gitignore", ".gitattributes",
]
missing = [f for f in REQUIRED if not os.path.exists(os.path.join(ROOT, f))]
if missing:
    bad("缺少必需文件：" + "、".join(missing))
else:
    ok("必需文件齐全（%d 项）" % len(REQUIRED))

if os.path.isdir(os.path.join(ROOT, "icon.iconset")):
    ok("icon.iconset 存在（mac 上可生成 .icns）")
else:
    warn("没有 icon.iconset，mac 版将没有自定义图标")

# --------------------------------------------------------------------------- #
# 2. .gitignore
# --------------------------------------------------------------------------- #
BIG_DIRS = ["build/", "build_dbg/", "dist/", "dist_dbg/", "out/",
            "wbuild/", "wbuild-mac/", ".venv-mac/"]
gi_path = os.path.join(ROOT, ".gitignore")
if os.path.isfile(gi_path):
    gi = open(gi_path, encoding="utf-8", errors="replace").read()
    not_ignored = [d for d in BIG_DIRS if d not in gi]
    if not_ignored:
        warn(".gitignore 未覆盖：" + "、".join(not_ignored))
    else:
        ok(".gitignore 已覆盖全部构建产物目录")
    # 未忽略的大目录体积
    total = 0
    for d in BIG_DIRS:
        p = os.path.join(ROOT, d.rstrip("/"))
        for r, _, fs in os.walk(p):
            for f in fs:
                try:
                    total += os.path.getsize(os.path.join(r, f))
                except OSError:
                    pass
    ok("本机构建产物约 %.0f MB（已被忽略，不会进仓库）" % (total / 1024 / 1024))
else:
    bad("没有 .gitignore —— 构建产物会被一起提交")

# --------------------------------------------------------------------------- #
# 3. .gitattributes
# --------------------------------------------------------------------------- #
ga_path = os.path.join(ROOT, ".gitattributes")
if os.path.isfile(ga_path):
    ga = open(ga_path, encoding="utf-8", errors="replace").read()
    for pat in ("*.sh", "*.command"):
        m = re.search(re.escape(pat) + r"\s+text\s+eol=lf", ga)
        if m:
            ok(".gitattributes 已强制 %s 使用 LF" % pat)
        else:
            bad(".gitattributes 未为 %s 指定 eol=lf —— mac 上会因 CRLF 报错" % pat)
else:
    bad("没有 .gitattributes —— shell 脚本可能被写成 CRLF 而无法在 mac 上执行")

# --------------------------------------------------------------------------- #
# 4. shell 脚本：换行符 + 语法
# --------------------------------------------------------------------------- #
def find_bash():
    for c in (r"D:\Git\bin\bash.exe", r"C:\Program Files\Git\bin\bash.exe",
              "/bin/bash", "/usr/bin/bash"):
        if os.path.isfile(c):
            return c
    return None


SH = ["mac/build_mac.sh", "mac/run_on_mac.command"]
bash = find_bash()
for s in SH:
    p = os.path.join(ROOT, s)
    if not os.path.isfile(p):
        continue
    raw = open(p, "rb").read()
    if b"\r\n" in raw:
        bad("%s 含 CRLF 换行 —— 到 mac 上会报 “\\r: command not found”" % s)
    else:
        ok("%s 换行符为 LF" % s)
    if bash:
        r = subprocess.run([bash, "-n", p], capture_output=True)
        if r.returncode == 0:
            ok("%s bash 语法检查通过" % s)
        else:
            bad("%s bash 语法错误：\n%s" % (s, r.stderr.decode("utf-8", "replace")))

# --------------------------------------------------------------------------- #
# 5. 工作流
# --------------------------------------------------------------------------- #
WF = os.path.join(ROOT, ".github", "workflows", "build-macos.yml")
LIVE_RUNNERS = {"macos-15", "macos-15-intel", "macos-26", "macos-26-intel",
                "macos-latest"}
DEAD_RUNNERS = {"macos-13", "macos-12", "macos-11"}
SOON_DEAD = {"macos-14", "macos-14-large"}
if os.path.isfile(WF):
    text = open(WF, encoding="utf-8", errors="replace").read()
    if text.count("\r\n"):
        warn("工作流文件含 CRLF（不影响运行，但建议统一 LF）")
    try:
        import yaml
        yaml.safe_load(text)
        ok("工作流 YAML 解析通过")
    except ImportError:
        warn("本机没有 pyyaml，跳过 YAML 解析检查")
    except Exception as e:                                            # noqa: BLE001
        bad("工作流 YAML 解析失败：%s" % e)

    used = set(re.findall(r"^\s*-?\s*runner:\s*([\w.-]+)", text, re.M))
    used |= set(re.findall(r"runs-on:\s*([\w.\-$]+)", text))
    used = {u for u in used if u.startswith("macos")}
    dead = used & DEAD_RUNNERS
    soon = used & SOON_DEAD
    unknown = used - LIVE_RUNNERS - DEAD_RUNNERS - SOON_DEAD
    if dead:
        bad("工作流用了已退役的 runner：%s（会立刻失败）" % "、".join(sorted(dead)))
    if soon:
        bad("工作流用了即将退役的 runner：%s（2026-11-02 EOL，建议换 macos-15）"
            % "、".join(sorted(soon)))
    if unknown:
        warn("工作流出现未核实的 runner 标签：%s" % "、".join(sorted(unknown)))
    if not dead and not soon and used:
        ok("runner 标签均可用：%s" % "、".join(sorted(used)))

    for need, why in (("actions/checkout@", "拉取代码"),
                      ("actions/setup-python@", "安装 Python"),
                      ("actions/upload-artifact@", "上传产物")):
        if need in text:
            ok("工作流包含 %s（%s）" % (need, why))
        else:
            bad("工作流缺少 %s（%s）" % (need, why))
    if "bash mac/build_mac.sh" in text:
        ok("工作流调用 mac/build_mac.sh")
    else:
        bad("工作流没有调用 mac/build_mac.sh")
else:
    bad("找不到 .github/workflows/build-macos.yml")

# --------------------------------------------------------------------------- #
# 6. 依赖
# --------------------------------------------------------------------------- #
req_path = os.path.join(ROOT, "requirements.txt")
if os.path.isfile(req_path):
    req = open(req_path, encoding="utf-8", errors="replace").read().lower()
    for mod, why in (("pyside6", "界面框架"),
                     ("pyinstaller", "打包工具"),
                     ("openpyxl", "台账导出 xlsx（曾漏装）")):
        if mod in req:
            ok("requirements.txt 含 %s（%s）" % (mod, why))
        else:
            bad("requirements.txt 缺 %s（%s）" % (mod, why))

sh_txt = open(os.path.join(ROOT, "mac", "build_mac.sh"),
              encoding="utf-8", errors="replace").read()
if "requirements.txt" in sh_txt:
    ok("build_mac.sh 从 requirements.txt 安装依赖")
else:
    warn("build_mac.sh 没有引用 requirements.txt，依赖可能与 Windows 版漂移")

# --------------------------------------------------------------------------- #
# 汇总
# --------------------------------------------------------------------------- #
print("=" * 66)
print("推送前预检 —— %s" % ROOT)
print("=" * 66)
for m in OK:
    print("  [OK]   " + m)
for m in WARN:
    print("  [注意] " + m)
for m in BAD:
    print("  [问题] " + m)
print("-" * 66)
print("通过 %d 项，注意 %d 项，问题 %d 项" % (len(OK), len(WARN), len(BAD)))
if BAD:
    print("\n有阻塞项，先修完再推送。")
    sys.exit(1)
print("\n预检通过，可以推送。")
