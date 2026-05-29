from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QGraphicsBlurEffect, QLabel, QWidget


class BlurLayer(QLabel):
    def __init__(self, blur_radius: float = 24.0, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setScaledContents(True)
        effect = QGraphicsBlurEffect(self)
        effect.setBlurRadius(blur_radius)
        self.setGraphicsEffect(effect)
        self._effect = effect

    def set_blur_radius(self, blur_radius: float) -> None:
        self._effect.setBlurRadius(blur_radius)


class TintLayer(QWidget):
    def __init__(self, color: QColor | None = None, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self._color = color or QColor(4, 7, 12, 86)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_opacity(self, alpha: int) -> None:
        self._color.setAlpha(max(0, min(alpha, 255)))
        self.update()

    def set_color(self, color: QColor) -> None:
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._color)
        super().paintEvent(event)
