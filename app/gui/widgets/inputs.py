from __future__ import annotations

from PySide6.QtWidgets import QDoubleSpinBox, QSpinBox


class WheelDisabledSpinBox(QSpinBox):
    def wheelEvent(self, event) -> None:  # noqa: ANN001
        event.ignore()


class WheelDisabledDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event) -> None:  # noqa: ANN001
        event.ignore()
