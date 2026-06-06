from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget


class BackgroundWidget(QWidget):
    def __init__(self, image_path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._image_path = image_path
        self._pixmap = QPixmap(str(image_path))
        self._overlay = QColor(5, 8, 14, 0)
        self._border = QColor(255, 255, 255, 42)

    def set_image(self, image_path: Path) -> None:
        self._image_path = image_path
        self._pixmap = QPixmap(str(image_path))
        self.update()

    def set_overlay_opacity(self, alpha: int) -> None:
        self._overlay.setAlpha(max(0, min(alpha, 255)))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        if not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        painter.fillRect(self.rect(), self._overlay)
        painter.setPen(QPen(self._border, 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        super().paintEvent(event)
