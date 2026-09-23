# -*- coding: utf-8 -*-
"""
科研数据归档助手 —— 主程序
Windows 桌面应用：初始化归档目录 / 文件归档 / 归档自查。
"""
from __future__ import annotations

import csv
import datetime as _dt
import os
import random
import subprocess
import sys

from PySide6.QtCore import QPointF, QSize, Qt, QThread, QTimer, Signal, QUrl
from PySide6.QtGui import (
    QColor, QDesktopServices, QFont, QGuiApplication, QIcon, QPainter, QPen,
)
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
    QFileDialog, QFormLayout, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QProgressBar, QPushButton, QRadioButton, QScrollArea,
    QSizePolicy, QSpinBox, QStackedWidget, QStatusBar, QTableWidget, QTableWidgetItem,
    QTextEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

import core
import ledger
import skin
from skin import OK, DANGER, WARN, PRIMARY, TEXT_MUTED

APP_TITLE = f"{core.APP_NAME} v{core.APP_VERSION}"


def resource(rel: str) -> str:
    """兼容 PyInstaller onefile 的资源路径。"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)



# --------------------------------------------------------------------------- #
# 通用小组件
# --------------------------------------------------------------------------- #
class Card(QFrame):
    """白底圆角卡片，带标题与说明。"""

    def __init__(self, title: str = "", desc: str = "", step: str = ""):
        super().__init__()
        self.setObjectName("card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(18, 13, 18, 14)
        self.body.setSpacing(9)
        if title:
            row = QHBoxLayout()
            row.setSpacing(9)
            if step:
                badge = QLabel(step)
                badge.setFixedSize(23, 23)
                badge.setAlignment(Qt.AlignCenter)
                badge.setStyleSheet(
                    f"background:{skin.PRIMARY_LT};color:{PRIMARY};border-radius:11px;"
                    f"font-weight:700;font-size:12.5px;")
                row.addWidget(badge)
            lab = QLabel(title)
            lab.setObjectName("cardTitle")
            row.addWidget(lab)
            row.addStretch(1)
            self.head = row
            self.body.addLayout(row)
        if desc:
            d = QLabel(desc)
            d.setObjectName("cardDesc")
            d.setWordWrap(True)
            self.body.addWidget(d)


def hline() -> QFrame:
    f = QFrame()
    f.setFixedHeight(1)
    f.setStyleSheet(f"background:{skin.BORDER};border:none;")
    return f


class ActionBar(QFrame):
    """
    固定在窗口底部的操作条。

    页面内容放在可滚动的区域里，但主操作按钮挂在这条操作条上，
    所以无论窗口多小、内容多长，用户都不用滚动就能看到并使用主按钮。
    """

    def __init__(self):
        super().__init__()
        self.setObjectName("actionbar")
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(20, 10, 20, 10)
        self.row.setSpacing(10)


class Chip(QLabel):
    """小胶囊标签。"""

    def __init__(self, text: str, color: str = PRIMARY, bg: str = None):
        super().__init__(text)
        bg = bg or _tint(color)
        self.setStyleSheet(
            f"background:{bg};color:{color};border-radius:9px;padding:3px 10px;"
            f"font-size:11.5px;font-weight:600;")
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

    def set_text(self, text: str):
        self.setText(text)
        self.adjustSize()


def _tint(hexcolor: str) -> str:
    c = QColor(hexcolor)
    c.setAlphaF(0.12)
    return f"rgba({c.red()},{c.green()},{c.blue()},0.12)"


class _FlexCols:
    """
    列宽规则：能铺满就铺满，铺不下就滚动 —— 而不是硬压到读不清。

    为什么不用「占位列」：Qt 会给占位列也画一个表头格子，看起来像多出一栏（实测反馈），
    而且它只是把空白"藏"进了一个假列，并不能让真实列变宽。

    内部状态：
      * `_flex_w`   各列的**绝对目标宽度**（初值取各页设定的设计列宽）；
      * `_flex_minw` 各列"不要被挤到读不清"的下限，用于**自动让位**与**窗口缩放**时的保护，
                     不限制用户主动拖动（用户想拖多窄都行，只受全局 40px 约束）。

    行为：
      * 目标宽度之和 < 视口 → 把剩余空间按目标宽度比例分掉 → 铺满窗口，右侧不留白；
      * 目标宽度之和 > 视口 → 原样保留 → 出现横向滚动条，内容读得全；
      * 拖动某列时，若表格当前还能装下，其余列按比例让位（但不低于各自下限）；
        若已经超宽（正在滚动），则只改这一列，不去挤别人；
      * 窗口尺寸变化时，各列按新视口等比缩放，但同样不低于各自下限。
    """

    def _init_flex(self, real_cols: int, min_w: int = 40):
        self._flex_n = real_cols
        self._flex_min = min_w
        self._flex_minw = None         # 每列下限（set_flex_minimums 设定）
        self._flex_design = None       # 设计列宽（用于一键复位）
        self._flex_w = None            # 各列绝对目标宽度
        self._flex_busy = False
        self._flex_ready = False       # 首次显示前的 setColumnWidth 是初始化，不算用户拖动
        self._flex_last_vp = None
        # QTableWidget 用 horizontalHeader()，QTreeWidget 用 header()
        hh = (self.horizontalHeader() if hasattr(self, "horizontalHeader")
              else self.header())
        hh.setSectionResizeMode(QHeaderView.Interactive)
        hh.setStretchLastSection(False)
        hh.setMinimumSectionSize(min_w)
        hh.setSectionsClickable(True)
        hh.setToolTip("拖动表头列与列之间的分隔线即可调整列宽；表格优先铺满窗口，"
                      "列太多放不下时会出现横向滚动条")
        hh.sectionResized.connect(self._on_flex_resized)
        try:
            # 竖向滚动条出现/消失会改变视口宽度 → 需要重新适配
            self.verticalScrollBar().rangeChanged.connect(self._flex_layout_evt)
            # 横向滚动按像素走，才能平滑拖动（默认是"按列跳"，滚动条范围也不是像素）
            self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        except AttributeError:
            pass

    def set_flex_minimums(self, mins) -> None:
        """
        设定各列下限，并把当前各列宽度记作「设计列宽」。

        各页在设置完设计列宽之后紧接着调用；下限主要用于自动让位与窗口缩放时的保护。
        """
        self._flex_minw = [max(int(self._flex_min), int(m)) for m in mins]
        self._flex_design = [int(self.columnWidth(i)) for i in range(self._flex_n)]
        self._flex_w = [float(x) for x in self._flex_design]
        self._flex_fill()

    def reset_flex(self) -> None:
        """恢复各列的设计列宽（拖动改乱后可一键复位），并按当前窗口重新适配。"""
        if not self._flex_design:
            return
        self._flex_w = [float(x) for x in self._flex_design]
        vp = self.viewport().width()
        if vp > 20:
            self._flex_adapt(vp)
            self._flex_last_vp = vp
        self._flex_fill()

    # ------------------------------------------------------------------ 内部
    def _flex_adapt(self, vp: int) -> None:
        """
        把各列目标宽度缩放到"刚好适配当前视口"。

        目标总宽 = max(视口宽, 各列下限之和)：
          * 视口够宽 → 缩放到正好铺满；
          * 下限之和更大（列太多/窗口太窄）→ 缩放到下限为止，剩下的交给横向滚动。

        用迭代而不是一次缩放：某些列撞到下限后会把"省不下来"的宽度顶回去，
        一次缩放就收敛不到目标（实测会多出十几像素），需要再把这些差额摊给还没触底的列。
        """
        n = self._flex_n
        mins = self._flex_minw or [self._flex_min] * n
        new = [float(x) for x in (self._flex_w or mins)]
        target = float(max(vp, sum(mins)))
        for _ in range(8):
            cur = float(sum(new)) or 1.0
            k = target / cur
            nxt = [max(float(mins[i]), new[i] * k) for i in range(n)]
            done = all(abs(nxt[i] - new[i]) < 0.5 for i in range(n))
            new = nxt
            if done:
                break
        self._flex_w = new

    def _flex_widths(self, vp: int) -> List[int]:
        """
        按绝对目标宽度分配；有富余就按目标宽度的比例补满，没有富余就维持原样（横向滚动）。
        """
        n = self._flex_n
        w = self._flex_w or [1.0] * n
        out = [max(int(self._flex_min), int(round(x))) for x in w]
        slack = vp - sum(out)
        if slack > 0:
            tw = sum(w) or 1.0
            extra = [slack * w[i] / tw for i in range(n)]
            add = [int(e) for e in extra]
            order = sorted(range(n), key=lambda i: extra[i] - add[i], reverse=True)
            for k in range(slack - sum(add)):
                add[order[k % n]] += 1
            out = [out[i] + add[i] for i in range(n)]
        elif -slack <= n:
            # 取整让合计比视口多出几像素 → 从最宽的列上扣回来，保证正好铺满
            order = sorted(range(n), key=lambda i: out[i], reverse=True)
            for k in range(-slack):
                i = order[k % n]
                if out[i] > self._flex_min:
                    out[i] -= 1
        return out

    def _flex_fill(self, recheck: bool = True):
        """把当前目标宽度落到各列上；顺带自愈——发现视口变了就重新适配。"""
        if self._flex_busy or self._flex_n <= 0:
            return
        vp = self.viewport().width()
        if vp <= 20:
            return
        if self._flex_w is None:
            self._flex_w = [max(1.0, float(self.columnWidth(i)))
                            for i in range(self._flex_n)]
        old = self._flex_last_vp
        if old and old > 20 and vp != old:
            self._flex_adapt(vp)
        self._flex_last_vp = vp
        widths = self._flex_widths(vp)
        if all(self.columnWidth(i) == widths[i] for i in range(self._flex_n)):
            return
        self._flex_busy = True
        for i, wd in enumerate(widths):
            self.setColumnWidth(i, wd)
        self._flex_busy = False
        if recheck:
            # 列宽变化可能让滚动条出现/消失，视口宽度随之变化 → 下一轮事件循环再校正一次
            QTimer.singleShot(0, lambda: self._flex_fill(False))

    def _on_flex_resized(self, index, _old, new):
        if self._flex_busy or not self._flex_ready or index >= self._flex_n:
            return
        vp = self.viewport().width()
        if vp <= 20:
            return
        if self._flex_w is None:
            self._flex_w = [max(1.0, float(self.columnWidth(i)))
                            for i in range(self._flex_n)]
        mins = self._flex_minw or [self._flex_min] * self._flex_n
        others = [i for i in range(self._flex_n) if i != index]
        if not others:
            return
        cur = [max(1.0, float(self.columnWidth(i))) for i in range(self._flex_n)]
        w = list(cur)
        w[index] = max(float(self._flex_min), float(new))   # 允许用户拖得很窄
        if sum(cur) <= vp + 2:
            # 表格当前还装得下 → 其余列按比例让位/补位（但不低于各自下限）
            others_sum = sum(cur[i] for i in others)
            floor = sum(float(mins[i]) for i in others)
            rest = max(floor, vp - float(new))
            k = rest / others_sum if others_sum > 0 else 1.0
            for i in others:
                w[i] = max(float(mins[i]), cur[i] * k)
        # 已经超宽（正在横向滚动）→ 只改这一列，不去挤别人
        self._flex_w = w
        self._flex_fill()

    # ------------------------------------------------------------------ 事件
    def _flex_layout_evt(self, *_):
        """视口尺寸变了（窗口缩放 / 滚动条出现）→ 重新适配列宽。"""
        self._flex_fill()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._flex_fill()

    def showEvent(self, e):
        super().showEvent(e)
        self._flex_ready = True
        vp = self.viewport().width()
        if vp > 20 and self._flex_w:
            self._flex_adapt(vp)
            self._flex_last_vp = vp
        self._flex_fill()


class CatTree(_FlexCols, QTreeWidget):
    """分类树：列宽可拖动；只给『有子节点』的行画展开箭头，叶子行留空。"""

    def __init__(self, real_cols: int = 3):
        QTreeWidget.__init__(self)
        self.setColumnCount(real_cols)
        self._init_flex(real_cols)

    def drawBranches(self, painter: QPainter, rect, index):
        item = self.itemFromIndex(index)
        if item is None or item.childCount() == 0:
            return
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(QColor(skin.TEXT_MUTED))
        pen.setWidthF(1.8)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        cx = rect.right() - 9.0
        cy = rect.center().y()
        if item.isExpanded():
            painter.drawPolyline([QPointF(cx - 4.5, cy - 2.2),
                                  QPointF(cx, cy + 2.2),
                                  QPointF(cx + 4.5, cy - 2.2)])
        else:
            painter.drawPolyline([QPointF(cx - 2.2, cy - 4.5),
                                  QPointF(cx + 2.2, cy),
                                  QPointF(cx - 2.2, cy + 4.5)])
        painter.restore()


class FnWorker(QThread):
    """在后台线程执行 fn(progress_cb)，避免界面卡死。"""

    progress = Signal(int, int, str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            self.done.emit(self.fn(self.progress.emit))
        except Exception as e:                                       # noqa: BLE001
            self.failed.emit(f"{type(e).__name__}: {e}")


def open_in_explorer(path: str, select: bool = False):
    """在系统文件管理器中打开文件，或定位到该文件（跨平台）。"""
    try:
        if sys.platform == "win32":
            if select and os.path.isfile(path):
                subprocess.Popen(f'explorer /select,"{os.path.normpath(path)}"')
            else:
                os.startfile(path)                                   # noqa: S606
            return
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path] if select else ["open", path])
            return
        subprocess.Popen(["xdg-open", path])
    except Exception:
        QDesktopServices.openUrl(QUrl.fromLocalFile(
            path if os.path.isdir(path) else os.path.dirname(path)))


# --------------------------------------------------------------------------- #
# 第 1 页：初始化归档目录
# --------------------------------------------------------------------------- #
class InitPage(QWidget):
    initialized = Signal(str)

    def __init__(self, win):
        super().__init__()
        self.win = win
        self._tree_busy = False
        n1, n2, n3, n4 = core.tree_counts()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        # —— 选择目标路径
        c1 = Card("选择归档目标路径", "指定一个空的文件夹（或尚不存在的路径）作为科研数据归档根目录。"
                                    "系统会在此路径下按分类树建立一级、二级分类文件夹。", "1")
        row = QHBoxLayout()
        row.setSpacing(8)
        self.ed_path = QLineEdit()
        self.ed_path.setObjectName("path")
        self.ed_path.setPlaceholderText("请选择或粘贴一个空文件夹路径，例如 D:\\科研数据归档")
        self.ed_path.textChanged.connect(self._on_path_changed)
        btn = QPushButton("  浏览…")
        btn.setIcon(skin.icon("folder", 16, skin.TEXT_SUB))
        btn.clicked.connect(self.pick)
        row.addWidget(self.ed_path, 1)
        row.addWidget(btn)
        c1.body.addLayout(row)

        self.lb_path_state = QLabel("尚未选择路径")
        self.lb_path_state.setObjectName("muted")
        crate = QHBoxLayout()
        crate.setSpacing(8)
        crate.addWidget(self.lb_path_state, 1)
        self.lb_path_name = QLabel("")
        self.lb_path_name.setObjectName("mono")
        crate.addWidget(self.lb_path_name)
        c1.body.addLayout(crate)
        root.addWidget(c1)

        # —— 结构预览（可勾选，只创建需要的分类）
        c2 = Card("选择要创建的分类目录",
                  f"依据《科研数据元信息采集·目录分类树》：一级 {n1} 个、二级 {n2} 个"
                  f"（三、四级共 {n3} / {n4} 个，可作为细分参考）。"
                  f"只有勾选的目录会被创建 —— 不需要的分类取消勾选即可；"
                  f"勾选子目录时，其上级目录会自动一起建出来。", "2")
        bar = QHBoxLayout()
        self.chk_l3 = QCheckBox("同时列出三级分类子目录（可选）")
        self.chk_l3.toggled.connect(self._on_l3_toggled)
        b_all = QPushButton("全选")
        b_all.setObjectName("ghost")
        b_all.clicked.connect(lambda: self._set_all(True))
        b_none = QPushButton("全不选")
        b_none.setObjectName("ghost")
        b_none.clicked.connect(lambda: self._set_all(False))
        btn_exp = QPushButton("展开全部")
        btn_exp.setObjectName("ghost")
        btn_exp.clicked.connect(lambda: self.tree.expandAll())
        btn_col = QPushButton("收起全部")
        btn_col.setObjectName("ghost")
        btn_col.clicked.connect(lambda: self.tree.collapseAll())
        bar.addWidget(self.chk_l3)
        bar.addStretch(1)
        bar.addWidget(b_all)
        bar.addWidget(b_none)
        bar.addWidget(btn_exp)
        bar.addWidget(btn_col)
        c2.body.addLayout(bar)

        self.tree = CatTree(3)
        self.tree.setHeaderLabels(["分类目录（勾选要创建的）", "层级",
                                   "包含的三级 / 四级分类"])
        self.tree.setColumnWidth(0, 300)
        self.tree.setColumnWidth(1, 92)
        self.tree.setColumnWidth(2, 360)
        self.tree.set_flex_minimums((190, 76, 170))
        self.tree.setAlternatingRowColors(False)
        self.tree.setRootIsDecorated(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setMinimumHeight(200)
        self.tree.itemChanged.connect(self._on_item_changed)
        c2.body.addWidget(self.tree, 1)

        self.lb_sel = QLabel("")
        self.lb_sel.setObjectName("muted")
        self.lb_sel.setWordWrap(True)
        c2.body.addWidget(self.lb_sel)
        root.addWidget(c2, 1)

        # —— 执行
        # —— 主操作条（固定在窗口底部，不随内容滚动）
        self.actions = ActionBar()
        self.btn_init = QPushButton("  初始化归档目录")
        self.btn_init.setObjectName("primary")
        self.btn_init.setIcon(skin.icon("folder_plus", 18, "#FFFFFF"))
        self.btn_init.setIconSize(QSize(18, 18))
        self.btn_init.setMinimumHeight(40)
        self.btn_init.setMinimumWidth(190)
        self.btn_init.clicked.connect(self.do_init)
        self.btn_open = QPushButton("  打开归档目录")
        self.btn_open.setIcon(skin.icon("external", 16, skin.TEXT_SUB))
        self.btn_open.clicked.connect(
            lambda: open_in_explorer(self.ed_path.text().strip()) if self.ed_path.text().strip() else None)
        self.btn_open.setEnabled(False)
        self.prog = QProgressBar()
        self.prog.setFixedWidth(220)
        self.prog.setVisible(False)
        self.lb_res = QLabel("")
        self.lb_res.setObjectName("muted")
        self.actions.row.addWidget(self.btn_init)
        self.actions.row.addWidget(self.btn_open)
        self.actions.row.addWidget(self.prog)
        self.actions.row.addStretch(1)
        self.actions.row.addWidget(self.lb_res)

        self._refresh_tree()

    # ------------------------------------------------------------------ 逻辑
    def _collect_checks(self):
        """把当前勾选状态收成 {(一级,), (一级,二级), (一级,二级,三级)} 的集合。"""
        sel = set()
        for i in range(self.tree.topLevelItemCount()):
            it1 = self.tree.topLevelItem(i)
            n1 = it1.data(0, Qt.UserRole)
            if it1.checkState(0) == Qt.Checked:
                sel.add((n1,))
            for j in range(it1.childCount()):
                it2 = it1.child(j)
                n2 = it2.data(0, Qt.UserRole)
                if it2.checkState(0) == Qt.Checked:
                    sel.add((n1, n2))
                for k in range(it2.childCount()):
                    it3 = it2.child(k)
                    if it3.checkState(0) == Qt.Checked:
                        sel.add((n1, n2, it3.data(0, Qt.UserRole)))
        return sel

    def _refresh_tree(self, sel=None):
        """重建分类树。sel 为 None 时默认全部勾选。"""
        if sel is None and self.tree.topLevelItemCount():
            sel = self._collect_checks()      # 记住用户当前的选择
        self._tree_busy = True
        try:
            self.tree.clear()
            show_l3 = self.chk_l3.isChecked()
            # 该二级下是否已经有"三级勾选信息"（用于决定新列出的三级默认是否勾上）
            has_l3_info = {k[:2] for k in (sel or ()) if len(k) == 3}

            def checked(key, parent_key=None, inherit=False):
                """inherit=True 只用于三级项：刚展开三级时继承所属二级的勾选状态。"""
                if sel is None:
                    return True
                if key in sel:
                    return True
                return bool(inherit and parent_key and parent_key in sel
                            and parent_key not in has_l3_info)

            for a, d2 in core.TREE.items():
                it1 = QTreeWidgetItem([core.safe_name(a), "一级目录",
                                       f"{len(d2)} 个二级分类"])
                it1.setData(0, Qt.UserRole, a)
                it1.setIcon(0, skin.icon("folder", 16, PRIMARY))
                f = QFont()
                f.setBold(True)
                it1.setFont(0, f)
                it1.setFlags(it1.flags() | Qt.ItemIsUserCheckable)
                it1.setCheckState(0, Qt.Checked if checked((a,)) else Qt.Unchecked)
                for l2, d3 in d2.items():
                    names = list(d3.keys())
                    fourth = sum(len(v) for v in d3.values())
                    tip = "、".join(names) if names else ""
                    if fourth:
                        tip += f"（含 {fourth} 个四级分类）"
                    it2 = QTreeWidgetItem([core.safe_name(l2), "二级目录", tip or "—"])
                    it2.setData(0, Qt.UserRole, l2)
                    it2.setIcon(0, skin.icon("folder", 15, skin.TEXT_SUB))
                    it2.setFlags(it2.flags() | Qt.ItemIsUserCheckable)
                    it2.setCheckState(
                        0, Qt.Checked if checked((a, l2)) else Qt.Unchecked)
                    if show_l3:
                        for l3name in d3:
                            it3 = QTreeWidgetItem(
                                [core.safe_name(l3name), "三级目录",
                                 "、".join(d3[l3name]) or "—"])
                            it3.setData(0, Qt.UserRole, l3name)
                            it3.setForeground(1, QColor(TEXT_MUTED))
                            it3.setFlags(it3.flags() | Qt.ItemIsUserCheckable)
                            it3.setCheckState(
                                0, Qt.Checked
                                if checked((a, l2, l3name), (a, l2), inherit=True)
                                else Qt.Unchecked)
                            it2.addChild(it3)
                    it1.addChild(it2)
                self.tree.addTopLevelItem(it1)
            self.tree.expandToDepth(0)
        finally:
            self._tree_busy = False
        self._update_sel()

    def _on_item_changed(self, item, col):
        if self._tree_busy or col != 0:
            return
        self._tree_busy = True
        try:
            state = item.checkState(0)
            # 勾选/取消父项 → 级联到整棵子树
            stack = [item]
            while stack:
                cur = stack.pop()
                for c in range(cur.childCount()):
                    ch = cur.child(c)
                    if ch.checkState(0) != state:
                        ch.setCheckState(0, state)
                    stack.append(ch)
            # 勾选了子项 → 上级目录自动勾上（父目录必须存在）
            if state == Qt.Checked:
                p = item.parent()
                while p is not None:
                    if p.checkState(0) != Qt.Checked:
                        p.setCheckState(0, Qt.Checked)
                    p = p.parent()
        finally:
            self._tree_busy = False
        self._update_sel()

    def _set_all(self, on: bool):
        self._tree_busy = True
        state = Qt.Checked if on else Qt.Unchecked
        try:
            for i in range(self.tree.topLevelItemCount()):
                it = self.tree.topLevelItem(i)
                it.setCheckState(0, state)
                for j in range(it.childCount()):
                    c2 = it.child(j)
                    c2.setCheckState(0, state)
                    for k in range(c2.childCount()):
                        c2.child(k).setCheckState(0, state)
        finally:
            self._tree_busy = False
        self._update_sel()

    def _on_l3_toggled(self, _checked):
        self._refresh_tree(self._collect_checks())

    def _selected_dirs(self):
        """按勾选状态生成待创建的相对目录列表。"""
        out = []
        for i in range(self.tree.topLevelItemCount()):
            it1 = self.tree.topLevelItem(i)
            if it1.checkState(0) != Qt.Checked:
                continue
            d1 = core.safe_name(it1.data(0, Qt.UserRole))
            out.append(d1)
            for j in range(it1.childCount()):
                it2 = it1.child(j)
                if it2.checkState(0) != Qt.Checked:
                    continue
                d2 = os.path.join(d1, core.safe_name(it2.data(0, Qt.UserRole)))
                out.append(d2)
                for k in range(it2.childCount()):
                    it3 = it2.child(k)
                    if it3.checkState(0) == Qt.Checked:
                        out.append(os.path.join(
                            d2, core.safe_name(it3.data(0, Qt.UserRole))))
        return out

    def _update_sel(self):
        dirs = self._selected_dirs()
        n1 = sum(1 for d in dirs if os.sep not in d)
        n2 = sum(1 for d in dirs if d.count(os.sep) == 1)
        n3 = sum(1 for d in dirs if d.count(os.sep) == 2)
        parts = [f"一级 {n1} 个", f"二级 {n2} 个"]
        if n3 or self.chk_l3.isChecked():
            parts.append(f"三级 {n3} 个")
        if not dirs:
            self.lb_sel.setText("● 未勾选任何目录，无法初始化。请至少勾选一个。")
            self.lb_sel.setObjectName("danger")
        else:
            all_dirs = core.plan_dirs(3 if self.chk_l3.isChecked() else 2)
            extra = ""
            if len(dirs) < len(all_dirs):
                extra = f"（完整分类树为 {len(all_dirs)} 个，其余不会创建）"
            self.lb_sel.setText("● 将创建：" + " · ".join(parts)
                                + f"，合计 {len(dirs)} 个目录 {extra}")
            self.lb_sel.setObjectName("muted")
        self._restyle(self.lb_sel)
        if hasattr(self, "btn_init"):
            # 两个条件都满足才让点：勾了目录 + 路径可用
            self.btn_init.setEnabled(bool(dirs) and self._path_ok())
        self._refresh_open_btn()

    def pick(self):
        d = QFileDialog.getExistingDirectory(
            self, "选择归档目标路径（请选择一个空文件夹）",
            self.ed_path.text().strip() or os.path.expanduser("~"))
        if d:
            self.ed_path.setText(os.path.normpath(d))

    def _path_ok(self):
        p = self.ed_path.text().strip()
        if not p:
            return False
        if core.is_initialized(p):
            return True
        ok, _ = core.check_empty_target(p)
        return ok

    def _refresh_open_btn(self):
        p = self.ed_path.text().strip()
        self.btn_open.setEnabled(bool(p) and os.path.isdir(p))

    def _on_path_changed(self, text):
        p = text.strip()
        if not p:
            self.lb_path_state.setText("尚未选择路径")
            self.lb_path_state.setObjectName("muted")
            self.lb_path_name.setText("")
            self._restyle(self.lb_path_state)
            self._update_sel()
            return
        if core.is_initialized(p):
            self.lb_path_state.setText("● 该目录已经初始化，可直接用于归档")
            self.lb_path_state.setObjectName("ok")
            self.btn_init.setText("  补齐勾选的分类目录")
        else:
            ok, msg = core.check_empty_target(p)
            self.lb_path_state.setText("● " + msg)
            self.lb_path_state.setObjectName("ok" if ok else "danger")
            self.btn_init.setText("  初始化归档目录")
        try:
            parent = os.path.dirname(os.path.abspath(p))
            self.lb_path_name.setText("父目录可写：" + ("是" if os.access(parent, os.W_OK) else "否")
                                      if os.path.isdir(parent) else "")
        except Exception:
            self.lb_path_name.setText("")
        self._restyle(self.lb_path_state)
        self._update_sel()

    @staticmethod
    def _restyle(w):
        w.style().unpolish(w)
        w.style().polish(w)

    def do_init(self):
        p = self.ed_path.text().strip()
        if not p:
            return
        levels = 3 if self.chk_l3.isChecked() else 2
        sel = core.norm_dirs(self._selected_dirs())
        if not sel:
            QMessageBox.information(self, "提示", "请至少勾选一个要创建的分类目录。")
            return
        full = core.plan_dirs(levels)
        # 勾的正好是完整分类树 → 按整体初始化处理（说明文件里不必标成"部分初始化"）
        dirs = None if set(sel) >= set(full) else sel
        total = len(sel)
        n1 = sum(1 for d in sel if os.sep not in d)
        n2 = sum(1 for d in sel if d.count(os.sep) == 1)
        n3 = sum(1 for d in sel if d.count(os.sep) == 2)
        detail = f"一级 {n1} 个 · 二级 {n2} 个" + (f" · 三级 {n3} 个" if n3 else "")
        if dirs is None:
            detail += f"（完整分类树，共 {total} 个目录）"
        else:
            detail += f"（完整分类树共 {len(full)} 个，你未勾选的 {len(full) - total} 个不会创建）"

        if core.is_initialized(p):
            if QMessageBox.question(
                    self, "确认",
                    f"该目录已初始化。将创建其中缺失的目录（已存在的不动）：\n\n"
                    f"{os.path.normpath(p)}\n\n{detail}\n\n是否继续？"
            ) != QMessageBox.Yes:
                return
        else:
            if QMessageBox.question(
                    self, "确认初始化",
                    f"将在以下路径创建 {total} 个分类目录：\n\n{os.path.normpath(p)}\n\n"
                    f"{detail}\n\n"
                    f"同时写入《归档说明.md》与索引文件。是否继续？"
            ) != QMessageBox.Yes:
                return

        self.btn_init.setEnabled(False)
        self.prog.setVisible(True)
        self.prog.setRange(0, total)
        self.lb_res.setText("正在创建…")

        def job(cb):
            return core.init_archive(p, levels, lambda i, t, rel: cb(i, t, rel), dirs)

        self.worker = FnWorker(job)
        self.worker.progress.connect(
            lambda i, t, rel: (self.prog.setValue(i),
                               self.lb_res.setText(f"创建中 {i}/{t}  {rel}")))
        self.worker.done.connect(self._init_done)
        self.worker.failed.connect(self._init_fail)
        self.worker.start()

    def _init_done(self, manifest):
        self.prog.setVisible(False)
        folders = manifest.get("folders") or []
        n1 = sum(1 for d in folders if os.sep not in d)
        n2 = sum(1 for d in folders if d.count(os.sep) == 1)
        n3 = sum(1 for d in folders if d.count(os.sep) == 2)
        cnt = f"{n1} 个一级 / {n2} 个二级" + (f" / {n3} 个三级" if n3 else "")
        self.lb_res.setText(f"✓ 初始化完成：{cnt}")
        self.lb_res.setObjectName("ok")
        self._restyle(self.lb_res)
        self._refresh_open_btn()
        self.btn_init.setEnabled(True)
        self.initialized.emit(manifest["root"])
        tag = "（部分初始化）" if manifest.get("partial") else ""
        QMessageBox.information(
            self, "初始化完成",
            f"归档目录已创建完成{tag}。\n\n路径：{manifest['root']}\n"
            f"本次创建 {cnt}，合计 {len(folders)} 个目录\n\n"
            f"提示：目录中的《归档说明.md》列出了实际创建的分类结构与含义，可随时查阅。\n"
            f"需要补建其它分类时，在本页重新勾选后再点『补齐勾选的分类目录』即可，"
            f"已存在的数据不会受影响。")

    def _init_fail(self, msg):
        self.prog.setVisible(False)
        self.lb_res.setText("✗ 初始化失败")
        self.lb_res.setObjectName("danger")
        self._restyle(self.lb_res)
        self.btn_init.setEnabled(True)
        QMessageBox.critical(self, "初始化失败", msg)

    def set_root(self, path):
        if path and self.ed_path.text().strip() != path:
            self.ed_path.setText(path)


# --------------------------------------------------------------------------- #
# 第 2 页：文件归档
# --------------------------------------------------------------------------- #
class ArchivePage(QWidget):
    STATUS_WAIT = "待归档"
    STATUS_DONE = "[已归档]"
    STATUS_NEW = "待归档"

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.files = []            # 候选文件（扫描/添加进来的全部文件）
        self._checked = set()      # 用户勾选、本次真正要归档的文件
        self._pending = []         # 本次实际执行的待归档列表
        self.archived = {}         # normcase(src) -> info
        self._row_of = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        # 1 归档根目录
        c1 = Card("归档根目录", "选择已完成初始化的归档目录。", "1")
        r = QHBoxLayout()
        r.setSpacing(8)
        self.ed_root = QLineEdit()
        self.ed_root.setObjectName("path")
        self.ed_root.setPlaceholderText("请选择已初始化的归档根目录")
        self.ed_root.setReadOnly(True)
        b = QPushButton("  浏览…")
        b.setIcon(skin.icon("folder", 16, skin.TEXT_SUB))
        b.clicked.connect(self.pick_root)
        self.lb_root_state = QLabel("未选择")
        self.lb_root_state.setObjectName("muted")
        r.addWidget(self.ed_root, 1)
        r.addWidget(b)
        r.addWidget(self.lb_root_state)
        c1.body.addLayout(r)
        root.addWidget(c1)

        # 2 待归档数据（先扫描成候选列表，再由用户勾选要归档的）
        c2 = Card("待归档数据（先预览，再勾选）",
                  "扫描文件夹或添加文件后，候选文件先列在下方；"
                  "然后在列表里勾选真正要归档的文件：可点选、Ctrl / Shift 多选，"
                  "选中行后按空格键批量勾选或取消。", "2")
        r2 = QHBoxLayout()
        r2.setSpacing(8)
        b1 = QPushButton("  扫描文件夹…")
        b1.setIcon(skin.icon("folder", 16, skin.TEXT_SUB))
        b1.clicked.connect(self.pick_folder)
        b2 = QPushButton("  添加文件…")
        b2.setIcon(skin.icon("files", 16, skin.TEXT_SUB))
        b2.clicked.connect(self.pick_files)
        b3 = QPushButton("  移出列表")
        b3.setObjectName("ghost")
        b3.setIcon(skin.icon("x", 15, skin.TEXT_SUB))
        b3.clicked.connect(self.remove_rows)
        b4 = QPushButton("  清空列表")
        b4.setObjectName("ghost")
        b4.clicked.connect(self.clear_files)
        r2.addWidget(b1)
        r2.addWidget(b2)
        r2.addWidget(b3)
        r2.addWidget(b4)
        r2.addStretch(1)
        c2.body.addLayout(r2)

        r2b = QHBoxLayout()
        r2b.setSpacing(7)
        for txt, slot, tip in (
                ("全选", lambda: self.check_all(True), "勾选列表中全部未归档文件"),
                ("全不选", lambda: self.check_all(False), "取消勾选列表中的全部文件"),
                ("反选", self.invert_check, "已勾选的取消、未勾选的勾上"),
                ("勾选高亮行", lambda: self.check_rows(True), "勾选当前高亮（可 Ctrl/Shift 多选）的行"),
                ("取消高亮行", lambda: self.check_rows(False), "取消勾选当前高亮的行")):
            bb = QPushButton("  " + txt)
            bb.setObjectName("seg")
            bb.setToolTip(tip)
            bb.setCursor(Qt.PointingHandCursor)
            bb.clicked.connect(slot)
            r2b.addWidget(bb)
        r2b.addStretch(1)
        self.lb_sel = QLabel("尚未添加文件")
        self.lb_sel.setObjectName("muted")
        r2b.addWidget(self.lb_sel)
        c2.body.addLayout(r2b)

        self.tb_files = FileTable(0, 6)
        self.tb_files.dropped.connect(self.add_paths)
        self.tb_files.spacePressed.connect(self._toggle_selected_checks)
        self.tb_files.setHorizontalHeaderLabels(
            ["归档", "#", "文件名", "大小", "所在目录", "归档状态"])
        self.tb_files.verticalHeader().setVisible(False)
        self.tb_files.verticalHeader().setDefaultSectionSize(32)
        self.tb_files.setAlternatingRowColors(True)
        self.tb_files.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tb_files.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tb_files.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tb_files.setMinimumHeight(110)
        self.tb_files.itemChanged.connect(self._on_row_check)
        self.tb_files.setColumnWidth(0, 52)
        self.tb_files.setColumnWidth(1, 40)
        self.tb_files.setColumnWidth(2, 300)
        self.tb_files.setColumnWidth(3, 84)
        self.tb_files.setColumnWidth(4, 340)
        self.tb_files.setColumnWidth(5, 98)
        self.tb_files.set_flex_minimums((52, 40, 160, 72, 150, 88))
        c2.body.addWidget(self.tb_files, 1)
        root.addWidget(c2, 1)

        # 3 归档目标（分类选择 + 执行合并为一张卡，把更多高度留给文件列表）
        c3 = Card("选择归档到的分类目录并执行",
                  "先选择一级分类、再选择二级分类；『智能推荐』依据文件名给出建议，仅供参考。", "3")
        r3 = QHBoxLayout()
        r3.setSpacing(9)
        self.cb_l1 = QComboBox()
        self.cb_l1.setMinimumWidth(210)
        self.cb_l1.currentTextChanged.connect(self._on_l1)
        self.cb_l2 = QComboBox()
        self.cb_l2.setMinimumWidth(210)
        self.cb_l2.currentTextChanged.connect(lambda _: self._update_target())
        b_rec = QPushButton("  智能推荐")
        b_rec.setIcon(skin.icon("wand", 16, skin.TEXT_SUB))
        b_rec.clicked.connect(self.recommend)
        self.lb_target = QLabel("")
        self.lb_target.setObjectName("mono")
        self.lb_target.setWordWrap(True)
        r3.addWidget(QLabel("一级分类"))
        r3.addWidget(self.cb_l1)
        r3.addWidget(QLabel("二级分类"))
        r3.addWidget(self.cb_l2)
        r3.addWidget(b_rec)
        r3.addStretch(1)
        c3.body.addLayout(r3)
        c3.body.addWidget(self.lb_target)
        c3.body.addWidget(hline())

        self.btn_go = QPushButton("  开始归档")
        self.btn_go.setObjectName("primary")
        self.btn_go.setIcon(skin.icon("inbox", 18, "#FFFFFF"))
        self.btn_go.setIconSize(QSize(18, 18))
        self.btn_go.setMinimumHeight(40)
        self.btn_go.setMinimumWidth(158)
        self.btn_go.clicked.connect(self.do_archive)
        self.prog = QProgressBar()
        self.prog.setFixedWidth(220)
        self.prog.setVisible(False)
        self.lb_res = QLabel("归档是『复制』操作，不会删除原始文件。")
        self.lb_res.setObjectName("muted")
        self.lb_res.setWordWrap(True)
        self.lb_res.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        # 主操作条（固定在窗口底部）
        self.actions = ActionBar()
        self.actions.row.addWidget(self.btn_go)
        self.actions.row.addWidget(self.prog)
        self.actions.row.addStretch(1)
        self.actions.row.addWidget(self.lb_res, 3)
        # 运行日志留在内容区
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(70)
        self.log.setVisible(False)
        c3.body.addWidget(self.log)
        self.cb_l1.addItems(core.l1_list())
        root.addWidget(c3)

    # ------------------------------------------------------------------ 数据
    def set_root(self, path):
        path = os.path.normpath(path) if path else ""
        self.ed_root.setText(path)
        self.archived = core.archived_map(path) if path and core.is_initialized(path) else {}
        if not path:
            self.lb_root_state.setText("未选择")
            self.lb_root_state.setObjectName("muted")
        elif core.is_initialized(path):
            self.lb_root_state.setText("● 已初始化")
            self.lb_root_state.setObjectName("ok")
        else:
            self.lb_root_state.setText("● 未初始化（请先完成初始化）")
            self.lb_root_state.setObjectName("danger")
        ArchivePage._style(self.lb_root_state)
        self._refresh_status()

    @staticmethod
    def _style(w):
        w.style().unpolish(w)
        w.style().polish(w)

    def pick_root(self):
        d = QFileDialog.getExistingDirectory(self, "选择已初始化的归档根目录",
                                             self.ed_root.text() or os.path.expanduser("~"))
        if d:
            if not core.is_initialized(d):
                if QMessageBox.question(
                        self, "该目录尚未初始化",
                        "所选目录中没有找到归档索引，可能尚未初始化。\n\n"
                        "是否现在跳转到『初始化归档目录』页面进行初始化？"
                ) == QMessageBox.Yes:
                    self.win.goto(0, preset=d)
                    return
                return
            self.win.set_root(os.path.normpath(d))

    def pick_files(self):
        fs, _ = QFileDialog.getOpenFileNames(
            self, "添加待归档文件（可按住 Ctrl / Shift 多选）", os.path.expanduser("~"))
        if fs:
            self.add_paths(fs)

    def pick_folder(self):
        d = QFileDialog.getExistingDirectory(self, "选择待归档文件夹（将递归扫描其中的文件）",
                                             os.path.expanduser("~"))
        if d:
            self.add_paths([d])

    def add_paths(self, paths):
        """把文件/文件夹展开为候选列表；候选项默认不勾选，由用户在列表里挑选。"""
        stats = {}
        added = core.scan_sources(list(paths), stats=stats)
        junk = stats.get("junk_skipped", 0)
        if not added:
            msg = "所选内容中没有可归档的文件。"
            if junk:
                msg += (f"\n\n（其中 {junk} 个系统/临时文件已被自动忽略："
                        f"{core.junk_desc()}）")
            QMessageBox.information(self, "提示", msg)
            return
        have = set(self.files)
        new = [p for p in added if p not in have]
        self.files.extend(new)
        self.refresh_table()
        dup = len(added) - len(new)
        tip = f"共 {len(self.files)} 个候选文件"
        if dup:
            tip += f"（重复忽略 {dup} 个）"
        if junk:
            tip += f"（系统文件忽略 {junk} 个）"
        tip += " · 请在列表中勾选要归档的文件"
        self.lb_sel.setText(tip)
        if len(self.files) == 1 and not self.lb_target.text():
            self.recommend()

    def remove_rows(self):
        rows = sorted({i.row() for i in self.tb_files.selectedIndexes()}, reverse=True)
        if not rows:
            QMessageBox.information(
                self, "提示", "请先在列表中点选要移出的行（可 Ctrl / Shift 多选）。")
            return
        for r in rows:
            if 0 <= r < len(self.files):
                self._checked.discard(self.files.pop(r))
        self.refresh_table()

    def clear_files(self):
        self.files = []
        self._checked.clear()
        self.tb_files.blockSignals(True)
        self.tb_files.setRowCount(0)
        self.tb_files.blockSignals(False)
        self.lb_sel.setText("尚未添加文件")
        self.log.clear()

    # ------------------------------------------------------------------ 勾选
    def _path_of_row(self, row):
        return self.files[row] if 0 <= row < len(self.files) else None

    def _set_row_checked(self, row, checked: bool) -> bool:
        it = self.tb_files.item(row, 0)
        if it is None or not (it.flags() & Qt.ItemIsUserCheckable):
            return False
        p = self._path_of_row(row)
        self.tb_files.blockSignals(True)
        it.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self.tb_files.blockSignals(False)
        if p is not None:
            self._checked.add(p) if checked else self._checked.discard(p)
        return True

    def check_all(self, checked: bool):
        for i in range(self.tb_files.rowCount()):
            self._set_row_checked(i, checked)
        self._update_sel_label()

    def invert_check(self):
        for i in range(self.tb_files.rowCount()):
            it = self.tb_files.item(i, 0)
            if it is not None and (it.flags() & Qt.ItemIsUserCheckable):
                self._set_row_checked(i, it.checkState() != Qt.Checked)
        self._update_sel_label()

    def check_rows(self, checked: bool):
        rows = {i.row() for i in self.tb_files.selectedIndexes()}
        if not rows:
            QMessageBox.information(
                self, "提示", "请先点选一行或多行（可按住 Ctrl / Shift 多选）。")
            return
        for r in rows:
            self._set_row_checked(r, checked)
        self._update_sel_label()

    def _toggle_selected_checks(self):
        """空格键：以首行的勾选状态为准，批量勾选 / 取消高亮行。"""
        rows = sorted({i.row() for i in self.tb_files.selectedIndexes()})
        rows = [r for r in rows
                if self.tb_files.item(r, 0) is not None
                and (self.tb_files.item(r, 0).flags() & Qt.ItemIsUserCheckable)]
        if not rows:
            return
        target = self.tb_files.item(rows[0], 0).checkState() != Qt.Checked
        for r in rows:
            self._set_row_checked(r, target)
        self._update_sel_label()

    def checked_files(self):
        out = []
        for i in range(self.tb_files.rowCount()):
            it = self.tb_files.item(i, 0)
            if it is not None and it.checkState() == Qt.Checked:
                p = self._path_of_row(i)
                if p:
                    out.append(p)
        return out

    def _on_row_check(self, item):
        if item.column() != 0:
            return
        p = self._path_of_row(item.row())
        if p is not None:
            self._checked.add(p) if item.checkState() == Qt.Checked else self._checked.discard(p)
        self._update_sel_label()

    def _update_sel_label(self):
        total = len(self.files)
        if not total:
            self.lb_sel.setText("尚未添加文件")
            return
        chosen = self.checked_files()
        if not chosen:
            self.lb_sel.setText(f"共 {total} 个候选文件 · 尚未勾选")
            return
        size = 0
        for p in chosen:
            try:
                size += os.path.getsize(p)
            except OSError:
                pass
        n_done = sum(1 for p in chosen if core.src_key(p) in self.archived)
        txt = f"已勾选 {len(chosen)}/{total} 个 · {core.human_size(size)}"
        if n_done:
            txt += f" · 其中 {n_done} 个已归档（自动跳过）"
        self.lb_sel.setText(txt)

    def refresh_table(self):
        self.tb_files.blockSignals(True)
        self.tb_files.setRowCount(len(self.files))
        self._row_of = {}
        for i, p in enumerate(self.files):
            self._row_of[p] = i
            it0 = QTableWidgetItem("")
            it0.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            it0.setCheckState(Qt.Checked if p in self._checked else Qt.Unchecked)
            it0.setTextAlignment(Qt.AlignCenter)
            self.tb_files.setItem(i, 0, it0)
            it1 = QTableWidgetItem(str(i + 1))
            it1.setForeground(QColor(TEXT_MUTED))
            it1.setTextAlignment(Qt.AlignCenter)
            self.tb_files.setItem(i, 1, it1)
            self.tb_files.setItem(i, 2, QTableWidgetItem(os.path.basename(p)))
            try:
                it3 = QTableWidgetItem(core.human_size(os.path.getsize(p)))
            except OSError:
                it3 = QTableWidgetItem("—")
            it3.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tb_files.setItem(i, 3, it3)
            it4 = QTableWidgetItem(os.path.dirname(p))
            it4.setForeground(QColor(TEXT_MUTED))
            self.tb_files.setItem(i, 4, it4)
            self.tb_files.setItem(i, 5, QTableWidgetItem(""))
        self.tb_files.blockSignals(False)
        self._refresh_status()

    def _refresh_status(self):
        for p, i in self._row_of.items():
            key = core.src_key(p)
            done = key in self.archived
            cell = self.tb_files.item(i, 5)
            if cell is None:
                continue
            chk = self.tb_files.item(i, 0)
            self.tb_files.blockSignals(True)
            if done:
                info = self.archived[key]
                cell.setText("[已归档]")
                cell.setForeground(QColor(OK))
                cell.setToolTip(
                    f"{info.get('l1')} / {info.get('l2')}\n归档时间：{info.get('time')}\n"
                    f"{info.get('dest')}\n\n已归档的文件不会重复复制。")
                # 已归档 → 禁止勾选，避免重复复制
                if chk is not None:
                    chk.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                    chk.setCheckState(Qt.Unchecked)
                    chk.setToolTip("该文件已归档，本次不会重复复制")
                self._checked.discard(p)
                for c in (1, 2, 3, 4):
                    it = self.tb_files.item(i, c)
                    if it is not None:
                        it.setForeground(QColor(TEXT_MUTED))
            else:
                cell.setText("待归档")
                cell.setForeground(QColor(TEXT_MUTED))
                cell.setToolTip("尚未归档，可勾选后归档")
                if chk is not None:
                    chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    chk.setCheckState(Qt.Checked if p in self._checked else Qt.Unchecked)
                    chk.setToolTip("勾选表示本次要归档该文件")
            self.tb_files.blockSignals(False)
        self._update_sel_label()

    # ------------------------------------------------------------------ 分类
    def _on_l1(self, text):
        self.cb_l2.blockSignals(True)
        self.cb_l2.clear()
        self.cb_l2.addItems(core.l2_list(text))
        self.cb_l2.blockSignals(False)
        self._update_target()

    def _update_target(self):
        l1, l2 = self.cb_l1.currentText(), self.cb_l2.currentText()
        if not (l1 and l2):
            self.lb_target.setText("")
            return
        target = os.path.join(self.ed_root.text() or "<归档根目录>",
                              core.safe_name(l1), core.safe_name(l2))
        self.lb_target.setText("归档到：" + target)

    def recommend(self):
        pool = self.checked_files() or self.files
        if not pool:
            QMessageBox.information(self, "提示", "请先添加待归档文件。")
            return
        votes = {}
        detail = {}
        for p in pool:
            for l1, l2, score, kw in core.recommend_category(os.path.basename(p)):
                votes[(l1, l2)] = votes.get((l1, l2), 0) + score
                detail.setdefault((l1, l2), []).append(kw)
        if not votes:
            QMessageBox.information(
                self, "智能推荐",
                "未能从文件名中识别出明显的分类特征。\n\n请手动选择一级、二级分类。")
            return
        top = sorted(votes.items(), key=lambda kv: -kv[1])[0][0]
        l1, l2 = top
        self.cb_l1.setCurrentText(l1)
        self.cb_l2.setCurrentText(l2)
        kws = "、".join(dict.fromkeys(detail[top]))[:40]
        scope = "已勾选文件" if self.checked_files() else "全部候选文件"
        self.lb_res.setText(f"智能推荐（依据{scope}）：{l1} / {l2}（命中：{kws}…）请人工确认")
        self.lb_res.setObjectName("muted")
        self._style(self.lb_res)

    # ------------------------------------------------------------------ 执行
    def do_archive(self):
        root = self.ed_root.text().strip()
        if not root:
            QMessageBox.warning(self, "缺少归档根目录", "请先选择归档根目录。"); return
        if not core.is_initialized(root):
            QMessageBox.warning(self, "未初始化",
                                "该目录尚未初始化，请先在『初始化归档目录』页面完成初始化。"); return
        if not self.files:
            QMessageBox.warning(self, "缺少文件", "请先扫描文件夹或添加文件。"); return
        chosen = self.checked_files()
        if not chosen:
            QMessageBox.warning(
                self, "尚未勾选文件",
                "请在下方列表最左侧的『归档』列勾选要归档的文件。\n\n"
                "提示：可点选、按住 Ctrl / Shift 多选，选中后按空格键批量勾选或取消。")
            return
        l1, l2 = self.cb_l1.currentText(), self.cb_l2.currentText()
        if not (l1 and l2):
            QMessageBox.warning(self, "缺少分类", "请选择一级分类与二级分类。"); return

        # 只对「未归档」的文件执行复制，已归档的一律跳过
        # （重新读一次索引，避免其他窗口/进程刚归档过造成误判）
        self.archived = core.archived_map(root)
        pending, done = core.split_archived(root, chosen, self.archived)
        if not pending:
            QMessageBox.information(
                self, "无需归档",
                f"勾选的 {len(chosen)} 个文件都已归档过，本次不会重复复制。\n\n"
                f"如需继续整理其他数据，请扫描新文件夹后再勾选。")
            self._refresh_status()
            return

        dest = os.path.join(root, core.safe_name(l1), core.safe_name(l2))
        total_size = 0
        for p in pending:
            try:
                total_size += os.path.getsize(p)
            except OSError:
                pass
        extra = f"\n\n已归档、将自动跳过：{len(done)} 个" if done else ""
        if QMessageBox.question(
                self, "确认归档",
                f"本次将归档 {len(pending)} 个未归档文件（{core.human_size(total_size)}）"
                f"{extra}\n\n归档到：\n{dest}\n\n"
                f"提示：本操作是『复制』，原始文件不会被删除；"
                f"已归档文件不会重复复制。是否继续？"
        ) != QMessageBox.Yes:
            return

        # ---- 台账填报信息：第一次归档前问一次，之后自动带入
        self._ledger_meta = {}
        self._ledger_ok = False
        meta = core.manifest_get(root, "ledger_meta")
        if meta is None:
            dlg = LedgerMetaDialog(ledger.default_meta(), self, first_time=True)
            if dlg.exec() == QDialog.Accepted:
                self._ledger_meta = dlg.values()
                core.manifest_set(root, "ledger_meta", self._ledger_meta)
                self._ledger_ok = True
        else:
            self._ledger_meta = meta or {}
            self._ledger_ok = True

        self._pending = list(pending)
        self.btn_go.setEnabled(False)
        self.prog.setVisible(True)
        self.prog.setRange(0, len(pending))
        self.prog.setValue(0)
        self.log.setVisible(True)
        self.log.clear()
        self.lb_res.setText("正在复制…")
        self.lb_res.setObjectName("muted")
        self._style(self.lb_res)

        todo = list(pending)

        def job(cb):
            return core.archive_files(root, todo, l1, l2, cb)

        self.worker = FnWorker(job)
        self.worker.progress.connect(self._on_prog)
        self.worker.done.connect(lambda res: self._done(root, res, l1, l2))
        self.worker.failed.connect(self._fail)
        self.worker.start()

    def _on_prog(self, i, t, name):
        self.prog.setValue(i)
        self.lb_res.setText(f"复制中 {i}/{t} · {name}")
        self.log.append(f"[{i}/{t}] {name}")

    def _done(self, root, results, l1, l2):
        self.prog.setVisible(False)
        self.btn_go.setEnabled(True)
        try:
            core.record_archive(root, results, l1, l2)
            self.archived = core.archived_map(root)
        except Exception as e:                                        # noqa: BLE001
            QMessageBox.warning(self, "索引写入失败", str(e))

        ok = sum(1 for r in results if r["result"] == "成功")
        skip = sum(1 for r in results if r["result"] == "跳过")
        fail = sum(1 for r in results if r["result"] == "失败")
        renamed = sum(1 for r in results if "重命名" in (r["note"] or ""))

        # ---- 台账生成器：把本次新归档的数据写成《科研数据元信息采集》对应的一行
        n_ledger = 0
        ledger_err = ""
        if ok:
            if getattr(self, "_ledger_ok", False):
                try:
                    rows = ledger.build_rows(
                        root, results, l1, l2, getattr(self, "_ledger_meta", {}),
                        core.manifest_get(root, "ledger_granularity", "batch"))
                    n_ledger = ledger.append_rows(root, rows)
                except Exception as e:                                # noqa: BLE001
                    ledger_err = f"{type(e).__name__}: {e}"

        parts = [f"成功 {ok} 个"]
        if skip:
            parts.append(f"跳过已归档 {skip} 个")
        if fail:
            parts.append(f"失败 {fail} 个")
        if renamed:
            parts.append(f"同名重命名 {renamed} 个")
        if n_ledger:
            parts.append(f"已写台账 {n_ledger} 条")
        self.lb_res.setText("✓ 归档完成：" + "，".join(parts))
        self.lb_res.setObjectName("ok" if not fail else "warn")
        self._style(self.lb_res)
        self._refresh_status()
        self.win.notify_archive_changed()

        msg = f"成功归档 {ok} 个文件（均为本次新归档）。"
        if skip:
            msg += f"\n跳过已归档文件 {skip} 个，未重复复制。"
        if renamed:
            msg += f"\n其中 {renamed} 个因目标目录存在同名文件，已自动重命名（追加序号）。"
        if fail:
            msg += f"\n失败 {fail} 个，请查看页面下方日志。"
        if n_ledger:
            msg += (f"\n\n已自动写入数据台账 {n_ledger} 条（《科研数据元信息采集》对应行），"
                    f"可在『数据台账』页查看或导出 Excel。")
        elif ok and not getattr(self, "_ledger_ok", False):
            msg += ("\n\n未填写台账填报信息，本次没有生成台账记录。"
                    "可到『数据台账』页填写后，用『导出』补录。")
        if ledger_err:
            msg += f"\n\n⚠ 台账写入失败：{ledger_err}"
        QMessageBox.information(self, "归档完成", msg)

    def _fail(self, msg):
        self.prog.setVisible(False)
        self.btn_go.setEnabled(True)
        self.lb_res.setText("✗ 归档失败")
        self.lb_res.setObjectName("danger")
        self._style(self.lb_res)
        QMessageBox.critical(self, "归档失败", msg)


class FlexTable(_FlexCols, QTableWidget):
    """列宽可手动调整的表格。"""

    def __init__(self, rows: int, cols: int):
        QTableWidget.__init__(self, rows, cols)
        self._init_flex(cols)


class FileTable(FlexTable):
    """候选文件表：支持拖入文件，空格键批量切换高亮行的勾选状态。"""

    dropped = Signal(list)
    spacePressed = Signal()

    def __init__(self, rows, cols):
        super().__init__(rows, cols)
        self.setAcceptDrops(True)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Space and self.selectedIndexes():
            self.spacePressed.emit()
            e.accept()
            return
        super().keyPressEvent(e)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        if e.mimeData().hasUrls():
            paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
            if paths:
                self.dropped.emit(paths)
            e.acceptProposedAction()
        else:
            super().dropEvent(e)


class DropTable(QWidget):
    """（已弃用）保留占位，避免旧引用报错。"""

    dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.hide()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.dropped.emit(paths)
        e.acceptProposedAction()


# --------------------------------------------------------------------------- #
# 第 3 页：归档自查
# --------------------------------------------------------------------------- #
class CheckPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.records = []
        self.shown = []
        self.scope = ""            # 当前检查范围绝对路径（空 = 整个归档根目录）
        self._scan_key = None      # 已扫描的 (根目录, 范围)，参数变化时不用重扫
        self._junk = 0             # 上次扫描被忽略的系统文件数

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        # 1 归档根目录 + 检查范围
        c1 = Card("检查范围与抽样规则",
                  "可以先指定一个子文件夹（一/二级分类），只检查该范围内的文件。", "1")
        r = QHBoxLayout()
        r.setSpacing(8)
        self.ed_root = QLineEdit()
        self.ed_root.setObjectName("path")
        self.ed_root.setPlaceholderText("请选择已初始化的归档根目录")
        self.ed_root.setReadOnly(True)
        b = QPushButton("  归档根目录…")
        b.setIcon(skin.icon("folder", 16, skin.TEXT_SUB))
        b.clicked.connect(self.pick_root)
        r.addWidget(self.ed_root, 1)
        r.addWidget(b)
        c1.body.addLayout(r)

        r2 = QHBoxLayout()
        r2.setSpacing(8)
        lab = QLabel("检查范围")
        lab.setMinimumWidth(56)
        self.cb_scope = QComboBox()
        self.cb_scope.setMinimumWidth(320)
        self.cb_scope.currentIndexChanged.connect(self._on_scope_selected)
        b2 = QPushButton("  其他子文件夹…")
        b2.setIcon(skin.icon("folder", 16, skin.TEXT_SUB))
        b2.setToolTip("也可以选到更深的子文件夹（例如初始化时创建的三级目录）")
        b2.clicked.connect(self.pick_scope)
        b_ref = QPushButton("  刷新")
        b_ref.setObjectName("ghost")
        b_ref.setIcon(skin.icon("refresh", 15, skin.TEXT_SUB))
        b_ref.setToolTip("按归档根目录的实际结构重新列出可检查的子文件夹")
        b_ref.clicked.connect(self.reload_scopes)
        r2.addWidget(lab)
        r2.addWidget(self.cb_scope, 1)
        r2.addWidget(b2)
        r2.addWidget(b_ref)
        c1.body.addLayout(r2)
        self.lb_scope = QLabel("")
        self.lb_scope.setObjectName("mono")
        self.lb_scope.setWordWrap(True)
        c1.body.addWidget(self.lb_scope)

        r3 = QHBoxLayout()
        r3.setSpacing(14)
        self.rb_all = QRadioButton("检查范围内全部文件")
        self.rb_ratio = QRadioButton("按二级分类随机抽样")
        self.rb_ratio.setChecked(True)
        b_scan = QPushButton("  开始检查")
        b_scan.setObjectName("primary")
        b_scan.setIcon(skin.icon("scan", 17, "#FFFFFF"))
        b_scan.setMinimumHeight(36)
        b_scan.clicked.connect(lambda: self.do_sample())
        r3.addWidget(self.rb_all)
        r3.addWidget(self.rb_ratio)
        r3.addStretch(1)
        r3.addWidget(b_scan)
        c1.body.addLayout(r3)

        # 抽样参数：比例由用户自己定，并可控每个分类的保底 / 封顶数量
        r3b = QHBoxLayout()
        r3b.setSpacing(7)
        r3b.addSpacing(24)
        self.sp_ratio = QDoubleSpinBox()
        self.sp_ratio.setRange(0.5, 100.0)
        self.sp_ratio.setDecimals(1)
        self.sp_ratio.setSingleStep(1.0)
        self.sp_ratio.setValue(10.0)
        self.sp_ratio.setSuffix(" %")
        self.sp_ratio.setFixedWidth(98)
        self.sp_ratio.setToolTip("每个二级分类（或所选范围内的子文件夹）按这个比例随机抽取")
        self.sp_min = QSpinBox()
        self.sp_min.setRange(0, 9999)
        self.sp_min.setValue(1)
        self.sp_min.setFixedWidth(74)
        self.sp_min.setToolTip("每个分类至少抽这么多个；该分类文件更少时取全部")
        self.sp_max = QSpinBox()
        self.sp_max.setRange(1, 99999)
        self.sp_max.setValue(20)
        self.sp_max.setFixedWidth(84)
        self.sp_max.setToolTip("每个分类最多抽这么多个，避免大分类拖垮复核工作量")
        for lab_txt, w in (("抽样比例", self.sp_ratio), ("每类至少", self.sp_min),
                           ("每类至多", self.sp_max)):
            lab = QLabel(lab_txt)
            lab.setObjectName("muted")
            r3b.addWidget(lab)
            r3b.addWidget(w)
        b_preset = QPushButton("  恢复默认")
        b_preset.setObjectName("ghost")
        b_preset.setIcon(skin.icon("refresh", 14, skin.TEXT_SUB))
        b_preset.setToolTip("恢复为 10% / 至少 1 个 / 至多 20 个")
        b_preset.clicked.connect(self.reset_rule)
        r3b.addWidget(b_preset)
        self.lb_rule = QLabel("")
        self.lb_rule.setObjectName("muted")
        r3b.addSpacing(6)
        r3b.addWidget(self.lb_rule)
        r3b.addStretch(1)
        c1.body.addLayout(r3b)

        self.rb_all.toggled.connect(self._on_rule_changed)
        self.sp_ratio.valueChanged.connect(self._on_rule_changed)
        self.sp_min.valueChanged.connect(self._on_rule_changed)
        self.sp_max.valueChanged.connect(self._on_rule_changed)
        self._on_rule_changed()

        self.chips = QHBoxLayout()
        self.chips.setSpacing(10)
        c1.body.addLayout(self.chips)
        self.chip_total = Chip("范围内文件：0", PRIMARY)
        self.chip_sub = Chip("涉及子文件夹：0 个", skin.TEAL)
        self.chip_n = Chip("本次展示：0", skin.WARN)
        self.chip_junk = Chip("", TEXT_MUTED)
        self.chip_junk.setToolTip(
            "扫描时自动忽略了这些系统/临时文件：\n"
            ".DS_Store、._*（macOS）、Thumbs.db、desktop.ini（Windows）、~$*（Office 锁文件）")
        self.chip_junk.setVisible(False)
        for c in (self.chip_total, self.chip_sub, self.chip_n, self.chip_junk):
            self.chips.addWidget(c)
        self.chips.addStretch(1)
        root.addWidget(c1)

        # 2 待检查文件列表
        c2 = Card()
        self.tb = FlexTable(0, 5)
        self.tb.setHorizontalHeaderLabels(
            ["✓", "文件名", "所属分类（相对归档根目录）", "大小", "修改时间"])
        self.tb.verticalHeader().setVisible(False)
        self.tb.verticalHeader().setDefaultSectionSize(34)
        self.tb.setAlternatingRowColors(True)
        self.tb.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tb.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tb.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tb.setMinimumHeight(170)
        self.tb.setColumnWidth(0, 38)
        self.tb.setColumnWidth(1, 320)
        self.tb.setColumnWidth(2, 420)
        self.tb.setColumnWidth(3, 84)
        self.tb.setColumnWidth(4, 146)
        self.tb.set_flex_minimums((36, 150, 150, 72, 120))
        self.tb.itemChanged.connect(self._on_item_changed)
        self.tb.doubleClicked.connect(lambda idx: self.open_file())
        c2.body.addWidget(self.tb, 1)
        self.lb_tip = QLabel("提示：双击表格行可直接打开文件；勾选最左侧复选框标记归档有问题的文件，"
                             "再点底部『导出问题文件清单』。")
        self.lb_tip.setObjectName("muted")
        self.lb_tip.setWordWrap(True)
        c2.body.addWidget(self.lb_tip)
        root.addWidget(c2, 1)

        # 主操作条（固定在窗口底部）
        self.actions = ActionBar()
        self.lb_pick = QLabel("已标记问题文件 0 个")
        self.lb_pick.setObjectName("muted")
        b_open = QPushButton("  打开文件")
        b_open.setIcon(skin.icon("file", 15, skin.TEXT_SUB))
        b_open.clicked.connect(self.open_file)
        b_loc = QPushButton("  定位所在文件夹")
        b_loc.setIcon(skin.icon("folder", 15, skin.TEXT_SUB))
        b_loc.clicked.connect(lambda: self.locate())
        b_clear = QPushButton("  清空标记")
        b_clear.setObjectName("ghost")
        b_clear.setIcon(skin.icon("x", 15, skin.TEXT_SUB))
        b_clear.clicked.connect(self.clear_marks)
        b_exp = QPushButton("  导出问题文件清单")
        b_exp.setObjectName("primary")
        b_exp.setIcon(skin.icon("download", 16, "#FFFFFF"))
        b_exp.setMinimumHeight(40)
        b_exp.clicked.connect(self.export)
        self.actions.row.addWidget(self.lb_pick)
        self.actions.row.addStretch(1)
        self.actions.row.addWidget(b_open)
        self.actions.row.addWidget(b_loc)
        self.actions.row.addWidget(b_clear)
        self.actions.row.addWidget(b_exp)

    # ------------------------------------------------------------------ 范围
    def _set_chips(self, total, nsub, n2, njunk=0):
        self.chip_total.set_text(f"范围内文件：{total}")
        self.chip_sub.set_text(f"涉及子文件夹：{nsub} 个")
        self.chip_n.set_text(f"本次展示：{n2}")
        self.chip_junk.set_text(f"已忽略系统文件：{njunk} 个")
        self.chip_junk.setVisible(njunk > 0)

    def set_root(self, path):
        self.ed_root.setText(os.path.normpath(path) if path else "")
        self.records = []
        self.shown = []
        self._scan_key = None
        self._junk = 0
        self._load_rule()
        self.reload_scopes()
        self.do_sample(silent=True)

    def pick_root(self):
        d = QFileDialog.getExistingDirectory(self, "选择已初始化的归档根目录",
                                             self.ed_root.text() or os.path.expanduser("~"))
        if d:
            if not core.is_initialized(d):
                QMessageBox.warning(self, "未初始化", "所选目录不是本软件初始化的归档目录。")
                return
            self.win.set_root(os.path.normpath(d))

    def reload_scopes(self):
        """按归档根目录的实际结构重建「检查范围」下拉框。"""
        root = self.ed_root.text().strip()
        keep = self.scope
        self.cb_scope.blockSignals(True)
        self.cb_scope.clear()
        if not root or not core.is_initialized(root):
            self.cb_scope.addItem("（请先选择归档根目录）", "")
            self.cb_scope.setEnabled(False)
            self.cb_scope.blockSignals(False)
            self.scope = ""
            self.lb_scope.setText("")
            return
        self.cb_scope.setEnabled(True)
        self.cb_scope.addItem("整个归档目录（全部一级 / 二级分类）", os.path.normpath(root))
        for text, path, _lv in core.list_scope_folders(root):
            self.cb_scope.addItem(text, os.path.normpath(path))
        idx = self.cb_scope.findData(keep) if keep else 0
        self.cb_scope.setCurrentIndex(idx if idx >= 0 else 0)
        self.cb_scope.blockSignals(False)
        self._on_scope_changed()

    def _on_scope_changed(self):
        root = self.ed_root.text().strip()
        picked = self.cb_scope.currentData() or ""
        if not picked or (root and os.path.normpath(picked) == os.path.normpath(root)):
            self.scope = ""
            base = root
        else:
            self.scope = picked
            base = picked
        if not base:
            self.lb_scope.setText("")
            return
        try:
            rel = os.path.relpath(base, root)
        except ValueError:
            rel = base
        show = "整个归档目录" if rel == "." else rel
        self.lb_scope.setText(f"当前检查范围：{show}    （{base}）")

    def _on_scope_selected(self, *_):
        """用户切换检查范围：立刻按新范围重算，不用再点一次『开始检查』。"""
        self._on_scope_changed()
        self.do_sample(silent=True, force=False)

    def pick_scope(self):
        root = self.ed_root.text().strip()
        if not root or not core.is_initialized(root):
            QMessageBox.warning(self, "提示", "请先选择已初始化的归档根目录。")
            return
        d = QFileDialog.getExistingDirectory(
            self, "选择要检查的子文件夹（须位于归档根目录之内）", root)
        if not d:
            return
        if not core.in_scope(root, d):
            QMessageBox.warning(self, "范围不合法",
                                "所选文件夹必须位于当前归档根目录之内。\n\n"
                                "如需检查别的目录，请先切换归档根目录。")
            return
        d = os.path.normpath(d)
        idx = self.cb_scope.findData(d)
        if idx < 0:
            self.cb_scope.blockSignals(True)
            self.cb_scope.addItem("│    └ " + os.path.relpath(d, root), d)
            self.cb_scope.blockSignals(False)
            idx = self.cb_scope.count() - 1
        self.cb_scope.setCurrentIndex(idx)
        self.do_sample(silent=True, force=False)

    # ------------------------------------------------------------------ 抽样规则
    DEFAULT_RULE = {"ratio": 10.0, "min": 1, "max": 20, "mode": "ratio"}

    def _on_rule_changed(self, *_):
        ratio_mode = self.rb_ratio.isChecked()
        for w in (self.sp_ratio, self.sp_min, self.sp_max):
            w.setEnabled(ratio_mode)
        if self.sp_max.value() < self.sp_min.value():
            self.sp_max.blockSignals(True)
            self.sp_max.setValue(self.sp_min.value())
            self.sp_max.blockSignals(False)
        self._update_rule_label()
        self._save_rule()
        # 规则一变就按新规则重算；不重新扫描目录，秒出结果
        if getattr(self, "records", None):
            self.do_sample(silent=True, force=False)

    def _update_rule_label(self):
        if self.rb_all.isChecked():
            self.lb_rule.setText("列出范围内全部文件，不做抽样")
            return
        n = len(self.shown) if getattr(self, "records", None) else 0
        txt = (f"每个分类抽 {self.sp_ratio.value():g}%，至少 {self.sp_min.value()} 个、"
               f"至多 {self.sp_max.value()} 个")
        if self.records:
            txt += f" → 本次 {n}/{len(self.records)} 个"
        self.lb_rule.setText(txt)

    def _save_rule(self):
        root = self.ed_root.text().strip()
        if root and core.is_initialized(root):
            core.manifest_set(root, "sample_rule", {
                "ratio": self.sp_ratio.value(),
                "min": self.sp_min.value(),
                "max": self.sp_max.value(),
                "mode": "all" if self.rb_all.isChecked() else "ratio",
            })

    def _load_rule(self):
        root = self.ed_root.text().strip()
        rule = core.manifest_get(root, "sample_rule", {}) \
            if (root and core.is_initialized(root)) else {}
        if not isinstance(rule, dict):
            rule = {}
        rule = {**self.DEFAULT_RULE, **rule}
        for w, key in ((self.sp_ratio, "ratio"), (self.sp_min, "min"), (self.sp_max, "max")):
            w.blockSignals(True)
            try:
                w.setValue(type(w.value())(rule[key]))
            except (TypeError, ValueError):
                pass
            w.blockSignals(False)
        self.rb_all.blockSignals(True)
        self.rb_ratio.blockSignals(True)
        self.rb_all.setChecked(rule.get("mode") == "all")
        self.rb_ratio.setChecked(rule.get("mode") != "all")
        self.rb_all.blockSignals(False)
        self.rb_ratio.blockSignals(False)
        self._on_rule_changed()

    def reset_rule(self):
        self.sp_ratio.setValue(self.DEFAULT_RULE["ratio"])
        self.sp_min.setValue(self.DEFAULT_RULE["min"])
        self.sp_max.setValue(self.DEFAULT_RULE["max"])

    def sample_params(self):
        """当前抽样参数：(比例, 每类最少, 每类最多)。"""
        return (self.sp_ratio.value() / 100.0, self.sp_min.value(), self.sp_max.value())

    # ------------------------------------------------------------------ 抽样
    def do_sample(self, silent=False, force=True):
        root = self.ed_root.text().strip()
        if not root or not core.is_initialized(root):
            if not silent:
                QMessageBox.warning(self, "提示", "请先选择已初始化的归档根目录。")
            return
        scope = self.scope or root
        key = (root, scope)
        if force or key != getattr(self, "_scan_key", None):
            stats = {}
            self.records = core.scan_archive(root, scope, stats)
            self._junk = stats.get("junk_skipped", 0)
            self._scan_key = key
        mode = "all" if self.rb_all.isChecked() else "ratio"
        ratio, mn, mx = self.sample_params()
        self.shown = core.sample_archive(self.records, mode, ratio, mn, mx,
                                         random.Random())
        self.fill_table()
        self._set_chips(len(self.records),
                        len({r["group"] for r in self.records}), len(self.shown),
                        getattr(self, "_junk", 0))
        self._update_rule_label()
        if not self.records and not silent:
            QMessageBox.information(
                self, "提示",
                f"该范围内还没有文件：\n{scope}\n\n"
                f"可以换一个检查范围，或先到『文件归档』页面归档数据。")

    def fill_table(self):
        self.tb.blockSignals(True)
        self.tb.setRowCount(len(self.shown))
        for i, r in enumerate(self.shown):
            it0 = QTableWidgetItem("")
            it0.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            it0.setCheckState(Qt.Unchecked)
            self.tb.setItem(i, 0, it0)
            self.tb.setItem(i, 1, QTableWidgetItem(r["name"]))
            it2 = QTableWidgetItem(os.path.dirname(r["rel"]) or core.ROOT_LABEL)
            it2.setForeground(QColor(PRIMARY))
            it2.setToolTip("文件在归档目录中的分类位置（相对归档根目录）")
            self.tb.setItem(i, 2, it2)
            it3 = QTableWidgetItem(core.human_size(r["size"]))
            it3.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tb.setItem(i, 3, it3)
            it4 = QTableWidgetItem(r["mtime"])
            it4.setForeground(QColor(TEXT_MUTED))
            self.tb.setItem(i, 4, it4)
        self.tb.blockSignals(False)
        self.lb_pick.setText("已标记问题文件 0 个")
        self.lb_pick.setObjectName("muted")
        self.lb_pick.style().unpolish(self.lb_pick)
        self.lb_pick.style().polish(self.lb_pick)

    def _on_item_changed(self, item):
        if item.column() != 0:
            return
        n = sum(1 for i in range(self.tb.rowCount())
                if self.tb.item(i, 0) and self.tb.item(i, 0).checkState() == Qt.Checked)
        self.lb_pick.setText(f"已标记问题文件 {n} 个")
        self.lb_pick.setObjectName("warn" if n else "muted")
        self.lb_pick.style().unpolish(self.lb_pick)
        self.lb_pick.style().polish(self.lb_pick)

    def _current(self):
        i = self.tb.currentRow()
        if i < 0 or i >= len(self.shown):
            QMessageBox.information(self, "提示", "请先在表格中选择一行。")
            return None
        return self.shown[i]

    def open_file(self):
        r = self._current()
        if r:
            open_in_explorer(r["path"])

    def locate(self):
        r = self._current()
        if r:
            open_in_explorer(r["path"], select=True)

    def clear_marks(self):
        self.tb.blockSignals(True)
        for i in range(self.tb.rowCount()):
            if self.tb.item(i, 0):
                self.tb.item(i, 0).setCheckState(Qt.Unchecked)
        self.tb.blockSignals(False)
        self._on_item_changed(QTableWidgetItem())

    def export(self):
        picked = [self.shown[i] for i in range(self.tb.rowCount())
                  if self.tb.item(i, 0) and self.tb.item(i, 0).checkState() == Qt.Checked]
        if not picked:
            QMessageBox.information(self, "提示", "还没有勾选任何问题文件。\n\n"
                                                  "请先在左侧复选框标记归档有问题的文件。")
            return
        default = os.path.join(os.path.expanduser("~"),
                               f"问题文件清单_{_dt.datetime.now():%Y%m%d_%H%M}.csv")
        path, _ = QFileDialog.getSaveFileName(self, "导出问题文件清单", default,
                                              "CSV 文件 (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(["序号", "文件名", "所属分类（相对归档根目录）", "完整路径",
                            "大小(字节)", "修改时间", "问题描述（请填写）"])
                for i, r in enumerate(picked, 1):
                    w.writerow([i, r["name"], os.path.dirname(r["rel"]) or core.ROOT_LABEL,
                                r["path"], r["size"], r["mtime"], ""])
            if QMessageBox.question(self, "导出成功",
                                    f"已导出 {len(picked)} 条记录：\n{path}\n\n是否打开该文件？"
                                    ) == QMessageBox.Yes:
                open_in_explorer(path)
        except Exception as e:                                        # noqa: BLE001
            QMessageBox.critical(self, "导出失败", str(e))


# --------------------------------------------------------------------------- #
# 数据台账
# --------------------------------------------------------------------------- #
class LedgerMetaDialog(QDialog):
    """编辑台账默认填报信息（写进《科研数据元信息采集》每一行的固定列）。"""

    def __init__(self, meta: dict, parent=None, first_time: bool = False):
        super().__init__(parent)
        self.setWindowTitle("台账填报信息 · " + core.APP_NAME)
        self.resize(660, 640)
        self.inputs = {}
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 18, 18, 16)
        v.setSpacing(12)

        head = QLabel("台账填报信息")
        head.setObjectName("h1")
        v.addWidget(head)
        desc = QLabel(
            "这些字段会写进《科研数据元信息采集》里对应那一行的固定列（填报中心、共享方式等）。"
            "填一次即可，以后每次归档自动带入；随时可以在『数据台账』页修改。")
        desc.setObjectName("muted")
        desc.setWordWrap(True)
        v.addWidget(desc)

        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        form = QFormLayout(inner)
        form.setContentsMargins(2, 2, 14, 2)
        form.setSpacing(9)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        for name, options, tip in ledger.META_FIELDS:
            lab = QLabel(name)
            lab.setToolTip(tip)
            cur = str((meta or {}).get(name, "") or "")
            if options:
                w = QComboBox()
                w.setEditable(True)
                w.addItems(options)
                w.setCurrentText(cur)
                w.setMinimumWidth(320)
            else:
                w = QLineEdit()
                w.setText(cur)
                w.setPlaceholderText(tip)
                w.setMinimumWidth(320)
            w.setToolTip(tip)
            form.addRow(lab, w)
            self.inputs[name] = w
        area.setWidget(inner)
        v.addWidget(area, 1)

        row = QHBoxLayout()
        row.addStretch(1)
        b_cancel = QPushButton("  暂不填写" if first_time else "  取消")
        b_cancel.setObjectName("ghost")
        b_cancel.clicked.connect(self.reject)
        b_ok = QPushButton("  保存")
        b_ok.setObjectName("primary")
        b_ok.setMinimumWidth(120)
        b_ok.clicked.connect(self.accept)
        row.addWidget(b_cancel)
        row.addWidget(b_ok)
        v.addLayout(row)

    def values(self) -> dict:
        out = {}
        for name, w in self.inputs.items():
            txt = w.currentText() if isinstance(w, QComboBox) else w.text()
            out[name] = (txt or "").strip()
        return out


class LedgerPage(QWidget):
    """数据台账：查看归档自动生成的元信息记录，导出官方表结构的 Excel。"""

    COLS = ["归档时间", "一级分类", "二级分类", "序号", "数量统计值", "数量统计单位",
            "填报中心", "填报人姓名", "存储位置详情（选填）", "备注"]

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.rows = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        c1 = Card("数据台账（对应《科研数据元信息采集》的行）",
                  "每次归档成功后，软件会自动把本次归档的数据汇总成台账记录，"
                  "字段与《附件1：科研数据元信息采集》逐列对应，可直接复制回官方文件。", "1")
        r = QHBoxLayout()
        r.setSpacing(8)
        self.lb_meta = QLabel("尚未填写填报信息")
        self.lb_meta.setObjectName("muted")
        self.lb_meta.setWordWrap(True)
        b_edit = QPushButton("  编辑填报信息…")
        b_edit.setIcon(skin.icon("sliders", 16, skin.TEXT_SUB))
        b_edit.clicked.connect(self.edit_meta)
        r.addWidget(self.lb_meta, 1)
        r.addWidget(b_edit)
        c1.body.addLayout(r)

        r2 = QHBoxLayout()
        r2.setSpacing(10)
        r2.addWidget(QLabel("台账粒度"))
        self.cb_gran = QComboBox()
        self.cb_gran.addItem("按归档批次汇总（推荐，与官方表『数量统计值』口径一致）", "batch")
        self.cb_gran.addItem("按文件逐条登记", "file")
        self.cb_gran.setMinimumWidth(300)
        self.cb_gran.currentIndexChanged.connect(self._on_gran)
        r2.addWidget(self.cb_gran)
        r2.addStretch(1)
        b_ref = QPushButton("  刷新")
        b_ref.setObjectName("ghost")
        b_ref.setIcon(skin.icon("refresh", 15, skin.TEXT_SUB))
        b_ref.clicked.connect(self.reload)
        r2.addWidget(b_ref)
        c1.body.addLayout(r2)

        self.chips = QHBoxLayout()
        self.chips.setSpacing(10)
        c1.body.addLayout(self.chips)
        self.chip_n = Chip("台账记录：0 条", PRIMARY)
        self.chip_l1 = Chip("覆盖一级分类：0 个", skin.TEAL)
        self.chip_last = Chip("最近写入：—", skin.WARN)
        for c in (self.chip_n, self.chip_l1, self.chip_last):
            self.chips.addWidget(c)
        self.chips.addStretch(1)
        root.addWidget(c1)

        c2 = Card()
        self.tb = FlexTable(0, len(self.COLS))
        self.tb.setHorizontalHeaderLabels(self.COLS)
        self.tb.verticalHeader().setVisible(False)
        self.tb.verticalHeader().setDefaultSectionSize(30)
        self.tb.setAlternatingRowColors(True)
        self.tb.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tb.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tb.setMinimumHeight(170)
        # 设计列宽之和已超过常见窗口宽度 → 保持设计宽度并横向滚动，保证内容读得全。
        # 下限就取设计宽度，这样窗口变窄时也不会把这 10 列压到读不清。
        # 前三列按"能完整显示不省略"来定：时间戳 19 字符、一级/二级分类各 11/10 个汉字。
        LEDGER_W = (166, 156, 150, 52, 80, 86, 120, 80, 235, 215)
        for i, w in enumerate(LEDGER_W):
            self.tb.setColumnWidth(i, w)
        self.tb.set_flex_minimums(LEDGER_W)
        c2.body.addWidget(self.tb, 1)
        self.lb_tip = QLabel("提示：上表是台账的汇总视图，列较多时可左右拖动表头调宽，"
                             "或拖动表格下方的横向滚动条查看右侧列；完整 30 列数据在 "
                             "_归档索引/科研数据元信息台账.csv，导出的 xlsx 按官方分 sheet 排布。")
        self.lb_tip.setObjectName("muted")
        self.lb_tip.setWordWrap(True)
        c2.body.addWidget(self.lb_tip)
        root.addWidget(c2, 1)

        self.actions = ActionBar()
        self.lb_cnt = QLabel("—")
        self.lb_cnt.setObjectName("muted")
        b_xlsx = QPushButton("  导出 Excel 台账（官方表结构）")
        b_xlsx.setObjectName("primary")
        b_xlsx.setIcon(skin.icon("download", 16, "#FFFFFF"))
        b_xlsx.setMinimumHeight(40)
        b_xlsx.clicked.connect(self.export_xlsx)
        b_open = QPushButton("  打开台账文件")
        b_open.setIcon(skin.icon("sheet", 15, skin.TEXT_SUB))
        b_open.clicked.connect(self.open_ledger)
        b_dir = QPushButton("  打开索引目录")
        b_dir.setIcon(skin.icon("folder", 15, skin.TEXT_SUB))
        b_dir.clicked.connect(self.open_index_dir)
        self.actions.row.addWidget(self.lb_cnt)
        self.actions.row.addStretch(1)
        self.actions.row.addWidget(b_open)
        self.actions.row.addWidget(b_dir)
        self.actions.row.addWidget(b_xlsx)

    # ------------------------------------------------------------------ 数据
    def _root(self) -> str:
        return self.win.root or ""

    def _meta(self) -> dict:
        root = self._root()
        if not root or not core.is_initialized(root):
            return {}
        return core.manifest_get(root, "ledger_meta", {}) or {}

    def _granularity(self) -> str:
        return self.cb_gran.currentData() or "batch"

    def _on_gran(self):
        root = self._root()
        if root and core.is_initialized(root):
            core.manifest_set(root, "ledger_granularity", self._granularity())

    def set_root(self, path):
        root = path or ""
        if root and core.is_initialized(root):
            gran = core.manifest_get(root, "ledger_granularity", "batch")
            i = self.cb_gran.findData(gran)
            if i >= 0:
                self.cb_gran.blockSignals(True)
                self.cb_gran.setCurrentIndex(i)
                self.cb_gran.blockSignals(False)
        self.reload()

    def reload(self):
        root = self._root()
        meta = self._meta()
        if not root or not core.is_initialized(root):
            self.rows = []
            self.lb_meta.setText("尚未选择归档根目录")
            self.lb_cnt.setText("—")
            self.chip_n.set_text("台账记录：0 条")
            self.chip_l1.set_text("覆盖一级分类：0 个")
            self.chip_last.set_text("最近写入：—")
            self._fill([])
            return
        center = meta.get("填报中心") or "（未填）"
        who = meta.get("填报人姓名") or "（未填）"
        done = any(meta.get(k) for k in ("填报中心", "填报人姓名"))
        self.lb_meta.setText(
            f"当前填报信息：填报中心 {center} · 填报人 {who} · "
            f"介质 {meta.get('存储介质类型') or '—'} · "
            f"院内共享 {meta.get('院内共享是否允许') or '—'}"
            + ("" if done else "　← 建议先点右侧『编辑填报信息』补全"))
        self.lb_meta.setObjectName("muted")
        _h, rows = ledger.read_rows(root)
        self.rows = rows
        self._fill(rows)
        self.chip_n.set_text(f"台账记录：{len(rows)} 条")
        self.chip_l1.set_text(f"覆盖一级分类：{len({(r.get('一级分类') or '').strip() for r in rows})} 个"
                              if rows else "覆盖一级分类：0 个")
        times = [r.get("归档时间", "") for r in rows if r.get("归档时间")]
        self.chip_last.set_text("最近写入：" + (max(times) if times else "—"))
        self.lb_cnt.setText("台账文件：" + os.path.basename(ledger.ledger_csv_path(root)))

    def _fill(self, rows):
        self.tb.blockSignals(True)
        self.tb.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for c, name in enumerate(self.COLS):
                v = str(r.get(name, "") or "")
                it = QTableWidgetItem(v)
                if name in ("序号", "数量统计值", "数量统计单位"):
                    it.setTextAlignment(Qt.AlignCenter)
                if name == "一级分类":
                    it.setForeground(QColor(PRIMARY))
                if name == "备注":
                    it.setToolTip(v)
                self.tb.setItem(i, c, it)
        self.tb.blockSignals(False)

    # ------------------------------------------------------------------ 操作
    def edit_meta(self):
        root = self._root()
        if not root or not core.is_initialized(root):
            QMessageBox.warning(self, "提示", "请先选择已初始化的归档根目录。")
            return
        dlg = LedgerMetaDialog(self._meta(), self)
        if dlg.exec() == QDialog.Accepted:
            core.manifest_set(root, "ledger_meta", dlg.values())
            self.reload()
            QMessageBox.information(self, "已保存", "台账填报信息已保存，之后归档会自动带入。")

    def export_xlsx(self):
        root = self._root()
        if not root or not core.is_initialized(root):
            QMessageBox.warning(self, "提示", "请先选择已初始化的归档根目录。")
            return
        if not self.rows:
            QMessageBox.information(self, "提示", "台账还没有任何记录。\n\n"
                                                  "请先到『文件归档』页完成一次归档。")
            return
        try:
            path = ledger.export_xlsx(root)
        except ImportError:
            QMessageBox.warning(self, "缺少组件",
                                "当前环境没有 Excel 导出组件（openpyxl）。\n\n"
                                "可以先使用 CSV 台账，或用 Excel 直接打开：\n"
                                + ledger.ledger_csv_path(root))
            return
        except Exception as e:                                        # noqa: BLE001
            QMessageBox.critical(self, "导出失败", str(e))
            return
        if QMessageBox.question(self, "导出成功",
                                f"已导出 {len(self.rows)} 条台账记录：\n{path}\n\n"
                                f"每个一级分类一张 sheet，列序与官方文件一致，"
                                f"可整行复制粘贴回《科研数据元信息采集》。\n\n是否打开？"
                                ) == QMessageBox.Yes:
            open_in_explorer(path)

    def open_ledger(self):
        root = self._root()
        if not root:
            QMessageBox.warning(self, "提示", "请先选择归档根目录。")
            return
        p = ledger.ledger_csv_path(root)
        if not os.path.isfile(p):
            QMessageBox.information(self, "提示", "台账文件还不存在，完成一次归档后会自动生成。")
            return
        open_in_explorer(p)

    def open_index_dir(self):
        root = self._root()
        if not root:
            QMessageBox.warning(self, "提示", "请先选择归档根目录。")
            return
        d = os.path.join(root, core.INDEX_DIR)
        if os.path.isdir(d):
            open_in_explorer(d)
        else:
            open_in_explorer(root)


# --------------------------------------------------------------------------- #
# 帮助
# --------------------------------------------------------------------------- #
HELP_TEXT = """
<h3 style="margin:0 0 6px 0;">四步完成科研数据归档</h3>
<p style="color:#5A6B84;margin:0 0 14px 0;">无需培训，按左侧导航从上到下操作即可。</p>

<p><b>① 初始化归档目录</b><br>
选择一个<b>空的文件夹</b>（或尚不存在的路径）作为归档根目录，然后在下方分类树里<b>勾选要创建的分类</b>，
点『初始化归档目录』即可。<br>
· <b>只创建勾选的那部分</b>——不需要的一级/二级/三级分类取消勾选就不会建出来，
  分类树总共 5 个一级、30 个二级（另有三、四级共 76 / 251 个可作细分参考）；
· 勾选某个子目录时，它的上级目录会<b>自动一起建出来</b>（父目录必须存在）；
  『全选 / 全不选』可一键切换，底部会实时显示"将创建 一级 x 个 · 二级 y 个 · 合计 n 个目录"；
· 勾『同时列出三级分类子目录』可以把三级也纳入选择；
· 选多了或后来需要补：再勾上缺失的，点『补齐勾选的分类目录』即可，<b>已建目录与已有数据不受影响</b>；
· 初始化会生成《归档说明.md》（只列实际创建的目录）与归档索引。一个归档根目录只需初始化一次。</p>

<p><b>② 文件归档</b><br>
先选择归档根目录，然后用『扫描文件夹』或『添加文件』把候选数据<b>先放进下方列表预览</b>；
再在列表最左侧的『归档』列<b>勾选</b>真正要归档的文件——可点选、按住 Ctrl / Shift 多选，
选中行后按<b>空格键</b>批量勾选或取消，也可用上方的『全选 / 全不选 / 反选 / 勾选高亮行』。
最后选择一级、二级分类，点击『开始归档』。<br>
· 归档是 <b>复制</b> 操作，<b>不会删除原始文件</b>；<br>
· <b>已归档的文件不会重复复制</b>：列表中会显示 <b>[已归档]</b> 标记且无法再勾选；<br>
· 只有从未归档的文件才真正复制；若目标目录已有同名同大小文件，也按已归档直接跳过，
  不会生成"xxx(1).xxx"这类副本；<br>
· 每次归档都会写入 <code>_归档索引/归档日志.csv</code>，便于追溯。</p>

<p><b>③ 归档自查</b><br>
先选归档根目录，再用『检查范围』下拉框把范围收窄到某个<b>一级或二级分类子文件夹</b>
（也可以点『其他子文件夹…』选到更深的目录，如三级目录）。<br>
然后在所选范围内点击『开始检查』，规则可选『检查范围内全部文件』或
<b>『按二级分类随机抽样』——比例由你自己填</b>（默认 10%，可填 0.5%～100%，每个分类独立计算）；
还能设定每个分类的<b>保底数量</b>（默认至少 1 个）和<b>封顶数量</b>（默认至多 20 个），
避免大分类拖垮复核工作量。参数一改就立刻按新规则重算，不用再点一次『开始检查』；
点『恢复默认』回到 10% / 至少 1 个 / 至多 20 个。抽样规则按归档根目录记忆，下次打开自动沿用。
在表格中勾选归档有问题的文件，点击底部『导出问题文件清单』即可得到 CSV 清单。</p>

<p><b>④ 数据台账</b><br>
<b>每次归档成功后会自动生成台账记录</b>——也就是《附件1：科研数据元信息采集》里对应的那一行。
首次归档前会请你填一次「填报中心、填报人、存储介质、共享方式」等固定字段，填一次长期有效，
之后每次归档自动带入，不再打断你。<br>
· 台账默认<b>按归档批次汇总</b>（数量统计值 = 本次归档的文件数），与官方表的口径一致，
  也可在『数据台账』页切换为<b>按文件逐条</b>登记；<br>
· 台账存在 <code>_归档索引/科研数据元信息台账.csv</code>；<br>
· 点『导出 Excel 台账』会生成 <code>科研数据元信息台账.xlsx</code>，
  <b>每个一级分类一张 sheet、列序与官方文件完全一致</b>，可整行复制粘贴回官方表；<br>
· 已自动带出：二级分类、数量统计值与单位、存储位置详情、填报时间、来源路径、备注；
  需要人工补的是三级/四级分类（选填）和关联项目编号这类只有你知道的信息。</p>

<hr style="border:none;border-top:1px solid #DDE5F1;margin:14px 0;">

<p><b>几点说明</b></p>
<ul style="color:#5A6B84;margin:4px 0 0 0;">
<li><b>系统文件会自动忽略</b>：扫描（归档候选与归档自查）时会跳过
    <code>.DS_Store</code>、<code>._*</code>、<code>Thumbs.db</code>、<code>desktop.ini</code>、
    <code>~$xxx.xlsx</code> 这类操作系统和 Office 自动生成的临时文件——它们不是科研数据本体。
    被忽略的数量会在界面上提示，不会静默吞掉。</li>
<li><b>主操作按钮固定在窗口底部</b>：『初始化归档目录』『开始归档』『导出问题文件清单』『导出 Excel 台账』
    始终显示在底部操作条上，内容再长也不用滚动去找。</li>
<li><b>表格列宽都能拖动调整</b>：把鼠标移到表头两列之间的<b>分隔线</b>上，光标变成左右箭头后拖动即可。
    列少的表会<b>按比例铺满窗口</b>——把某一列拖宽，其余列自动让出空间；
    列多的表（如数据台账 10 列）<b>不会把列压到读不清</b>，放不下时表格下方会出现<b>横向滚动条</b>，
    拖动它即可查看右侧的列。</li>
<li>分类名中的 <code>/</code> 等 Windows 非法字符会替换为全角字符（如 <code>粒度/颗粒/粉末分析</code> → <code>粒度／颗粒／粉末分析</code>）。</li>
<li>『智能推荐』依据文件名关键词给出建议，<b>仅供参考</b>，请务必人工确认。</li>
<li>归档根目录下的 <code>_归档索引</code> 是软件的数据目录，请勿手工删改。</li>
</ul>
"""


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("使用说明 · " + core.APP_NAME)
        self.resize(660, 620)
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 18, 18, 16)
        v.setSpacing(12)
        head = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(skin.pixmap("help", 22, PRIMARY))
        t = QLabel("使用说明")
        t.setObjectName("h1")
        head.addWidget(ic)
        head.addWidget(t)
        head.addStretch(1)
        v.addLayout(head)
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        lab = QLabel(HELP_TEXT)
        lab.setTextFormat(Qt.RichText)
        lab.setWordWrap(True)
        lab.setStyleSheet("background:#FFFFFF;border:1px solid #DCE5F1;border-radius:12px;padding:16px;")
        lab.setAlignment(Qt.AlignTop)
        area.setWidget(lab)
        v.addWidget(area, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        b = QPushButton("知道了")
        b.setObjectName("primary")
        b.setMinimumWidth(110)
        b.clicked.connect(self.accept)
        row.addWidget(b)
        v.addLayout(row)


# --------------------------------------------------------------------------- #
# 主窗口
# --------------------------------------------------------------------------- #
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1210, 800)
        self.setMinimumSize(1020, 640)
        self._fit_screen()
        self.root = ""

        central = QWidget()
        self.setCentralWidget(central)
        h = QHBoxLayout(central)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        h.addWidget(self._build_sidebar())

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(0)
        rv.addWidget(self._build_topbar())

        self.stack = QStackedWidget()
        wrap = QWidget()
        wv = QVBoxLayout(wrap)
        wv.setContentsMargins(20, 18, 20, 16)
        wv.setSpacing(0)
        wv.addWidget(self.stack)
        # 小屏幕 / 缩放较大时内容可滚动，避免控件被裁掉
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
            "QScrollArea>QWidget>QWidget{background:transparent;}")
        scroll.setWidget(wrap)
        rv.addWidget(scroll, 1)
        h.addWidget(right, 1)

        self.page_init = InitPage(self)
        self.page_arch = ArchivePage(self)
        self.page_check = CheckPage(self)
        self.page_ledger = LedgerPage(self)
        self.pages = (self.page_init, self.page_arch, self.page_check, self.page_ledger)
        for p in self.pages:
            self.stack.addWidget(p)

        # 底部固定操作条：与页面同步切换，主按钮永远可见（不受内容滚动影响）
        self.actions = QStackedWidget()
        self.actions.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        for p in self.pages:
            self.actions.addWidget(p.actions)
        rv.addWidget(self.actions)

        sb = QStatusBar()
        sb.setSizeGripEnabled(False)
        self.lb_status = QLabel("就绪 · 尚未选择归档根目录")
        sb.addWidget(self.lb_status, 1)
        sb.addPermanentWidget(QLabel(f"{core.APP_NAME} v{core.APP_VERSION} · 分类树 v1.0"))
        self.setStatusBar(sb)

        self.page_init.initialized.connect(self.set_root)
        self.nav[0].setChecked(True)
        self.goto(0)

    # -------------------------------------------------------------- 窗口自适应
    def _fit_screen(self):
        """按屏幕可用区域取一个舒适的初始尺寸并居中。"""
        try:
            scr = QGuiApplication.primaryScreen()
            if scr is None:
                return
            avail = scr.availableGeometry()
            w = min(1320, max(1020, avail.width() - 100))
            h = min(960, max(660, avail.height() - 80))
            self.resize(w, h)
            self.move(avail.x() + max(0, (avail.width() - w) // 2),
                      avail.y() + max(0, (avail.height() - h) // 2))
        except Exception:
            pass

    # -------------------------------------------------------------- 侧边栏
    def _build_sidebar(self):
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(214)
        v = QVBoxLayout(side)
        v.setContentsMargins(14, 20, 14, 12)
        v.setSpacing(6)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(skin.pixmap("layers", 24, "#FFFFFF"))
        logo.setFixedSize(26, 26)
        bt = QVBoxLayout()
        bt.setSpacing(0)
        t1 = QLabel("科研数据归档")
        t1.setObjectName("brand")
        t2 = QLabel("Research Data Archiver")
        t2.setObjectName("brandSub")
        bt.addWidget(t1)
        bt.addWidget(t2)
        brand.addWidget(logo)
        brand.addLayout(bt)
        brand.addStretch(1)
        v.addLayout(brand)
        v.addSpacing(16)

        g = QLabel("工作流程")
        g.setObjectName("navGroup")
        v.addWidget(g)
        v.addSpacing(2)

        self.nav = []
        for i, (txt, ic) in enumerate([("初始化归档目录", "folder_plus"),
                                       ("文件归档", "inbox"),
                                       ("归档自查", "clipboard"),
                                       ("数据台账", "table")]):
            b = QPushButton("  " + txt)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setIcon(skin.dual_icon(ic, 18))
            b.setIconSize(QSize(18, 18))
            b.clicked.connect(lambda _=False, k=i: self.goto(k))
            v.addWidget(b)
            self.nav.append(b)

        v.addStretch(1)

        tip = QFrame()
        tip.setObjectName("sideFoot")
        tv = QVBoxLayout(tip)
        tv.setContentsMargins(4, 10, 4, 0)
        tv.setSpacing(3)
        lb = QLabel("当前归档根目录")
        lb.setObjectName("sideFootTxt")
        self.lb_side_root = QLabel("未设置")
        self.lb_side_root.setObjectName("sideFootTxt")
        self.lb_side_root.setWordWrap(True)
        self.lb_side_root.setStyleSheet("color:#9FB4D2;font-size:11px;")
        tv.addWidget(lb)
        tv.addWidget(self.lb_side_root)
        v.addWidget(tip)
        return side

    # -------------------------------------------------------------- 顶栏
    def _build_topbar(self):
        bar = QFrame()
        bar.setObjectName("topbar")
        bar.setFixedHeight(62)
        h = QHBoxLayout(bar)
        h.setContentsMargins(20, 0, 18, 0)
        h.setSpacing(12)
        self.lb_page_title = QLabel("初始化归档目录")
        self.lb_page_title.setObjectName("h2")
        self.lb_page_sub = QLabel("")
        self.lb_page_sub.setObjectName("sub")
        box = QVBoxLayout()
        box.setSpacing(1)
        box.addWidget(self.lb_page_title)
        box.addWidget(self.lb_page_sub)
        h.addLayout(box)
        h.addStretch(1)
        self.chip_root = Chip("未设置归档根目录", skin.TEXT_MUTED)
        self.chip_root.setCursor(Qt.PointingHandCursor)
        self.chip_root.setToolTip("点击可快速设置归档根目录")
        h.addWidget(self.chip_root)
        b_help = QPushButton("  使用说明")
        b_help.setObjectName("ghost")
        b_help.setIcon(skin.icon("help", 16, skin.TEXT_SUB))
        b_help.clicked.connect(lambda: HelpDialog(self).exec())
        h.addWidget(b_help)
        return bar

    # -------------------------------------------------------------- 导航
    TITLES = [
        ("初始化归档目录", "按分类树创建一级 / 二级分类文件夹，一个归档根目录只需初始化一次"),
        ("文件归档", "选择待归档科研数据 → 选择分类目录 → 复制归档（保留原始文件）"),
        ("归档自查", "随机抽样复核归档结果，勾选问题文件并一键导出清单"),
        ("数据台账", "归档时自动生成《科研数据元信息采集》对应的一行，可导出官方表结构的 Excel"),
    ]

    def goto(self, idx, preset=None):
        for i, b in enumerate(self.nav):
            b.setChecked(i == idx)
        self.stack.setCurrentIndex(idx)
        self.actions.setCurrentIndex(idx)
        t, s = self.TITLES[idx]
        self.lb_page_title.setText(t)
        self.lb_page_sub.setText(s)
        if preset:
            self.page_init.set_root(preset)

    def set_root(self, path):
        self.root = path or ""
        self.lb_side_root.setText(os.path.normpath(path) if path else "未设置")
        if path:
            self.lb_side_root.setToolTip(os.path.normpath(path))
            self.chip_root.setText("归档根目录：" + self._short(path))
            self.chip_root.setStyleSheet(
                f"background:{skin.PRIMARY_LT};color:{PRIMARY};border-radius:9px;"
                f"padding:3px 10px;font-size:11.5px;font-weight:600;")
            self.lb_status.setText("就绪 · 归档根目录：" + os.path.normpath(path))
        else:
            self.chip_root.setText("未设置归档根目录")
            self.chip_root.setStyleSheet(
                f"background:#EEF2F8;color:{TEXT_MUTED};border-radius:9px;"
                f"padding:3px 10px;font-size:11.5px;font-weight:600;")
            self.lb_status.setText("就绪 · 尚未选择归档根目录")
        self.page_init.set_root(path)
        self.page_arch.set_root(path)
        self.page_check.set_root(path)
        self.page_ledger.set_root(path)

    @staticmethod
    def _short(p: str, n: int = 34) -> str:
        p = os.path.normpath(p)
        return p if len(p) <= n else "…" + p[-(n - 1):]

    def notify_archive_changed(self):
        self.page_check.do_sample(silent=True)
        self.page_ledger.reload()


def _selftest(out_path: str) -> int:
    """
    打包后自检：由环境变量 RDA_SELFTEST=<结果文件> 触发，不弹任何界面。

    主要用来确认冻结后的 exe 里 openpyxl（Excel 台账导出）等依赖确实可用。
    """
    import tempfile
    import traceback
    lines = []
    try:
        lines.append("frozen=%s" % bool(getattr(sys, "frozen", False)))
        lines.append("ledger import OK")
        try:
            import openpyxl
            lines.append("openpyxl %s OK" % openpyxl.__version__)
        except Exception as e:                                        # noqa: BLE001
            lines.append("openpyxl FAIL: %r" % (e,))
        tmp = tempfile.mkdtemp(prefix="rda_selftest_")
        root = os.path.join(tmp, "arc")
        core.init_archive(root, 2)
        with open(os.path.join(tmp, "样本文档.txt"), "wb") as f:
            f.write(b"x" * 128)
        res = core.archive_files(root, [os.path.join(tmp, "样本文档.txt")],
                                 "实验与过程数据", "材料合成与加工记录")
        core.record_archive(root, res, "实验与过程数据", "材料合成与加工记录")
        rows = ledger.build_rows(root, res, "实验与过程数据", "材料合成与加工记录",
                                 ledger.default_meta())
        n = ledger.append_rows(root, rows)
        lines.append("ledger append rows=%d" % n)
        p = ledger.export_xlsx(root)
        lines.append("xlsx export OK (%d bytes)" % os.path.getsize(p))
        _h, back = ledger.read_rows(root)
        lines.append("ledger read back rows=%d" % len(back))
        lines.append("SELFTEST OK")
    except Exception:                                                 # noqa: BLE001
        lines.append("SELFTEST FAILED")
        lines.append(traceback.format_exc())
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except Exception:                                                 # noqa: BLE001
        pass
    return 0


def main():
    _st = os.environ.get("RDA_SELFTEST")
    if _st:
        return _selftest(_st)
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ResearchDataArchiver")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName(core.APP_NAME)
    app.setApplicationDisplayName(core.APP_NAME)
    ico = resource("app.ico" if sys.platform == "win32" else "app.png")
    if not os.path.isfile(ico):
        ico = resource("app.ico")
    if os.path.isfile(ico):
        app.setWindowIcon(QIcon(ico))
    app.setStyleSheet(skin.build_stylesheet())
    fa = QFont()
    fa.setFamilies(["PingFang SC", "Hiragino Sans GB", "Heiti SC",
                    "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI"])
    fa.setPixelSize(13)
    app.setFont(fa)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
