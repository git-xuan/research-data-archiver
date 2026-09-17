# -*- coding: utf-8 -*-
"""
科研数据元信息台账。

把一次归档的结果，转换成《附件1：科研数据元信息采集》里对应的一行，
写入归档根目录的 `_归档索引/科研数据元信息台账.csv`，并可按官方表结构导出 xlsx。

官方文件的结构（已核对）：
  5 个一级分类各一张 sheet（文献与情报数据 / 实验与过程数据 / 表征与测试数据 /
  计算模拟与模型输出数据 / 生产数据），列结构各不相同，A 列是行标记列（填写说明/示例）。
"""
import csv
import io
import os
import time
from typing import Dict, List, Optional, Tuple

LEDGER_CSV = "科研数据元信息台账.csv"
LEDGER_XLSX = "科研数据元信息台账.xlsx"

# --------------------------------------------------------------------------- #
# 官方各 sheet 的业务列（顺序即官方列顺序；已剔除后面的辅助列）
# --------------------------------------------------------------------------- #
SHEET_COLUMNS: Dict[str, List[str]] = {
    "文献与情报数据": [
        "序号", "填报中心", "填报人姓名", "二级分类", "三级分类（选填）",
        "数据简要说明（选填）", "数量统计值", "数量统计单位", "存储介质类型",
        "存储位置详情（选填）", "容量（GB）", "数据来源类型", "关联项目类型",
        "关联项目名称/编号（选填）", "数据产生方式", "院内共享是否允许", "院内获取方式",
        "对外共享是否允许", "对外获取方式", "备注",
    ],
    "实验与过程数据": [
        "序号", "填报中心", "填报人姓名", "二级分类", "数据简要说明（选填）",
        "数量统计值", "数量统计单位", "存储介质类型", "存储位置详情（选填）",
        "数据来源类型", "关联项目类型", "关联项目名称/编号（选填）", "数据产生方式",
        "院内共享是否允许", "院内获取方式", "对外共享是否允许", "对外获取方式",
        "实验ID", "样品ID", "备注",
    ],
    "表征与测试数据": [
        "序号", "填报中心", "填报人姓名", "二级分类", "三级分类（选填）", "四级分类（选填）",
        "数据简要说明（选填）", "数量统计值", "数量统计单位", "存储介质类型",
        "存储位置详情（选填）", "数据来源类型", "关联项目类型", "关联项目名称/编号（选填）",
        "数据产生方式", "院内共享是否允许", "院内获取方式", "对外共享是否允许",
        "对外获取方式", "实验ID", "样品ID", "表征记录号", "备注",
    ],
    "计算模拟与模型输出数据": [
        "序号", "填报中心", "填报人姓名", "二级分类", "三级分类（选填）", "四级分类（选填）",
        "数据简要说明（选填）", "数量统计值", "数量统计单位", "存储介质类型",
        "存储位置详情（选填）", "数据来源类型", "关联项目类型", "关联项目名称/编号（选填）",
        "数据产生方式", "院内共享是否允许", "院内获取方式", "对外共享是否允许",
        "对外获取方式", "计算任务ID", "备注",
    ],
    "生产数据": [
        "序号", "填报中心", "填报人姓名", "二级分类", "数据简要说明（选填）",
        "数量统计值", "数量统计单位", "存储介质类型", "存储位置详情（选填）",
        "数据来源类型", "关联项目类型", "关联项目名称/编号（选填）", "数据产生方式",
        "院内共享是否允许", "院内获取方式", "对外共享是否允许", "对外获取方式",
        "生产批次ID", "备注",
    ],
}

# 台账主表列（各 sheet 业务列的并集，前面加定位列），CSV 与界面表格共用
MASTER_COLUMNS: List[str] = [
    "归档时间", "一级分类", "序号", "填报中心", "填报人姓名", "二级分类",
    "三级分类（选填）", "四级分类（选填）", "数据简要说明（选填）",
    "数量统计值", "数量统计单位", "存储介质类型", "存储位置详情（选填）", "容量（GB）",
    "数据来源类型", "关联项目类型", "关联项目名称/编号（选填）", "数据产生方式",
    "院内共享是否允许", "院内获取方式", "对外共享是否允许", "对外获取方式",
    "实验ID", "样品ID", "表征记录号", "计算任务ID", "生产批次ID", "备注",
    "归档批次", "来源路径",
]

# --------------------------------------------------------------------------- #
# 下拉值域（取自官方文件的数据验证；顺序保持官方原样）
# --------------------------------------------------------------------------- #
CENTER_OPTIONS = [
    "科研人工智能研究中心", "氢能（氨能）技术研究中心", "储能技术研究中心",
    "碳捕集利用与封存（CCUS）技术研究中心", "煤基化学品技术研究中心",
    "煤间接液化技术研究中心", "先进材料研究中心",
    "煤炭开采水资源保护与利用全国重点实验室(能源绿色开发中心)", "科研管理中心",
]
MEDIA_OPTIONS = ["企业云平台", "本地服务器", "高性能计算平台", "业务信息系统",
                 "网络共享存储", "个人办公电脑", "移动存储介质", "第三方平台", "其他"]
SOURCE_OPTIONS = ["科研项目", "日常运营", "外部采购", "合作交流", "历史积累", "其他"]
PROJECT_OPTIONS = ["国家级项目", "省部级项目", "集团级项目", "院级项目",
                   "横向合作项目", "无关联项目"]
METHOD_OPTIONS = ["自主研发", "委托研发", "合作研发", "外部采购", "公开获取", "其他"]
SHARE_OPTIONS = ["允许", "不允许", "需审批"]
ACCESS_OPTIONS = ["内网系统直接访问", "提交申请后开通权限", "联系项目负责人",
                  "经主管部门审批后提供", "合作协议框架内提供", "不适用"]

# 二级分类 -> 数量统计单位（取自官方『值域』的 KEY_L2_UNIT / UNIT_VALUE）
L2_UNIT: Dict[str, str] = {
    "学术文献": "篇", "专利": "件", "标准与规范": "份", "技术报告": "份", "行业情报": "份",
    "知识图谱与语义数据": "条", "专业书籍": "本", "其他": "项",
    "材料合成": "批次", "催化剂制备": "批次", "反应条件筛选": "组", "设备运行": "台时",
    "中试与放大": "批次", "安全与环境": "份", "材料合成与加工记录": "批次",
    "性能验证与应用评价": "批次", "中试与工程验证": "批次", "机械性能": "份",
    "环境与耐久": "份", "在线监测": "条",
    "光谱分析": "份", "色谱分析": "份", "热分析": "份",
    "量子化学": "任务", "分子动力学": "任务", "CFD计算": "任务",
    "机器学习与数据驱动": "模型", "多尺度与耦合": "任务",
    "煤炭": "批次", "电力": "度", "化工": "批次", "运输": "车次", "新能源": "批次",
}
# 官方未覆盖到的二级分类，按一级分类给一个合理默认（官方该列本就是"自动带出"）
L1_UNIT_FALLBACK = {
    "文献与情报数据": "份",
    "实验与过程数据": "批次",
    "表征与测试数据": "份",
    "计算模拟与模型输出数据": "任务",
    "生产数据": "批次",
}

# 各一级分类专有的 ID 列
L1_ID_COLUMN = {
    "实验与过程数据": ["实验ID", "样品ID"],
    "表征与测试数据": ["实验ID", "样品ID", "表征记录号"],
    "计算模拟与模型输出数据": ["计算任务ID"],
    "生产数据": ["生产批次ID"],
    "文献与情报数据": [],
}


def unit_for(l1: str, l2: str) -> str:
    """二级分类对应的数量统计单位。"""
    return L2_UNIT.get(l2) or L1_UNIT_FALLBACK.get(l1, "项")


def default_meta() -> Dict[str, str]:
    """台账默认填报信息（用户可在界面上改，存在 manifest 里）。"""
    return {
        "填报中心": "",
        "填报人姓名": "",
        "数据简要说明（选填）": "",
        "存储介质类型": "本地服务器",
        "数据来源类型": "科研项目",
        "关联项目类型": "无关联项目",
        "关联项目名称/编号（选填）": "",
        "数据产生方式": "自主研发",
        "院内共享是否允许": "需审批",
        "院内获取方式": "提交申请后开通权限",
        "对外共享是否允许": "不允许",
        "对外获取方式": "不适用",
        "实验ID": "",
        "样品ID": "",
        "表征记录号": "",
        "计算任务ID": "",
        "生产批次ID": "",
        "备注": "",
    }


# 需要用户在界面上填写的字段（供对话框生成）
META_FIELDS: List[Tuple[str, Optional[List[str]], str]] = [
    ("填报中心", CENTER_OPTIONS, "填写所属研发中心全称，与总院组织架构保持一致"),
    ("填报人姓名", None, "本条数据的填报责任人姓名"),
    ("数据简要说明（选填）", None, "一至两句话概述数据内容、用途与价值，留空也可以"),
    ("存储介质类型", MEDIA_OPTIONS, "数据存放的介质或系统类型"),
    ("数据来源类型", SOURCE_OPTIONS, "数据产生的主要来源类型"),
    ("关联项目类型", PROJECT_OPTIONS, "无关联项目时选『无关联项目』"),
    ("关联项目名称/编号（选填）", None, "关联的项目名称或编号"),
    ("数据产生方式", METHOD_OPTIONS, "数据的产生方式"),
    ("院内共享是否允许", SHARE_OPTIONS, "院内共享的开放程度"),
    ("院内获取方式", ACCESS_OPTIONS, "院内获取该数据的方式"),
    ("对外共享是否允许", SHARE_OPTIONS, "对外（院外单位）共享的开放程度"),
    ("对外获取方式", ACCESS_OPTIONS, "对外获取该数据的方式"),
    ("实验ID", None, "具备则填写，用于实验数据关联（不适用的一级分类会忽略）"),
    ("样品ID", None, "具备则填写，用于样品追溯"),
    ("表征记录号", None, "仅表征与测试数据使用"),
    ("计算任务ID", None, "仅计算模拟与模型输出数据使用"),
    ("生产批次ID", None, "仅生产数据使用"),
    ("备注", None, "补充说明，如历史版本、数据质量、特殊情况等"),
]


# --------------------------------------------------------------------------- #
# 路径与读写
# --------------------------------------------------------------------------- #
def ledger_csv_path(root: str, index_dir: str = "_归档索引") -> str:
    return os.path.join(root, index_dir, LEDGER_CSV)


def ledger_xlsx_path(root: str, index_dir: str = "_归档索引") -> str:
    return os.path.join(root, index_dir, LEDGER_XLSX)


def read_rows(root: str, index_dir: str = "_归档索引") -> Tuple[List[str], List[Dict[str, str]]]:
    """读取台账 CSV，返回 (表头, 记录列表)。"""
    p = ledger_csv_path(root, index_dir)
    if not os.path.isfile(p):
        return list(MASTER_COLUMNS), []
    with io.open(p, "r", encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        head = rd.fieldnames or list(MASTER_COLUMNS)
        rows = [dict(r) for r in rd]
    return list(head), rows


def _existing_seq(root: str, index_dir: str) -> Dict[str, int]:
    """每个一级分类已有的最大序号。"""
    _h, rows = read_rows(root, index_dir)
    out: Dict[str, int] = {}
    for r in rows:
        l1 = (r.get("一级分类") or "").strip()
        try:
            n = int(float(str(r.get("序号") or 0)))
        except (TypeError, ValueError):
            n = 0
        out[l1] = max(out.get(l1, 0), n)
    return out


def append_rows(root: str, rows: List[Dict[str, str]], index_dir: str = "_归档索引") -> int:
    """把台账行追加写入 CSV（自动分配各一级分类内的序号）。返回写入条数。"""
    if not rows:
        return 0
    os.makedirs(os.path.join(root, index_dir), exist_ok=True)
    path = ledger_csv_path(root, index_dir)
    is_new = not os.path.isfile(path)
    seq = _existing_seq(root, index_dir)
    with io.open(path, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MASTER_COLUMNS, extrasaction="ignore")
        if is_new:
            w.writeheader()
        for r in rows:
            l1 = (r.get("一级分类") or "").strip()
            seq[l1] = seq.get(l1, 0) + 1
            r = dict(r)
            r["序号"] = str(seq[l1])
            w.writerow({k: r.get(k, "") for k in MASTER_COLUMNS})
    return len(rows)


# --------------------------------------------------------------------------- #
# 由归档结果生成台账行
# --------------------------------------------------------------------------- #
def batch_id(ts: Optional[str] = None) -> str:
    return "AR" + (ts or time.strftime("%Y%m%d%H%M%S"))


def build_rows(root: str, results: List[dict], l1: str, l2: str,
               meta: Optional[Dict[str, str]] = None,
               granularity: str = "batch",
               index_dir: str = "_归档索引") -> List[Dict[str, str]]:
    """
    把一次归档的结果转成台账行。

    granularity='batch'：本次同一二级分类的**新归档文件汇总成一行**（默认，
                        与官方表"数量统计值 = 该类数据的规模"的口径一致）；
    granularity='file' ：每个文件一行。
    只统计 result == '成功' 的记录（跳过/失败的不进台账）。
    """
    meta = {**default_meta(), **(meta or {})}
    ok = [r for r in results if r.get("result") == "成功" and r.get("dest")]
    if not ok:
        return []

    now = time.strftime("%Y-%m-%d %H:%M:%S")
    bid = batch_id(now)
    dest_dir = os.path.dirname(ok[0]["dest"])
    rel_dir = os.path.relpath(dest_dir, root)
    try:
        root_disp = os.path.abspath(root)
    except OSError:
        root_disp = root
    pos = (rel_dir if rel_dir != "." else "归档根目录") + "（" + root_disp + "）"

    src_dirs = []
    for r in ok:
        d = os.path.dirname(os.path.abspath(r["src"]))
        if d not in src_dirs:
            src_dirs.append(d)
    src_note = src_dirs[0] + (" 等 %d 个来源目录" % len(src_dirs) if len(src_dirs) > 1 else "")

    def _base(count: int, size: int, extra_pos: str = "") -> Dict[str, str]:
        row: Dict[str, str] = {k: "" for k in MASTER_COLUMNS}
        row["归档时间"] = now
        row["一级分类"] = l1
        for k, v in meta.items():
            if k in MASTER_COLUMNS:
                row[k] = v
        # 只保留该一级分类 sheet 里存在的 ID 列
        keep_ids = set(L1_ID_COLUMN.get(l1, []))
        for k in ("实验ID", "样品ID", "表征记录号", "计算任务ID", "生产批次ID"):
            if k not in keep_ids:
                row[k] = ""
        row["二级分类"] = l2
        row["数量统计值"] = str(count)
        row["数量统计单位"] = unit_for(l1, l2)
        row["存储位置详情（选填）"] = pos + ((" / " + extra_pos) if extra_pos else "")
        if l1 == "文献与情报数据":
            row["容量（GB）"] = "%.4f" % (size / 1024.0 / 1024.0 / 1024.0)
        note = "归档助手自动生成：%s 归档 %d 个文件；来源 %s" % (now, count, src_note)
        if meta.get("备注"):
            note = meta["备注"] + "；" + note
        row["备注"] = note
        row["归档批次"] = bid
        row["来源路径"] = src_note
        return row

    if granularity == "file":
        out = []
        for r in ok:
            try:
                size = os.path.getsize(r["dest"])
            except OSError:
                size = 0
            row = _base(1, size, r["name"])
            row["数据简要说明（选填）"] = meta.get("数据简要说明（选填）") or r["name"]
            out.append(row)
        return out

    total = 0
    for r in ok:
        try:
            total += os.path.getsize(r["dest"])
        except OSError:
            pass
    return [_base(len(ok), total)]


# --------------------------------------------------------------------------- #
# 导出官方结构的 xlsx
# --------------------------------------------------------------------------- #
def export_xlsx(root: str, path: Optional[str] = None,
                index_dir: str = "_归档索引") -> str:
    """
    导出 xlsx：每个一级分类一张 sheet，列序与官方《科研数据元信息采集》完全一致，
    可整行复制粘贴回官方文件；另附一张『全部记录』汇总表。
    """
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    _head, rows = read_rows(root, index_dir)
    path = path or ledger_xlsx_path(root, index_dir)
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    head_font = Font(bold=True, color="FFFFFF")
    head_fill = PatternFill("solid", fgColor="1F6FEB")
    center = Alignment(horizontal="center", vertical="center")

    # 选项页（供下拉引用，最后隐藏）
    opt_ws = wb.create_sheet("_选项")
    opt_defs = [("填报中心", CENTER_OPTIONS), ("存储介质类型", MEDIA_OPTIONS),
                ("数据来源类型", SOURCE_OPTIONS), ("关联项目类型", PROJECT_OPTIONS),
                ("数据产生方式", METHOD_OPTIONS), ("共享", SHARE_OPTIONS),
                ("获取方式", ACCESS_OPTIONS)]
    for ci, (name, vals) in enumerate(opt_defs, 1):
        opt_ws.cell(row=1, column=ci, value=name)
        for ri, v in enumerate(vals, 2):
            opt_ws.cell(row=ri, column=ci, value=v)

    def opt_range(name: str) -> str:
        for ci, (n, vals) in enumerate(opt_defs, 1):
            if n == name:
                col = get_column_letter(ci)
                return "'_选项'!$%s$2:$%s$%d" % (col, col, len(vals) + 1)
        return ""

    dv_map = {
        "填报中心": "填报中心",
        "存储介质类型": "存储介质类型",
        "数据来源类型": "数据来源类型",
        "关联项目类型": "关联项目类型",
        "数据产生方式": "数据产生方式",
        "院内共享是否允许": "共享", "对外共享是否允许": "共享",
        "院内获取方式": "获取方式", "对外获取方式": "获取方式",
    }
    widths = {"序号": 6, "填报中心": 26, "填报人姓名": 12, "二级分类": 20,
              "三级分类（选填）": 18, "四级分类（选填）": 18,
              "数据简要说明（选填）": 40, "数量统计值": 11, "数量统计单位": 11,
              "存储介质类型": 16, "存储位置详情（选填）": 46, "容量（GB）": 11,
              "数据来源类型": 14, "关联项目类型": 14, "关联项目名称/编号（选填）": 28,
              "数据产生方式": 14, "院内共享是否允许": 16, "院内获取方式": 20,
              "对外共享是否允许": 16, "对外获取方式": 20, "备注": 44}

    for l1, cols in SHEET_COLUMNS.items():
        sub = [r for r in rows if (r.get("一级分类") or "").strip() == l1]
        ws = wb.create_sheet(l1)
        for ci, name in enumerate(cols, 1):
            c = ws.cell(row=1, column=ci, value=name)
            c.font, c.fill, c.alignment = head_font, head_fill, center
            ws.column_dimensions[get_column_letter(ci)].width = widths.get(name, 16)
        for ri, r in enumerate(sub, 2):
            for ci, name in enumerate(cols, 1):
                ws.cell(row=ri, column=ci, value=r.get(name, ""))
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = "A1:%s%d" % (get_column_letter(len(cols)), max(1, len(sub) + 1))
        for ci, name in enumerate(cols, 1):
            if name in dv_map and opt_range(dv_map[name]):
                dv = DataValidation(type="list", formula1=opt_range(dv_map[name]),
                                    allow_blank=True, showDropDown=False)
                ws.add_data_validation(dv)
                col = get_column_letter(ci)
                dv.add("%s2:%s1000" % (col, col))

    ws = wb.create_sheet("全部记录")
    for ci, name in enumerate(MASTER_COLUMNS, 1):
        c = ws.cell(row=1, column=ci, value=name)
        c.font, c.fill, c.alignment = head_font, head_fill, center
        ws.column_dimensions[get_column_letter(ci)].width = widths.get(name, 18)
    for ri, r in enumerate(rows, 2):
        for ci, name in enumerate(MASTER_COLUMNS, 1):
            ws.cell(row=ri, column=ci, value=r.get(name, ""))
    ws.freeze_panes = "A2"

    opt_ws.sheet_state = "hidden"
    wb.save(path)
    return path
