# -*- coding: utf-8 -*-
"""视觉皮肤：图标（内嵌 SVG）、运行时生成的 QSS 位图资源、全局样式表。"""
from __future__ import annotations

import os
import tempfile

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# ---------------------------------------------------------------- 调色板
PRIMARY = "#1F6FEB"
PRIMARY_DK = "#1758C4"
PRIMARY_LT = "#E8F1FE"
TEAL = "#0EA5A0"
SIDEBAR = "#15243C"
SIDEBAR_HOVER = "#1E3352"
SIDEBAR_LINE = "#22375A"
BG = "#F2F5FA"
CARD = "#FFFFFF"
BORDER = "#DCE5F1"
TEXT = "#1B2A41"
TEXT_SUB = "#5A6B84"
TEXT_MUTED = "#8A98AE"
OK = "#17A673"
WARN = "#E08C2B"
DANGER = "#E0475C"
INFO = "#2F80ED"

FONT = ('"PingFang SC", "Hiragino Sans GB", "Heiti SC", '
        '"Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif')
MONO = ('"SF Mono", "Menlo", "Cascadia Mono", "Consolas", monospace')

# ---------------------------------------------------------------- 图标
_ICONS = {
    "folder_plus": '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>'
                   '<line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/>',
    "inbox": '<path d="M22 12h-6l-2 3h-4l-2-3H2"/>'
             '<path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
    "clipboard": '<path d="M9 11l3 3L22 4"/>'
                 '<path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>',
    "search": '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
    "folder": '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>',
    "file": '<path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>'
            '<polyline points="13 2 13 9 20 9"/>',
    "files": '<path d="M15 2H9a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2z"/>'
             '<path d="M3 6v14a2 2 0 0 0 2 2h10"/>',
    "external": '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>'
                '<polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
                '<polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
    "help": '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>'
            '<line x1="12" y1="17" x2="12.01" y2="17"/>',
    "refresh": '<polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>'
               '<path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>',
    "check_circle": '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>'
                    '<polyline points="22 4 12 14.01 9 11.01"/>',
    "play": '<polygon points="6 3 20 12 6 21 6 3"/>',
    "sparkle": '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/>'
               '<path d="M19 15l.7 1.9L21.6 17.6 19.7 18.3 19 20.2 18.3 18.3 16.4 17.6 18.3 16.9z"/>',
    "x": '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
    "scan": '<path d="M3 7V5a2 2 0 0 1 2-2h2"/><path d="M17 3h2a2 2 0 0 1 2 2v2"/>'
            '<path d="M21 17v2a2 2 0 0 1-2 2h-2"/><path d="M7 21H5a2 2 0 0 1-2-2v-2"/>'
            '<line x1="7" y1="12" x2="17" y2="12"/>',
    "layers": '<polygon points="12 2 2 7 12 12 22 7 12 2"/>'
              '<polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>',
    "alert": '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/>'
             '<line x1="12" y1="16" x2="12.01" y2="16"/>',
    "filter": '<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>',
    "wand": '<line x1="3" y1="21" x2="14" y2="10"/><path d="M14 6l4 4"/>'
            '<path d="M18 2v3"/><path d="M21.5 5.5h-3"/><path d="M12 3l1 2 2 1-2 1-1 2-1-2-2-1 2-1z"/>',
    "info": '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/>'
            '<line x1="12" y1="8" x2="12.01" y2="8"/>',
    "table": '<rect x="3" y="3" width="18" height="18" rx="2"/>'
             '<line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/>'
             '<line x1="9" y1="3" x2="9" y2="21"/>',
    "sliders": '<line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/>'
               '<line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/>'
               '<line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/>'
               '<line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/>'
               '<line x1="17" y1="16" x2="23" y2="16"/>',
    "sheet": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
             '<polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/>'
             '<line x1="8" y1="17" x2="13" y2="17"/>',
}


def _svg(body: str, color: str, w: str = "2") -> bytes:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round">'
        f"{body}</svg>"
    ).encode("utf-8")


def pixmap(name: str, size: int = 18, color: str = TEXT, dpr: int = 3) -> QPixmap:
    r = QSvgRenderer(QByteArray(_svg(_ICONS[name], color)))
    pm = QPixmap(size * dpr, size * dpr)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    r.render(p)
    p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def icon(name: str, size: int = 18, color: str = TEXT) -> QIcon:
    return QIcon(pixmap(name, size, color))


def dual_icon(name: str, size: int = 18, off: str = "#9FB0C9", on: str = "#FFFFFF") -> QIcon:
    """用于可切换按钮：未选中 = off 颜色，选中 = on 颜色。"""
    ic = QIcon()
    ic.addPixmap(pixmap(name, size, off), QIcon.Normal, QIcon.Off)
    ic.addPixmap(pixmap(name, size, on), QIcon.Normal, QIcon.On)
    ic.addPixmap(pixmap(name, size, off), QIcon.Active, QIcon.Off)
    ic.addPixmap(pixmap(name, size, on), QIcon.Active, QIcon.On)
    return ic


# ---------------------------------------------------------------- QSS 位图资源
_ASSET_DIR = None


def _asset_dir() -> str:
    global _ASSET_DIR
    if _ASSET_DIR is None:
        d = os.path.join(tempfile.gettempdir(), "rda_skin")
        os.makedirs(d, exist_ok=True)
        _ASSET_DIR = d
    return _ASSET_DIR


def _write_png(name: str, body: str, size: int, color: str, stroke: str = "2") -> str:
    path = os.path.join(_asset_dir(), name)
    r = QSvgRenderer(QByteArray(_svg(body, color, stroke)))
    pm = QPixmap(size * 3, size * 3)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    r.render(p)
    p.end()
    pm.save(path, "PNG")
    return path.replace("\\", "/")


def _write_blank(name: str, size: int = 14) -> str:
    """透明占位图（备用）。"""
    path = os.path.join(_asset_dir(), name)
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    pm.save(path, "PNG")
    return path.replace("\\", "/")


def build_stylesheet() -> str:
    check = _write_png("chk.png", '<polyline points="4 12.5 9.5 18 20 6"/>', 16, "#FFFFFF", "3")
    dot = _write_png("dot.png", '<circle cx="12" cy="12" r="6" fill="#FFFFFF" stroke="none"/>', 16, "#FFFFFF")
    arrow_d = _write_png("ad.png", '<polyline points="4 8 12 16 20 8"/>', 14, TEXT_SUB, "2.4")
    arrow_r = _write_png("ar.png", '<polyline points="8 4 16 12 8 20"/>', 14, TEXT_SUB, "2.4")
    arrow_dd = _write_png("add.png", '<polyline points="4 8 12 16 20 8"/>', 14, TEXT_MUTED, "2.4")

    qss = """
* { font-family: @@FONT@@; }
QWidget { color: @@TEXT@@; font-size: 13px; }
QMainWindow, QDialog { background: @@BG@@; }
QToolTip {
    background: #1B2A41; color: #FFFFFF; border: none;
    padding: 6px 9px; border-radius: 6px; font-size: 12px;
}

/* ---------- 通用 ---------- */
QFrame#card {
    background: @@CARD@@; border: 1px solid @@BORDER@@; border-radius: 12px;
}
QLabel#cardTitle { font-size: 14.5px; font-weight: 700; color: @@TEXT@@; }
QLabel#cardDesc  { font-size: 12px; color: @@TEXT_MUTED@@; }
QLabel#h1 { font-size: 19px; font-weight: 700; color: @@TEXT@@; }
QLabel#h2 { font-size: 15px; font-weight: 700; color: @@TEXT@@; }
QLabel#sub { font-size: 12.5px; color: @@TEXT_SUB@@; }
QLabel#muted { font-size: 12px; color: @@TEXT_MUTED@@; }
QLabel#ok { color: @@OK@@; font-weight: 600; }
QLabel#warn { color: @@WARN@@; font-weight: 600; }
QLabel#danger { color: @@DANGER@@; font-weight: 600; }
QLabel#big { font-size: 21px; font-weight: 700; color: @@PRIMARY@@; }
QLabel#mono { font-family: @@MONO@@ ; font-size: 12px; color: @@TEXT_SUB@@; }

/* ---------- 侧边栏 ---------- */
QFrame#sidebar { background: @@SIDEBAR@@; border: none; }
QLabel#brand { color: #FFFFFF; font-size: 16px; font-weight: 700; }
QLabel#brandSub { color: #7C90AE; font-size: 11px; }
QLabel#navGroup { color: #61789B; font-size: 11px; font-weight: 700; }
QPushButton#nav {
    text-align: left; padding: 0 14px; border: none; border-radius: 9px;
    color: #A9BAD3; font-size: 13.5px; min-height: 42px; background: transparent;
}
QPushButton#nav:hover { background: @@SIDEBAR_HOVER@@; color: #FFFFFF; }
QPushButton#nav:checked { background: @@PRIMARY@@; color: #FFFFFF; font-weight: 600; }
QFrame#sideFoot { background: @@SIDEBAR@@; border-top: 1px solid @@SIDEBAR_LINE@@; }
QLabel#sideFootTxt { color: #6C82A5; font-size: 11px; }

/* ---------- 顶栏 / 底部操作条 ---------- */
QFrame#topbar { background: @@CARD@@; border-bottom: 1px solid @@BORDER@@; }
QFrame#actionbar { background: @@CARD@@; border-top: 1px solid @@BORDER@@; }

/* ---------- 按钮 ---------- */
QPushButton {
    background: @@CARD@@; color: @@TEXT@@; border: 1px solid @@BORDER@@;
    border-radius: 8px; padding: 8px 15px; min-height: 20px;
}
QPushButton:hover { border-color: #B9CBDF; background: #F7FAFF; }
QPushButton:pressed { background: #EDF3FC; }
QPushButton:disabled { color: #AAB6C6; background: #F5F7FA; border-color: #E6ECF4; }

QPushButton#primary {
    background: @@PRIMARY@@; color: #FFFFFF; border: 1px solid @@PRIMARY@@; font-weight: 600;
}
QPushButton#primary:hover { background: #2C7CF0; border-color: #2C7CF0; }
QPushButton#primary:pressed { background: @@PRIMARY_DK@@; border-color: @@PRIMARY_DK@@; }
QPushButton#primary:disabled { background: #B8CDF0; border-color: #B8CDF0; color: #F0F5FF; }

QPushButton#ghost {
    background: transparent; border: 1px solid @@BORDER@@; color: @@TEXT_SUB@@;
}
QPushButton#ghost:hover { background: #F5F9FF; border-color: #B9CBDF; color: @@TEXT@@; }

QPushButton#link {
    background: transparent; border: none; color: @@PRIMARY@@; padding: 4px 6px;
    font-size: 12.5px; text-decoration: underline;
}
QPushButton#link:hover { color: @@PRIMARY_DK@@; }

QPushButton#dangerBtn {
    background: @@CARD@@; color: @@DANGER@@; border: 1px solid #F3CDD4;
}
QPushButton#dangerBtn:hover { background: #FDF3F5; }

QPushButton#seg {
    background: @@CARD@@; border: 1px solid @@BORDER@@; color: @@TEXT_SUB@@;
    padding: 6px 14px; border-radius: 7px;
}
QPushButton#seg:hover { background: #F7FAFF; }
QPushButton#seg:checked {
    background: @@PRIMARY@@; color: #FFFFFF; border-color: @@PRIMARY@@; font-weight: 600;
}

/* ---------- 输入 ---------- */
QLineEdit {
    background: @@CARD@@; border: 1px solid @@BORDER@@; border-radius: 8px;
    padding: 8px 11px; selection-background-color: @@PRIMARY_LT@@; selection-color: @@TEXT@@;
}
QLineEdit:focus { border: 1px solid @@PRIMARY@@; }
QLineEdit#path { font-family: @@MONO@@; font-size: 12px; color: @@TEXT_SUB@@; background: #F8FAFD; }
QLineEdit#path:focus { background: @@CARD@@; }

QComboBox {
    background: @@CARD@@; border: 1px solid @@BORDER@@; border-radius: 8px;
    padding: 7px 10px; min-height: 20px;
}
QComboBox:hover { border-color: #B9CBDF; }
QComboBox:focus { border: 1px solid @@PRIMARY@@; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow { image: url(@@ARROW_D@@); width: 13px; height: 13px; }
QComboBox QAbstractItemView {
    background: @@CARD@@; border: 1px solid @@BORDER@@; border-radius: 8px;
    padding: 4px; outline: none; selection-background-color: @@PRIMARY_LT@@;
    selection-color: @@TEXT@@;
}

QSpinBox {
    background: @@CARD@@; border: 1px solid @@BORDER@@; border-radius: 8px; padding: 6px 8px;
}

/* ---------- 复选框 / 单选 ---------- */
QCheckBox, QRadioButton { spacing: 7px; color: @@TEXT@@; }
QCheckBox::indicator, QRadioButton::indicator { width: 16px; height: 16px; }
QCheckBox::indicator {
    border: 1px solid #C4D2E4; border-radius: 4px; background: @@CARD@@;
}
QCheckBox::indicator:hover { border-color: @@PRIMARY@@; }
QCheckBox::indicator:checked {
    background: @@PRIMARY@@; border-color: @@PRIMARY@@; image: url(@@CHK@@);
}
QCheckBox::indicator:indeterminate {
    background: @@PRIMARY@@; border-color: @@PRIMARY@@;
}
QRadioButton::indicator {
    border: 1px solid #C4D2E4; border-radius: 8px; background: @@CARD@@;
}
QRadioButton::indicator:hover { border-color: @@PRIMARY@@; }
QRadioButton::indicator:checked {
    background: @@PRIMARY@@; border-color: @@PRIMARY@@; image: url(@@DOT@@);
}

/* ---------- 表格 ---------- */
QTableWidget, QTableView {
    background: @@CARD@@; border: 1px solid @@BORDER@@; border-radius: 10px;
    gridline-color: #EDF2F9; outline: none;
    selection-background-color: @@PRIMARY_LT@@; selection-color: @@TEXT@@;
    alternate-background-color: #FAFCFF;
}
QTableWidget::item { padding: 6px 8px; border: none; }
QTableWidget::item:selected { background: @@PRIMARY_LT@@; color: @@TEXT@@; }
QHeaderView { background: transparent; }
QHeaderView::section {
    background: #F6F9FD; color: @@TEXT_SUB@@; padding: 8px 8px; border: none;
    border-bottom: 1px solid @@BORDER@@; border-right: 1px solid #EDF2F9;
    font-weight: 600; font-size: 12.5px;
}
QHeaderView::section:first { border-top-left-radius: 10px; }
QHeaderView::section:last { border-top-right-radius: 10px; border-right: none; }
QTableCornerButton::section { background: #F6F9FD; border: none; }

/* ---------- 树 ---------- */
QTreeWidget {
    background: @@CARD@@; border: 1px solid @@BORDER@@; border-radius: 10px;
    outline: none; padding: 4px;
    selection-background-color: @@PRIMARY_LT@@; selection-color: @@TEXT@@;
}
QTreeWidget::item { height: 27px; border-radius: 6px; padding-right: 6px; }
QTreeWidget::item:hover { background: #F4F8FF; }
QTreeWidget::item:selected { background: @@PRIMARY_LT@@; color: @@TEXT@@; }
QTreeWidget::branch { background: transparent; }

/* ---------- 进度条 ---------- */
QProgressBar {
    background: #EDF2F9; border: none; border-radius: 5px; height: 10px;
    text-align: center; color: transparent;
}
QProgressBar::chunk { background: @@PRIMARY@@; border-radius: 5px; }

/* ---------- 滚动条 ---------- */
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical {
    background: #CBD7E7; border-radius: 5px; min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: #AFC1DA; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #CBD7E7; border-radius: 5px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QTextEdit, QPlainTextEdit {
    background: #F8FAFD; border: 1px solid @@BORDER@@; border-radius: 8px;
    font-family: @@MONO@@; font-size: 12px; color: @@TEXT_SUB@@; padding: 6px;
}

QStatusBar { background: @@CARD@@; border-top: 1px solid @@BORDER@@; color: @@TEXT_MUTED@@; }
QStatusBar::item { border: none; }

QGroupBox {
    border: 1px solid @@BORDER@@; border-radius: 10px; margin-top: 12px;
    background: @@CARD@@; font-weight: 600; color: @@TEXT_SUB@@;
}
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }

QSplitter::handle { background: transparent; }
"""
    for k, v in {
        "@@FONT@@": FONT, "@@MONO@@": MONO, "@@PRIMARY@@": PRIMARY, "@@PRIMARY_DK@@": PRIMARY_DK,
        "@@PRIMARY_LT@@": PRIMARY_LT, "@@SIDEBAR@@": SIDEBAR, "@@SIDEBAR_HOVER@@": SIDEBAR_HOVER,
        "@@SIDEBAR_LINE@@": SIDEBAR_LINE, "@@BG@@": BG, "@@CARD@@": CARD, "@@BORDER@@": BORDER,
        "@@TEXT@@": TEXT, "@@TEXT_SUB@@": TEXT_SUB, "@@TEXT_MUTED@@": TEXT_MUTED,
        "@@OK@@": OK, "@@WARN@@": WARN, "@@DANGER@@": DANGER, "@@INFO@@": INFO,
        "@@CHK@@": check, "@@DOT@@": dot, "@@ARROW_D@@": arrow_d,
        "@@ARROW_R@@": arrow_r, "@@ARROW_DD@@": arrow_dd,
    }.items():
        qss = qss.replace(k, v)
    return qss
