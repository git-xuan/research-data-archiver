# -*- coding: utf-8 -*-
"""
科研数据归档助手 —— 核心逻辑层
负责：分类树读取、归档目录初始化、文件扫描与复制、抽样、归档索引与日志维护。
不依赖任何 GUI 库，可单独测试。
"""
from __future__ import annotations

import csv
import datetime as _dt
import json
import os
import random
import re
import shutil
import time
from collections import OrderedDict
from typing import Callable, Dict, List, Optional, Tuple

import data as _d

APP_NAME = "科研数据归档助手"
APP_VERSION = "1.0.0"
INDEX_DIR = "_归档索引"          # 存放在归档根目录下的系统数据目录
MANIFEST = "manifest.json"
LOG_CSV = "归档日志.csv"
README = "归档说明.md"

TREE = _d.TREE

# Windows 文件名非法字符 -> 全角等价字符（保持可读性）
_ILLEGAL = {
    "/": "／", "\\": "＼", ":": "：", "*": "＊",
    "?": "？", '"': "”", "<": "＜", ">": "＞", "|": "｜",
}
_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


# --------------------------------------------------------------------------- #
# 分类树
# --------------------------------------------------------------------------- #
def l1_list() -> List[str]:
    return list(TREE.keys())


def l2_list(l1: str) -> List[str]:
    return list(TREE.get(l1, {}).keys())


def l3_list(l1: str, l2: str) -> List[str]:
    return list(TREE.get(l1, {}).get(l2, {}).keys())


def l4_list(l1: str, l2: str, l3: str) -> List[str]:
    return list(TREE.get(l1, {}).get(l2, {}).get(l3, []))


def tree_counts() -> Tuple[int, int, int, int]:
    n1 = len(TREE)
    n2 = sum(len(v) for v in TREE.values())
    n3 = sum(len(x) for v in TREE.values() for x in v.values())
    n4 = sum(len(y) for v in TREE.values() for x in v.values() for y in x.values())
    return n1, n2, n3, n4


def safe_name(name: str) -> str:
    """把分类名转换为合法的 Windows 目录名。"""
    out = []
    for ch in name:
        out.append(_ILLEGAL.get(ch, ch))
    s = "".join(out).strip().rstrip(". ")
    if not s:
        s = "未命名"
    if s.upper() in _RESERVED:
        s += "_"
    return s


def plan_dirs(levels: int = 2) -> List[str]:
    """返回需要创建的相对目录列表。levels=2 -> 一级/二级。"""
    result: List[str] = []
    for l1, d2 in TREE.items():
        s1 = safe_name(l1)
        result.append(s1)
        for l2, d3 in d2.items():
            s2 = safe_name(l2)
            result.append(os.path.join(s1, s2))
            if levels >= 3:
                for l3 in d3.keys():
                    result.append(os.path.join(s1, s2, safe_name(l3)))
    return result


# --------------------------------------------------------------------------- #
# 归档目录初始化
# --------------------------------------------------------------------------- #
def check_empty_target(path: str) -> Tuple[bool, str]:
    """检查目标路径是否可用作归档根目录（不存在或为空目录）。"""
    p = os.path.abspath(path)
    if not p or p in (os.path.abspath(os.sep),):
        return False, "请选择有效的归档目标路径。"
    if os.path.exists(p):
        if not os.path.isdir(p):
            return False, "该路径已被文件占用，请选择文件夹或新的路径。"
        try:
            entries = os.listdir(p)
        except OSError as e:
            return False, f"无法读取该目录：{e}"
        # 允许「上次已初始化」的目录被识别为已初始化而非报错
        if entries:
            marker_ok = os.path.isdir(os.path.join(p, INDEX_DIR))
            return (False, "已初始化" if marker_ok else "目标文件夹不为空，请更换一个空文件夹或新路径。")
    return True, "可以初始化"


def is_initialized(root: str) -> bool:
    return os.path.isfile(os.path.join(root, INDEX_DIR, MANIFEST))


def init_archive(root: str, levels: int = 2,
                 progress: Optional[Callable[[int, int, str], None]] = None) -> dict:
    """按分类树在 root 下创建目录，并写入索引、日志、说明文件。"""
    root = os.path.abspath(root)
    dirs = plan_dirs(levels)
    os.makedirs(root, exist_ok=True)

    total = len(dirs)
    for i, rel in enumerate(dirs):
        os.makedirs(os.path.join(root, rel), exist_ok=True)
        if progress:
            progress(i + 1, total, rel)

    os.makedirs(os.path.join(root, INDEX_DIR), exist_ok=True)

    manifest = {
        "app": APP_NAME,
        "version": APP_VERSION,
        "created_at": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "root": root,
        "levels": levels,
        "counts": dict(zip(("l1", "l2", "l3", "l4"), tree_counts())),
        "folders": dirs,
        "renamed": {k: safe_name(k) for k in _all_class_names() if safe_name(k) != k},
        "archived": {},
    }
    _write_json(os.path.join(root, INDEX_DIR, MANIFEST), manifest)
    _ensure_log(root)
    _write_readme(root, manifest)
    return manifest


def _all_class_names():
    names = []
    for l1, d2 in TREE.items():
        names.append(l1)
        for l2, d3 in d2.items():
            names.append(l2)
            for l3, d4 in d3.items():
                names.append(l3)
                names.extend(d4)
    return names


def _write_json(path: str, obj) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def read_manifest(root: str) -> Optional[dict]:
    path = os.path.join(root, INDEX_DIR, MANIFEST)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _ensure_log(root: str) -> None:
    path = os.path.join(root, INDEX_DIR, LOG_CSV)
    if not os.path.isfile(path):
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["时间", "一级分类", "二级分类", "文件名", "大小(字节)",
                        "来源路径", "归档后路径", "结果", "说明"])


def append_log(root: str, rows: List[list]) -> None:
    if not rows:
        return
    _ensure_log(root)
    path = os.path.join(root, INDEX_DIR, LOG_CSV)
    with open(path, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerows(rows)


def _write_readme(root: str, manifest: dict) -> None:
    n1, n2, n3, n4 = tree_counts()
    lines = [
        f"# 归档目录说明",
        "",
        f"- 归档根目录：`{root}`",
        f"- 初始化时间：{manifest['created_at']}",
        f"- 分类层级：一级 + 二级（共 {n1} 个一级目录、{n2} 个二级目录）",
        f"- 参考分类树：一级 {n1} / 二级 {n2} / 三级 {n3} / 四级 {n4}",
        "",
        "## 目录结构",
        "",
        "```",
    ]
    for l1, d2 in TREE.items():
        lines.append(safe_name(l1))
        keys = list(d2.keys())
        for i, l2 in enumerate(keys):
            branch = "└──" if i == len(keys) - 1 else "├──"
            lines.append(f"{branch} {safe_name(l2)}")
    lines += [
        "```",
        "",
        "## 使用说明",
        "",
        f"1. 使用『科研数据归档助手』的 **文件归档** 页面，把科研数据复制到对应的二级分类目录中（仅复制，不删除原始文件）。",
        f"2. 使用 **归档自查** 页面按比例随机抽样复核，导出问题文件清单。",
        f"3. `{INDEX_DIR}/` 为本软件的索引目录，保存归档清单与日志，请勿手工修改。",
        "",
        "## 分类含义（三级 / 四级参考）",
        "",
    ]
    for l1, d2 in TREE.items():
        lines.append(f"### {l1}")
        for l2, d3 in d2.items():
            if not d3:
                lines.append(f"- **{l2}**")
                continue
            lines.append(f"- **{l2}**")
            for l3, d4 in d3.items():
                if d4:
                    lines.append(f"  - {l3}：{'、'.join(d4)}")
                else:
                    lines.append(f"  - {l3}")
        lines.append("")
    with open(os.path.join(root, README), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# --------------------------------------------------------------------------- #
# 系统垃圾文件过滤
#
# 这些是操作系统或 Office 自动生成的，不是科研数据本体，不该出现在
# 「待归档候选」和「归档自查」列表里（macOS 上 .DS_Store 尤其泛滥）。
# --------------------------------------------------------------------------- #
JUNK_NAMES = {
    # macOS
    ".DS_Store", ".localized", "Icon\r", ".apdisk",
    # Windows
    "Thumbs.db", "ehthumbs.db", "desktop.ini",
    # 通用
    "Desktop.ini",
}
JUNK_PREFIXES = (
    "._",       # macOS AppleDouble 资源分叉
    "~$",       # Office（Word/Excel/PPT）打开文件时生成的锁文件
    ".~lock.",  # LibreOffice 锁文件
)
JUNK_DIRS = {
    ".Spotlight-V100", ".Trashes", ".fseventsd", ".TemporaryItems",
    ".DocumentRevisions-V100", ".PKInstallSandboxManager",
    "__MACOSX", "$RECYCLE.BIN", "System Volume Information",
}


def is_junk(name: str) -> bool:
    """是否属于应当忽略的系统/临时文件。"""
    if not name:
        return False
    if name in JUNK_NAMES:
        return True
    for pre in JUNK_PREFIXES:
        if name.startswith(pre):
            return True
    if name.endswith(".tmp") and name.startswith("~"):
        return True
    return False


def junk_desc() -> str:
    return ".DS_Store、~$ 临时文件等"


# --------------------------------------------------------------------------- #
# 来源扫描
# --------------------------------------------------------------------------- #
def scan_sources(paths: List[str], recurse: bool = True,
                 stats: Optional[dict] = None) -> List[str]:
    """
    把用户选择的文件夹/文件展开为文件绝对路径列表。

    会自动跳过系统/临时文件（.DS_Store、~~$xxx.xlsx 等）；传入 stats 时会写入
    {"junk_skipped": n}，便于界面提示"已忽略多少个系统文件"。
    """
    out: List[str] = []
    skipped = 0
    for p in paths:
        if os.path.isfile(p):
            if is_junk(os.path.basename(p)):
                skipped += 1
                continue
            out.append(os.path.abspath(p))
        elif os.path.isdir(p):
            if recurse:
                for dirpath, dirnames, filenames in os.walk(p):
                    dirnames[:] = [d for d in dirnames
                                   if d not in JUNK_DIRS and d != INDEX_DIR]
                    for fn in filenames:
                        if is_junk(fn):
                            skipped += 1
                            continue
                        out.append(os.path.abspath(os.path.join(dirpath, fn)))
            else:
                for fn in os.listdir(p):
                    fp = os.path.join(p, fn)
                    if not os.path.isfile(fp):
                        continue
                    if is_junk(fn):
                        skipped += 1
                        continue
                    out.append(os.path.abspath(fp))
    if stats is not None:
        stats["junk_skipped"] = skipped
    # 去重并保序
    seen, uniq = set(), []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def human_size(n: int) -> str:
    step = 1024.0
    v = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if v < step or unit == "TB":
            return (f"{v:.0f} {unit}" if unit == "B" else f"{v:.2f} {unit}")
        v /= step
    return f"{v:.2f} TB"


# --------------------------------------------------------------------------- #
# 归档（复制）
# --------------------------------------------------------------------------- #
def unique_target(dest_dir: str, filename: str) -> str:
    base, ext = os.path.splitext(filename)
    cand = os.path.join(dest_dir, filename)
    i = 1
    while os.path.exists(cand):
        cand = os.path.join(dest_dir, f"{base}({i}){ext}")
        i += 1
    return cand


def src_key(path: str) -> str:
    """来源文件的唯一键（大小写无关的绝对路径）。"""
    return os.path.normcase(os.path.abspath(path))


def is_archived(root: str, src: str, known: Optional[Dict[str, dict]] = None) -> bool:
    """该来源文件是否已经归档过。"""
    known = archived_map(root) if known is None else known
    return src_key(src) in known


def split_archived(root: str, files: List[str],
                   known: Optional[Dict[str, dict]] = None) -> Tuple[List[str], List[str]]:
    """把候选文件拆成 (未归档, 已归档)，供界面提示与归档时过滤。"""
    known = archived_map(root) if known is None else known
    pending, done = [], []
    for f in files:
        (done if src_key(f) in known else pending).append(f)
    return pending, done


def same_file_in_dest(dest_dir: str, filename: str, size: int) -> Optional[str]:
    """目标目录里是否已有同名且同大小的文件（索引丢失时的兜底判重）。"""
    cand = os.path.join(dest_dir, filename)
    try:
        if os.path.isfile(cand) and os.path.getsize(cand) == size:
            return cand
    except OSError:
        pass
    return None


def archive_files(root: str, files: List[str], l1: str, l2: str,
                  on_progress: Optional[Callable[[int, int, str], None]] = None,
                  keep_mtime: bool = True,
                  known_archived: Optional[Dict[str, dict]] = None) -> List[dict]:
    """
    把 files 复制到 root/一级/二级 下。

    已经归档过的来源文件**不再重复复制**（result='跳过'）；
    只有从未归档、且目标目录不存在同名同大小文件时才真正复制。
    """
    dest_dir = os.path.join(root, safe_name(l1), safe_name(l2))
    os.makedirs(dest_dir, exist_ok=True)
    known = archived_map(root) if known_archived is None else known_archived

    results: List[dict] = []
    total = len(files)
    for i, src in enumerate(files, 1):
        name = os.path.basename(src)
        rec = {"src": src, "name": name, "dest": "", "result": "失败",
               "note": "", "skipped": False}
        try:
            if not os.path.isfile(src):
                rec["note"] = "源文件不存在"
            else:
                size = os.path.getsize(src)
                info = known.get(src_key(src))
                if info is not None:
                    rec["result"] = "跳过"
                    rec["skipped"] = True
                    rec["dest"] = info.get("dest", "")
                    rec["note"] = (f"已归档于 {info.get('l1', '')}/{info.get('l2', '')}"
                                   f"（{info.get('time', '')}），不再重复复制")
                else:
                    dup = same_file_in_dest(dest_dir, name, size)
                    if dup:
                        # 索引里没有但目标已存在同名同大小文件 → 认定为已归档，补写索引
                        rec["result"] = "跳过"
                        rec["skipped"] = True
                        rec["dest"] = dup
                        rec["note"] = "目标目录已存在同名同大小文件，按已归档处理"
                        known[src_key(src)] = {"name": name, "l1": l1, "l2": l2,
                                               "dest": dup, "time": "（本次补登记）"}
                    else:
                        target = unique_target(dest_dir, name)
                        if os.path.basename(target) != name:
                            rec["note"] = "同名文件已存在，已自动重命名"
                        shutil.copy2(src, target)
                        if not keep_mtime:
                            os.utime(target, None)
                        if os.path.getsize(target) != size:
                            rec["result"] = "失败"
                            rec["note"] = "复制后大小不一致"
                        else:
                            rec["result"] = "成功"
                            rec["dest"] = target
        except Exception as e:                                    # noqa: BLE001
            rec["note"] = f"{type(e).__name__}: {e}"
        results.append(rec)
        if on_progress:
            on_progress(i, total, name)
    return results


def record_archive(root: str, results: List[dict], l1: str, l2: str) -> dict:
    """把归档结果写入 manifest 与日志（跳过项也会登记，避免下次重复判断）。"""
    mf = read_manifest(root)
    if mf is None:
        raise RuntimeError("归档根目录未初始化或索引损坏。")
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    archived = mf.setdefault("archived", {})
    log_rows = []
    for r in results:
        key = src_key(r["src"])
        if r["result"] in ("成功", "跳过") and r["dest"]:
            archived.setdefault(key, {
                "name": r["name"], "l1": l1, "l2": l2,
                "dest": r["dest"], "time": now,
            })
        try:
            size = os.path.getsize(r["src"]) if os.path.isfile(r["src"]) else ""
        except OSError:
            size = ""
        log_rows.append([now, l1, l2, r["name"], size,
                         r["src"], r["dest"], r["result"], r["note"]])
    _write_json(os.path.join(root, INDEX_DIR, MANIFEST), mf)
    append_log(root, log_rows)
    return mf


def archived_map(root: str) -> Dict[str, dict]:
    mf = read_manifest(root) or {}
    am = mf.get("archived", {}) or {}
    return {k: v for k, v in am.items()}


def manifest_get(root: str, key: str, default=None):
    """读取归档根目录 manifest 里的自定义配置（如台账填报信息）。"""
    mf = read_manifest(root)
    if mf is None:
        return default
    return mf.get(key, default)


def manifest_set(root: str, key: str, value):
    """写入 manifest 里的自定义配置。"""
    mf = read_manifest(root)
    if mf is None:
        return None
    mf[key] = value
    _write_json(os.path.join(root, INDEX_DIR, MANIFEST), mf)
    return mf


# --------------------------------------------------------------------------- #
# 自查 / 抽样
# --------------------------------------------------------------------------- #
ROOT_LABEL = "（归档根目录）"
# 归档根目录下由本软件生成的说明文件，扫描自查时应排除
SYSTEM_ROOT_FILES = {README}


def in_scope(root: str, folder: str) -> bool:
    """folder 是否位于归档根目录之内（校验用户手动选择的检查范围）。"""
    try:
        root = os.path.abspath(root)
        folder = os.path.abspath(folder)
        return os.path.commonpath([root, folder]) == root
    except (ValueError, OSError):
        return False


def list_scope_folders(root: str, depth: int = 2) -> List[Tuple[str, str, int]]:
    """列出可作为自查范围的一 / 二级子文件夹：[(显示名, 绝对路径, 层级)]。"""
    root = os.path.abspath(root)
    out: List[Tuple[str, str, int]] = []
    if not os.path.isdir(root):
        return out
    try:
        first = sorted(d for d in os.listdir(root)
                       if os.path.isdir(os.path.join(root, d))
                       and d != INDEX_DIR and d not in JUNK_DIRS)
    except OSError:
        return out
    for a in first:
        pa = os.path.join(root, a)
        out.append(("├ " + a, pa, 1))
        if depth < 2:
            continue
        try:
            second = sorted(d for d in os.listdir(pa)
                            if os.path.isdir(os.path.join(pa, d)) and d != INDEX_DIR)
        except OSError:
            continue
        for b in second:
            out.append(("│    └ " + b, os.path.join(pa, b), 2))
    return out


def scan_archive(root: str, scope: Optional[str] = None,
                 stats: Optional[dict] = None) -> List[dict]:
    """
    扫描归档目录，或其中的任意一级子文件夹（scope 为空表示整个归档根目录）。

    返回记录的字段：path / rel / name / size / mtime，
    以及 l1、l2（相对归档根目录的前两级）和 group（抽样分组名）。

    会跳过系统/临时文件（.DS_Store、~$ 锁文件等）；传入 stats 时写入
    {"junk_skipped": n}，便于界面提示"已忽略多少个系统文件"。
    """
    root = os.path.abspath(root)
    base = os.path.abspath(scope) if scope else root
    records: List[dict] = []
    skipped = 0
    if not os.path.isdir(base):
        if stats is not None:
            stats["junk_skipped"] = 0
        return records
    whole = (base == root)
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames
                       if d != INDEX_DIR and d not in JUNK_DIRS]
        for fn in filenames:
            if is_junk(fn):
                skipped += 1
                continue
            fp = os.path.join(dirpath, fn)
            try:
                st = os.stat(fp)
            except OSError:
                continue
            rel = os.path.relpath(fp, root)
            if os.sep not in rel and rel in SYSTEM_ROOT_FILES:
                continue                      # 跳过软件自己生成的说明文件
            parts = rel.split(os.sep)
            l1 = parts[0] if len(parts) > 1 else ROOT_LABEL
            l2 = parts[1] if len(parts) > 2 else ""
            sub = os.path.relpath(os.path.dirname(fp), base)
            if whole:
                group = f"{l1} / {l2}" if l2 else l1
            elif sub == ".":
                group = "（本级文件）"
            else:
                group = sub
            records.append({
                "path": fp,
                "rel": rel,
                "name": fn,
                "l1": l1,
                "l2": l2,
                "group": group,
                "size": st.st_size,
                "mtime": _dt.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
            })
    records.sort(key=lambda r: (r["group"], r["name"].lower()))
    if stats is not None:
        stats["junk_skipped"] = skipped
    return records


def sample_archive(records: List[dict], mode: str = "all",
                   ratio: float = 0.10, min_n: int = 1, max_n: int = 20,
                   rng: Optional[random.Random] = None) -> List[dict]:
    """mode: 'all' 全部文件；'ratio' 按二级分类（或所选范围内的子文件夹）随机抽样。"""
    if mode == "all":
        return list(records)
    rng = rng or random.Random()
    groups: "OrderedDict[str, List[dict]]" = OrderedDict()
    for r in records:
        groups.setdefault(r.get("group", ""), []).append(r)
    picked: List[dict] = []
    for _key, items in groups.items():
        n = int(round(len(items) * ratio))
        n = max(min_n, min(max_n, n)) if items else 0
        n = min(n, len(items))
        picked.extend(rng.sample(items, n))
    picked.sort(key=lambda r: (r.get("group", ""), r["name"].lower()))
    return picked


def archive_stats(records: List[dict]) -> List[Tuple[str, int, int]]:
    """按分组（一级分类 / 所在子目录）统计 (名称, 文件数, 字节数)。"""
    groups: "OrderedDict[str, List[int]]" = OrderedDict()
    for r in records:
        g = groups.setdefault(r.get("group") or r.get("l1", ""), [0, 0])
        g[0] += 1
        g[1] += r["size"]
    return [(k, v[0], v[1]) for k, v in groups.items()]


# --------------------------------------------------------------------------- #
# 智能分类推荐（启发式，仅供参考）
# --------------------------------------------------------------------------- #
_RULES: List[Tuple[str, str, str, int]] = [
    # (正则, 一级分类, 二级分类, 权重)
    (r"(专利|专利申请|交底|授权公告|发明名称)", "文献与情报数据", "专利文献", 3),
    (r"(标准|规范|GB[/_\-]?T?|ISO|HG[/_\-]?T|ASTM)", "文献与情报数据", "标准规范", 3),
    (r"(学位论文|硕士论文|博士论文|毕业论文)", "文献与情报数据", "学位论文", 3),
    (r"(综述|review)", "文献与情报数据", "学术文献", 3),
    (r"(期刊|论文|paper|journal|doi|acs\.|sciencedirect|article)", "文献与情报数据", "学术文献", 2),
    (r"(书籍|专著|教材|手册|handbook|book)", "文献与情报数据", "专业书籍", 3),
    (r"(可行性研究|评估报告|调研报告|技术报告|研究报告|科技报告)", "文献与情报数据", "科技报告", 3),
    (r"(报告)", "文献与情报数据", "科技报告", 1),
    (r"(立项|申报书|任务书|过程材料|验收|结题|成果)", "文献与情报数据", "项目材料", 3),
    (r"(xrd|衍射|x-ray)", "表征与测试数据", "结构与物相分析", 4),
    (r"(xps|ups|光电子能谱)", "表征与测试数据", "表面化学分析", 4),
    (r"(sem|tem|afm|micro-?ct|电镜|形貌|粒度|颗粒|断面|扫描电镜)", "表征与测试数据", "形貌与微观结构分析", 4),
    (r"(红外|拉曼|raman|紫外|荧光|ftir|uv-?vis|光谱)", "表征与测试数据", "光谱与分子结构分析", 4),
    (r"(nmr|核磁|13c|1h|27al|29si|31p)", "表征与测试数据", "光谱与分子结构分析", 4),
    (r"(色谱|质谱|gc|lc|gcms|hplc|chromat)", "表征与测试数据", "色谱与质谱分析", 4),
    (r"(吸附|bet|孔结构|tpr|tpd|tpo|比表面)", "表征与测试数据", "吸附与孔结构分析", 4),
    (r"(热重|tga|dsc|sta|热分析|差热)", "表征与测试数据", "热性质分析", 4),
    (r"(电化学|阻抗|eis|循环伏安|充放电)", "表征与测试数据", "电化学分析", 4),
    (r"(元素分析|icp|xrf|chns|组成分析)", "表征与测试数据", "元素与组成分析", 4),
    (r"(油品|煤分析|水分析|环境检测|聚合物|polyolefin)", "表征与测试数据", "专用理化分析", 3),
    (r"(vasp|dft|第一性原理|量子化学|gaussian|orca|cp2k|castep|quantum\s?espresso)",
     "计算模拟与模型输出数据", "第一性原理与量子化学", 4),
    (r"(分子动力学|lammps|gromacs|amber|namd|蒙特卡洛)", "计算模拟与模型输出数据", "分子动力学与介观模拟", 4),
    (r"(aspen|fluent|cfx|comsol|openfoam|abaqus|流体力学|流程模拟|仿真)",
     "计算模拟与模型输出数据", "工程仿真与流程模拟", 4),
    (r"(机器学习|深度学习|pytorch|tensorflow|sklearn|xgboost|lightgbm|paddle)",
     "计算模拟与模型输出数据", "人工智能与数据驱动", 4),
    (r"(dcs|中试|工艺包|pid图|工艺流程图|设备规格|物料台账)", "实验与过程数据", "中试与工程验证", 4),
    (r"(合成|配方|浸渍|焙烧|干燥|催化剂制备)", "实验与过程数据", "材料合成与加工记录", 3),
    (r"(评价|性能验证|寿命|老化|稳定性|选择性|转化率|产气|膨胀|截留|去除率)",
     "实验与过程数据", "性能验证与应用评价", 3),
    (r"(生产|日报|月报|产量|销量|库存|发电|运行台账|车次|批次)", "生产数据", "煤炭", 1),
]


def recommend_category(filename: str) -> List[Tuple[str, str, int, str]]:
    """返回 [(一级, 二级, 总分, 命中关键词)]，按总分降序。"""
    name = filename.lower()
    hits: Dict[Tuple[str, str], Tuple[int, List[str]]] = {}
    for pat, l1, l2, w in _RULES:
        found = re.findall(pat, name, flags=re.I)
        if found:
            k = (l1, l2)
            cnt, kws = hits.get(k, (0, []))
            flat = [f if isinstance(f, str) else f[0] for f in found]
            hits[k] = (cnt + w * len(found), kws + [x for x in flat if x][:3])
    out = [(l1, l2, c, "、".join(dict.fromkeys(ws))) for (l1, l2), (c, ws) in hits.items()]
    out.sort(key=lambda x: -x[2])
    return out
