# -*- coding: utf-8 -*-
"""
生成应用图标资源：
  app.ico                  —— Windows 多尺寸图标（PNG 内嵌 ICO）
  app.png                  —— 通用图标（macOS/Linux 窗口图标）
  icon.iconset/*.png       —— macOS 用，构建时 iconutil -c icns 转 app.icns
"""
import os
import struct
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QImage, QLinearGradient, QPainter,
                           QPainterPath)
from PySide6.QtWidgets import QApplication
from PySide6.QtSvg import QSvgRenderer

HERE = os.path.dirname(os.path.abspath(__file__))

GLYPH = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
         'stroke="#FFFFFF" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">'
         '<polygon points="12 2 2 7 12 12 22 7 12 2"/>'
         '<polyline points="2 17 12 22 22 17"/>'
         '<polyline points="2 12 12 17 22 12"/></svg>').encode()

ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]
ICONSET = {
    "icon_16x16.png": 16, "icon_16x16@2x.png": 32,
    "icon_32x32.png": 32, "icon_32x32@2x.png": 64,
    "icon_128x128.png": 128, "icon_128x128@2x.png": 256,
    "icon_256x256.png": 256, "icon_256x256@2x.png": 512,
    "icon_512x512.png": 512, "icon_512x512@2x.png": 1024,
}


def render(size: int) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    g = QLinearGradient(0, 0, 0, size)
    g.setColorAt(0.0, QColor("#3D8BF5"))
    g.setColorAt(1.0, QColor("#1450BC"))
    path = QPainterPath()
    ins = size * 0.02
    # macOS 图标惯例：四周留白更多、圆角更大
    path.addRoundedRect(QRectF(ins, ins, size - ins * 2, size - ins * 2),
                        size * 0.22, size * 0.22)
    p.fillPath(path, QBrush(g))
    hl = QLinearGradient(0, 0, 0, size * 0.5)
    hl.setColorAt(0.0, QColor(255, 255, 255, 38))
    hl.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.fillPath(path, QBrush(hl))
    pad = size * 0.235
    QSvgRenderer(QByteArray(GLYPH)).render(
        p, QRectF(pad, pad, size - pad * 2, size - pad * 2))
    p.end()
    return img


def main() -> int:
    app = QApplication(sys.argv)                     # noqa: F841  (需要 QGuiApplication)

    # --- ICO
    tmp = os.path.join(HERE, "_icon_tmp")
    os.makedirs(tmp, exist_ok=True)
    entries, blobs, offset = [], [], 6 + 16 * len(ICO_SIZES)
    for s in ICO_SIZES:
        path = os.path.join(tmp, f"{s}.png")
        render(s).save(path, "PNG")
        data = open(path, "rb").read()
        w = 0 if s >= 256 else s
        entries.append(struct.pack("<BBBBHHII", w, w, 0, 0, 1, 32, len(data), offset))
        offset += len(data)
        blobs.append(data)
    with open(os.path.join(HERE, "app.ico"), "wb") as f:
        f.write(struct.pack("<HHH", 0, 1, len(ICO_SIZES)))
        for e in entries:
            f.write(e)
        for b in blobs:
            f.write(b)
    print("app.ico ok")

    # --- 通用 PNG（非 Windows 平台的窗口图标）
    render(512).save(os.path.join(HERE, "app.png"), "PNG")
    print("app.png ok")

    # --- macOS iconset（在 macOS 上执行 iconutil -c icns icon.iconset -o app.icns）
    iset = os.path.join(HERE, "icon.iconset")
    os.makedirs(iset, exist_ok=True)
    cache = {}
    for name, size in ICONSET.items():
        if size not in cache:
            cache[size] = render(size)
        cache[size].save(os.path.join(iset, name), "PNG")
    print("icon.iconset ok:", len(ICONSET), "files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
