from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


ICON_DIR = Path(__file__).resolve().parent / "assets" / "icons"


def svg_icon(name: str, color: QColor | str = "#f7f9fc", size: int = 24) -> QIcon:
    path = ICON_DIR / f"{name}.svg"
    data = path.read_text(encoding="utf-8").replace("currentColor", QColor(color).name())
    renderer = QSvgRenderer(QByteArray(data.encode("utf-8")))
    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)
