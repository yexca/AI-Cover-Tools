from __future__ import annotations

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton, QWidget

from ..icons import svg_icon
from ..i18n import Translator
from ..paths import APP_ICON


class WindowTitleBar(QFrame):
    minimize_requested = Signal()
    maximize_requested = Signal()
    close_requested = Signal()

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._translator = translator
        self._drag_position: QPoint | None = None
        self.setObjectName("WindowTitleBar")
        self.setFixedHeight(44)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 8, 0)
        layout.setSpacing(8)

        self._app_icon = QLabel()
        self._app_icon.setFixedSize(24, 24)
        self._app_icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        if APP_ICON.exists():
            self._app_icon.setPixmap(
                QPixmap(str(APP_ICON)).scaled(
                    22,
                    22,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        layout.addWidget(self._app_icon)

        self._title = QLabel(self._translator.text("app.title"))
        self._title.setObjectName("WindowTitle")
        self._title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self._title, 1)

        self._minimize_button = self._chrome_button("window-minimize")
        self._maximize_button = self._chrome_button("window-maximize")
        self._close_button = self._chrome_button("window-close")
        self._close_button.setObjectName("WindowCloseButton")

        self._minimize_button.clicked.connect(self.minimize_requested)
        self._maximize_button.clicked.connect(self.maximize_requested)
        self._close_button.clicked.connect(self.close_requested)

        layout.addWidget(self._minimize_button)
        layout.addWidget(self._maximize_button)
        layout.addWidget(self._close_button)
        self.refresh_window_state(False)
        self.retranslate(translator)

    def retranslate(self, translator: Translator) -> None:
        self._translator = translator
        self._title.setText(translator.text("app.title"))
        self._minimize_button.setToolTip(translator.text("window.minimize"))
        self.refresh_window_state(self.window().isMaximized() if self.window() else False)
        self._close_button.setToolTip(translator.text("window.close"))

    def refresh_window_state(self, maximized: bool) -> None:
        icon_name = "window-restore" if maximized else "window-maximize"
        text_key = "window.restore" if maximized else "window.maximize"
        self._maximize_button.setIcon(svg_icon(icon_name, "#f7f9fc", 18))
        self._maximize_button.setToolTip(self._translator.text(text_key))

    def is_chrome_button_at(self, position) -> bool:  # noqa: ANN001
        for button in (self._minimize_button, self._maximize_button, self._close_button):
            if button.geometry().contains(position):
                return True
        return False

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: ANN001
        if event.button() == Qt.MouseButton.LeftButton and not self.is_chrome_button_at(event.position().toPoint()):
            self.maximize_requested.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: ANN001
        window = self.window()
        if self._drag_position is not None and window and not window.isMaximized():
            window.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        window = self.window()
        if event.button() == Qt.MouseButton.LeftButton and window and not self.is_chrome_button_at(event.position().toPoint()):
            self._drag_position = event.globalPosition().toPoint() - window.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: ANN001
        self._drag_position = None
        super().mouseReleaseEvent(event)

    def _chrome_button(self, icon_name: str) -> QToolButton:
        button = QToolButton(self)
        button.setObjectName("WindowChromeButton")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setIcon(svg_icon(icon_name, "#f7f9fc", 18))
        button.setIconSize(QSize(18, 18))
        button.setFixedSize(36, 30)
        return button
